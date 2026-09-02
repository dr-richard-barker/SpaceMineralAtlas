# OSDR curation report: unit-labelling defect in OSD-655

**Submitted by:** Richard Barker (dr.richard.barker@gmail.com)
**Date:** 2 September 2026
**Dataset:** OSD-655 — *Pick-and-eat space crop production flight testing on the
International Space Station* (Bunchek et al. 2024)
**Severity:** High — affects 5 of 12 elements by a factor of 1000, and is present
in the archived data dictionary as well as the data files.

---

## Summary

`LSDS-63_InductivelyCoupledPlasmaOpticalEmissionSpectroscopy_Bunchek2024_ICPOES_TRANSFORMED.csv`
names five columns with the unit `milligram_per_gram_of_dry_weight`:

| Column | Stated unit | Actual unit |
|---|---|---|
| `calcium_milligram_per_gram_of_dry_weight` | mg/g DW | µg/g DW |
| `potassium_milligram_per_gram_of_dry_weight` | mg/g DW | µg/g DW |
| `magnesium_milligram_per_gram_of_dry_weight` | mg/g DW | µg/g DW |
| `phosphorus_milligram_per_gram_of_dry_weight` | mg/g DW | µg/g DW |
| `sulfur_milligram_per_gram_of_dry_weight` | mg/g DW | µg/g DW |

`OSD-655_dictionary_DataDictionary_OSD-655.csv` repeats `unit: milligram_per_gram`
for each, so a consumer reading the dictionary is misled in the same way as one
reading the header.

## Evidence

**1. The stated units are physically impossible.** Mean values read as mg/g:

| Element | Mean as stated (mg/g) | Implied % of dry weight |
|---|---:|---:|
| Potassium | 29 426 | **2 943 %** |
| Magnesium | 8 053 | 805 % |
| Calcium | 6 510 | 651 % |
| Sulfur | 5 507 | 551 % |
| Phosphorus | 3 672 | 367 % |

No tissue can contain more than 100 % of its dry weight in a single element.

**2. Reinterpreted as µg/g, the values agree with an independent study.**
OSD-745 reports lettuce elemental data in `milligram_per_kilogram_of_dry_weight`
(numerically identical to µg/g). Ground-control means:

| Element | OSD-745 lettuce (µg/g) | OSD-655 Tokyo Bekana read as µg/g |
|---|---:|---:|
| Calcium | 4 501 | 5 827 |
| Potassium | 47 951 | 23 191 |
| Magnesium | 2 605 | 7 231 |

These are the ordinary ranges for leafy tissue and differ between the two species
by well under an order of magnitude.

**3. The defect is localised.** The six elements OSD-655 already labels in µg/g
(Al, B, Cu, Fe, Mn, Zn) require no correction and agree across studies as
supplied. Only the five columns labelled mg/g are affected, which is consistent
with a unit field applied incorrectly during transformation of the submitted
`Veg-04A_B_Master Chem.xlsx`.

## Impact

Any analysis concatenating OSD-655 with another elemental dataset without
correction places five of twelve elements on a scale 1000-fold larger in one
study. This would dominate any distance-based method, any principal component
analysis, and any model trained on pooled data.

## Suggested remedy

1. Correct the unit token in the five `*_TRANSFORMED.csv` column names to
   `microgram_per_gram_of_dry_weight`.
2. Correct the corresponding `unit` values in
   `OSD-655_dictionary_DataDictionary_OSD-655.csv`.
3. Consider adding an automated plausibility check to the transformation
   pipeline: flagging any elemental value above ~10 % of dry weight would have
   caught this before publication.

## Reproduction

```bash
git clone https://github.com/dr-richard-barker/SpaceMineralAtlas
cd SpaceMineralAtlas && make curate
```

`fair/harmonisation_report.txt` lists every override applied and its
justification; `analysis/results/qc_report.json` records the plausibility gate.
