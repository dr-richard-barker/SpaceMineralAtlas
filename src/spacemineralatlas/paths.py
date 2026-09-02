"""Single source of truth for every path this project reads or writes.

Centralising paths here means a script can be run from any working directory and
still resolve the repository layout correctly -- and it means there is exactly one
place to look when auditing what the pipeline touches.
"""

from pathlib import Path

# paths.py lives at <repo>/src/spacemineralatlas/paths.py, so the repository root
# is three parents up.
REPO_ROOT = Path(__file__).resolve().parents[2]

DATA = REPO_ROOT / "data"
RAW = DATA / "raw"            # cached API downloads, byte-identical to source (gitignored)
INTERIM = DATA / "interim"    # intermediate artefacts (gitignored)
PROCESSED = DATA / "processed"  # small, tracked, publication-ready tables

CATALOG = REPO_ROOT / "catalog"
ANALYSIS = REPO_ROOT / "analysis"
RESULTS = ANALYSIS / "results"
FIGURES = ANALYSIS / "figures"

MANUSCRIPT = REPO_ROOT / "manuscript"
MANUSCRIPT_FIGURES = MANUSCRIPT / "figures"
DOCS = REPO_ROOT / "docs"
DOCS_DATA = DOCS / "data"
DOCS_FIGURES = DOCS / "figures"
FAIR = REPO_ROOT / "fair"

CHECKSUM_FILE = FAIR / "checksums.sha256"


def ensure_dirs() -> None:
    """Create every output directory the pipeline writes to.

    Safe to call repeatedly; existing directories are left untouched.
    """
    for directory in (
        RAW, INTERIM, PROCESSED, CATALOG, RESULTS, FIGURES,
        MANUSCRIPT_FIGURES, DOCS_DATA, DOCS_FIGURES, FAIR,
    ):
        directory.mkdir(parents=True, exist_ok=True)
