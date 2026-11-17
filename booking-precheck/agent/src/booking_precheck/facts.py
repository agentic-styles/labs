from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any

MISSING = object()


def _path_tokens(path: str) -> list[str | int]:
    tokens: list[str | int] = []
    for part in path.split("."):
        match = re.fullmatch(r"([A-Za-z0-9_*]+)((?:\[\d+\])*)", part)
        if not match:
            return []
        tokens.append(match.group(1))
        tokens.extend(int(index) for index in re.findall(r"\[(\d+)\]", match.group(2)))
    return tokens


def resolve(data: Any, path: str) -> list[Any]:
    values = [data]
    for token in _path_tokens(path):
        next_values: list[Any] = []
        for value in values:
            if token == "*":
                if isinstance(value, list):
                    next_values.extend(value)
                elif isinstance(value, dict):
                    next_values.extend(value.values())
            elif isinstance(token, int) and isinstance(value, list) and token < len(value):
                next_values.append(value[token])
            elif isinstance(value, dict) and token in value:
                next_values.append(value[token])
        values = next_values
        if not values:
            return [MISSING]
    return values


def first(data: Any, path: str) -> Any:
    values = resolve(data, path)
    return values[0] if values else MISSING


def canonical(value: Any, normalizations: list[str]) -> Any:
    for mode in normalizations:
        if value is MISSING:
            return value
        if mode == "UN_NUMBER_CANONICAL":
            value = re.sub(r"[^0-9]", "", str(value))
            value = f"UN{value}"
        elif mode == "PSN_CANONICAL":
            value = " ".join(str(value).upper().split())
        elif mode == "DATE_TO_ISO":
            value = _as_date(value).isoformat()
        elif mode == "UNIT_TO_KG":
            value = float(value)
    return value


def _as_date(value: Any) -> date:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()


def _subtract_months(value: date, months: int) -> date:
    year = value.year - (months // 12)
    month = value.month - (months % 12)
    if month <= 0:
        year -= 1
        month += 12
    month_lengths = [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    return date(year, month, min(value.day, month_lengths[month - 1]))


def _working_days_between(start: date, end: date) -> int:
    count = 0
    cursor = start + timedelta(days=1)
    while cursor <= end:
        if cursor.weekday() < 5:
            count += 1
        cursor += timedelta(days=1)
    return count


def evaluate_predicate(data: dict[str, Any], predicate: dict[str, Any]) -> bool:
    values = resolve(data, predicate["fact"])
    op = predicate["operator"]
    normalizations = predicate.get("normalization", [])
    compare = first(data, predicate["compare_to_fact"]) if predicate.get("compare_to_fact") else predicate.get("value", MISSING)

    if op == "MISSING":
        return all(value is MISSING or value is None or value == "" for value in values)
    if op == "EXISTS":
        return any(value is not MISSING and value is not None and value != "" for value in values)
    if op == "NOT_IN":
        expected = predicate.get("value", [])
        return all(value is MISSING or value not in expected for value in values)

    value = values[0]
    if value is MISSING or value is None or compare is MISSING or compare is None:
        return False
    left = canonical(value, normalizations)
    right = canonical(compare, normalizations)
    if op == "EQUALS": return left == right
    if op == "NOT_EQUALS": return left != right
    if op == "IN": return left in right
    if op == "CONTAINS": return right in left
    if op == "MATCHES": return re.search(str(right), str(left)) is not None
    if op == "LESS_THAN": return left < right
    if op == "LESS_THAN_OR_EQUAL": return left <= right
    if op == "GREATER_THAN": return left > right
    if op == "GREATER_THAN_OR_EQUAL": return left >= right
    if op == "PERCENT_DIFFERENCE_GREATER_THAN":
        return abs(float(left) - float(right)) / abs(float(right)) * 100 > float(predicate["value"])
    if op == "OLDER_THAN_MONTHS":
        return _as_date(left) < _subtract_months(_as_date(right), int(predicate["value"]))
    if op == "WORKING_DAYS_BEFORE":
        return _working_days_between(_as_date(left), _as_date(right)) < int(predicate["value"])
    if op == "DATE_BETWEEN":
        current = _as_date(left); low, high = predicate["value"]
        return _as_date(low) <= current <= _as_date(high)
    if op == "DATE_AFTER": return _as_date(left) > _as_date(right)
    if op == "DATE_BEFORE": return _as_date(left) < _as_date(right)
    raise ValueError(f"Unsupported operator: {op}")


def evaluate_condition(data: dict[str, Any], condition: dict[str, Any]) -> bool:
    if "all" in condition:
        return all(evaluate_condition(data, item) for item in condition["all"])
    if "any" in condition:
        return any(evaluate_condition(data, item) for item in condition["any"])
    return evaluate_predicate(data, condition)


def predicate_fact_paths(condition: dict[str, Any]) -> list[str]:
    if "all" in condition:
        return [path for item in condition["all"] for path in predicate_fact_paths(item)]
    if "any" in condition:
        return [path for item in condition["any"] for path in predicate_fact_paths(item)]
    paths = [condition["fact"]]
    if condition.get("compare_to_fact"):
        paths.append(condition["compare_to_fact"])
    return paths
