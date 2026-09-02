"""Client for the NASA Open Science Data Repository (OSDR) file API.

OSDR exposes a per-dataset file listing at::

    https://visualization.osdr.nasa.gov/biodata/api/v2/dataset/{OSD-ID}/files/

whose JSON body is shaped ``{"<OSD-ID>": {"files": {"<filename>": {"URL": ...}}}}``.
The ``URL`` value is sometimes absolute and sometimes relative to
``https://osdr.nasa.gov``, so :func:`file_url` normalises both forms.

Where a study offers a ``*_TRANSFORMED.csv`` we prefer it over the originally
submitted file: OSDR's curators rewrite the column headers into a
``<analyte>_<unit>`` convention that carries the unit with the data. That
convention is what makes cross-study harmonisation tractable -- though note that
for OSD-655 the unit named in the header is wrong, which is handled in
``harmonise.py`` rather than here. This module's job is faithful retrieval only:
it does not alter a single byte it receives.
"""

from __future__ import annotations

import io
import json
import logging
from dataclasses import dataclass

import pandas as pd

from .http import fetch
from .paths import RAW

logger = logging.getLogger(__name__)

FILES_API = "https://visualization.osdr.nasa.gov/biodata/api/v2/dataset/{osd_id}/files/"
OSDR_BASE = "https://osdr.nasa.gov"


@dataclass(frozen=True)
class StudyRef:
    """A NASA OSDR study used by this project, with why it is here recorded inline."""

    osd_id: str
    label: str
    role: str          # "plant" | "astronaut" | "microbiology"
    description: str


# Datasets this analysis actually consumes. Anything not in this list is not
# downloaded; see EXPANSION_CANDIDATES for studies identified but deliberately
# out of scope for the present manuscript.
STUDIES: tuple[StudyRef, ...] = (
    StudyRef(
        "OSD-745", "Lettuce (VEG-01A/01B/03A)", "plant",
        "ICP-OES elemental, phenolic, anthocyanin and ORAC assays of "
        "Lactuca sativa cv. 'Outredgeous' grown in Veggie. Khodadad et al. 2020.",
    ),
    StudyRef(
        "OSD-655", "Tokyo Bekana (VEG-04A/04B)", "plant",
        "ICP-OES elemental, phenolic and ORAC assays of Brassica rapa cv. "
        "'Tokyo Bekana', plus per-pillow water delivery and harvest mass "
        "supplements. Bunchek et al. 2024.",
    ),
    StudyRef(
        "OSD-780", "Tokyo Bekana microbiology (VEG-04A)", "microbiology",
        "Aerobic plate counts and yeast/mould counts for the VEG-04 crop.",
    ),
    StudyRef(
        "OSD-575", "Inspiration4 clinical chemistry", "astronaut",
        "Comprehensive Metabolic Panel for four civilian astronauts across "
        "seven timepoints, including serum calcium, potassium, sodium, chloride "
        "and CO2 with per-analyte clinical reference ranges.",
    ),
)

# Studies located during the LSDA/OSDR survey that measure Veggie-crop nutrition
# or spaceflight plant mineral content, but which are not analysed here. Recorded
# so the scope boundary is explicit and the next study can pick them up.
EXPANSION_CANDIDATES: dict[str, str] = {
    "OSD-267": "Microbiological and nutritional analysis of ISS lettuce crops",
    "OSD-268": "Microbiological and nutritional analysis of ISS lettuce crops",
    "OSD-269": "Microbiological and nutritional analysis of ISS lettuce crops",
    "OSD-766": "Microbial communities of a Veggie tomato crop under differing light",
    "OSD-767": "Stress and light spectral quality in an ISS tomato crop (VEG-05)",
    "OSD-772": "PH-04 Chile Peppers in Space",
    "OSD-773": "XROOTS aeroponic/hydroponic plant growth technology demonstration",
}


def list_files(osd_id: str, *, force: bool = False) -> dict[str, dict]:
    """Return OSDR's file manifest for *osd_id* as ``{filename: metadata}``."""
    payload = fetch(
        FILES_API.format(osd_id=osd_id),
        RAW / osd_id / "_file_manifest.json",
        force=force,
    )
    manifest = json.loads(payload)
    return manifest[osd_id]["files"]


def file_url(entry: dict) -> str:
    """Resolve a manifest entry's ``URL`` field to an absolute URL.

    OSDR returns relative paths for some files and absolute for others; joining
    naively produces a double slash that happens to resolve but is not something
    to rely on.
    """
    url = entry["URL"]
    if url.startswith("http"):
        return url
    return f"{OSDR_BASE}/{url.lstrip('/')}"


def download(osd_id: str, filename: str, *, force: bool = False) -> bytes:
    """Download one named file from *osd_id*, caching it under ``data/raw/<osd_id>/``."""
    files = list_files(osd_id, force=force)
    if filename not in files:
        raise KeyError(
            f"{filename!r} is not in the OSDR manifest for {osd_id}. "
            f"Available: {sorted(files)[:5]}..."
        )
    # Slashes and spaces appear in OSDR filenames; keep the cache path flat and safe.
    safe_name = filename.replace("/", "_")
    return fetch(file_url(files[filename]), RAW / osd_id / safe_name, force=force)


def read_csv(osd_id: str, filename: str, *, force: bool = False) -> pd.DataFrame:
    """Download and parse a CSV from *osd_id*.

    ``utf-8-sig`` is used because several OSDR TRANSFORMED files begin with a
    byte-order mark, which would otherwise corrupt the first column name.
    Fully blank rows (OSDR pads some files with trailing commas) are dropped.
    """
    raw = download(osd_id, filename, force=force)
    frame = pd.read_csv(io.BytesIO(raw), encoding="utf-8-sig")
    return frame.dropna(how="all").reset_index(drop=True)


def find_file(osd_id: str, *must_contain: str, force: bool = False) -> str:
    """Return the single manifest filename containing every fragment in *must_contain*.

    Raises if the fragments match zero or more than one file, so that a change in
    OSDR's naming surfaces as a loud failure rather than a silently different file.
    """
    matches = [
        name for name in list_files(osd_id, force=force)
        if all(fragment.lower() in name.lower() for fragment in must_contain)
    ]
    if len(matches) != 1:
        raise LookupError(
            f"Expected exactly one file in {osd_id} matching {must_contain}, "
            f"found {len(matches)}: {matches}"
        )
    return matches[0]
