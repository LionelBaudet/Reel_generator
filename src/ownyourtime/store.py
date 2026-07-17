"""Inspectable filesystem artifact storage for pipeline runs."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel


class ArtifactStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def run_directory(self, run_id: str) -> Path:
        path = self.root / run_id
        path.mkdir(parents=True, exist_ok=False)
        return path

    @staticmethod
    def write_model(path: Path, value: BaseModel) -> None:
        path.write_text(
            json.dumps(value.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
