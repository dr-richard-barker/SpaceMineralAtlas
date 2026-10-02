# SpaceMineralAtlas -- end-to-end reproducible pipeline.
#
# `make all` runs everything from a clean checkout: harvest, download, harmonise,
# quality-control, analyse, plot, and build the manuscript. Every stage writes to
# a tracked location, and no stage has a fallback that substitutes generated data
# for a failed retrieval.

PY := ./.venv/bin/python
PIP := ./.venv/bin/pip

.PHONY: all setup harvest fetch fetch-nhanes curate analyse figures nhanes-figures numbers bibliography \
        manuscript fair docs test check clean distclean help

help:
	@echo "SpaceMineralAtlas"
	@echo ""
	@echo "  make setup        create the venv and install pinned dependencies"
	@echo "  make all          run the complete pipeline end to end"
	@echo ""
	@echo "  make harvest      harvest the LSDA experiment catalog (2,676 records)"
	@echo "  make fetch-nhanes download NHANES population baselines (2017-2018)"
	@echo "  make curate       download OSDR data, harmonise units, run QC gates"
	@echo "  make analyse      contrasts, supply indices, astronaut trajectories, ML"
	@echo "  make nhanes-figures plot Inspiration4 vs NHANES comparisons"
	@echo "  make figures      generate and distribute all publication figures"
	@echo "  make numbers      regenerate the manuscript's LaTeX number macros"
	@echo "  make bibliography re-verify every DOI against Crossref"
	@echo "  make manuscript   build the PDF and DOCX"
	@echo "  make fair         assemble the Zenodo / RO-Crate deposit package"
	@echo "  make docs         build the GitHub Pages interactive research portal"
	@echo ""
	@echo "  make test         run the test suite"
	@echo "  make check        verify no macro is used without a definition"
	@echo "  make clean        remove build artefacts (keeps cached downloads)"
	@echo "  make distclean    also remove cached downloads"

setup:
	python3.11 -m venv .venv
	$(PIP) install --quiet --upgrade pip
	$(PIP) install --quiet -e ".[dev]"
	@echo "environment ready"

all: harvest curate analyse figures numbers manuscript fair docs test
	@echo ""
	@echo "=================================================================="
	@echo " Pipeline complete."
	@echo "   manuscript : manuscript/SpaceMineralAtlas_manuscript.pdf"
	@echo "   catalog    : catalog/lsda_mineral_nutrition_catalog.csv"
	@echo "   data       : data/processed/plant_elemental_ugg.csv"
	@echo "   docs       : docs/index.html"
	@echo "=================================================================="

harvest:
	$(PY) scripts_harvest_lsda.py

# `curate` is the fetch stage: it downloads from OSDR, harmonises units and runs
# the QC gates. It fails the build if any gate fails.
fetch curate:
	$(PY) scripts_curate.py

fetch-nhanes:
	$(PY) scripts_integrate_nhanes.py

analyse: curate fetch-nhanes
	$(PY) scripts_analyse_plants.py
	$(PY) scripts_analyse_astronauts.py
	$(PY) scripts_analyse_supply.py
	$(PY) scripts_integrate.py
	$(PY) scripts_ml.py

nhanes-figures: fetch-nhanes
	$(PY) scripts_plot_nhanes_comparison.py

figures: analyse nhanes-figures
	$(PY) scripts_figures.py

numbers: analyse
	$(PY) scripts_generate_numbers.py

bibliography:
	$(PY) scripts_build_bibliography.py

check: numbers
	$(PY) scripts_check_macros.py

manuscript: numbers figures check
	cd manuscript && ./build.sh

fair:
	$(PY) scripts_fair_package.py

docs: figures fair
	python3 scripts_build_docs.py

test:
	$(PY) -m pytest tests/ -q

clean:
	rm -f manuscript/*.aux manuscript/*.bbl manuscript/*.blg manuscript/*.log \
	      manuscript/*.out manuscript/*.toc manuscript/*.fls manuscript/*.fdb_latexmk
	find . -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache

distclean: clean
	rm -rf data/raw data/interim
	@echo "cached downloads removed; the next run will re-fetch from NASA"
