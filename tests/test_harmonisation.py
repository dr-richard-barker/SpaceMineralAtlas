"""Tests for unit harmonisation and the physical-plausibility gate."""

import sys
from pathlib import Path

import pandas as pd
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from spacemineralatlas import qc
from spacemineralatlas.harmonise import (
    MAX_PLAUSIBLE_UG_PER_G, UNIT_OVERRIDES, parse_column, to_micrograms_per_gram,
)


@pytest.mark.parametrize(
    "column,expected",
    [
        ("calcium_milligram_per_kilogram_of_dry_weight", ("calcium", "milligram_per_kilogram")),
        ("potassium_milligram_per_gram_of_dry_weight", ("potassium", "milligram_per_gram")),
        ("iron_microgram_per_gram_of_dry_weight", ("iron", "microgram_per_gram")),
        ("Sample Name", (None, None)),
        ("total_phenolic_content_milligram_per_gram_of_dry_weight", (None, None)),
    ],
)
def test_parse_column(column, expected):
    assert parse_column(column) == expected


def test_mg_per_kg_is_unchanged():
    """mg/kg and ug/g are the same unit; OSD-745 must not be rescaled."""
    frame = pd.DataFrame({"calcium_milligram_per_kilogram_of_dry_weight": [4776.22]})
    converted, provenance = to_micrograms_per_gram(frame, "OSD-745")
    assert converted["calcium"].iloc[0] == pytest.approx(4776.22)
    assert provenance[0]["factor_to_ug_per_g"] == 1.0
    assert not provenance[0]["override_applied"]


def test_osd655_override_fires_and_is_recorded():
    """The mislabelled OSD-655 columns must be corrected and the change logged."""
    frame = pd.DataFrame({"potassium_milligram_per_gram_of_dry_weight": [29426.2]})
    converted, provenance = to_micrograms_per_gram(frame, "OSD-655")

    # Corrected: the value is already ug/g, so it must pass through unscaled.
    assert converted["potassium"].iloc[0] == pytest.approx(29426.2)
    entry = provenance[0]
    assert entry["override_applied"] is True
    assert entry["stated_unit"] == "milligram_per_gram"
    assert entry["applied_unit"] == "microgram_per_gram"


def test_override_does_not_leak_to_other_studies():
    """A study-specific override must not apply to a different study."""
    frame = pd.DataFrame({"potassium_milligram_per_gram_of_dry_weight": [1.0]})
    converted, _ = to_micrograms_per_gram(frame, "OSD-999")
    # No override for OSD-999, so the stated mg/g is honoured: 1 mg/g = 1000 ug/g.
    assert converted["potassium"].iloc[0] == pytest.approx(1000.0)


def test_every_override_carries_evidence():
    for override in UNIT_OVERRIDES:
        assert len(override.evidence) > 100, (
            f"{override.osd_id} override lacks a substantive justification"
        )


def test_plausibility_gate_catches_a_thousandfold_error():
    """The uncorrected OSD-655 potassium value must fail the gate."""
    bad = pd.DataFrame({
        "crop": ["tokyo_bekana"] * 3,
        "condition": ["Flight", "Ground", "Flight"],
        # 29426.2 mg/g misread as ug/g-equivalent -> 29.4 million ug/g
        "potassium": [29426.2 * 1000] * 3,
    })
    result = qc.check_physical_plausibility(bad)
    assert not result.passed
    assert "potassium" in result.data


def test_plausibility_gate_passes_real_values():
    good = pd.DataFrame({
        "crop": ["lettuce"] * 3,
        "condition": ["Flight", "Ground", "Flight"],
        "potassium": [47334.6, 47951.2, 62425.7],
        "calcium": [4032.0, 4501.2, 4776.2],
    })
    assert qc.check_physical_plausibility(good).passed
    assert MAX_PLAUSIBLE_UG_PER_G == 100_000
