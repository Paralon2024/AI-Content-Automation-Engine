import json
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

router = APIRouter(prefix="/api/config", tags=["config"])

# Stored beside the project files. In Docker, the /app bind mount makes this
# file persistent on the host and keeps the key out of environment variables.
CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.json"


def _load() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    try:
        parsed = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        return parsed if isinstance(parsed, dict) else {}
    except (OSError, json.JSONDecodeError):
        # A damaged config file should not prevent the user from saving a new key.
        return {}


def _save(data: dict[str, Any]) -> None:
    temp_path = CONFIG_PATH.with_name(f"{CONFIG_PATH.name}.tmp")
    try:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        temp_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        os.replace(temp_path, CONFIG_PATH)
    except OSError as exc:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass
        reason = exc.strerror or str(exc)
        raise HTTPException(
            status_code=500,
            detail=f"Cannot write {CONFIG_PATH.name}: {reason}",
        ) from exc


def get_gemini_key() -> str | None:
    env_key = os.getenv("GEMINI_API_KEY")
    if env_key:
        return env_key
    value = _load().get("gemini_api_key")
    return value if isinstance(value, str) and value else None


class KeyPayload(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    key: str = Field(min_length=1)


@router.get("/gemini-key")
def check_gemini_key() -> dict[str, str | bool | None]:
    key = get_gemini_key()
    if os.getenv("GEMINI_API_KEY"):
        source: str | None = "env"
    elif key:
        source = "file"
    else:
        source = None
    return {"configured": bool(key), "source": source}


@router.post("/gemini-key")
def set_gemini_key(payload: KeyPayload) -> dict[str, bool]:
    key = payload.key.strip()
    if not key:
        raise HTTPException(status_code=400, detail="Key cannot be empty")

    data = _load()
    data["gemini_api_key"] = key
    _save(data)

    # GeminiBase reads this value when a client is created.
    os.environ["GEMINI_API_KEY"] = key
    return {"ok": True}


@router.delete("/gemini-key")
def delete_gemini_key() -> dict[str, bool]:
    data = _load()
    data.pop("gemini_api_key", None)
    _save(data)
    os.environ.pop("GEMINI_API_KEY", None)
    return {"ok": True}
