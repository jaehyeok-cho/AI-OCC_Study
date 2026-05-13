from __future__ import annotations

import json
import time
from pathlib import Path
from uuid import uuid4


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_ROOT / "OCCStudy" / "outputs"
UI_COMMAND_FILE = OUTPUT_DIR / "ui_command.json"


def write_ui_model_command(code: str) -> dict:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "request_id": f"{int(time.time() * 1000)}-{uuid4().hex}",
        "action": "model_tray",
        "code": code.strip().upper(),
        "created_at": time.time(),
    }
    tmp_path = UI_COMMAND_FILE.with_name(f"{UI_COMMAND_FILE.stem}.{payload['request_id']}.tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(UI_COMMAND_FILE)
    return payload


def read_ui_model_command() -> dict | None:
    if not UI_COMMAND_FILE.exists():
        return None
    try:
        return json.loads(UI_COMMAND_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
