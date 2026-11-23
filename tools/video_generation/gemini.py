import base64
import json
import os
import mimetypes
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

from tools.common.gemini_base import GeminiBase
from tools.common.messenger import Messenger


class GeminiVideoGenerator(GeminiBase):
    """
    Generate short clips with Gemini Omni through the Gemini Interactions API.
    Supports text-to-video, image-to-video, and first/last-frame interpolation.
    """

    video_model: str = "gemini-omni-1.2-flash"
    api_url: str = "https://generativelanguage.googleapis.com/v1beta/interactions"
    aspect_ratio: str = "9:16"
    duration: str = "8s"
    resolution: str = "1080p"

    def generate_video(
        self,
        prompt: str,
        out_path: str,
        img_start_path: Optional[str] = None,
        img_end_path: Optional[str] = None,
    ) -> None:
        """
        Generate an MP4 clip and save it to disk.

        The Gemini Developer API video model requires a billed Tier 1 project.
        """
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")

        if not prompt.strip():
            raise ValueError("Video prompt cannot be empty")

        out_path_obj = Path(out_path)
        out_path_obj.parent.mkdir(parents=True, exist_ok=True)

        input_items: list[dict[str, str]] = []

        for image_path in (img_start_path, img_end_path):
            if not image_path:
                continue
            path = Path(image_path)
            if not path.is_file():
                raise FileNotFoundError(f"Reference image not found: {path}")

            mime_type, _ = mimetypes.guess_type(path.name)
            if mime_type not in {"image/png", "image/jpeg", "image/webp"}:
                raise ValueError(f"Unsupported reference image type: {path.name}")

            input_items.append(
                {
                    "type": "image",
                    "data": base64.b64encode(path.read_bytes()).decode("ascii"),
                    "mime_type": mime_type,
                }
            )

        input_items.append({"type": "text", "text": prompt})
        task = "image_to_video" if img_start_path else "text_to_video"

        payload = {
            "model": self.video_model,
            "store": False,
            "input": input_items,
            "response_format": {
                "type": "video",
                "duration": self.duration,
                "resolution": self.resolution,
                "aspect_ratio": self.aspect_ratio,
            },
            "generation_config": {
                "video_config": {"task": task},
            },
        }

        request = urllib.request.Request(
            self.api_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": api_key,
            },
            method="POST",
        )

        Messenger.info(f"Starting Gemini video generation: {out_path_obj.name}")

        try:
            with urllib.request.urlopen(request, timeout=900) as response:
                result = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"Gemini video request failed (HTTP {exc.code}): {details}"
            ) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Could not connect to the Gemini video API: {exc}") from exc

        encoded_video = None
        for step in result.get("steps", []):
            if step.get("type") != "model_output":
                continue
            for item in step.get("content", []):
                if item.get("type") == "video" and item.get("data"):
                    encoded_video = item["data"]
                    break
            if encoded_video:
                break

        if not encoded_video:
            raise RuntimeError(
                f"Gemini returned no video data. Response status: {result.get('status')}"
            )

        try:
            video_bytes = base64.b64decode(encoded_video, validate=True)
        except (ValueError, TypeError) as exc:
            raise RuntimeError("Gemini returned invalid base64 video data") from exc

        if b"ftyp" not in video_bytes[:16]:
            raise RuntimeError("Gemini returned data that is not a valid MP4 file")

        out_path_obj.write_bytes(video_bytes)
        Messenger.success(f"Video saved: {out_path_obj}")
