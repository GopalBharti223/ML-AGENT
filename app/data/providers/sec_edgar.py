"""SEC EDGAR Provider - public-company financials (companies_brands).

Source: https://www.sec.gov/edgar (US SEC EDGAR / data.sec.gov)
License: US public domain.
Commercial use: ALLOWED (see provider catalog).

Provides revenue / net income / assets time series for major
public companies via the SEC companyfacts API.  SEC fair-access
rules require an identifiable User-Agent (we set one).

Stories this enables:
  "Which Company Has the Highest Revenue?"
  "Which Company Grew Fastest?"
  "Biggest Companies by Revenue"
  "Revenue Growth Rankings"
  "Company vs Company"

We NEVER claim market cap, valuation, brand value, or stock
performance unless the SEC actually provides the metric.
"""
import datetime
from typing import Dict, List

import pandas as pd
import requests

from app.data.providers.base import (
    DataProvider,
    DataProviderResult,
    IndicatorInfo,
)


class SECEdgarProvider(DataProvider):

    provider_id = "sec_edgar"
    provider_name = "SEC EDGAR"
    source_url = "https://www.sec.gov/edgar"
    base_url = "https://data.sec.gov/api/xbrl"
    request_timeout = 30

    # Minimum span (days) for a duration fact to count as a fiscal
    # YEAR.  10-K entries mix quarterly (~90d) and annual (~365d)
    # periods under the same fy/fp, so duration is the only reliable
    # annual selector.  300 comfortably accepts 52/53-week fiscal
    # years and rejects quarters and semi-annuals.
    ANNUAL_MIN_DAYS = 300

    # Well-known public-company tickers (real SEC filers).
    COMPANIES: Dict[str, str] = {
        "AAPL": "Apple Inc.",
        "MSFT": "Microsoft Corporation",
        "GOOG": "Alphabet Inc.",
        "AMZN": "Amazon.com Inc.",
        "META": "Meta Platforms Inc.",
        "TSLA": "Tesla Inc.",
        "NVDA": "NVIDIA Corporation",
        "JPM": "JPMorgan Chase & Co.",
        "V": "Visa Inc.",
        "WMT": "Walmart Inc.",
        "KO": "The Coca-Cola Company",
        "PEP": "PepsiCo Inc.",
        "JNJ": "Johnson & Johnson",
        "XOM": "Exxon Mobil Corporation",
        "CVX": "Chevron Corporation",
        "DIS": "The Walt Disney Company",
        "NFLX": "Netflix Inc.",
        "ADBE": "Adobe Inc.",
        "CRM": "Salesforce Inc.",
    }

    INDICATORS: Dict[str, Dict] = {
        "public_company_revenue": {
            "name": "Public Company Revenue",
            "category": "Companies",
            "fact_key": "Revenues",
            # Revenue tagging is NOT uniform across filers: e.g. Apple
            # reports modern fiscal years under the ASC-606 tag and only
            # pre-2019 under "Revenues".  Try in order, first hit wins.
            "fact_keys": [
                "Revenues",
                "RevenueFromContractWithCustomerExcludingAssessedTax",
                "RevenueFromContractWithCustomerIncludingAssessedTax",
                "SalesRevenueNet",
            ],
            "unit_key": "USD",
            "metric_name": "Revenue (USD)",
        },
        "public_company_net_income": {
            "name": "Public Company Net Income",
            "category": "Companies",
            "fact_key": "NetIncomeLoss",
            "fact_keys": ["NetIncomeLoss", "ProfitLoss"],
            "unit_key": "USD",
            "metric_name": "Net Income (USD)",
        },
        "public_company_assets": {
            "name": "Public Company Total Assets",
            "category": "Companies",
            "fact_key": "Assets",
            "fact_keys": ["Assets"],
            "unit_key": "USD",
            "metric_name": "Total Assets (USD)",
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

    @classmethod
    def _cik_for_ticker(cls, ticker: str) -> str:
        """Resolve a ticker to a CIK via the SEC ticker-CIK file."""
        url = "https://www.sec.gov/files/company_tickers.json"
        response = requests.get(
            url,
            timeout=cls.request_timeout,
            headers={
                "User-Agent": (
                    "MyShorts-DataFactory/1.0 "
                    "(mailto:myshorts-datafactory@example.org)"
                )
            },
        )
        response.raise_for_status()
        payload = response.json()
        for entry in payload.values():
            if str(entry.get("ticker", "")).upper() == ticker.upper():
                return str(entry.get("cik_str", ""))
        return ""

    @classmethod
    def _fetch_company_facts(cls, cik: str) -> Dict:
        # SEC requires the zero-padded 10-digit form:
        #   /companyfacts/CIK0001045810.json
        # An unpadded CIK (e.g. "1045810") returns 404.
        url = f"{cls.base_url}/companyfacts/CIK{str(cik).zfill(10)}.json"

        response = requests.get(
            url,
            timeout=cls.request_timeout,
            headers={
                "User-Agent": (
                    "MyShorts-DataFactory/1.0 "
                    "(mailto:myshorts-datafactory@example.org)"
                )
            },
        )
        response.raise_for_status()
        return response.json()

    @classmethod
    def _extract_yearly_values(
        cls,
        facts: Dict,
        fact_key: str,
        unit_key: str,
        fact_keys: List[str] = None
    ) -> Dict[int, float]:
        """Extract annual values for a given XBRL fact.

        Returns {fiscal_year: value} using only real reported
        values from the SEC.  No extrapolation.

        SEC companyfacts nests facts under a TAXONOMY level
        (us-gaap / ifrs-full / dei), so the lookup must traverse
        taxonomies -- facts["facts"]["Revenues"] is always a
        KeyError.  `fact_keys` is an ordered fallback chain of
        XBRL tags; results from all tags are UNION-MERGED because
        filers switch tags mid-history (e.g. Apple reports only
        pre-2019 under "Revenues" and modern years under the
        ASC-606 tag; NVIDIA has a gap in "Revenues" for FY2020-21).

        CRITICAL: the fy/fp fields mark the FILING's fiscal-period
        focus, not the fact's duration -- one 10-K entry set mixes
        quarterly and full-year values under the SAME fy/fp (e.g.
        J&J's FY2019 10-K carries Q4 revenue $20.7B and full-year
        $82.1B both as fy=2019, fp=FY).  The period length is
        therefore derived from start/end dates and only ~annual
        durations (>= ANNUAL_MIN_DAYS) are kept for duration
        facts; instants (no start, e.g. Assets) pass through.
        When a fiscal year still appears more than once, the
        entry with the latest period end (most recent filing)
        wins.
        """
        tag_chain = list(fact_keys or [fact_key])
        taxonomies = ("us-gaap", "ifrs-full", "dei")
        merged: Dict[int, tuple] = {}
        for tag in tag_chain:
            tag_result: Dict[int, tuple] = {}
            for taxonomy in taxonomies:
                fact = (facts.get("facts") or {}).get(taxonomy, {}).get(tag)
                if not fact:
                    continue
                units = fact.get("units", {}) or {}
                unit_values = units.get(unit_key, []) or []
                for entry in unit_values:
                    fy = entry.get("fy")
                    val = entry.get("val")
                    if fy is None or val is None:
                        continue
                    try:
                        fy = int(fy)
                        val = float(val)
                    except (ValueError, TypeError):
                        continue
                    end = str(entry.get("end") or "")
                    start = str(entry.get("start") or "")
                    if start:
                        try:
                            duration = (
                                datetime.date.fromisoformat(end[:10])
                                - datetime.date.fromisoformat(start[:10])
                            ).days
                        except ValueError:
                            continue
                        if duration < cls.ANNUAL_MIN_DAYS:
                            continue  # quarterly / interim value
                    if fy not in tag_result or end >= tag_result[fy][0]:
                        tag_result[fy] = (end, val)
                if tag_result:
                    break  # most-specific taxonomy hit wins
            for fy, tv in tag_result.items():
                if fy not in merged:
                    merged[fy] = tv
        return {fy: val for fy, (end, val) in merged.items()}

    @classmethod
    def fetch_normalized(
        cls,
        indicator_code: str,
        years: int = 10,
        story_type: str = "fastest_growth",
        min_countries: int = 3
    ) -> DataProviderResult:
        config = cls.INDICATORS.get(indicator_code)
        if not config:
            raise ValueError(f"Unknown indicator: {indicator_code}")

        fact_key = config["fact_key"]
        unit_key = config["unit_key"]
        metric_name = config["metric_name"]
        fact_keys = config.get("fact_keys") or [fact_key]

        end_year = 2024
        start_year = end_year - years + 1

        rows = []

        for ticker, company_name in cls.COMPANIES.items():
            try:
                cik = cls._cik_for_ticker(ticker)
            except Exception:
                continue

            if not cik:
                continue

            try:
                facts = cls._fetch_company_facts(cik)
            except Exception:
                continue

            yearly = cls._extract_yearly_values(
                facts, fact_key, unit_key, fact_keys=fact_keys
            )
            yearly = {
                y: v for y, v in yearly.items()
                if start_year <= y <= end_year
            }

            if not yearly:
                continue

            for year, value in yearly.items():
                rows.append({
                    "name": company_name,
                    "code": ticker,
                    "year": year,
                    "value": value,
                })

        if not rows:
            return cls._empty_result(indicator_code, config)

        df = pd.DataFrame(rows)
        wide = df.pivot_table(
            index="name", columns="year",
            values="value", aggfunc="max",
        ).sort_index(axis=1)
        wide = wide.dropna(
            thresh=max(3, int(len(wide.columns) * 0.5))
        )

        if wide.empty or len(wide) < min_countries:
            return cls._empty_result(indicator_code, config)

        normalized_rows = []
        for name, row in wide.iterrows():
            for year, value in row.items():
                if pd.isna(value):
                    continue
                normalized_rows.append({
                    "country": name, "country_code": name,
                    "year": int(year), "metric": metric_name,
                    "value": float(value),
                    "provider": cls.provider_id,
                    "source_name": cls.provider_name,
                    "source_url": cls.source_url,
                    "indicator_code": indicator_code,
                })
        normalized = pd.DataFrame(normalized_rows)
        metadata = {
            "provider": cls.provider_id,
            "source_name": cls.provider_name,
            "source_url": cls.source_url,
            "indicator_code": indicator_code,
            "indicator_name": config["name"],
            "category": config["category"],
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
    def _empty_result(cls, indicator_code: str, config: Dict) -> DataProviderResult:
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