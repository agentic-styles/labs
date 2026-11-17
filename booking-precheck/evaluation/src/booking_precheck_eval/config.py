from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


SUITES = ("rule", "document", "business")


@dataclass(frozen=True)
class SuiteCommand:
    args: tuple[str, ...]
    timeout_seconds: float = 120.0


@dataclass(frozen=True)
class SystemConfig:
    name: str
    command: tuple[str, ...]
    cwd: Path
    suites: dict[str, SuiteCommand]
    env: dict[str, str] = field(default_factory=dict)
    env_file: Path | None = None


@dataclass(frozen=True)
class HarnessConfig:
    path: Path
    assets_dir: Path
    output_dir: Path
    systems: dict[str, SystemConfig]
    repeat: int = 1


def _resolve(base: Path, value: str) -> Path:
    candidate = Path(value)
    return candidate.resolve() if candidate.is_absolute() else (base / candidate).resolve()


def load_config(path: str | Path) -> HarnessConfig:
    config_path = Path(path).resolve()
    raw: dict[str, Any] = json.loads(config_path.read_text(encoding="utf-8"))
    base = config_path.parent
    assets_dir = _resolve(base, raw["assets_dir"])
    if not (assets_dir / "policy_snapshot.json").is_file():
        raise ValueError(f"assets_dir is not a Booking Precheck asset bundle: {assets_dir}")
    repeat = int(raw.get("repeat", 1))
    if repeat < 1:
        raise ValueError("repeat must be at least 1")

    systems: dict[str, SystemConfig] = {}
    for name, item in raw.get("systems", {}).items():
        command = tuple(str(part) for part in item.get("command", []))
        if not command:
            raise ValueError(f"system {name!r} must define a command")
        suites = {
            suite: SuiteCommand(
                args=tuple(str(part) for part in suite_item.get("args", [])),
                timeout_seconds=float(suite_item.get("timeout_seconds", item.get("timeout_seconds", 120))),
            )
            for suite, suite_item in item.get("suites", {}).items()
        }
        unknown = set(suites) - set(SUITES)
        if unknown:
            raise ValueError(f"system {name!r} has unknown suites: {sorted(unknown)}")
        systems[name] = SystemConfig(
            name=name,
            command=command,
            cwd=_resolve(base, item.get("cwd", ".")),
            suites=suites,
            env={str(key): str(value) for key, value in item.get("env", {}).items()},
            env_file=_resolve(base, item["env_file"]) if item.get("env_file") else None,
        )
    if not systems:
        raise ValueError("at least one system must be configured")
    return HarnessConfig(
        path=config_path,
        assets_dir=assets_dir,
        output_dir=_resolve(base, raw.get("output_dir", "../reports")),
        systems=systems,
        repeat=repeat,
    )
