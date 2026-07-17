"""Single V2 workflow for creating a traceable Reel package."""

from __future__ import annotations

from pathlib import Path

from ownyourtime.models import GenerationMode, Language, ReelRun, RunStatus
from ownyourtime.providers import ContentProvider
from ownyourtime.quality import QualityGate
from ownyourtime.store import ArtifactStore


class CreateReelWorkflow:
    def __init__(
        self,
        provider: ContentProvider,
        store: ArtifactStore,
        quality_gate: QualityGate,
    ) -> None:
        self.provider = provider
        self.store = store
        self.quality_gate = quality_gate

    def run(
        self,
        topic: str,
        language: Language = Language.FR,
        mode: GenerationMode = GenerationMode.STANDARD,
        dry_run: bool = True,
    ) -> ReelRun:
        if not topic.strip():
            raise ValueError("topic cannot be empty")

        run = ReelRun(output_directory=Path("."), mode=mode, dry_run=dry_run)
        run_dir = self.store.run_directory(run.run_id)
        run.output_directory = run_dir

        try:
            script = self.provider.generate(topic.strip(), language)
            quality = self.quality_gate.evaluate(script)
            run.script = script
            run.quality = quality
            run.status = RunStatus.NEEDS_REVIEW if quality.publishable else RunStatus.GENERATED

            self.store.write_model(run_dir / "script.json", script)
            self.store.write_model(run_dir / "quality.json", quality)
            self.store.write_model(run_dir / "run.json", run)
            return run
        except Exception as exc:
            run.status = RunStatus.FAILED
            run.error = str(exc)
            self.store.write_model(run_dir / "run.json", run)
            raise
