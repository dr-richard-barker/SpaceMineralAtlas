"""Stage 4: flight-vs-ground contrasts with compositional (dilution) correction.

Run:  python scripts_analyse_plants.py
Output: analysis/results/plant_contrasts_concentration.csv
        analysis/results/plant_contrasts_clr.csv
        analysis/results/plant_contrast_comparison.csv
        analysis/results/crop_divergence.csv
        analysis/results/plant_summary.json
"""

import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import pandas as pd

from spacemineralatlas import plant_stats
from spacemineralatlas.paths import PROCESSED, RESULTS, ensure_dirs

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-7s | %(message)s")
log = logging.getLogger("plants")


def main() -> None:
    ensure_dirs()
    frame = pd.read_csv(PROCESSED / "plant_elemental_ugg.csv")

    outputs = plant_stats.analyse(frame)
    for name, table in outputs.items():
        table.to_csv(RESULTS / f"plant_contrasts_{name}.csv", index=False)

    divergence = plant_stats.crop_divergence(outputs["comparison"])
    divergence.to_csv(RESULTS / "crop_divergence.csv", index=False)

    conc, clr = outputs["concentration"], outputs["clr"]
    comparison = outputs["comparison"]

    summary = {
        "n_samples": int(len(frame)),
        "n_by_crop": frame["crop"].value_counts().to_dict(),
        "n_by_crop_condition": {
            f"{crop}/{cond}": int(n)
            for (crop, cond), n in frame.groupby(["crop", "condition"]).size().items()
        },
        "n_significant_concentration_fdr05": int(conc["significant_fdr05"].sum()),
        "n_significant_clr_fdr05": int(clr["significant_fdr05"].sum()),
        "n_significant_both": int(comparison["significant_both"].sum()),
        "n_direction_preserved": int(comparison["direction_preserved"].sum()),
        "n_element_crop_pairs": int(len(comparison)),
        "fold_changes_concentration": {
            f"{r.group}/{r.element}": round(float(r.fold_change_conc), 4)
            for r in comparison.itertuples()
        },
        "fold_changes_clr": {
            f"{r.group}/{r.element}": round(float(r.fold_change_clr), 4)
            for r in comparison.itertuples()
        },
    }
    if "divergent_conc" in divergence:
        summary["n_divergent_elements_concentration"] = int(divergence["divergent_conc"].sum())
        summary["divergent_elements_concentration"] = divergence.loc[
            divergence["divergent_conc"], "element"
        ].tolist()
    if "divergent_clr" in divergence:
        summary["n_divergent_elements_clr"] = int(divergence["divergent_clr"].sum())
        summary["divergent_elements_clr"] = divergence.loc[
            divergence["divergent_clr"], "element"
        ].tolist()

    (RESULTS / "plant_summary.json").write_text(json.dumps(summary, indent=2))

    # Console report -- the key numbers, so a reader sees them without opening a file.
    print("\n" + "=" * 88)
    print("FLIGHT / GROUND FOLD CHANGES  --  raw concentration vs CLR (dilution-corrected)")
    print("=" * 88)
    print(f"{'crop':14s} {'element':12s} {'conc':>8s} {'q':>8s} {'':2s} "
          f"{'CLR':>8s} {'q':>8s} {'':2s} {'dir kept':>9s}")
    print("-" * 88)
    for row in comparison.sort_values(["group", "element"]).itertuples():
        star_c = "*" if row.significant_fdr05_conc else " "
        star_l = "*" if row.significant_fdr05_clr else " "
        print(f"{row.group:14s} {row.element:12s} "
              f"{row.fold_change_conc:8.3f} {row.p_adjusted_bh_conc:8.4f} {star_c:2s} "
              f"{row.fold_change_clr:8.3f} {row.p_adjusted_bh_clr:8.4f} {star_l:2s} "
              f"{str(row.direction_preserved):>9s}")
    print("-" * 88)
    print("* = FDR q < 0.05 (Benjamini-Hochberg within crop)")
    print(f"\nsignificant on concentration: {summary['n_significant_concentration_fdr05']}"
          f" | on CLR: {summary['n_significant_clr_fdr05']}"
          f" | on both: {summary['n_significant_both']}")
    if "n_divergent_elements_clr" in summary:
        print(f"elements where the two crops diverge in direction (CLR): "
              f"{summary['n_divergent_elements_clr']} -> {summary['divergent_elements_clr']}")


if __name__ == "__main__":
    main()
