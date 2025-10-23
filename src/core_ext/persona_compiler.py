import json
import re
from functools import lru_cache
from pathlib import Path
from typing import List, Tuple

import yaml

_FORBIDDEN_PATTERNS_PATH = (
    Path(__file__).resolve().parents[2] / "config" / "persona_forbidden_patterns.json"
)


@lru_cache(maxsize=1)
def _load_forbidden_patterns() -> List[re.Pattern[str]]:
    try:
        with _FORBIDDEN_PATTERNS_PATH.open("r", encoding="utf-8") as handle:
            raw_patterns = json.load(handle)
    except FileNotFoundError:
        return []
    except Exception:
        return []

    patterns: List[re.Pattern[str]] = []
    if isinstance(raw_patterns, list):
        for entry in raw_patterns:
            if isinstance(entry, str) and entry:
                try:
                    patterns.append(re.compile(entry))
                except re.error:
                    continue
    return patterns


def _collect_forbidden_terms(values: List[str]) -> List[str]:
    seen: dict[str, str] = {}
    for pattern in _load_forbidden_patterns():
        for value in values:
            for match in pattern.finditer(value):
                term = match.group(0).strip()
                if not term:
                    continue
                key = term.casefold()
                if key not in seen:
                    normalized = term.casefold()
                    seen[key] = normalized if normalized else term
    return sorted(seen.values(), key=str.casefold)


def compile_persona_yaml(yaml_str: str) -> Tuple[str, List[str]]:
    issues: List[str] = []
    if not yaml_str.strip():
        return ("You are Katamari, a helpful, precise assistant.", issues)
    try:
        data = yaml.safe_load(yaml_str) or {}
    except Exception as e:
        return (
            "You are Katamari, a helpful, precise assistant.",
            [f"YAML parse error: {e}"],
        )

    name = str(data.get("name", "Katamari"))
    style = str(data.get("style", "calm, concise"))
    forbid = data.get("forbid", []) or []
    notes = str(data.get("notes", "")).strip()

    if not isinstance(forbid, list):
        issues.append("`forbid` must be a list of strings.")
        forbid = [str(forbid)]
    else:
        forbid = [str(item) for item in forbid]

    forbidden_terms = _collect_forbidden_terms([name, style, notes] + forbid)
    if forbidden_terms:
        issues.append("Forbidden terms detected: " + ", ".join(forbidden_terms) + ".")

    sys = [
        f"You are {name}. Maintain {style} tone.",
        "Be accurate, helpful, and safe.",
    ]
    if forbid:
        sys.append("Avoid the following strictly: " + ", ".join(forbid))
    if notes:
        sys.append("Additional notes:\n" + notes)
    return ("\n\n".join(sys), issues)
