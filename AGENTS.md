# OwnYourTime Content OS

## Mission

Build a reliable, measurable pipeline that creates publish-ready short-form videos for
`@ownyourtime.ai`. The product must optimize for useful, defensible content rather than
claiming that virality can be guaranteed.

## Repository map

- `src/ownyourtime/`: V2 application code. New business logic belongs here.
- `tests/`: automated tests for V2 and critical legacy compatibility.
- `config/v2/`: versioned, non-secret V2 configuration.
- `docs/`: architecture and operating documentation.
- `agents/`, `utils/`, `templates/`, root Python scripts: legacy prototype. Reuse through
  adapters; do not extend these monoliths with new V2 business logic.
- `assets/`: reusable media inputs. Do not add generated videos here.
- `output/`: generated artifacts. New generated artifacts must remain ignored by Git.

## Working rules

1. Preserve the behavior of `master`; perform V2 work on a feature branch.
2. Keep domain models independent from Streamlit, Reflex, Meta, LLM and rendering SDKs.
3. Put external integrations behind provider interfaces.
4. Every pipeline run must have a unique `run_id` and write inspectable JSON artifacts.
5. A quality score is a prediction, never a statement that a Reel will become viral.
6. Claims and statistics must keep their source URL and verification state.
7. Never commit API keys, access tokens, downloaded stock media or generated MP4 files.
8. Prefer small modules, typed interfaces and explicit exceptions over silent fallbacks.
9. Add or update tests for every behavior change.

## Commands

```bash
python -m pip install -e '.[dev]'
pytest
ruff check src tests
oyt doctor
oyt generate --topic "Automatiser un reporting Power BI" --dry-run
```

## Definition of done

- relevant tests pass;
- lint passes for changed V2 files;
- commands and configuration are documented;
- no secret or generated media is introduced;
- output artifacts can be traced back to a `run_id`;
- legacy code remains callable unless the change explicitly migrates it.
