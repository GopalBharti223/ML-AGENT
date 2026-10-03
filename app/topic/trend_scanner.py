"""
Trending-topic auto-scanner (B2).

Pulls today's trending topics from four free, keyless sources:

  1. Google Trends daily-trends RSS   (explicit search volume)
  2. Google News category RSS         (news coverage per category)
  3. CoinGecko trending coins         (crypto)
  4. Hacker News top stories          (tech)

...then normalizes each headline/term into lowercase keywords and
matches them against the provider indicator catalog via
DataProviderRegistry -- surfacing ONLY candidates whose underlying
provider is currently healthy (circuit closed) and configured
(API key present), i.e. topics the pipeline can ACTUALLY generate
content for today.

Output: 3-5 vetted candidates written to trend_candidates.json
(repo root) plus a console printout.  Intended to be run manually
(the morning check); the interactive menu in run.py displays the
latest saved candidates above the topic prompt.

Defensive posture (matching provider conventions): every source
fetch is individually guarded -- a failed/slow source is skipped
with a warning and never fails the scan.  Matching and output are
pure-local operations.
"""

import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import requests

from app.data.providers.registry import DataProviderRegistry
from app.data.providers.health import provider_health


# ---------------------------------------------------------
# CONFIG
# ---------------------------------------------------------

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "MetricForgeTrendScanner/1.0"
)

REQUEST_TIMEOUT_S = 15

# Candidate JSON lives at the repo root (next to run.py).

OUTPUT_PATH = (
    Path(__file__).resolve().parents[2]
    / "trend_candidates.json"
)

MAX_CANDIDATES = 5

# Words that never make useful topic keywords on their own.

STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "in", "on", "for",
    "to", "with", "at", "by", "from", "as", "is", "are", "was",
    "were", "be", "been", "new", "news", "update", "updates",
    "latest", "report", "reports", "says", "said", "after",
    "before", "over", "under", "into", "about", "amid", "vs",
    "how", "why", "what", "who", "when", "where", "this",
    "that", "these", "those", "will", "can", "could", "should",
    "more", "most", "than", "then", "best", "top", "first",
    "watch", "live", "video", "game", "games", "match",
    "today", "week", "month", "year", "years", "day", "days",
    "just", "now", "get", "got", "has", "have", "had", "his",
    "her", "its", "their", "our", "your", "not", "but", "all",
    "out", "up", "down", "one", "two", "three", "big", "war",
    "world", "time", "back", "off", "again", "still", "ever",
}

# Source ranking: explicit search volume beats passive
# news coverage; crypto/tech beat generic headlines.

SOURCE_WEIGHTS = {
    "google_trends": 3,
    "coingecko": 2,
    "hacker_news": 2,
    "google_news": 1,
}


# ---------------------------------------------------------
# SOURCE FETCHERS (each individually guarded)
# ---------------------------------------------------------

def _http_get(
    url: str
) -> str:

    """
    GET with a browser UA and a hard timeout; returns response
    text or raises.  Callers wrap in try/except.
    """

    response = requests.get(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "*/*",
        },
        timeout=REQUEST_TIMEOUT_S,
    )

    response.raise_for_status()

    return response.text


def fetch_google_trends(
    geo: str = "US"
) -> list:

    """
    Google Trends daily-trends RSS: returns raw trending
    phrases (list of str), roughly 10-20 per geo per day.
    """

    url = (
        "https://trends.google.com/trending/rss"
        f"?geo={geo}"
    )

    xml_text = _http_get(url)

    root = ET.fromstring(xml_text)

    phrases = []

    for item in root.iter("item"):

        title = item.findtext("title")

        if title and title.strip():

            phrases.append(title.strip())

    return phrases


def fetch_google_news(
    query: str,
    when: str = "1d",
    limit: int = 30
) -> list:

    """
    Google News search RSS: returns recent headline strings
    for one query (e.g. 'economy OR inflation').
    """

    url = (
        "https://news.google.com/rss/search"
        f"?q={requests.utils.quote(query)}"
        f"+when:{when}&hl=en-US&gl=US&ceid=US:en"
    )

    xml_text = _http_get(url)

    root = ET.fromstring(xml_text)

    headlines = []

    for item in root.iter("item"):

        title = item.findtext("title")

        if title and title.strip():

            headlines.append(title.strip())

        if len(headlines) >= limit:

            break

    return headlines


def fetch_coingecko() -> list:

    """
    CoinGecko trending coins: returns coin names and symbols
    ('bitcoin', 'btc', ...) -- the crypto category input.
    """

    url = (
        "https://api.coingecko.com/api/v3"
        "/search/trending"
    )

    text = _http_get(url)

    payload = json.loads(text)

    phrases = []

    for coin in payload.get("coins", []):

        item = coin.get("item", {}) or {}

        name = (item.get("name") or "").strip()

        symbol = (
            item.get("symbol") or ""
        ).strip()

        if name:

            phrases.append(name)

        if symbol and symbol.lower() != name.lower():

            phrases.append(symbol)

    return phrases


def fetch_hacker_news(
    limit: int = 12
) -> list:

    """
    Hacker News front page: returns story titles (tech-heavy).
    """

    ids_text = _http_get(
        "https://hacker-news.firebaseio.com/v0"
        "/topstories.json"
    )

    story_ids = json.loads(ids_text)[:limit]

    titles = []

    for story_id in story_ids:

        try:

            item_text = _http_get(
                "https://hacker-news.firebaseio.com/v0"
                f"/item/{story_id}.json"
            )

            item = json.loads(item_text) or {}

            title = (item.get("title") or "").strip()

            if title:

                titles.append(title)

        except (
            requests.RequestException,
            ValueError,
        ):

            # One dead story id never fails the source.

            continue

    return titles


# ---------------------------------------------------------
# NORMALIZATION
# ---------------------------------------------------------

_WORD_RE = re.compile(r"[a-z0-9#]+")


def normalize_keywords(
    phrases: list
) -> list:

    """
    Raw headline/term strings -> deduplicated lowercase
    keyword candidates (full phrases kept intact AND their
    significant individual words split out, since the
    indicator catalog matches on substring).
    """

    keywords = []

    seen = set()

    def _add(candidate: str):

        candidate = candidate.strip().lower()

        if (
            len(candidate) < 3
            or len(candidate) > 60
            or candidate in seen
        ):

            return

        seen.add(candidate)

        keywords.append(candidate)

    for phrase in phrases or []:

        phrase = str(phrase or "").strip()

        if not phrase:

            continue

        # Hyphen/slash-separated compounds become spaces
        # ("US-China" -> "us china").

        cleaned = re.sub(
            r"[-–—/|]+", " ", phrase
        )

        _add(cleaned)

        words = _WORD_RE.findall(cleaned.lower())

        significant = [
            word
            for word in words
            if len(word) >= 4
            and word not in STOPWORDS
            and not word.isdigit()
        ]

        for word in significant:

            _add(word)

    return keywords


# ---------------------------------------------------------
# CATALOG MATCHING (provider-aware)
# ---------------------------------------------------------

def _has_word_boundary(
    keyword: str,
    *fields: str,
) -> bool:
    """
    True if `keyword` (or, failing that, its first token) appears
    as a WHOLE WORD ins any of `fields` -- not as a substring.

    Examples: "ship" vs "F1 Driver Championship Points" ->
    False (inside "championship");"finance" vs "General
    government gross debt (Public Finance)" -> True (category).)
    """

    pattern = re.compile(
        r"(?<![a-z0-9])"
        + re.escape(keyword.lower())
        + r"(?![a-z0-9])"
    )

    for field in fields:

        if field and pattern.search(
            str(field).lower()
        ):

            return True

    # Fallback: the first token (e.g. "bitcoin price" ->
    # match on "bitcoin") -- still word-bounded.


    parts = keyword.lower().split()
    if len(parts) > 1:

        first_pattern = re.compile(
            r"(?<![a-z0-9])"
            + re.escape(parts[0])
            + r"(?![a-z0-9])"
        )

        for field in fields:

            if field and first_pattern.search(
                str(field).lower()
            ):

                return True

    return False


def match_keywords_to_indicators(
    keywords: list,
    max_keywords: int = 120
) -> list:

    """
    Run each keyword against every healthy+configured
    provider's indicator catalog.

    Returns a list of match dicts:
      {keyword, source, provider_id, provider_name,
       indicator_code, indicator_name, category}

    Registry-level search_indicators() is NOT used here
    because IndicatorInfo carries no provider id -- iterating
    per provider keeps provenance for the health gate.
    """

    matches = []

    seen_keys = set()

    checked = 0

    for provider_id in (
        DataProviderRegistry.list_providers()
    ):

        provider = DataProviderRegistry.get(
            provider_id
        )

        # Key-gated providers (football_data, rawg) and
        # circuit-open providers are skipped: a trending
        # keyword pointing at a down source is a dead
        # candidate today.

        if not provider.is_configured():

            continue

        if not provider_health.is_available(
            provider_id
        ):

            continue

        for keyword in keywords[:max_keywords]:

            checked += 1

            try:

                hits = provider.search_indicators(
                    keyword
                )

            except Exception:

                continue

            for indicator in hits:
                # Word-boundary re-check: 'ship' must NOT match
                # 'championship', 'rank' must NOT match 'frank'.
                # The provider catalogs substring-match, which is too
                # loose for trending keywords -- re-verify here so the
                # morning list is topical, not noise.
                if not _has_word_boundary(
                    keyword,
                    indicator.name,
                    indicator.code,
                    indicator.category,
                ):
                    continue

                key = (
                    provider_id,
                    indicator.code,
                )

                if key in seen_keys:

                    continue

                seen_keys.add(key)

                matches.append(
                    {
                        "keyword": keyword,
                        "provider_id": provider_id,
                        "provider_name": getattr(
                            provider,
                            "provider_name",
                            provider_id,
                        ),
                        "indicator_code": indicator.code,
                        "indicator_name": indicator.name,
                        "category": indicator.category,
                    }
                )

    return matches


# ---------------------------------------------------------
# SCAN ORCHESTRATOR
# ---------------------------------------------------------

def _fetch_all_sources() -> tuple:
    """
    Pull every source; each failure is logged and skipped.
    Returns (keywords, source_of_keyword) where source_of maps
    each keyword to the highest-weight source it came from.
    """

    keyword_source = {}

    buckets = {
        "google_trends": [],
        "google_news": [],
        "coingecko": [],
        "hacker_news": [],
    }

    # 1. Google Trends daily RSS (explicit search volume)

    try:

        buckets["google_trends"] = (
            fetch_google_trends()
        )

        print(
            f"  [google_trends] "
            f"{len(buckets['google_trends'])} phrases"
        )

    except Exception as trends_error:

        print(
            f"  [google_trends] SKIPPED: "
            f"{type(trends_error).__name__}: "
            f"{trends_error}"
        )

    # 2. Google News category RSS (broad category queries
    #    aligned with the pipeline's content families)

    news_queries = (
        "economy OR inflation OR gdp",
        "technology OR artificial intelligence",
        "sports OR football OR formula 1",
    )

    for query in news_queries:

        try:

            headlines = fetch_google_news(
                query
            )

            buckets["google_news"].extend(
                headlines
            )

            print(
                f"  [google_news] "
                f"+{len(headlines)} "
                f"({query[:28]}...)"
            )

        except Exception as news_error:

            print(
                f"  [google_news] SKIPPED "
                f"({query[:20]}...): "
                f"{type(news_error).__name__}"
            )

    # 3. CoinGecko trending (crypto)

    try:

        buckets["coingecko"] = fetch_coingecko()

        print(
            f"  [coingecko] "
            f"{len(buckets['coingecko'])} coins"
        )

    except Exception as coin_error:

        print(
            f"  [coingecko] SKIPPED: "
            f"{type(coin_error).__name__}"
        )

    # 4. Hacker News top stories (tech)

    try:

        buckets["hacker_news"] = (
            fetch_hacker_news()
        )

        print(
            f"  [hacker_news] "
            f"{len(buckets['hacker_news'])} stories"
        )

    except Exception as hn_error:

        print(
            f"  [hacker_news] SKIPPED: "
            f"{type(hn_error).__name__}"
        )

    # Normalize each bucket separately so keyword -> source
    # provenance survives the merge.

    keywords = []

    for source_name in (
        "google_trends",
        "coingecko",
        "hacker_news",
        "google_news",
    ):

        for keyword in normalize_keywords(
            buckets[source_name]
        ):

            if keyword not in keyword_source:

                keyword_source[keyword] = (
                    source_name
                )

            keywords.append(keyword)

    return keywords, keyword_source


def scan() -> list:
    """
    Full pipeline: fetch -> normalize -> match -> score ->
    write trend_candidates.json -> return the vetted list.
    """

    print(
        "\n📡 TREND SCANNER — pulling "
        "4 keyless sources..."
    )

    keywords, keyword_source = (
        _fetch_all_sources()
    )

    unique_count = len(keyword_source)

    print(
        f"\n[SCAN] {unique_count} unique "
        "keywords after normalization"
    )

    if not keywords:

        print(
            "[SCAN] No trending keywords "
            "fetched today; nothing to match."
        )

        _write_output(
            generated_at=datetime.now(
                timezone.utc
            ).isoformat(),
            sources_summary={},
            keyword_count=0,
            candidates=[],
        )

        return []

    matches = match_keywords_to_indicators(
        keywords
    )

    print(
        f"[SCAN] {len(matches)} indicator "
        "matches from healthy providers"
    )

    # ---- Score: each match = (provider, indicator).
    # Score starts from the best source weight of any
    # keyword that hit it; +1 per additional distinct
    # keyword (broader coverage = stronger signal).

    scored = {}

    for match in matches:

        key = (
            match["provider_id"],
            match["indicator_code"],
        )

        weight = SOURCE_WEIGHTS.get(
            keyword_source.get(
                match["keyword"], ""
            ),
            0,
        )

        entry = scored.setdefault(
            key,
            {
                **match,
                "score": 0,
                "keywords": set(),
            },
        )

        entry["score"] = max(
            entry["score"], weight
        )

        entry["keywords"].add(
            match["keyword"]
        )

    candidates = []

    for entry in scored.values():

        entry["score"] += (
            len(entry["keywords"]) - 1
        )

        entry["keywords"] = sorted(
            entry["keywords"]
        )[:3]

        candidates.append(entry)

    candidates.sort(
        key=lambda c: c["score"],
        reverse=True,
    )

    return _finalize(
        candidates,
        keyword_source,
        unique_count,
    )


def _finalize(
    candidates: list,
    keyword_source: dict,
    unique_count: int,
) -> list:
    """
    Category-diverse top-N selection, JSON output,
    console printout.  Returns the vetted list.
    """

    if not candidates:

        print(
            "[SCAN] No trending keyword maps "
            "to a fetchable indicator today."
        )

        _write_output(
            generated_at=datetime.now(
                timezone.utc
            ).isoformat(),
            sources_summary={},
            keyword_count=unique_count,
            candidates=[],
        )

        return []

    # At most 2 candidates per category so the morning
    # list stays varied.

    vetted = []

    for entry in candidates:

        if len(vetted) >= MAX_CANDIDATES:

            break

        same_category = sum(
            1
            for kept in vetted
            if kept["category"]
            == entry["category"]
        )

        if same_category >= 2:

            continue

        vetted.append(entry)

    sources_summary = {
        source: len(
            [
                keyword
                for keyword, mapped in
                keyword_source.items()
                if mapped == source
            ]
        )
        for source in sorted(
            set(keyword_source.values())
        )
    }

    _write_output(
        generated_at=datetime.now(
            timezone.utc
        ).isoformat(),
        sources_summary=sources_summary,
        keyword_count=unique_count,
        candidates=vetted,
    )

    _print_candidates(vetted)

    return vetted


# =========================================================
# OUTPUT PERSISTENCE
# =========================================================

def _write_output(
    generated_at: str,
    sources_summary: dict,
    keyword_count: int,
    candidates: list,
) -> str:
    """
    Persist the scan result to trend_candidates.json (repo root)
    so run.py's menu (and the user) can read it later without
    re-scanning.  Written atomically-ish: temp file then replace.
    """

    payload = {
        "generated_at": generated_at,
        "sources": sources_summary,
        "keyword_count": keyword_count,
        "candidate_count": len(candidates),
        "candidates": candidates,
    }

    output_path = str(OUTPUT_PATH)

    tmp_path = output_path + ".tmp"

    try:

        with open(
            tmp_path,
            "w",
            encoding="utf-8",
        ) as handle:

            json.dump(
                payload,
                handle,
                indent=2,
                ensure_ascii=False,
            )

        os.replace(
            tmp_path,
            output_path,
        )

        print(
            f"\n💾 Vetted candidates saved to: "
            f"{output_path}"
        )

    except OSError as write_error:

        print(
            f"⚠️ Could not write {OUTPUT_PATH.name}: "
            f"{write_error}"
        )

    return output_path


def _print_candidates(
    candidates: list,
) -> None:

    print(
        "\n" + "=" * 60
    )

    print(
        "🔥 TRENDING CANDIDATES (vetted against "
        "indicator catalog + provider health)"
    )

    print(
        "=" * 60
    )

    if not candidates:

        print(
            "   (none today — no trending keyword "
            "mapped to a healthy provider)"
        )

        return

    for position, entry in enumerate(
        candidates,
        start=1,
    ):

        print(
            f"\n  [{position}] {entry['keyword']}"
        )

        print(
            f"      -> {entry.get('provider_name') or entry.get('provider_id')}"
            f" / {entry.get('indicator_name')}"
            f" ({entry.get('category')})"
        )

        print(
            f"      score: {entry['score']}"
        )

        if entry.get("keywords"):

            print(
                f"      matched keywords: "
                f"{', '.join(entry['keywords'])}"
            )

    print(
        "\nPick one by typing its keyword in the "
        "manual-topic prompt, or press Enter for "
        "random mode."
    )


# =========================================================
# CLI
# =========================================================

if __name__ == "__main__":

    scan()

