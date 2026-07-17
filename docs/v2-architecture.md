# OwnYourTime Content OS V2

## Objective

Create a measurable content factory. The system may predict content quality, but only real
platform analytics can establish performance. Human approval remains mandatory until the
publishing and feedback loop is proven reliable.

## Target pipeline

1. ingest credible trend signals;
2. select a topic and preserve its sources;
3. generate hook variants and a structured script;
4. run deterministic and model-based quality checks;
5. build voice, storyboard and video artifacts;
6. request human approval;
7. publish through the Meta API;
8. collect reach, watch time, shares and saves;
9. compare predictions with observed performance.

## Architecture boundaries

- **Domain**: provider-independent Pydantic models in `src/ownyourtime/models.py`.
- **Providers**: OpenAI, Anthropic, ElevenLabs, Pexels and Meta adapters.
- **Workflow**: one explicit orchestrator that creates traceable artifacts.
- **Rendering**: initially reuse the legacy MoviePy/FFmpeg templates through an adapter.
- **Persistence**: filesystem artifacts in milestone 1, PostgreSQL in a later milestone.
- **UI**: chosen only after the backend workflow and data contracts are stable.

## Migration policy

The legacy prototype remains available during migration. V2 imports no Streamlit or Reflex
code and does not depend directly on a model vendor. Legacy capabilities are migrated behind
adapters one vertical slice at a time.

## Milestones

- **M1 Foundation**: models, offline provider, quality gate, artifact store, CLI and tests.
- **M2 Content**: live LLM provider, trend adapter, structured outputs and source integrity.
- **M3 Production**: voice and video renderer adapters plus approval queue.
- **M4 Distribution**: Meta publishing, scheduler and failure recovery.
- **M5 Learning**: Instagram insights, experiment tracking and prediction calibration.
