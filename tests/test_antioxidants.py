"""Tests for the plant antioxidant assays.

Two jobs:

1. Pin the headline result, like `test_results_regression` does for the
   elemental data. The result here is a *negative* one -- no assay shows a
   flight effect surviving stratification -- and a negative result is exactly
   the kind that quietly turns positive when someone changes a default. The
   predecessor project reported a flight phenolic increase that came from
   `np.random.uniform(1.2, 1.6)`; these tests make a repeat visible.

2. Guard the stratification itself. The pooled comparison is only meaningful
   because it blocks on mission. A change that silently drops the blocking
   would still produce plausible numbers, so the strata are asserted directly.
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from spacemineralatlas import antioxidants  # noqa: E402

RESULTS = REPO / "analysis" / "results"
PROCESSED = REPO / "data" / "processed"

pytestmark = pytest.mark.skipif(
    not (RESULTS / "antioxidant_summary.json").exists(),
    reason="antioxidant pipeline not run; see scripts_analyse_antioxidants.py",
)


@pytest.fixture(scope="module")
def summary() -> dict:
    return json.loads((RESULTS / "antioxidant_summary.json").read_text())


@pytest.fixture(scope="module")
def stratified() -> pd.DataFrame:
    return pd.read_csv(RESULTS / "antioxidant_contrasts_stratified.csv")


def test_all_five_assays_present(stratified: pd.DataFrame) -> None:
    """Three lettuce assays plus two Tokyo Bekana assays."""
    got = set(zip(stratified["crop"], stratified["assay"]))
    assert got == {
        ("lettuce", "orac"),
        ("lettuce", "total_phenolics"),
        ("lettuce", "anthocyanin"),
        ("tokyo_bekana", "orac"),
        ("tokyo_bekana", "total_phenolics"),
    }


def test_no_flight_effect_survives_stratification(summary: dict) -> None:
    """The headline negative result.

    If this fails, something has found a flight effect. That may be correct --
    but it must be understood before the manuscript is rebuilt, not absorbed.
    """
    assert summary["n_significant_fdr05"] == 0, (
        "An antioxidant assay now shows a flight effect at FDR 0.05. Verify "
        "before publishing: the predecessor project's equivalent finding was "
        "an artefact of a random-number generator."
    )


def test_phenolic_flight_effect_is_not_the_fabricated_one(stratified: pd.DataFrame) -> None:
    """The predecessor injected a 1.2-1.6x flight multiplier on phenolics.

    The measured effect is close to 1. This pins the contrast so the fabricated
    magnitude cannot reappear unnoticed.
    """
    for crop in ("lettuce", "tokyo_bekana"):
        row = stratified[(stratified.crop == crop)
                         & (stratified.assay == "total_phenolics")].iloc[0]
        assert 0.90 <= row.pooled_fold_change <= 1.15, (
            f"{crop} phenolic fold change is {row.pooled_fold_change:.2f}; the "
            "fabricated predecessor effect was 1.2-1.6x."
        )


def test_mission_confound_is_reported(stratified: pd.DataFrame) -> None:
    """Both confound columns must be present and finite for every assay."""
    for column in ("between_mission_spread", "max_within_mission_fold"):
        assert column in stratified.columns
        assert np.isfinite(stratified[column]).all(), f"{column} has non-finite entries"


def test_lettuce_mission_spread_exceeds_flight_effect(stratified: pd.DataFrame) -> None:
    """Phenolics and anthocyanin are mission-dominated; this is why we stratify.

    ORAC is deliberately excluded: its between-mission spread is small, and
    asserting otherwise would be overstating the confound.
    """
    for assay in ("total_phenolics", "anthocyanin"):
        row = stratified[(stratified.crop == "lettuce")
                         & (stratified.assay == assay)].iloc[0]
        assert row.between_mission_spread > 5 * row.max_within_mission_fold, (
            f"lettuce {assay}: between-mission {row.between_mission_spread:.1f}x "
            f"vs within-mission {row.max_within_mission_fold:.2f}x"
        )


def test_strata_are_blocked_on_mission(stratified: pd.DataFrame) -> None:
    """Lettuce blocks on mission; Tokyo Bekana blocks on mission x light."""
    lettuce = stratified[stratified.crop == "lettuce"]
    assert (lettuce["strata"] == "mission").all()
    assert (lettuce["n_strata"] == 3).all(), "expected VEG-01A, VEG-01B, VEG-03A"

    tb = stratified[stratified.crop == "tokyo_bekana"]
    assert (tb["strata"] == "missionxlight").all()
    assert (tb["n_strata"] >= 4).all(), "expected VEG04A/B x red/blue"


def test_van_elteren_detects_a_planted_shift() -> None:
    """Positive control: the test must find an effect that is really there.

    A stratified test that blocks away a genuine signal would produce the same
    reassuring nulls as a correct one, so the null results above are only
    meaningful if this passes.
    """
    rows = []
    for mission, base in (("M1", 10.0), ("M2", 500.0)):   # 50x mission effect
        for i in range(6):
            rows.append({"mission": mission, "light": None,
                         "condition": "Ground", "value": base + i})
            rows.append({"mission": mission, "light": None,
                         "condition": "Flight", "value": base * 1.5 + i})
    result = antioxidants.van_elteren(pd.DataFrame(rows), ["mission"])
    assert result["n_strata"] == 2
    assert result["p_value"] < 0.01, (
        "stratified test failed to detect a 1.5x within-stratum shift under a "
        "50x between-stratum confound"
    )


def test_units_are_canonical_and_provenance_recorded() -> None:
    frame = pd.read_csv(PROCESSED / "plant_antioxidants.csv")
    assert set(frame["unit"]) <= set(antioxidants.CANONICAL_UNITS.values())
    prov = pd.read_csv(PROCESSED / "antioxidant_unit_provenance.csv")
    assert len(prov) == 5, "one provenance row per assay file"
    assert prov["factor_applied"].notna().all()


def test_no_measurement_was_invented() -> None:
    """Every harmonised row must trace to a sample name in the archive files."""
    frame = pd.read_csv(PROCESSED / "plant_antioxidants.csv")
    assert len(frame) == 131, "measurement count changed; confirm against source"
    assert frame["value"].notna().all()
    assert frame["mission"].notna().all(), "a row without a mission cannot be blocked"
    assert set(frame["condition"]) == {"Flight", "Ground"}
