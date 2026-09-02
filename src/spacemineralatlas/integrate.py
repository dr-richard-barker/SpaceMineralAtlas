"""Bridge the plant and astronaut sides: what a Veggie harvest actually delivers.

The defensible question
-----------------------
The plant data (OSD-745, OSD-655) and the astronaut data (OSD-575) come from
different missions and different people. Nothing in them supports a causal claim
that eating Veggie produce changed anyone's serum chemistry, and this module does
not attempt one. What the two sides *can* jointly answer is a supply question:

    Given the mineral concentrations actually measured in spaceflight-grown
    lettuce and Tokyo Bekana, how much of a crew member's daily mineral
    requirement does a realistic serving deliver?

That is a straightforward calculation from measured concentrations, a serving
mass, and a published requirement -- and it is what determines whether the
hyperaccumulation concern that motivated this project is quantitatively plausible.

Requirement values
------------------
Daily intake requirements are taken verbatim from NASA JSC-67378 Rev 1,
"Nutritional Requirements for Exploration Missions up to 365 days" (20 April
2020), which specifies requirements for a 70-kg crew member. Values are NOT
taken from terrestrial DRI tables, which differ: NASA caps iron at 8 mg/d
specifically because of spaceflight-induced increases in iron stores, whereas
terrestrial guidance for men is also 8 mg/d but for premenopausal women is 18.

Serving mass
------------
Veggie harvests are small. The VEG-04A per-pillow biomass recorded in OSD-655
averages roughly 45 g fresh across the pillows that produced a harvest, and a
crew serving is assembled from several pillows. :data:`SERVING_MASSES_G` spans a
range from a garnish to an implausibly generous salad so that the conclusion can
be read off at any assumption rather than resting on one chosen number.
"""

from __future__ import annotations

import logging

import pandas as pd

from .harmonise import DIETARY_ELEMENTS
from .supply import DRY_MATTER_FRACTION_RANGE

logger = logging.getLogger(__name__)

# --- NASA JSC-67378 Rev 1 (20 April 2020), daily requirements for a 70-kg crew
# member. Transcribed from the source document's nutrient requirements table.
# Where the standard gives a range, both bounds are recorded; where it gives
# sex-specific values, both are recorded. "upper" is a stated not-to-exceed
# limit, not a target.
JSC_67378_REQUIREMENTS: dict[str, dict] = {
    "calcium":    {"min_mg": 1000.0, "max_mg": 1200.0,
                   "note": "1,000-1,200 mg/d for men and women"},
    "phosphorus": {"min_mg": 700.0, "max_mg": None,
                   "note": "700 mg/d, and <= 1.5 x calcium intake"},
    "magnesium":  {"female_mg": 320.0, "male_mg": 420.0,
                   "note": "Women 320 mg/d, Men 420 mg/d"},
    "sodium":     {"min_mg": 1500.0, "max_mg": 2300.0,
                   "note": "1,500-2,300 mg/d"},
    "potassium":  {"female_mg": 2600.0, "male_mg": 3400.0,
                   "note": "Women 2,600 mg/d, Men 3,400 mg/d"},
    "iron":       {"min_mg": 8.0, "upper_mg": 8.0,
                   "note": "shall not exceed 8 mg/d; 18 mg/d for women under 50 "
                           "who do not pharmacologically suppress menstruation"},
    "copper":     {"min_mg": 0.9, "note": "900 ug/d"},
    "manganese":  {"female_mg": 1.8, "male_mg": 2.3,
                   "note": "Women 1.8 mg/d, Men 2.3 mg/d"},
    "zinc":       {"female_mg": 8.0, "male_mg": 11.0, "upper_mg": 40.0,
                   "note": "Women 8 mg/d, Men 11 mg/d; should not exceed 40 mg/d"},
}

REQUIREMENT_CITATION = (
    "NASA JSC-67378 Rev 1, Nutritional Requirements for Exploration Missions "
    "up to 365 days, 20 April 2020"
)

# Fresh-mass servings, in grams, spanning garnish to a generous salad. The upper
# end deliberately exceeds what a single VEG-04A pillow produced (~45 g fresh),
# so the "even at an implausible serving" case is covered.
SERVING_MASSES_G: tuple[float, ...] = (25.0, 50.0, 100.0, 200.0)


def requirement_mg(element: str, *, sex: str = "male") -> float | None:
    """Return the daily requirement in mg for *element*, or None if unspecified.

    For elements given as a range, the lower bound (the target to be met) is
    returned; for sex-specific elements, the value for *sex*.
    """
    entry = JSC_67378_REQUIREMENTS.get(element)
    if entry is None:
        return None
    if "male_mg" in entry:
        return entry["male_mg"] if sex == "male" else entry["female_mg"]
    return entry.get("min_mg")


def serving_contribution(
    elemental: pd.DataFrame, *, sex: str = "male"
) -> pd.DataFrame:
    """Mineral delivered per serving, and the fraction of requirement it covers.

    One row per (crop, condition, element, serving mass, dry-matter assumption).
    Concentrations are per gram DRY weight, so a fresh serving is converted using
    the dry-matter fraction range -- the same missing-variable caveat that applies
    in ``supply.py`` applies here, and is why both bounds are reported.
    """
    records = []
    low, high = DRY_MATTER_FRACTION_RANGE

    for (crop, condition), group in elemental.groupby(["crop", "condition"]):
        for element in DIETARY_ELEMENTS:
            if element not in group.columns:
                continue
            concentration = pd.to_numeric(group[element], errors="coerce").dropna()
            if concentration.empty:
                continue
            mean_ug_per_g_dw = float(concentration.mean())
            requirement = requirement_mg(element, sex=sex)

            for serving_g in SERVING_MASSES_G:
                for label, dry_fraction in (("low", low), ("high", high)):
                    # ug/g DW * g fresh * (g DW / g fresh) / 1000 -> mg
                    delivered_mg = mean_ug_per_g_dw * serving_g * dry_fraction / 1000.0
                    records.append({
                        "crop": crop,
                        "condition": condition,
                        "element": element,
                        "serving_fresh_g": serving_g,
                        "dry_matter_assumption": label,
                        "dry_matter_fraction": dry_fraction,
                        "mean_concentration_ug_per_g_dw": mean_ug_per_g_dw,
                        "delivered_mg": delivered_mg,
                        "requirement_mg": requirement,
                        "percent_of_requirement": (
                            100.0 * delivered_mg / requirement if requirement else None
                        ),
                    })

    return pd.DataFrame(records)


def overload_assessment(contributions: pd.DataFrame) -> pd.DataFrame:
    """Assess whether any element could approach an upper intake limit.

    This is the direct test of the hyperaccumulation concern: for the elements
    where NASA states a not-to-exceed value (iron, zinc), how large a serving of
    spaceflight-grown tissue would be needed to reach it?
    """
    records = []
    for element, entry in JSC_67378_REQUIREMENTS.items():
        upper = entry.get("upper_mg")
        if upper is None:
            continue
        subset = contributions[contributions["element"] == element]
        for (crop, condition, assumption), group in subset.groupby(
            ["crop", "condition", "dry_matter_assumption"]
        ):
            # mg delivered scales linearly with serving mass, so one row is
            # enough to derive the serving that would reach the upper limit.
            reference = group.iloc[0]
            mg_per_g_fresh = reference["delivered_mg"] / reference["serving_fresh_g"]
            records.append({
                "element": element,
                "crop": crop,
                "condition": condition,
                "dry_matter_assumption": assumption,
                "upper_limit_mg": upper,
                "mg_per_gram_fresh": mg_per_g_fresh,
                "grams_fresh_to_reach_upper_limit": (
                    upper / mg_per_g_fresh if mg_per_g_fresh else None
                ),
                "kilograms_fresh_to_reach_upper_limit": (
                    upper / mg_per_g_fresh / 1000.0 if mg_per_g_fresh else None
                ),
            })
    return pd.DataFrame(records)


def summarise(
    contributions: pd.DataFrame, overload: pd.DataFrame, *, sex: str = "male"
) -> dict:
    """Summary of the plant-to-crew supply calculation for the manuscript."""
    # A 100 g serving is the reference case reported in the text.
    reference = contributions[
        (contributions["serving_fresh_g"] == 100.0)
        & (contributions["dry_matter_assumption"] == "high")
    ]

    summary: dict = {
        "requirement_source": REQUIREMENT_CITATION,
        "sex_assumed_for_requirements": sex,
        "serving_masses_g": list(SERVING_MASSES_G),
        "dry_matter_fraction_range": list(DRY_MATTER_FRACTION_RANGE),
        "reference_case": "100 g fresh serving at 10% dry matter",
        "percent_of_requirement_per_100g": {},
        "overload_assessment": {},
        "interpretation_note": (
            "Plant and astronaut datasets derive from different missions and "
            "crews. These figures describe what a serving supplies against a "
            "published requirement; they are not evidence that Veggie produce "
            "altered any measured serum value."
        ),
    }

    for row in reference.itertuples():
        if row.percent_of_requirement is None:
            continue
        key = f"{row.crop}/{row.condition}/{row.element}"
        summary["percent_of_requirement_per_100g"][key] = round(
            float(row.percent_of_requirement), 3
        )

    for row in overload.itertuples():
        key = f"{row.element}/{row.crop}/{row.condition}/{row.dry_matter_assumption}"
        summary["overload_assessment"][key] = {
            "upper_limit_mg": float(row.upper_limit_mg),
            "kg_fresh_tissue_to_reach_limit": (
                round(float(row.kilograms_fresh_to_reach_upper_limit), 2)
                if row.kilograms_fresh_to_reach_upper_limit else None
            ),
        }

    return summary
