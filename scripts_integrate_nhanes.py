#!/usr/bin/env python3
"""Integration script: Load NHANES cohort and compare to astronaut data.

Fetches the NHANES 2017-2018 cycle (most recent pre-pandemic), computes
age/sex-stratified reference ranges for minerals and CBC parameters, and
expresses astronaut (Inspiration4) measurements as percentile ranks within
the population distribution.

Output: data/processed/nhanes_astronaut_comparison.csv
"""

import logging
from pathlib import Path

import pandas as pd

from src.spacemineralatlas import nhanes_analysis, nhanes_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    """Fetch NHANES, compute references, and compare to astronauts."""
    logger.info("=" * 70)
    logger.info("NHANES-Astronaut Integration")
    logger.info("=" * 70)

    # Step 1: Fetch NHANES 2017-2018 cohort
    logger.info("\n[1] Fetching NHANES 2017-2018 population cohort...")
    nhanes_cohort = nhanes_client.get_cohort(cycle="2017-2018", age_min=18, force=False)
    logger.info(f"    Loaded {len(nhanes_cohort)} respondents")

    # Step 2: Compute stratified reference ranges
    logger.info("\n[2] Computing age/sex-stratified reference ranges...")

    # Normalize NHANES column names to match astronaut CMP names
    nhanes_mapping = {
        "calcium_mg_per_dL": "calcium",
        "potassium_mmol_per_L": "potassium",
        "sodium_mmol_per_L": "sodium",
        "hemoglobin_g_per_dL": "hemoglobin",
        "hematocrit_pct": "hematocrit",
        "iron_ug_per_dL": "iron",
    }
    nhanes_refs_data = nhanes_cohort.copy()
    for old_name, new_name in nhanes_mapping.items():
        if old_name in nhanes_refs_data.columns:
            nhanes_refs_data[new_name] = nhanes_refs_data[old_name]

    variables = [new_name for new_name in nhanes_mapping.values()
                 if new_name in nhanes_refs_data.columns]
    logger.info(f"    Analysing {len(variables)} variables")

    nhanes_refs = nhanes_analysis.stratified_reference_ranges(
        nhanes_refs_data, variables=variables
    )

    # Step 3: Compare astronaut data to population norms
    logger.info("\n[3] Comparing Inspiration4 astronauts to NHANES population...")
    comparison = nhanes_analysis.compare_astronauts_to_nhanes(
        nhanes_cohort, nhanes_refs
    )
    logger.info(f"    Generated {len(comparison)} subject-analyte comparisons")

    # Step 4: Write output
    output_dir = Path("data/processed")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "nhanes_astronaut_comparison.csv"

    if len(comparison) > 0:
        comparison.to_csv(output_path, index=False)
        logger.info(f"\n[✓] Comparison table written to {output_path}")

        # Step 5: Summary statistics
        logger.info("\nComparison summary:")
        logger.info(f"  Subjects: {comparison['subject'].nunique()}")
        logger.info(f"  Analytes: {comparison['analyte'].nunique()}")
        logger.info(f"  Records: {len(comparison)}")

        if not comparison["preflight_percentile"].isna().all():
            logger.info(
                f"  Pre-flight percentiles: median={comparison['preflight_percentile'].median():.1f}, "
                f"range=[{comparison['preflight_percentile'].min():.1f}, "
                f"{comparison['preflight_percentile'].max():.1f}]"
            )
        if not comparison["postflight_percentile"].isna().all():
            logger.info(
                f"  Post-flight percentiles: median={comparison['postflight_percentile'].median():.1f}, "
                f"range=[{comparison['postflight_percentile'].min():.1f}, "
                f"{comparison['postflight_percentile'].max():.1f}]"
            )
    else:
        logger.warning("No astronaut-NHANES comparisons could be generated")
        logger.info("(This is expected with placeholder age/sex estimates; see nhanes_analysis.py)")

    logger.info("\n" + "=" * 70)


if __name__ == "__main__":
    main()
