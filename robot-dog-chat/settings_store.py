from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
SETTINGS_PATH = BASE_DIR / "settings.json"
ENV_PATH = BASE_DIR / ".env"

DEFAULT_API_URL = "https://robot-dog-api.eolivermoland.workers.dev"
DEFAULT_MODEL = "@cf/google/gemma-4-26b-a4b-it"
DEFAULT_SYSTEM_PROMPT = (
    "Du er Bingo, en nysgjerrig og vennlig robothund. "
    "Svar kort, morsomt og på norsk. Maks én kort setning, cirka 12 ord. "
    "Ikke bruk emoji."
)

DEFAULTS: dict[str, Any] = {
    "api": {
        "base_url": DEFAULT_API_URL,
    },
    "bot": {
        "name": "Bingo",
        "personality": "Nysgjerrig valp",
        "system_prompt": DEFAULT_SYSTEM_PROMPT,
        "model": DEFAULT_MODEL,
        "temperature": 0.8,
        "max_tokens": 80,
        "history_turns": 6,
    },
    "voice": {
        "profile": "min_stemme",
        "exaggeration": 0.5,
        "cfg_weight": 0.5,
        "temperature": 0.8,
        "repetition_penalty": 1.2,
        "top_p": 1.0,
        "lang_code": "no",
        "max_tokens": 1000,
    },
    "audio": {
        "input_device": None,
        "output_device": None,
        "mode": "vad",
        "silence_threshold_db": -40.0,
        "silence_ms": 900,
        "max_record_s": 20,
        "pre_roll_ms": 300,
        "trim_silence": True,
    },
}


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(base)
    for key, value in override.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_settings() -> dict[str, Any]:
    if not SETTINGS_PATH.exists():
        return copy.deepcopy(DEFAULTS)

    try:
        raw = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return copy.deepcopy(DEFAULTS)

    if not isinstance(raw, dict):
        return copy.deepcopy(DEFAULTS)
    return deep_merge(DEFAULTS, raw)


def save_settings(settings: dict[str, Any]) -> None:
    SETTINGS_PATH.write_text(
        json.dumps(settings, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    try:
        os.chmod(SETTINGS_PATH, 0o600)
    except OSError:
        pass


def read_env() -> dict[str, str]:
    values: dict[str, str] = {}
    if not ENV_PATH.exists():
        return values

    for raw_line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def load_token() -> str:
    values = read_env()
    token = values.get("ROBOT_TOKEN", "").strip()
    if token and token != "CHANGE_ME":
        return token

    for candidate in (
        BASE_DIR / ".robot_token",
        Path.home() / "robot-dog-api" / ".robot_token",
    ):
        if candidate.exists():
            token = candidate.read_text(encoding="utf-8").strip()
            if token:
                return token
    return ""


def save_env(base_url: str, token: str) -> None:
    content = (
        f"API_URL={base_url.strip()}\n"
        f"ROBOT_TOKEN={token.strip()}\n"
    )
    ENV_PATH.write_text(content, encoding="utf-8")
    try:
        os.chmod(ENV_PATH, 0o600)
    except OSError:
        pass
