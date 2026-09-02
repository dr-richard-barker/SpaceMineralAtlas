"""Regression tests pinning the headline results.

These lock in the numbers the manuscript reports. If a change to the pipeline
moves them, the build fails and the change must be understood before the
manuscript is rebuilt -- which is the point: the predecessor project's reported
values drifted away from its computed values precisely because nothing checked.

Tests skip (rather than fail) when the pipeline has not been run, so a fresh
clone can run the unit tests without network access.
"""

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

RESULTS = REPO / "analysis" / "results"
PROCESSED = REPO / "data" / "processed"
CATALOG = REPO / "catalog"

pytestmark = pytest.mark.skipif(
    not (RESULTS / "plant_summary.json").exists(),
    reason="pipeline outputs absent; run `make all` first",
)

TOLERANCE = 0.02  # fold changes are reported to 2 dp in the manuscript


@pytest.fixture(scope="module")
def comparison():
    return pd.read_csv(RESULTS / "plant_contrasts_comparison.csv")


def fold(frame, crop, element, kind="conc"):
    row = frame[(frame.group == crop) & (frame.element == element)]
    assert len(row) == 1, f"expected one row for {crop}/{element}, got {len(row)}"
    return float(row[f"fold_change_{kind}"].iloc[0])


@pytest.mark.parametrize(
    "crop,element,expected",
    [
        ("lettuce", "potassium", 0.99),
        ("lettuce", "calcium", 0.90),
        ("lettuce", "iron", 0.96),
        ("tokyo_bekana", "potassium", 1.54),
        ("tokyo_bekana", "calcium", 1.23),
        ("tokyo_bekana", "iron", 1.43),
        ("tokyo_bekana", "sodium", 2.15),
    ],
)
def test_raw_concentration_fold_changes(comparison, crop, element, expected):
    """Raw flight/ground ratios must match the values reported in the manuscript."""
    assert fold(comparison, crop, element) == pytest.approx(expected, abs=TOLERANCE)


@pytest.mark.parametrize(
    "element",
    ["calcium", "iron"],
)
def test_divalent_increases_do_not_survive_clr(comparison, element):
    """Ca and Fe rise on the raw scale but must lose significance after CLR.

    This is the manuscript's central analytical claim; if a pipeline change ever
    made these survive, the discussion would be wrong.
    """
    row = comparison[
        (comparison.group == "tokyo_bekana") & (comparison.element == element)
    ].iloc[0]
    assert row.fold_change_conc > 1.15, "expected an apparent increase on the raw scale"
    assert not row.significant_fdr05_clr, (
        f"{element} became significant after CLR; the discussion asserts it does not"
    )


@pytest.mark.parametrize("element", ["potassium", "sodium", "sulfur"])
def test_mobile_ions_survive_clr(comparison, element):
    """K, Na and S must remain significant in Tokyo Bekana on both scales."""
    row = comparison[
        (comparison.group == "tokyo_bekana") & (comparison.element == element)
    ].iloc[0]
    assert row.significant_fdr05_conc and row.significant_fdr05_clr


def test_lettuce_has_no_significant_elements(comparison):
    """The manuscript states lettuce shows no significant change on either scale."""
    lettuce = comparison[comparison.group == "lettuce"]
    assert not lettuce.significant_fdr05_conc.any()
    assert not lettuce.significant_fdr05_clr.any()


def test_sample_counts():
    summary = json.loads((RESULTS / "plant_summary.json").read_text())
    assert summary["n_samples"] == 60
    assert summary["n_by_crop"]["lettuce"] == 24
    assert summary["n_by_crop"]["tokyo_bekana"] == 36
    assert summary["n_by_crop_condition"]["lettuce/Flight"] == 11
    assert summary["n_by_crop_condition"]["lettuce/Ground"] == 13
    assert summary["n_by_crop_condition"]["tokyo_bekana/Flight"] == 18


def test_qc_gates_all_passed():
    qc = json.loads((RESULTS / "qc_report.json").read_text())
    assert qc["all_passed"], f"QC failed: {[c for c in qc['checks'] if not c['passed']]}"


def test_ml_does_not_beat_chance_across_crops():
    """The cross-crop failure is a reported result, not an incidental detail."""
    ml = json.loads((RESULTS / "ml_results.json").read_text())
    crop_scheme = ml["schemes"]["LeaveOneCropOut"]
    for name, entry in crop_scheme["models"].items():
        if not entry["is_baseline"]:
            assert entry["margin_over_baseline"] < 0.05, (
                f"{name} now beats baseline across crops; the manuscript says it does not"
            )


def test_lsda_catalog_is_complete():
    summary = json.loads((CATALOG / "lsda_catalog_summary.json").read_text())
    assert summary["n_experiments_total"] == 2676
    full = pd.read_csv(CATALOG / "lsda_experiments_full.csv")
    assert len(full) == 2676
    assert full["_key"].duplicated().sum() == 0, "duplicate records: pagination failed"


def test_no_element_exceeds_physical_bound():
    from spacemineralatlas.harmonise import ELEMENT_SYMBOLS, MAX_PLAUSIBLE_UG_PER_G
    frame = pd.read_csv(PROCESSED / "plant_elemental_ugg.csv")
    for element in [c for c in frame.columns if c in ELEMENT_SYMBOLS]:
        assert frame[element].max(skipna=True) <= MAX_PLAUSIBLE_UG_PER_G
