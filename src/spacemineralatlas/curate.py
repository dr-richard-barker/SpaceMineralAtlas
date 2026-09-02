"""Assemble the harmonised plant elemental table from the raw OSDR downloads.

The two plant studies encode their experimental design entirely inside the
``Sample Name`` string, using different conventions:

* OSD-745 (lettuce)  ``VEG-01A_A_Flight_33days``
                      mission, pillow, condition, harvest day
* OSD-655 (Tokyo Bekana)  ``VEG04A_F_leaf_pillow3_red``
                      mission, condition, tissue, pillow, light spectrum

Parsing these into explicit columns is what allows the two studies to be analysed
together, and it recovers two design factors the sample names carry but no other
file states: the per-pillow identifier (which joins the elemental data to the
water-delivery and harvest-mass supplements) and, for OSD-655, the red/blue light
treatment.
"""

from __future__ import annotations

import logging
import re

import pandas as pd

from . import osdr_client
from .harmonise import ELEMENT_SYMBOLS, harmonisation_report, to_micrograms_per_gram

logger = logging.getLogger(__name__)

# Species and cultivar for each study, recorded here rather than inferred so the
# published table is unambiguous. Note that OSD-655's crop is 'Tokyo Bekana', a
# Chinese-cabbage type of Brassica rapa; it is frequently but incorrectly called
# "mizuna", which is a different B. rapa cultivar group.
CROP_METADATA: dict[str, dict[str, str]] = {
    "OSD-745": {
        "crop": "lettuce",
        "species": "Lactuca sativa",
        "cultivar": "Outredgeous",
        "reference": "Khodadad et al. 2020",
    },
    "OSD-655": {
        "crop": "tokyo_bekana",
        "species": "Brassica rapa",
        "cultivar": "Tokyo Bekana",
        "reference": "Bunchek et al. 2024",
    },
}


def parse_sample_name_745(name: str) -> dict:
    """Parse an OSD-745 sample name, e.g. ``VEG-01A_A_Flight_33days``."""
    match = re.match(
        r"^(?P<mission>VEG-\w+)_(?P<pillow>\w+)_(?P<condition>Flight|Ground)_"
        r"(?P<harvest_day>\d+)days$",
        name.strip(), flags=re.IGNORECASE,
    )
    if not match:
        return {}
    parts = match.groupdict()
    return {
        "mission": parts["mission"].upper(),
        "pillow": parts["pillow"].upper(),
        "condition": parts["condition"].capitalize(),
        "harvest_day": int(parts["harvest_day"]),
        "tissue": "leaf",         # OSD-745 assayed edible leaf tissue only
        "light_spectrum": None,   # not a factor in VEG-01/VEG-03
    }


def parse_sample_name_655(name: str) -> dict:
    """Parse an OSD-655 sample name, e.g. ``VEG04A_F_leaf_pillow3_red``.

    ``F`` denotes flight and ``GC`` ground control. The trailing token is the
    light treatment the pillow received (red- or blue-dominant LED spectrum).
    """
    match = re.match(
        r"^(?P<mission>VEG\d+\w*)_(?P<condition>F|GC)_(?P<tissue>\w+)_"
        r"pillow(?P<pillow>\d+)_(?P<light>\w+)$",
        name.strip(), flags=re.IGNORECASE,
    )
    if not match:
        return {}
    parts = match.groupdict()
    mission = parts["mission"].upper()
    # Normalise VEG04A -> VEG-04A so both studies share one mission vocabulary.
    mission = re.sub(r"^VEG0?(\d+)", r"VEG-0\1", mission)
    return {
        "mission": mission,
        "pillow": parts["pillow"],
        "condition": "Flight" if parts["condition"].upper() == "F" else "Ground",
        "harvest_day": None,      # not encoded in the OSD-655 sample names
        "tissue": parts["tissue"].lower(),
        "light_spectrum": parts["light"].lower(),
    }


def load_plant_elemental(*, force: bool = False) -> tuple[pd.DataFrame, list[dict]]:
    """Download, harmonise and merge the OSD-745 and OSD-655 elemental tables.

    Returns the combined long-form table (one row per sample, one column per
    element in ug/g dry weight) and the unit-conversion provenance log.
    """
    frames: list[pd.DataFrame] = []
    provenance: list[dict] = []

    sources = [
        ("OSD-745",
         ("ICPOESpectroscopy", "Khodadad2020", "TRANSFORMED"),
         parse_sample_name_745),
        ("OSD-655",
         ("ICPOES", "Bunchek2024", "TRANSFORMED"),
         parse_sample_name_655),
    ]

    for osd_id, fragments, parser in sources:
        filename = osdr_client.find_file(osd_id, *fragments, force=force)
        logger.info("%s: reading %s", osd_id, filename)
        raw = osdr_client.read_csv(osd_id, filename, force=force)

        # Drop OSDR's trailing padding rows, which carry no sample name.
        raw = raw[raw["Sample Name"].notna() & (raw["Sample Name"].str.strip() != "")]

        elements, study_provenance = to_micrograms_per_gram(raw, osd_id)
        provenance.extend(study_provenance)

        design = pd.DataFrame(
            [parser(name) for name in raw["Sample Name"]], index=raw.index
        )
        unparsed = design["mission"].isna().sum() if "mission" in design else len(design)
        if unparsed:
            raise ValueError(
                f"{osd_id}: {unparsed} sample name(s) did not match the expected "
                f"convention; refusing to guess. Examples: "
                f"{raw['Sample Name'][design.get('mission', pd.Series(dtype=object)).isna()].head(3).tolist()}"
            )

        meta = CROP_METADATA[osd_id]
        frame = pd.concat([design, elements], axis=1)
        frame.insert(0, "sample_name", raw["Sample Name"].values)
        frame.insert(0, "osd_id", osd_id)
        for key, value in meta.items():
            frame[key] = value

        frames.append(frame)
        logger.info("%s: %d samples, %d elements", osd_id, len(frame), len(elements.columns))

    combined = pd.concat(frames, ignore_index=True, sort=False)

    # Order columns: identifiers, design factors, then elements alphabetically.
    identifier_cols = [
        "osd_id", "sample_name", "crop", "species", "cultivar", "reference",
        "mission", "condition", "pillow", "tissue", "light_spectrum", "harvest_day",
    ]
    element_cols = sorted(c for c in combined.columns if c in ELEMENT_SYMBOLS)
    combined = combined[identifier_cols + element_cols]

    logger.info("\n%s", harmonisation_report(provenance))
    return combined, provenance
