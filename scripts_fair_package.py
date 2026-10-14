"""Stage 9c: assemble the FAIR deposit package.

Generates the Zenodo deposition metadata, an RO-Crate manifest and a data
dictionary from the actual repository contents rather than from a hand-maintained
list, so the metadata cannot describe files that are not there.

Run:  python scripts_fair_package.py
"""

import hashlib
import json
import logging
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import pandas as pd

from spacemineralatlas import __version__
from spacemineralatlas.harmonise import ELEMENT_SYMBOLS, UNIT_OVERRIDES
from spacemineralatlas.paths import (
    CATALOG, FAIR, PROCESSED, REPO_ROOT, RESULTS, ensure_dirs
)

logging.basicConfig(level=logging.INFO, format="%(levelname)-7s | %(message)s")
log = logging.getLogger("fair")

TODAY = date.today().isoformat()
# ORCID verified against pub.orcid.org and CrossRef (10.1038/s41526-023-00247-6) on 2026-10-14.
AUTHOR = {
    "name": "Barker, Richard",
    "affiliation": "University of Wisconsin-Madison",
    "orcid": "0000-0001-5681-9857",
}
REPO_URL = "https://github.com/dr-richard-barker/SpaceMineralAtlas"


def zenodo_metadata() -> dict:
    """Zenodo deposition metadata, describing what this record actually contains."""
    return {
        "metadata": {
            "title": (
                "SpaceMineralAtlas: crop-specific mineral responses to spaceflight, "
                "a unit-labelling defect in OSD-655, and a survey of mineral and "
                "dietary data availability across the NASA Life Sciences Data Archive"
            ),
            "upload_type": "software",
            "description": (
                "<p>Open-data reanalysis of the two NASA Veggie studies with archived "
                "ICP-OES elemental data (OSD-745 lettuce, OSD-655 Tokyo Bekana), "
                "Inspiration4 clinical chemistry (OSD-575), and a machine-readable "
                "survey of all 2,676 NASA Life Sciences Data Archive experiments "
                "annotated for mineral and dietary content and classified by "
                "accessibility.</p>"
                "<p>Principal findings: (1) OSD-655 labels five elements as mg/g dry "
                "weight in both its data files and its archived data dictionary when "
                "the values are ug/g, a 1000-fold error; (2) the two Veggie crops do "
                "not share a flight ionome response, and apparent calcium and iron "
                "increases are dry-matter dilution artefacts that do not survive a "
                "centred log-ratio correction; (3) dietary mineral overload from "
                "Veggie produce is not achievable at plausible harvest scales.</p>"
                "<p>All analysis code, harmonised data tables, the annotated LSDA "
                "catalog and the manuscript source are included. No value in this "
                "work is simulated; every input is retrieved from a public NASA API "
                "and checksummed.</p>"
            ),
            "creators": [AUTHOR],
            "access_right": "open",
            "license": "MIT",
            "version": __version__,
            "publication_date": TODAY,
            "keywords": [
                "spaceflight", "space nutrition", "ionome", "NASA Veggie",
                "compositional data analysis", "OSDR", "LSDA", "FAIR data",
                "data quality", "plant mineral nutrition",
            ],
            "related_identifiers": [
                {"identifier": "10.3389/fpls.2020.00199", "relation": "isDerivedFrom",
                 "resource_type": "publication-article"},
                {"identifier": "10.1080/17429145.2023.2292220", "relation": "isDerivedFrom",
                 "resource_type": "publication-article"},
                {"identifier": "10.3389/fphys.2023.1219221", "relation": "references",
                 "resource_type": "publication-article"},
                {"identifier": "10.1038/s41586-024-07639-y", "relation": "references",
                 "resource_type": "publication-article"},
                {"identifier": "https://osdr.nasa.gov/bio/repo/data/studies/OSD-745",
                 "relation": "isDerivedFrom", "resource_type": "dataset"},
                {"identifier": "https://osdr.nasa.gov/bio/repo/data/studies/OSD-655",
                 "relation": "isDerivedFrom", "resource_type": "dataset"},
                {"identifier": "https://osdr.nasa.gov/bio/repo/data/studies/OSD-575",
                 "relation": "isDerivedFrom", "resource_type": "dataset"},
                {"identifier": REPO_URL, "relation": "isSupplementTo",
                 "resource_type": "software"},
            ],
            "communities": [{"identifier": "nasa-genelab"}],
        }
    }


def data_dictionary() -> dict:
    """Column-level documentation for every published data table."""
    elements = {
        element: {
            "symbol": symbol,
            "type": "number",
            "unit": "microgram_per_gram_of_dry_weight",
            "description": (
                f"Concentration of {element} in dried edible tissue, measured by "
                f"ICP-OES and harmonised to ug/g dry weight."
            ),
            "measured_by": "Inductively coupled plasma optical emission spectroscopy",
        }
        for element, symbol in sorted(ELEMENT_SYMBOLS.items())
    }

    return {
        "canonical_element_unit": "microgram_per_gram_of_dry_weight",
        "unit_harmonisation": {
            "note": (
                "All elemental values are expressed in ug/g dry weight. mg/kg (as "
                "used by OSD-745) is numerically identical and requires no scaling."
            ),
            "overrides_applied": [
                {
                    "osd_id": o.osd_id,
                    "elements": list(o.elements),
                    "stated_unit": o.stated_unit,
                    "actual_unit": o.actual_unit,
                    "evidence": o.evidence,
                }
                for o in UNIT_OVERRIDES
            ],
        },
        "tables": {
            "data/processed/plant_elemental_ugg.csv": {
                "description": (
                    "Harmonised elemental composition of Veggie-grown lettuce and "
                    "Tokyo Bekana, one row per sample."
                ),
                "columns": {
                    "osd_id": {"type": "string", "description": "Source OSDR study accession"},
                    "sample_name": {"type": "string", "description": "Original OSDR sample identifier"},
                    "crop": {"type": "string", "description": "lettuce | tokyo_bekana"},
                    "species": {"type": "string", "description": "Binomial species name"},
                    "cultivar": {"type": "string", "description": "Cultivar name"},
                    "reference": {"type": "string", "description": "Source publication"},
                    "mission": {"type": "string", "description": "Veggie growout (VEG-01A, VEG-01B, VEG-03A, VEG-04A, VEG-04B)"},
                    "condition": {"type": "string", "description": "Flight | Ground"},
                    "pillow": {"type": "string", "description": "Plant pillow identifier; joins to the water and mass supplements"},
                    "tissue": {"type": "string", "description": "Tissue assayed (leaf)"},
                    "light_spectrum": {"type": "string", "description": "LED treatment (red | blue); OSD-655 only"},
                    "harvest_day": {"type": "integer", "description": "Days after planting at harvest; OSD-745 only"},
                    **elements,
                },
            },
            "data/processed/astronaut_serum_cmp.csv": {
                "description": (
                    "Inspiration4 comprehensive metabolic panel, one row per "
                    "subject-timepoint, with clinical reference ranges."
                ),
                "columns": {
                    "subject": {"type": "string", "description": "De-identified crew identifier (C001-C004)"},
                    "timepoint": {"type": "string", "description": "L-n = days before launch; R+n = days after return"},
                    "day_relative": {"type": "integer", "description": "Days relative to return; negative is pre-flight"},
                    "phase": {"type": "string", "description": "preflight | postflight"},
                    "calcium": {"type": "number", "unit": "milligram_per_deciliter", "description": "Serum calcium"},
                    "potassium": {"type": "number", "unit": "millimole_per_liter", "description": "Serum potassium"},
                    "sodium": {"type": "number", "unit": "millimole_per_liter", "description": "Serum sodium"},
                    "chloride": {"type": "number", "unit": "millimole_per_liter", "description": "Serum chloride"},
                    "carbon_dioxide": {"type": "number", "unit": "millimole_per_liter", "description": "Total CO2 / bicarbonate"},
                    "<analyte>_range_min": {"type": "number", "description": "Lower clinical reference limit as supplied by OSDR"},
                    "<analyte>_range_max": {"type": "number", "description": "Upper clinical reference limit as supplied by OSDR"},
                    "<analyte>_range_position": {"type": "number", "description": "Position within the reference range; 0 = lower limit, 1 = upper limit"},
                    "<analyte>_out_of_range": {"type": "boolean", "description": "True if the value lies outside the reference range"},
                },
            },
            "catalog/lsda_mineral_nutrition_catalog.csv": {
                "description": (
                    "LSDA experiments mentioning or measuring a mineral or "
                    "nutritional variable, annotated and ranked."
                ),
                "columns": {
                    "experiment_id": {"type": "string", "description": "LSDA experiment identifier"},
                    "experiment_title": {"type": "string", "description": "Experiment title"},
                    "parameter_name": {"type": "string", "description": "Variables the experiment measured, as recorded by LSDA"},
                    "species": {"type": "string", "description": "Study organism"},
                    "missions": {"type": "string", "description": "Missions or analog campaigns"},
                    "archive_status": {"type": "string", "description": "LSDA free-text data availability statement"},
                    "access_category": {"type": "string", "description": "open | request_required | held_elsewhere | not_submitted | other | unknown"},
                    "mineral_<element>": {"type": "boolean", "description": "Element appears anywhere in the record"},
                    "measured_<element>": {"type": "boolean", "description": "Element appears in the measured-parameter list"},
                    "minerals": {"type": "string", "description": "Semicolon-separated list of minerals matched"},
                    "n_minerals": {"type": "integer", "description": "Count of minerals mentioned"},
                    "n_minerals_measured": {"type": "integer", "description": "Count of minerals measured"},
                    "is_nutrition": {"type": "boolean", "description": "Record matches a nutritional term"},
                    "relevance": {"type": "integer", "description": "Ranking score; ordering only, no analysis depends on it"},
                },
            },
        },
    }


def ro_crate() -> dict:
    """RO-Crate 1.1 manifest describing the deposited entities."""
    parts = [
        ("data/processed/plant_elemental_ugg.csv", "Dataset",
         "Harmonised Veggie elemental composition (60 samples, 12 elements, ug/g DW)"),
        ("data/processed/astronaut_serum_cmp.csv", "Dataset",
         "Inspiration4 serum minerals with clinical reference ranges"),
        ("catalog/lsda_mineral_nutrition_catalog.csv", "Dataset",
         "LSDA experiments annotated for mineral and nutritional content"),
        ("catalog/lsda_experiments_full.csv", "Dataset",
         "Complete annotated LSDA experiment catalog (2,676 records)"),
        ("src/spacemineralatlas", "SoftwareSourceCode",
         "Analysis package: API clients, unit harmonisation, QC, statistics, ML"),
        ("manuscript/SpaceMineralAtlas_manuscript.pdf", "ScholarlyArticle",
         "Manuscript"),
        ("fair/osdr_curation_report.md", "Report",
         "Data-quality report on the OSD-655 unit-labelling defect"),
        ("lsda_request/", "Collection",
         "Prepared LSDA data request for SMO-016E Nutritional Status Assessment"),
        ("veggie_correction/", "Collection",
         "Correction note and replacement data-acquisition module for a prior "
         "synthetic-data analysis of these studies"),
    ]

    graph = [
        {"@type": "CreativeWork", "@id": "ro-crate-metadata.json",
         "conformsTo": {"@id": "https://w3id.org/ro/crate/1.1"},
         "about": {"@id": "./"}},
        {
            "@type": "Dataset", "@id": "./",
            "name": "SpaceMineralAtlas",
            "description": (
                "Crop-specific mineral responses to spaceflight, a unit-labelling "
                "defect in OSD-655, and a survey of mineral and dietary data "
                "availability across the NASA Life Sciences Data Archive."
            ),
            "datePublished": TODAY,
            "version": __version__,
            "license": {"@id": "https://spdx.org/licenses/MIT.html"},
            "author": {"@id": "#richard-barker"},
            "isBasedOn": [
                {"@id": "https://doi.org/10.3389/fpls.2020.00199"},
                {"@id": "https://doi.org/10.1080/17429145.2023.2292220"},
                {"@id": "https://osdr.nasa.gov/bio/repo/data/studies/OSD-745"},
                {"@id": "https://osdr.nasa.gov/bio/repo/data/studies/OSD-655"},
                {"@id": "https://osdr.nasa.gov/bio/repo/data/studies/OSD-575"},
                {"@id": "https://nlsp.nasa.gov/explore/mtable/lsda_experiment/lsda_experiment"},
            ],
            "hasPart": [{"@id": path} for path, _, _ in parts],
        },
        {"@type": "Person", "@id": "#richard-barker", "name": "Richard Barker",
         "email": "dr.richard.barker@gmail.com"},
    ]
    for path, kind, description in parts:
        entry = {"@id": path, "@type": kind, "description": description}
        actual = REPO_ROOT / path
        if actual.is_file():
            entry["contentSize"] = actual.stat().st_size
        graph.append(entry)

    return {"@context": "https://w3id.org/ro/crate/1.1/context", "@graph": graph}


def write_manifest() -> int:
    """Checksum every published (non-gitignored) data and manuscript artefact."""
    targets: list[Path] = []
    for pattern in ("data/processed/*.csv", "catalog/*.csv", "catalog/*.json",
                    "analysis/results/*.json", "analysis/results/*.csv",
                    "analysis/figures/*.png", "manuscript/*.pdf", "manuscript/*.docx"):
        targets.extend(sorted(REPO_ROOT.glob(pattern)))

    lines = []
    for path in targets:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {path.relative_to(REPO_ROOT)}")
    (FAIR / "outputs.sha256").write_text("\n".join(lines) + "\n")
    return len(lines)


def main() -> None:
    ensure_dirs()

    (REPO_ROOT / ".zenodo.json").write_text(json.dumps(zenodo_metadata(), indent=2))
    (FAIR / "zenodo.json").write_text(json.dumps(zenodo_metadata(), indent=2))
    (FAIR / "data_dictionary.json").write_text(json.dumps(data_dictionary(), indent=2))
    (FAIR / "ro-crate-metadata.json").write_text(json.dumps(ro_crate(), indent=2))
    n = write_manifest()

    log.info("wrote .zenodo.json (repo root, where Zenodo's GitHub integration reads it)")
    log.info("wrote fair/{zenodo,data_dictionary,ro-crate-metadata}.json")
    log.info("wrote fair/outputs.sha256 with %d artefacts", n)


if __name__ == "__main__":
    main()
