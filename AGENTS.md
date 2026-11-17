# Lab maintenance

- Keep each runnable case self-contained. Booking Precheck is a uv workspace under `booking-precheck/`.
- Commit Python, schemas, frozen JSON fixtures, Markdown and lockfiles only. Never commit generated PDF/HTML, screenshots, reports, traces, runtime state, real credentials or Git backups. `.env.example` files contain placeholders only.
- Build PDFs with `uv run --locked python tools/generate_materials.py` in the case workspace. Frozen inputs and expected outputs must not change during generation.
- Run the complete contracts/agent/evaluation tests, the deterministic smoke and `scripts/verify_evaluation.py` before publishing changes.
- Preserve the distinction between a deterministic rule baseline, a scripted test model and a real-model Agent run. Do not describe offline scores as model accuracy.
- The migrated Single-Agent deliberately lacks some application-level guardrails. Keep that teaching boundary explicit; behavior changes belong in a separately evaluated variant.
- Tests and default CI do not invoke real models or Langfuse. Keep tracing disabled for offline checks.
- Keep the course link and release version in sync with `agentic-styles/patterns`; the website must not require this workspace to build.
