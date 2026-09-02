# Correction note — OSDR-Veggie-Nutrition-Dashboard

**Subject repository:** `dr-richard-barker/OSDR-Veggie-Nutrition-Dashboard`
**Prepared:** 2 September 2026
**Prepared by:** Richard Barker
**Status:** Draft for the author's decision. Nothing in the subject repository
has been modified.

---

## Summary

The OSDR-Veggie-Nutrition-Dashboard reports elemental concentrations, statistical
contrasts, model accuracies and cross-species generalisation results for NASA
Veggie studies OSD-745, OSD-655 and OSD-780. **None of those values derive from
the NASA data.** Every numeric observation in `data/` is produced by
`numpy.random.normal()` in `data/fetch_osdr_data.py`, and the reported
machine-learning metrics are literals.

The real data for all three studies is openly available from the OSDR API and
was so at the time. This note documents what is affected and supplies a working
replacement.

## How the synthetic data enters

`data/fetch_osdr_data.py:160-172` contacts the OSDR API, confirms a 200 response,
and then discards it:

```python
def fetch_study(study_id: str):
    url = f"https://visualization.osdr.nasa.gov/biodata/api/v2/dataset/{study_id}/"
    ...
        if response.status_code == 200:
            logger.info(f"Connected successfully to {study_id} API.")
            # Simulating OSDR 502/ gaterestrictions
            logger.warning("Simulating 502 Bad Gateway fallback for study data.")
            return False
    ...
    return False
```

Because `fetch_study` returns `False` unconditionally, `main()` always falls
through to `create_synthetic_data()`, which generates every value from a normal
distribution and applies fixed multipliers to the flight arm
(`fetch_osdr_data.py:66-74`).

## Affected claims, with real replacements

The flight effects reported are the injected multipliers, not measurements.
Real flight/ground ratios, computed from the OSDR data:

| Element | Injected multiplier | **Real** lettuce (OSD-745) | **Real** Tokyo Bekana (OSD-655) | Tokyo Bekana after dilution correction |
|---|---|---:|---:|---:|
| Potassium | ×0.7–0.9 (down) | **0.99** (no change) | 1.54 | 1.15 (still significant) |
| Iron | ×1.2–1.5 (up) | **0.96** (no change) | 1.44 | 1.10 (**not** significant) |
| Calcium | *none injected* | **0.90** | 1.23 | 0.91 (**not** significant) |
| Sodium | ×1.5–2.0 | 1.18 | 2.15 | 1.80 (significant) |
| Sulfur | ×1.1–1.4 | 0.98 | 1.75 | 1.29 (significant) |
| Zinc | ×1.3–1.6 | 1.24 | 1.15 | 0.85 (significantly *down*) |
| Phosphorus | ×0.8–0.95 (down) | 1.10 (**up**) | 1.36 | 1.01 (not significant) |
| Magnesium | *none injected* | 1.00 | 1.23 | 0.91 |
| Manganese | *none injected* | 0.95 | 1.04 | 0.76 (significantly down) |

Two specific corrections matter most:

- **"K down, Fe up" is not what the real data shows.** In lettuce neither moves.
  In Tokyo Bekana both rise, and iron's rise does not survive correction for
  dry-matter dilution.
- **Calcium had no flight effect injected at all**, so any calcium claim in the
  dashboard, README or manuscript has no basis even in the synthetic data.

### Machine-learning metrics

| Claim | Where reported | Actual origin |
|---|---|---|
| TabPFN 89.6 % accuracy | README, abstract, discussion, conclusion, dashboard | Literal `0.896` at `analysis/meta_ml_pipeline.py:163`, inside an `except` block |
| Random forest 83.3 % | manuscript | `analysis/results/meta_ml_results.json` records 88.3 % |
| LOCOCV 79.2 % / 83.3 % | README, manuscript, `ro-crate-metadata.json` | **No leave-one-crop-out code exists in the repository** |
| PCA variance 42 % / 25 % | `03_results.tex` | Computed values are 37.0 % / 20.7 % |
| Feature importance Fe 0.28, K 0.18 | manuscript | Matches the `demoMLData` placeholder in `docs/js/app.js`, not the computed results |

On the real data, flight-versus-ground classification does **not** beat chance:
balanced accuracy 0.608 against a 0.568 baseline under leave-one-mission-out,
and *below* baseline (−0.11) under a genuine leave-one-crop-out split.

### Additional issues found

- **Sample size.** The synthetic dataset has 60 balanced samples (6 per
  mission-arm). The real data has 24 lettuce (11 flight / 13 ground) and 36
  Tokyo Bekana (18/18) — unbalanced, and lettuce has roughly a third of the
  claimed replication.
- **Wrong element set.** The synthetic data includes copper and omits boron.
  OSD-745 measures boron and not copper.
- **Crop naming.** OSD-655 grew *Brassica rapa* cv. 'Tokyo Bekana', a
  Chinese-cabbage type. The repository calls it "Mizuna mustard" throughout;
  mizuna is a different *B. rapa* cultivar group.
- **Gallery metadata.** `data/download_real_images.py:83-85` labels every image
  `"condition": "Ground"` and `"mission": "VEG-01B"`, because the filename test
  `if "KSC-" in filename` matches all ten files.
- **Methods claim.** `02_methods.tex` states files were "parsed from ISA-Tab
  (Investigation, Study, Assay) format sheets". No ISA-Tab parser exists in the
  repository.

## Suggested actions

1. Add a prominent notice to `README.md` and `docs/index.html` stating that the
   published figures derive from synthetic data and are being revised.
2. Replace `data/fetch_osdr_data.py` with `real_osdr_fetcher.py` from this
   directory (see below), then re-run the pipeline on real data.
3. Correct the elemental panel (add boron, remove copper for OSD-745) and the
   crop name.
4. Either implement leave-one-crop-out or remove the claim from the README,
   manuscript and `ro-crate-metadata.json`.
5. Remove the hardcoded metric fallbacks so a failed model surfaces as an error.
6. If a Zenodo DOI has been minted, publish a new version with these corrections
   and a versioned note.

## Replacement code

`real_osdr_fetcher.py` in this directory is a drop-in replacement for
`data/fetch_osdr_data.py`. It downloads the genuine OSDR elemental tables for
OSD-745 and OSD-655, applies the unit correction OSD-655 requires (see
`../fair/osdr_curation_report.md`), and **raises on failure rather than
generating data**. It has no dependency on the SpaceMineralAtlas package and can
be copied into the subject repository as-is.

Verified working as of 2 September 2026.
