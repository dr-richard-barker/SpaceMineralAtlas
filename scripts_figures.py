"""Stage 9a: generate every publication figure and distribute copies.

Figures are written once to analysis/figures/ then copied to manuscript/figures/
and docs/figures/ by this script -- never by hand -- so the manuscript and the
dashboard always show the figure the current code produced.

Run:  python scripts_figures.py
"""

import json
import logging
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import pandas as pd

from spacemineralatlas import figures
from spacemineralatlas.paths import (
    CATALOG, DOCS_FIGURES, FIGURES, MANUSCRIPT_FIGURES, PROCESSED, RESULTS, ensure_dirs
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-7s | %(message)s")
log = logging.getLogger("figures")


def main() -> None:
    ensure_dirs()

    elemental = pd.read_csv(PROCESSED / "plant_elemental_ugg.csv")
    comparison = pd.read_csv(RESULTS / "plant_contrasts_comparison.csv")
    serum = pd.read_csv(PROCESSED / "astronaut_serum_cmp.csv")
    contributions = pd.read_csv(RESULTS / "serving_contributions.csv")
    ml_results = json.loads((RESULTS / "ml_results.json").read_text())
    lsda_summary = json.loads((CATALOG / "lsda_catalog_summary.json").read_text())

    figures.fig_fold_change_comparison(comparison, FIGURES / "fig1_fold_change_clr.png")
    figures.fig_crop_divergence(comparison, FIGURES / "fig2_crop_divergence.png")
    figures.fig_element_profiles(elemental, FIGURES / "fig3_element_profiles.png")
    figures.fig_astronaut_trajectories(serum, FIGURES / "fig4_astronaut_serum.png")
    figures.fig_serving_contribution(contributions, FIGURES / "fig5_serving_contribution.png")
    figures.fig_ml_performance(ml_results, FIGURES / "fig6_ml_performance.png")
    figures.fig_lsda_landscape(lsda_summary, FIGURES / "fig7_lsda_landscape.png")

    for destination in (MANUSCRIPT_FIGURES, DOCS_FIGURES):
        for figure in sorted(FIGURES.glob("*.png")):
            shutil.copy2(figure, destination / figure.name)
        log.info("copied %d figures to %s",
                 len(list(FIGURES.glob('*.png'))), destination)


if __name__ == "__main__":
    main()
