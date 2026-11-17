from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .catalog import EvaluationCase
from .config import SuiteCommand, SystemConfig


@dataclass(frozen=True)
class Invocation:
    payload: Any | None
    elapsed_ms: int
    command: tuple[str, ...]
    return_code: int
    stdout: str
    stderr: str
    error: str | None = None


class CliAdapter:
    """Invoke a system as a black box and parse one JSON response from stdout."""

    def __init__(self, system: SystemConfig, assets_dir: Path):
        self.system = system
        self.assets_dir = assets_dir

    def _configured_env(self) -> dict[str, str]:
        values: dict[str, str] = {}
        path = self.system.env_file
        if path and path.is_file():
            for raw_line in path.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.removeprefix("export ").split("=", 1)
                values[key.strip()] = value.strip().strip("'\"")
        return {**values, **self.system.env}

    def invoke(self, case: EvaluationCase) -> Invocation:
        suite_config: SuiteCommand = self.system.suites[case.suite]
        values = {
            "case_id": case.case_id,
            "pack_id": case.case_id,
            "stage_id": case.stage_id or "S1",
        }
        command = tuple(self.system.command) + tuple(part.format(**values) for part in suite_config.args)
        env = {
            **os.environ,
            "BOOKING_PRECHECK_ASSETS": str(self.assets_dir),
            **self._configured_env(),
        }
        started = time.perf_counter()
        try:
            completed = subprocess.run(
                command,
                cwd=self.system.cwd,
                env=env,
                text=True,
                capture_output=True,
                timeout=suite_config.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            elapsed = int((time.perf_counter() - started) * 1000)
            return Invocation(None, elapsed, command, -1, error.stdout or "", error.stderr or "", "TIMEOUT")
        except OSError as error:
            elapsed = int((time.perf_counter() - started) * 1000)
            return Invocation(None, elapsed, command, -1, "", "", f"{type(error).__name__}: {error}")
        elapsed = int((time.perf_counter() - started) * 1000)
        if completed.returncode != 0:
            return Invocation(
                None, elapsed, command, completed.returncode, completed.stdout, completed.stderr,
                f"PROCESS_EXIT_{completed.returncode}",
            )
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError as error:
            return Invocation(
                None, elapsed, command, completed.returncode, completed.stdout, completed.stderr,
                f"INVALID_JSON: {error}",
            )
        return Invocation(payload, elapsed, command, completed.returncode, completed.stdout, completed.stderr)
