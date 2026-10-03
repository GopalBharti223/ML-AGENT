"""Wikipedia Pageviews Provider — general-purpose entity comparison.

Source: Wikimedia REST API (official pageview metrics) + the
MediaWiki opensearch API for title resolution.
  - Pageviews: https://wikimedia.org/api/rest_v1/#/Pageviews data
  - Title search: https://en.wikipedia.org/w/api.php (opensearch)
License: public REST API, no key required (Wikimedia asks for a
descriptive User-Agent and polite rates).
Commercial use: ALLOWED (see provider catalog).

CRITICAL HONESTY CONTRACT (Tier-2c):

Wikipedia pageviews measure PUBLIC SEARCH INTEREST / attention.
They are NOT sales, revenue, viewership, skill, or any real-world
performance metric.  Stories generated from this provider must be
framed as interest/attention comparisons ("who is searched about
more", "most-searched"), never "who sells more" / "who is richer".
The indicator name, metric name, and metadata all carry this
framing, and the script prompt receives it verbatim.

Design contract:

- Same DataProvider interface as the other providers (base.py).
- Same normalized country/country_code-shaped schema: the
  compared ENTITIES occupy the country/country_code columns so
  the existing resolver, scoring, rendering, and metadata
  pipeline work without special-casing.
- The optional `countries` fetch parameter carries the requested
  ENTITY article titles (this provider supports_countries() ->
  True, so the manual path's existing hint plumbing delivers
  them; every other provider keeps ignoring the hint).
- Only real pageview numbers returned by the API are used.
  Entities whose article titles cannot be verified against the
  pageview API are dropped with a logged warning, never
  fabricated.  Fewer than 2 verifiable entities -> RuntimeError
  (the engine catches it and skips, per the established
  never-crash convention).
- NOT part of the automatic provider rotation: without an entity
  hint there is no meaningful default dataset, so this provider
  is only reachable from the manual entity-comparison route.
"""
import time
from datetime import date
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote

import pandas as pd
import requests

from app.data.providers.base import (
    DataProvider,
    DataProviderResult,
    IndicatorInfo,
)


class WikipediaPageviewsProvider(DataProvider):

    provider_id = "wikipedia"
    provider_name = "Wikipedia Pageviews"
    source_url = "https://wikimedia.org/api/rest_v1/"
    base_url = (
        "https://wikimedia.org/api/rest_v1/metrics/"
        "pageviews/per-article"
    )
    search_api = "https://en.wikipedia.org/w/api.php"
    request_timeout = 30
    max_retries = 3
    retry_delay = 1.0

    # Politeness spacing between REST calls (Wikimedia asks for
    # modest, identified traffic; we also send a real UA below).
    request_spacing = 0.15

    # The pageview API has no data before this year.
    pageview_data_start_year = 2015

    # Marks this provider as the entity-comparison route used by
    # the manual resolver (manual_topic.py reads this flag to
    # relax the >=3-entity quality gates to >=2 for this path).
    entity_comparison = True

    INDICATORS: Dict[str, Dict] = {
        "search_interest": {
            "name": "Wikipedia Search Interest (Pageviews)",
            "category": "Public Interest",
        },
    }

    @classmethod
    def list_indicators(cls) -> List[IndicatorInfo]:
        return [
            IndicatorInfo(
                code=code,
                name=config["name"],
                category=config["category"],
                source_url=cls.source_url,
            )
            for code, config in cls.INDICATORS.items()
        ]

    # =====================================================
    # HTTP
    # =====================================================

    @staticmethod
    def _headers() -> Dict[str, str]:
        return {
            "User-Agent": (
                "MyShorts-DataFactory/1.0 "
                "(mailto:myshorts-datafactory@example.org)"
            )
        }

    @classmethod
    def _request_json(
        cls,
        url: str,
        params: Optional[Dict] = None,
    ) -> Optional[Dict]:
        """GET JSON with retries.

        Returns None for HTTP 404 (no data for this exact
        article/window) so callers can distinguish "absent" from
        "failed".  Other failures raise RuntimeError after the
        retries are exhausted -- callers own the graceful-skip
        policy, matching the other providers' style.
        """
        last_error: Optional[Exception] = None

        for attempt in range(cls.max_retries):

            if attempt:
                time.sleep(cls.retry_delay * attempt)

            try:
                response = requests.get(
                    url,
                    params=params,
                    timeout=cls.request_timeout,
                    headers=cls._headers(),
                )
            except requests.RequestException as error:
                last_error = error
                continue

            if response.status_code == 404:
                return None

            if response.status_code in (429, 503):
                # Rate limited / temporarily unavailable.
                last_error = RuntimeError(
                    f"HTTP {response.status_code} from Wikimedia"
                )
                time.sleep(cls.retry_delay * (attempt + 1))
                continue

            response.raise_for_status()

            time.sleep(cls.request_spacing)

            return response.json()

        raise RuntimeError(
            f"Wikimedia request failed after "
            f"{cls.max_retries} attempts: {last_error}"
        )

    # =====================================================
    # TITLE RESOLUTION (opensearch)
    # =====================================================

    @classmethod
    def article_title_candidates(
        cls,
        name: str,
        limit: int = 3,
    ) -> List[str]:
        """Opensearch a name into ranked Wikipedia article titles.

        Used both to map a display name to its canonical article
        and to provide ALTERNATE titles when the first candidate
        has no pageview data (disambiguation retry).
        """
        query = str(name or "").strip()

        if not query:
            return []

        try:
            payload = cls._request_json(
                cls.search_api,
                params={
                    "action": "opensearch",
                    "search": query,
                    "limit": max(1, int(limit)),
                    "namespace": 0,
                    "format": "json",
                    "redirects": "resolve",
                },
            )
        except Exception:
            return []

        # opensearch returns [query, [titles], [descs], [urls]].
        if (
            not isinstance(payload, list)
            or len(payload) < 2
            or not isinstance(payload[1], list)
        ):
            return []

        titles = [
            str(title).strip()
            for title in payload[1]
            if str(title or "").strip()
        ]

        return titles

    # =====================================================
    # PAGEVIEWS
    # =====================================================

    @classmethod
    def _yearly_views(
        cls,
        title: str,
        start_year: int,
        end_year: int,
    ) -> Dict[int, float]:
        """Total daily pageviews per year for one article.

        Requests are made per calendar year so a single missing
        year never blocks the rest.  Years before the API's data
        window are skipped.  Returns {} when the article has no
        pageview data at all.
        """
        safe_title = quote(str(title or "").strip(), safe="")

        if not safe_title:
            return {}

        views_by_year: Dict[int, float] = {}

        for year in range(
            max(int(start_year), cls.pageview_data_start_year),
            int(end_year) + 1,
        ):
            url = (
                f"{cls.base_url}/en.wikipedia/all-access/user/"
                f"{safe_title}/daily/"
                f"{year}0101/{year}1231"
            )

            payload = cls._request_json(url)

            if payload is None:
                # 404: no data for this article/window.  A missing
                # FIRST year usually means the article did not
                # exist yet -- keep trying later years.
                continue

            total = 0.0

            for item in payload.get("items", []) or []:
                try:
                    total += float(item.get("views", 0) or 0)
                except (TypeError, ValueError):
                    continue

            if total > 0:
                views_by_year[year] = total

        return views_by_year

    @classmethod
    def probe_entities(
        cls,
        proposals: List[Dict[str, str]],
        probe_year: Optional[int] = None,
    ) -> Tuple[Dict[str, str], List[str]]:
        """Verify proposed entities actually have pageview data.

        proposals: [{"name": <display>, "title": <wikipedia title>}]

        Each proposal is resolved against opensearch (the proposed
        title plus ranked alternate titles) and every candidate is
        probed against the pageview API for `probe_year`.

        Selection rule 1 — the exact entity wins: prefer the
        candidate whose title case-insensitively equals the
        proposed title.  The pageview REST API is case-sensitive:
        the canonical article is "IPhone 13" while the natural
        user/LLM spelling is "iPhone 13", which resolves through a
        tiny redirect page that still reports a few pageviews.  A
        naive first-match-with-any-data rule would lock in that
        sparse redirect (dozens of views) and never reach the real
        article (hundreds of thousands) -- the exact-title rule
        lands on the canonical, correctly-cased article.

        Selection rule 2 — safe fallback: when NO candidate matches
        the proposed title (ambiguous/common words), fall back to
        the candidate with the most pageview data.  Never chase a
        higher-view UNRELATED article ("Samsung Galaxy S25",
        "List of iPhone models") when the requested entity has its
        own article.

        Returns (verified, failed) where verified maps display
        name -> verified article title, and failed lists display
        names with no usable data.  NEVER raises for a missing
        entity -- dropping and logging is the contract.
        """
        if probe_year is None:
            probe_year = date.today().year - 1

        verified: Dict[str, str] = {}
        failed: List[str] = []

        for proposal in proposals:

            name = str(
                (proposal or {}).get("name", "")
            ).strip()

            proposed_title = str(
                (proposal or {}).get("title", "")
            ).strip()

            if not name:
                continue

            candidates = []

            if proposed_title:
                candidates.append(proposed_title)

            for candidate in cls.article_title_candidates(name):
                if candidate not in candidates:
                    candidates.append(candidate)

            best_title = None
            best_views = 0.0
            best_exact = False

            # Case-insensitive canonical target: resolve to the
            # article that actually IS the requested entity before
            # considering any unrelated higher-view candidate.
            target = (
                str(proposed_title).casefold()
                if proposed_title
                else ""
            )

            for title in candidates:

                try:
                    views_by_year = cls._yearly_views(
                        title,
                        int(probe_year),
                        int(probe_year),
                    )
                except Exception:
                    continue

                total = 0.0

                for value in views_by_year.values():
                    total += float(value)

                if total <= 0:
                    continue

                is_exact = (
                    bool(target)
                    and str(title).casefold() == target
                )

                if best_title is None:
                    best_title = title
                    best_views = total
                    best_exact = is_exact

                # An exact-title candidate always outranks an
                # unrelated higher-view article ("IPhone 13" over
                # "List of iPhone models").
                elif is_exact and not best_exact:
                    best_title = title
                    best_views = total
                    best_exact = True

                # Same class: prefer the one with more pageviews
                # (canonical case usually wins on size too).
                elif is_exact == best_exact and total > best_views:
                    best_title = title
                    best_views = total

            if best_title is not None:
                verified[name] = best_title

            else:
                failed.append(name)

        return verified, failed

    # =====================================================
    # FETCH NORMALIZED
    # =====================================================

    @classmethod
    def fetch_normalized(
        cls,
        indicator_code: str,
        years: int = 10,
        story_type: str = "fastest_growth",
        min_countries: int = 6,
        countries=None,
    ) -> DataProviderResult:
        """Pageviews per year for the requested ENTITIES.

        `countries` carries the requested entity ARTICLE TITLES
        (the manual entity-comparison route delivers them through
        the standard hint plumbing).  Every entity with usable
        data is guaranteed a row; entities without pageview data
        are dropped with a logged warning.
        """
        config = cls.INDICATORS.get(indicator_code)

        if not config:
            raise ValueError(
                f"Unknown indicator: {indicator_code}"
            )

        entities = [
            str(entity).strip()
            for entity in (countries or [])
            if str(entity or "").strip()
        ]

        if len(entities) < 2:
            raise RuntimeError(
                "Wikipedia pageviews provider compares named "
                "entities and needs at least 2 requested entity "
                "article titles via the 'countries' hint; got "
                f"{len(entities)}."
            )

        # Completed years only (the current year is partial).
        end_year = date.today().year - 1
        start_year = max(
            end_year - max(1, int(years)) + 1,
            cls.pageview_data_start_year,
        )

        # Verify every requested entity FIRST (reject/retry with
        # an alternate title when the pageview API has nothing).
        proposals = [
            {"name": entity, "title": entity}
            for entity in entities
        ]

        verified, failed = cls.probe_entities(
            proposals,
            probe_year=end_year,
        )

        if failed:
            print(
                "  [WIKIPEDIA] No usable pageview data for: "
                f"{', '.join(failed)} (dropped, real data only)"
            )

        if len(verified) < 2:
            raise RuntimeError(
                "Wikipedia pageviews provider verified only "
                f"{len(verified)} of {len(entities)} requested "
                "entities with pageview data; refusing to "
                "compare fewer than 2."
            )

        rows = []

        for name, title in verified.items():
            try:
                views_by_year = cls._yearly_views(
                    title,
                    start_year,
                    end_year,
                )
            except Exception as error:
                print(
                    f"  [WIKIPEDIA] '{title}' pageview fetch "
                    f"failed: {error}"
                )
                continue

            for year, value in sorted(views_by_year.items()):
                rows.append(
                    {
                        "country": name,
                        "country_code": title,
                        "year": int(year),
                        "metric": config["name"],
                        "value": float(value),
                        "provider": cls.provider_id,
                        "source_name": cls.provider_name,
                        "source_url": cls.source_url,
                        "indicator_code": indicator_code,
                    }
                )

        if not rows:
            return cls._empty_result(indicator_code, config)

        df = pd.DataFrame(rows)

        wide = df.pivot(
            index=["country_code", "country"],
            columns="year",
            values="value",
        )

        wide = wide.sort_index(axis=1)

        # Keep entities with a reasonable share of the window
        # (same loose threshold convention as the jikan provider).
        wide = wide.dropna(
            thresh=max(2, int(len(wide.columns) * 0.4))
        )

        if wide.empty or len(wide) < 2:
            return cls._empty_result(indicator_code, config)

        normalized = pd.DataFrame(rows)

        return cls._result(
            indicator_code, config, wide, normalized
        )
    @classmethod
    def _result(
        cls,
        indicator_code: str,
        config: Dict,
        wide: pd.DataFrame,
        normalized: pd.DataFrame,
    ) -> DataProviderResult:
        metadata = {
            "provider": cls.provider_id,
            "source_name": cls.provider_name,
            "source_url": cls.source_url,
            "indicator_code": indicator_code,
            "indicator_name": config["name"],
            "category": config["category"],
            # Honesty framing (Tier-2c): pageviews are a public
            # interest metric, never sales/revenue/performance.
            "metric_meaning": (
                "public search interest (Wikipedia pageviews); "
                "NOT sales, revenue, or real-world performance"
            ),
        }

        wide.attrs.update(metadata)
        wide.attrs["normalized_data"] = normalized

        return DataProviderResult(
            provider=cls.provider_id,
            indicator_code=indicator_code,
            metric_name=config["name"],
            source_name=cls.provider_name,
            source_url=cls.source_url,
            normalized_data=normalized,
            wide_data=wide,
            metadata=metadata,
        )

    @classmethod
    def _empty_result(
        cls,
        indicator_code: str,
        config: Dict,
    ) -> DataProviderResult:
        empty_df = pd.DataFrame()
        metadata = {
            "provider": cls.provider_id,
            "source_name": cls.provider_name,
            "source_url": cls.source_url,
            "indicator_code": indicator_code,
            "indicator_name": config["name"],
            "category": config["category"],
        }
        return DataProviderResult(
            provider=cls.provider_id,
            indicator_code=indicator_code,
            metric_name=config["name"],
            source_name=cls.provider_name,
            source_url=cls.source_url,
            normalized_data=empty_df,
            wide_data=empty_df,
            metadata=metadata,
        )
