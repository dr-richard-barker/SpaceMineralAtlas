"""Harvester for the NASA Life Sciences Data Archive (LSDA) experiment catalog.

The LSDA public portal at ``nlsp.nasa.gov`` is backed by a JSON query endpoint::

    https://nlsp.nasa.gov/explore/api/v1/query?type=lsda_experiment&query=all&page=N

Two behaviours of that endpoint drive the design of this module, both established
by direct probing rather than from documentation (there is none published):

1. **``query`` does not filter server-side.** Every search term returns
   ``total = 2676`` -- the full corpus. The term only influences ``_score``
   ordering. Consequently there is no way to ask the API for "experiments that
   measure potassium"; the only correct approach is to harvest the whole catalog
   once and filter locally. That is also better for reproducibility, since the
   filter logic then lives in version control instead of in a URL.

2. **It is easily overloaded.** Issuing requests without delay produces HTTP
   502/503 within a handful of calls. Retrieval therefore goes through
   ``http.fetch``, which throttles and retries.

Pagination uses ``page=N`` (1-based, 20 records per page). ``from``/``offset``/
``skip``/``start`` are all accepted by the server but silently ignored -- they
return page 1 -- so using one of those would have produced a catalog of 2,676
copies of the same twenty records.

What makes the catalog worth harvesting is the ``parameter_name`` field: a list
of the physiological variables each experiment actually measured (e.g.
``['Aldosterone', 'Bicarbonate (HCO3), base excess', ...]``). Combined with
``archive_status``, it lets us answer a question that is otherwise very laborious:
*which spaceflight experiments measured mineral or dietary variables, and can I
actually obtain the data?*
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Iterator

import pandas as pd

from .http import fetch
from .paths import RAW

logger = logging.getLogger(__name__)

QUERY_API = "https://nlsp.nasa.gov/explore/api/v1/query"
RECORDS_PER_PAGE = 20

# Fields retained from each record. The API returns ~60 fields per hit, most of
# them access-control lists and internal indexing metadata; these are the ones
# with scientific or provenance meaning.
KEEP_FIELDS = [
    "experiment_id", "experiment_title", "experiment_description",
    "PrincipalInvestigator", "investigators", "pme_role_with_name",
    "species", "species_sci_name", "CombinedSpecies",
    "missions", "mission_id", "program_name", "ExperimentDesign",
    "research_area", "parameter_name", "keyword",
    "experiment_type_lk", "proposal_source", "proposal_date",
    "LaunchDate", "LaunchYear",
    "nasa_center", "agency", "archive_status", "archive_status_index",
    "_key",
]


# --------------------------------------------------------------------------
# Mineral / nutrition ontology
# --------------------------------------------------------------------------
# Terms are matched case-insensitively against an experiment's measured
# parameters, research areas, keywords, title and description. Each element maps
# to the surface forms that actually occur in LSDA parameter strings -- including
# the analyte names clinicians use, since LSDA records blood chemistry under names
# like "Bicarbonate (HCO3)" rather than "carbon".
#
# Word-boundary matching is used throughout so that, for example, "iron" does not
# match "environment" and "K" does not match every capital K in a title.

# Every plain-word term is word-bounded. This is not cosmetic: an unbounded
# "iron" matches env-IRON-ment, which alone produced 1,266 spurious hits (47% of
# the corpus) in an earlier revision. Chemical symbols are bounded for the same
# reason, and bare single letters are excluded entirely -- a lone "B" matches
# "vitamin B", "B cells" and personal initials, none of which mean boron.
MINERAL_TERMS: dict[str, list[str]] = {
    "calcium":    [r"\bcalcium\b", r"\bCa\b", r"\bhypercalc", r"\bhypocalc",
                   r"\bcalcitonin\b", r"\bparathyroid\b", r"\bPTH\b",
                   r"\bvitamin D\b", r"\bcalcitriol\b",
                   r"\bbone mineral\b", r"\bbone resorption\b", r"\bbone formation\b",
                   r"\bosteocalcin\b", r"\brenal stone", r"\bkidney stone",
                   r"\bnephrolithiasis\b"],
    "potassium":  [r"\bpotassium\b", r"\bK\+", r"\bhypokal", r"\bhyperkal",
                   r"\baldosterone\b"],
    "sodium":     [r"\bsodium\b", r"\bNa\+", r"\bhyponatr", r"\bhypernatr",
                   r"\bsalt intake\b", r"\bnatriuretic\b"],
    "magnesium":  [r"\bmagnesium\b", r"\bMg\b", r"\bhypomagnes"],
    "iron":       [r"\biron\b", r"\bferritin\b", r"\btransferrin\b",
                   r"\bh[ae]moglobin\b", r"\bh[ae]matocrit\b",
                   r"\berythropoiet", r"\ban[ae]mia\b", r"\bferrous\b", r"\bferric\b"],
    "zinc":       [r"\bzinc\b", r"\bZn\b"],
    "copper":     [r"\bcopper\b", r"\bCu\b", r"\bceruloplasmin\b"],
    "selenium":   [r"\bselenium\b", r"\bglutathione peroxidase\b"],
    "phosphorus": [r"\bphosphorus\b", r"\bphosphate\b",
                   r"\balkaline phosphatase\b", r"\bhypophosphat"],
    "manganese":  [r"\bmanganese\b", r"\bMn\b"],
    "boron":      [r"\bboron\b"],
    "chloride":   [r"\bchloride\b", r"\bbicarbonate\b", r"\bHCO3\b"],
}

# Word-bounded for the same reason as MINERAL_TERMS. These are already regexes,
# so they are compiled directly rather than passed through re.escape.
NUTRITION_TERMS: list[str] = [
    r"\bnutri",            # nutrition, nutritional, nutrient, nutriture
    r"\bdiet\b", r"\bdietary\b", r"\bfood\b", r"\bintake\b",
    r"\bfeeding\b", r"\bmalnutrition\b", r"\bvitamin\b", r"\bsupplement",
    r"\benergy balance\b", r"\bcaloric\b", r"\bcalorie", r"\bbody composition\b",
    r"\belectrolyte", r"\bfluid balance\b", r"\bhydration\b",
    r"\bmetabolic panel\b", r"\bblood chemistr", r"\bserum chemistr",
    r"\burine chemistr", r"\burinalysis\b",
]

# archive_status is free text; these patterns map it to an actionable category so
# a reader can tell at a glance whether a dataset is obtainable.
ACCESS_PATTERNS: list[tuple[str, str]] = [
    ("data request",           "request_required"),
    ("accessible via",         "request_required"),
    ("held by another",        "held_elsewhere"),
    ("another repository",     "held_elsewhere"),
    ("no data from this study", "not_submitted"),
    ("not submitted",          "not_submitted"),
    ("publicly available",     "open"),
    ("available online",       "open"),
]


def classify_access(archive_status: Any) -> str:
    """Map LSDA's free-text ``archive_status`` to one actionable category."""
    text = str(archive_status or "").lower()
    if not text or text == "nan":
        return "unknown"
    for pattern, category in ACCESS_PATTERNS:
        if pattern in text:
            return category
    return "other"


def _flatten(value: Any) -> str:
    """Render an arbitrarily nested LSDA field as one searchable lowercase string.

    LSDA nests inconsistently -- ``species`` may be ``[['Human']]`` while
    ``missions`` is ``['Ground']`` -- so recursion is simpler than special-casing.
    HTML is stripped because several fields embed markup (``investigators`` is an
    anchor tag, ``experiment_description`` contains Word-exported divs).
    """
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        return " ".join(_flatten(item) for item in value)
    if isinstance(value, dict):
        return " ".join(_flatten(item) for item in value.values())
    return re.sub(r"<[^>]+>", " ", str(value))


class NonJSONResponse(RuntimeError):
    """The LSDA endpoint answered with something other than JSON.

    Raised when a request succeeds at the HTTP level but the body is not the
    expected JSON. The usual cause is network-level filtering rather than a
    fault in this code: nlsp.nasa.gov serves an HTML interstitial with HTTP 200
    to some clients, which the retry logic cannot detect because 200 is not a
    retryable status. This has been observed from GitHub Actions runners while
    the same request succeeds from a residential connection.
    """


def fetch_page(page: int, *, force: bool = False) -> dict:
    """Retrieve one page of the experiment catalog (1-based).

    Raises
    ------
    NonJSONResponse
        If the endpoint returns a non-JSON body. A bare ``JSONDecodeError``
        here is very hard to interpret, so the cause and the remedy are stated
        explicitly, and the cached file is removed so a later run does not read
        the interstitial back out of the cache as though it were data.
    """
    url = f"{QUERY_API}?type=lsda_experiment&query=all&page={page}"
    cache_path = RAW / "lsda" / f"experiments_page_{page:04d}.json"
    payload = fetch(url, cache_path, force=force)

    try:
        return json.loads(payload)
    except json.JSONDecodeError as error:
        snippet = payload[:200].decode("utf-8", "replace").replace("\n", " ")
        # Do not let a non-JSON body persist in the cache: a later run would
        # serve it from disk and fail identically without touching the network.
        cache_path.unlink(missing_ok=True)
        raise NonJSONResponse(
            f"LSDA returned a non-JSON body for page {page} "
            f"({len(payload)} bytes) from {url}\n"
            f"  first bytes: {snippet!r}\n"
            f"  This is usually network-level filtering, not a code fault: the "
            f"endpoint serves an HTML interstitial with HTTP 200 to some "
            f"clients (observed from CI runners and other datacenter ranges) "
            f"while the same request succeeds from a residential connection.\n"
            f"  Remedy: run `make harvest` from a network that LSDA answers, or "
            f"use the catalog already committed under catalog/."
        ) from error


def harvest(*, max_pages: int | None = None, force: bool = False) -> list[dict]:
    """Harvest the full LSDA experiment catalog.

    Returns one dict per experiment, restricted to :data:`KEEP_FIELDS`. Records
    are de-duplicated on ``_key``; a duplicate would indicate that pagination had
    silently stopped advancing, so the count is logged for verification.
    """
    first = fetch_page(1, force=force)
    total = int(first.get("total", 0))
    pages = -(-total // RECORDS_PER_PAGE)  # ceiling division
    if max_pages is not None:
        pages = min(pages, max_pages)

    logger.info("LSDA catalog: %d experiments across %d pages", total, pages)

    seen: set[str] = set()
    records: list[dict] = []

    for page in range(1, pages + 1):
        body = first if page == 1 else fetch_page(page, force=force)
        hits = body.get("hits", [])
        if not hits:
            logger.warning("page %d returned no hits; stopping early", page)
            break
        for hit in hits:
            key = hit.get("_key")
            if key in seen:
                continue
            seen.add(key)
            records.append({field: hit.get(field) for field in KEEP_FIELDS})
        if page % 20 == 0 or page == pages:
            logger.info("  harvested page %d/%d (%d unique records)", page, pages, len(records))

    return records


def annotate(records: list[dict]) -> pd.DataFrame:
    """Tag each experiment with the minerals and nutrition topics it touches.

    Adds one boolean column per mineral (``mineral_calcium`` etc.), a
    ``minerals`` summary string, ``is_nutrition``, ``n_minerals``,
    ``access_category`` and a ``relevance`` score used only for sorting.
    """
    frame = pd.DataFrame.from_records(records)

    # Fields searched for ontology terms. parameter_name is weighted most heavily
    # in `relevance` because it states what was actually measured, whereas a title
    # may merely mention a mineral in passing.
    def haystack(row: pd.Series) -> str:
        return " ".join(
            _flatten(row.get(field))
            for field in ("parameter_name", "research_area", "keyword",
                          "experiment_title", "experiment_description")
        ).lower()

    def measured(row: pd.Series) -> str:
        return _flatten(row.get("parameter_name")).lower()

    haystacks = frame.apply(haystack, axis=1)
    measured_only = frame.apply(measured, axis=1)

    for mineral, patterns in MINERAL_TERMS.items():
        combined = "|".join(patterns)
        frame[f"mineral_{mineral}"] = haystacks.str.contains(
            combined, case=False, regex=True, na=False
        )
        frame[f"measured_{mineral}"] = measured_only.str.contains(
            combined, case=False, regex=True, na=False
        )

    # NUTRITION_TERMS are regexes carrying their own word boundaries; escaping
    # them here would turn every "\b" into a literal backslash-b and match nothing.
    nutrition_re = "|".join(NUTRITION_TERMS)
    frame["is_nutrition"] = haystacks.str.contains(
        nutrition_re, case=False, regex=True, na=False
    )
    frame["measured_nutrition"] = measured_only.str.contains(
        nutrition_re, case=False, regex=True, na=False
    )

    mineral_cols = [f"mineral_{m}" for m in MINERAL_TERMS]
    measured_cols = [f"measured_{m}" for m in MINERAL_TERMS]

    frame["n_minerals"] = frame[mineral_cols].sum(axis=1)
    frame["n_minerals_measured"] = frame[measured_cols].sum(axis=1)
    frame["minerals"] = frame[mineral_cols].apply(
        lambda row: ";".join(c.removeprefix("mineral_") for c in mineral_cols if row[c]),
        axis=1,
    )
    frame["access_category"] = frame["archive_status"].map(classify_access)

    # Relevance ranks experiments that *measured* a mineral above those that merely
    # mention one, and rewards breadth across minerals. Used for ordering the
    # catalog only -- no analysis depends on it.
    frame["relevance"] = (
        3 * frame["n_minerals_measured"]
        + frame["n_minerals"]
        + 2 * frame["measured_nutrition"].astype(int)
        + frame["is_nutrition"].astype(int)
    )

    # Collapse the nested list fields to readable strings for the published CSV.
    for field in ("species", "missions", "research_area", "parameter_name",
                  "keyword", "program_name", "PrincipalInvestigator",
                  "experiment_type_lk", "species_sci_name"):
        if field in frame.columns:
            frame[field] = frame[field].map(
                lambda v: "; ".join(dict.fromkeys(_flatten(v).split())) if isinstance(v, (list, tuple))
                else _flatten(v)
            )

    return frame
