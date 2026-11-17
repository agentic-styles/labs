from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def apply_mutations(document: dict[str, Any], mutations: list[dict[str, Any]]) -> dict[str, Any]:
    result = copy.deepcopy(document)
    for mutation in mutations:
        tokens = [token.replace("~1", "/").replace("~0", "~") for token in mutation["path"].split("/")[1:]]
        parent: Any = result
        for token in tokens[:-1]:
            parent = parent[int(token)] if isinstance(parent, list) else parent[token]
        key = tokens[-1]
        op = mutation["op"]
        if op == "remove":
            if isinstance(parent, list):
                parent.pop(int(key))
            else:
                parent.pop(key, None)
        elif op in {"add", "replace"}:
            if isinstance(parent, list):
                index = int(key)
                if op == "add":
                    parent.insert(index, copy.deepcopy(mutation["value"]))
                else:
                    parent[index] = copy.deepcopy(mutation["value"])
            else:
                parent[key] = copy.deepcopy(mutation["value"])
        else:
            raise ValueError(f"Unsupported mutation operation: {op}")
    return result


def materialize_business_steps(case_path: Path) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    definition = load_json(case_path)
    base = load_json((case_path.parent / definition["base_fixture_path"]).resolve())
    states: dict[str, dict[str, Any]] = {}
    materialized = []
    for step in definition["steps"]:
        source = base if step["derives_from"] == "BASE_FIXTURE" else states[step["derives_from"]]
        current = apply_mutations(source, step.get("mutations", []))
        current["case_id"] = definition["case_id"]
        states[step["step_id"]] = current
        materialized.append((step, current))
    return materialized


def apply_policy_variant(snapshot: dict[str, Any], variant: dict[str, Any] | None) -> dict[str, Any]:
    result = copy.deepcopy(snapshot)
    if not variant:
        return result
    result["snapshot_id"] = variant.get("snapshot_id", result["snapshot_id"])
    for override in variant.get("rule_overrides", []):
        rule = next(item for item in result["rules"] if item["rule_id"] == override["rule_id"])
        for key, value in override.items():
            if key == "rule_id":
                continue
            if isinstance(value, dict) and isinstance(rule.get(key), dict):
                rule[key].update(copy.deepcopy(value))
            else:
                rule[key] = copy.deepcopy(value)
    return result

