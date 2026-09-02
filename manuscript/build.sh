#!/usr/bin/env bash
# Build the manuscript PDF and DOCX.
#
# Prefers latexmk (handles the bibtex passes automatically); falls back to an
# explicit pdflatex/bibtex/pdflatex/pdflatex sequence. Fails loudly rather than
# emitting a stale PDF, so a broken build is never mistaken for a successful one.
set -euo pipefail
cd "$(dirname "$0")"

OUT="SpaceMineralAtlas_manuscript"

if command -v latexmk >/dev/null 2>&1; then
    echo "==> building with latexmk"
    latexmk -pdf -interaction=nonstopmode -halt-on-error -jobname="$OUT" main.tex
elif command -v pdflatex >/dev/null 2>&1; then
    echo "==> building with pdflatex + bibtex"
    pdflatex -interaction=nonstopmode -halt-on-error -jobname="$OUT" main.tex
    bibtex "$OUT" || true
    pdflatex -interaction=nonstopmode -halt-on-error -jobname="$OUT" main.tex
    pdflatex -interaction=nonstopmode -halt-on-error -jobname="$OUT" main.tex
else
    echo "ERROR: no LaTeX engine found (need latexmk or pdflatex)" >&2
    exit 1
fi

echo "==> PDF: $(pwd)/${OUT}.pdf"

if command -v pandoc >/dev/null 2>&1; then
    echo "==> building DOCX with pandoc"
    pandoc main.tex \
        --from=latex --to=docx \
        --bibliography=references.bib --citeproc \
        --resource-path=.:figures \
        --output="${OUT}.docx" \
    && echo "==> DOCX: $(pwd)/${OUT}.docx" \
    || echo "WARNING: pandoc DOCX conversion failed; PDF is still valid" >&2
else
    echo "WARNING: pandoc not found; skipping DOCX" >&2
fi
