import mimetypes
import shutil
import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

router = APIRouter(prefix="/api/music", tags=["music"])

_LIBRARY = Path("flows/image_content_generator/resource/bg-music").resolve()

_AUDIO_EXTENSIONS = {".mp3", ".wav", ".ogg", ".aac", ".m4a", ".flac"}
_MAX_AUDIO_UPLOAD_BYTES = 100 * 1024 * 1024


def _safe_path(rel: str) -> Path:
    root = _LIBRARY.resolve()
    target = (root / rel).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise HTTPException(400, "Invalid path") from exc
    return target


def _build_tree(path: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for p in sorted(path.iterdir(), key=lambda x: (x.is_file(), x.name.lower())):
        if p.name.startswith(".music-upload-"):
            continue
        rel = str(p.relative_to(_LIBRARY))
        if p.is_dir():
            items.append({"type": "dir", "name": p.name, "path": rel, "children": _build_tree(p)})
        elif p.suffix.lower() in _AUDIO_EXTENSIONS:
            items.append({"type": "file", "name": p.name, "path": rel, "size": p.stat().st_size})
    return items


@router.get("")
def list_library() -> list[dict[str, Any]]:
    if not _LIBRARY.exists():
        return []
    return _build_tree(_LIBRARY)


@router.post("/upload")
async def upload_tracks(
    files: list[UploadFile] = File(...),
    folder: str = Form(""),
) -> dict[str, list[str]]:
    dest_dir = _safe_path(folder) if folder else _LIBRARY.resolve()
    dest_dir.mkdir(parents=True, exist_ok=True)

    names: list[str] = []
    for file in files:
        name = Path((file.filename or "track.mp3").replace("\\", "/")).name
        if Path(name).suffix.lower() not in _AUDIO_EXTENSIONS:
            raise HTTPException(415, f"Unsupported audio format: {name}")
        names.append(name)

    # Reject duplicate names before writing; otherwise the last copy would
    # silently overwrite the earlier one in the same multi-file request.
    normalized_names = [name.casefold() for name in names]
    if len(set(normalized_names)) != len(normalized_names):
        raise HTTPException(409, "The upload contains duplicate filenames")

    staging_dir = Path(tempfile.mkdtemp(prefix=".music-upload-", dir=dest_dir))
    staged_files: list[tuple[Path, Path]] = []
    installed_targets: list[Path] = []
    backups: list[tuple[Path, Path]] = []
    cleanup_staging = True

    try:
        # Read and validate every file before replacing any existing track.
        for index, (file, name) in enumerate(zip(files, names)):
            staged_path = staging_dir / f"upload-{index:04d}{Path(name).suffix.lower()}"
            total_size = 0
            with staged_path.open("wb") as destination:
                while chunk := await file.read(1024 * 1024):
                    total_size += len(chunk)
                    if total_size > _MAX_AUDIO_UPLOAD_BYTES:
                        raise HTTPException(
                            413, f"Audio file is too large (100 MB maximum): {name}"
                        )
                    destination.write(chunk)
            staged_files.append((staged_path, dest_dir / name))

        # Install all files as one transaction. Existing tracks are backed up
        # inside the staging directory and restored if any replacement fails.
        for index, (staged_path, target) in enumerate(staged_files):
            if target.exists() and not target.is_file():
                raise HTTPException(409, f"An item with this name is not a file: {target.name}")

            if target.exists():
                backup = staging_dir / f"backup-{index:04d}"
                target.replace(backup)
                backups.append((backup, target))

            staged_path.replace(target)
            installed_targets.append(target)

    except Exception as original_error:
        rollback_errors: list[str] = []
        for target in reversed(installed_targets):
            try:
                target.unlink(missing_ok=True)
            except OSError as exc:
                rollback_errors.append(f"could not remove {target.name}: {exc}")

        for backup, target in reversed(backups):
            if backup.exists():
                try:
                    backup.replace(target)
                except OSError as exc:
                    rollback_errors.append(f"could not restore {target.name}: {exc}")

        if rollback_errors:
            # Keep the hidden staging folder, including any remaining backups,
            # so an operator can recover the old tracks instead of losing them.
            cleanup_staging = False
            raise RuntimeError(
                "Music upload failed and rollback was incomplete. "
                f"Recovery files were preserved in {staging_dir}. "
                + "; ".join(rollback_errors)
            ) from original_error
        raise
    finally:
        if cleanup_staging:
            shutil.rmtree(staging_dir, ignore_errors=True)

    uploaded = [str(target.relative_to(_LIBRARY)) for _, target in staged_files]
    return {"uploaded": uploaded}


@router.post("/folder")
def create_folder(name: str = Form(...), parent: str = Form("")) -> dict[str, str]:
    if not name.strip() or name in {".", ".."}:
        raise HTTPException(422, "Folder name is required")
    target = _safe_path(f"{parent}/{name}" if parent else name)
    target.mkdir(parents=True, exist_ok=True)
    return {"path": str(target.relative_to(_LIBRARY))}


@router.get("/{path:path}/stream")
def stream_track(path: str) -> FileResponse:
    target = _safe_path(path)
    if not target.is_file():
        raise HTTPException(404, "Track not found")
    media_type, _ = mimetypes.guess_type(target.name)
    return FileResponse(str(target), media_type=media_type or "application/octet-stream")


@router.delete("/{path:path}")
def delete_entry(path: str) -> dict[str, str]:
    if not path.strip():
        raise HTTPException(400, "Cannot delete the music library root")
    target = _safe_path(path)
    if not target.exists():
        raise HTTPException(404, "Not found")
    if target.is_dir():
        shutil.rmtree(target)
    else:
        target.unlink()
    return {"deleted": path}
