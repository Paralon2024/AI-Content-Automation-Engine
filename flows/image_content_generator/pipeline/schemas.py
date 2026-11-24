from enum import Enum
from math import isfinite
from typing import List, Optional

from pydantic import BaseModel, model_validator

from tools.common.storage_folder import StoreRecord


class State(str, Enum):
    NEW = "NEW"
    SCRIPT_GENERATED = "SCRIPT_GENERATED"
    VIDEOS_GENERATED = "VIDEOS_GENERATED"
    AUDIO_GENERATED = "AUDIO_GENERATED"
    VIDEO_GENERATED = "VIDEO_GENERATED"
    VIDEO_SUBTITLED = "VIDEO_SUBTITLED"
    VIDEO_MUSIC_GENERATED = "VIDEO_MUSIC_GENERATED"
    COMPLETED = "COMPLETED"


class VideoOrientation(str, Enum):
    SHORT = "short"
    LONG = "long"


class SceneAlignment(BaseModel):
    scene_number: int
    start_time: float
    end_time: float

    @model_validator(mode="after")
    def validate_time_range(self) -> "SceneAlignment":
        if not isfinite(self.start_time) or not isfinite(self.end_time):
            raise ValueError("Scene alignment times must be finite numbers")
        if self.start_time < 0 or self.end_time <= self.start_time:
            raise ValueError("Scene alignment must have a non-negative start and a later end")
        return self


class AudioAlignment(BaseModel):
    alignments: List[SceneAlignment]

    @model_validator(mode="after")
    def validate_scene_sequence(self) -> "AudioAlignment":
        numbers = [alignment.scene_number for alignment in self.alignments]
        expected = list(range(1, len(numbers) + 1))
        if numbers != expected:
            raise ValueError(
                "Audio alignments must contain each scene exactly once in sequential order"
            )
        return self


class ScriptFormData(BaseModel):
    idea: str
    style: str = "stickman"
    category: str = "finanzas"
    tone: str = "motivacional"
    aspect_ratio: str = "9:16"


class IdeaRaw(StoreRecord[State]):
    title: str
    category: str
    form: Optional[ScriptFormData] = None
