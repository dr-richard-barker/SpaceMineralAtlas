"""Generate manuscript/references.bib from verified DOIs.

Every entry is fetched live from Crossref rather than typed. This exists because
a hand-written bibliography is the easiest place in a manuscript for an incorrect
year, volume or author list to survive review -- and because a citation that
cannot be resolved should fail the build, not the reader.

Each DOI below was checked to resolve to the work described in its comment before
being added. Running this script re-verifies all of them.

Run:  python scripts_build_bibliography.py
"""

import logging
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent / "src"))
from spacemineralatlas.paths import MANUSCRIPT

logging.basicConfig(level=logging.INFO, format="%(levelname)-7s | %(message)s")
log = logging.getLogger("bib")

# citation key -> (DOI, what it is cited for)
REFERENCES: dict[str, tuple[str, str]] = {
    "khodadad2020": (
        "10.3389/fpls.2020.00199",
        "Source publication for OSD-745 lettuce elemental and microbiological data",
    ),
    "bunchek2024": (
        "10.1080/17429145.2023.2292220",
        "Source publication for OSD-655 Tokyo Bekana pick-and-eat crop data",
    ),
    "zheng2023": (
        "10.3389/fphys.2023.1219221",
        "Time-resolved astronaut measurements from SMO-016E / SMO-015 via LSDA",
    ),
    "overbey2024": (
        "10.1038/s41586-024-07639-y",
        "Space Omics and Medical Atlas; the Inspiration4 data resource behind OSD-575",
    ),
    "smith2005": (
        "10.1093/jn/135.3.437",
        "Altered nutritional status of astronauts after long-duration ISS flight",
    ),
    "massa2017": (
        "10.2478/gsr-2017-0002",
        "Veggie plant pillow preparation, substrate and fertiliser charge",
    ),
    "aitchison1982": (
        "10.1111/j.2517-6161.1982.tb01195.x",
        "Compositional data analysis; the basis for the centred log-ratio transform",
    ),
    "benjamini1995": (
        "10.1111/j.2517-6161.1995.tb02031.x",
        "Benjamini-Hochberg false discovery rate control",
    ),
}

# Not indexed in Crossref: NASA technical documents have no DOI. Written out
# explicitly with the exact document number, revision and date read from the
# source PDF at ntrs.nasa.gov.
MANUAL_ENTRIES = r"""
@techreport{jsc67378,
  author      = {{National Aeronautics and Space Administration}},
  title       = {Nutritional Requirements for Exploration Missions up to 365 days},
  number      = {JSC-67378 Rev 1},
  institution = {NASA Johnson Space Center},
  address     = {Houston, TX},
  year        = {2020},
  month       = {4},
  note        = {Revision 1, 20 April 2020},
  url         = {https://ntrs.nasa.gov/citations/20205008306}
}

@misc{osdr745,
  author       = {{NASA Open Science Data Repository}},
  title        = {{OSD-745}: Elemental, phenolic, anthocyanin and {ORAC} analysis of
                  {Veggie}-grown lettuce ({VEG-01A}, {VEG-01B}, {VEG-03A})},
  howpublished = {NASA Open Science Data Repository},
  year         = {2024},
  url          = {https://osdr.nasa.gov/bio/repo/data/studies/OSD-745},
  note         = {Accessed 2 September 2026}
}

@misc{osdr655,
  author       = {{NASA Open Science Data Repository}},
  title        = {{OSD-655}: Elemental and biochemical analysis of {Veggie}-grown
                  {Tokyo Bekana} ({VEG-04A}, {VEG-04B})},
  howpublished = {NASA Open Science Data Repository},
  year         = {2024},
  url          = {https://osdr.nasa.gov/bio/repo/data/studies/OSD-655},
  note         = {Accessed 2 September 2026}
}

@misc{osdr575,
  author       = {{NASA Open Science Data Repository}},
  title        = {{OSD-575}: {Inspiration4} comprehensive metabolic panel and
                  multiplex serum assays},
  howpublished = {NASA Open Science Data Repository},
  year         = {2024},
  url          = {https://osdr.nasa.gov/bio/repo/data/studies/OSD-575},
  note         = {Accessed 2 September 2026}
}

@misc{lsda,
  author       = {{NASA Life Sciences Data Archive}},
  title        = {{LSDA} Experiment Catalog},
  howpublished = {NASA Life Sciences Portal},
  year         = {2026},
  url          = {https://nlsp.nasa.gov/explore/mtable/lsda_experiment/lsda_experiment},
  note         = {2,676 experiment records harvested 2 September 2026}
}
"""


def fetch(doi: str) -> dict:
    """Retrieve a Crossref record, raising if the DOI does not resolve."""
    response = requests.get(
        f"https://api.crossref.org/works/{doi}",
        timeout=45,
        headers={"User-Agent": "SpaceMineralAtlas/0.1 (mailto:dr.richard.barker@gmail.com)"},
    )
    response.raise_for_status()
    return response.json()["message"]


def to_bibtex(key: str, record: dict, purpose: str) -> str:
    """Render a Crossref record as a BibTeX article entry."""
    authors = " and ".join(
        f"{a.get('family', '')}, {a.get('given', '')}".strip(", ")
        for a in record.get("author", [])
        if a.get("family")
    )
    dates = (record.get("published-print") or record.get("published-online")
             or record.get("issued") or {})
    year = dates.get("date-parts", [[None]])[0][0]
    title = record.get("title", [""])[0]
    journal = (record.get("container-title") or [""])[0]
    pages = record.get("page") or record.get("article-number") or ""

    # The purpose comment must not contain an "@": BibTeX scans for it
    # even inside a "%" line and would try to parse an entry there.
    entry = [f"% {purpose.replace(chr(64), 'at')}", f"@article{{{key},"]
    entry.append(f"  author  = {{{authors}}},")
    entry.append(f"  title   = {{{title}}},")
    entry.append(f"  journal = {{{journal}}},")
    if year:
        entry.append(f"  year    = {{{year}}},")
    if record.get("volume"):
        entry.append(f"  volume  = {{{record['volume']}}},")
    if record.get("issue"):
        entry.append(f"  number  = {{{record['issue']}}},")
    if pages:
        entry.append(f"  pages   = {{{pages}}},")
    entry.append(f"  doi     = {{{record['DOI']}}}")
    entry.append("}")
    return "\n".join(entry)


def main() -> int:
    blocks = [
        "% references.bib -- GENERATED by scripts_build_bibliography.py",
        "% Do not edit by hand. Every entry below was fetched from",
        "% Crossref and verified to resolve. Re-run the script to refresh.",
        "",
    ]
    failures = []

    for key, (doi, purpose) in REFERENCES.items():
        try:
            record = fetch(doi)
            blocks.append(to_bibtex(key, record, purpose))
            blocks.append("")
            log.info("verified %-14s %s -> %s",
                     key, doi, record.get("title", [""])[0][:56])
        except Exception as error:  # noqa: BLE001
            log.error("FAILED  %-14s %s: %s", key, doi, error)
            failures.append((key, doi, str(error)))
        time.sleep(0.4)  # Crossref asks for polite request rates

    blocks.append("% --- Entries with no DOI (NASA technical documents, data repositories) ---")
    blocks.append(MANUAL_ENTRIES.strip())
    blocks.append("")

    if failures:
        log.error("%d reference(s) could not be verified; refusing to write "
                  "references.bib", len(failures))
        return 1

    (MANUSCRIPT / "references.bib").write_text("\n".join(blocks))
    log.info("wrote %s with %d verified + %d manual entries",
             MANUSCRIPT / "references.bib", len(REFERENCES),
             MANUAL_ENTRIES.count("@"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
