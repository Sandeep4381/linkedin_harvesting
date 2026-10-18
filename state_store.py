"""Read optional JSON state without failing on a new or emptied file."""
import json


def read_json_object(path):
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8-sig").strip()
    if not text:
        print(f"State file {path.name} is empty; starting with an empty object.", flush=True)
        return {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Invalid JSON in {path.name}, line {exc.lineno}, column {exc.colno}. "
            "File preserved; correct its JSON before restarting."
        ) from exc
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object in {path.name}; file preserved")
    return data
