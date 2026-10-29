"""Audience-relevance scoring for topic selection.

WHY THIS EXISTS
---------------
Analytics on the live channel show a 74.8% swipe-away rate and only
0.1% returning viewers.  The best-performing videos are head-to-head
comparisons between entities the audience actually knows (USA vs
China, India vs China).  The worst are comparisons where NEITHER side
is recognizable ("Syria vs Namibia", "Uzbekistan CPI") at 5-40 views.

The pre-existing `TopicDistributionPreference` only applies a SOFT
score multiplier (max +8%), and the final pick in
`CategoryRotationSelector.select()` is `rng.choice(pool)` -- scores
are NOT consulted, so an obscure-country candidate and a USA-vs-China
candidate had identical odds.

This module supplies the missing signal: a coarse, explainable
relevance BAND derived from the entities a candidate actually puts on
screen (story subject + leader/challenger + the entities in the chart
data).  `SmartStoryEngine` uses it to restrict auto-selection to the
top-scoring subset, and `CategoryRotationSelector` uses it to weight
the within-category pick.

Bands
-----
    A  audience geography OR a famous rivalry pair   (best)
    B  globally recognizable / major entity          (acceptable)
    C  neither side recognizable                     (drop when possible)

The band is deliberately coarse: it gates the pool, it does not
micro-rank stories, so story quality still decides inside a band.
"""

import re
from typing import Dict, List, Optional, Sequence, Set, Tuple

from app.config import settings
# =========================================================
# RECOGNIZABLE ENTITIES
# =========================================================

# Globally recognizable countries/entities.  Anything not listed
# lands in band C unless another rule matches.  Kept broad on
# purpose: this is a "would a general audience know it?" filter,
# not a quality judgement.
RECOGNIZABLE_ENTITIES: Set[str] = {
    # audience geographies
    "india", "usa", "united states", "us", "america",
    "china", "indonesia", "philippines", "uk", "united kingdom",
    "pakistan", "britain", "england",
    # other major nations
    "russia", "japan", "germany", "france", "italy", "spain",
    "canada", "australia", "brazil", "mexico", "south korea",
    "korea", "turkey", "saudi arabia", "iran", "iraq", "israel",
    "egypt", "nigeria", "south africa", "ukraine", "poland",
    "netherlands", "switzerland", "sweden", "norway", "vietnam",
    "thailand", "singapore", "malaysia", "bangladesh", "argentina",
    "taiwan", "hong kong", "uae", "united arab emirates", "qatar",
    "new zealand", "ireland", "greece", "portugal", "belgium",
    "austria", "denmark", "finland", "czech republic", "czechia",
    "romania", "hungary", "chile", "colombia", "peru",
    "north korea", "ethiopia", "kenya", "ghana", "morocco",
    "algeria", "venezuela", "cuba", "myanmar", "afghanistan",
    "syria", "lebanon", "jordan", "kuwait", "kazakhstan",
    # non-country entities the channel covers
    "jupiter", "saturn", "earth", "mars", "venus", "mercury",
    "neptune", "uranus", "sun", "moon", "pluto",
    "apple", "google", "alphabet", "microsoft", "amazon",
    "meta", "nvidia", "tesla", "netflix", "samsung", "intel",
    "adobe", "openai", "taiwan semiconductor", "tsmc",
    # major Indian corporate / national titans
    "tata", "reliance", "reliance industries", "isro", "tcs", "infosys",
    "wipro", "hdfc", "hdfc bank", "icici", "icici bank", "state bank of india",
    "sbi", "airtel", "bharti airtel", "adani", "adani group", "lic",
    "mahindra", "l&t", "larsen & toubro", "bajaj", "maruti", "maruti suzuki",
    "jio", "upi",
    # viral gaming, tech & billionaire titans
    "gta", "grand theft auto", "minecraft", "roblox", "tetris", "wii sports",
    "pubg", "mario kart", "red dead redemption", "witcher", "fortnite",
    "league of legends", "genshin impact", "playstation", "nintendo", "xbox", "game boy",
    "elon musk", "jeff bezos", "bernard arnault", "bill gates", "mark zuckerberg",
    "warren buffett", "mukesh ambani", "gautam adani", "byd", "tiktok", "wechat",
    "xiaomi", "avatar", "avengers", "titanic", "nvidia", "saudi aramco",
    # viral youtube & sports icons
    "mrbeast", "t-series", "pewdiepie", "cocomelon", "set india",
    "cristiano ronaldo", "ronaldo", "lionel messi", "messi", "lewandowski", "benzema", "mbappe", "haaland",
    "sachin tendulkar", "sachin", "virat kohli", "kohli", "rohit sharma", "ricky ponting", "sangakkara", "joe root",
}

# Provider spellings normalised before matching.
_ENTITY_ALIASES: Dict[str, str] = {
    "united states": "usa",
    "united states of america": "usa",
    "us": "usa",
    "america": "usa",
    "u.s.": "usa",
    "u.s.a.": "usa",
    "united kingdom": "uk",
    "great britain": "uk",
    "britain": "uk",
    "england": "uk",
    "korea, rep.": "south korea",
    "korea": "south korea",
    "republic of korea": "south korea",
    "russian federation": "russia",
    "viet nam": "vietnam",
    "turkiye": "turkey",
    "czechia": "czech republic",
    "iran, islamic rep.": "iran",
    "egypt, arab rep.": "egypt",
    "uae": "united arab emirates",
    "reliance industries ltd": "reliance",
    "reliance industries limited": "reliance",
    "reliance industries": "reliance",
    "tata consultancy services": "tcs",
    "tata motors": "tata",
    "tata steel": "tata",
    "tata group": "tata",
    "bharti airtel limited": "airtel",
    "state bank of india": "sbi",
    "hdfc bank limited": "hdfc",
}


def _normalize(entity: str) -> str:
    """Lowercase + strip punctuation + resolve provider aliases.

    NOTE: the "strip punctuation" half of that contract was NOT
    implemented until the provider-decoration fix.  It used to
    lowercase, turn "_" into " " and alias-resolve ONLY, so every
    dot and comma survived.  That is why "Amazon.com Inc." compared
    as "amazon.com inc." and never matched the bare "amazon" the
    table trusts.
    """
    text = str(entity or "").strip().lower()
    if not text:
        return ""
    text = text.replace("_", " ").strip()
    text = " ".join(text.split())
    return _ENTITY_ALIASES.get(text, text)


# -----------------------------------------------------
# PROVIDER DECORATIONS
# -----------------------------------------------------
# Providers name the same entity in forms the recognizable table
# was never written against.  Two families matter:
#
#   1. Corporate/legal suffixes -- SEC EDGAR reports the registrant
#      exactly as filed: "Amazon.com Inc.", "NVIDIA Corporation",
#      "Alphabet Inc.".  The table trusts "amazon" / "nvidia" /
#      "alphabet"; stripping the suffix recovers an entity that is
#      ALREADY in the table, so this is a formatting fix, not a
#      scope change.
#   2. Terse World-Bank / IMF qualifiers -- "Somalia, Fed. Rep.",
#      "Congo, Rep.", "Iran, Islamic Rep."  (the last two were
#      already alias entries; the Fed./Rep. family was not).
#
# Deliberately NOT used here: app.countries.lookup().  That
# gazetteer resolves ~330 countries, so routing the gate through
# it would pull in hundreds of small states and CHANGE WHAT COUNTS
# AS RECOGNIZABLE -- out of scope for a normalization fix.  The
# gate's table is a curated "would a general audience know it?"
# list and stays that way.
# -----------------------------------------------------

_LEGAL_SUFFIXES = frozenset({
    "inc", "incorporated", "corp", "corporation", "company", "co",
    "ltd", "limited", "llc", "plc", "ag", "sa", "nv", "bv", "gmbh",
    "holdings", "holding", "group", "technologies", "technology",
    "international", "systems", "enterprises", "sa.",
})

# Country qualifiers that follow a comma in provider labels.
_COUNTRY_QUALIFIERS = (
    "fed. rep.", "fed rep.", "dem. rep.", "dem rep.", "rep.",
    "arab rep.", "islamic rep.", "islamic republic",
    "democratic republic", "people's rep.", "fed. st.",
)

# Domain-ish tails glued by a dot: "Amazon.com Inc." -> "amazon".
_DOTTED_TAIL_RE = re.compile(r"\b(com|net|org|io|co|gov|edu|ai)\b")


def _strip_decorations(text: str) -> str:
    """Reduce a provider label to its bare entity name.

    Idempotent by construction: punctuation is collapsed to spaces
    BEFORE the filler tokens are tested, so "Amazon.com Inc." never
    leaves a trailing "inc." that the suffix test would miss on a
    second pass.

    Conservative by construction: it only removes tokens that are
    unambiguously legal/domain filler.  A genuine name that happens
    to contain one of those as a whole token is the only risk, and
    none of them are present in the table as standalone names.
    """
    if not text:
        return ""

    # "Somalia, Fed. Rep." -> "Somalia"
    if "," in text:
        head, _, tail = text.partition(",")
        if tail.strip() in _COUNTRY_QUALIFIERS:
            text = head.strip()

    # "Amazon.com Inc." -> "Amazon  Inc."
    text = _DOTTED_TAIL_RE.sub(" ", text)

    # Collapse EVERY punctuation run to a space.  Doing this before
    # the suffix test is what makes "inc." -> "inc" reachable and
    # the whole function idempotent.
    text = re.sub(r"[^\w\s&']+", " ", text, flags=re.UNICODE)
    text = " ".join(text.split())

    # Drop trailing legal fillers, repeatedly ("... Holdings Co.").
    tokens = text.split()
    while tokens and (
        tokens[-1] in _LEGAL_SUFFIXES
        # "JPMorgan Chase & Co." leaves a bare conjunction once
        # "co" is gone.
        or tokens[-1] in {"&", "'s"}
    ):
        tokens.pop()
    text = " ".join(tokens)

    return " ".join(text.split())


def _recognizable_keys(entity: str) -> Set[str]:
    """Every normalized form under which `entity` may be looked up.

    Returns the plain normalization PLUS decoration-stripped and
    alias-resolved variants, so membership tests can try each.  The
    plain form is always first, so behaviour only ever ADDS matches
    -- a name already recognised stays recognised.
    """
    forms: List[str] = []

    def _add(value: str) -> None:
        value = (value or "").strip()
        if value and value not in forms:
            forms.append(value)

    _add(_normalize(entity))

    stripped = _strip_decorations(_normalize(entity))
    _add(stripped)
    _add(_ENTITY_ALIASES.get(stripped, stripped))

    return set(forms)


def _match_any(entity: str, table: Set[str]) -> bool:
    """True when ANY normalized form of `entity` is in `table`.

    Also accepts a table entry that is a word-boundary PREFIX of the
    stripped name, so "Taiwan Semiconductor Manufacturing" still
    reaches "taiwan semiconductor" and "Amazon.com" still reaches
    "amazon" even if a suffix the table does not know about sits in
    between.  Prefix matching is restricted to table entries of 4+
    characters to avoid absurd one-or-two-letter matches.
    """
    forms = _recognizable_keys(entity)

    if any(form in table for form in forms):
        return True

    for form in forms:
        words = form.split()
        for entry in table:
            if len(entry) < 4:
                continue
            entry_words = entry.split()
            if (
                len(words) > len(entry_words)
                and words[:len(entry_words)] == entry_words
            ):
                return True
    return False


# Nicer forms for logs / titles (avoid "Usa", "Uk").
_DISPLAY_NAMES: Dict[str, str] = {
    "usa": "USA",
    "uk": "UK",
    "uae": "UAE",
    "tsmc": "TSMC",
    "dprk": "North Korea",
}


def _display(entity: str) -> str:
    """Human-friendly entity label for logs."""
    norm = _normalize(entity)
    if not norm:
        return ""
    if norm in _DISPLAY_NAMES:
        return _DISPLAY_NAMES[norm]
    return norm.title()


def _audience_set() -> Set[str]:
    """Audience geographies from settings (comma-separated)."""
    raw = str(getattr(settings, "AUDIENCE_COUNTRIES", "") or "")
    values = {
        _normalize(part)
        for part in raw.split(",")
        if part.strip()
    }
    return {value for value in values if value}


def _rivalry_pairs() -> Set[Tuple[str, str]]:
    """Rivalry pairs from settings, stored as sorted tuples."""
    raw = str(getattr(settings, "RIVALRY_PAIRS", "") or "")
    pairs: Set[Tuple[str, str]] = set()
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if "|" not in chunk:
            continue
        left, _, right = chunk.partition("|")
        first, second = _normalize(left), _normalize(right)
        if first and second:
            pairs.add(tuple(sorted((first, second))))
    return pairs


# =========================================================
# ENTITY EXTRACTION FROM A CANDIDATE
# =========================================================

def candidate_entities(candidate) -> List[str]:
    """Every entity a candidate puts on screen, best-effort.

    Reads:
      * metrics["entity"]      -- the story subject
      * metrics["leader"]      -- leader_challenge
      * metrics["challenger"]  -- leader_challenge
      * metrics["data"] index  -- entities drawn in the chart
      * metrics["latest_sorted"] index
    """
    metrics = getattr(candidate, "metrics", None) or {}

    found: List[str] = []

    for key in ("entity", "leader", "challenger"):
        value = metrics.get(key)
        if value:
            found.append(str(value))

    for key in ("latest_sorted", "data"):
        frame = metrics.get(key)
        if frame is None:
            continue
        try:
            index = list(frame.index)[:12]
        except Exception:
            continue
        for value in index:
            found.append(str(value))

    # Preserve order, drop blanks/dupes.
    seen: Set[str] = set()
    result: List[str] = []
    for value in found:
        norm = _normalize(value)
        if not norm or norm in seen:
            continue
        seen.add(norm)
        result.append(value)
    return result


# =========================================================
# SCORING
# =========================================================

# Scores per band, used for ordering and for the weighted pick.
_BAND_SCORES = {"A": 1.0, "B": 0.55, "C": 0.15}


class AudienceRelevance:
    """Band + score + human-readable reasons for one candidate."""

    __slots__ = (
        "band", "score", "reasons", "audience_hits",
        "rivalry", "recognizable",
    )

    def __init__(
        self,
        band: str,
        score: float,
        reasons: Sequence[str],
        audience_hits: Sequence[str],
        rivalry: bool,
        recognizable: bool,
    ):
        self.band = band
        self.score = score
        self.reasons = list(reasons)
        self.audience_hits = list(audience_hits)
        self.rivalry = rivalry
        self.recognizable = recognizable

    def __repr__(self) -> str:
        return (
            f"AudienceRelevance(band={self.band!r}, "
            f"score={self.score:.3f}, reasons={self.reasons!r})"
        )


def _canonical(entity: str) -> str:
    """The one form used for audience-set and rivalry comparisons.

    Both tables hold plain country names, so the decoration-stripped
    form is the right key.  Rivalry pairs are resolved through the
    SAME function, so both sides of a comparison are canonicalized
    identically and a decorated label still pairs correctly.
    """
    stripped = _strip_decorations(_normalize(entity))
    return stripped or _normalize(entity)


def evaluate(candidate) -> AudienceRelevance:
    """Score one StoryCandidate for audience relevance."""
    audience = _audience_set()
    rivalries = _rivalry_pairs()

    entities = candidate_entities(candidate)
    normalized = [_normalize(entity) for entity in entities]
    canonical = [_canonical(entity) for entity in entities]

    reasons: List[str] = []

    # -----------------------------------------------------
    # 1. Audience geography
    # -----------------------------------------------------

    # Matched on the decoration-stripped form so a provider label
    # like "United States, Fed. Rep." still resolves to the "usa"
    # audience geography instead of falling through.
    audience_hits = sorted({
        canon for canon in canonical if canon in audience
    })

    # -----------------------------------------------------
    # 2. Rivalry pair (any two entities in the candidate)
    # -----------------------------------------------------

    rivalry = False
    rivalry_pair: Optional[Tuple[str, str]] = None

    unique_norms = list(dict.fromkeys(canonical))

    for i, first in enumerate(unique_norms):
        for second in unique_norms[i + 1:]:
            key = tuple(sorted((first, second)))
            if key in rivalries:
                rivalry = True
                rivalry_pair = key
                break
        if rivalry:
            break

    # -----------------------------------------------------
    # 3. Recognizability (at least one known side)
    # -----------------------------------------------------

    # The fix that matters: _match_any tries the plain normalization
    # AND the decoration-stripped form, so "Amazon.com Inc." /
    # "Somalia, Fed. Rep." reach the bare "amazon" / "somalia" the
    # table already trusts instead of scoring as band C.
    recognizable_hits = sorted({
        _canonical(entity)
        for entity in entities
        if _match_any(entity, RECOGNIZABLE_ENTITIES)
    })
    recognizable = bool(recognizable_hits)

    # -----------------------------------------------------
    # Band assignment
    # -----------------------------------------------------

    if rivalry and rivalry_pair:
        band = "A"
        reasons.append(
            "rivalry pair "
            f"{_display(rivalry_pair[0])} vs {_display(rivalry_pair[1])}"
        )
    elif audience_hits:
        band = "A"
        reasons.append(
            "audience geography: "
            + ", ".join(_display(hit) for hit in audience_hits[:3])
        )
    elif recognizable:
        band = "B"
        reasons.append(
            "recognizable entity: "
            + ", ".join(_display(hit) for hit in recognizable_hits[:3])
        )
    else:
        band = "C"
        reasons.append(
            "no recognizable entity on either side"
            + (f" ({', '.join(entities[:3])})" if entities else "")
        )

    score = _BAND_SCORES[band]

    # A rivalry between two audience geographies is the strongest
    # possible signal (e.g. India vs Pakistan, India vs China).
    if rivalry and audience_hits:
        score += 0.10
        reasons.append("rivalry + audience geography")

    return AudienceRelevance(
        band=band,
        score=score,
        reasons=reasons,
        audience_hits=audience_hits,
        rivalry=rivalry,
        recognizable=recognizable,
    )


# =========================================================
# POOL GATE
# =========================================================

def filter_pool(candidates: List, logger=None) -> List:
    """Restrict a candidate pool to the top-scoring relevance subset.

    Rules (deliberately conservative so the rotation pool never
    collapses):
      * band C (obscure) candidates are dropped only when band A/B
        candidates exist AND enough survivors remain;
      * band B candidates are added only when band A alone cannot
        reach settings.AUDIENCE_MIN_POOL.
    """
    if not candidates:
        return candidates

    if not getattr(settings, "AUDIENCE_RELEVANCE_ENABLED", True):
        return candidates

    scored = [(evaluate(candidate), candidate) for candidate in candidates]

    band_a = [c for rel, c in scored if rel.band == "A"]
    band_b = [c for rel, c in scored if rel.band == "B"]
    band_c = [c for rel, c in scored if rel.band == "C"]

    log = logger or (lambda *_args, **_kwargs: None)

    min_pool = max(1, int(getattr(settings, "AUDIENCE_MIN_POOL", 4)))
    drop_obscure = bool(
        getattr(settings, "AUDIENCE_DROP_OBSCURE", True)
    )

    # Prefer band A; widen to B, then C, only to reach the floor.
    survivors = list(band_a)

    if len(survivors) < min_pool:
        survivors = survivors + band_b

    # Only widen to band C (obscure) if drop_obscure is explicitly disabled
    if not drop_obscure and len(survivors) < min_pool:
        survivors = survivors + band_c

    # If the gate starved the pool, fall back to the full pool
    # rather than hand the rotator a single topic.
    if len(survivors) < min_pool:
        log(
            "[AUDIENCE] Gate would starve the pool "
            f"({len(survivors)} < {min_pool}); keeping all "
            f"{len(candidates)} candidates."
        )
        return candidates

    dropped_obscure = (
        len(band_c)
        if drop_obscure and len(band_a) + len(band_b) >= min_pool
        else 0
    )

    log(
        "[AUDIENCE] Relevance gate: "
        f"A={len(band_a)} B={len(band_b)} C={len(band_c)} "
        f"-> kept {len(survivors)}/{len(candidates)} "
        f"(dropped {dropped_obscure} obscure)"
    )

    return survivors


def annotate(candidates: List, logger=None) -> List:
    """Stamp `metrics["audience_*"]` onto each candidate.

    Makes the signal available to CategoryRotationSelector (weighted
    pick) and to the run logs, without replacing the candidates.
    """
    log = logger or (lambda *_args, **_kwargs: None)

    for candidate in candidates:
        relevance = evaluate(candidate)
        metrics = getattr(candidate, "metrics", None)
        if isinstance(metrics, dict):
            metrics["audience_band"] = relevance.band
            metrics["audience_score"] = relevance.score
            metrics["audience_reasons"] = relevance.reasons

    for candidate in candidates:
        metrics = getattr(candidate, "metrics", None) or {}
        log(
            "  [AUDIENCE] "
            f"{metrics.get('audience_band', '?')} "
            f"{getattr(candidate, 'provider_id', '?')}/"
            f"{getattr(candidate, 'indicator_code', '?')}/"
            f"{getattr(candidate, 'story_type', '?')} "
            f"score={float(metrics.get('audience_score', 0.0)):.2f} "
            f"({'; '.join(metrics.get('audience_reasons', []))})"
        )

    return candidates