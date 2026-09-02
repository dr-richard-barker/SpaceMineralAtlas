"""Bring the OSDR plant elemental datasets onto one auditable unit scale.

Why this module exists
----------------------
The two Veggie elemental datasets express concentrations in different units, and
one of them states its unit incorrectly:

* **OSD-745** (lettuce) uses column names of the form
  ``calcium_milligram_per_kilogram_of_dry_weight``. mg/kg is numerically identical
  to ug/g, so these values need no rescaling.

* **OSD-655** (Tokyo Bekana) names five of its columns
  ``*_milligram_per_gram_of_dry_weight`` -- calcium, potassium, magnesium,
  phosphorus and sulfur -- and ``OSD-655_dictionary_DataDictionary_OSD-655.csv``
  repeats ``unit: milligram_per_gram`` for each. The values are not mg/g. Read as
  mg/g, mean potassium would be 29,426 mg/g, i.e. **2,943% of dry weight**, which
  is impossible; the same reading puts calcium at 651% and magnesium at 805%.
  Read as ug/g, every value lands in the normal range for leafy Brassica tissue
  and agrees with the independently-scaled OSD-745 lettuce measurements
  (Ca 5.83 vs 4.50 mg/g; K 29.4 vs 47.9 mg/g).

Reading OSD-655 at face value therefore inflates five of its twelve elements by a
factor of 1000. Any cross-study comparison, any PCA, and any machine-learning
model trained on the concatenation would be dominated by that artefact.

Design principle
----------------
The correction is applied through :data:`UNIT_OVERRIDES`, an explicit table in
which each entry carries the evidence justifying it. Nothing is silently rescaled:
:func:`harmonisation_report` emits every override that fired, and ``qc.py``
independently re-checks the result against a physical plausibility bound. A
correction that cannot be stated and defended in the output is not a correction,
it is a hidden assumption.

This defect has been written up for submission to the OSDR curation team; see
``fair/osdr_curation_report.md``.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

import pandas as pd

logger = logging.getLogger(__name__)

# Multiplicative factor converting each named source unit to ug/g dry weight.
UNIT_TO_MICROGRAM_PER_GRAM: dict[str, float] = {
    "microgram_per_gram": 1.0,
    "milligram_per_kilogram": 1.0,   # mg/kg == ug/g exactly
    "milligram_per_gram": 1000.0,    # 1 mg/g == 1000 ug/g
    "gram_per_kilogram": 1000.0,
    "percent": 10000.0,
}

# Elements quantified by ICP-OES in these studies, with atomic symbols for display.
ELEMENT_SYMBOLS: dict[str, str] = {
    "aluminium": "Al", "boron": "B", "calcium": "Ca", "copper": "Cu",
    "iron": "Fe", "potassium": "K", "magnesium": "Mg", "manganese": "Mn",
    "sodium": "Na", "phosphorus": "P", "sulfur": "S", "zinc": "Zn",
}

# Elements that are plant nutrients AND human dietary minerals -- the subset on
# which the plant-to-astronaut comparison in integrate.py operates.
DIETARY_ELEMENTS: tuple[str, ...] = (
    "calcium", "copper", "iron", "potassium", "magnesium",
    "manganese", "sodium", "phosphorus", "zinc",
)

# Highest credible concentration for any single element in dried plant tissue,
# expressed as a fraction of dry weight. Potassium, the most abundant cation in
# leafy tissue, reaches roughly 6-8% of dry weight; 10% leaves generous headroom
# while still catching a 1000x unit error immediately.
MAX_PLAUSIBLE_FRACTION_OF_DRY_WEIGHT = 0.10
MAX_PLAUSIBLE_UG_PER_G = MAX_PLAUSIBLE_FRACTION_OF_DRY_WEIGHT * 1_000_000


@dataclass(frozen=True)
class UnitOverride:
    """A documented correction to a unit that a source dataset states incorrectly."""

    osd_id: str
    elements: tuple[str, ...]
    stated_unit: str
    actual_unit: str
    evidence: str


UNIT_OVERRIDES: tuple[UnitOverride, ...] = (
    UnitOverride(
        osd_id="OSD-655",
        elements=("calcium", "potassium", "magnesium", "phosphorus", "sulfur"),
        stated_unit="milligram_per_gram",
        actual_unit="microgram_per_gram",
        evidence=(
            "Taking the stated mg/g at face value gives mean concentrations of "
            "2943% (K), 805% (Mg), 651% (Ca), 551% (S) and 367% (P) of dry weight, "
            "which are physically impossible. Interpreted as ug/g the same values "
            "agree with OSD-745, whose lettuce elemental data are independently "
            "expressed in mg/kg: Ca 5.83 vs 4.50 mg/g, K 29.4 vs 47.9 mg/g, "
            "Mg 8.05 vs 2.60 mg/g. The three elements OSD-655 labels in ug/g "
            "(Al, B, Cu, Fe, Mn, Zn) require no correction and already agree "
            "across studies, which localises the defect to the five mg/g labels. "
            "OSD-655_dictionary_DataDictionary_OSD-655.csv repeats the incorrect "
            "unit, so the defect is in the curation metadata, not only the header."
        ),
    ),
)


def parse_column(column: str) -> tuple[str | None, str | None]:
    """Split an OSDR TRANSFORMED column name into ``(analyte, unit)``.

    OSDR names elemental columns ``<analyte>_<unit>_of_dry_weight``, e.g.
    ``calcium_milligram_per_kilogram_of_dry_weight``. Returns ``(None, None)``
    for columns that do not follow the convention (such as ``Sample Name``).
    """
    match = re.match(r"^([a-z]+)_((?:micro|milli)?gram_per_(?:gram|kilogram))", column.strip())
    if not match:
        return None, None
    return match.group(1), match.group(2)


def to_micrograms_per_gram(
    frame: pd.DataFrame, osd_id: str
) -> tuple[pd.DataFrame, list[dict]]:
    """Rescale every recognised elemental column of *frame* to ug/g dry weight.

    Returns the converted frame (columns renamed to bare element names) together
    with a per-column provenance log recording the stated unit, the unit actually
    applied, the factor used, and whether an override fired.
    """
    overrides = {
        (override.osd_id, element): override
        for override in UNIT_OVERRIDES
        for element in override.elements
    }

    converted = pd.DataFrame(index=frame.index)
    provenance: list[dict] = []

    for column in frame.columns:
        element, stated_unit = parse_column(column)
        if element is None:
            continue

        override = overrides.get((osd_id, element))
        if override is not None and stated_unit == override.stated_unit:
            applied_unit = override.actual_unit
            note = "unit override applied"
        else:
            applied_unit = stated_unit
            note = "stated unit accepted"

        factor = UNIT_TO_MICROGRAM_PER_GRAM.get(applied_unit)
        if factor is None:
            logger.warning("%s: unrecognised unit %r on %r; column skipped",
                           osd_id, applied_unit, column)
            continue

        values = pd.to_numeric(frame[column], errors="coerce")
        converted[element] = values * factor

        provenance.append({
            "osd_id": osd_id,
            "source_column": column,
            "element": element,
            "stated_unit": stated_unit,
            "applied_unit": applied_unit,
            "factor_to_ug_per_g": factor,
            "override_applied": override is not None and note == "unit override applied",
            "note": note,
            "n_values": int(values.notna().sum()),
        })

    return converted, provenance


def harmonisation_report(provenance: list[dict]) -> str:
    """Render a human-readable summary of what the unit harmonisation did."""
    lines = ["Unit harmonisation report", "=" * 60]
    for osd_id in sorted({entry["osd_id"] for entry in provenance}):
        entries = [e for e in provenance if e["osd_id"] == osd_id]
        overridden = [e for e in entries if e["override_applied"]]
        lines.append(f"\n{osd_id}: {len(entries)} elemental columns -> ug/g dry weight")
        if overridden:
            lines.append(f"  {len(overridden)} unit override(s) applied:")
            for entry in overridden:
                lines.append(
                    f"    {entry['element']:12s} "
                    f"{entry['stated_unit']} (stated) -> {entry['applied_unit']} "
                    f"(applied, x{entry['factor_to_ug_per_g']:g})"
                )
        else:
            lines.append("  no overrides required; all stated units accepted")
    lines.append("\nJustification for each override:")
    for override in UNIT_OVERRIDES:
        lines.append(f"\n  {override.osd_id} [{', '.join(override.elements)}]")
        lines.append(f"    stated: {override.stated_unit} -> applied: {override.actual_unit}")
        for chunk in _wrap(override.evidence, 74):
            lines.append(f"    {chunk}")
    return "\n".join(lines)


def _wrap(text: str, width: int) -> list[str]:
    """Minimal greedy word wrap, used so the report reads well in a terminal."""
    words, lines, current = text.split(), [], ""
    for word in words:
        if len(current) + len(word) + 1 > width:
            lines.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
    if current:
        lines.append(current)
    return lines
