"""Analysis and comparison of astronaut data against NHANES population baselines.

This module provides methods to:
1. Calculate percentile distributions of minerals and CBC parameters in NHANES cohorts.
2. Stratify by age group and sex to produce age/sex-matched reference ranges.
3. Express astronaut measurements as percentile ranks within population cohorts.
4. Compare pre-flight and post-flight values relative to population norms.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import astronaut, nhanes_client

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PercentileStats:
    """Summary statistics for a variable: percentiles, min, max, n."""

    n: int
    min: float
    p5: float
    p25: float
    p50: float  # median
    p75: float
    p95: float
    max: float
    mean: float
    std: float


def compute_percentiles(values: pd.Series) -> PercentileStats:
    """Compute percentile summary for a series."""
    v = values.dropna()
    return PercentileStats(
        n=len(v),
        min=float(v.min()),
        p5=float(v.quantile(0.05)),
        p25=float(v.quantile(0.25)),
        p50=float(v.quantile(0.50)),
        p75=float(v.quantile(0.75)),
        p95=float(v.quantile(0.95)),
        max=float(v.max()),
        mean=float(v.mean()),
        std=float(v.std()),
    )


def percentile_rank(value: float, values: pd.Series) -> float:
    """Compute the percentile rank of *value* within *values* (0-100)."""
    if pd.isna(value):
        return np.nan
    v = values.dropna().sort_values().values
    if len(v) == 0:
        return np.nan
    rank = (v < value).sum() / len(v) * 100
    return float(rank)


def stratified_reference_ranges(
    cohort: pd.DataFrame, variables: list[str] = None, age_bands: list[tuple[int, int]] = None
) -> dict[str, dict]:
    """Compute age/sex-stratified reference ranges for a NHANES cohort.

    Parameters
    ----------
    cohort : pd.DataFrame
        NHANES cohort with columns including 'age_years', 'sex', and mineral/CBC columns.
    variables : list[str], optional
        Variable names to summarise (default: all mineral/CBC columns).
    age_bands : list[tuple[int, int]], optional
        Age ranges for stratification. Default: [(18, 30), (30, 50), (50, 70), (70, 120)].

    Returns
    -------
    dict[str, dict]
        Nested dictionary: {variable: {stratum: PercentileStats}}, where
        stratum is e.g., "M_30-50" (male, 30-50 years).
    """
    if variables is None:
        variables = [c for c in cohort.columns if c not in ("SEQN", "age_years", "sex")]

    if age_bands is None:
        age_bands = [(18, 30), (30, 50), (50, 70), (70, 120)]

    results = {}
    for var in variables:
        if var not in cohort.columns:
            logger.warning("Variable %s not in cohort", var)
            continue

        results[var] = {}
        for sex_code, sex_name in [(1, "M"), (2, "F")]:
            for age_min, age_max in age_bands:
                stratum = (
                    (cohort["age_years"] >= age_min)
                    & (cohort["age_years"] < age_max)
                    & (cohort["sex"] == sex_code)
                )
                values = cohort.loc[stratum, var]

                if len(values.dropna()) > 0:
                    stratum_label = f"{sex_name}_{age_min}-{age_max - 1}"
                    results[var][stratum_label] = compute_percentiles(values)

    logger.info(
        "Computed stratified reference ranges for %d variables, "
        "%d strata per variable (on average)",
        len(results),
        sum(len(v) for v in results.values()) // len(results) if results else 0,
    )
    return results


def compare_astronauts_to_nhanes(
    nhanes_cohort: pd.DataFrame,
    nhanes_references: dict[str, dict],
    age_bands: list[tuple[int, int]] = None,
) -> pd.DataFrame:
    """Compare Inspiration4 astronaut measurements to NHANES population norms.

    Loads the Inspiration4 CMP and CBC data, matches each astronaut to their
    age/sex stratum in NHANES, and computes percentile ranks for pre-flight
    and post-flight values.

    Parameters
    ----------
    nhanes_cohort : pd.DataFrame
        NHANES cohort (output of nhanes_client.get_cohort()).
    nhanes_references : dict[str, dict]
        Stratified reference ranges (output of stratified_reference_ranges()).
    age_bands : list[tuple[int, int]], optional
        Age bands used in references (must match those used to compute references).

    Returns
    -------
    pd.DataFrame
        Columns: subject, mineral/analyte, unit, preflight_value, preflight_percentile,
        postflight_value, postflight_percentile, nhanes_median, nhanes_range_95,
        percentile_change.
    """
    if age_bands is None:
        age_bands = [(18, 30), (30, 50), (50, 70), (70, 120)]

    # Load astronaut data
    cmp = astronaut.load_cmp(force=False)
    # CBC is not yet in astronaut.py; for now, we'll skip it or load it separately
    # For this prototype, we'll focus on CMP minerals.

    records = []

    for subject in cmp["subject"].unique():
        subject_data = cmp[cmp["subject"] == subject]

        # Get crew metadata: age at mission and sex
        age_series = subject_data["age_at_mission"].dropna()
        sex_series = subject_data["sex"].dropna()

        if age_series.empty or sex_series.empty:
            logger.warning("%s: missing age or sex metadata", subject)
            continue

        estimated_age = int(age_series.iloc[0])
        estimated_sex = int(sex_series.iloc[0])

        # Find matching stratum
        matching_band = None
        for age_min, age_max in age_bands:
            if age_min <= estimated_age < age_max:
                matching_band = (age_min, age_max)
                stratum_label = f"{['M', 'F'][estimated_sex - 1]}_{age_min}-{age_max - 1}"
                break

        if matching_band is None:
            logger.warning("%s: age %d outside all age bands", subject, estimated_age)
            continue

        age_min, age_max = matching_band

        # Mapping from astronaut CMP column names to NHANES cohort column names
        mineral_mapping = {
            "calcium": "calcium_mg_per_dL",
            "potassium": "potassium_mmol_per_L",
            "sodium": "sodium_mmol_per_L",
        }

        # For each mineral measured in CMP
        for mineral, nhanes_col in mineral_mapping.items():
            if mineral not in subject_data.columns:
                continue

            preflight_vals = subject_data[subject_data["phase"] == "preflight"][mineral]
            postflight_vals = subject_data[subject_data["phase"] == "postflight"][mineral]

            if preflight_vals.empty or postflight_vals.empty:
                continue

            preflight_mean = preflight_vals.mean()
            postflight_mean = postflight_vals.mean()

            # Find NHANES reference for this mineral in this stratum
            # Use the astronaut column name (e.g., "calcium") as key for references
            if mineral not in nhanes_references or stratum_label not in nhanes_references[mineral]:
                logger.debug(
                    "%s: no NHANES reference for %s in stratum %s",
                    subject, mineral, stratum_label,
                )
                # Try using all-cohort reference as fallback
                if mineral in nhanes_references:
                    # Use any available stratum from this mineral
                    available_strata = list(nhanes_references[mineral].keys())
                    if available_strata:
                        logger.debug("%s: using fallback stratum %s", subject, available_strata[0])
                        stratum_label = available_strata[0]
                    else:
                        continue
                else:
                    continue

            nhanes_ref = nhanes_references[mineral][stratum_label]
            nhanes_vals = nhanes_cohort[
                (nhanes_cohort["age_years"] >= age_min)
                & (nhanes_cohort["age_years"] < age_max)
                & (nhanes_cohort["sex"] == estimated_sex)
            ][nhanes_col]

            pct_preflight = percentile_rank(preflight_mean, nhanes_vals)
            pct_postflight = percentile_rank(postflight_mean, nhanes_vals)

            records.append({
                "subject": subject,
                "analyte": mineral,
                "nhanes_cycle": "2017-2018",
                "nhanes_stratum": stratum_label,
                "preflight_value": float(preflight_mean),
                "preflight_percentile": pct_preflight,
                "postflight_value": float(postflight_mean),
                "postflight_percentile": pct_postflight,
                "percentile_change": pct_postflight - pct_preflight if not (
                    pd.isna(pct_preflight) or pd.isna(pct_postflight)
                ) else np.nan,
                "nhanes_median": nhanes_ref.p50,
                "nhanes_range_5_95": f"{nhanes_ref.p5:.1f}-{nhanes_ref.p95:.1f}",
                "nhanes_n": nhanes_ref.n,
            })

    if not records:
        logger.warning("No astronaut-NHANES comparisons generated")
        result = pd.DataFrame()
    else:
        result = pd.DataFrame(records)
        logger.info(
            "Comparison table: %d subject-analyte pairs, %d unique subjects",
            len(result), result["subject"].nunique(),
        )
    return result
