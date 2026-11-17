# Synthetic material rebuild

Run from `booking-precheck/` after installing the workspace development dependencies:

```sh
uv sync --all-packages --all-extras
uv run python tools/generate_materials.py
```

From the repository root, the equivalent command is:

```sh
uv run --project booking-precheck python booking-precheck/tools/generate_materials.py
```

Generation needs ReportLab and validation needs pdfplumber. Their locked versions are installed by the workspace environment. No model API, private archive, system fonts or external service is needed.

## Frozen sources and generated files

The committed `assets/` JSON and Markdown files are the frozen teaching fixtures, manifests, rules, policy index and ground truth. Do not regenerate expected answers to make an Agent pass evaluation.

The wrapper copies these sources into an isolated directory under `.generated/`, runs the original DP-001 and remaining-material renderers, and compares every regenerated JSON/Markdown file with its frozen source. The report distinguishes JSON serialization differences, JSON semantic differences using precise JSON pointers, and Markdown text differences. It then validates the generated PDFs against the frozen sources, rather than using newly generated answers as the validation oracle.

Only validated PDFs are copied back to their existing manifest paths, such as `assets/document-packs/DP-001/output/pdf/booking-request.pdf` and `assets/document-packs/DP-008/stage-02/output/pdf/preliminary-dgd.pdf`. The tests and runtime retain the original `assets/` paths. Every frozen source byte is checked again after publication.

PDFs, `.generated/`, temporary builds and reports are local/CI artifacts, not versioned source. The low-level `generate_dp001_pilot.py` and `generate_remaining_materials.py` renderers can also rewrite metadata; use the wrapper for normal builds. Their `BOOKING_PRECHECK_MATERIALS_ROOT` environment variable exists for isolated builds, and defaults to this lab's `assets/`.

## Validation

```sh
uv run python tools/validate_materials.py
```

The validator requires all present documents across 8 packs and 9 stages, while keeping intentionally absent documents absent. It checks each input PDF's frozen page count, all 238 field-evidence fragments on the specified pages, the policy index's 28 rule-evidence fragments, the 3 policy documents' frozen pagination, complete rule coverage, fixture semantics and exact PDF inventory. Policy page counts are frozen in `assets/policy-documents/EXPECTED_PAGE_COUNTS.json` as 2, 6 and 1 pages.

A successful full build produces 27 PDFs: 24 input documents and 3 policy documents. The report is `.generated/materials-report.json`. Its page-count inventory and source-difference summary can be retained as CI artifacts. A failure exits nonzero and preserves its isolated build directory for diagnosis; no unvalidated staging PDFs are published.

After changing a renderer, also render its PDFs with a local PDF viewer or Poppler and inspect the page layout. Evidence extraction is a correctness check, not a substitute for visual review.
