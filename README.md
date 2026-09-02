# SpaceMineralAtlas

Mining NASA's Life Sciences Data Archive and Open Science Data Repository for
spaceflight mineral-ion and dietary data — and reanalysing what is actually
there.

[![Python](https://img.shields.io/badge/python-3.11-blue)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/code-MIT-green)](LICENSE)
[![Data: CC BY 4.0](https://img.shields.io/badge/data-CC%20BY%204.0-lightgrey)](LICENSE-CC-BY-4.0)
[![Tests](https://img.shields.io/badge/tests-80%20passing-brightgreen)](tests/)

---

## What this is

Crops grown on the ISS are meant to supplement crew diets, which makes their
mineral content a question for both plant biology and crew nutrition. This
repository reanalyses the two NASA Veggie studies that have archived ICP-OES
elemental data, joins them to openly available astronaut clinical chemistry, and
surveys the entire NASA Life Sciences Data Archive to establish what mineral and
dietary data exists and whether it can actually be obtained.

**Every value here comes from a public NASA API and is checksummed. Nothing is
simulated.** A test suite fails the build if synthetic-data generation is ever
introduced ([`tests/test_no_synthetic_data.py`](tests/test_no_synthetic_data.py)).

## Headline findings

### 1. A 1000-fold unit-labelling defect in OSD-655

OSD-655 labels calcium, potassium, magnesium, phosphorus and sulfur as **mg/g dry
weight** — in both its data files and its archived data dictionary. The values
are µg/g. Read as stated, potassium would be **2,943% of dry weight**.

Any analysis pooling OSD-655 with another elemental dataset without correcting
this is wrong by a factor of 1000 on five of twelve elements. Reported to the
OSDR curation team: [`fair/osdr_curation_report.md`](fair/osdr_curation_report.md).

### 2. The two Veggie crops do not share a flight response

Flight/ground fold changes, before and after correcting for dry-matter dilution
with a centred log-ratio transform:

| Element | Lettuce (raw) | Tokyo Bekana (raw) | Tokyo Bekana (CLR) | Survives correction? |
|---|---:|---:|---:|:---|
| Potassium | 0.99 | 1.54 | 1.15 | **yes** |
| Sodium | 1.18 | 2.15 | 1.80 | **yes** |
| Sulfur | 0.97 | 1.75 | 1.28 | **yes** |
| Calcium | 0.90 | 1.23 | 0.91 | no — dilution artefact |
| Iron | 0.96 | 1.43 | 1.10 | no — dilution artefact |

Lettuce shows **no** element significantly altered by spaceflight on either
scale. Tokyo Bekana shows 6 after correction.
The apparent calcium and iron increases — the accumulation hypothesis this work
set out to test — do not survive.

### 3. No flight signature transfers between crops

| Cross-validation | Best model (balanced accuracy) | Baseline | Margin |
|---|---:|---:|---:|
| Leave-one-mission-out | 0.608 | 0.568 | +0.040 |
| Leave-one-crop-out | 0.486 | 0.600 | -0.113 |

Training on one crop and testing on the other performs **below chance** — which
is itself the measurement: there is no shared signature to learn.

### 4. Dietary mineral overload is not achievable

A 100 g fresh serving supplies 13.9% (lettuce) /
10.5% (Tokyo Bekana) of the NASA daily
potassium requirement, and 4.0% / 7.2%
of calcium. Reaching NASA's iron upper limit would take **0.85 kg** of fresh
lettuce or **1.23 kg** of Tokyo Bekana per day, against a per-pillow yield of
roughly 45 g. Sufficiency, not excess, is the operative question — and manganese
(122% of the daily requirement per serving) is the element to watch.

### 5. Access, not measurement, is the bottleneck

Of 2,676 LSDA experiments surveyed, 423
measured a mineral or nutritional variable. Only **62 are openly
available**; 213 require a formal data
request and 145 were never submitted to the archive.

The highest-value target — **SMO-016E Nutritional Status Assessment** (27
astronauts, ~165-day missions, in-flight sampling, paired dietary intake and
serum chemistry) — is request-gated. A prepared request is in
[`lsda_request/`](lsda_request/).

## Quick start

```bash
make setup     # create the venv, install pinned dependencies
make all       # run everything: harvest, fetch, analyse, figures, manuscript
```

Individual stages: `make harvest`, `make curate`, `make analyse`,
`make figures`, `make manuscript`, `make fair`, `make test`.

The first run downloads roughly 140 files from NASA APIs and takes about six
minutes, most of it the deliberately throttled LSDA harvest (the endpoint
returns 502/503 if requests are not spaced). Downloads are cached, so re-runs
are fast.

## What's here

| Path | Contents |
|---|---|
| `src/spacemineralatlas/` | The analysis package — API clients, unit harmonisation, QC gates, statistics, ML, figures |
| `catalog/` | The annotated LSDA catalog: all 2,676 experiments, plus mineral/nutrition subsets |
| `data/processed/` | Harmonised analysis-ready tables (µg/g dry weight throughout) |
| `analysis/results/` | Every statistic as JSON/CSV |
| `analysis/figures/` | Publication figures at 300 dpi |
| `manuscript/` | LaTeX source, PDF and DOCX |
| `fair/` | Zenodo metadata, RO-Crate, data dictionary, checksums, OSDR curation report |
| `lsda_request/` | Prepared data request for SMO-016E |
| `veggie_correction/` | Correction note and replacement fetcher for a prior analysis (see below) |
| `tests/` | 80 tests, including guards against synthetic data and result drift |

## Data sources

| Study | Contents | Access |
|---|---|---|
| [OSD-745](https://osdr.nasa.gov/bio/repo/data/studies/OSD-745) | Lettuce ICP-OES, VEG-01A/01B/03A (24 samples) | Open |
| [OSD-655](https://osdr.nasa.gov/bio/repo/data/studies/OSD-655) | Tokyo Bekana ICP-OES + water/mass supplements, VEG-04A/04B (36 samples) | Open |
| [OSD-575](https://osdr.nasa.gov/bio/repo/data/studies/OSD-575) | Inspiration4 metabolic panel (4 crew, 28 observations) | Open |
| [LSDA catalog](https://nlsp.nasa.gov/explore/mtable/lsda_experiment/lsda_experiment) | 2,676 experiment records | Open |
| SMO-016E | Nutritional Status Assessment | **Request required** |

## How reproducibility is enforced

Not by convention — by construction:

- **No synthetic data path exists.** Tests fail the build on `np.random.normal`,
  `make_classification`, or a numeric literal assigned inside an `except` block.
- **A failed download raises.** `http.fetch` never returns a fallback value.
- **Manuscript numbers are injected, never typed.** All 179 statistics in the
  paper are `\newcommand` macros generated from the analysis JSON. A macro used
  without a definition halts the LaTeX build; `make check` catches it first.
- **The bibliography is generated.** Every DOI is fetched from Crossref at build
  time; an unresolvable DOI fails the build.
- **Unit corrections are auditable.** Each override records the stated unit, the
  applied unit and its evidence; an independent QC gate re-checks the result
  against a physical bound.
- **Headline results are pinned by regression tests.** If a pipeline change moves
  a reported fold change, the tests go red.

## Note on a prior analysis

An earlier repository (`OSDR-Veggie-Nutrition-Dashboard`) published elemental
results, model accuracies and cross-species generalisation figures for these same
studies. Those values were produced by a `numpy.random` generator rather than
measured, and the reported model metrics were hardcoded literals. They are not
comparable with the results here.

[`veggie_correction/`](veggie_correction/) contains a correction note with real
replacement values and a tested drop-in replacement for the data-acquisition
module. The subject repository has not been modified.

## Limitations

- 60 plant samples total; the crop divergence needs replication.
- Crop, mission, duration and light spectrum are confounded across the two studies.
- No dry-matter fraction is archived, so mineral content is bounded (5–10% DM), not point-estimated.
- No substrate elemental assay exists, so true bioavailability cannot be computed.
- The astronaut cohort is 4 crew over 3 days with no in-flight sample.
- Plant and crew data are from different missions and crews: the integration is a
  supply calculation, not a causal link.

## Citation

See [`CITATION.cff`](CITATION.cff). Code MIT; data, figures and text CC BY 4.0.
