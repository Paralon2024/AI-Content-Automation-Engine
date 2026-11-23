"""Local-only Hans4 character consistency and manual n8n handoff.

This router deliberately does not execute workflows, store API keys, or expose
an unauthenticated remote n8n proxy. Keep the development server on localhost.
"""
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api.routers.ideas import _store

router = APIRouter(prefix="/api/hans4", tags=["hans4"])

BASE = Path("flows/image_content_generator/out_short/ideas")
DRIVE_ID = re.compile(r"^[a-zA-Z0-9_-]{12,}$")


class CharacterBible(BaseModel):
    name: str = Field(default="", max_length=120)
    identity: str = Field(default="", max_length=2000)
    wardrobe: str = Field(default="", max_length=1000)
    style_rules: str = Field(
        default="2D hand-inked horror comic, teal and indigo ink, amber practical lighting, vertical 9:16; no words, watermarks or logos.",
        max_length=2000,
    )
    canonical_image_id: str = Field(default="", max_length=160)
    style_reference_folder_id: str = Field(default="", max_length=160)


class Scene(BaseModel):
    step: int = Field(ge=1, le=4)
    description: str = Field(min_length=15, max_length=3000)


class HandoffRequest(BaseModel):
    scenes: list[Scene] = Field(min_length=4, max_length=4)


def _path(idea_id: int) -> Path:
    if idea_id < 1 or idea_id > 999999:
        raise HTTPException(422, "Invalid idea ID")
    if not _store().get_by_id(idea_id):
        raise HTTPException(404, "Idea not found")
    return BASE / f"idea_{idea_id:06d}" / "hans4_character.json"


def _read(path: Path) -> CharacterBible:
    if not path.is_file():
        return CharacterBible()
    try:
        return CharacterBible.model_validate_json(path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        raise HTTPException(500, "Stored character bible is not readable") from exc


def _validate_drive_ids(bible: CharacterBible) -> None:
    for field in ("canonical_image_id", "style_reference_folder_id"):
        value = getattr(bible, field)
        if value and not DRIVE_ID.fullmatch(value):
            raise HTTPException(422, f"{field} must be a Google Drive file/folder ID")


@router.get("/ideas/{idea_id}/character", response_model=CharacterBible)
def get_character(idea_id: int) -> CharacterBible:
    return _read(_path(idea_id))


@router.put("/ideas/{idea_id}/character", response_model=CharacterBible)
def save_character(idea_id: int, bible: CharacterBible) -> CharacterBible:
    path = _path(idea_id)
    _validate_drive_ids(bible)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Atomic replacement prevents a partial JSON write from corrupting the bible.
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent,
            prefix=".hans4-", suffix=".tmp", delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(bible.model_dump_json(indent=2))
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return bible


@router.post("/ideas/{idea_id}/handoff")
def preview_handoff(idea_id: int, request: HandoffRequest) -> dict:
    """Return four exact n8n image subworkflow inputs, without executing media."""
    bible = _read(_path(idea_id))
    _validate_drive_ids(bible)
    if not bible.name.strip() or not bible.identity.strip():
        raise HTTPException(422, "Save character name and fixed identity first")
    if [scene.step for scene in request.scenes] != [1, 2, 3, 4]:
        raise HTTPException(422, "Scenes must be numbered 1, 2, 3, 4")
    results = []
    for scene in request.scenes:
        prompt = {
            "subject": scene.description,
            "environment": "Maintain the exact scene location and characters described.",
            "technical_specs": (
                f"{bible.style_rules} Protagonist: {bible.name}. "
                f"Locked physical identity: {bible.identity}. "
                f"Locked clothing: {bible.wardrobe}. "
                "Match the canonical image identity whenever the protagonist is visible. "
                "Do not add dialogue text, extra characters or unrelated objects."
            ),
        }
        results.append({
            "step": scene.step,
            "image_prompt": json.dumps(prompt, ensure_ascii=False),
            "folder_reference_id": bible.style_reference_folder_id,
            "filename_output": f"image_step{scene.step}",
            "folder_output_id": "",  # Fill with intended Drive output folder in n8n.
            "character_image_id": bible.canonical_image_id if scene.step > 1 else "",
            "character_bible": f"{bible.name}: {bible.identity}; wardrobe: {bible.wardrobe}",
        })
    return {
        "status": "manual_preview_only",
        "scene_count": 4,
        "requires_review": True,
        "generates_images": False,
        "publishes": False,
        "n8n_image_workflow_inputs": results,
    }
