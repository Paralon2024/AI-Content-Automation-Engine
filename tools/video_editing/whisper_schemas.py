from typing import List

from pydantic import BaseModel, Field, model_validator


class WhisperOffsets(BaseModel):
    """Segment offsets must cover a non-empty time range."""

    from_ms: int = Field(alias="from")
    to_ms: int = Field(alias="to")

    @model_validator(mode="after")
    def validate_time_range(self) -> "WhisperOffsets":
        if self.from_ms < 0 or self.to_ms <= self.from_ms:
            raise ValueError("Whisper segment timestamps must be non-negative and have positive duration")
        return self


class WhisperTokenOffsets(BaseModel):
    """Token offsets may be zero-length for Whisper control/boundary tokens."""

    from_ms: int = Field(alias="from")
    to_ms: int = Field(alias="to")

    @model_validator(mode="after")
    def validate_time_range(self) -> "WhisperTokenOffsets":
        if self.from_ms < 0 or self.to_ms < self.from_ms:
            raise ValueError("Whisper token timestamps must be non-negative and non-decreasing")
        return self


class WhisperToken(BaseModel):
    text: str
    offsets: WhisperTokenOffsets


class WhisperSegment(BaseModel):
    text: str
    offsets: WhisperOffsets
    tokens: List[WhisperToken] = []


class WhisperTranscription(BaseModel):
    transcription: List[WhisperSegment]


class WhisperTranscriptionSegment(BaseModel):
    text: str
    start: float  # s
    end: float    # s


class WhisperWord(BaseModel):
    text: str
    start: int  # ms
    end: int    # ms
