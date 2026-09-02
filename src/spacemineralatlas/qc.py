"""Quality-control gates run between curation and analysis.

These checks are deliberately independent of ``harmonise.py``: that module knows
which correction it intends to apply, whereas these functions only know what a
plant can physically contain. If the two ever disagree the build stops, so a
future unit change cannot quietly propagate into the results.

Every check returns a structured record rather than raising immediately, so a
single run reports all problems at once instead of one per invocation.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field

import pandas as pd

from .harmonise import (
    ELEMENT_SYMBOLS,
    MAX_PLAUSIBLE_FRACTION_OF_DRY_WEIGHT,
    MAX_PLAUSIBLE_UG_PER_G,
)

logger = logging.getLogger(__name__)


@dataclass
class CheckResult:
    """Outcome of one QC check."""

    name: str
    passed: bool
    detail: str
    data: dict = field(default_factory=dict)


def check_physical_plausibility(frame: pd.DataFrame) -> CheckResult:
    """Fail if any element exceeds a credible fraction of dry weight.

    This is the gate that catches a 1000x unit error. Interpreted as mg/g, the
    uncorrected OSD-655 potassium column averages 2,943% of dry weight and would
    trip this check immediately.
    """
    offenders = {}
    for element in [c for c in frame.columns if c in ELEMENT_SYMBOLS]:
        worst = frame[element].max()
        if pd.notna(worst) and worst > MAX_PLAUSIBLE_UG_PER_G:
            offenders[element] = {
                "max_ug_per_g": float(worst),
                "percent_of_dry_weight": float(worst / 10_000),
            }

    if offenders:
        detail = (
            f"{len(offenders)} element(s) exceed "
            f"{MAX_PLAUSIBLE_FRACTION_OF_DRY_WEIGHT:.0%} of dry weight: "
            + ", ".join(
                f"{el} at {v['percent_of_dry_weight']:.1f}%"
                for el, v in offenders.items()
            )
        )
        return CheckResult("physical_plausibility", False, detail, offenders)

    return CheckResult(
        "physical_plausibility", True,
        f"all {sum(c in ELEMENT_SYMBOLS for c in frame.columns)} elements within "
        f"{MAX_PLAUSIBLE_FRACTION_OF_DRY_WEIGHT:.0%} of dry weight",
    )


def check_cross_study_agreement(
    frame: pd.DataFrame, *, tolerance_fold: float = 10.0
) -> CheckResult:
    """Fail if the two crops' ground-control means differ by more than *tolerance_fold*.

    Both studies grew leafy greens in the same hardware under comparable nutrient
    supply, so their ground-control tissue concentrations should sit within a small
    multiple of each other. A 1000x labelling error shows up here as a
    three-order-of-magnitude discrepancy.

    The 10x tolerance is calibrated to separate unit errors from biology, and sits
    two orders of magnitude below the error it is designed to catch. It has to be
    this loose because genuine between-species differences in these studies are
    already large: ground-control sodium differs 5.4-fold between lettuce
    (1965 ug/g) and Tokyo Bekana (363 ug/g). Sodium is not an essential
    macronutrient for either crop, so its tissue concentration tracks the nutrient
    solution and the species' exclusion behaviour rather than a regulated set
    point, and a five-fold difference between a Lactuca and a Brassica is
    unremarkable. Tightening this check to catch that difference would make it
    report species biology as a data defect.
    """
    ground = frame[frame["condition"] == "Ground"]
    shared = [
        element for element in ELEMENT_SYMBOLS
        if element in frame.columns
        and ground.groupby("crop")[element].count().gt(0).sum() == 2
    ]

    ratios, offenders = {}, {}
    for element in shared:
        means = ground.groupby("crop")[element].mean().dropna()
        if len(means) != 2 or means.min() <= 0:
            continue
        fold = float(means.max() / means.min())
        ratios[element] = round(fold, 3)
        if fold > tolerance_fold:
            offenders[element] = {
                "fold_difference": fold,
                "means_ug_per_g": {k: float(v) for k, v in means.items()},
            }

    if offenders:
        return CheckResult(
            "cross_study_agreement", False,
            f"{len(offenders)} element(s) differ >{tolerance_fold}x between crops "
            f"in ground controls: " + ", ".join(
                f"{el} {v['fold_difference']:.1f}x" for el, v in offenders.items()
            ),
            {"offenders": offenders, "all_ratios": ratios},
        )

    return CheckResult(
        "cross_study_agreement", True,
        f"all {len(ratios)} shared elements agree within {tolerance_fold}x "
        f"between crops in ground controls",
        {"all_ratios": ratios},
    )


def check_design_balance(frame: pd.DataFrame) -> CheckResult:
    """Report the flight/ground sample counts per crop and mission.

    Informational rather than pass/fail on balance itself -- the real studies are
    unbalanced (lettuce is 11 flight vs 13 ground) and that is a fact to model,
    not an error to fix. It fails only if a crop is missing one arm entirely,
    which would make a flight-versus-ground contrast impossible.
    """
    counts = (
        frame.groupby(["crop", "mission", "condition"])
        .size().unstack(fill_value=0)
    )
    per_crop = frame.groupby(["crop", "condition"]).size().unstack(fill_value=0)

    missing = [
        crop for crop in per_crop.index
        if per_crop.loc[crop].get("Flight", 0) == 0
        or per_crop.loc[crop].get("Ground", 0) == 0
    ]
    if missing:
        return CheckResult(
            "design_balance", False,
            f"crop(s) missing a flight or ground arm: {missing}",
            {"per_crop": per_crop.to_dict()},
        )

    detail = "; ".join(
        f"{crop}: {row.get('Flight', 0)} flight / {row.get('Ground', 0)} ground"
        for crop, row in per_crop.iterrows()
    )
    # `counts` is indexed by (crop, mission), which json cannot serialise as a key,
    # so flatten the MultiIndex to "crop/mission" strings before returning.
    per_mission = {
        f"{crop}/{mission}": {str(k): int(v) for k, v in row.items()}
        for (crop, mission), row in counts.iterrows()
    }
    return CheckResult(
        "design_balance", True, detail,
        {"per_crop": per_crop.to_dict(), "per_mission": per_mission},
    )


def check_missingness(frame: pd.DataFrame, *, max_missing_fraction: float = 0.2) -> CheckResult:
    """Fail if any element is missing in more than *max_missing_fraction* of samples."""
    elements = [c for c in frame.columns if c in ELEMENT_SYMBOLS]
    fractions = {
        element: float(frame[element].isna().mean()) for element in elements
    }
    offenders = {
        el: round(frac, 3) for el, frac in fractions.items()
        if frac > max_missing_fraction
    }
    # Elements measured by only one study are expected to be ~50% missing in the
    # pooled table; report them separately rather than failing the build.
    single_study = {
        el for el in elements
        if frame.groupby("crop")[el].count().gt(0).sum() < 2
    }
    real_offenders = {el: v for el, v in offenders.items() if el not in single_study}

    if real_offenders:
        return CheckResult(
            "missingness", False,
            f"element(s) missing in >{max_missing_fraction:.0%} of samples "
            f"within a study: {real_offenders}",
            {"fractions": fractions},
        )
    return CheckResult(
        "missingness", True,
        f"missingness acceptable; {len(single_study)} element(s) measured by one "
        f"study only ({', '.join(sorted(single_study)) or 'none'})",
        {"fractions": fractions, "single_study_elements": sorted(single_study)},
    )


def run_all(frame: pd.DataFrame) -> tuple[bool, list[dict]]:
    """Run every QC check. Returns ``(all_passed, [result dicts])``."""
    checks = [
        check_physical_plausibility(frame),
        check_cross_study_agreement(frame),
        check_design_balance(frame),
        check_missingness(frame),
    ]
    for result in checks:
        level = logging.INFO if result.passed else logging.ERROR
        logger.log(level, "[%s] %s: %s",
                   "PASS" if result.passed else "FAIL", result.name, result.detail)
    return all(c.passed for c in checks), [asdict(c) for c in checks]
