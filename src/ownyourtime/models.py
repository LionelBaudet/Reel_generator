"""Provider-independent domain models for the OwnYourTime pipeline."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class Language(StrEnum):
    FR = "fr"
    EN = "en"


class GenerationMode(StrEnum):
    STANDARD = "standard"
    TREND = "trend"
    SOCIAL = "social"
    NEWS = "news"


class RunStatus(StrEnum):
    CREATED = "created"
    GENERATED = "generated"
    NEEDS_REVIEW = "needs_review"
    APPROVED = "approved"
    RENDERED = "rendered"
    PUBLISHED = "published"
    FAILED = "failed"


class SceneType(StrEnum):
    HOOK = "hook"
    TENSION = "tension"
    SHIFT = "shift"
    PROOF = "proof"
    SOLUTION = "solution"
    RESULT = "result"
    CTA = "cta"


class SourceReference(BaseModel):
    """A factual source that supports a content claim."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=3, max_length=240)
    url: HttpUrl
    publisher: str = Field(min_length=2, max_length=120)
    verified: bool = False
    published_at: datetime | None = None


class TopicBrief(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=5, max_length=180)
    audience: str = "Professionnels Data, IT et business de 25 à 45 ans"
    angle: str = Field(min_length=5, max_length=300)
    language: Language = Language.FR
    sources: list[SourceReference] = Field(default_factory=list)


class HookCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=4, max_length=100)
    angle: str = Field(min_length=3, max_length=80)
    predicted_score: float = Field(ge=0, le=10)

    @field_validator("text")
    @classmethod
    def hook_must_be_short(cls, value: str) -> str:
        if len(value.split()) > 12:
            raise ValueError("a hook must contain at most 12 words")
        return value.strip()


class ScriptScene(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: SceneType
    text: str = Field(min_length=1, max_length=360)
    duration_seconds: float = Field(gt=0, le=10)
    source: SourceReference | None = None


class ReelScript(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic: TopicBrief
    hooks: list[HookCandidate] = Field(min_length=1, max_length=5)
    selected_hook: HookCandidate
    scenes: list[ScriptScene] = Field(min_length=4, max_length=9)
    caption: str = Field(min_length=10, max_length=2200)

    @field_validator("scenes")
    @classmethod
    def scenes_must_have_hook_and_cta(cls, value: list[ScriptScene]) -> list[ScriptScene]:
        scene_types = {scene.type for scene in value}
        if SceneType.HOOK not in scene_types or SceneType.CTA not in scene_types:
            raise ValueError("a script must contain hook and cta scenes")
        return value

    @property
    def duration_seconds(self) -> float:
        return round(sum(scene.duration_seconds for scene in self.scenes), 2)


class QualityResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    predicted_score: float = Field(ge=0, le=10)
    publishable: bool
    issues: list[str] = Field(default_factory=list)
    checks: dict[str, bool] = Field(default_factory=dict)


class ReelRun(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(default_factory=lambda: uuid4().hex)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    status: RunStatus = RunStatus.CREATED
    mode: GenerationMode = GenerationMode.STANDARD
    dry_run: bool = True
    output_directory: Path
    script: ReelScript | None = None
    quality: QualityResult | None = None
    video_path: Path | None = None
    error: str | None = None
