"""Astronaut serum mineral data from the Inspiration4 clinical chemistry panel.

Source
------
OSD-575, ``LSDS-8_Comprehensive_Metabolic_Panel_CMP_TRANSFORMED.csv``: four
civilian astronauts (C001-C004) sampled at seven timepoints across a three-day
low-Earth-orbit mission. Sample names encode subject and timepoint as
``C001_serum_L-3``, where ``L-`` is days before launch and ``R+`` days after return.

The panel directly measures four of the minerals relevant to this project --
calcium, potassium, sodium and chloride -- plus bicarbonate (reported as CO2).
Iron is not measured; the Inspiration4 CBC reports haemoglobin, which is at best
an indirect proxy and is treated as such here.

What makes this file unusually useful is that OSDR carries the clinical reference
range with every analyte (``<analyte>_range_min_*`` / ``_range_max_*``). That
allows each value to be expressed as a position within its own normal range,
which is both more interpretable than a raw concentration and comparable across
analytes measured in different units.

Scope limits, stated plainly
----------------------------
Four subjects, one three-day mission, and no in-flight sample: every timepoint is
pre-flight or post-return. These data can describe what happened to four people;
they cannot establish a spaceflight effect on serum minerals, and no test in this
module should be read as attempting to. The dataset that could support that claim
is SMO-016E (27 astronauts, ~165-day missions, in-flight sampling), which is not
openly available -- see ``lsda_request/``.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import numpy as np
import pandas as pd

from . import osdr_client

logger = logging.getLogger(__name__)

OSD_ID = "OSD-575"

# Minerals and electrolytes in the CMP, mapped to the column prefix OSDR uses.
SERUM_MINERALS: dict[str, str] = {
    "calcium": "calcium",
    "potassium": "potassium",
    "sodium": "sodium",
    "chloride": "chloride",
    "carbon_dioxide": "carbon_dioxide",   # bicarbonate / total CO2
}

# Ordering for the flight timeline. Negative = days before launch, positive =
# days after return. Used for plotting and for splitting pre- from post-flight.
TIMEPOINT_DAYS: dict[str, int] = {
    "L-92": -92, "L-44": -44, "L-3": -3,
    "R+1": 1, "R+45": 45, "R+82": 82, "R+194": 194,
}


def parse_sample_name(name: str) -> dict:
    """Parse ``C001_serum_L-3`` into subject, matrix and timepoint."""
    match = re.match(
        r"^(?P<subject>C\d+)_(?P<matrix>\w+)_(?P<timepoint>[LR][-+]\d+)$", name.strip()
    )
    if not match:
        return {}
    parts = match.groupdict()
    timepoint = parts["timepoint"]
    return {
        "subject": parts["subject"],
        "matrix": parts["matrix"],
        "timepoint": timepoint,
        "day_relative": TIMEPOINT_DAYS.get(timepoint),
        "phase": "preflight" if timepoint.startswith("L-") else "postflight",
    }


def load_cmp(*, force: bool = False) -> pd.DataFrame:
    """Load and reshape the Inspiration4 CMP into one row per subject-timepoint.

    Returns columns for each mineral's value, its reference range, and a
    ``*_range_position`` giving where the value sits within that range
    (0 = lower limit, 1 = upper limit, outside [0,1] = outside the normal range).
    """
    filename = osdr_client.find_file(
        OSD_ID, "Comprehensive_Metabolic_Panel", "TRANSFORMED", force=force
    )
    raw = osdr_client.read_csv(OSD_ID, filename, force=force)
    raw = raw[raw["Sample Name"].notna()]

    design = pd.DataFrame([parse_sample_name(n) for n in raw["Sample Name"]],
                          index=raw.index)
    unparsed = design["subject"].isna().sum() if "subject" in design else len(design)
    if unparsed:
        raise ValueError(
            f"{OSD_ID}: {unparsed} sample name(s) did not match the expected "
            f"'C###_matrix_timepoint' convention; refusing to guess."
        )

    frame = design.copy()
    frame.insert(0, "sample_name", raw["Sample Name"].values)

    for mineral, prefix in SERUM_MINERALS.items():
        value_col = _find_column(raw, f"{prefix}_value")
        min_col = _find_column(raw, f"{prefix}_range_min")
        max_col = _find_column(raw, f"{prefix}_range_max")
        if value_col is None:
            logger.warning("%s: no value column found for %s", OSD_ID, mineral)
            continue

        frame[mineral] = pd.to_numeric(raw[value_col], errors="coerce")
        frame[f"{mineral}_unit"] = _unit_from_column(value_col)

        if min_col and max_col:
            low = pd.to_numeric(raw[min_col], errors="coerce")
            high = pd.to_numeric(raw[max_col], errors="coerce")
            frame[f"{mineral}_range_min"] = low
            frame[f"{mineral}_range_max"] = high
            span = (high - low).replace(0, np.nan)
            frame[f"{mineral}_range_position"] = (frame[mineral] - low) / span
            frame[f"{mineral}_out_of_range"] = (
                (frame[mineral] < low) | (frame[mineral] > high)
            )

    frame = frame.sort_values(["subject", "day_relative"]).reset_index(drop=True)
    logger.info(
        "%s: %d subject-timepoint rows (%d subjects x %d timepoints)",
        OSD_ID, len(frame), frame["subject"].nunique(), frame["timepoint"].nunique(),
    )
    return frame


def _find_column(frame: pd.DataFrame, prefix: str) -> str | None:
    """Return the first column starting with *prefix*, or None."""
    for column in frame.columns:
        if column.lower().startswith(prefix.lower()):
            return column
    return None


def _unit_from_column(column: str) -> str:
    """Recover the unit that OSDR appended to a CMP column name."""
    match = re.search(
        r"_value_(.+)$|_(gram_per_deciliter|millimoles?_per_liter|"
        r"milligram_per_deciliter|units_per_liter)$", column
    )
    return (match.group(1) or match.group(2)) if match else "unknown"


def per_subject_change(frame: pd.DataFrame) -> pd.DataFrame:
    """Within-subject change from pre-flight baseline to immediate return (R+1).

    Baseline is each subject's mean across their pre-flight timepoints, which is
    more stable than any single draw. Reported per subject rather than pooled:
    with four people, a group mean conceals more than it reveals.
    """
    records = []
    for subject, subject_frame in frame.groupby("subject"):
        preflight = subject_frame[subject_frame["phase"] == "preflight"]
        return_row = subject_frame[subject_frame["timepoint"] == "R+1"]
        if preflight.empty or return_row.empty:
            continue

        for mineral in SERUM_MINERALS:
            if mineral not in subject_frame.columns:
                continue
            baseline = preflight[mineral].mean()
            at_return = return_row[mineral].iloc[0]
            if pd.isna(baseline) or pd.isna(at_return):
                continue
            records.append({
                "subject": subject,
                "mineral": mineral,
                "preflight_mean": float(baseline),
                "R+1": float(at_return),
                "absolute_change": float(at_return - baseline),
                "percent_change": float(100 * (at_return - baseline) / baseline),
                "direction": "decrease" if at_return < baseline else
                             ("increase" if at_return > baseline else "unchanged"),
                "n_preflight_samples": int(preflight[mineral].notna().sum()),
            })
    return pd.DataFrame(records)


def summarise(frame: pd.DataFrame, changes: pd.DataFrame) -> dict:
    """Descriptive summary of the astronaut serum data for the manuscript.

    Deliberately descriptive. With n=4 and no in-flight sampling, the honest
    output is a count of how many subjects moved in each direction, not a p-value.
    """
    summary: dict = {
        "source": f"NASA OSDR {OSD_ID} (Inspiration4 Comprehensive Metabolic Panel)",
        "n_subjects": int(frame["subject"].nunique()),
        "n_timepoints": int(frame["timepoint"].nunique()),
        "n_observations": int(len(frame)),
        "timepoints": sorted(frame["timepoint"].unique(),
                             key=lambda t: TIMEPOINT_DAYS.get(t, 0)),
        "mission_duration_days": 3,
        "inflight_samples": 0,
        "minerals_measured": [m for m in SERUM_MINERALS if m in frame.columns],
        "by_mineral": {},
    }

    for mineral in SERUM_MINERALS:
        if mineral not in frame.columns:
            continue
        mineral_changes = changes[changes["mineral"] == mineral]
        entry = {
            "unit": (frame[f"{mineral}_unit"].dropna().iloc[0]
                     if f"{mineral}_unit" in frame else "unknown"),
            "observed_min": float(frame[mineral].min()),
            "observed_max": float(frame[mineral].max()),
            "n_decreased_at_return": int((mineral_changes["direction"] == "decrease").sum()),
            "n_increased_at_return": int((mineral_changes["direction"] == "increase").sum()),
            "n_subjects_compared": int(len(mineral_changes)),
            "median_percent_change": (
                float(mineral_changes["percent_change"].median())
                if not mineral_changes.empty else None
            ),
        }
        if f"{mineral}_out_of_range" in frame:
            entry["n_observations_outside_reference_range"] = int(
                frame[f"{mineral}_out_of_range"].sum()
            )
        summary["by_mineral"][mineral] = entry

    return summary


# ---------------------------------------------------------------------------
# Ingest slot for the request-gated dataset
# ---------------------------------------------------------------------------

SMO016E_DIRECTORY = "data/raw/smo016e"


def load_smo016e(*, path: str | None = None) -> pd.DataFrame:
    """Load SMO-016E Nutritional Status Assessment data, once it has been granted.

    This is the ingest point for the dataset that would let this project relate
    dietary mineral intake to crew mineral status: 27 astronauts across
    long-duration ISS missions, eight timepoints including three in-flight, with
    recorded dietary intake alongside serum and urine chemistry.

    Those data are held by the NASA Life Sciences Data Archive and are not
    openly downloadable. ``lsda_request/`` contains a prepared request, the list
    of variables sought, and ``target_schema.json`` describing the shape this
    function returns. Place the delivered files under
    :data:`SMO016E_DIRECTORY` and this loader will map them into that schema;
    nothing downstream needs to change.

    Raises
    ------
    FileNotFoundError
        Always, until the data are present. This function has no fallback and
        never substitutes OSD-575 or any other dataset: the whole point of
        SMO-016E is the in-flight sampling and dietary intake that no open
        dataset provides, so quietly analysing a substitute would answer a
        different question while appearing to answer this one.
    """
    from .paths import REPO_ROOT

    directory = Path(path) if path else REPO_ROOT / SMO016E_DIRECTORY
    files = sorted(directory.glob("*.csv")) if directory.is_dir() else []

    if not files:
        raise FileNotFoundError(
            f"No SMO-016E data found at {directory}.\n\n"
            f"These data are request-gated. To obtain them:\n"
            f"  1. Submit the prepared request in lsda_request/ to\n"
            f"     https://nlsp.nasa.gov/explore/lsdahome/datarequest\n"
            f"  2. Place the delivered files in {directory}\n"
            f"  3. Re-run this analysis\n\n"
            f"The expected schema is documented in lsda_request/target_schema.json.\n"
            f"No substitute dataset is used in the meantime."
        )

    frames = [pd.read_csv(f, encoding="utf-8-sig") for f in files]
    combined = pd.concat(frames, ignore_index=True, sort=False)
    logger.info("SMO-016E: loaded %d rows from %d file(s)", len(combined), len(files))
    return combined
