
from typing import List, Tuple

import yaml

def compile_persona_yaml(yaml_str: str) -> Tuple[str, List[str]]:
    issues: List[str] = []
    if not yaml_str.strip():
        return ("You are Katamari, a helpful, precise assistant.", issues)
    try:
        data = yaml.safe_load(yaml_str) or {}
    except Exception as e:
        return ("You are Katamari, a helpful, precise assistant.", [f"YAML parse error: {e}"])

    name = str(data.get("name","Katamari"))
    style = str(data.get("style","calm, concise"))
    forbid = data.get("forbid",[]) or []
    notes = str(data.get("notes","")).strip()

    if not isinstance(forbid, list):
        issues.append("`forbid` must be a list of strings.")
        forbid = [str(forbid)]

    sys = [f"You are {name}. Maintain {style} tone.", "Be accurate, helpful, and safe."]
    if forbid:
        sys.append("Avoid the following strictly: " + ", ".join(map(str,forbid)))
    if notes:
        sys.append("Additional notes:\n" + notes)
    return ("\n\n".join(sys), issues)
