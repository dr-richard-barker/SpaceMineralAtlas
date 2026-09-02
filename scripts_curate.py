"""Stage 2-3: download the real OSDR plant data, harmonise units, run QC gates.

Run:  python scripts_curate.py
Output: data/processed/plant_elemental_ugg.csv  -- the analysis-ready table
        data/processed/unit_provenance.csv      -- per-column conversion audit trail
        analysis/results/qc_report.json         -- QC outcomes
        fair/harmonisation_report.txt           -- human-readable unit report
"""

import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import pandas as pd

from spacemineralatlas import qc
from spacemineralatlas.curate import load_plant_elemental
from spacemineralatlas.harmonise import harmonisation_report
from spacemineralatlas.paths import FAIR, PROCESSED, RESULTS, ensure_dirs

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s | %(levelname)-7s | %(message)s"
)
log = logging.getLogger("curate")


def main() -> int:
    ensure_dirs()

    frame, provenance = load_plant_elemental()
    frame.to_csv(PROCESSED / "plant_elemental_ugg.csv", index=False)
    pd.DataFrame(provenance).to_csv(PROCESSED / "unit_provenance.csv", index=False)
    (FAIR / "harmonisation_report.txt").write_text(harmonisation_report(provenance))

    log.info("curated table: %d samples x %d columns", *frame.shape)

    passed, results = qc.run_all(frame)
    (RESULTS / "qc_report.json").write_text(json.dumps(
        {"all_passed": passed, "checks": results}, indent=2, default=str
    ))

    if not passed:
        log.error("QC FAILED -- refusing to emit an analysis-ready table.")
        return 1

    log.info("all QC gates passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
