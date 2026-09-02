"""Water-delivery and harvest-mass supplements: a supply-normalised uptake proxy.

What this module can and cannot do
----------------------------------
The user-facing motivation is bioavailability: how much of the mineral supplied to
a Veggie plant actually ends up in the edible tissue. No spaceflight dataset
currently supports that calculation directly -- it would need a substrate
elemental assay or an isotope tracer, and neither exists for VEG-01, VEG-03 or
VEG-04. What OSD-655 does provide are two supplements that get partway there:

* ``OSD-655_sup_Veg-04-FlightWater.csv`` and ``...GroundControlWater.csv`` --
  daily water delivery per pillow in mL, from 0 to 35 days after initiation,
  with a per-pillow cumulative total.
* ``OSD-655_sup_VEG-04-Flight-Mass.csv`` and ``...GroundControl-Mass.csv`` --
  per-pillow harvested mass, number of plants established, and leaf counts.

Both join to the elemental data on pillow number, which the ICP-OES sample names
carry (``VEG04A_F_leaf_pillow3_red``).

Three limitations are load-bearing and are propagated into every output:

1. **VEG-04A only.** Neither supplement covers VEG-04B, so half the Tokyo Bekana
   elemental samples have no matching water or mass record.
2. **Fresh mass, dry concentration.** Harvest masses are fresh weight; ICP-OES
   concentrations are per gram *dry* weight. The dataset contains no dry-matter
   fraction, so total mineral content per plant cannot be computed exactly. This
   module therefore reports content across a range of plausible dry-matter
   fractions (:data:`DRY_MATTER_FRACTION_RANGE`) rather than asserting one value.
   This missing variable is itself a finding: it is the single cheapest
   measurement that would unlock uptake-efficiency analysis for future Veggie
   crops.
3. **Water is not nutrient.** Veggie pillows carry a fixed charge of controlled-
   release fertiliser and are irrigated with plain water, so water volume does not
   measure nutrient delivery. It measures the mass-flow driver that transports
   solubilised nutrient to the root surface. A ratio of mineral to water is
   therefore a water-use-normalised uptake index, not a bioavailability fraction,
   and is named accordingly throughout.
"""

from __future__ import annotations

import io
import logging
import re

import numpy as np
import pandas as pd

from . import osdr_client
from .harmonise import DIETARY_ELEMENTS

logger = logging.getLogger(__name__)

OSD_ID = "OSD-655"

# Typical dry-matter fraction for hydroponically grown leafy Brassica greens.
# Used only to bound the content estimate; every derived figure is reported at
# both ends of this range so the reader sees the uncertainty rather than a
# spuriously precise single number.
DRY_MATTER_FRACTION_RANGE = (0.05, 0.10)

WATER_FILES = {
    "Flight": "OSD-655_sup_Veg-04-FlightWater.csv",
    "Ground": "OSD-655_sup_VEG-04-GroundControlWater.csv",
}
MASS_FILES = {
    "Flight": "OSD-655_sup_VEG-04-Flight-Mass.csv",
    "Ground": "OSD-655_sup_VEG-04-GroundControl-Mass.csv",
}

# Both supplements describe VEG-04A. Recorded explicitly so the join cannot
# silently attach VEG-04A water volumes to VEG-04B tissue.
SUPPLEMENT_MISSION = "VEG-04A"


def _load_water(condition: str, *, force: bool = False) -> pd.DataFrame:
    """Parse one water-delivery spreadsheet into ``pillow, total_water_ml``.

    These files are Excel exports with a two-row banner, a date row, a
    days-after-initiation row and a 'Predicted' row before the per-pillow data,
    plus trailing analyst commentary columns. Rather than assume fixed offsets,
    the parser locates the header row by finding 'Pillow Total' and the data rows
    by requiring an integer pillow number in the second column.
    """
    raw = osdr_client.download(OSD_ID, WATER_FILES[condition], force=force)
    rows = list(io.StringIO(raw.decode("utf-8", "replace")))
    table = pd.read_csv(io.StringIO("".join(rows)), header=None, dtype=str)

    header_idx = next(
        (i for i in range(len(table))
         if table.iloc[i].astype(str).str.contains("Pillow Total", na=False).any()),
        None,
    )
    if header_idx is None:
        raise LookupError(f"{WATER_FILES[condition]}: no 'Pillow Total' header found")

    total_col = int(
        np.flatnonzero(
            table.iloc[header_idx].astype(str).str.contains("Pillow Total", na=False)
        )[0]
    )

    records = []
    for i in range(header_idx + 1, len(table)):
        pillow_raw = str(table.iat[i, 1]).strip()
        if not re.fullmatch(r"\d+", pillow_raw):
            continue  # skips the 'DAI' and 'Predicted' rows and any trailing notes
        total = pd.to_numeric(table.iat[i, total_col], errors="coerce")
        records.append({
            "pillow": pillow_raw,
            "condition": condition,
            "total_water_ml": float(total) if pd.notna(total) else np.nan,
        })

    frame = pd.DataFrame(records)
    logger.info("%s water (%s): %d pillows", OSD_ID, condition, len(frame))
    return frame


def _load_mass(condition: str, *, force: bool = False) -> pd.DataFrame:
    """Parse one harvest-mass spreadsheet into per-pillow fresh mass and plant counts."""
    raw = osdr_client.download(OSD_ID, MASS_FILES[condition], force=force)
    table = pd.read_csv(io.BytesIO(raw), dtype=str)

    def column(fragment: str) -> str | None:
        for name in table.columns:
            if fragment.lower() in str(name).lower():
                return name
        return None

    serial_col = column("SN")
    established_col = column("# Established")
    leaves_col = column("# Leaves, Total")

    # Biomass column choice matters and is not obvious from the header alone.
    # The two files populate different columns for the same quantity:
    #   flight  -- 'Harvested (g)' is empty for all 12 pillows; the biomass is
    #              recorded as MMD device masses plus returned samples, summed
    #              into 'Total (g)' (9 pillows populated).
    #   ground  -- 'Harvested (g)' is populated for 6 pillows, and 'Total (g)'
    #              holds the same figure plus broken leaves (e.g. pillow 6:
    #              71.4 g harvested, 82.58 g total).
    # 'Total (g)' is therefore the only column carrying comparable total edible
    # biomass in both arms. Using 'Harvested (g)' would silently discard every
    # flight pillow and leave the flight arm with no mass data at all.
    harvested_col = column("Total (g)")

    records = []
    for _, row in table.iterrows():
        serial = str(row.get(serial_col, "")).strip()
        # Serials are 'Veg04A_7' in flight and '#7' in ground control; both end
        # in the pillow number.
        match = re.search(r"(\d+)$", serial)
        if not match:
            continue
        records.append({
            "pillow": match.group(1),
            "condition": condition,
            "harvested_fresh_g": pd.to_numeric(row.get(harvested_col), errors="coerce"),  # from "Total (g)"; see note above
            "n_established": pd.to_numeric(row.get(established_col), errors="coerce"),
            "n_leaves_total": pd.to_numeric(row.get(leaves_col), errors="coerce"),
        })

    frame = pd.DataFrame(records)
    logger.info(
        "%s mass (%s): %d pillows, %d with harvest mass",
        OSD_ID, condition, len(frame), int(frame["harvested_fresh_g"].notna().sum()),
    )
    return frame


def load_supplements(*, force: bool = False) -> pd.DataFrame:
    """Combine water and mass supplements into one per-pillow table."""
    water = pd.concat([_load_water(c, force=force) for c in WATER_FILES], ignore_index=True)
    mass = pd.concat([_load_mass(c, force=force) for c in MASS_FILES], ignore_index=True)

    merged = water.merge(mass, on=["pillow", "condition"], how="outer")
    merged["mission"] = SUPPLEMENT_MISSION

    # Water-use efficiency: grams of edible fresh mass per litre delivered.
    merged["water_use_efficiency_g_per_l"] = (
        merged["harvested_fresh_g"] / (merged["total_water_ml"] / 1000.0)
    ).replace([np.inf, -np.inf], np.nan)

    return merged


def join_to_elemental(
    elemental: pd.DataFrame, supplements: pd.DataFrame
) -> pd.DataFrame:
    """Attach per-pillow water and mass records to the Tokyo Bekana elemental data.

    Only VEG-04A rows can match, since the supplements do not cover VEG-04B; the
    ``has_supplement`` flag makes the coverage explicit rather than leaving it as
    silent NaN.
    """
    tokyo = elemental[elemental["crop"] == "tokyo_bekana"].copy()
    tokyo["pillow"] = tokyo["pillow"].astype(str)

    joined = tokyo.merge(
        supplements, on=["mission", "condition", "pillow"], how="left",
        validate="many_to_one",
    )
    joined["has_supplement"] = joined["total_water_ml"].notna()

    matched = int(joined["has_supplement"].sum())
    logger.info(
        "supplement join: %d/%d Tokyo Bekana samples matched (VEG-04A only; "
        "VEG-04B has no water or mass supplement)",
        matched, len(joined),
    )
    return joined


def uptake_indices(joined: pd.DataFrame) -> pd.DataFrame:
    """Derive supply-normalised uptake indices for each dietary element.

    For every element three quantities are produced:

    ``<element>_content_mg_low`` / ``_high``
        Estimated total mineral in the harvested tissue, in mg, at the low and
        high ends of :data:`DRY_MATTER_FRACTION_RANGE`. The spread between them
        is the uncertainty introduced by the missing dry-matter measurement.
    ``<element>_per_litre_low`` / ``_high``
        The same content divided by water delivered -- a water-use-normalised
        uptake index in mg per litre.
    """
    frame = joined[joined["has_supplement"]].copy()
    low, high = DRY_MATTER_FRACTION_RANGE

    for element in DIETARY_ELEMENTS:
        if element not in frame.columns:
            continue
        # ug/g DW * g fresh * (g DW / g fresh) = ug -> /1000 = mg
        for label, fraction in (("low", low), ("high", high)):
            content_mg = (
                frame[element] * frame["harvested_fresh_g"] * fraction / 1000.0
            )
            frame[f"{element}_content_mg_{label}"] = content_mg
            frame[f"{element}_per_litre_{label}"] = (
                content_mg / (frame["total_water_ml"] / 1000.0)
            ).replace([np.inf, -np.inf], np.nan)

    return frame


def summarise(joined: pd.DataFrame, indices: pd.DataFrame) -> dict:
    """Summary of supplement coverage and the derived indices."""
    summary: dict = {
        "source": f"NASA OSDR {OSD_ID} supplementary water and harvest-mass files",
        "supplement_mission": SUPPLEMENT_MISSION,
        "n_tokyo_bekana_samples": int(len(joined)),
        "n_with_supplement": int(joined["has_supplement"].sum()),
        "n_without_supplement": int((~joined["has_supplement"]).sum()),
        "coverage_note": (
            "Water and harvest-mass supplements exist for VEG-04A only. VEG-04B "
            "elemental samples have no matching per-pillow record."
        ),
        "dry_matter_fraction_range": list(DRY_MATTER_FRACTION_RANGE),
        "dry_matter_note": (
            "OSD-655 reports harvested FRESH mass while ICP-OES reports "
            "concentration per DRY gram, and no dry-matter fraction is archived. "
            "Mineral content is therefore bounded across a plausible range rather "
            "than point-estimated. Archiving dry-matter fraction is the single "
            "cheapest addition that would make uptake efficiency computable."
        ),
        "by_condition": {},
    }

    for condition, group in joined.groupby("condition"):
        with_supp = group[group["has_supplement"]]
        entry = {
            "n_samples": int(len(group)),
            "n_with_supplement": int(len(with_supp)),
        }
        if not with_supp.empty:
            entry.update({
                "mean_total_water_ml": float(with_supp["total_water_ml"].mean()),
                "mean_harvested_fresh_g": float(with_supp["harvested_fresh_g"].mean()),
                "mean_water_use_efficiency_g_per_l": (
                    float(with_supp["water_use_efficiency_g_per_l"].mean())
                    if with_supp["water_use_efficiency_g_per_l"].notna().any() else None
                ),
            })
        summary["by_condition"][condition] = entry

    if not indices.empty:
        summary["uptake_index_mg_per_litre"] = {}
        for element in DIETARY_ELEMENTS:
            column = f"{element}_per_litre_low"
            if column not in indices.columns:
                continue
            by_condition = indices.groupby("condition")[
                [f"{element}_per_litre_low", f"{element}_per_litre_high"]
            ].mean()
            summary["uptake_index_mg_per_litre"][element] = {
                condition: {
                    "low_dry_matter": float(row[f"{element}_per_litre_low"]),
                    "high_dry_matter": float(row[f"{element}_per_litre_high"]),
                }
                for condition, row in by_condition.iterrows()
                if pd.notna(row[f"{element}_per_litre_low"])
            }

    return summary
