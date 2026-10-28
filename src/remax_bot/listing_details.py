from __future__ import annotations

import json
from collections.abc import Mapping


def _clean(value) -> str:
    return " ".join(str(value or "").split())


def normalize_details(value) -> dict[str, str]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}
    if isinstance(value, Mapping):
        pairs = value.items()
    elif isinstance(value, (list, tuple)):
        pairs = value
    else:
        return {}
    cleaned: dict[str, str] = {}
    for pair in pairs:
        try:
            key, raw_value = pair
        except (TypeError, ValueError):
            continue
        key = _clean(key)
        detail_value = _clean(raw_value)
        if key and detail_value:
            cleaned[key] = detail_value
    return cleaned


def details_to_json(value) -> str:
    return json.dumps(
        normalize_details(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def details_text(value) -> str:
    details = normalize_details(value)
    return " ".join(
        f"{key} {details[key]}" for key in sorted(details, key=str.casefold)
    )


def display_address(item) -> str:
    full_address = _clean(getattr(item, "full_address", ""))
    if full_address:
        return full_address
    parts = []
    for field in ("province", "district", "neighborhood", "street", "complex_name"):
        value = _clean(getattr(item, field, ""))
        if value and value.casefold() not in {part.casefold() for part in parts}:
            parts.append(value)
    return " / ".join(parts) or _clean(getattr(item, "location", ""))
