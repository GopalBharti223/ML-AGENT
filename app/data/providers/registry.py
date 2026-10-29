from typing import Dict, List, Type

from app.data.providers.base import (
    DataProvider,
    IndicatorInfo,
)


class DataProviderRegistry:

    _providers: Dict[str, Type[DataProvider]] = {}

    @classmethod
    def register(
        cls,
        provider: Type[DataProvider]
    ):

        cls._providers[
            provider.provider_id
        ] = provider

    @classmethod
    def get(
        cls,
        provider_id: str
    ) -> Type[DataProvider]:

        provider_id = str(
            provider_id
        ).strip().lower()

        if provider_id not in cls._providers:
            raise ValueError(
                "Unknown data provider: "
                f"{provider_id}. "
                "Use one of: "
                f"{', '.join(sorted(cls._providers))}."
            )

        return cls._providers[
            provider_id
        ]

    @classmethod
    def list_providers(cls) -> List[str]:

        return sorted(
            cls._providers
        )

    @classmethod
    def search_indicators(
        cls,
        query: str,
        provider_id: str = ""
    ) -> List[IndicatorInfo]:

        if provider_id:
            providers = [
                cls.get(
                    provider_id
                )
            ]
        else:
            providers = [
                cls._providers[key]
                for key in sorted(
                    cls._providers
                )
            ]

        results = []

        for provider in providers:
            results.extend(
                provider.search_indicators(
                    query
                )
            )

        return results


from app.data.providers.ai_index import AIIndexProvider
from app.data.providers.football_data import FootballDataOrgProvider
from app.data.providers.imf import IMFProvider
from app.data.providers.jolpica_f1 import JolpicaF1Provider
from app.data.providers.jikan import JikanProvider
from app.data.providers.nhtsa import NHTSAProvider
from app.data.providers.openalex import OpenAlexProvider
from app.data.providers.owid import OWIDProvider
from app.data.providers.rawg import RAWGProvider
from app.data.providers.sec_edgar import SECEdgarProvider
from app.data.providers.solar_system import SolarSystemProvider
from app.data.providers.usgs import USGSEarthquakeProvider
from app.data.providers.wikipedia import WikipediaPageviewsProvider
from app.data.providers.worldbank import WorldBankProvider
from app.data.providers.viral_topics import ViralTopicsProvider


DataProviderRegistry.register(
    WorldBankProvider
)

DataProviderRegistry.register(
    OWIDProvider
)

DataProviderRegistry.register(
    IMFProvider
)

DataProviderRegistry.register(
    AIIndexProvider
)

DataProviderRegistry.register(
    JolpicaF1Provider
)

DataProviderRegistry.register(
    OpenAlexProvider
)

DataProviderRegistry.register(
    JikanProvider
)

DataProviderRegistry.register(
    NHTSAProvider
)

DataProviderRegistry.register(
    SECEdgarProvider
)

# Solar System: static NASA NSSDC planetary facts.  Snapshot-only:
# the engine self-restricts it to ranking / head-to-head story
# types (SUPPORTED_STORY_TYPES) and scores on leader separation.
DataProviderRegistry.register(
    SolarSystemProvider
)

# USGS earthquakes: keyless FDSN event feed aggregated at fetch
# time into country-year wide_data (M6+ events only; nearest-
# coastline attribution with an honest "International waters"
# bucket instead of force-fitting a country).  Honesty framing
# enforced in app/ai/script.py.
DataProviderRegistry.register(
    USGSEarthquakeProvider
)

# Wikipedia pageviews: manual entity-comparison route only (NOT
# in the automatic provider rotation -- without an explicit
# entity hint there is no meaningful default dataset).
DataProviderRegistry.register(
    WikipediaPageviewsProvider
)

# Key-gated providers.  REGISTERED so the resolver and tooling
# can list them, but they refuse to fetch until their (free,
# instant-signup) API key is configured -- the engines catch the
# RuntimeError and skip them gracefully.
DataProviderRegistry.register(
    FootballDataOrgProvider
)

DataProviderRegistry.register(
    RAWGProvider
)

DataProviderRegistry.register(
    ViralTopicsProvider
)
