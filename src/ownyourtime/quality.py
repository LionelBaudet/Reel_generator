"""Deterministic pre-publication checks."""

from __future__ import annotations

from ownyourtime.models import QualityResult, ReelScript, SceneType


class QualityGate:
    def __init__(self, minimum_score: float = 7.5) -> None:
        self.minimum_score = minimum_score

    def evaluate(self, script: ReelScript) -> QualityResult:
        hook_words = len(script.selected_hook.text.split())
        duration = script.duration_seconds
        has_proof = any(scene.type is SceneType.PROOF for scene in script.scenes)
        has_source = any(scene.source is not None for scene in script.scenes)

        checks = {
            "short_hook": hook_words <= 8,
            "reel_duration": 15 <= duration <= 30,
            "has_cta": any(scene.type is SceneType.CTA for scene in script.scenes),
            "claim_integrity": has_proof == has_source,
        }
        issues: list[str] = []
        if not checks["short_hook"]:
            issues.append("Le hook dépasse 8 mots.")
        if not checks["reel_duration"]:
            issues.append("La durée doit être comprise entre 15 et 30 secondes.")
        if not checks["has_cta"]:
            issues.append("Le script ne contient pas de CTA.")
        if not checks["claim_integrity"]:
            issues.append("Une scène de preuve doit contenir une source vérifiable.")

        rules_score = sum(checks.values()) / len(checks) * 10
        score = round((rules_score * 0.6) + (script.selected_hook.predicted_score * 0.4), 2)
        publishable = score >= self.minimum_score and not issues
        return QualityResult(
            predicted_score=score,
            publishable=publishable,
            issues=issues,
            checks=checks,
        )
