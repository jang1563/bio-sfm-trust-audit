# dist/ — citable artifacts + how to publish them

This folder holds the publish-ready outputs and a reproducible builder.

## Files

- `REPORT.pdf` — the technical report (built from `../REPORT.md`).
- `PHASE2_PREREGISTRATION.pdf` — the confirmatory-redo pre-registration
  (built from `../experiments/trust_cue_attribution/PHASE2_PREREGISTRATION.md`).
- `build_pdf.sh` — rebuilds both PDFs from the markdown sources (pandoc + xelatex).
- `header.tex`, `meta.yaml` — LaTeX header + title-block metadata used by the build.
- `zenodo_deposit.zip` — (generated) a self-contained bundle to drag-and-drop
  into Zenodo/OSF. Not committed (derived from repo files).

## Rebuild

```bash
bash dist/build_pdf.sh      # -> dist/REPORT.pdf, dist/PHASE2_PREREGISTRATION.pdf
```

Needs `pandoc` and `xelatex` (TeX Live). No extra LaTeX packages required: the few
math-symbol Unicode characters are converted to LaTeX math by the build, and the
optional `microtype`/`titlesec` are guarded with `\IfFileExists`.

## Publish (visible + referenceable, without arXiv)

Repo is private, so use the manual route (keeps the repo private):

1. **Zenodo (DOI for the report + data).** Upload `zenodo_deposit.zip` (or its
   contents) to a new Zenodo deposit. `../.zenodo.json` and `../CITATION.cff`
   provide the metadata. Publishing mints a citable DOI.
2. **OSF (pre-registration).** Upload `PHASE2_PREREGISTRATION.pdf` to an OSF
   project/registration for a timestamped, citable pre-reg; link the Zenodo DOI.
3. **Hugging Face (visibility, optional).** Publish the 80-target benchmark as an
   HF dataset card (or a short HF blog post) linking back to the Zenodo DOI.

Alternative (only if the repo is made public): connect the GitHub repo in Zenodo,
then create a GitHub Release — Zenodo auto-mints a DOI from `.zenodo.json`.
