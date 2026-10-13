# Correction note 2 — antioxidant results in OSDR-Veggie-Nutrition-Dashboard

**Subject repository:** `dr-richard-barker/OSDR-Veggie-Nutrition-Dashboard`
**Prepared:** 13 October 2026
**Prepared by:** Richard Barker
**Status:** Draft for the author's decision. Nothing in the subject repository
has been modified.
**Follows:** [`CORRECTION_NOTE.md`](CORRECTION_NOTE.md) (2 September 2026)

---

## Summary

The first correction note established that every numeric observation in the
subject repository came from `numpy.random`. The `np.random` calls were
subsequently removed (commit `8d84205`), but **the antioxidant results were not
corrected — they were replaced with a second set of untraceable numbers.**

Three distinct problems remain, each verified against the repository as it
stands at `4d8d01b`:

1. The published antioxidant model performance (`R² = 0.528` / `0.491`) appears
   in **no result file in the repository**.
2. The regression that the repository *does* compute is **fit and scored on the
   same rows**, so its R² of 0.96–0.99 is in-sample and not a generalisation
   estimate.
3. Leave-One-Crop-Out cross-validation is claimed in four places; **every
   `LeaveOneGroupOut` call in `analysis/` groups on mission, not crop.**

Separately, the real antioxidant measurements have now been obtained and
analysed, so replacements are available for the first time. They do not support
the published direction of effect.

## 1. The published R² values exist in no result file

`manuscript/chapters/03_results.tex:49`:

> "The Random Forest regressor achieved an $R^2$ of 0.528 for ORAC and 0.491 for
> phenolics."

The same two literals are baked into the site at `docs/js/ml-results.js:323-324`
and `docs/index.html:339,343`.

The repository's own computed values, in `analysis/results/ml_results_summary.json`
and `docs/data/ml_results.json`:

| target | computed R² |
| :- | -: |
| phenolics | 0.9600 |
| anthocyanins | 0.9841 |
| orac | 0.9915 |

A search for `0.528` or `0.491` across every file in `analysis/results/` and
`docs/data/` returns nothing. The published numbers match neither the computed
output nor any other artefact in the repository.

## 2. The computed R² is in-sample

`analysis/ml_pipeline.py:294-298`:

```python
rf = RandomForestRegressor(n_estimators=100, random_state=42)
rf.fit(X, y)
y_pred = rf.predict(X)

r2 = r2_score(y, y_pred)
```

The model is scored on the rows it was fit on. With 100 trees and no held-out
split this will approach 1.0 on almost any input, which is why the values read
0.96–0.99. They are not evidence that elemental profile predicts antioxidant
content; substituting them for the published 0.528/0.491 would replace an
untraceable number with an invalid one.

## 3. LOCOCV is claimed but not implemented

Claimed at `README.md:24`, `manuscript/chapters/02_methods.tex:43`,
`manuscript/chapters/03_results.tex:31` ("trained entirely on Lettuce … achieved
79.2% accuracy, while TabPFN reached 83.3%") and
`manuscript/chapters/05_conclusion.tex:8`.

Implemented grouping:

- `analysis/ml_pipeline.py:181` — `groups = df['mission']`
- `analysis/meta_ml_pipeline.py:97` — `groups_mission = df['mission'].values`
- `analysis/tabpfn_pipeline.py:162` — `groups = df['mission'].values`

No crop-based split was found anywhere in `analysis/`. The cross-species
generalisation claim — "validates the existence of a universal spaceflight
physiological signature across plant families" — therefore rests on a
cross-validation that was not run.

## 4. The real antioxidant data, and what it says

The ORAC, total phenolic and anthocyanin assay files were listed in each study's
OSDR file manifest throughout, but had never been downloaded. They were fetched
on 13 October 2026 by
[`fetch_antioxidant_data.py`](fetch_antioxidant_data.py) (17 files, checksums in
`SpaceMineralAtlas/fair/antioxidant_inputs.sha256`) and analysed by
`SpaceMineralAtlas/scripts_analyse_antioxidants.py`.

**Mission dominates these assays.** In the lettuce data the between-mission
spread is 11.1× for phenolics and 15.9× for anthocyanin, against within-mission
flight effects of 1.29× and 1.31×. A pooled flight-versus-ground comparison over
such data measures mission, not spaceflight. The analysis therefore uses a
stratified (van Elteren) test blocking on mission, and on mission × light for
OSD-655.

**Result: no antioxidant assay shows a flight effect surviving stratification at
FDR 0.05.**

| crop | assay | median flight | median ground | fold | FDR *p* | |
| :- | :- | -: | -: | -: | -: | :- |
| lettuce | ORAC (µmol TE/g DW) | 847.7 | 746.9 | 1.14 | 0.152 | ns |
| lettuce | total phenolics (mg/g DW) | 18.74 | 17.90 | 1.05 | 0.152 | ns |
| lettuce | anthocyanin (mg/g DW) | 4.42 | 4.04 | 1.09 | 0.370 | ns |
| Tokyo Bekana | ORAC (µmol TE/g DW) | 125.11 | 120.28 | 1.04 | 0.698 | ns |
| Tokyo Bekana | total phenolics (mg/g DW) | 11.42 | 11.90 | 0.96 | 0.698 | ns |

Source: `SpaceMineralAtlas/analysis/results/antioxidant_summary.json`, with
per-mission contrasts in `antioxidant_contrasts_by_mission.csv`.

### Against what the subject repository publishes

| | published | measured |
| :- | -: | -: |
| ORAC, flight / ground | 435.0 / 412.0 | **847.7 / 746.9** |
| phenolics, flight / ground | 11.2 / 9.2 | **18.74 / 17.90** |
| phenolics, direction | flight ↑, *p* = 0.032 significant | **+5%, not significant** |
| ORAC, direction | not significant | **+14%, not significant** |
| Tokyo Bekana phenolics | not reported separately | **−4%, not significant** |

The published absolute values are low by roughly a factor of two. More
importantly, the published flight phenolic increase corresponds to the
multiplier the superseded generator applied:

```python
phenolics *= np.random.uniform(1.2, 1.6)   # git show d30caa2:data/fetch_osdr_data.py
```

The measured effect is +5% in lettuce and −4% in Tokyo Bekana. **The flight
antioxidant increase was an artefact of the generator and does not survive
contact with the archive.**

This is consistent with the elemental finding already published in
SpaceMineralAtlas — lettuce shows no element significantly altered by
spaceflight — now reproduced independently on the antioxidant side.

## 5. Status of the 2 September recommendations

| Recommendation | Status |
| :- | :- |
| Remove `numpy.random` from the data path | **Done** (`8d84205`) |
| Remove the hardcoded accuracy literal in the `except` block | **Done** |
| Add a notice to `README.md` and `docs/index.html` that published figures derive from synthetic data | **Not done.** `README.md:44` instead asserts "60 authentic experimental samples … harmonized from NASA OSDR metadata" |
| Correct the element set | Not assessed in this note |
| Correct the "Mizuna" naming | **Not done** — `fetch_osdr_data.py:198` still writes `"Crop": "mizuna"` |
| Implement LOCOCV | **Not done** — see §3 |

Note also that `README.md` currently carries an **uncommitted** working-tree
change adding a crop → crew countermeasure claim (`README.md:47`). It asserts
"dietary countermeasures for spaceflight mineral imbalances identified in human
crew members" with no supporting result file. If committed it would be the
newest unsupported translational claim in the repository. SpaceMineralAtlas
makes the comparable claim only as a *supply* calculation and states explicitly
that it is "not a causal link".

## 6. Suggested actions

In order of urgency, since the site is live:

1. **Remove the 0.528 / 0.491 literals** from `docs/js/ml-results.js:323-324`,
   `docs/index.html:339,343` and `manuscript/chapters/03_results.tex:49`. They
   cannot be sourced. Do **not** replace them with the computed 0.96–0.99 —
   those are in-sample (§2). If a generalisation estimate is wanted, it needs a
   held-out or grouped split first.
2. **Add the notice** the 2 September note asked for, and amend `README.md:44`.
3. **Either implement LOCOCV or withdraw the claim** and the 79.2% / 83.3%
   figures that depend on it.
4. **Replace the antioxidant results** with the measured values in §4, framed as
   the negative result they are, blocking on mission. The analysis and a
   positive-control test for the stratified statistic already exist in
   `SpaceMineralAtlas/src/spacemineralatlas/antioxidants.py`.
5. Consider pointing the subject repository's data path at
   `fetch_antioxidant_data.py` rather than maintaining a second curation layer
   of hand-typed literals.

## 7. A caution about this note's own method

The first run of `fetch_antioxidant_data.py` reported 17 successful downloads
and wrote checksums for them. They were **API metadata records, not data**: the
biodata `REST_URL` returns a JSON description of a file, and the content
validator passed it because a single-line JSON object contains commas. The
archive's own `"file_size"` field was what exposed it.

The script now rejects JSON explicitly and prefers the datamanager URL. The
episode is recorded here because it is the same failure this note is about —
a pipeline that reports success while carrying something other than the
measurement — and because the checksums written on that first run would have
lent it entirely unearned credibility.
