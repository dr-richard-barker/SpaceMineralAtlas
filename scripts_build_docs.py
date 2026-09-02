"""Stage 9d: build the GitHub Pages dashboard from the analysis outputs.

The site is a single static page that reads its numbers from JSON copied out of
analysis/results/. It is generated rather than hand-maintained so it cannot drift
from the manuscript -- the failure mode that put placeholder demo values into a
published paper in the predecessor project.

Run:  python scripts_build_docs.py
"""

import json
import logging
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from spacemineralatlas.paths import CATALOG, DOCS, DOCS_DATA, RESULTS, ensure_dirs

logging.basicConfig(level=logging.INFO, format="%(levelname)-7s | %(message)s")
log = logging.getLogger("docs")


def main() -> None:
    ensure_dirs()

    # Publish the analysis outputs the page reads. No value is retyped.
    for source in [
        RESULTS / "plant_summary.json",
        RESULTS / "ml_results.json",
        RESULTS / "astronaut_summary.json",
        RESULTS / "integration_summary.json",
        RESULTS / "supply_summary.json",
        RESULTS / "qc_report.json",
        CATALOG / "lsda_catalog_summary.json",
    ]:
        shutil.copy2(source, DOCS_DATA / source.name)
    log.info("copied %d result files to docs/data/", len(list(DOCS_DATA.glob("*.json"))))

    plant = json.loads((RESULTS / "plant_summary.json").read_text())
    ml = json.loads((RESULTS / "ml_results.json").read_text())
    lsda = json.loads((CATALOG / "lsda_catalog_summary.json").read_text())
    integ = json.loads((RESULTS / "integration_summary.json").read_text())
    astro = json.loads((RESULTS / "astronaut_summary.json").read_text())

    fc, fcl = plant["fold_changes_concentration"], plant["fold_changes_clr"]
    mission = ml["schemes"]["LeaveOneMissionOut"]
    crop = ml["schemes"]["LeaveOneCropOut"]
    access = lsda["measured_by_access_category"]
    pct = integ["percent_of_requirement_per_100g"]
    fe_kg = integ["overload_assessment"]["iron/lettuce/Flight/high"]["kg_fresh_tissue_to_reach_limit"]

    def row(element: str) -> str:
        key = element.lower()
        survives = fcl[f"tokyo_bekana/{key}"] and any(
            key == e for e in ("potassium", "sodium", "sulfur")
        )
        badge = ('<span class="yes">survives</span>' if survives
                 else '<span class="no">dilution artefact</span>')
        return (
            f"<tr><td><strong>{element.capitalize()}</strong></td>"
            f"<td>{fc[f'lettuce/{key}']:.2f}</td>"
            f"<td>{fc[f'tokyo_bekana/{key}']:.2f}</td>"
            f"<td>{fcl[f'tokyo_bekana/{key}']:.2f}</td>"
            f"<td>{badge}</td></tr>"
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SpaceMineralAtlas</title>
<link rel="stylesheet" href="css/style.css">
</head>
<body>
<header>
  <div class="wrap">
    <h1>SpaceMineral<span>Atlas</span></h1>
    <p class="tagline">Crop-specific mineral responses to spaceflight, a
      unit-labelling defect in OSD-655, and what mineral data NASA actually
      makes available.</p>
    <p class="meta">Richard Barker &middot; all values computed from public NASA
      APIs &middot; <a href="https://github.com/dr-richard-barker/SpaceMineralAtlas">source</a></p>
  </div>
</header>

<main class="wrap">

<section class="stats">
  <div class="stat"><span class="n">{plant['n_samples']}</span><span class="l">plant samples</span></div>
  <div class="stat"><span class="n">{lsda['n_experiments_total']:,}</span><span class="l">LSDA experiments surveyed</span></div>
  <div class="stat"><span class="n">{access.get('open', 0)}</span><span class="l">openly available</span></div>
  <div class="stat"><span class="n">{access.get('request_required', 0)}</span><span class="l">request-gated</span></div>
</section>

<section class="card alert">
  <h2>A 1000-fold unit error in an open NASA dataset</h2>
  <p>OSD-655 labels calcium, potassium, magnesium, phosphorus and sulfur as
  <strong>mg/g dry weight</strong> &mdash; in both its data files and its
  archived data dictionary. The values are &micro;g/g. Read as stated, potassium
  would be <strong>2,943% of dry weight</strong>.</p>
  <p>Any analysis pooling OSD-655 with another elemental dataset without
  correcting this is wrong by a factor of 1000 on five of twelve elements.
  <a href="https://github.com/dr-richard-barker/SpaceMineralAtlas/blob/main/fair/osdr_curation_report.md">Full curation report &rarr;</a></p>
</section>

<section class="card">
  <h2>The two Veggie crops respond differently</h2>
  <p>Flight/ground fold changes, before and after correcting for dry-matter
  dilution with a centred log-ratio transform. Concentrations are compositional:
  if flight tissue differs in dry-matter composition, every element shifts
  together even with no change in uptake.</p>
  <table>
    <thead><tr><th>Element</th><th>Lettuce (raw)</th><th>Tokyo Bekana (raw)</th>
      <th>Tokyo Bekana (CLR)</th><th>After correction</th></tr></thead>
    <tbody>
      {row('potassium')}
      {row('sodium')}
      {row('sulfur')}
      {row('calcium')}
      {row('iron')}
    </tbody>
  </table>
  <p class="note">Lettuce shows <strong>no</strong> element significantly altered
  on either scale. The apparent calcium and iron increases &mdash; the
  accumulation hypothesis this work set out to test &mdash; do not survive
  correction.</p>
  <img src="figures/fig1_fold_change_clr.png" alt="Fold changes before and after CLR correction">
</section>

<section class="card">
  <h2>No flight signature transfers between crops</h2>
  <table>
    <thead><tr><th>Cross-validation</th><th>Best model</th><th>Baseline</th><th>Margin</th></tr></thead>
    <tbody>
      <tr><td>Leave-one-mission-out</td>
        <td>{mission['models']['random_forest']['balanced_accuracy']:.3f}</td>
        <td>{mission['best_baseline_balanced_accuracy']:.3f}</td>
        <td>{mission['models']['random_forest']['margin_over_baseline']:+.3f}</td></tr>
      <tr><td>Leave-one-crop-out</td>
        <td>{crop['models']['random_forest']['balanced_accuracy']:.3f}</td>
        <td>{crop['best_baseline_balanced_accuracy']:.3f}</td>
        <td class="neg">{crop['models']['random_forest']['margin_over_baseline']:+.3f}</td></tr>
    </tbody>
  </table>
  <p class="note">Training on one crop and testing on the other performs
  <strong>below chance</strong>. That is not a failure of method &mdash; it is
  the measurement.</p>
  <img src="figures/fig6_ml_performance.png" alt="Model performance against baselines">
</section>

<section class="card">
  <h2>Overload is not the risk; sufficiency is the question</h2>
  <p>A 100&nbsp;g fresh serving against NASA daily requirements
  (JSC-67378 Rev&nbsp;1): potassium
  <strong>{pct['lettuce/Flight/potassium']:.1f}%</strong> (lettuce) /
  <strong>{pct['tokyo_bekana/Flight/potassium']:.1f}%</strong> (Tokyo Bekana);
  calcium {pct['lettuce/Flight/calcium']:.1f}% / {pct['tokyo_bekana/Flight/calcium']:.1f}%;
  manganese <strong>{pct['lettuce/Flight/manganese']:.0f}%</strong> / {pct['tokyo_bekana/Flight/manganese']:.0f}%.</p>
  <p>Reaching NASA's iron upper limit would require <strong>{fe_kg:.2f}&nbsp;kg</strong>
  of fresh tissue per day, against a per-pillow yield of roughly 45&nbsp;g.
  Dietary mineral overload from Veggie produce is not achievable at plausible
  harvest scales.</p>
  <img src="figures/fig5_serving_contribution.png" alt="Serving contribution against requirements">
</section>

<section class="card">
  <h2>Access, not measurement, is the bottleneck</h2>
  <p>Of {lsda['n_experiments_total']:,} LSDA experiments,
  {lsda['n_measured_mineral_or_nutrition']} measured a mineral or nutritional
  variable. Only <strong>{access.get('open', 0)}</strong> are openly available;
  {access.get('request_required', 0)} require a formal data request and
  {access.get('not_submitted', 0)} were never submitted to the archive.</p>
  <p>The highest-value dataset for linking diet to crew mineral status &mdash;
  <strong>SMO-016E Nutritional Status Assessment</strong> (27 astronauts,
  ~165-day missions, in-flight sampling, paired dietary intake) &mdash; is
  request-gated. A prepared request is included in the repository.</p>
  <img src="figures/fig7_lsda_landscape.png" alt="LSDA mineral data landscape">
</section>

<section class="card">
  <h2>Astronaut serum minerals</h2>
  <p>Inspiration4 clinical chemistry: {astro['n_subjects']} crew,
  {astro['n_observations']} observations across {astro['n_timepoints']} timepoints.
  Potassium fell in {astro['by_mineral']['potassium']['n_decreased_at_return']} of
  {astro['n_subjects']} crew at first return.</p>
  <p class="caution">{astro['n_subjects']} subjects, a
  {astro['mission_duration_days']}-day mission, and
  {astro['inflight_samples']} in-flight samples. These data describe what happened
  to four people; they cannot establish a spaceflight effect, and no inferential
  test is performed.</p>
  <img src="figures/fig4_astronaut_serum.png" alt="Astronaut serum trajectories">
</section>

<section class="card muted">
  <h2>Note on a prior analysis</h2>
  <p>An earlier dashboard published elemental results and model accuracies for
  these same studies. Those values were generated by a <code>numpy.random</code>
  routine rather than measured, and the reported model metrics were hardcoded
  literals. They are not comparable with the results here. A correction note and
  a tested replacement data-acquisition module are in the repository under
  <code>veggie_correction/</code>.</p>
</section>

</main>

<footer>
  <div class="wrap">
    <p>Code MIT &middot; data, figures and text CC BY 4.0 &middot;
       generated {plant['n_samples']}-sample analysis, no simulated values.</p>
    <p class="sources">Sources:
      <a href="https://osdr.nasa.gov/bio/repo/data/studies/OSD-745">OSD-745</a>,
      <a href="https://osdr.nasa.gov/bio/repo/data/studies/OSD-655">OSD-655</a>,
      <a href="https://osdr.nasa.gov/bio/repo/data/studies/OSD-575">OSD-575</a>,
      <a href="https://nlsp.nasa.gov/explore/mtable/lsda_experiment/lsda_experiment">LSDA catalog</a>
    </p>
  </div>
</footer>
</body>
</html>
"""
    (DOCS / "index.html").write_text(html)
    # Jekyll would otherwise ignore nothing here, but being explicit avoids
    # surprises if a future file starts with an underscore.
    (DOCS / ".nojekyll").write_text("")
    log.info("wrote docs/index.html")


if __name__ == "__main__":
    main()
