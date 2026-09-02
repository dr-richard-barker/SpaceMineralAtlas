"""Stage 8: classification of flight vs ground from the plant ionome.

Two grouped cross-validation schemes are run:
  * LeaveOneMissionOut -- generalisation to an unseen growout
  * LeaveOneCropOut    -- generalisation to an unseen species

Run:  python scripts_ml.py
Output: analysis/results/ml_results.json
        analysis/results/feature_importance.csv
"""

import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import pandas as pd

from spacemineralatlas import ml
from spacemineralatlas.paths import PROCESSED, RESULTS, ensure_dirs

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-7s | %(message)s")
log = logging.getLogger("ml")


def main() -> None:
    ensure_dirs()
    frame = pd.read_csv(PROCESSED / "plant_elemental_ugg.csv")

    features = ml.usable_features(frame)
    log.info("features complete across all %d samples: %s", len(frame), features)

    results = {
        "n_samples": int(len(frame)),
        "features_used": features,
        "features_excluded": sorted(
            set(c for c in frame.columns if c in __import__(
                "spacemineralatlas.harmonise", fromlist=["ELEMENT_SYMBOLS"]
            ).ELEMENT_SYMBOLS) - set(features)
        ),
        "schemes": {},
    }

    for scheme_name, group_column in (
        ("LeaveOneMissionOut", "mission"),
        ("LeaveOneCropOut", "crop"),
    ):
        results["schemes"][scheme_name] = ml.grouped_evaluation(
            frame, features, group_column=group_column, scheme_name=scheme_name
        )

    importance = ml.feature_importance(frame, features, group_column="mission")
    importance.to_csv(RESULTS / "feature_importance.csv", index=False)
    results["permutation_importance_top5"] = (
        importance.head(5).to_dict(orient="records")
    )

    (RESULTS / "ml_results.json").write_text(json.dumps(results, indent=2))

    print("\n" + "=" * 84)
    print("FLIGHT vs GROUND CLASSIFICATION FROM THE PLANT IONOME")
    print(f"n = {results['n_samples']} samples, {len(features)} elements: "
          f"{', '.join(features)}")
    print("=" * 84)
    for scheme_name, scheme in results["schemes"].items():
        print(f"\n{scheme_name}  ({scheme['n_folds']} folds, "
              f"{scheme['class_balance']['flight']} flight / "
              f"{scheme['class_balance']['ground']} ground)")
        print(f"  {'model':22s} {'acc':>6s} {'bal.acc':>8s} {'95% CI':>16s} {'vs baseline':>12s}")
        print("  " + "-" * 72)
        for name, entry in scheme["models"].items():
            ci = entry["accuracy_ci95"]
            margin = ("       --" if entry["is_baseline"]
                      else f"{entry['margin_over_baseline']:+11.3f}")
            tag = "  (baseline)" if entry["is_baseline"] else ""
            print(f"  {name:22s} {entry['accuracy']:6.3f} "
                  f"{entry['balanced_accuracy']:8.3f} "
                  f"[{ci[0]:.2f}, {ci[1]:.2f}]{'':4s} {margin}{tag}")

    print("\nTop permutation importances (indicative only at this sample size):")
    for row in importance.head(5).itertuples():
        print(f"  {row.feature:12s} {row.importance_mean:+.4f} +/- {row.importance_std:.4f}")


if __name__ == "__main__":
    main()
