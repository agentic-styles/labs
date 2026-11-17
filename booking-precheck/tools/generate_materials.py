"""Rebuild synthetic PDFs without rewriting frozen fixtures or ground truth.

Run from booking-precheck with ``uv run python tools/generate_materials.py``.
Only ignored PDF output directories and .generated/ are written.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


LAB_ROOT = Path(__file__).resolve().parents[1]
TOOLS = Path(__file__).resolve().parent


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def semantic_changes(before, after, path=""):
    """Return precise JSON pointers instead of concealing regenerated changes."""
    if type(before) is not type(after):
        return [path or "/"]
    if isinstance(before, dict):
        changes = []
        for key in sorted(before.keys() | after.keys()):
            escaped = str(key).replace("~", "~0").replace("/", "~1")
            pointer = f"{path}/{escaped}"
            if key not in before or key not in after:
                changes.append(pointer)
            else:
                changes.extend(semantic_changes(before[key], after[key], pointer))
        return changes
    if isinstance(before, list):
        if len(before) != len(after):
            return [path or "/"]
        return [pointer for index, (left, right) in enumerate(zip(before, after))
                for pointer in semantic_changes(left, right, f"{path}/{index}")]
    return [] if before == after else [path or "/"]


def run_tool(name: str, root: Path) -> str:
    environment = dict(os.environ, BOOKING_PRECHECK_MATERIALS_ROOT=str(root))
    result = subprocess.run(
        [sys.executable, str(TOOLS / name)], env=environment,
        capture_output=True, text=True, check=False,
    )
    if result.returncode:
        raise RuntimeError(f"{name} failed:\n{result.stdout}\n{result.stderr}")
    return result.stdout


def generate(assets_root: Path, generated_root: Path) -> dict:
    assets_root = assets_root.resolve()
    generated_root = generated_root.resolve()
    if not (assets_root / "policy_snapshot.json").is_file():
        raise ValueError(f"Not an assets root: {assets_root}")
    generated_root.mkdir(parents=True, exist_ok=True)
    build_root = Path(tempfile.mkdtemp(prefix="materials-", dir=generated_root))
    staged_assets = build_root / "assets"
    report_path = generated_root / "materials-report.json"
    report = {
        "status": "running",
        "frozen_metadata_policy": "Generated metadata is compared and reported, then frozen source bytes are used to validate PDFs.",
        "metadata_changes": [],
        "source_metadata_unchanged": False,
    }
    frozen = {
        path.relative_to(assets_root): path.read_bytes()
        for path in assets_root.rglob("*")
        if path.is_file() and path.suffix.lower() in {".json", ".md"}
    }
    try:
        # Never copy previous PDFs, reports or runtime secrets into the build.
        for relative, data in frozen.items():
            target = staged_assets / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        run_tool("generate_dp001_pilot.py", staged_assets)
        run_tool("generate_remaining_materials.py", staged_assets)
        for relative, before in frozen.items():
            target = staged_assets / relative
            after = target.read_bytes()
            if before == after:
                continue
            change = {"path": relative.as_posix(), "source_sha256": digest(before), "regenerated_sha256": digest(after)}
            if relative.suffix == ".json":
                pointers = semantic_changes(json.loads(before), json.loads(after))
                change.update({
                    "kind": "json_semantics" if pointers else "serialization_only",
                    "changed_json_pointers": pointers,
                })
            else:
                change["kind"] = "source_text"
            report["metadata_changes"].append(change)
            # These are explicit frozen references, not regenerated answers.
            target.write_bytes(before)
        new_metadata = [path.relative_to(staged_assets).as_posix()
                        for path in staged_assets.rglob("*")
                        if path.is_file() and path.suffix in {".json", ".md"}
                        and path.relative_to(staged_assets) not in frozen]
        if new_metadata:
            raise ValueError(f"Generators created unreviewed source metadata: {new_metadata}")
        report["validation"] = json.loads(run_tool("validate_materials.py", staged_assets))
        if report["validation"]["errors"]:
            raise ValueError("Generated PDFs do not match frozen source evidence")
        pdfs = sorted(staged_assets.rglob("*.pdf"))
        report["pdfs"] = []
        for pdf in pdfs:
            relative = pdf.relative_to(staged_assets)
            # Publication leaves every original JSON/Markdown byte untouched.
            target = assets_root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_suffix(".pdf.tmp")
            shutil.copyfile(pdf, temporary)
            temporary.replace(target)
            report["pdfs"].append({"path": relative.as_posix(), "sha256": digest(target.read_bytes())})
        # Check the actual paths consumed by tests and the Agent, including inventory.
        report["published_validation"] = json.loads(run_tool("validate_materials.py", assets_root))
        for relative, before in frozen.items():
            if (assets_root / relative).read_bytes() != before:
                raise ValueError(f"Frozen source changed: {relative}")
        report["source_metadata_unchanged"] = True
        report["frozen_source_files"] = len(frozen)
        report["status"] = "passed"
        report["metadata_change_counts"] = {
            kind: sum(change["kind"] == kind for change in report["metadata_changes"])
            for kind in ["serialization_only", "json_semantics", "source_text"]
        }
        return report
    except Exception as error:
        report.update({"status": "failed", "error": str(error), "diagnostic_build_root": str(build_root)})
        raise
    finally:
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if report["status"] == "passed":
            shutil.rmtree(build_root)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets-root", type=Path, default=LAB_ROOT / "assets")
    parser.add_argument("--generated-root", type=Path, default=LAB_ROOT / ".generated")
    args = parser.parse_args()
    report = generate(args.assets_root, args.generated_root)
    summary = {key: report[key] for key in ["status", "frozen_source_files", "source_metadata_unchanged", "metadata_change_counts"]}
    summary.update(report["published_validation"])
    summary["report"] = str(args.generated_root / "materials-report.json")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
