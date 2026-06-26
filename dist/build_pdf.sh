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

# Sanitize the handful of math-symbol Unicode chars so they render in any font
# (xelatex + Latin Modern), and strip REPORT's markdown title block (-> meta.yaml).
# Applied to BOTH documents (the pre-registration also contains >=, etc.).
python3 - <<'PY'
import re
# Relational ops (>=, <=, !=) -> ASCII: their math glyphs are missing in the bold
# weight (headings, **bold** spans) and pandoc won't parse "$\geq$90" (closing $ before
# a digit) as math. Arrows/approx/times/lambda render fine as math; Delta kept literal.
SYM=[('→',r'$\rightarrow$'),('≈',r'$\approx$'),('×',r'$\times$'),('λ',r'$\lambda$'),
     ('≥','>='),('≤','<='),('≠','!=')]
def sanitize(text):
    text=text.replace('`net = correct − λ·assays`','`net = correct - lambda*assays`')
    text=text.replace('—','---').replace('–','--')                   # em/en dash -> ligatures
    text=re.sub(r'−([0-9][0-9.]*)', r'$-\1$', text)                      # negative numbers wrapped
    text=text.replace('−','-')                                            # binary minus -> hyphen (a bare $-$ mis-pairs with adjacent $..$)
    for u,t in SYM: text=text.replace(u,t)
    assert '−' not in text                                                # Delta (U+0394) kept literal
    return text
lines=open('REPORT.md',encoding='utf-8').read().splitlines(keepends=True)
start=next(i for i,l in enumerate(lines) if l.startswith('## Abstract'))
open('dist/_report_body.md','w',encoding='utf-8').write(sanitize(''.join(lines[start:])))
open('dist/_prereg_body.md','w',encoding='utf-8').write(
    sanitize(open('experiments/trust_cue_attribution/PHASE2_PREREGISTRATION.md',encoding='utf-8').read()))
open('dist/_prereg4_body.md','w',encoding='utf-8').write(
    sanitize(open('experiments/trust_cue_attribution/PHASE4_PREREGISTRATION.md',encoding='utf-8').read()))
PY
pandoc dist/meta.yaml dist/_report_body.md -o dist/REPORT.pdf "${PANDOC_COMMON[@]}"
echo "built dist/REPORT.pdf"
pandoc dist/_prereg_body.md -o dist/PHASE2_PREREGISTRATION.pdf "${PANDOC_COMMON[@]}"
echo "built dist/PHASE2_PREREGISTRATION.pdf"
pandoc dist/_prereg4_body.md -o dist/PHASE4_PREREGISTRATION.pdf "${PANDOC_COMMON[@]}"
echo "built dist/PHASE4_PREREGISTRATION.pdf"
rm -f dist/_report_body.md dist/_prereg_body.md dist/_prereg4_body.md
