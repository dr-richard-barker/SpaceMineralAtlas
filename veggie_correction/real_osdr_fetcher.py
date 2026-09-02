#!/usr/bin/env python3
"""Drop-in replacement for OSDR-Veggie-Nutrition-Dashboard/data/fetch_osdr_data.py.

Downloads the genuine NASA OSDR elemental data for the Veggie studies. This is a
standalone script with no dependency on the SpaceMineralAtlas package: copy it
into the subject repository as `data/fetch_osdr_data.py` and run it in place of
the original.

Differences from the file it replaces:

* It actually uses the OSDR response. The original contacted the API, logged
  "Simulating 502 Bad Gateway fallback", and returned False unconditionally,
  which routed every run into a numpy.random data generator.
* **It has no synthetic fallback.** A failed download raises. A pipeline that
  cannot obtain its data should stop, not silently substitute numbers that look
  like data.
* It corrects the OSD-655 unit-labelling defect: five columns are labelled mg/g
  dry weight when the values are ug/g. See ../fair/osdr_curation_report.md.
* It emits boron (measured by OSD-745) and does not invent copper for that study.

Usage:
    python real_osdr_fetcher.py --outdir data/raw

Requires: requests, pandas.
"""

from __future__ import annotations

import argparse
import io
import json
import logging
import sys
import time
from pathlib import Path

import pandas as pd
import requests

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

FILES_API = "https://visualization.osdr.nasa.gov/biodata/api/v2/dataset/{osd_id}/files/"
OSDR_BASE = "https://osdr.nasa.gov"

# The curated TRANSFORMED products carry the unit in each column name.
SOURCES = {
    "OSD-745": {
        "fragments": ("ICPOESpectroscopy", "Khodadad2020", "TRANSFORMED"),
        "crop": "lettuce",
        "species": "Lactuca sativa",
        "cultivar": "Outredgeous",
    },
    "OSD-655": {
        "fragments": ("ICPOES", "Bunchek2024", "TRANSFORMED"),
        "crop": "tokyo_bekana",
        "species": "Brassica rapa",
        "cultivar": "Tokyo Bekana",
    },
}

# OSD-655 labels these five columns milligram_per_gram when the values are
# microgram_per_gram. Read as stated, potassium would be 2943% of dry weight.
OSD655_MISLABELLED = {"calcium", "potassium", "magnesium", "phosphorus", "sulfur"}

# Any single element above 10% of dry weight indicates a unit error, not biology.
MAX_PLAUSIBLE_UG_PER_G = 100_000


def get(url: str, *, retries: int = 4, timeout: int = 90) -> bytes:
    """Fetch a URL, retrying transient failures. Raises if it cannot succeed."""
    last: Exception | None = None
    for attempt in range(retries):
        try:
            response = requests.get(
                url, timeout=timeout,
                headers={"User-Agent": "VeggieRealDataFetcher/1.0 (research)"},
            )
            response.raise_for_status()
            return response.content
        except Exception as error:  # noqa: BLE001
            last = error
            if attempt < retries - 1:
                wait = 2 ** attempt
                logger.warning("attempt %d/%d failed (%s); retrying in %ds",
                               attempt + 1, retries, error, wait)
                time.sleep(wait)
    raise RuntimeError(f"Could not retrieve {url} after {retries} attempts: {last}")


def find_file(osd_id: str, *fragments: str) -> tuple[str, str]:
    """Return (filename, absolute_url) for the single manifest match."""
    manifest = json.loads(get(FILES_API.format(osd_id=osd_id)))
    files = manifest[osd_id]["files"]
    matches = [
        name for name in files
        if all(fragment.lower() in name.lower() for fragment in fragments)
    ]
    if len(matches) != 1:
        raise LookupError(
            f"{osd_id}: expected one file matching {fragments}, found {len(matches)}"
        )
    name = matches[0]
    url = files[name]["URL"]
    return name, (url if url.startswith("http") else f"{OSDR_BASE}/{url.lstrip('/')}")


def parse_unit(column: str) -> tuple[str | None, str | None]:
    """Split '<element>_<unit>_of_dry_weight' into (element, unit)."""
    import re
    match = re.match(r"^([a-z]+)_((?:micro|milli)?gram_per_(?:gram|kilogram))", column)
    return (match.group(1), match.group(2)) if match else (None, None)


def to_micrograms_per_gram(frame: pd.DataFrame, osd_id: str) -> pd.DataFrame:
    """Convert every elemental column to ug/g dry weight, correcting OSD-655."""
    factors = {
        "microgram_per_gram": 1.0,
        "milligram_per_kilogram": 1.0,   # identical to ug/g
        "milligram_per_gram": 1000.0,
    }
    out = pd.DataFrame(index=frame.index)

    for column in frame.columns:
        element, unit = parse_unit(column)
        if element is None:
            continue
        if osd_id == "OSD-655" and element in OSD655_MISLABELLED:
            logger.info("  %s: '%s' labelled %s but values are ug/g -- correcting",
                        osd_id, element, unit)
            unit = "microgram_per_gram"
        factor = factors.get(unit)
        if factor is None:
            logger.warning("  %s: unrecognised unit %r on %r; skipped", osd_id, unit, column)
            continue
        out[element] = pd.to_numeric(frame[column], errors="coerce") * factor

    # Independent verification that the correction produced sane values.
    for element in out.columns:
        worst = out[element].max()
        if pd.notna(worst) and worst > MAX_PLAUSIBLE_UG_PER_G:
            raise ValueError(
                f"{osd_id}: {element} reaches {worst:.0f} ug/g "
                f"({worst / 10_000:.1f}% of dry weight), which is not physically "
                f"possible. A unit is being interpreted incorrectly."
            )
    return out


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Download real NASA OSDR Veggie elemental data."
    )
    parser.add_argument("--outdir", default="data/raw", help="output directory")
    args = parser.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    frames = []
    for osd_id, spec in SOURCES.items():
        logger.info("Fetching %s from OSDR...", osd_id)
        name, url = find_file(osd_id, *spec["fragments"])
        logger.info("  file: %s", name)

        raw = get(url)
        (outdir / name.replace("/", "_")).write_bytes(raw)

        frame = pd.read_csv(io.BytesIO(raw), encoding="utf-8-sig").dropna(how="all")
        frame = frame[frame["Sample Name"].notna()]

        elements = to_micrograms_per_gram(frame, osd_id)
        elements.insert(0, "sample_name", frame["Sample Name"].values)
        elements.insert(0, "osd_id", osd_id)
        for key in ("crop", "species", "cultivar"):
            elements[key] = spec[key]

        frames.append(elements)
        logger.info("  %d real samples, %d elements", len(elements), len(elements.columns) - 5)

    combined = pd.concat(frames, ignore_index=True, sort=False)
    destination = outdir.parent / "processed" / "veggie_elemental_real_ugg.csv"
    destination.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(destination, index=False)

    logger.info("=" * 66)
    logger.info("Wrote %s", destination)
    logger.info("%d real samples (no synthetic data was generated)", len(combined))
    logger.info("Units: micrograms per gram dry weight throughout")
    logger.info("=" * 66)
    return 0


if __name__ == "__main__":
    sys.exit(main())
