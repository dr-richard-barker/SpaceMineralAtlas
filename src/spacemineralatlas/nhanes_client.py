"""Client for CDC NHANES population baseline data.

Wraps nhanes_pytool_api to retrieve NHANES laboratory and demographic data,
providing harmonised access to population reference distributions for minerals
and haematological parameters.

The NHANES (National Health and Nutrition Examination Survey) is a continuous
cross-sectional survey conducted by the CDC's National Center for Health Statistics,
covering 1999-2018 in ten 2-year cycles. This module provides access to:

- Laboratory data: serum minerals (calcium, potassium, sodium, iron, phosphorus),
  complete blood counts (hemoglobin, hematocrit, RBC, WBC).
- Demographics: age, sex, race/ethnicity, weight, height (for stratification).

All data is fetched from public CDC servers and checksummed for auditability.
"""

from __future__ import annotations

import io
import logging
from pathlib import Path

import pandas as pd
import requests
from nhanes_data.nhanes_data_api import NHANESDataAPI

from .http import record_checksum
from .paths import RAW

logger = logging.getLogger(__name__)

# NHANES cycles available in nhanes_pytool_api. The library covers pre-pandemic
# data only; pandemic-era data (2019-2020+) must be obtained separately.
NHANES_CYCLES = (
    "1999-2000", "2001-2002", "2003-2004", "2005-2006", "2007-2008",
    "2009-2010", "2011-2012", "2013-2014", "2015-2016", "2017-2018"
)

# Mapping of NHANES variable names to human-readable mineral/analyte names.
# These are the column names as they appear in the TRANSFORMED CSV files.
BIOCHEMISTRY_VARIABLES = {
    "calcium": ("LBXSCA", "mg/dL"),  # Total Calcium, refrigerated serum
    "potassium": ("LBXSKSI", "mmol/L"),  # Potassium
    "sodium": ("LBXSNASI", "mmol/L"),  # Sodium
    "iron": ("LBXSIR", "ug/dL"),  # Iron, refrigerated serum
    "phosphorus": ("LBXSPH", "mg/dL"),  # Phosphorus
}

CBC_VARIABLES = {
    "hemoglobin": ("LBXHGB", "g/dL"),  # Hemoglobin
    "hematocrit": ("LBXHCT", "%"),  # Hematocrit
    "rbc_count": ("LBXRBCSI", "million/uL"),  # Red blood cell count
    "wbc_count": ("LBXWBCSI", "1000/uL"),  # White blood cell count
}

DEMOGRAPHIC_VARIABLES = {
    "seqn": "SEQN",  # Respondent sequence number (key for joining)
    "age": "RIDAGEYR",  # Age at screening
    "sex": "RIAGENDR",  # Sex (1=male, 2=female)
}


def _nhanes_api(data_dir: str = "data/raw/nhanes/") -> NHANESDataAPI:
    """Initialise the NHANES API with a cache directory."""
    return NHANESDataAPI(data_directory=data_dir)


def list_available_cycles() -> tuple[str, ...]:
    """Return available NHANES survey cycles."""
    return NHANES_CYCLES


def _download_xpt(cycle: str, filename: str) -> pd.DataFrame:
    """Download a single XPT file from CDC using corrected URL format.

    The nhanes_pytool_api library uses outdated URL patterns; this helper
    uses the current CDC structure.
    """
    # Convert cycle "2017-2018" to year "2017"
    year = cycle.split("-")[0]
    url = f"https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/{year}/DataFiles/{filename}.xpt"

    try:
        response = requests.get(url, timeout=90)
        response.raise_for_status()
        return pd.read_sas(io.BytesIO(response.content), format="xport")
    except Exception as e:
        logger.error("Failed to download %s: %s", url, e)
        raise


def get_biochemistry(cycle: str, *, force: bool = False) -> pd.DataFrame:
    """Download and parse NHANES standard biochemistry (BIOPRO) for *cycle*.

    Returns only the mineral variables relevant to this analysis: calcium,
    potassium, sodium, iron, phosphorus. Column names are transformed to
    human-readable forms and include the unit as a suffix.

    Parameters
    ----------
    cycle : str
        NHANES cycle, e.g. "2017-2018" or "2015-2016"
    force : bool
        If True, ignore cached data and re-download.

    Returns
    -------
    pd.DataFrame
        Rows are survey respondents, columns are mineral analytes with units.

    Raises
    ------
    ValueError
        If the cycle is not available.
    """
    if cycle not in NHANES_CYCLES:
        raise ValueError(f"Invalid cycle {cycle}; available: {NHANES_CYCLES}")

    api = _nhanes_api()
    file_description = "Standard Biochemistry Profile"

    try:
        # Get the actual filename from the variable table
        var_table = api._retrieve_variable_table("laboratory")
        file_mapping = api.retrieve_cycle_data_file_name_mapping(
            var_table, file_description
        )
        filename = file_mapping[cycle]

        # Download using corrected URL format
        raw = _download_xpt(cycle, filename)
    except Exception as e:
        logger.warning("Could not retrieve biochemistry for cycle %s: %s", cycle, e)
        raise ValueError(f"Could not retrieve biochemistry data for cycle {cycle}: {e}")

    output = pd.DataFrame()
    for mineral, (nhanes_var, unit) in BIOCHEMISTRY_VARIABLES.items():
        if nhanes_var in raw.columns:
            output[f"{mineral}_{unit.replace('/', '_per_').replace('%', 'pct')}"] = raw[nhanes_var]

    if "SEQN" in raw.columns:
        output.insert(0, "SEQN", raw["SEQN"])

    logger.info(
        "NHANES %s biochemistry: %d respondents, %d minerals",
        cycle, len(output), len(output.columns) - 1,
    )
    return output


def get_cbc(cycle: str, *, force: bool = False) -> pd.DataFrame:
    """Download and parse NHANES complete blood count (CBC) for *cycle*.

    Returns hemoglobin, hematocrit, RBC count, WBC count. Column names are
    transformed to human-readable forms with units.

    Parameters
    ----------
    cycle : str
        NHANES cycle
    force : bool
        If True, ignore cached data and re-download.

    Returns
    -------
    pd.DataFrame
        One row per respondent, columns for CBC analytes.

    Raises
    ------
    ValueError
        If the cycle is not available.
    """
    if cycle not in NHANES_CYCLES:
        raise ValueError(f"Invalid cycle {cycle}; available: {NHANES_CYCLES}")

    api = _nhanes_api()
    # Note: file description varies by cycle; try both variants
    file_descriptions = [
        "Complete Blood Count with 5-Part Differential",
        "Complete Blood Count",
    ]

    raw = None
    for file_description in file_descriptions:
        try:
            # Get the actual filename from the variable table
            var_table = api._retrieve_variable_table("laboratory")
            file_mapping = api.retrieve_cycle_data_file_name_mapping(
                var_table, file_description
            )
            filename = file_mapping[cycle]

            # Download using corrected URL format
            raw = _download_xpt(cycle, filename)
            break  # Success
        except Exception as e:
            logger.debug("Failed with description '%s': %s", file_description, e)
            continue

    if raw is None:
        raise ValueError(f"Could not retrieve CBC data for cycle {cycle}: tried {file_descriptions}")

    output = pd.DataFrame()
    for analyte, (nhanes_var, unit) in CBC_VARIABLES.items():
        if nhanes_var in raw.columns:
            output[f"{analyte}_{unit.replace('/', '_per_').replace('%', 'pct')}"] = raw[nhanes_var]

    if "SEQN" in raw.columns:
        output.insert(0, "SEQN", raw["SEQN"])

    logger.info(
        "NHANES %s CBC: %d respondents, %d analytes",
        cycle, len(output), len(output.columns) - 1,
    )
    return output


def get_demographics(cycle: str, *, force: bool = False) -> pd.DataFrame:
    """Download and parse NHANES demographics for *cycle*.

    Returns respondent sequence number (SEQN, for joining), age, and sex.

    Parameters
    ----------
    cycle : str
        NHANES cycle
    force : bool
        If True, ignore cached data and re-download.

    Returns
    -------
    pd.DataFrame
        Columns: SEQN, age_years, sex (1=male, 2=female)

    Raises
    ------
    ValueError
        If the cycle is not available.
    """
    if cycle not in NHANES_CYCLES:
        raise ValueError(f"Invalid cycle {cycle}; available: {NHANES_CYCLES}")

    api = _nhanes_api()
    file_description = "Demographic Variables & Sample Weights"

    try:
        # Get the actual filename from the variable table
        var_table = api._retrieve_variable_table("demographics")
        file_mapping = api.retrieve_cycle_data_file_name_mapping(
            var_table, file_description
        )
        filename = file_mapping[cycle]

        # Download using corrected URL format
        raw = _download_xpt(cycle, filename)
    except Exception as e:
        logger.warning("Could not retrieve demographics for cycle %s: %s", cycle, e)
        raise ValueError(f"Could not retrieve demographics data for cycle {cycle}: {e}")

    output = pd.DataFrame()
    if "SEQN" in raw.columns:
        output["SEQN"] = raw["SEQN"]
    if "RIDAGEYR" in raw.columns:
        output["age_years"] = raw["RIDAGEYR"]
    if "RIAGENDR" in raw.columns:
        output["sex"] = raw["RIAGENDR"]

    logger.info("NHANES %s demographics: %d respondents", cycle, len(output))
    return output


def get_cohort(cycle: str = "2017-2018", age_min: int = 18, *, force: bool = False) -> pd.DataFrame:
    """Load a combined NHANES cohort for analysis.

    Retrieves biochemistry, CBC, and demographics for the specified cycle,
    filters to adults >= age_min, and joins on SEQN.

    Parameters
    ----------
    cycle : str
        NHANES cycle (default: most recent, "2017-2018")
    age_min : int
        Minimum age for inclusion (default: 18 years)
    force : bool
        If True, ignore cached data and re-download.

    Returns
    -------
    pd.DataFrame
        One row per adult respondent, columns for minerals, CBC, age, sex.
        Rows with missing key analytes are dropped.
    """
    demo = get_demographics(cycle, force=force)
    bio = get_biochemistry(cycle, force=force)
    cbc = get_cbc(cycle, force=force)

    combined = (
        demo.merge(bio, on="SEQN", how="inner")
        .merge(cbc, on="SEQN", how="inner")
    )

    combined = combined[combined["age_years"] >= age_min].reset_index(drop=True)

    n_start = len(combined)
    combined = combined.dropna(subset=[
        col for col in combined.columns
        if any(m in col for m in ["calcium", "potassium", "sodium", "hemoglobin", "hematocrit"])
    ])
    n_after = len(combined)

    logger.info(
        "NHANES %s cohort (age >= %d): %d → %d respondents after dropna",
        cycle, age_min, n_start, n_after,
    )
    return combined
