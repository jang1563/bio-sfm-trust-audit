#!/usr/bin/env bash
# Reproducibly build the citable PDFs from the markdown sources.
#   dist/REPORT.pdf   <- REPORT.md          (+ dist/meta.yaml title block, dist/header.tex)
#   dist/PHASE2_PREREGISTRATION.pdf <- experiments/trust_cue_attribution/PHASE2_PREREGISTRATION.md
# Requires: pandoc + xelatex (TeX Live). No extra LaTeX packages needed.
set -euo pipefail
cd "$(dirname "$0")/.."   # repo root

PANDOC_COMMON=(--pdf-engine=xelatex -H dist/header.tex
  -V geometry:margin=1in -V fontsize=11pt
  -V colorlinks=true -V linkcolor=blue -V urlcolor=blue)

# --- REPORT.pdf : strip the markdown title block (-> dist/meta.yaml) and make the
#     handful of math-symbol Unicode chars render in any font (xelatex + Latin Modern).
python3 - <<'PY'
import re
lines=open('REPORT.md',encoding='utf-8').read().splitlines(keepends=True)
start=next(i for i,l in enumerate(lines) if l.startswith('## Abstract'))
body=''.join(lines[start:])
body=body.replace('`net = correct − λ·assays`', '`net = correct - lambda*assays`')
body=body.replace('—','---').replace('–','--')          # em/en dash -> ligatures
body=re.sub(r'−([0-9][0-9.]*)', r'$-\1$', body)              # negative numbers wrapped (pandoc: closing $ not before a digit)
body=body.replace('−','$-$')                                  # remaining (binary) minus
for u,tex in [('→',r'$\rightarrow$'),('≈',r'$\approx$'),('≥',r'$\geq$'),
              ('≤',r'$\leq$'),('≠',r'$\neq$'),('×',r'$\times$'),('λ',r'$\lambda$')]:
    body=body.replace(u,tex)                                      # Greek Delta (U+0394) kept literal (Latin Modern has it)
assert '−' not in body
open('dist/_report_body.md','w',encoding='utf-8').write(body)
PY
pandoc dist/meta.yaml dist/_report_body.md -o dist/REPORT.pdf "${PANDOC_COMMON[@]}"
echo "built dist/REPORT.pdf"

# --- PHASE2_PREREGISTRATION.pdf : pure ASCII, render directly.
pandoc experiments/trust_cue_attribution/PHASE2_PREREGISTRATION.md \
  -o dist/PHASE2_PREREGISTRATION.pdf "${PANDOC_COMMON[@]}"
echo "built dist/PHASE2_PREREGISTRATION.pdf"

rm -f dist/_report_body.md
