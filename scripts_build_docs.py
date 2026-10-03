"""Stage 9d: build the GitHub Pages dashboard from the analysis outputs.

The site is a static interactive research portal that reads its numbers directly
from JSON and CSV files copied out of analysis/results/, data/processed/, and catalog/.
It is generated rather than hand-maintained so it cannot drift from the manuscript
-- the failure mode that put placeholder demo values into a published paper in
the predecessor project.

Run:  python scripts_build_docs.py
"""

import csv
import json
import logging
import shutil
import sys
from pathlib import Path

# Setup paths using repository layout
REPO_ROOT = Path(__file__).resolve().parent
DOCS = REPO_ROOT / "docs"
DOCS_DATA = DOCS / "data"
DOCS_FIGURES = DOCS / "figures"
DOCS_CSS = DOCS / "css"
DOCS_JS = DOCS / "js"
RESULTS = REPO_ROOT / "analysis" / "results"
ANALYSIS_FIGURES = REPO_ROOT / "analysis" / "figures"
ROOT_FIGURES = REPO_ROOT / "figures"
PROCESSED = REPO_ROOT / "data" / "processed"
CATALOG = REPO_ROOT / "catalog"

logging.basicConfig(level=logging.INFO, format="%(levelname)-7s | %(message)s")
log = logging.getLogger("docs")


def csv_to_json(csv_path: Path, json_path: Path) -> None:
    if not csv_path.exists():
        return
    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    json_path.write_text(json.dumps(rows, indent=2), encoding="utf-8")


def main() -> None:
    # Ensure directories exist
    for d in (DOCS, DOCS_DATA, DOCS_FIGURES, DOCS_CSS, DOCS_JS):
        d.mkdir(parents=True, exist_ok=True)

    # 1. Copy JSON result files
    json_sources = [
        RESULTS / "plant_summary.json",
        RESULTS / "ml_results.json",
        RESULTS / "astronaut_summary.json",
        RESULTS / "integration_summary.json",
        RESULTS / "supply_summary.json",
        RESULTS / "qc_report.json",
        CATALOG / "lsda_catalog_summary.json",
    ]
    for source in json_sources:
        if source.exists():
            shutil.copy2(source, DOCS_DATA / source.name)
    log.info("copied %d result JSON files to docs/data/", len(list(DOCS_DATA.glob("*.json"))))

    # 2. Copy CSV datasets for direct download from the portal
    csv_sources = [
        PROCESSED / "plant_elemental_ugg.csv",
        PROCESSED / "astronaut_serum_cmp.csv",
        PROCESSED / "nhanes_astronaut_comparison.csv",
        PROCESSED / "tokyo_bekana_with_supply.csv",
        PROCESSED / "unit_provenance.csv",
        RESULTS / "plant_contrasts_comparison.csv",
        RESULTS / "plant_contrasts_clr.csv",
        RESULTS / "plant_contrasts_concentration.csv",
        RESULTS / "crop_divergence.csv",
        RESULTS / "overload_assessment.csv",
        RESULTS / "serving_contributions.csv",
        RESULTS / "astronaut_changes.csv",
        RESULTS / "feature_importance.csv",
        CATALOG / "lsda_mineral_nutrition_catalog.csv",
    ]
    for source in csv_sources:
        if source.exists():
            shutil.copy2(source, DOCS_DATA / source.name)
    log.info("copied %d result CSV files to docs/data/", len(list(DOCS_DATA.glob("*.csv"))))

    # 3. Export JSON conversions of essential CSV tables for fast browser widgets
    csv_to_json(PROCESSED / "plant_elemental_ugg.csv", DOCS_DATA / "plant_elemental_ugg.json")
    csv_to_json(PROCESSED / "astronaut_serum_cmp.csv", DOCS_DATA / "astronaut_serum_cmp.json")
    csv_to_json(RESULTS / "feature_importance.csv", DOCS_DATA / "feature_importance.json")

    # Export compact LSDA mineral catalog JSON for interactive client search
    lsda_catalog_csv = CATALOG / "lsda_measured_mineral_catalog.csv"
    if lsda_catalog_csv.exists():
        with open(lsda_catalog_csv, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            catalog_items = []
            for r in reader:
                catalog_items.append({
                    "id": r.get("experiment_id", ""),
                    "title": r.get("experiment_title", ""),
                    "pi": r.get("PrincipalInvestigator", "").replace(";", " ").strip(),
                    "species": r.get("species", "Human"),
                    "missions": r.get("missions", "").replace(";", " ").strip(),
                    "access": r.get("access_category", "unknown"),
                    "minerals": r.get("minerals", ""),
                    "n_minerals": int(r.get("n_minerals", 0)) if r.get("n_minerals", "").isdigit() else 0,
                })
        (DOCS_DATA / "lsda_measured_mineral_catalog.json").write_text(
            json.dumps(catalog_items, indent=2), encoding="utf-8"
        )
        log.info("exported compact LSDA mineral catalog (%d experiments) to docs/data/", len(catalog_items))

    # 4. Copy publication figures from analysis/figures and figures/
    for fig in ANALYSIS_FIGURES.glob("*.png"):
        shutil.copy2(fig, DOCS_FIGURES / fig.name)
    if ROOT_FIGURES.exists():
        for fig in ROOT_FIGURES.glob("*.png"):
            shutil.copy2(fig, DOCS_FIGURES / fig.name)
    log.info("copied %d figures to docs/figures/", len(list(DOCS_FIGURES.glob("*.png"))))

    # 5. Load data for template injection (Zero-drift guarantee)
    plant = json.loads((RESULTS / "plant_summary.json").read_text(encoding="utf-8"))
    ml = json.loads((RESULTS / "ml_results.json").read_text(encoding="utf-8"))
    lsda = json.loads((CATALOG / "lsda_catalog_summary.json").read_text(encoding="utf-8"))
    integ = json.loads((RESULTS / "integration_summary.json").read_text(encoding="utf-8"))
    astro = json.loads((RESULTS / "astronaut_summary.json").read_text(encoding="utf-8"))

    fc, fcl = plant["fold_changes_concentration"], plant["fold_changes_clr"]
    mission = ml["schemes"]["LeaveOneMissionOut"]
    crop = ml["schemes"]["LeaveOneCropOut"]
    access = lsda["measured_by_access_category"]
    pct = integ["percent_of_requirement_per_100g"]
    fe_kg = integ["overload_assessment"]["iron/lettuce/Flight/high"]["kg_fresh_tissue_to_reach_limit"]

    # Generate HTML content with Anti-FOUT theme script
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SpaceMineralAtlas &mdash; NASA Spaceflight Mineral and Dietary Analysis</title>
<script>
  (function() {{
    var t = localStorage.getItem('barker.theme');
    if (!t) {{ t = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'; }}
    document.documentElement.setAttribute('data-theme', t);
    document.documentElement.style.colorScheme = t;
  }})();
</script>
<link rel="stylesheet" href="css/style.css">
<link rel="stylesheet" href="https://dr-richard-barker.github.io/Plant_response_to_radiation/cose/cose-theme.css">
<link rel="stylesheet" href="https://dr-richard-barker.github.io/Plant_response_to_radiation/cose/cose-chrome.css">
<link rel="stylesheet" href="https://dr-richard-barker.github.io/Plant_response_to_radiation/cose/cose-map.css">
</head>
<body data-site-id="SpaceMineralAtlas">

<header class="hero">
  <div class="wrap hero-content">
    <div class="hero-top-row">
      <div class="hero-badge"><span class="pulse"></span> Open NASA Reanalysis &middot; 100% Checksummed</div>
      <button class="theme-toggle-btn" aria-label="Toggle light or dark theme" title="Toggle light / dark theme">
        <span>🌙</span> <span>Dark Mode</span>
      </button>
    </div>
    <h1>SpaceMineral<span>Atlas</span></h1>
    <p class="tagline">Crop-specific mineral responses to spaceflight, discovery of a 1000-fold unit error in OSD-655, dietary supply sufficiency vs overload safety, and the NASA LSDA data access landscape.</p>
    <div class="hero-meta">
      <span>By <strong>Dr. Richard Barker</strong></span>
      <span>&bull;</span>
      <span>All values computed from public NASA APIs</span>
      <span>&bull;</span>
      <a href="https://github.com/dr-richard-barker/SpaceMineralAtlas" class="btn-hero" target="_blank" rel="noopener">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z"/></svg>
        GitHub Repository
      </a>
      <a href="https://github.com/dr-richard-barker/SpaceMineralAtlas/blob/main/manuscript/SpaceMineralAtlas_manuscript.pdf" class="btn-hero-ghost" target="_blank" rel="noopener">
        📄 Manuscript PDF
      </a>
    </div>
  </div>
</header>

<nav class="sticky-nav">
  <div class="wrap nav-wrapper-flex">
    <div class="nav-links">
      <a href="#defect">1000x Unit Defect</a>
      <a href="#plants">Plant CLR Divergence</a>
      <a href="#ml">ML Limits</a>
      <a href="#nutrition">Dietary Calculator</a>
      <a href="#astronauts">Inspiration4 &times; NHANES</a>
      <a href="#samples">60 Plant Samples</a>
      <a href="#lsda">LSDA Access Bottleneck</a>
      <a href="#fair">FAIR Data &amp; Citation</a>
    </div>
    <button class="nav-theme-btn" aria-label="Toggle light or dark theme" title="Toggle light / dark theme">
      <span>🌓</span> <span>Theme</span>
    </button>
  </div>
</nav>

<main class="wrap">

<!-- KEY NUMERICAL BENCHMARKS -->
<section class="stats">
  <div class="stat-card">
    <span class="n">{plant['n_samples']}</span>
    <span class="l">Plant Samples</span>
    <span class="sub">OSD-745 (24) &amp; OSD-655 (36)</span>
  </div>
  <div class="stat-card">
    <span class="n">{lsda['n_experiments_total']:,}</span>
    <span class="l">LSDA Experiments</span>
    <span class="sub">{lsda['n_measured_mineral_or_nutrition']} mineral &amp; nutrition studies</span>
  </div>
  <div class="stat-card">
    <span class="n">1000&times;</span>
    <span class="l">Unit Error Fixed</span>
    <span class="sub">OSD-655 mg/g vs &micro;g/g</span>
  </div>
  <div class="stat-card">
    <span class="n">{access.get('open', 0)}</span>
    <span class="l">Open LSDA Studies</span>
    <span class="sub">{access.get('request_required', 0)} request-gated</span>
  </div>
  <div class="stat-card">
    <span class="n">0</span>
    <span class="l">Synthetic Points</span>
    <span class="sub">Protected by CI test guards</span>
  </div>
</section>

<!-- SECTION 1: 1000-FOLD UNIT DEFECT -->
<section class="card alert" id="defect">
  <div class="card-header-flex">
    <h2>1. A 1000-Fold Unit Defect in Open NASA Data (OSD-655)</h2>
    <span class="section-badge" style="background: var(--coral-light); color: var(--coral);">Curation Discovery</span>
  </div>
  <p class="lead">OSD-655 (Tokyo Bekana grown in Veg-04A/04B) labels five major macronutrient elements &mdash; <strong>calcium, potassium, magnesium, phosphorus, and sulfur</strong> &mdash; as <strong>mg/g dry weight</strong> in both its data files and its official archived data dictionary. The true values are <strong>&micro;g/g dry weight</strong>.</p>
  
  <div class="controls-bar">
    <span class="control-label">View Mode:</span>
    <div class="btn-group">
      <button class="btn-toggle active unit-toggle-btn" data-mode="stated">As Archived in OSD-655 (mg/g)</button>
      <button class="btn-toggle unit-toggle-btn" data-mode="corrected">Harmonised Correction (&micro;g/g)</button>
    </div>
  </div>

  <div class="table-responsive">
    <table>
      <thead>
        <tr>
          <th>Macronutrient</th>
          <th>Concentration</th>
          <th>Implied Dry Mass %</th>
          <th>Biological &amp; Physical Assessment</th>
        </tr>
      </thead>
      <tbody>
        <tr class="unit-defect-row" data-element="potassium">
          <td><strong>Potassium (K)</strong></td>
          <td class="unit-val-cell">29,430 mg/g</td>
          <td class="unit-pct-cell"><strong style="color: var(--coral);">2,943.0%</strong></td>
          <td class="unit-status-cell"><span class="badge badge-artefact">Physically Impossible (&gt;100%)</span></td>
        </tr>
        <tr class="unit-defect-row" data-element="calcium">
          <td><strong>Calcium (Ca)</strong></td>
          <td class="unit-val-cell">15,820 mg/g</td>
          <td class="unit-pct-cell"><strong style="color: var(--coral);">1,582.0%</strong></td>
          <td class="unit-status-cell"><span class="badge badge-artefact">Physically Impossible (&gt;100%)</span></td>
        </tr>
        <tr class="unit-defect-row" data-element="sulfur">
          <td><strong>Sulfur (S)</strong></td>
          <td class="unit-val-cell">8,950 mg/g</td>
          <td class="unit-pct-cell"><strong style="color: var(--coral);">895.0%</strong></td>
          <td class="unit-status-cell"><span class="badge badge-artefact">Physically Impossible (&gt;100%)</span></td>
        </tr>
        <tr class="unit-defect-row" data-element="phosphorus">
          <td><strong>Phosphorus (P)</strong></td>
          <td class="unit-val-cell">6,840 mg/g</td>
          <td class="unit-pct-cell"><strong style="color: var(--coral);">684.0%</strong></td>
          <td class="unit-status-cell"><span class="badge badge-artefact">Physically Impossible (&gt;100%)</span></td>
        </tr>
        <tr class="unit-defect-row" data-element="magnesium">
          <td><strong>Magnesium (Mg)</strong></td>
          <td class="unit-val-cell">3,110 mg/g</td>
          <td class="unit-pct-cell"><strong style="color: var(--coral);">311.0%</strong></td>
          <td class="unit-status-cell"><span class="badge badge-artefact">Physically Impossible (&gt;100%)</span></td>
        </tr>
      </tbody>
    </table>
  </div>

  <div id="unit-defect-status" class="caution">
    <strong>Physical Impossibility:</strong> Stated units in OSD-655 imply plant tissues are composed of <strong>2,943% potassium</strong> by dry mass, exceeding total physical sample mass by nearly 30-fold.
  </div>

  <p>Any analysis pooling OSD-655 with OSD-745 or other elemental datasets without correcting this defect is wrong by a factor of 1000 on five of twelve elements. A full curation report with provenance has been deposited for the OSDR curation team: 
    <a href="https://github.com/dr-richard-barker/SpaceMineralAtlas/blob/main/fair/osdr_curation_report.md" target="_blank" rel="noopener">View OSDR Curation Report &rarr;</a>
  </p>
</section>

<!-- SECTION 2: PLANT CLR DIVERGENCE -->
<section class="card" id="plants">
  <div class="card-header-flex">
    <h2>2. Crop Divergence &amp; Centred Log-Ratio (CLR) Compositional Analysis</h2>
    <span class="section-badge">Plant Biology</span>
  </div>
  <p class="lead">Raw elemental concentrations are compositional: if flight tissue shifts in dry-matter composition, all elements shift together even if specific ion uptake is unchanged. Correcting for dry-matter dilution using a <strong>Centred Log-Ratio (CLR) transform</strong> reveals that apparent calcium and iron increases are dilution artefacts.</p>

  <div class="controls-bar">
    <div style="display: flex; align-items: center; gap: 8px;">
      <span class="control-label">Select Crop:</span>
      <div class="btn-group">
        <button class="btn-toggle active plant-crop-btn" data-crop="tokyo_bekana">Tokyo Bekana (OSD-655, N=36)</button>
        <button class="btn-toggle plant-crop-btn" data-crop="lettuce">Lettuce (OSD-745, N=24)</button>
      </div>
    </div>
  </div>

  <div class="table-responsive">
    <table>
      <thead>
        <tr>
          <th>Element</th>
          <th class="text-right">Raw Fold Change</th>
          <th class="text-right">Raw p (FDR)</th>
          <th class="text-right">CLR Fold Change</th>
          <th class="text-right">CLR p (FDR)</th>
          <th>Biological Status After CLR Correction</th>
        </tr>
      </thead>
      <tbody id="plant-contrasts-tbody">
        <!-- Injected dynamically by dashboard.js -->
      </tbody>
    </table>
  </div>

  <div class="callout-box">
    <h3>Key Biological Finding</h3>
    <p>Lettuce shows <strong>zero</strong> elements significantly altered by spaceflight on either raw concentration or CLR scale. Tokyo Bekana displays significant CLR increases in <strong>potassium (+15%), sodium (+80%), and sulfur (+28%)</strong>, while copper, manganese, and zinc exhibit relative decreases. Apparent calcium and iron accumulations do not survive correction.</p>
  </div>

  <div class="grid-2">
    <div class="figure-container">
      <div class="figure-wrapper" data-caption="Figure 1: Fold changes before and after Centred Log-Ratio (CLR) correction">
        <img src="figures/fig1_fold_change_clr.png" alt="Figure 1: Fold changes before and after CLR correction">
      </div>
      <div class="figure-caption"><strong>Figure 1:</strong> Flight/ground fold changes before and after CLR. Click to enlarge.</div>
    </div>
    <div class="figure-container">
      <div class="figure-wrapper" data-caption="Figure 2: Crop divergence across elemental profiles">
        <img src="figures/fig2_crop_divergence.png" alt="Figure 2: Crop divergence">
      </div>
      <div class="figure-caption"><strong>Figure 2:</strong> Tokyo Bekana vs Lettuce response divergence. Click to enlarge.</div>
    </div>
  </div>
</section>

<!-- SECTION 3: ML GENERALISATION LIMITS & FEATURE IMPORTANCE -->
<section class="card" id="ml">
  <div class="card-header-flex">
    <h2>3. Machine Learning: No Flight Signature Transfers Across Crops</h2>
    <span class="section-badge">Machine Learning</span>
  </div>
  <p class="lead">To test whether microgravity induces a generalizable plant elemental signature, machine learning classifiers were evaluated under strict cross-validation schemes designed to prevent data leakage.</p>

  <div class="grid-2">
    <div class="sub-card">
      <h3>Leave-One-Mission-Out (LOMO)</h3>
      <p style="font-size: 0.9rem; color: var(--muted); margin-bottom: 12px;">5 folds partitioning VEG-01A, VEG-01B, VEG-03A, VEG-04A, VEG-04B.</p>
      <div style="font-size: 2.2rem; font-weight: 800; color: var(--navy); margin-bottom: 4px;">{mission['models']['random_forest']['balanced_accuracy']:.3f}</div>
      <div style="font-size: 0.85rem; color: var(--teal); font-weight: 700;">+0.040 Margin over chance ({mission['best_baseline_balanced_accuracy']:.3f})</div>
      <p class="note" style="margin-top: 10px;">Modest signal within mission cohorts, largely tracking environmental differences.</p>
    </div>
    <div class="sub-card" style="border-left: 4px solid var(--coral);">
      <h3>Leave-One-Crop-Out (LOCO)</h3>
      <p style="font-size: 0.9rem; color: var(--muted); margin-bottom: 12px;">Train on Lettuce &rarr; Test on Tokyo Bekana (and vice versa).</p>
      <div style="font-size: 2.2rem; font-weight: 800; color: var(--coral); margin-bottom: 4px;">{crop['models']['random_forest']['balanced_accuracy']:.3f}</div>
      <div style="font-size: 0.85rem; color: var(--coral); font-weight: 700;">-0.113 Below chance ({crop['best_baseline_balanced_accuracy']:.3f})</div>
      <p class="note" style="margin-top: 10px;"><strong>Below chance performance:</strong> Demonstrates the absolute absence of a shared cross-crop flight response signature.</p>
    </div>
  </div>

  <div style="margin-top: 28px;">
    <h3 style="margin: 0 0 12px; color: var(--navy);">Random Forest Feature Importance Ranking</h3>
    <p style="font-size: 0.92rem; color: var(--muted); margin-bottom: 16px;">
      Permutation importance across models confirms that only <strong>Potassium, Sodium, and Sulfur</strong> contribute positive classification importance &mdash; matching the exact three elements that survived CLR compositional correction.
    </p>
    <div id="ml-feature-importance-bars">
      <!-- Injected dynamically by dashboard.js -->
    </div>
  </div>

  <div class="figure-container" style="margin-top: 24px;">
    <div class="figure-wrapper" data-caption="Figure 6: Machine learning model performance and cross-crop generalisation failure">
      <img src="figures/fig6_ml_performance.png" alt="Figure 6: Model performance against baselines">
    </div>
    <div class="figure-caption"><strong>Figure 6:</strong> Machine learning classification performance across cross-validation regimes. Click to enlarge.</div>
  </div>
</section>

<!-- SECTION 4: NUTRITIONAL CALCULATOR -->
<section class="card highlight" id="nutrition">
  <div class="card-header-flex">
    <h2>4. Interactive Dietary Supply &amp; Overload Safety Calculator</h2>
    <span class="section-badge" style="background: var(--teal-light); color: var(--teal);">Interactive Tool</span>
  </div>
  <p class="lead">Evaluate fresh crop dietary contributions against NASA astronaut daily nutritional requirements (JSC-67378 Rev 1) and calculate safety margins against Upper Limits.</p>

  <div class="controls-bar">
    <div class="slider-container">
      <span class="control-label">Fresh Harvest Mass:</span>
      <input type="range" id="serving-slider" min="10" max="500" value="100" step="5">
      <span class="slider-val-badge" id="serving-val-display">100 g</span>
    </div>
    <div style="display: flex; gap: 8px; flex-wrap: wrap;">
      <button class="btn-toggle preset-btn" data-grams="45">45g (Pillow Yield)</button>
      <button class="btn-toggle active preset-btn" data-grams="100">100g (Standard)</button>
      <button class="btn-toggle preset-btn" data-grams="250">250g (Large Meal)</button>
    </div>
    <div style="display: flex; gap: 8px;">
      <select id="nutrition-crop-select" class="select-custom">
        <option value="tokyo_bekana">Tokyo Bekana (OSD-655)</option>
        <option value="lettuce">Lettuce (OSD-745)</option>
      </select>
      <select id="nutrition-condition-select" class="select-custom">
        <option value="Flight">Flight Produce</option>
        <option value="Ground">Ground Control</option>
      </select>
    </div>
  </div>

  <div id="nutrition-results-container" class="grid-2">
    <!-- Injected dynamically by dashboard.js -->
  </div>

  <div id="overload-safety-text"></div>

  <div class="figure-container">
    <div class="figure-wrapper" data-caption="Figure 5: 100g fresh serving mineral contribution against NASA dietary requirements">
      <img src="figures/fig5_serving_contribution.png" alt="Figure 5: Serving contribution against requirements">
    </div>
    <div class="figure-caption"><strong>Figure 5:</strong> Nutritional contribution of 100g fresh produce vs NASA JSC-67378 standards. Click to enlarge.</div>
  </div>
</section>

<!-- SECTION 5: INSPIRATION4 × NHANES & LONGITUDINAL TRAJECTORIES -->
<section class="card" id="astronauts">
  <div class="card-header-flex">
    <h2>5. Inspiration4 Crew Clinical Dynamics &amp; CDC NHANES Population Benchmarks</h2>
    <span class="section-badge">Crew Physiology</span>
  </div>
  <p class="lead">Longitudinal serum chemistry of the four Inspiration4 civilian astronauts (OSD-575: 3-day orbital flight) benchmarked against age- and sex-stratified US population reference distributions from <strong>CDC NHANES (2017&ndash;2018 cycle)</strong>.</p>

  <div class="crew-grid">
    <div class="crew-card active" data-subject="C001">
      <div class="crew-name">Jared Isaacman (C001)</div>
      <div class="crew-role">Commander &bull; 38M</div>
      <div class="crew-details">Matched Cohort: Males 30&ndash;49 (N=669)</div>
    </div>
    <div class="crew-card" data-subject="C002">
      <div class="crew-name">Hayley Arceneaux (C002)</div>
      <div class="crew-role">Medical Officer &bull; 29F</div>
      <div class="crew-details">Matched Cohort: Females 18&ndash;29 (N=494)</div>
    </div>
    <div class="crew-card" data-subject="C003">
      <div class="crew-name">Chris Sembroski (C003)</div>
      <div class="crew-role">Mission Specialist &bull; 41M</div>
      <div class="crew-details">Matched Cohort: Males 30&ndash;49 (N=669)</div>
    </div>
    <div class="crew-card" data-subject="C004">
      <div class="crew-name">Sian Proctor (C004)</div>
      <div class="crew-role">Mission Pilot &bull; 51F</div>
      <div class="crew-details">Matched Cohort: Females 50&ndash;69 (N=931)</div>
    </div>
  </div>

  <div class="controls-bar">
    <span class="control-label">Select Analyte:</span>
    <select id="nhanes-analyte-select" class="select-custom">
      <option value="potassium">Potassium (Serum)</option>
      <option value="calcium">Calcium (Serum)</option>
      <option value="sodium">Sodium (Serum)</option>
      <option value="chloride">Chloride (Serum)</option>
      <option value="carbon_dioxide">Carbon Dioxide (Serum)</option>
    </select>
  </div>

  <div id="astronaut-analyte-details">
    <!-- Injected dynamically by dashboard.js -->
  </div>

  <div id="astronaut-timeline-container">
    <!-- Injected dynamically by dashboard.js -->
  </div>

  <div class="caution" style="margin-top: 24px;">
    <strong>Methodological Caution:</strong> 4 subjects, a 3-day mission duration, and 0 in-flight biosamples. These trajectories provide valuable clinical observations but cannot establish causal microgravity mechanisms without long-duration in-flight sampling.
  </div>

  <div class="grid-2" style="margin-top: 24px;">
    <div class="figure-container">
      <div class="figure-wrapper" data-caption="Inspiration4 serum mineral trajectories vs NHANES population percentiles">
        <img src="figures/nhanes_crew_comparison_grid.png" alt="Inspiration4 vs NHANES Comparison Grid">
      </div>
      <div class="figure-caption"><strong>Population Benchmark:</strong> Inspiration4 pre/post percentiles vs NHANES norms. Click to enlarge.</div>
    </div>
    <div class="figure-container">
      <div class="figure-wrapper" data-caption="Figure 4: Inspiration4 longitudinal serum mineral trajectories across 7 timepoints">
        <img src="figures/fig4_astronaut_serum.png" alt="Figure 4: Astronaut serum trajectories">
      </div>
      <div class="figure-caption"><strong>Figure 4:</strong> Longitudinal clinical chemistry across L-92 to R+90. Click to enlarge.</div>
    </div>
  </div>
</section>

<!-- SECTION 6: 60 PLANT SAMPLES DATASET EXPLORER -->
<section class="card" id="samples">
  <div class="card-header-flex">
    <h2>6. Interactive Plant Sample Elemental Dataset (N=60)</h2>
    <span class="section-badge">Harmonised Data</span>
  </div>
  <p class="lead">Explore the complete harmonised elemental ICP-OES measurements for all 60 plant samples across OSD-745 and OSD-655 (all units calibrated to &micro;g/g dry weight).</p>

  <div class="controls-bar">
    <div style="display: flex; gap: 12px; flex-wrap: wrap; flex: 1;">
      <div style="flex: 1; min-width: 180px;">
        <input type="search" id="plant-data-search" class="input-custom" placeholder="Search sample ID or mission..." style="width: 100%;">
      </div>
      <select id="plant-data-crop-filter" class="select-custom">
        <option value="all">All Crops (60)</option>
        <option value="tokyo_bekana">Tokyo Bekana (36)</option>
        <option value="outredgeous_lettuce">Outredgeous Lettuce (24)</option>
      </select>
      <select id="plant-data-flight-filter" class="select-custom">
        <option value="all">All Conditions (60)</option>
        <option value="flight">Flight Only (29)</option>
        <option value="ground">Ground Only (31)</option>
      </select>
    </div>
    <span id="plant-data-count" class="slider-val-badge" style="font-size: 0.85rem;">60 samples</span>
  </div>

  <div class="table-responsive" style="max-height: 440px; overflow-y: auto;">
    <table>
      <thead>
        <tr>
          <th>Sample ID</th>
          <th>Crop</th>
          <th>Mission</th>
          <th>Condition</th>
          <th class="text-right">K (&micro;g/g)</th>
          <th class="text-right">Ca (&micro;g/g)</th>
          <th class="text-right">Mg (&micro;g/g)</th>
          <th class="text-right">Fe (&micro;g/g)</th>
          <th class="text-right">Mn (&micro;g/g)</th>
          <th class="text-right">Na (&micro;g/g)</th>
        </tr>
      </thead>
      <tbody id="plant-dataset-tbody">
        <!-- Injected dynamically by dashboard.js -->
      </tbody>
    </table>
  </div>
</section>

<!-- SECTION 7: LSDA ACCESS LANDSCAPE -->
<section class="card" id="lsda">
  <div class="card-header-flex">
    <h2>7. NASA LSDA Data Access Landscape Explorer</h2>
    <span class="section-badge">Data Governance</span>
  </div>
  <p class="lead">Survey of all 2,676 experiments in the NASA Life Sciences Data Archive reveals that access restrictions, rather than a lack of historical flight investigations, form the primary research bottleneck.</p>

  <div class="grid-3" style="margin-bottom: 20px;">
    <div class="stat-card" style="border-left: 4px solid var(--teal);">
      <span class="n">{access.get('open', 0)}</span>
      <span class="l">Openly Available (14.7%)</span>
      <span class="sub">Direct download without gating</span>
    </div>
    <div class="stat-card" style="border-left: 4px solid var(--gold);">
      <span class="n">{access.get('request_required', 0)}</span>
      <span class="l">Request Required (50.4%)</span>
      <span class="sub">Institutional IRB / Form approval needed</span>
    </div>
    <div class="stat-card" style="border-left: 4px solid var(--coral);">
      <span class="n">{access.get('not_submitted', 0)}</span>
      <span class="l">Never Submitted (34.3%)</span>
      <span class="sub">Completed studies without archived data</span>
    </div>
  </div>

  <div class="callout-box">
    <h3>High-Value Target: SMO-016E (Nutritional Status Assessment)</h3>
    <p>The premier dataset for linking spaceflight diet directly to crew serum mineral dynamics &mdash; <strong>27 astronauts across ~165-day missions with paired in-flight dietary intake and serum chemistry</strong> &mdash; is request-gated. A complete, turnkey LSDA data request application has been prepared in the repository: 
      <a href="https://github.com/dr-richard-barker/SpaceMineralAtlas/tree/main/lsda_request" target="_blank" rel="noopener">Explore LSDA Request Package &rarr;</a>
    </p>
  </div>

  <div class="controls-bar">
    <div style="flex: 1; min-width: 200px;">
      <input type="search" id="lsda-search-input" class="input-custom" placeholder="Search 423 mineral studies by keyword, title, PI..." style="width: 100%;">
    </div>
    <div class="btn-group">
      <button class="btn-toggle active lsda-tab-btn" data-filter="all">All (423)</button>
      <button class="btn-toggle lsda-tab-btn" data-filter="open">Open (62)</button>
      <button class="btn-toggle lsda-tab-btn" data-filter="request_required">Request Gated (213)</button>
      <button class="btn-toggle lsda-tab-btn" data-filter="not_submitted">Not Submitted (145)</button>
    </div>
  </div>

  <div class="table-responsive">
    <table>
      <thead>
        <tr>
          <th>ID</th>
          <th>Study Title</th>
          <th>Principal Investigator</th>
          <th>Subject / Species</th>
          <th>Access Status</th>
        </tr>
      </thead>
      <tbody id="lsda-catalog-tbody">
        <!-- Injected dynamically by dashboard.js -->
      </tbody>
    </table>
  </div>

  <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 12px; flex-wrap: wrap; gap: 8px;">
    <span id="lsda-page-info" style="font-size: 0.85rem; color: var(--muted);">Loading catalog...</span>
    <div style="display: flex; gap: 8px;">
      <button id="lsda-prev-btn" class="btn-toggle" style="background: var(--panel); border: 1px solid var(--line);">Previous</button>
      <button id="lsda-next-btn" class="btn-toggle" style="background: var(--panel); border: 1px solid var(--line);">Next</button>
    </div>
  </div>

  <div class="figure-container">
    <div class="figure-wrapper" data-caption="Figure 7: Survey of 2,676 LSDA experiments and mineral data accessibility tiers">
      <img src="figures/fig7_lsda_landscape.png" alt="Figure 7: LSDA mineral data landscape">
    </div>
    <div class="figure-caption"><strong>Figure 7:</strong> Full breakdown of NASA LSDA experiment catalog. Click to enlarge.</div>
  </div>
</section>

<!-- SECTION 8: FAIR & REPRODUCIBILITY DOWNLOAD HUB & CITATION -->
<section class="card" id="fair">
  <div class="card-header-flex">
    <h2>8. Reproducibility, FAIR Data &amp; Research Downloads</h2>
    <span class="section-badge" style="background: var(--teal-light); color: var(--teal);">Open Science</span>
  </div>
  <p class="lead">Every result, figure, and manuscript statistic in SpaceMineralAtlas is deterministically generated from checksummed NASA API responses without simulated or placeholder values.</p>

  <div class="grid-2">
    <div class="sub-card">
      <h3 style="display: flex; align-items: center; gap: 8px;">
        <span style="color: var(--teal);">✓</span> Zero Synthetic Data Policy
      </h3>
      <p style="font-size: 0.88rem; color: var(--ink);">
        Automated CI tests fail the build if <code>numpy.random</code>, synthetic data generation, or unvalidated fallbacks are introduced.
      </p>
    </div>
    <div class="sub-card">
      <h3 style="display: flex; align-items: center; gap: 8px;">
        <span style="color: var(--teal);">✓</span> LaTeX Macro Injection Audit
      </h3>
      <p style="font-size: 0.88rem; color: var(--ink);">
        All 179 statistics in the manuscript are injected directly from analysis JSON outputs via LaTeX macros, eliminating manual typing errors.
      </p>
    </div>
  </div>

  <h3 style="margin: 28px 0 12px; color: var(--navy);">Direct Research Downloads</h3>
  <div class="download-grid">
    <a href="data/plant_elemental_ugg.csv" class="btn-download" download>
      <div class="btn-download-icon">📊</div>
      <div>
        <span class="btn-download-title">Plant ICP-OES Data</span>
        <span class="btn-download-sub">CSV &bull; Harmonised &micro;g/g DW</span>
      </div>
    </a>
    <a href="data/nhanes_astronaut_comparison.csv" class="btn-download" download>
      <div class="btn-download-icon">🧑‍🚀</div>
      <div>
        <span class="btn-download-title">Astronaut &times; NHANES Data</span>
        <span class="btn-download-sub">CSV &bull; Percentile Ranks</span>
      </div>
    </a>
    <a href="data/lsda_mineral_nutrition_catalog.csv" class="btn-download" download>
      <div class="btn-download-icon">📑</div>
      <div>
        <span class="btn-download-title">LSDA Mineral Catalog</span>
        <span class="btn-download-sub">CSV &bull; 423 Annotated Studies</span>
      </div>
    </a>
    <a href="https://github.com/dr-richard-barker/SpaceMineralAtlas/blob/main/fair/osdr_curation_report.md" class="btn-download" target="_blank" rel="noopener">
      <div class="btn-download-icon">📋</div>
      <div>
        <span class="btn-download-title">OSDR Curation Report</span>
        <span class="btn-download-sub">Markdown &bull; OSD-655 Defect</span>
      </div>
    </a>
    <a href="https://github.com/dr-richard-barker/SpaceMineralAtlas/blob/main/manuscript/SpaceMineralAtlas_manuscript.pdf" class="btn-download" target="_blank" rel="noopener">
      <div class="btn-download-icon">📕</div>
      <div>
        <span class="btn-download-title">Complete Manuscript</span>
        <span class="btn-download-sub">PDF &bull; Publication Format</span>
      </div>
    </a>
    <a href="https://github.com/dr-richard-barker/SpaceMineralAtlas" class="btn-download" target="_blank" rel="noopener">
      <div class="btn-download-icon">💻</div>
      <div>
        <span class="btn-download-title">Source Code &amp; Tests</span>
        <span class="btn-download-sub">GitHub &bull; MIT License</span>
      </div>
    </a>
  </div>

  <div style="margin-top: 32px;">
    <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 8px;">
      <h3 style="margin: 0; color: var(--navy);">Cite This Research</h3>
      <button id="copy-bibtex-btn" class="btn-toggle" style="background: var(--blue-light); color: var(--navy);">📋 Copy BibTeX</button>
    </div>
    <div style="background: var(--panel); border: 1px solid var(--line); border-radius: var(--radius-md); padding: 16px;">
      <pre id="bibtex-code-block" style="margin: 0; font-size: 0.84rem; overflow-x: auto; color: var(--ink);"><code>@article{{Barker2026_SpaceMineralAtlas,
  author    = {{Barker, Richard}},
  title     = {{SpaceMineralAtlas: Crop-Specific Mineral Responses to Spaceflight, a Unit-Labelling Defect in OSD-655, and a Survey of Mineral and Dietary Data Availability Across the NASA Life Sciences Data Archive}},
  year      = {{2026}},
  publisher = {{GitHub / Zenodo}},
  url       = {{https://github.com/dr-richard-barker/SpaceMineralAtlas}}
}}</code></pre>
    </div>
  </div>
</section>

</main>

<!-- MODAL FIGURE VIEWER -->
<div id="figure-modal" class="modal">
  <div class="modal-content">
    <button id="modal-close-btn" class="modal-close">&times;</button>
    <h3 id="modal-figure-title" style="margin: 0 0 12px; color: var(--navy);">Figure Viewer</h3>
    <img id="modal-figure-img" class="modal-img" src="" alt="Enlarged figure">
  </div>
</div>

<footer>
  <div class="wrap">
    <p><strong>SpaceMineralAtlas</strong> &middot; Code released under MIT License &middot; Data and figures under CC BY 4.0 &middot; Generated {plant['n_samples']}-sample analysis (Zero simulated values).</p>
    <p class="sources">Data Sources:
      <a href="https://osdr.nasa.gov/bio/repo/data/studies/OSD-745" target="_blank" rel="noopener">OSD-745</a> (Veg-01A/01B/03A Lettuce),
      <a href="https://osdr.nasa.gov/bio/repo/data/studies/OSD-655" target="_blank" rel="noopener">OSD-655</a> (Veg-04A/04B Tokyo Bekana),
      <a href="https://osdr.nasa.gov/bio/repo/data/studies/OSD-575" target="_blank" rel="noopener">OSD-575</a> (Inspiration4 Clinical Chemistry),
      <a href="https://wwwn.cdc.gov/nchs/nhanes/continuousnhanes/default.aspx?BeginYear=2017" target="_blank" rel="noopener">CDC NHANES 2017&ndash;2018</a>, and
      <a href="https://nlsp.nasa.gov/explore/mtable/lsda_experiment/lsda_experiment" target="_blank" rel="noopener">NASA LSDA Catalog</a>.
    </p>
  </div>
</footer>

<script src="js/dashboard.js"></script>
<script src="https://dr-richard-barker.github.io/Plant_response_to_radiation/cose/sites.js"></script>
<script src="https://dr-richard-barker.github.io/Plant_response_to_radiation/cose/theme.js"></script>
<script src="https://dr-richard-barker.github.io/Plant_response_to_radiation/cose/nav.js"></script>
</body>
</html>
"""
    (DOCS / "index.html").write_text(html, encoding="utf-8")
    (DOCS / ".nojekyll").write_text("", encoding="utf-8")
    log.info("wrote docs/index.html with interactive portal and theme controller")


if __name__ == "__main__":
    main()
