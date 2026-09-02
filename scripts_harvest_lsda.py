"""Stage 1: harvest the LSDA experiment catalog and build the mineral/nutrition index.

Run:  python scripts_harvest_lsda.py
Output: catalog/lsda_experiments_full.csv        -- all 2,676 experiments, annotated
        catalog/lsda_mineral_nutrition_catalog.csv -- the filtered, ranked subset
        catalog/lsda_catalog_summary.json        -- counts used by the manuscript
"""

import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from spacemineralatlas import lsda_client as lsda
from spacemineralatlas.paths import CATALOG, ensure_dirs

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s | %(levelname)-7s | %(message)s"
)
log = logging.getLogger("harvest")


def main() -> None:
    ensure_dirs()

    records = lsda.harvest()
    log.info("harvested %d unique experiment records", len(records))

    frame = lsda.annotate(records)
    frame.to_csv(CATALOG / "lsda_experiments_full.csv", index=False)

    # The catalog of interest: anything that touches a mineral or a nutrition topic.
    relevant = frame[(frame["n_minerals"] > 0) | frame["is_nutrition"]].copy()
    relevant = relevant.sort_values("relevance", ascending=False)
    relevant.to_csv(CATALOG / "lsda_mineral_nutrition_catalog.csv", index=False)

    # The strictest tier: experiments that actually *measured* a mineral or a
    # nutritional variable, as opposed to merely mentioning one.
    measured = frame[
        (frame["n_minerals_measured"] > 0) | frame["measured_nutrition"]
    ].copy().sort_values("relevance", ascending=False)
    measured.to_csv(CATALOG / "lsda_measured_mineral_catalog.csv", index=False)

    summary = {
        "n_experiments_total": int(len(frame)),
        "n_mineral_or_nutrition": int(len(relevant)),
        "n_measured_mineral_or_nutrition": int(len(measured)),
        "by_access_category": (
            relevant["access_category"].value_counts().to_dict()
        ),
        "measured_by_access_category": (
            measured["access_category"].value_counts().to_dict()
        ),
        "by_mineral_mentioned": {
            m: int(frame[f"mineral_{m}"].sum()) for m in lsda.MINERAL_TERMS
        },
        "by_mineral_measured": {
            m: int(frame[f"measured_{m}"].sum()) for m in lsda.MINERAL_TERMS
        },
        "n_human_studies": int(
            frame["species"].str.contains("human", case=False, na=False).sum()
        ),
        "n_nutrition_mentioned": int(frame["is_nutrition"].sum()),
        "n_nutrition_measured": int(frame["measured_nutrition"].sum()),
    }
    (CATALOG / "lsda_catalog_summary.json").write_text(json.dumps(summary, indent=2))

    log.info("=" * 66)
    log.info("total experiments harvested   : %d", summary["n_experiments_total"])
    log.info("mineral or nutrition relevant : %d", summary["n_mineral_or_nutrition"])
    log.info("with measured mineral/nutrition: %d", summary["n_measured_mineral_or_nutrition"])
    log.info("access categories             : %s", summary["by_access_category"])
    log.info("=" * 66)


if __name__ == "__main__":
    main()
