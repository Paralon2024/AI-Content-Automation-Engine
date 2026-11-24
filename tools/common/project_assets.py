import shutil
import uuid
from pathlib import Path

AssetBackups = list[tuple[Path, Path]]


def stage_derived_assets(idea_dir: Path) -> AssetBackups:
    """Move generated assets aside while a replacement script is being committed.

    The original files remain recoverable until the script and its metadata have
    both been saved successfully.
    """
    transaction_id = uuid.uuid4().hex
    candidates = [
        idea_dir / "audios",
        idea_dir / "videos",
        idea_dir / "editions",
        *sorted(idea_dir.glob("*.mp4")),
    ]
    backups: AssetBackups = []

    try:
        for source in candidates:
            if not source.exists():
                continue
            backup = idea_dir / f".{source.name}.{transaction_id}.backup"
            source.replace(backup)
            backups.append((backup, source))
    except Exception:
        restore_derived_assets(backups)
        raise

    return backups


def restore_derived_assets(backups: AssetBackups) -> None:
    """Restore staged assets after a failed script replacement."""
    for backup, original in reversed(backups):
        if not backup.exists():
            continue
        if original.is_symlink() or original.is_file():
            original.unlink(missing_ok=True)
        elif original.is_dir():
            shutil.rmtree(original)
        backup.replace(original)


def discard_derived_asset_backups(backups: AssetBackups) -> None:
    """Remove old generated assets after the replacement script is committed."""
    for backup, _ in backups:
        try:
            if backup.is_symlink() or backup.is_file():
                backup.unlink(missing_ok=True)
            elif backup.is_dir():
                shutil.rmtree(backup, ignore_errors=True)
        except OSError:
            # Backups are hidden and are never picked up as current project assets.
            pass
