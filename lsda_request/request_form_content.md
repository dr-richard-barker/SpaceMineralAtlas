# Prepared content for the LSDA data request form

Submit at <https://nlsp.nasa.gov/explore/lsdahome/datarequest>. Fields below map
to the portal's request form; adjust wording to fit any field length limits.

---

## Requester

**Name:** Richard Barker
**Email:** dr.richard.barker@gmail.com
**Institution:** University of Wisconsin–Madison
**Role:** Researcher (space biology / plant and crew nutrition)

## Experiments requested

1. **SMO-016E — Nutritional Status Assessment** (primary)
2. **SMO-015 — Validation of Procedures for Monitoring Crewmember Immune Function** (secondary, if available under the same request)

## Data requested

De-identified, timepoint-summarised biochemical and dietary data for the ISS
long-duration cohort, specifically:

- Serum and urine mineral and electrolyte concentrations: potassium, sodium,
  chloride, calcium, magnesium, phosphorus, iron, zinc, selenium, sulfate,
  oxalate
- Iron-status indices: ferritin, transferrin, transferrin receptors, haemoglobin,
  haematocrit
- Bone and mineral-regulatory markers: bone-specific alkaline phosphatase,
  pyridinium cross-links, N-telopeptide, parathyroid hormone, 25-hydroxyvitamin D
- **Recorded dietary intake** per timepoint, at nutrient level where available
  (this is the element without an open-data equivalent)
- Timepoint labels and days relative to launch and return
- Subject-level identifiers sufficient to link timepoints within a subject
  (de-identified codes, as used in the published analyses)

The eight-timepoint non-attributable summarisation described in Zheng et al.
(2023) is entirely sufficient; we are not requesting raw per-draw values and have
no need for any information that could identify individual crew members.

## Purpose of the request

We have completed an open-data reanalysis of the two NASA Veggie studies with
archived ICP-OES elemental data (OSD-745, OSD-655) and Inspiration4 clinical
chemistry (OSD-575). That work quantifies what spaceflight-grown produce
contains and what a realistic serving delivers against NASA crew mineral
requirements (JSC-67378 Rev 1).

The analysis cannot presently address the question it was designed for: whether
dietary mineral intake during spaceflight is reflected in crew mineral status.
The openly available crew data (OSD-575) covers four subjects on a three-day
mission with no in-flight sampling and no recorded dietary intake. SMO-016E
supplies all three of the missing elements.

Intended analysis:

1. Relate recorded dietary mineral intake to serum and urine mineral status
   across pre-flight, in-flight and post-flight timepoints, within subject.
2. Establish empirical intake-to-status relationships for potassium, calcium,
   iron and magnesium, and compare them against the JSC-67378 requirements.
3. Determine what fraction of crew mineral requirements a Veggie-scale crop
   production system could realistically supply, and whether the mineral profile
   of spaceflight-grown produce complements or duplicates the existing flight
   food system.

## Intended products

Peer-reviewed publication, plus open-source analysis code and a FAIR data package
deposited on Zenodo. Derived summary statistics only will be published; no
subject-level data will be redistributed, and we will follow whatever
redistribution terms LSDA specifies.

Existing outputs from the open-data portion of this work:
<https://github.com/dr-richard-barker/SpaceMineralAtlas>

## Funding / affiliation context

Independent research continuing prior NASA GeneLab / OSDR analysis work.

## Data handling

Data will be stored on encrypted institutional storage, not committed to any
public repository, and not shared beyond the named requester without LSDA's
written agreement. The analysis pipeline reads the data from a local path that
is excluded from version control by default.
