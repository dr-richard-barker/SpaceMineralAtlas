"""Flight-versus-ground contrasts for the plant antioxidant assays.

The central analytical problem
------------------------------
These assays were never analysed in this project before, and the predecessor
analysis of the same studies reported antioxidant flight effects that were
produced by ``numpy.random`` (see ``veggie_correction/CORRECTION_NOTE.md``). The
archive files themselves were only downloaded on 13 Oct 2026, by
``veggie_correction/fetch_antioxidant_data.py``.

The dominant structure in the measured data is **mission, not spaceflight**.
In the OSD-745 lettuce phenolics, the mission medians are roughly 5, 52 and 19
mg/g dry weight for VEG-01A, VEG-01B and VEG-03A -- a spread of about ten-fold.
Anthocyanin is worse: VEG-01A sits near 69 ug/mg while VEG-01B and VEG-03A sit
near 4, about seventeen-fold. The flight-versus-ground differences inside each
mission are of order 1.0-1.3x.

A pooled flight-versus-ground test over such data is not measuring spaceflight.
Whichever missions happen to contribute more flight than ground samples will
dominate the result, and the statistic will mostly reflect which missions are in
which arm. That is the same class of error as the dilution problem documented in
``plant_stats``: an artefact that looks like biology because nobody tested the
alternative.

Three views are therefore computed, and all are reported:

1. **Per-mission contrasts** -- descriptive fold change and a within-mission
   Mann-Whitney test. Honest but low-powered: n is 2-8 per arm per mission.
2. **Stratified (van Elteren) test** -- the correct pooled inference. Ranks are
   computed *within* each stratum and combined with weights 1/(N_h + 1), so a
   mission can never contribute a difference that is really a mission effect.
   This is the number to quote.
3. **Mission variance ratio** -- the ratio of the between-mission spread to the
   within-mission flight effect, reported explicitly so a reader can see why
   view 2 is required rather than taking it on trust.

For OSD-655 the light treatment (red / blue pillows) is a second blocking
factor, so strata there are mission x light.

Statistics follow ``plant_stats``: Mann-Whitney rather than t-tests (n is small,
normality is not established), Benjamini-Hochberg FDR across assays within a
crop, and rank-biserial correlation as the effect size, alongside the
descriptive fold change.

No value in this module is generated, defaulted or filled. A file that cannot be
parsed raises.
"""

from __future__ import annotations

import logging
import math
import re
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)

# The curated ALSDA "TRANSFORMED" products are authoritative: they carry the
# unit in the column name and one row per sample. The per-mission raw exports
# (Elemental-Phenolic-Anthocyanin-ORAC-VEG-*.csv) duplicate this content in a
# wide layout and are not read here.
SOURCES = {
    "lettuce": {
        "study": "OSD-745",
        "species": "Lactuca sativa",
        "cultivar": "Outredgeous",
        "reference": "Khodadad 2020",
        "files": {
            "orac": "LSDS-109_Oxygen Radical Absorbance Capacity_Khodadad2020_"
                    "OxygenRadicalAbsorbanceCapacity_TRANSFORMED.csv",
            "total_phenolics": "LSDS-109_Phenolic_Content_Khodadad2020_"
                               "PhenolicContent_TRANSFORMED.csv",
            "anthocyanin": "LSDS-109_Anthocyanin Content_Khodadad2020_"
                           "AnthocyaninContent_TRANSFORMED.csv",
        },
    },
    "tokyo_bekana": {
        "study": "OSD-655",
        "species": "Brassica rapa",
        "cultivar": "Tokyo Bekana",
        "reference": "Bunchek 2024",
        "files": {
            "orac": "LSDS-63_Oxygen Radical Absorbance Capacity_Bunchek2024_"
                    "ORAC_TRANSFORMED.csv",
            "total_phenolics": "LSDS-63_Phenolic_Content_Bunchek2024_"
                               "TotalPhenolic_TRANSFORMED.csv",
        },
    },
}

# Canonical reporting units. ug/mg and mg/g are the same ratio, so the
# anthocyanin conversion is an identity -- recorded rather than applied silently,
# matching the unit-provenance practice used for the elemental data.
CANONICAL_UNITS = {
    "orac": "umol_trolox_equivalents_per_gram_dry_weight",
    "total_phenolics": "milligram_per_gram_dry_weight",
    "anthocyanin": "milligram_per_gram_dry_weight",
}

UNIT_CONVERSIONS = {
    # (assay, source unit fragment) -> (factor, note)
    ("anthocyanin", "microgram_per_milligram"): (
        1.0,
        "ug/mg and mg/g are the same ratio; factor is exactly 1 (identity).",
    ),
}

# OSD-745: VEG-01A_A_Flight_33days
RE_745 = re.compile(r"^(VEG-\d+[AB])_([A-Z])_(Flight|Ground)_(\d+)days$")
# OSD-655: VEG04A_GC_leaf_pillow3_red
RE_655 = re.compile(r"^(VEG04[AB])_(GC|F)_leaf_pillow(\d+)_(red|blue)$")


def _parse_sample(crop: str, name: str) -> dict | None:
    name = name.strip()
    if crop == "lettuce":
        m = RE_745.match(name)
        if not m:
            return None
        return {"mission": m.group(1), "replicate": m.group(2),
                "condition": m.group(3), "light": None,
                "duration_days": int(m.group(4))}
    m = RE_655.match(name)
    if not m:
        return None
    return {"mission": m.group(1), "replicate": f"pillow{m.group(3)}",
            "condition": "Ground" if m.group(2) == "GC" else "Flight",
            "light": m.group(4), "duration_days": None}


def load(raw_root: Path) -> tuple[pd.DataFrame, list[dict]]:
    """Read every antioxidant TRANSFORMED file into one long table.

    Returns (frame, unit_provenance). Raises if a file is missing or yields no
    parseable rows -- a silent empty assay would be indistinguishable from an
    assay that genuinely found nothing.
    """
    rows: list[dict] = []
    provenance: list[dict] = []

    for crop, spec in SOURCES.items():
        study = spec["study"]
        for assay, filename in spec["files"].items():
            path = raw_root / study / filename
            if not path.exists():
                raise FileNotFoundError(
                    f"{path} is missing. Run "
                    f"`python3 -I veggie_correction/fetch_antioxidant_data.py` first."
                )
            frame = pd.read_csv(path, encoding="utf-8-sig")
            if frame.shape[1] < 2:
                raise ValueError(f"{path}: expected 2 columns, got {frame.shape[1]}")
            sample_col, value_col = frame.columns[0], frame.columns[1]

            factor, note = 1.0, "source unit already canonical"
            for (a, fragment), (f, n) in UNIT_CONVERSIONS.items():
                if a == assay and fragment in value_col:
                    factor, note = f, n
            provenance.append({
                "crop": crop, "study": study, "assay": assay,
                "source_column": value_col,
                "canonical_unit": CANONICAL_UNITS[assay],
                "factor_applied": factor, "note": note,
                "source_file": filename,
            })

            parsed = 0
            for _, record in frame.iterrows():
                name = str(record[sample_col]).strip()
                if not name or name.lower() == "nan":
                    continue          # trailing blank rows in the anthocyanin export
                value = pd.to_numeric(record[value_col], errors="coerce")
                if pd.isna(value):
                    continue
                meta = _parse_sample(crop, name)
                if meta is None:
                    raise ValueError(
                        f"{path}: unrecognised sample name {name!r}. Sample "
                        f"naming is the blocking variable; an unparsed name "
                        f"would silently drop a stratum."
                    )
                rows.append({
                    "crop": crop, "study": study,
                    "species": spec["species"], "cultivar": spec["cultivar"],
                    "assay": assay, "sample": name,
                    "unit": CANONICAL_UNITS[assay],
                    "value": float(value) * factor, **meta,
                })
                parsed += 1
            if parsed == 0:
                raise ValueError(f"{path}: no parseable rows")
            logger.info("%s %s: %d samples", study, assay, parsed)

    return pd.DataFrame(rows), provenance


def _tie_corrected_variance(ranks: np.ndarray, n1: int, n2: int) -> float:
    """Variance of the rank-sum under H0, with the standard tie correction."""
    total = n1 + n2
    if total < 2:
        return 0.0
    _, counts = np.unique(ranks, return_counts=True)
    tie_term = float(((counts ** 3) - counts).sum())
    return (n1 * n2 / 12.0) * ((total + 1) - tie_term / (total * (total - 1)))


def van_elteren(frame: pd.DataFrame, stratum_cols: list[str]) -> dict:
    """Stratified Wilcoxon rank-sum (van Elteren), flight versus ground.

    Ranks are computed inside each stratum and combined with design-free weights
    1/(N_h + 1), so between-stratum differences cannot contribute to the
    statistic. This is what makes the pooled number interpretable when mission
    dominates the variance.
    """
    numerator, variance, used, skipped = 0.0, 0.0, [], []

    for key, block in frame.groupby(stratum_cols, dropna=False):
        flight = block.loc[block["condition"] == "Flight", "value"].to_numpy()
        ground = block.loc[block["condition"] == "Ground", "value"].to_numpy()
        n1, n2 = len(flight), len(ground)
        label = "/".join(str(k) for k in (key if isinstance(key, tuple) else (key,)))
        if n1 == 0 or n2 == 0:
            skipped.append({"stratum": label, "n_flight": n1, "n_ground": n2,
                            "reason": "one arm empty"})
            continue
        ranks = stats.rankdata(np.concatenate([flight, ground]))
        rank_sum = float(ranks[:n1].sum())
        total = n1 + n2
        expected = n1 * (total + 1) / 2.0
        var = _tie_corrected_variance(ranks, n1, n2)
        weight = 1.0 / (total + 1)
        numerator += weight * (rank_sum - expected)
        variance += (weight ** 2) * var
        used.append({"stratum": label, "n_flight": n1, "n_ground": n2})

    if variance <= 0 or not used:
        return {"z": float("nan"), "p_value": float("nan"),
                "n_strata": len(used), "strata": used, "skipped": skipped}

    z = numerator / math.sqrt(variance)
    return {"z": float(z),
            "p_value": float(2.0 * (1.0 - stats.norm.cdf(abs(z)))),
            "n_strata": len(used), "strata": used, "skipped": skipped}


def benjamini_hochberg(pvalues: np.ndarray) -> np.ndarray:
    """BH step-up FDR. Mirrors plant_stats.benjamini_hochberg."""
    pvalues = np.asarray(pvalues, dtype=float)
    finite = ~np.isnan(pvalues)
    result = np.full_like(pvalues, np.nan)
    values = pvalues[finite]
    if values.size == 0:
        return result
    order = np.argsort(values)
    ranked = values[order]
    adjusted = ranked * values.size / (np.arange(values.size) + 1)
    adjusted = np.minimum.accumulate(adjusted[::-1])[::-1]
    out = np.empty_like(adjusted)
    out[order] = np.clip(adjusted, 0, 1)
    result[finite] = out
    return result


def rank_biserial(flight: np.ndarray, ground: np.ndarray, u_statistic: float) -> float:
    """Rank-biserial correlation, the effect size matching Mann-Whitney."""
    if len(flight) == 0 or len(ground) == 0:
        return float("nan")
    return 2.0 * u_statistic / (len(flight) * len(ground)) - 1.0


def per_mission(frame: pd.DataFrame) -> pd.DataFrame:
    """Descriptive flight/ground contrast within each mission (and light level)."""
    records = []
    for (crop, assay, mission, light), block in frame.groupby(
        ["crop", "assay", "mission", "light"], dropna=False
    ):
        flight = block.loc[block["condition"] == "Flight", "value"].to_numpy()
        ground = block.loc[block["condition"] == "Ground", "value"].to_numpy()
        if len(flight) == 0 or len(ground) == 0:
            continue
        median_f, median_g = float(np.median(flight)), float(np.median(ground))
        try:
            u, p = stats.mannwhitneyu(flight, ground, alternative="two-sided")
        except ValueError:
            u, p = float("nan"), float("nan")
        records.append({
            "crop": crop, "assay": assay, "mission": mission,
            "light": light if light is not None else "",
            "n_flight": len(flight), "n_ground": len(ground),
            "median_flight": median_f, "median_ground": median_g,
            "fold_change": median_f / median_g if median_g else float("nan"),
            "mannwhitney_u": float(u), "p_value": float(p),
            "rank_biserial": rank_biserial(flight, ground, float(u)),
        })
    return pd.DataFrame(records).sort_values(["crop", "assay", "mission", "light"])


def confound_scale(frame: pd.DataFrame, assay_rows: pd.DataFrame) -> dict:
    """Size the mission confound against the flight effect, as two plain numbers.

    ``between_mission_spread`` is max/min of the per-mission grand medians --
    how far apart the missions are from each other, ignoring condition.
    ``max_within_mission_fold`` is the largest flight/ground fold change seen
    inside any single mission, expressed as a ratio >= 1.

    Reported separately rather than as a single ratio: a composite collapses two
    quite different quantities into a number that is easy to misread, and the
    point here is to let a reader see both and judge for themselves whether
    stratification was necessary.
    """
    medians = frame.groupby("mission")["value"].median()
    between = (float(medians.max() / medians.min())
               if len(medians) >= 2 and medians.min() > 0 else float("nan"))
    folds = assay_rows["fold_change"].dropna()
    within = (float(max(folds.max(), 1.0 / folds.min()))
              if len(folds) and folds.min() > 0 else float("nan"))
    return {"between_mission_spread": between, "max_within_mission_fold": within}


def analyse(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (per-mission contrasts, stratified contrasts)."""
    missionwise = per_mission(frame)

    records = []
    for (crop, assay), block in frame.groupby(["crop", "assay"]):
        strata = ["mission"] if crop == "lettuce" else ["mission", "light"]
        result = van_elteren(block, strata)
        flight = block.loc[block["condition"] == "Flight", "value"].to_numpy()
        ground = block.loc[block["condition"] == "Ground", "value"].to_numpy()
        rows = missionwise[(missionwise["crop"] == crop) & (missionwise["assay"] == assay)]
        records.append({
            "crop": crop, "assay": assay,
            "unit": block["unit"].iloc[0],
            "strata": "x".join(strata),
            "n_strata": result["n_strata"],
            "n_flight": len(flight), "n_ground": len(ground),
            "median_flight": float(np.median(flight)) if len(flight) else float("nan"),
            "median_ground": float(np.median(ground)) if len(ground) else float("nan"),
            "pooled_fold_change": (float(np.median(flight)) / float(np.median(ground))
                                   if len(ground) and np.median(ground) else float("nan")),
            "van_elteren_z": result["z"],
            "p_value": result["p_value"],
            **confound_scale(block, rows),
            "n_strata_dropped": len(result["skipped"]),
        })

    stratified = pd.DataFrame(records)
    # FDR across assays within a crop.
    stratified["p_value_fdr"] = np.nan
    for crop, block in stratified.groupby("crop"):
        stratified.loc[block.index, "p_value_fdr"] = benjamini_hochberg(
            block["p_value"].to_numpy()
        )
    stratified["significant_fdr05"] = stratified["p_value_fdr"] < 0.05
    return missionwise, stratified.sort_values(["crop", "assay"])
