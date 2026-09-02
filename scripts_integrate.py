"""Stage 7: what a Veggie serving delivers against NASA crew mineral requirements.

Run:  python scripts_integrate.py
Output: analysis/results/serving_contributions.csv
        analysis/results/overload_assessment.csv
        analysis/results/integration_summary.json
"""

import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import pandas as pd

from spacemineralatlas import integrate
from spacemineralatlas.paths import PROCESSED, RESULTS, ensure_dirs

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-7s | %(message)s")


def main() -> None:
    ensure_dirs()
    elemental = pd.read_csv(PROCESSED / "plant_elemental_ugg.csv")

    contributions = integrate.serving_contribution(elemental)
    contributions.to_csv(RESULTS / "serving_contributions.csv", index=False)

    overload = integrate.overload_assessment(contributions)
    overload.to_csv(RESULTS / "overload_assessment.csv", index=False)

    summary = integrate.summarise(contributions, overload)
    (RESULTS / "integration_summary.json").write_text(json.dumps(summary, indent=2))

    print("\n" + "=" * 84)
    print("MINERAL DELIVERED BY A 100 g FRESH SERVING (10% dry matter)")
    print("as a percentage of the NASA daily requirement, JSC-67378 Rev 1")
    print("=" * 84)
    ref = contributions[
        (contributions.serving_fresh_g == 100.0)
        & (contributions.dry_matter_assumption == "high")
        & (contributions.condition == "Flight")
    ]
    print(f"{'element':12s} {'req mg/d':>9s} "
          f"{'lettuce mg':>11s} {'%req':>7s}   {'tokyo mg':>9s} {'%req':>7s}")
    print("-" * 84)
    for element in sorted(ref["element"].unique()):
        rows = ref[ref.element == element]
        lettuce = rows[rows.crop == "lettuce"]
        tokyo = rows[rows.crop == "tokyo_bekana"]
        req = rows["requirement_mg"].dropna()
        req_s = f"{req.iloc[0]:9.1f}" if not req.empty else "        -"
        lm = f"{lettuce.delivered_mg.iloc[0]:11.2f}" if not lettuce.empty else "          -"
        lp = (f"{lettuce.percent_of_requirement.iloc[0]:6.1f}%"
              if not lettuce.empty and pd.notna(lettuce.percent_of_requirement.iloc[0]) else "      -")
        tm = f"{tokyo.delivered_mg.iloc[0]:9.2f}" if not tokyo.empty else "        -"
        tp = (f"{tokyo.percent_of_requirement.iloc[0]:6.1f}%"
              if not tokyo.empty and pd.notna(tokyo.percent_of_requirement.iloc[0]) else "      -")
        print(f"{element:12s} {req_s} {lm} {lp}   {tm} {tp}")

    print("\n" + "=" * 84)
    print("HYPERACCUMULATION / OVERLOAD TEST")
    print("How much fresh spaceflight-grown tissue would reach NASA's upper limit?")
    print("=" * 84)
    for row in overload[
        (overload.condition == "Flight") & (overload.dry_matter_assumption == "high")
    ].itertuples():
        print(f"  {row.element:10s} {row.crop:14s} limit {row.upper_limit_mg:5.1f} mg/d "
              f"-> {row.kilograms_fresh_to_reach_upper_limit:8.2f} kg fresh tissue per day")


if __name__ == "__main__":
    main()
