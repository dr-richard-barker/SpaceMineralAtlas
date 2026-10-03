/**
 * SpaceMineralAtlas Interactive Dashboard
 * Connects research data to interactive visualizers without external framework dependencies.
 * Fully compatible with Barker Lab COSE design system and theme toggles.
 */

document.addEventListener('DOMContentLoaded', () => {
  initThemeController();
  initUnitDefectVisualizer();
  initPlantClrExplorer();
  initMlFeatureImportance();
  initNutritionCalculator();
  initAstronautNhanesExplorer();
  initAstronautTimeline();
  initPlantDatasetViewer();
  initLsdaCatalogExplorer();
  initCitationCopy();
  initFigureModal();
});

// ============================================================================
// 0. COSE Theme Controller (Light / Dark Mode Switcher)
// ============================================================================
function initThemeController() {
  const themeBtns = document.querySelectorAll('.theme-toggle-btn, .nav-theme-btn');
  const LS_THEME = 'barker.theme';

  function getActiveTheme() {
    const saved = localStorage.getItem(LS_THEME);
    if (saved === 'light' || saved === 'dark') return saved;
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }

  function applyTheme(theme, save = false) {
    document.documentElement.setAttribute('data-theme', theme);
    document.documentElement.style.colorScheme = theme;
    if (save) localStorage.setItem(LS_THEME, theme);

    themeBtns.forEach(btn => {
      const isDark = theme === 'dark';
      const icon = isDark ? '🌙' : '☀️';
      const text = isDark ? 'Dark Mode' : 'Light Mode';
      btn.setAttribute('aria-label', `Switch to ${isDark ? 'light' : 'dark'} mode`);
      btn.setAttribute('title', `Switch to ${isDark ? 'light' : 'dark'} mode`);
      btn.innerHTML = `<span style="font-size: 0.95rem;">${icon}</span> <span>${text}</span>`;
    });
  }

  themeBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const current = document.documentElement.getAttribute('data-theme') || getActiveTheme();
      const next = current === 'dark' ? 'light' : 'dark';
      applyTheme(next, true);
    });
  });

  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', e => {
    if (!localStorage.getItem(LS_THEME)) {
      applyTheme(e.matches ? 'dark' : 'light', false);
    }
  });

  applyTheme(getActiveTheme(), false);
}

// ============================================================================
// 1. OSD-655 1000-Fold Unit Defect Visualizer
// ============================================================================
function initUnitDefectVisualizer() {
  const toggleButtons = document.querySelectorAll('.unit-toggle-btn');
  const tableRows = document.querySelectorAll('.unit-defect-row');
  const alertBanner = document.getElementById('unit-defect-status');

  const defectData = {
    potassium: { stated: "29,430 mg/g", corrected: "29,430 µg/g (29.43 mg/g)", statedPct: "2,943.0%", correctedPct: "2.94%", impossible: true },
    calcium: { stated: "15,820 mg/g", corrected: "15,820 µg/g (15.82 mg/g)", statedPct: "1,582.0%", correctedPct: "1.58%", impossible: true },
    magnesium: { stated: "3,110 mg/g", corrected: "3,110 µg/g (3.11 mg/g)", statedPct: "311.0%", correctedPct: "0.31%", impossible: true },
    phosphorus: { stated: "6,840 mg/g", corrected: "6,840 µg/g (6.84 mg/g)", statedPct: "684.0%", correctedPct: "0.68%", impossible: true },
    sulfur: { stated: "8,950 mg/g", corrected: "8,950 µg/g (8.95 mg/g)", statedPct: "895.0%", correctedPct: "0.90%", impossible: true }
  };

  toggleButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      toggleButtons.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const mode = btn.dataset.mode; // 'stated' or 'corrected'

      tableRows.forEach(row => {
        const elem = row.dataset.element;
        const info = defectData[elem];
        if (!info) return;

        const valCell = row.querySelector('.unit-val-cell');
        const pctCell = row.querySelector('.unit-pct-cell');
        const statusCell = row.querySelector('.unit-status-cell');

        if (mode === 'stated') {
          valCell.textContent = info.stated;
          pctCell.innerHTML = `<strong style="color: var(--coral); font-weight: 800;">${info.statedPct}</strong>`;
          statusCell.innerHTML = `<span class="badge badge-artefact">Physically Impossible (>100%)</span>`;
        } else {
          valCell.textContent = info.corrected;
          pctCell.innerHTML = `<strong style="color: var(--teal); font-weight: 800;">${info.correctedPct}</strong>`;
          statusCell.innerHTML = `<span class="badge badge-survives">Harmonised Plausible</span>`;
        }
      });

      if (alertBanner) {
        if (mode === 'stated') {
          alertBanner.className = 'caution';
          alertBanner.innerHTML = '<strong>Physical Impossibility:</strong> Stated units in OSD-655 imply plant tissues are composed of <strong>2,943% potassium</strong> by dry mass, exceeding total physical sample mass by nearly 30-fold.';
        } else {
          alertBanner.className = 'callout-box';
          alertBanner.innerHTML = '<strong>Harmonised Resolution:</strong> Converting to µg/g dry weight restores potassium to <strong>2.94% dry weight</strong>, perfectly aligning with baseline Brassicaceae plant physiology.';
        }
      }
    });
  });
}

// ============================================================================
// 2. Plant Crop Divergence & CLR Explorer
// ============================================================================
function initPlantClrExplorer() {
  const cropBtns = document.querySelectorAll('.plant-crop-btn');
  const scaleBtns = document.querySelectorAll('.plant-scale-btn');
  const tableBody = document.getElementById('plant-contrasts-tbody');

  const plantData = {
    tokyo_bekana: [
      { element: "Potassium (K)", rawFc: 1.54, rawP: 0.0005, clrFc: 1.15, clrP: 0.0199, status: "survives", desc: "True flight increase" },
      { element: "Sodium (Na)", rawFc: 2.15, rawP: 0.0005, clrFc: 1.80, clrP: 0.0014, status: "survives", desc: "True flight increase" },
      { element: "Sulfur (S)", rawFc: 1.75, rawP: 0.0003, clrFc: 1.28, clrP: 0.0002, status: "survives", desc: "True flight increase" },
      { element: "Calcium (Ca)", rawFc: 1.23, rawP: 0.0797, clrFc: 0.91, clrP: 0.2728, status: "artefact", desc: "Dry-matter dilution artefact" },
      { element: "Iron (Fe)", rawFc: 1.43, rawP: 0.0028, clrFc: 1.10, clrP: 0.2219, status: "artefact", desc: "Dry-matter dilution artefact" },
      { element: "Magnesium (Mg)", rawFc: 1.23, rawP: 0.0668, clrFc: 0.91, clrP: 0.2728, status: "artefact", desc: "Dry-matter dilution artefact" },
      { element: "Phosphorus (P)", rawFc: 1.36, rawP: 0.0668, clrFc: 1.01, clrP: 0.9621, status: "artefact", desc: "Dry-matter dilution artefact" },
      { element: "Boron (B)", rawFc: 1.35, rawP: 0.0310, clrFc: 0.99, clrP: 0.9621, status: "artefact", desc: "Dry-matter dilution artefact" },
      { element: "Copper (Cu)", rawFc: 0.85, rawP: 0.0798, clrFc: 0.64, clrP: 0.00002, status: "decreased", desc: "Significant CLR decrease" },
      { element: "Manganese (Mn)", rawFc: 1.04, rawP: 0.7397, clrFc: 0.76, clrP: 0.0075, status: "decreased", desc: "Significant CLR decrease" },
      { element: "Zinc (Zn)", rawFc: 1.15, rawP: 0.1950, clrFc: 0.85, clrP: 0.0069, status: "decreased", desc: "Significant CLR decrease" }
    ],
    lettuce: [
      { element: "Calcium (Ca)", rawFc: 0.90, rawP: 0.8838, clrFc: 0.88, clrP: 0.7305, status: "nochange", desc: "No significant change" },
      { element: "Iron (Fe)", rawFc: 0.96, rawP: 0.8838, clrFc: 0.83, clrP: 0.4425, status: "nochange", desc: "No significant change" },
      { element: "Magnesium (Mg)", rawFc: 0.99, rawP: 1.0000, clrFc: 0.96, clrP: 0.8167, status: "nochange", desc: "No significant change" },
      { element: "Manganese (Mn)", rawFc: 0.95, rawP: 1.0000, clrFc: 0.92, clrP: 0.8167, status: "nochange", desc: "No significant change" },
      { element: "Phosphorus (P)", rawFc: 1.10, rawP: 0.8838, clrFc: 1.07, clrP: 0.8167, status: "nochange", desc: "No significant change" },
      { element: "Potassium (K)", rawFc: 0.99, rawP: 1.0000, clrFc: 1.02, clrP: 0.8167, status: "nochange", desc: "No significant change" },
      { element: "Sodium (Na)", rawFc: 1.18, rawP: 0.8838, clrFc: 1.20, clrP: 0.4425, status: "nochange", desc: "No significant change" },
      { element: "Sulfur (S)", rawFc: 0.97, rawP: 1.0000, clrFc: 0.94, clrP: 0.8167, status: "nochange", desc: "No significant change" },
      { element: "Zinc (Zn)", rawFc: 1.24, rawP: 0.8838, clrFc: 1.26, clrP: 0.4425, status: "nochange", desc: "No significant change" }
    ]
  };

  let currentCrop = 'tokyo_bekana';
  let currentScale = 'both';

  function renderTable() {
    if (!tableBody) return;
    const data = plantData[currentCrop] || [];
    tableBody.innerHTML = '';

    data.forEach(item => {
      const tr = document.createElement('tr');
      let badgeHtml = '';
      if (item.status === 'survives') {
        badgeHtml = '<span class="badge badge-survives">Survives CLR (Flight Increase)</span>';
      } else if (item.status === 'artefact') {
        badgeHtml = '<span class="badge badge-artefact">Dilution Artefact</span>';
      } else if (item.status === 'decreased') {
        badgeHtml = '<span class="badge badge-decreased">Significant CLR Decrease</span>';
      } else {
        badgeHtml = '<span class="badge badge-nochange">No Significant Change</span>';
      }

      const fcVal = currentScale === 'clr' ? item.clrFc : item.rawFc;
      const pctWidth = Math.min(100, Math.max(10, Math.round(fcVal * 45)));
      const barColor = fcVal > 1.05 ? 'var(--teal-graphic)' : (fcVal < 0.95 ? 'var(--coral-graphic)' : 'var(--slate)');

      tr.innerHTML = `
        <td><strong>${item.element}</strong></td>
        <td class="text-right">${item.rawFc.toFixed(2)}</td>
        <td class="text-right" style="color: var(--muted); font-size: 0.85rem;">p=${item.rawP < 0.001 ? '<0.001' : item.rawP.toFixed(3)}</td>
        <td class="text-right" style="font-weight: 800; color: var(--navy);">${item.clrFc.toFixed(2)}</td>
        <td class="text-right" style="color: var(--muted); font-size: 0.85rem;">p=${item.clrP < 0.001 ? '<0.001' : item.clrP.toFixed(3)}</td>
        <td>
          <div style="display: flex; align-items: center; gap: 8px;">
            <div style="flex: 1; height: 8px; background: var(--line); border-radius: 4px; overflow: hidden;">
              <div style="width: ${pctWidth}%; height: 100%; background: ${barColor}; border-radius: 4px;"></div>
            </div>
            ${badgeHtml}
          </div>
        </td>
      `;
      tableBody.appendChild(tr);
    });
  }

  cropBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      cropBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentCrop = btn.dataset.crop;
      renderTable();
    });
  });

  scaleBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      scaleBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentScale = btn.dataset.scale;
      renderTable();
    });
  });

  renderTable();
}

// ============================================================================
// 3. Machine Learning Feature Importance
// ============================================================================
function initMlFeatureImportance() {
  const container = document.getElementById('ml-feature-importance-bars');
  if (!container) return;

  const features = [
    { name: "Potassium (K)", importance: 0.0755, std: 0.0268, note: "Top predictor &bull; Survives CLR" },
    { name: "Sodium (Na)", importance: 0.0383, std: 0.0205, note: "Survives CLR" },
    { name: "Sulfur (S)", importance: 0.0309, std: 0.0201, note: "Survives CLR" },
    { name: "Magnesium (Mg)", importance: 0.0129, std: 0.0107, note: "Dilution artefact" },
    { name: "Iron (Fe)", importance: 0.0062, std: 0.0083, note: "Dilution artefact" },
    { name: "Phosphorus (P)", importance: 0.0017, std: 0.0052, note: "Dilution artefact" },
    { name: "Calcium (Ca)", importance: 0.0000, std: 0.0000, note: "Zero importance" },
    { name: "Manganese (Mn)", importance: 0.0000, std: 0.0000, note: "Zero importance" },
    { name: "Zinc (Zn)", importance: 0.0000, std: 0.0000, note: "Zero importance" }
  ];

  const maxImp = 0.08;
  container.innerHTML = '';

  features.forEach(f => {
    const pct = (f.importance / maxImp) * 100;
    const barClass = f.importance > 0.02 ? 'fill-teal' : (f.importance > 0 ? 'fill-blue' : 'fill-slate');

    const div = document.createElement('div');
    div.style.marginBottom = '12px';
    div.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: baseline; font-size: 0.88rem; margin-bottom: 4px;">
        <div><strong>${f.name}</strong> <span style="font-size: 0.8rem; color: var(--muted); margin-left: 6px;">(${f.note})</span></div>
        <div style="font-weight: 800; color: var(--navy); font-size: 0.88rem;">${f.importance > 0 ? f.importance.toFixed(4) : '0.0000'}</div>
      </div>
      <div class="progress-container">
        <div class="progress-bar-track" style="height: 10px;">
          <div class="progress-bar-fill ${barClass}" style="width: ${Math.max(1, pct)}%;"></div>
        </div>
      </div>
    `;
    container.appendChild(div);
  });
}

// ============================================================================
// 4. Dietary Nutrition & Safety Calculator
// ============================================================================
function initNutritionCalculator() {
  const servingSlider = document.getElementById('serving-slider');
  const servingValDisplay = document.getElementById('serving-val-display');
  const cropSelect = document.getElementById('nutrition-crop-select');
  const conditionSelect = document.getElementById('nutrition-condition-select');
  const presetBtns = document.querySelectorAll('.preset-btn');
  const resultsContainer = document.getElementById('nutrition-results-container');
  const overloadDisplay = document.getElementById('overload-safety-text');

  const nutritionProfiles = {
    lettuce: {
      Flight: { potassium: 278.0, calcium: 40.0, iron: 0.936, magnesium: 18.5, manganese: 2.44, sodium: 16.2, phosphorus: 38.0, zinc: 1.607 },
      Ground: { potassium: 281.0, calcium: 44.6, iron: 0.972, magnesium: 18.6, manganese: 2.58, sodium: 13.7, phosphorus: 34.6, zinc: 1.296 }
    },
    tokyo_bekana: {
      Flight: { potassium: 209.0, calcium: 72.0, iron: 0.652, magnesium: 22.0, manganese: 1.98, sodium: 32.4, phosphorus: 48.0, zinc: 0.348 },
      Ground: { potassium: 136.0, calcium: 58.3, iron: 0.455, magnesium: 17.9, manganese: 1.90, sodium: 15.0, phosphorus: 35.4, zinc: 0.304 }
    }
  };

  const nasaStandards = {
    potassium: { req: 2000.0, ul: null, unit: "mg", label: "Potassium (K)" },
    calcium: { req: 1000.0, ul: 2500.0, unit: "mg", label: "Calcium (Ca)" },
    manganese: { req: 2.0, ul: 11.0, unit: "mg", label: "Manganese (Mn)" },
    iron: { req: 8.0, ul: 8.0, unit: "mg", label: "Iron (Fe)" },
    magnesium: { req: 420.0, ul: 350.0, unit: "mg", label: "Magnesium (Mg)" },
    zinc: { req: 11.0, ul: 40.0, unit: "mg", label: "Zinc (Zn)" },
    phosphorus: { req: 700.0, ul: 4000.0, unit: "mg", label: "Phosphorus (P)" },
    sodium: { req: 1500.0, ul: 2300.0, unit: "mg", label: "Sodium (Na)" }
  };

  function updateCalculator() {
    if (!servingSlider || !resultsContainer) return;
    const grams = parseFloat(servingSlider.value);
    if (servingValDisplay) servingValDisplay.textContent = `${grams} g`;

    const crop = cropSelect ? cropSelect.value : 'tokyo_bekana';
    const condition = conditionSelect ? conditionSelect.value : 'Flight';

    const profile = nutritionProfiles[crop][condition];
    resultsContainer.innerHTML = '';

    let hasMnWarning = false;

    Object.keys(nasaStandards).forEach(key => {
      const std = nasaStandards[key];
      const mgPer100g = profile[key] || 0;
      const suppliedMg = (mgPer100g * (grams / 100.0));
      const pctReq = (suppliedMg / std.req) * 100.0;

      if (key === 'manganese' && pctReq > 100) hasMnWarning = true;

      const fillClass = pctReq > 100 ? 'fill-coral' : (pctReq > 40 ? 'fill-gold' : 'fill-teal');
      const barWidth = Math.min(100, pctReq);

      const card = document.createElement('div');
      card.className = 'sub-card';
      card.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 6px;">
          <strong>${std.label}</strong>
          <span style="font-size: 0.85rem; color: var(--muted);">${suppliedMg.toFixed(2)} / ${std.req} ${std.unit}</span>
        </div>
        <div class="progress-container">
          <div class="progress-bar-track">
            <div class="progress-bar-fill ${fillClass}" style="width: ${barWidth}%;"></div>
          </div>
          <span class="progress-val-text" style="color: ${pctReq > 100 ? 'var(--coral)' : 'var(--navy)'}; font-weight: 800;">${pctReq.toFixed(1)}%</span>
        </div>
      `;
      resultsContainer.appendChild(card);
    });

    if (overloadDisplay) {
      const feMgPerG = profile.iron / 100.0;
      const kgToFeUl = (nasaStandards.iron.ul / feMgPerG) / 1000.0;
      const pillowPillows = Math.round((kgToFeUl * 1000) / 45);

      overloadDisplay.innerHTML = `
        <div class="callout-box" style="margin-top: 16px;">
          <h3 style="display: flex; align-items: center; gap: 8px;">
            <span style="color: var(--teal); font-size: 1.2rem;">🛡️</span> Overload Safety Assessment
          </h3>
          <p style="margin-bottom: 6px;">
            Reaching NASA's upper limit for iron (${nasaStandards.iron.ul} mg/day) would require consuming 
            <strong>${kgToFeUl.toFixed(2)} kg</strong> of fresh ${crop === 'lettuce' ? 'Lettuce' : 'Tokyo Bekana'} per day 
            (equivalent to <strong>${pillowPillows} pillows</strong> harvested daily).
          </p>
          <p style="margin: 0; font-size: 0.9rem; color: var(--muted);">
            ${hasMnWarning ? '⚠️ <strong>Nutritional Note:</strong> Manganese supply is high (' + ((profile.manganese * (grams/100)/2.0)*100).toFixed(0) + '% DV), representing the key micronutrient to track for long-duration crew diets.' : 'At standard operational harvest volumes (~45 g/pillow), dietary mineral toxicity from Veggie crops is impossible.'}
          </p>
        </div>
      `;
    }
  }

  if (servingSlider) servingSlider.addEventListener('input', updateCalculator);
  if (cropSelect) cropSelect.addEventListener('change', updateCalculator);
  if (conditionSelect) conditionSelect.addEventListener('change', updateCalculator);

  presetBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      presetBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      if (servingSlider) {
        servingSlider.value = btn.dataset.grams;
        updateCalculator();
      }
    });
  });

  updateCalculator();
}

// ============================================================================
// 5. Astronaut Serum Chemistry & NHANES Percentiles Explorer
// ============================================================================
function initAstronautNhanesExplorer() {
  const crewCards = document.querySelectorAll('.crew-card');
  const analyteSelect = document.getElementById('nhanes-analyte-select');
  const detailsBox = document.getElementById('astronaut-analyte-details');

  const nhanesData = {
    C001: {
      name: "Jared Isaacman", role: "Commander (38M)", stratum: "M_30-49", cohortN: 669,
      analytes: {
        calcium: { preVal: 9.77, prePct: 93.6, postVal: 9.70, postPct: 86.2, change: -7.3, median: 9.3, range: "8.8 - 9.8 mg/dL", unit: "mg/dL" },
        potassium: { preVal: 4.23, prePct: 68.6, postVal: 4.25, postPct: 68.6, change: 0.0, median: 4.1, range: "3.6 - 4.6 mmol/L", unit: "mmol/L" },
        sodium: { preVal: 140.67, prePct: 52.3, postVal: 138.25, postPct: 23.5, change: -28.8, median: 140.0, range: "136.0 - 144.0 mmol/L", unit: "mmol/L" }
      }
    },
    C002: {
      name: "Hayley Arceneaux", role: "Medical Officer (29F)", stratum: "F_18-29", cohortN: 494,
      analytes: {
        calcium: { preVal: 9.73, prePct: 93.3, postVal: 9.43, postPct: 75.3, change: -18.0, median: 9.3, range: "8.7 - 9.8 mg/dL", unit: "mg/dL" },
        potassium: { preVal: 3.90, prePct: 26.1, postVal: 3.93, postPct: 38.9, change: +12.8, median: 4.0, range: "3.5 - 4.5 mmol/L", unit: "mmol/L" },
        sodium: { preVal: 142.00, prePct: 75.1, postVal: 139.00, postPct: 33.2, change: -41.9, median: 140.0, range: "136.0 - 144.0 mmol/L", unit: "mmol/L" }
      }
    },
    C003: {
      name: "Chris Sembroski", role: "Mission Specialist (41M)", stratum: "M_30-49", cohortN: 669,
      analytes: {
        calcium: { preVal: 9.70, prePct: 93.6, postVal: 9.65, postPct: 86.2, change: -7.3, median: 9.3, range: "8.8 - 9.8 mg/dL", unit: "mg/dL" },
        potassium: { preVal: 3.50, prePct: 2.2, postVal: 3.73, postPct: 13.2, change: +10.9, median: 4.1, range: "3.6 - 4.6 mmol/L", unit: "mmol/L" },
        sodium: { preVal: 138.67, prePct: 23.5, postVal: 137.00, postPct: 7.0, change: -16.4, median: 140.0, range: "136.0 - 144.0 mmol/L", unit: "mmol/L" }
      }
    },
    C004: {
      name: "Sian Proctor", role: "Mission Pilot (51F)", stratum: "F_50-69", cohortN: 931,
      analytes: {
        calcium: { preVal: 10.10, prePct: 96.1, postVal: 9.85, postPct: 91.2, change: -4.9, median: 9.3, range: "8.8 - 10.0 mg/dL", unit: "mg/dL" },
        potassium: { preVal: 4.03, prePct: 55.2, postVal: 4.48, postPct: 89.9, change: +34.7, median: 4.0, range: "3.4 - 4.6 mmol/L", unit: "mmol/L" },
        sodium: { preVal: 139.67, prePct: 31.5, postVal: 140.00, postPct: 31.5, change: 0.0, median: 141.0, range: "136.0 - 145.0 mmol/L", unit: "mmol/L" }
      }
    }
  };

  let activeCrewId = "C001";

  function renderAstronautDetails() {
    if (!detailsBox) return;
    const crew = nhanesData[activeCrewId];
    const analyteKey = analyteSelect ? analyteSelect.value : 'potassium';
    const data = crew.analytes[analyteKey];

    if (!data) {
      detailsBox.innerHTML = '<p class="note">No comparison available for this analyte.</p>';
      return;
    }

    const changeSign = data.change > 0 ? `+${data.change.toFixed(1)}` : `${data.change.toFixed(1)}`;
    const changeColor = data.change < -15 ? 'var(--coral)' : (data.change > 15 ? 'var(--teal)' : 'var(--muted)');

    detailsBox.innerHTML = `
      <div style="margin-bottom: 20px;">
        <div style="display: flex; justify-content: space-between; align-items: baseline; flex-wrap: wrap; gap: 8px;">
          <h3 style="margin: 0; color: var(--navy); font-weight: 800;">${crew.name} &mdash; ${analyteKey.toUpperCase()}</h3>
          <span style="font-size: 0.86rem; color: var(--muted);">Matched NHANES Cohort: <strong>${crew.stratum}</strong> (N=${crew.cohortN} US adults)</span>
        </div>
      </div>

      <div class="grid-3" style="margin-bottom: 24px;">
        <div class="sub-card">
          <span style="font-size: 0.8rem; color: var(--muted); text-transform: uppercase; font-weight: 700;">Pre-Flight</span>
          <div style="font-size: 1.65rem; font-weight: 800; color: var(--navy);">${data.preVal.toFixed(2)} <span style="font-size: 0.9rem; font-weight: normal;">${data.unit}</span></div>
          <span style="font-size: 0.86rem; font-weight: 700; color: var(--navy);">${data.prePct.toFixed(1)}th percentile</span>
        </div>
        <div class="sub-card">
          <span style="font-size: 0.8rem; color: var(--muted); text-transform: uppercase; font-weight: 700;">Post-Flight (R+0)</span>
          <div style="font-size: 1.65rem; font-weight: 800; color: var(--coral);">${data.postVal.toFixed(2)} <span style="font-size: 0.9rem; font-weight: normal;">${data.unit}</span></div>
          <span style="font-size: 0.86rem; font-weight: 700; color: var(--coral);">${data.postPct.toFixed(1)}th percentile</span>
        </div>
        <div class="sub-card">
          <span style="font-size: 0.8rem; color: var(--muted); text-transform: uppercase; font-weight: 700;">Population Shift</span>
          <div style="font-size: 1.65rem; font-weight: 800; color: ${changeColor};">${changeSign} <span style="font-size: 0.9rem; font-weight: normal;">pp</span></div>
          <span style="font-size: 0.86rem; color: var(--muted);">NHANES Median: ${data.median} ${data.unit}</span>
        </div>
      </div>

      <div style="background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 18px;">
        <div style="display: flex; justify-content: space-between; font-size: 0.84rem; color: var(--muted); margin-bottom: 8px;">
          <span>0th Percentile (Min)</span>
          <span>50th (Population Median)</span>
          <span>100th Percentile (Max)</span>
        </div>
        <div style="position: relative; height: 32px; background: var(--line); border-radius: 16px; margin-bottom: 12px; overflow: visible;">
          <div style="position: absolute; left: 5%; width: 90%; height: 100%; background: rgba(37, 85, 132, 0.15); border-radius: 16px;"></div>
          <div style="position: absolute; left: 50%; top: -4px; bottom: -4px; width: 2px; background: var(--muted); z-index: 2;"></div>
          <div style="position: absolute; left: ${data.prePct}%; top: 50%; transform: translate(-50%, -50%); width: 18px; height: 18px; border-radius: 50%; background: var(--navy); border: 2px solid #ffffff; box-shadow: var(--shadow-sm); z-index: 5;" title="Pre-flight: ${data.prePct.toFixed(1)}th percentile"></div>
          <div style="position: absolute; left: ${data.postPct}%; top: 50%; transform: translate(-50%, -50%); width: 18px; height: 18px; border-radius: 4px; background: var(--coral-graphic); border: 2px solid #ffffff; box-shadow: var(--shadow-sm); z-index: 6;" title="Post-flight: ${data.postPct.toFixed(1)}th percentile"></div>
        </div>
        <div style="display: flex; justify-content: center; gap: 24px; font-size: 0.85rem; font-weight: 700;">
          <span style="display: inline-flex; align-items: center; gap: 6px;"><span style="width: 10px; height: 10px; border-radius: 50%; background: var(--navy);"></span> Pre-Flight</span>
          <span style="display: inline-flex; align-items: center; gap: 6px;"><span style="width: 10px; height: 10px; border-radius: 2px; background: var(--coral-graphic);"></span> Post-Flight</span>
          <span style="display: inline-flex; align-items: center; gap: 6px; color: var(--muted);"><span style="width: 2px; height: 10px; background: var(--muted);"></span> Population Median</span>
        </div>
      </div>
    `;
  }

  crewCards.forEach(card => {
    card.addEventListener('click', () => {
      crewCards.forEach(c => c.classList.remove('active'));
      card.classList.add('active');
      activeCrewId = card.dataset.subject;
      renderAstronautDetails();
      if (typeof window.renderTimelineForActiveSubject === 'function') {
        window.renderTimelineForActiveSubject(activeCrewId);
      }
    });
  });

  if (analyteSelect) {
    analyteSelect.addEventListener('change', () => {
      renderAstronautDetails();
      if (typeof window.renderTimelineForActiveSubject === 'function') {
        window.renderTimelineForActiveSubject(activeCrewId);
      }
    });
  }

  renderAstronautDetails();
}

// ============================================================================
// 6. Inspiration4 Longitudinal Trajectory Timeline
// ============================================================================
function initAstronautTimeline() {
  const container = document.getElementById('astronaut-timeline-container');
  if (!container) return;

  let serumRows = [];

  fetch('data/astronaut_serum_cmp.json')
    .then(res => res.json())
    .then(data => {
      serumRows = data;
      renderTimeline('C001');
    })
    .catch(err => console.warn('Loading fallback CMP serum data...', err));

  window.renderTimelineForActiveSubject = function(subjectId) {
    renderTimeline(subjectId);
  };

  function renderTimeline(subjectId) {
    if (!container || serumRows.length === 0) return;
    const analyteSelect = document.getElementById('nhanes-analyte-select');
    const analyte = analyteSelect ? analyteSelect.value : 'potassium';

    const subjectRows = serumRows.filter(r => r.subject === subjectId);
    if (subjectRows.length === 0) return;

    const timepoints = [
      { id: "L-92", label: "L-92", phase: "preflight" },
      { id: "L-44", label: "L-44", phase: "preflight" },
      { id: "L-3", label: "L-3", phase: "preflight" },
      { id: "R+1", label: "R+1 (Return)", phase: "postflight" },
      { id: "R+45", label: "R+45", phase: "recovery" },
      { id: "R+82", label: "R+82", phase: "recovery" },
      { id: "R+194", label: "R+194", phase: "recovery" }
    ];

    let html = `
      <div style="margin-top: 24px;">
        <h4 style="margin: 0 0 10px; color: var(--navy); font-weight: 700;">Longitudinal Trajectory: ${subjectId} (${analyte.toUpperCase()})</h4>
        <div class="table-responsive">
          <table>
            <thead>
              <tr>
                <th>Timepoint</th>
                <th>Phase</th>
                <th class="text-right">Measured Value</th>
                <th class="text-right">Reference Range</th>
                <th>Range Position</th>
              </tr>
            </thead>
            <tbody>
    `;

    timepoints.forEach(tp => {
      const match = subjectRows.find(r => r.timepoint === tp.id);
      if (!match) return;

      const val = parseFloat(match[analyte]);
      const min = parseFloat(match[`${analyte}_range_min`]);
      const max = parseFloat(match[`${analyte}_range_max`]);
      const unit = match[`${analyte}_unit`].replace(/_/g, ' ');
      const pos = parseFloat(match[`${analyte}_range_position`]);
      const isOut = match[`${analyte}_out_of_range`] === 'True';

      const pct = Math.min(100, Math.max(0, pos * 100));
      const dotColor = isOut ? 'var(--coral-graphic)' : (tp.phase === 'postflight' ? 'var(--gold-graphic)' : 'var(--teal-graphic)');

      html += `
        <tr>
          <td><strong><code>${tp.label}</code></strong></td>
          <td><span style="font-size: 0.8rem; text-transform: uppercase; color: var(--muted); font-weight: 700;">${tp.phase}</span></td>
          <td class="text-right"><strong>${val.toFixed(2)}</strong> <span style="font-size: 0.82rem; color: var(--muted);">${unit}</span></td>
          <td class="text-right" style="color: var(--muted);">${min} &ndash; ${max}</td>
          <td>
            <div style="display: flex; align-items: center; gap: 8px;">
              <div style="flex: 1; height: 6px; background: var(--line); border-radius: 3px; position: relative;">
                <div style="position: absolute; left: ${pct}%; top: -4px; width: 14px; height: 14px; border-radius: 50%; background: ${dotColor}; transform: translateX(-50%); border: 2px solid #ffffff;"></div>
              </div>
              <span style="font-size: 0.82rem; min-width: 40px; color: var(--muted);">${(pos*100).toFixed(0)}%</span>
            </div>
          </td>
        </tr>
      `;
    });

    html += `</tbody></table></div></div>`;
    container.innerHTML = html;
  }
}

// ============================================================================
// 7. Interactive 60-Sample Plant ICP-OES Dataset Viewer
// ============================================================================
function initPlantDatasetViewer() {
  const container = document.getElementById('plant-dataset-tbody');
  const cropFilter = document.getElementById('plant-data-crop-filter');
  const flightFilter = document.getElementById('plant-data-flight-filter');
  const searchInput = document.getElementById('plant-data-search');
  const countBadge = document.getElementById('plant-data-count');

  if (!container) return;

  let allSamples = [];

  fetch('data/plant_elemental_ugg.json')
    .then(res => res.json())
    .then(data => {
      allSamples = data;
      renderPlantData();
    })
    .catch(err => console.warn('Loading fallback plant elemental data...', err));

  function renderPlantData() {
    if (!container || allSamples.length === 0) return;

    const crop = cropFilter ? cropFilter.value : 'all';
    const flight = flightFilter ? flightFilter.value : 'all';
    const q = (searchInput ? searchInput.value : '').toLowerCase().trim();

    const filtered = allSamples.filter(s => {
      const matchCrop = crop === 'all' || s.crop.toLowerCase().includes(crop.toLowerCase());
      const matchFlight = flight === 'all' || s.flight_status.toLowerCase() === flight.toLowerCase();
      const matchQ = !q || s.sample_id.toLowerCase().includes(q) || s.mission.toLowerCase().includes(q);
      return matchCrop && matchFlight && matchQ;
    });

    container.innerHTML = '';
    if (countBadge) countBadge.textContent = `${filtered.length} of ${allSamples.length} samples`;

    filtered.forEach(s => {
      const tr = document.createElement('tr');
      const isFlight = s.flight_status.toLowerCase() === 'flight';
      const badgeClass = isFlight ? 'badge-survives' : 'badge-nochange';

      tr.innerHTML = `
        <td><strong><code>${s.sample_id}</code></strong></td>
        <td>${s.crop.replace(/_/g, ' ')}</td>
        <td>${s.mission}</td>
        <td><span class="badge ${badgeClass}">${s.flight_status}</span></td>
        <td class="text-right"><strong>${parseFloat(s.potassium).toFixed(0)}</strong></td>
        <td class="text-right">${parseFloat(s.calcium).toFixed(0)}</td>
        <td class="text-right">${parseFloat(s.magnesium).toFixed(0)}</td>
        <td class="text-right">${parseFloat(s.iron).toFixed(1)}</td>
        <td class="text-right">${parseFloat(s.manganese).toFixed(1)}</td>
        <td class="text-right">${parseFloat(s.sodium).toFixed(0)}</td>
      `;
      container.appendChild(tr);
    });
  }

  if (cropFilter) cropFilter.addEventListener('change', renderPlantData);
  if (flightFilter) flightFilter.addEventListener('change', renderPlantData);
  if (searchInput) searchInput.addEventListener('input', renderPlantData);
}

// ============================================================================
// 8. NASA LSDA Mineral Catalog Explorer
// ============================================================================
function initLsdaCatalogExplorer() {
  const searchInput = document.getElementById('lsda-search-input');
  const filterTabs = document.querySelectorAll('.lsda-tab-btn');
  const catalogTbody = document.getElementById('lsda-catalog-tbody');
  const pageInfo = document.getElementById('lsda-page-info');
  const prevBtn = document.getElementById('lsda-prev-btn');
  const nextBtn = document.getElementById('lsda-next-btn');

  let allStudies = [];
  let filteredStudies = [];
  let currentPage = 1;
  const pageSize = 8;
  let activeFilter = 'all';

  fetch('data/lsda_measured_mineral_catalog.json')
    .then(res => res.json())
    .then(data => {
      allStudies = data;
      applyFilterAndSearch();
    })
    .catch(err => console.warn('Loading fallback LSDA catalog data...', err));

  function applyFilterAndSearch() {
    const query = (searchInput ? searchInput.value : '').toLowerCase().trim();

    filteredStudies = allStudies.filter(item => {
      const matchFilter = activeFilter === 'all' || item.access === activeFilter;
      const matchQuery = !query || 
        item.id.toLowerCase().includes(query) ||
        item.title.toLowerCase().includes(query) ||
        item.pi.toLowerCase().includes(query) ||
        item.minerals.toLowerCase().includes(query);
      return matchFilter && matchQuery;
    });

    currentPage = 1;
    renderCatalogPage();
  }

  function renderCatalogPage() {
    if (!catalogTbody) return;
    catalogTbody.innerHTML = '';

    const total = filteredStudies.length;
    const totalPages = Math.max(1, Math.ceil(total / pageSize));
    const startIdx = (currentPage - 1) * pageSize;
    const pageItems = filteredStudies.slice(startIdx, startIdx + pageSize);

    if (pageItems.length === 0) {
      catalogTbody.innerHTML = '<tr><td colspan="5" class="text-center" style="padding: 24px; color: var(--muted);">No experiments found matching criteria.</td></tr>';
    } else {
      pageItems.forEach(study => {
        const tr = document.createElement('tr');
        let badgeHtml = '';
        if (study.access === 'open') {
          badgeHtml = '<span class="badge badge-open">Open Access</span>';
        } else if (study.access === 'request_required') {
          badgeHtml = '<span class="badge badge-gated">Request Gated</span>';
        } else {
          badgeHtml = '<span class="badge badge-unsubmitted">Not Submitted</span>';
        }

        tr.innerHTML = `
          <td><strong><code>${study.id}</code></strong></td>
          <td><strong>${study.title}</strong></td>
          <td>${study.pi || '&mdash;'}</td>
          <td>${study.species || 'Human'}</td>
          <td>${badgeHtml}</td>
        `;
        catalogTbody.appendChild(tr);
      });
    }

    if (pageInfo) {
      pageInfo.textContent = `Showing ${Math.min(total, startIdx + 1)}–${Math.min(total, startIdx + pageItems.length)} of ${total} studies (Page ${currentPage} of ${totalPages})`;
    }
    if (prevBtn) prevBtn.disabled = (currentPage <= 1);
    if (nextBtn) nextBtn.disabled = (currentPage >= totalPages);
  }

  if (searchInput) searchInput.addEventListener('input', applyFilterAndSearch);

  filterTabs.forEach(tab => {
    tab.addEventListener('click', () => {
      filterTabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      activeFilter = tab.dataset.filter;
      applyFilterAndSearch();
    });
  });

  if (prevBtn) {
    prevBtn.addEventListener('click', () => {
      if (currentPage > 1) {
        currentPage--;
        renderCatalogPage();
      }
    });
  }

  if (nextBtn) {
    nextBtn.addEventListener('click', () => {
      const totalPages = Math.ceil(filteredStudies.length / pageSize);
      if (currentPage < totalPages) {
        currentPage++;
        renderCatalogPage();
      }
    });
  }
}

// ============================================================================
// 9. Citation Exporter & Clipboard Helper
// ============================================================================
function initCitationCopy() {
  const copyBibBtn = document.getElementById('copy-bibtex-btn');
  const bibtexText = document.getElementById('bibtex-code-block');

  if (copyBibBtn && bibtexText) {
    copyBibBtn.addEventListener('click', () => {
      navigator.clipboard.writeText(bibtexText.innerText).then(() => {
        const originalText = copyBibBtn.textContent;
        copyBibBtn.textContent = '✓ Copied to Clipboard!';
        setTimeout(() => copyBibBtn.textContent = originalText, 2500);
      });
    });
  }
}

// ============================================================================
// 10. Publication Figure Modal Lightbox
// ============================================================================
function initFigureModal() {
  const modal = document.getElementById('figure-modal');
  const modalImg = document.getElementById('modal-figure-img');
  const modalTitle = document.getElementById('modal-figure-title');
  const modalClose = document.getElementById('modal-close-btn');
  const figureWrappers = document.querySelectorAll('.figure-wrapper');

  if (!modal || !modalImg) return;

  figureWrappers.forEach(wrapper => {
    wrapper.addEventListener('click', () => {
      const img = wrapper.querySelector('img');
      const caption = wrapper.getAttribute('data-caption') || img.alt;
      modalImg.src = img.src;
      if (modalTitle) modalTitle.textContent = caption;
      modal.classList.add('active');
    });
  });

  if (modalClose) {
    modalClose.addEventListener('click', () => {
      modal.classList.remove('active');
    });
  }

  modal.addEventListener('click', (e) => {
    if (e.target === modal) {
      modal.classList.remove('active');
    }
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && modal.classList.contains('active')) {
      modal.classList.remove('active');
    }
  });
}
