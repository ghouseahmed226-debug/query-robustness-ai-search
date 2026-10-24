#!/usr/bin/env bash
# Build the manuscript from the result files:
#   paper/manuscript_draft.md      (numbers filled in by scripts/build_paper.py)
#   paper/manuscript_draft.pdf     (pandoc -> LaTeX -> pdflatex + bibtex)
#   paper/arxiv_source/            (main.tex, main.bbl, references.bib, figures/ ; compiles stand-alone with pdflatex)
#
# Needs: python (with the project's dependencies), pandoc >= 3, pdflatex, bibtex, and the LaTeX packages natbib,
# booktabs, longtable, caption, psnfss (mathptmx), hyperref. Run from anywhere:  bash scripts/build_pdf.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="${PYTHON:-python}"
cd "$ROOT/paper"

"$PY" -I "$ROOT/scripts/build_paper.py"
"$PY" -I "$ROOT/scripts/build_paper.py" --template "$ROOT/docs/README_template.md" --out "$ROOT/README.md" --no-numbers-log

rm -rf build && mkdir -p build/figures
pandoc manuscript_draft.md -f markdown+smart -s --natbib -V natbiboptions=round --number-sections \
  -V documentclass=article -V fontsize=11pt -V geometry:margin=1in -V colorlinks=true -V fontfamily=mathptmx \
  -H header.tex -o build/main.tex
cp references.bib build/
cp figures/fig1_ndcg_change.pdf build/figures/
(
  cd build
  pdflatex -interaction=nonstopmode -halt-on-error main.tex >/dev/null
  bibtex main >/dev/null
  pdflatex -interaction=nonstopmode -halt-on-error main.tex >/dev/null
  pdflatex -interaction=nonstopmode -halt-on-error main.tex >/dev/null
)
cp build/main.pdf manuscript_draft.pdf

rm -rf arxiv_source && mkdir -p arxiv_source/figures
cp build/main.tex build/main.bbl build/references.bib arxiv_source/
cp figures/fig1_ndcg_change.pdf arxiv_source/figures/
echo "wrote paper/manuscript_draft.md, paper/manuscript_draft.pdf and paper/arxiv_source/"
