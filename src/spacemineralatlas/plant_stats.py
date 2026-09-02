"""Flight-versus-ground contrasts for the plant elemental data.

The central analytical problem
------------------------------
ICP-OES reports each element as a *concentration* -- mass of element per mass of
dried tissue. Concentrations are compositional: they share a fixed denominator, so
they cannot all move independently. If flight tissue differs from ground tissue in
water content, structural carbohydrate, or anything else that changes dry-matter
composition, then every element's concentration shifts together even when the
plant's actual elemental uptake did not change.

This matters acutely here. In the raw Tokyo Bekana data almost every element is
elevated in flight (Na 2.15x, S 1.75x, K 1.54x, Fe 1.44x, P 1.36x, B 1.35x,
Ca 1.23x, Mg 1.23x). A coordinated rise of that kind is the signature of a
denominator effect, not of eight independent uptake changes. Reporting those
ratios as biology without testing that alternative would be unsafe.

Three independent views are therefore computed, and the manuscript reports all of
them rather than choosing the most favourable:

1. **Raw concentration ratios** -- what the source data say at face value.
2. **Centred log-ratio (CLR)** -- the standard remedy for closure. Each value is
   divided by the geometric mean of all elements in that sample and log-transformed,
   which removes any per-sample scaling factor exactly. A CLR contrast asks
   "did this element change *relative to the rest of the ionome*", which is
   invariant to dry-matter dilution.
3. **Aluminium as an internal reference** -- Al is not a plant nutrient and is
   taken up passively; it should not respond to spaceflight physiologically. In
   the Tokyo Bekana data it moves in the *opposite* direction to everything else
   (0.45x), which is evidence against simple dilution and is worth reporting
   explicitly. Available for OSD-655 only, since OSD-745 did not measure it.

Statistics use Mann-Whitney U rather than t-tests (n is 11-18 per arm, normality
is not established) and Benjamini-Hochberg FDR control across elements within
each crop. Effect sizes are reported as rank-biserial correlation, the effect size
that corresponds to Mann-Whitney, alongside the descriptive fold change.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from scipy import stats

from .harmonise import ELEMENT_SYMBOLS

logger = logging.getLogger(__name__)

# Elements excluded from the CLR composition. Aluminium is a non-nutrient
# contaminant whose inclusion would let soil/substrate carryover drive the
# geometric mean; it is analysed separately as a reference element instead.
CLR_EXCLUDE = {"aluminium"}


def elements_in(frame: pd.DataFrame) -> list[str]:
    """Return the elemental columns present in *frame*, in a stable order."""
    return [e for e in sorted(ELEMENT_SYMBOLS) if e in frame.columns]


def clr_transform(frame: pd.DataFrame, elements: list[str]) -> pd.DataFrame:
    """Centred log-ratio transform of *elements* within each row of *frame*.

    For a sample with parts x1..xD, ``clr(xi) = log(xi) - mean(log(x1..xD))``.
    Subtracting the log geometric mean removes any per-sample multiplicative
    factor, which is exactly what a dry-matter dilution acts as.

    Choosing the parts
    ------------------
    A CLR is defined relative to a chosen set of parts, and every sample must
    contribute the same set or the geometric means are not comparable. Missingness
    in these studies is structural rather than random -- VEG-03A did not assay
    boron at all, so all twelve of its samples lack that one element while being
    otherwise complete. Dropping incomplete *rows* would therefore discard an
    entire mission (half the lettuce dataset) to accommodate a single element.

    This function instead drops incomplete *columns*: a part is admitted only if
    it is present and positive in every sample. That keeps all samples and costs
    only the elements that were never measured consistently. Both the retained and
    the excluded parts are logged, since the composition's membership changes what
    a CLR value means.
    """
    candidates = [e for e in elements if e not in CLR_EXCLUDE]
    values = frame[candidates].apply(pd.to_numeric, errors="coerce")

    complete = [c for c in candidates if values[c].notna().all() and (values[c] > 0).all()]
    excluded = [c for c in candidates if c not in complete]

    if excluded:
        logger.info(
            "CLR: composition uses %d parts (%s); excluded %s "
            "(not measured in every sample of this group)",
            len(complete), ", ".join(complete), ", ".join(excluded),
        )
    if len(complete) < 3:
        raise ValueError(
            f"CLR needs at least 3 complete parts, found {len(complete)}: {complete}"
        )

    logs = np.log(values[complete])
    centred = logs.sub(logs.mean(axis=1), axis=0)
    centred.columns = [f"clr_{c}" for c in centred.columns]
    return centred


def rank_biserial(flight: np.ndarray, ground: np.ndarray, u_statistic: float) -> float:
    """Rank-biserial correlation, the effect size matching Mann-Whitney U.

    Ranges from -1 to +1; positive means flight values tend to exceed ground.
    """
    return 2.0 * u_statistic / (len(flight) * len(ground)) - 1.0


def benjamini_hochberg(pvalues: np.ndarray) -> np.ndarray:
    """Benjamini-Hochberg step-up FDR-adjusted p-values."""
    pvalues = np.asarray(pvalues, dtype=float)
    n = len(pvalues)
    order = np.argsort(pvalues)
    ranked = pvalues[order]
    adjusted = ranked * n / np.arange(1, n + 1)
    # Enforce monotonicity walking back up the sorted list.
    adjusted = np.minimum.accumulate(adjusted[::-1])[::-1]
    result = np.empty(n, dtype=float)
    result[order] = np.clip(adjusted, 0, 1)
    return result


def contrast(
    frame: pd.DataFrame,
    elements: list[str],
    *,
    label: str,
    value_kind: str,
) -> pd.DataFrame:
    """Flight-versus-ground contrast for each element in *frame*.

    *value_kind* is ``"concentration"`` (fold change reported as a ratio) or
    ``"clr"`` (reported as a difference, since CLR values are logs and can be
    negative, making a ratio meaningless).
    """
    flight_rows = frame[frame["condition"] == "Flight"]
    ground_rows = frame[frame["condition"] == "Ground"]

    records = []
    for element in elements:
        flight = pd.to_numeric(flight_rows[element], errors="coerce").dropna().to_numpy()
        ground = pd.to_numeric(ground_rows[element], errors="coerce").dropna().to_numpy()
        if len(flight) < 3 or len(ground) < 3:
            continue

        u_statistic, p_value = stats.mannwhitneyu(flight, ground, alternative="two-sided")

        record = {
            "group": label,
            "element": element.removeprefix("clr_"),
            "value_kind": value_kind,
            "n_flight": len(flight),
            "n_ground": len(ground),
            "mean_flight": float(np.mean(flight)),
            "mean_ground": float(np.mean(ground)),
            "median_flight": float(np.median(flight)),
            "median_ground": float(np.median(ground)),
            "u_statistic": float(u_statistic),
            "p_value": float(p_value),
            "rank_biserial": float(rank_biserial(flight, ground, u_statistic)),
        }
        if value_kind == "concentration":
            record["fold_change"] = (
                float(np.mean(flight) / np.mean(ground)) if np.mean(ground) else np.nan
            )
            record["log2_fold_change"] = (
                float(np.log2(record["fold_change"]))
                if record["fold_change"] and record["fold_change"] > 0 else np.nan
            )
        else:
            # CLR values are already logs; the contrast is a difference, and
            # exponentiating it recovers the ratio-to-geometric-mean change.
            record["clr_difference"] = float(np.mean(flight) - np.mean(ground))
            record["fold_change"] = float(np.exp(record["clr_difference"]))
            record["log2_fold_change"] = float(record["clr_difference"] / np.log(2))

        records.append(record)

    result = pd.DataFrame(records)
    if not result.empty:
        result["p_adjusted_bh"] = benjamini_hochberg(result["p_value"].to_numpy())
        result["significant_fdr05"] = result["p_adjusted_bh"] < 0.05
        result = result.sort_values("p_adjusted_bh")
    return result


def analyse(frame: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Run the full contrast suite: raw concentration and CLR, per crop.

    Returns a dict of named tables ready for serialisation and plotting.
    """
    outputs: dict[str, pd.DataFrame] = {}
    raw_parts, clr_parts = [], []

    for crop, crop_frame in frame.groupby("crop"):
        # Elements this crop actually measured (Al and Cu are OSD-655 only).
        measured = [
            e for e in elements_in(crop_frame)
            if pd.to_numeric(crop_frame[e], errors="coerce").notna().sum() >= 6
        ]

        raw_parts.append(
            contrast(crop_frame, measured, label=crop, value_kind="concentration")
        )

        clr_values = clr_transform(crop_frame, measured)
        clr_frame = pd.concat(
            [crop_frame.loc[clr_values.index, ["condition", "mission"]], clr_values],
            axis=1,
        )
        clr_parts.append(
            contrast(
                clr_frame, list(clr_values.columns), label=crop, value_kind="clr"
            )
        )
        logger.info(
            "%s: %d elements contrasted (%d flight / %d ground)",
            crop, len(measured),
            (crop_frame["condition"] == "Flight").sum(),
            (crop_frame["condition"] == "Ground").sum(),
        )

    outputs["concentration"] = pd.concat(raw_parts, ignore_index=True)
    outputs["clr"] = pd.concat(clr_parts, ignore_index=True)

    # Side-by-side view: does an element's direction survive the CLR correction?
    merged = outputs["concentration"].merge(
        outputs["clr"], on=["group", "element"], suffixes=("_conc", "_clr")
    )
    merged["direction_conc"] = np.sign(merged["log2_fold_change_conc"])
    merged["direction_clr"] = np.sign(merged["log2_fold_change_clr"])
    merged["direction_preserved"] = merged["direction_conc"] == merged["direction_clr"]
    merged["significant_both"] = (
        merged["significant_fdr05_conc"] & merged["significant_fdr05_clr"]
    )
    outputs["comparison"] = merged[[
        "group", "element",
        "fold_change_conc", "p_adjusted_bh_conc", "significant_fdr05_conc",
        "fold_change_clr", "p_adjusted_bh_clr", "significant_fdr05_clr",
        "direction_preserved", "significant_both",
    ]].sort_values(["group", "element"])

    return outputs


def crop_divergence(comparison: pd.DataFrame) -> pd.DataFrame:
    """Per-element comparison of the two crops' flight responses.

    This is the table behind the manuscript's central claim: whether the two
    Veggie crops respond to spaceflight in the same direction.
    """
    wide = comparison.pivot(
        index="element",
        columns="group",
        values=["fold_change_conc", "fold_change_clr",
                "significant_fdr05_conc", "significant_fdr05_clr"],
    )
    wide.columns = [f"{stat}__{crop}" for stat, crop in wide.columns]
    wide = wide.reset_index()

    crops = sorted(comparison["group"].unique())
    if len(crops) == 2:
        left, right = crops
        for kind in ("conc", "clr"):
            lcol, rcol = f"fold_change_{kind}__{left}", f"fold_change_{kind}__{right}"
            if lcol in wide and rcol in wide:
                # Elements measured by only one crop pivot to NaN and the column
                # becomes object dtype, so coerce before any numeric comparison.
                left_fc = pd.to_numeric(wide[lcol], errors="coerce")
                right_fc = pd.to_numeric(wide[rcol], errors="coerce")
                # Divergent = the two crops move in opposite directions relative
                # to no change (fold change 1.0). NaN on either side yields False,
                # since an element measured in one crop cannot be said to diverge.
                wide[f"divergent_{kind}"] = (
                    (np.sign(left_fc - 1.0) != np.sign(right_fc - 1.0))
                    & left_fc.notna() & right_fc.notna()
                )
                wide[f"ratio_between_crops_{kind}"] = right_fc / left_fc
    return wide
