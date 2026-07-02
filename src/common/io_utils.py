import json
from pathlib import Path


def ensure_parent_dir(path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def save_json(path: str, data: dict) -> None:
    ensure_parent_dir(path)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()