import concurrent.futures
from pathlib import Path
from typing import Any, AsyncGenerator, List

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse

from api import job_manager
from flows.image_content_generator.pipeline.pipeline import Pipeline
from flows.image_content_generator.pipeline.prompt_base.models import VideoScript
from flows.image_content_generator.pipeline.schemas import (
    IdeaRaw,
    ScriptFormData,
    State,
    VideoOrientation,
)
from tools.common.storage_folder import FolderStore

router = APIRouter(prefix="/api/ideas", tags=["ideas"])

_RESOURCE_BASE = Path("flows/image_content_generator/resource")
_SHORT_OUT = Path("flows/image_content_generator/out_short")
_LONG_OUT = Path("flows/image_content_generator/out_long")
# Job logging redirects process-wide stdout/stderr, so serialize background jobs.
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)


def _out(orientation: VideoOrientation) -> Path:
    return _SHORT_OUT if orientation == VideoOrientation.SHORT else _LONG_OUT


def _store(orientation: VideoOrientation = VideoOrientation.SHORT) -> FolderStore[IdeaRaw]:
    return FolderStore(ideas_dir=_out(orientation) / "ideas", model=IdeaRaw)


def _pipeline(orientation: VideoOrientation = VideoOrientation.SHORT) -> Pipeline:
    return Pipeline(
        out_base=_out(orientation),
        resource_base=_RESOURCE_BASE,
        orientation=orientation,
    )


@router.get("")
def list_ideas(
    orientation: VideoOrientation = VideoOrientation.SHORT,
) -> list[dict[str, Any]]:
    return [idea.model_dump() for idea in _store(orientation).get_all()]


@router.post("/generate")
def create_idea(
    orientation: VideoOrientation = VideoOrientation.SHORT,
) -> dict[str, Any]:
    st = _store(orientation)
    idea = st.add(IdeaRaw(id=st.get_next_id(), title="", category="", state=State.NEW))
    return idea.model_dump()


@router.get("/stream/{job_id}")
async def stream(job_id: str) -> StreamingResponse:
    async def _gen() -> AsyncGenerator[str, None]:
        async for msg in job_manager.stream_job(job_id):
            if msg == ": keep-alive":
                yield ": keep-alive\n\n"
            else:
                yield f"data: {msg}\n\n"

    return StreamingResponse(
        _gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/{idea_id}/script")
def generate_script(
    idea_id: int,
    form: ScriptFormData,
    orientation: VideoOrientation = VideoOrientation.SHORT,
) -> dict[str, str]:
    job_id = job_manager.create_job()
    p = _pipeline(orientation)
    _executor.submit(
        job_manager.run_in_job,
        job_id,
        lambda: p.step1_generate_story(idea_id, form),
    )
    return {"job_id": job_id}


@router.get("/{idea_id}/script")
def get_script(
    idea_id: int,
    orientation: VideoOrientation = VideoOrientation.SHORT,
) -> FileResponse:
    path = _out(orientation) / "ideas" / f"idea_{idea_id:06d}" / "script.json"
    if not path.is_file():
        raise HTTPException(404, "Script not found")
    return FileResponse(str(path), filename="script.json")



@router.get("/{idea_id}/videos")
def list_videos(
    idea_id: int,
    synced: bool = False,
    orientation: VideoOrientation = VideoOrientation.SHORT,
) -> list[str]:
    videos_dir = _out(orientation) / "ideas" / f"idea_{idea_id:06d}" / "videos"
    if not videos_dir.exists():
        return []
    files = [f.name for f in videos_dir.glob("scene_*.mp4")]
    files = [f for f in files if ("_synced" in f) == synced]
    return sorted(files)


@router.get("/{idea_id}/videos/{filename}")
def get_video_scene(
    idea_id: int,
    filename: str,
    orientation: VideoOrientation = VideoOrientation.SHORT,
) -> FileResponse:
    safe = Path(filename).name
    path = _out(orientation) / "ideas" / f"idea_{idea_id:06d}" / "videos" / safe
    if not path.is_file():
        raise HTTPException(404, "Video not found")
    return FileResponse(str(path), media_type="video/mp4")


@router.get("/{idea_id}/audios")
def list_audios(
    idea_id: int,
    orientation: VideoOrientation = VideoOrientation.SHORT,
) -> list[str]:
    audios_dir = _out(orientation) / "ideas" / f"idea_{idea_id:06d}" / "audios"
    if not audios_dir.exists():
        return []
    return sorted(f.name for f in audios_dir.glob("scene_*.wav"))


@router.get("/{idea_id}/audios/{filename}")
def get_audio(
    idea_id: int,
    filename: str,
    orientation: VideoOrientation = VideoOrientation.SHORT,
) -> FileResponse:
    safe = Path(filename).name
    path = _out(orientation) / "ideas" / f"idea_{idea_id:06d}" / "audios" / safe
    if not path.is_file():
        raise HTTPException(404, "Audio not found")
    return FileResponse(str(path), media_type="audio/wav")


@router.get("/{idea_id}/editions/{filename}")
def get_edition(
    idea_id: int,
    filename: str,
    orientation: VideoOrientation = VideoOrientation.SHORT,
) -> FileResponse:
    safe = Path(filename).name
    path = _out(orientation) / "ideas" / f"idea_{idea_id:06d}" / "editions" / safe
    if not path.is_file():
        raise HTTPException(404, "Edition not found")
    return FileResponse(str(path), media_type="video/mp4")


@router.post("/{idea_id}/script/upload")
async def upload_script(
    idea_id: int,
    file: UploadFile = File(...),
    title: str = "",
    orientation: VideoOrientation = VideoOrientation.SHORT,
) -> dict[str, Any]:
    content = await file.read(10 * 1024 * 1024 + 1)
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(413, "Script file is too large (10 MB maximum)")
    try:
        VideoScript.model_validate_json(content)
    except Exception as exc:
        raise HTTPException(422, f"Invalid script.json: {exc}")

    st = _store(orientation)
    idea = st.get_by_id(idea_id)
    if not idea:
        raise HTTPException(404, "Idea not found")

    idea_dir = _out(orientation) / "ideas" / f"idea_{idea_id:06d}"
    idea_dir.mkdir(parents=True, exist_ok=True)
    (idea_dir / "script.json").write_bytes(content)

    if title:
        idea.title = title
    idea.state = State.SCRIPT_GENERATED
    st.save(idea)
    return idea.model_dump()



@router.post("/{idea_id}/videos")
async def upload_videos(
    idea_id: int,
    files: List[UploadFile] = File(...),
    orientation: VideoOrientation = VideoOrientation.SHORT,
) -> dict[str, Any]:
    st = _store(orientation)
    idea = st.get_by_id(idea_id)
    if not idea:
        raise HTTPException(404, "Idea not found")

    videos_dir = _out(orientation) / "ideas" / f"idea_{idea_id:06d}" / "videos"
    videos_dir.mkdir(parents=True, exist_ok=True)

    sorted_files = sorted(files, key=lambda f: f.filename or "")

    script_path = _out(orientation) / "ideas" / f"idea_{idea_id:06d}" / "script.json"
    if not script_path.is_file():
        raise HTTPException(409, "Generate or upload the script before uploading scene videos")
    try:
        script = VideoScript.model_validate_json(script_path.read_bytes())
    except Exception as exc:
        raise HTTPException(422, "The project's script.json is invalid") from exc

    expected_scenes = len(script.scenes)
    if len(sorted_files) != expected_scenes:
        raise HTTPException(
            422,
            f"Expected {expected_scenes} scene videos for this script; received {len(sorted_files)}",
        )

    for file in sorted_files:
        if Path((file.filename or "").replace("\\", "/")).suffix.lower() != ".mp4":
            raise HTTPException(415, f"Only MP4 scene videos are supported: {file.filename}")

    # Stage and validate every upload before touching the currently usable scenes.
    # The backup/rollback phase keeps the old set intact if any replacement fails.
    import uuid

    transaction_id = uuid.uuid4().hex
    staging_dir = videos_dir / f".upload-{transaction_id}"
    backup_dir = videos_dir / f".backup-{transaction_id}"
    staging_dir.mkdir()
    backup_dir.mkdir()
    old_state = idea.state
    installed_targets: list[Path] = []
    backed_up_targets: list[tuple[Path, Path]] = []

    try:
        for i, file in enumerate(sorted_files, start=1):
            staged_target = staging_dir / f"scene_{i:04d}.mp4"
            total_size = 0
            with staged_target.open("wb") as destination:
                while chunk := await file.read(1024 * 1024):
                    total_size += len(chunk)
                    if total_size > 500 * 1024 * 1024:
                        raise HTTPException(
                            413,
                            f"Scene video is too large (500 MB maximum): {file.filename}",
                        )
                    destination.write(chunk)
            with staged_target.open("rb") as uploaded_file:
                if b"ftyp" not in uploaded_file.read(16):
                    raise HTTPException(415, f"Invalid MP4 file: {file.filename}")

        for existing in videos_dir.glob("scene_*.mp4"):
            backup = backup_dir / existing.name
            existing.replace(backup)
            backed_up_targets.append((backup, existing))

        for staged in sorted(staging_dir.glob("scene_*.mp4")):
            target = videos_dir / staged.name
            staged.replace(target)
            installed_targets.append(target)

        idea.state = State.VIDEOS_GENERATED
        st.save(idea)
    except Exception:
        idea.state = old_state
        for target in installed_targets:
            target.unlink(missing_ok=True)
        for backup, original in reversed(backed_up_targets):
            if backup.exists():
                backup.replace(original)
        raise
    finally:
        import shutil
        shutil.rmtree(staging_dir, ignore_errors=True)
        shutil.rmtree(backup_dir, ignore_errors=True)

    return {"id": idea.id, "state": idea.state, "files_uploaded": len(sorted_files)}


@router.get("/{idea_id}/video")
def get_video(
    idea_id: int,
    orientation: VideoOrientation = VideoOrientation.SHORT,
) -> FileResponse:
    idea_dir = _out(orientation) / "ideas" / f"idea_{idea_id:06d}"
    videos = list(idea_dir.glob("*.mp4"))
    if not videos:
        raise HTTPException(404, "Video not found")
    return FileResponse(str(videos[0]), filename=videos[0].name, media_type="video/mp4")


@router.post("/{idea_id}/audio")
def generate_audio(
    idea_id: int,
    force: bool = False,
    orientation: VideoOrientation = VideoOrientation.SHORT,
) -> dict[str, str]:
    job_id = job_manager.create_job()
    p = _pipeline(orientation)
    _executor.submit(
        job_manager.run_in_job,
        job_id,
        lambda: p.step3_generate_audios(idea_id=idea_id, force=force),
    )
    return {"job_id": job_id}


@router.post("/{idea_id}/sync")
def generate_sync(
    idea_id: int,
    orientation: VideoOrientation = VideoOrientation.SHORT,
) -> dict[str, str]:
    job_id = job_manager.create_job()
    p = _pipeline(orientation)
    _executor.submit(
        job_manager.run_in_job,
        job_id,
        lambda: p.step4_generate_videos(idea_id=idea_id),
    )
    return {"job_id": job_id}


@router.post("/{idea_id}/subtitles")
def generate_subtitles(
    idea_id: int,
    orientation: VideoOrientation = VideoOrientation.SHORT,
) -> dict[str, str]:
    job_id = job_manager.create_job()
    p = _pipeline(orientation)
    _executor.submit(
        job_manager.run_in_job,
        job_id,
        lambda: p.step5_generate_subtitles(idea_id=idea_id),
    )
    return {"job_id": job_id}


@router.post("/{idea_id}/assemble")
def assemble_video(
    idea_id: int,
    orientation: VideoOrientation = Form(VideoOrientation.SHORT),
    bg_volume: float = Form(...),
    music_path: str = Form(...),
) -> dict[str, str]:
    music_root = (_RESOURCE_BASE / "bg-music").resolve()
    full_music_path = (music_root / music_path).resolve()
    try:
        full_music_path.relative_to(music_root)
    except ValueError as exc:
        raise HTTPException(400, "Invalid music path") from exc
    if not full_music_path.is_file():
        raise HTTPException(404, f"Music file not found: {music_path}")
    if not 0 <= bg_volume <= 1:
        raise HTTPException(422, "Background volume must be between 0 and 1")

    job_id = job_manager.create_job()
    p = _pipeline(orientation)

    def _run() -> None:
        p.step6_add_background_music(
            idea_id=idea_id,
            music_path=full_music_path,
            bg_volume=bg_volume,
        )
        p.step7_rename_final_video(idea_id=idea_id)

    _executor.submit(job_manager.run_in_job, job_id, _run)
    return {"job_id": job_id}
