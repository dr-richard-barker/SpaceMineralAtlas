# LSDA data request package — SMO-016E Nutritional Status Assessment

This directory contains everything needed to submit a data request to the NASA
Life Sciences Data Archive for the dataset that would close the principal gap in
this study: paired **dietary intake** and **serum mineral** measurements from
long-duration ISS crew, with in-flight sampling.

**Submit at:** <https://nlsp.nasa.gov/explore/lsdahome/datarequest>

## Why this dataset

Our survey of all 2,676 LSDA experiments (see `catalog/`) identified
**SMO-016E "Nutritional Status Assessment"** as the highest-value target for
plant-to-crew mineral questions. It is the most comprehensive in-flight study
NASA has conducted of human physiological change during long-duration
spaceflight, and it is the source behind Zheng et al. 2023
(*Front. Physiol.* 14:1219221, doi:10.3389/fphys.2023.1219221).

| | SMO-016E | OSD-575 (what we could use) |
|---|---|---|
| Subjects | 27 (19 M, 8 F) | 4 |
| Mission duration | ~165 days mean | 3 days |
| In-flight sampling | **Yes** (3 timepoints) | No |
| Minerals measured | K, Na, Cl, Ca, Mg, P, Fe, Zn, Se, sulfate, oxalate | Ca, K, Na, Cl, CO2 |
| Dietary intake recorded | **Yes** | No |
| Matrices | Serum and urine | Serum |
| Access | Request required | Open |

LSDA record: <https://lsda.jsc.nasa.gov/Experiment/exper/1343>

The two capabilities OSD-575 lacks entirely — in-flight timepoints and recorded
dietary intake — are precisely what an intake-versus-status analysis requires.

## Files

| File | Purpose |
|---|---|
| `request_form_content.md` | Prepared text for each field of the LSDA request form |
| `variables_requested.csv` | Explicit list of variables sought, with justification |
| `target_schema.json` | The schema the received data will be mapped into |

## How the data would be ingested

The analysis code already contains the ingest slot. `src/spacemineralatlas/astronaut.py`
defines `load_smo016e()`, which reads a file placed at
`data/raw/smo016e/` and returns a frame matching `target_schema.json`. No change
to the statistical or integration code is required — the plant-to-crew
calculations in `integrate.py` operate on that schema.

Until the request is granted, `load_smo016e()` raises a `FileNotFoundError` with
these instructions. It does **not** fall back to any substitute or simulated
data.

## Status

- [ ] Request submitted
- [ ] Request acknowledged
- [ ] Data received
- [ ] Data ingested and analysis extended

Update this checklist when the state changes.
