from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from .catalog import discover_cases
from .config import SUITES, load_config
from .document_dataset import make_request
from .langfuse_eval import (
    DEFAULT_DATASET_NAME,
    get_langfuse_client,
    load_env_file,
    require_authenticated_client,
    run_langfuse_experiment,
    sync_dataset,
)
from .protocol import JsonlAgentClient
from .report import summarize, write_reports
from .runner import run_evaluation


def _csv(value: str | None) -> list[str] | None:
    return None if not value else [item.strip() for item in value.split(",") if item.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate Booking Precheck implementations as black boxes")
    subparsers = parser.add_subparsers(dest="action", required=True)

    validate = subparsers.add_parser("validate-config", help="Validate configuration and list discovered cases")
    validate.add_argument("--config", required=True)

    run = subparsers.add_parser("run", help="Run suites and write JSON, CSV and Markdown reports")
    run.add_argument("--config", required=True)
    run.add_argument("--systems", help="Comma-separated configured system names")
    run.add_argument("--suites", help="Comma-separated suites; defaults to suites configured for the selected systems")
    run.add_argument("--case-ids", help="Optional case IDs or DP-ID:stage selectors")
    run.add_argument("--repeat", type=int)
    run.add_argument("--output-dir")

    doctor = subparsers.add_parser("doctor", help="Validate an Agent manifest and run one protocol request")
    doctor.add_argument("--config", required=True)
    doctor.add_argument("--manifest", required=True)
    doctor.add_argument("--pack-id", default="DP-001")
    doctor.add_argument("--stage", default="S1")

    sync = subparsers.add_parser("sync-langfuse", help="Upsert the nine document stages into Langfuse")
    sync.add_argument("--config", required=True)
    sync.add_argument("--dataset-name", default=DEFAULT_DATASET_NAME)
    sync.add_argument("--env-file", default=".env")

    experiment = subparsers.add_parser("experiment", help="Run the Single-Agent over the Langfuse dataset")
    experiment.add_argument("--config", required=True)
    experiment.add_argument("--manifest", required=True)
    experiment.add_argument("--dataset-name", default=DEFAULT_DATASET_NAME)
    experiment.add_argument("--run-name", required=True)
    experiment.add_argument("--env-file", default=".env")
    args = parser.parse_args()
    config = load_config(args.config)
    configured_suites = sorted({
        suite
        for system in config.systems.values()
        for suite in system.suites
    })

    if args.action == "validate-config":
        payload = {
            "assets_dir": str(config.assets_dir),
            "systems": sorted(config.systems),
            "cases": {
                suite: len(discover_cases(config.assets_dir, suite))
                for suite in configured_suites
            },
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    if args.action == "doctor":
        request = make_request(config.assets_dir, args.pack_id, args.stage, request_id="doctor-protocol-check")
        with JsonlAgentClient(args.manifest) as client:
            response = client.invoke(request)
        print(response.model_dump_json(indent=2))
        if response.technical_status != "COMPLETED":
            raise SystemExit(1)
        return

    if args.action == "sync-langfuse":
        load_env_file(args.env_file)
        client = get_langfuse_client()
        require_authenticated_client(client)
        count = sync_dataset(client, config.assets_dir, args.dataset_name)
        client.flush()
        print(json.dumps({"dataset_name": args.dataset_name, "items_upserted": count}, indent=2))
        return

    if args.action == "experiment":
        load_env_file(args.env_file)
        client = get_langfuse_client()
        require_authenticated_client(client)
        result = run_langfuse_experiment(
            client,
            assets_dir=config.assets_dir,
            manifest_path=Path(args.manifest).resolve(),
            dataset_name=args.dataset_name,
            run_name=args.run_name,
        )
        print(result.format())
        return

    systems = _csv(args.systems)
    suites = _csv(args.suites) or configured_suites
    unknown_suites = set(suites) - set(SUITES)
    if unknown_suites:
        parser.error(f"unknown suites: {', '.join(sorted(unknown_suites))}")
    records = run_evaluation(
        config,
        systems=systems,
        suites=suites,
        case_ids=set(_csv(args.case_ids) or []),
        repeat=args.repeat,
    )
    default_run_dir = config.output_dir / datetime.now().strftime("%Y%m%d-%H%M%S")
    output_dir = Path(args.output_dir).resolve() if args.output_dir else default_run_dir
    paths = write_reports(records, output_dir)
    print(json.dumps({
        "summary": summarize(records),
        "reports": {name: str(path) for name, path in paths.items()},
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
