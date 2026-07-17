"""Versioned V2 configuration loader."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field


class QualitySettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    minimum_score: float = Field(default=7.5, ge=0, le=10)


class AppSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    brand: str = "@ownyourtime.ai"
    output_directory: Path = Path("output/v2")
    quality: QualitySettings = Field(default_factory=QualitySettings)


def load_settings(path: Path) -> AppSettings:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return AppSettings.model_validate(data)
