"""Command line interface for the V2 foundation."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from ownyourtime.models import GenerationMode, Language
from ownyourtime.providers import OfflineContentProvider
from ownyourtime.quality import QualityGate
from ownyourtime.settings import load_settings
from ownyourtime.store import ArtifactStore
from ownyourtime.workflow import CreateReelWorkflow


DEFAULT_CONFIG = Path("config/v2/app.yaml")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="oyt", description="OwnYourTime Content OS V2")
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser("generate", help="Create a traceable Reel package")
    generate.add_argument("--topic", required=True)
    generate.add_argument("--language", choices=[item.value for item in Language], default="fr")
    generate.add_argument(
        "--mode", choices=[item.value for item in GenerationMode], default="standard"
    )
    generate.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    generate.add_argument("--output-dir", type=Path)
    generate.add_argument(
        "--dry-run",
        action="store_true",
        help="Use the deterministic offline provider; no external API call is made",
    )

    doctor = subparsers.add_parser("doctor", help="Check the local V2 environment")
    doctor.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    return parser


def run_generate(args: argparse.Namespace) -> int:
    if not args.dry_run:
        raise SystemExit("Only --dry-run is available in the foundation milestone.")
    settings = load_settings(args.config)
    output_dir = args.output_dir or settings.output_directory
    workflow = CreateReelWorkflow(
        provider=OfflineContentProvider(),
        store=ArtifactStore(output_dir),
        quality_gate=QualityGate(settings.quality.minimum_score),
    )
    run = workflow.run(
        topic=args.topic,
        language=Language(args.language),
        mode=GenerationMode(args.mode),
        dry_run=True,
    )
    summary = {
        "run_id": run.run_id,
        "status": run.status,
        "quality_score": run.quality.predicted_score if run.quality else None,
        "output_directory": str(run.output_directory),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def run_doctor(args: argparse.Namespace) -> int:
    settings = load_settings(args.config)
    checks = {
        "python_3_11_or_newer": sys.version_info >= (3, 11),
        "config_valid": bool(settings.brand),
        "ffmpeg_available": shutil.which("ffmpeg") is not None,
    }
    print(json.dumps(checks, indent=2))
    return 0 if all(checks.values()) else 1


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "generate":
        return run_generate(args)
    if args.command == "doctor":
        return run_doctor(args)
    raise AssertionError(f"unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
