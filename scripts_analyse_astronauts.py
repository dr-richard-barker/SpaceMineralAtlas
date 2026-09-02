"""Stage 6: astronaut serum mineral trajectories from the Inspiration4 CMP.

Run:  python scripts_analyse_astronauts.py
Output: data/processed/astronaut_serum_cmp.csv
        analysis/results/astronaut_changes.csv
        analysis/results/astronaut_summary.json
"""

import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from spacemineralatlas import astronaut
from spacemineralatlas.paths import PROCESSED, RESULTS, ensure_dirs

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-7s | %(message)s")
log = logging.getLogger("astronaut")


def main() -> None:
    ensure_dirs()

    frame = astronaut.load_cmp()
    frame.to_csv(PROCESSED / "astronaut_serum_cmp.csv", index=False)

    changes = astronaut.per_subject_change(frame)
    changes.to_csv(RESULTS / "astronaut_changes.csv", index=False)

    summary = astronaut.summarise(frame, changes)
    (RESULTS / "astronaut_summary.json").write_text(json.dumps(summary, indent=2))

    print("\n" + "=" * 78)
    print("INSPIRATION4 SERUM MINERALS -- change from pre-flight mean to R+1")
    print("=" * 78)
    print(f"{'mineral':16s} {'unit':22s} {'down':>5s} {'up':>4s}  {'median %change':>15s}")
    print("-" * 78)
    for mineral, entry in summary["by_mineral"].items():
        print(f"{mineral:16s} {entry['unit'][:22]:22s} "
              f"{entry['n_decreased_at_return']:5d} {entry['n_increased_at_return']:4d}  "
              f"{entry['median_percent_change']:14.2f}%")
    print("-" * 78)
    print(f"n = {summary['n_subjects']} subjects, {summary['n_timepoints']} timepoints, "
          f"{summary['inflight_samples']} in-flight samples, "
          f"{summary['mission_duration_days']}-day mission")
    print("\nPer-subject potassium (the mineral of interest):")
    k = changes[changes["mineral"] == "potassium"]
    for row in k.itertuples():
        print(f"  {row.subject}: preflight {row.preflight_mean:.2f} -> R+1 {getattr(row,'_4'):.2f} "
              f"({row.percent_change:+.1f}%)")


if __name__ == "__main__":
    main()
