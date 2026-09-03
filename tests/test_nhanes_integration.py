"""Tests for NHANES integration: data loading, integrity, no synthetic data."""

import pytest
from pathlib import Path

from spacemineralatlas import nhanes_client, nhanes_analysis


class TestNHANESClient:
    """NHANES data loading tests."""

    def test_cycles_available(self):
        """Verify that expected cycles are declared."""
        cycles = nhanes_client.list_available_cycles()
        assert len(cycles) == 10
        assert "2017-2018" in cycles
        assert "1999-2000" in cycles

    def test_biochemistry_variables_mapped(self):
        """Verify that biochemistry variable mapping is not empty."""
        assert len(nhanes_client.BIOCHEMISTRY_VARIABLES) > 0
        assert "calcium" in nhanes_client.BIOCHEMISTRY_VARIABLES
        assert "potassium" in nhanes_client.BIOCHEMISTRY_VARIABLES
        assert "sodium" in nhanes_client.BIOCHEMISTRY_VARIABLES
        assert "iron" in nhanes_client.BIOCHEMISTRY_VARIABLES

    def test_cbc_variables_mapped(self):
        """Verify CBC variable mapping."""
        assert len(nhanes_client.CBC_VARIABLES) > 0
        assert "hemoglobin" in nhanes_client.CBC_VARIABLES
        assert "hematocrit" in nhanes_client.CBC_VARIABLES
        assert "rbc_count" in nhanes_client.CBC_VARIABLES
        assert "wbc_count" in nhanes_client.CBC_VARIABLES

    def test_demographic_variables_mapped(self):
        """Verify demographic variable mapping."""
        assert len(nhanes_client.DEMOGRAPHIC_VARIABLES) > 0
        assert "seqn" in nhanes_client.DEMOGRAPHIC_VARIABLES
        assert "age" in nhanes_client.DEMOGRAPHIC_VARIABLES
        assert "sex" in nhanes_client.DEMOGRAPHIC_VARIABLES

    @pytest.mark.slow
    def test_get_cohort_downloads_and_joins(self):
        """Verify that get_cohort() downloads and joins NHANES data successfully.

        This test actually fetches data from CDC servers and is marked 'slow'.
        """
        try:
            cohort = nhanes_client.get_cohort(cycle="2017-2018", age_min=18)
        except ValueError as e:
            pytest.skip(f"Could not fetch NHANES data: {e}")

        # Basic shape checks
        assert len(cohort) > 0, "Cohort should not be empty"
        assert "SEQN" in cohort.columns, "SEQN (join key) should be present"
        assert "age_years" in cohort.columns, "age_years should be present"
        assert "sex" in cohort.columns, "sex should be present"

        # At least one mineral should be present
        mineral_cols = [c for c in cohort.columns if any(m in c for m in ["calcium", "potassium", "sodium"])]
        assert len(mineral_cols) > 0, "At least one mineral column should be present"

        # No invalid ages
        assert (cohort["age_years"] >= 18).all(), "All respondents should be >= 18 years"

    @pytest.mark.slow
    def test_no_synthetic_biochemistry(self):
        """Verify that biochemistry data comes from CDC, not synthetic generation."""
        try:
            cohort = nhanes_client.get_cohort(cycle="2017-2018")
        except ValueError:
            pytest.skip("Could not fetch NHANES data")

        # A tell-tale sign of synthetic data is zero variance or all identical values
        calcium_cols = [c for c in cohort.columns if "calcium" in c]
        if calcium_cols:
            col = calcium_cols[0]
            values = cohort[col].dropna()
            # Real population data has non-zero variance
            assert values.std() > 0, f"{col} should have non-zero variance"
            # Real population data should span a reasonable range
            assert values.max() - values.min() > 0.1, f"{col} range should be > 0.1"


class TestNHANESAnalysis:
    """NHANES statistical analysis tests."""

    def test_percentiles_computation(self):
        """Verify percentile computation."""
        import pandas as pd
        import numpy as np

        data = pd.Series(np.arange(1, 101))  # 1 to 100
        stats = nhanes_analysis.compute_percentiles(data)

        assert stats.n == 100
        assert stats.min == 1
        assert stats.max == 100
        assert stats.p50 == 50.5  # median of 1-100
        assert stats.mean == 50.5
        assert 0 < stats.std < 30  # reasonable std dev

    def test_percentile_rank_computation(self):
        """Verify percentile rank."""
        import pandas as pd
        import numpy as np

        data = pd.Series(np.arange(1, 101))

        # Value at median should be ~50th percentile
        rank_50 = nhanes_analysis.percentile_rank(50, data)
        assert 45 < rank_50 < 55, f"Rank of 50 should be ~50, got {rank_50}"

        # Value at max should be ~100th percentile
        rank_100 = nhanes_analysis.percentile_rank(100, data)
        assert rank_100 > 95, f"Rank of 100 should be ~100, got {rank_100}"

        # Value below min should be ~0th percentile
        rank_0 = nhanes_analysis.percentile_rank(0, data)
        assert rank_0 < 5, f"Rank of 0 should be ~0, got {rank_0}"

        # NaN value should return NaN
        rank_nan = nhanes_analysis.percentile_rank(np.nan, data)
        assert np.isnan(rank_nan)

    def test_stratified_references_produces_strata(self):
        """Verify that stratified_reference_ranges produces multiple strata."""
        import pandas as pd
        import numpy as np

        # Create a minimal cohort
        cohort = pd.DataFrame({
            "age_years": [25, 35, 45, 55, 65, 75] * 10,
            "sex": [1, 2] * 30,
            "calcium_mg_dL": np.random.normal(8.5, 0.5, 60),
        })

        refs = nhanes_analysis.stratified_reference_ranges(
            cohort,
            variables=["calcium_mg_dL"],
            age_bands=[(18, 30), (30, 50), (50, 70), (70, 120)],
        )

        assert "calcium_mg_dL" in refs
        strata = refs["calcium_mg_dL"]
        # Should have multiple strata (age bands × sex)
        assert len(strata) > 1, "Should have multiple age/sex strata"
        # Each stratum should have stats
        for stratum_label, stats in strata.items():
            assert stats.n > 0
            assert stats.p50 is not None
