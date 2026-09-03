"""SpaceMineralAtlas: spaceflight mineral-ion and dietary data from NASA LSDA and OSDR.

This package contains NO synthetic or simulated data generation. Every value that
reaches an analysis or a figure originates from a NASA API response whose bytes are
recorded in ``fair/checksums.sha256``. See ``tests/test_no_synthetic_data.py``, which
fails the build if a random-number data generator is ever introduced.
"""

__version__ = "0.1.0"

# Canonical unit for all elemental concentrations in this project.
# Chosen because it is the unit in which both source studies' values are actually
# expressed once the OSD-655 mislabelling is corrected (see harmonise.py).
CANONICAL_ELEMENT_UNIT = "microgram_per_gram_dry_weight"

# Public API
from . import nhanes_analysis, nhanes_client

__all__ = ["nhanes_analysis", "nhanes_client"]
