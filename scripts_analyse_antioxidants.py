"""Stage 4b: flight-vs-ground contrasts for the plant antioxidant assays.

These assays (ORAC, total phenolics, anthocyanin) were present in each study's
file manifest but never downloaded until 13 Oct 2026. Every antioxidant number
previously published for these studies came from a random generator, not the
archive -- see veggie_correction/CORRECTION_NOTE.md.

Mission dominates the variance in these assays by roughly an order of magnitude,
so the pooled inference is a stratified (van Elteren) test, never a naive
flight-vs-ground comparison. See spacemineralatlas.antioxidants for why.

Run:  ./.venv/bin/python scripts_analyse_antioxidants.py
Output: data/processed/plant_antioxidants.csv
        data/processed/antioxidant_unit_provenance.csv
        analysis/results/antioxidant_contrasts_by_mission.csv
        analysis/results/antioxidant_contrasts_stratified.csv
        analysis/results/antioxidant_summary.json
"""

import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import pandas as pd

from spacemineralatlas import antioxidants
from spacemineralatlas.paths import PROCESSED, RAW, RESULTS, ensure_dirs

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-7s | %(message)s")
log = logging.getLogger("antioxidants")


def main() -> None:
    ensure_dirs()

    frame, provenance = antioxidants.load(RAW)
    frame.to_csv(PROCESSED / "plant_antioxidants.csv", index=False)
    pd.DataFrame(provenance).to_csv(
        PROCESSED / "antioxidant_unit_provenance.csv", index=False
    )
    log.info("harmonised %d measurements across %d assays",
             len(frame), frame["assay"].nunique())

    missionwise, stratified = antioxidants.analyse(frame)
    missionwise.to_csv(RESULTS / "antioxidant_contrasts_by_mission.csv", index=False)
    stratified.to_csv(RESULTS / "antioxidant_contrasts_stratified.csv", index=False)

    summary = {
        "provenance": {
            "note": (
                "Antioxidant assay files were listed in each study's "
                "_file_manifest.json but never downloaded before 13 Oct 2026. "
                "Fetched by veggie_correction/fetch_antioxidant_data.py; "
                "checksums in fair/antioxidant_inputs.sha256."
            ),
            "studies": sorted(frame["study"].unique().tolist()),
            "assays": sorted(frame["assay"].unique().tolist()),
        },
        "n_measurements": int(len(frame)),
        "n_by_crop_assay": {
            f"{crop}/{assay}": int(n)
            for (crop, assay), n in frame.groupby(["crop", "assay"]).size().items()
        },
        "n_by_crop_assay_condition": {
            f"{crop}/{assay}/{cond}": int(n)
            for (crop, assay, cond), n
            in frame.groupby(["crop", "assay", "condition"]).size().items()
        },
        "stratified": {
            f"{row.crop}/{row.assay}": {
                "unit": row.unit,
                "strata": row.strata,
                "n_strata": int(row.n_strata),
                "n_flight": int(row.n_flight),
                "n_ground": int(row.n_ground),
                "median_flight": round(float(row.median_flight), 3),
                "median_ground": round(float(row.median_ground), 3),
                "pooled_fold_change": round(float(row.pooled_fold_change), 3),
                "van_elteren_z": round(float(row.van_elteren_z), 3),
                "p_value": float(row.p_value),
                "p_value_fdr": float(row.p_value_fdr),
                "significant_fdr05": bool(row.significant_fdr05),
                "between_mission_spread": round(float(row.between_mission_spread), 2),
                "max_within_mission_fold": round(float(row.max_within_mission_fold), 2),
            }
            for row in stratified.itertuples()
        },
        "by_mission": {
            f"{row.crop}/{row.assay}/{row.mission}" + (f"/{row.light}" if row.light else ""): {
                "n_flight": int(row.n_flight),
                "n_ground": int(row.n_ground),
                "fold_change": round(float(row.fold_change), 3),
                "p_value": float(row.p_value),
            }
            for row in missionwise.itertuples()
        },
        "finding": (
            "No antioxidant assay in either crop shows a flight effect that "
            "survives stratification on mission at FDR 0.05. Between-mission "
            "variation (between_mission_spread) exceeds the within-mission flight "
            "effect (max_within_mission_fold) by up to an order of magnitude, "
            "which is why the pooled comparison is stratified, not naive."
        ),
    }

    n_sig = int(stratified["significant_fdr05"].sum())
    summary["n_significant_fdr05"] = n_sig
    if n_sig:
        summary["finding"] = (
            f"{n_sig} of {len(stratified)} antioxidant assays show a flight "
            "effect surviving stratification on mission at FDR 0.05; see "
            "antioxidant_contrasts_stratified.csv."
        )

    (RESULTS / "antioxidant_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n"
    )

    log.info("stratified results:")
    for row in stratified.itertuples():
        log.info(
            "  %-13s %-16s fold=%.2f  z=%+.2f  p=%.3f  FDR=%.3f  %-3s  "
            "between-mission %.1fx vs within-mission %.2fx",
            row.crop, row.assay, row.pooled_fold_change, row.van_elteren_z,
            row.p_value, row.p_value_fdr,
            "SIG" if row.significant_fdr05 else "ns",
            row.between_mission_spread, row.max_within_mission_fold,
        )
    log.info("wrote analysis/results/antioxidant_summary.json")


if __name__ == "__main__":
    main()
