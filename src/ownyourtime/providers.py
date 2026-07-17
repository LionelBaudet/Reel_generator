"""Interfaces for external content providers and an offline development provider."""

from __future__ import annotations

from typing import Protocol

from ownyourtime.models import (
    HookCandidate,
    Language,
    ReelScript,
    SceneType,
    ScriptScene,
    TopicBrief,
)


class ContentProvider(Protocol):
    """Generate structured content without exposing a vendor SDK to the domain layer."""

    name: str

    def generate(self, topic: str, language: Language) -> ReelScript: ...


class OfflineContentProvider:
    """Deterministic provider used for local development, tests and CI."""

    name = "offline"

    def generate(self, topic: str, language: Language) -> ReelScript:
        brief = TopicBrief(
            title=topic,
            angle="Montrer le coût d'une tâche répétitive puis proposer une action mesurable",
            language=language,
        )
        hooks = [
            HookCandidate(
                text="Tu perds encore des heures sur ça",
                angle="frustration",
                predicted_score=8.1,
            ),
            HookCandidate(
                text="Cette tâche te coûte une journée par mois",
                angle="perte de temps",
                predicted_score=7.8,
            ),
            HookCandidate(
                text="Ton expertise vaut plus que ce copier-coller",
                angle="ego professionnel",
                predicted_score=7.5,
            ),
        ]
        selected = hooks[0]
        scenes = [
            ScriptScene(type=SceneType.HOOK, text=selected.text, duration_seconds=2.8),
            ScriptScene(
                type=SceneType.TENSION,
                text="Même fichier. Même manipulation. Chaque semaine.",
                duration_seconds=2.8,
            ),
            ScriptScene(
                type=SceneType.SHIFT,
                text="Le problème n'est pas ton outil. C'est le processus.",
                duration_seconds=3.0,
            ),
            ScriptScene(
                type=SceneType.SOLUTION,
                text=f"Documente une fois le workflow pour automatiser : {topic}.",
                duration_seconds=3.8,
            ),
            ScriptScene(
                type=SceneType.RESULT,
                text="Tu gardes le contrôle. La machine exécute le répétitif.",
                duration_seconds=3.2,
            ),
            ScriptScene(
                type=SceneType.CTA,
                text="Sauvegarde ce Reel et automatise ta première tâche.",
                duration_seconds=3.4,
            ),
        ]
        return ReelScript(
            topic=brief,
            hooks=hooks,
            selected_hook=selected,
            scenes=scenes,
            caption=(
                f"Tu n'as pas besoin de travailler plus longtemps pour améliorer {topic}. "
                "Commence par isoler l'étape répétitive, mesure le temps perdu et automatise "
                "une seule action.\n\n@ownyourtime.ai"
            ),
        )
