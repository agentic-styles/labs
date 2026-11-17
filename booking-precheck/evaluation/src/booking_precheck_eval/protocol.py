from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
from pathlib import Path
from typing import TextIO

from booking_precheck_contracts import AgentManifest, EvaluationRequest, EvaluationResponse


def _env_file(path: Path | None) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path or not path.is_file():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.removeprefix("export ").split("=", 1)
        values[key.strip()] = value.strip().strip("'\"")
    return values


class JsonlAgentClient:
    def __init__(self, manifest_path: str | Path):
        self.manifest_path = Path(manifest_path).resolve()
        self.base = self.manifest_path.parent
        self.manifest = AgentManifest.model_validate_json(self.manifest_path.read_text(encoding="utf-8"))
        self.process: subprocess.Popen[str] | None = None
        self.stderr_lines: list[str] = []
        self.stdout_lines: queue.Queue[str | None] = queue.Queue()

    @property
    def cwd(self) -> Path:
        path = Path(self.manifest.cwd)
        return path.resolve() if path.is_absolute() else (self.base / path).resolve()

    def start(self) -> None:
        if self.process and self.process.poll() is None:
            return
        env_path = None
        if self.manifest.env_file:
            candidate = Path(self.manifest.env_file)
            env_path = candidate if candidate.is_absolute() else self.base / candidate
        env = {**os.environ, **_env_file(env_path), **self.manifest.env}
        process = subprocess.Popen(
            self.manifest.command,
            cwd=self.cwd,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        assert process.stdout and process.stderr
        self.process = process
        self.stderr_lines = []
        self.stdout_lines = queue.Queue()
        threading.Thread(
            target=self._drain_stdout,
            args=(process.stdout, self.stdout_lines),
            daemon=True,
        ).start()
        threading.Thread(target=self._drain_stderr, args=(process.stderr,), daemon=True).start()

    @staticmethod
    def _drain_stdout(stream: TextIO, lines: queue.Queue[str | None]) -> None:
        try:
            for line in stream:
                lines.put(line)
        finally:
            lines.put(None)

    def _drain_stderr(self, stream: TextIO) -> None:
        for line in stream:
            self.stderr_lines.append(line.rstrip())

    def invoke(self, request: EvaluationRequest) -> EvaluationResponse:
        self.start()
        assert self.process and self.process.stdin and self.process.stdout
        if self.process.poll() is not None:
            raise RuntimeError(f"Agent process exited before request: {self.process.returncode}")
        self.process.stdin.write(request.model_dump_json() + "\n")
        self.process.stdin.flush()
        try:
            line = self.stdout_lines.get(timeout=self.manifest.case_timeout_seconds)
        except queue.Empty:
            raise TimeoutError(
                f"Agent did not answer {request.request_id} within {self.manifest.case_timeout_seconds}s"
            ) from None
        if line is None:
            raise RuntimeError(
                f"Agent closed stdout; return_code={self.process.poll()}, stderr={self.stderr_lines[-5:]}"
            )
        response = EvaluationResponse.model_validate_json(line)
        if response.request_id != request.request_id:
            raise ValueError(
                f"Response request_id mismatch: expected={request.request_id}, actual={response.request_id}"
            )
        return response

    def close(self) -> None:
        if not self.process:
            return
        if self.process.stdin:
            self.process.stdin.close()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        self.process = None

    def __enter__(self) -> "JsonlAgentClient":
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()
