"""Stage 5: supply-normalised uptake indices from the VEG-04A water and mass data.

Run:  python scripts_analyse_supply.py
Output: data/processed/veg04a_supplements.csv
        data/processed/tokyo_bekana_with_supply.csv
        analysis/results/supply_summary.json
"""

import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import pandas as pd

from spacemineralatlas import supply
from spacemineralatlas.paths import PROCESSED, RESULTS, ensure_dirs

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-7s | %(message)s")


def main() -> None:
    ensure_dirs()
    elemental = pd.read_csv(PROCESSED / "plant_elemental_ugg.csv")

    supplements = supply.load_supplements()
    supplements.to_csv(PROCESSED / "veg04a_supplements.csv", index=False)

    joined = supply.join_to_elemental(elemental, supplements)
    indices = supply.uptake_indices(joined)
    indices.to_csv(PROCESSED / "tokyo_bekana_with_supply.csv", index=False)

    summary = supply.summarise(joined, indices)
    (RESULTS / "supply_summary.json").write_text(json.dumps(summary, indent=2))

    print("\n" + "=" * 76)
    print("VEG-04A WATER DELIVERY AND HARVEST (supply proxy)")
    print("=" * 76)
    for condition, entry in summary["by_condition"].items():
        print(f"\n{condition}: {entry['n_with_supplement']}/{entry['n_samples']} "
              f"samples have a per-pillow record")
        if "mean_total_water_ml" in entry:
            print(f"  mean water delivered   : {entry['mean_total_water_ml']:.0f} mL/pillow")
            print(f"  mean harvested (fresh) : {entry['mean_harvested_fresh_g']:.1f} g/pillow")
            wue = entry.get("mean_water_use_efficiency_g_per_l")
            if wue:
                print(f"  water-use efficiency   : {wue:.1f} g fresh mass per litre")

    print("\n" + "-" * 76)
    print("Potassium uptake index (mg per litre delivered), bounded by dry-matter fraction:")
    for condition, bounds in summary.get("uptake_index_mg_per_litre", {}).get(
        "potassium", {}
    ).items():
        print(f"  {condition:8s} {bounds['low_dry_matter']:7.2f} - "
              f"{bounds['high_dry_matter']:7.2f} mg/L")
    print("-" * 76)
    print(summary["coverage_note"])


if __name__ == "__main__":
    main()
