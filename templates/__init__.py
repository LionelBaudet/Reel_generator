# Module des templates de reels
from .prompt_reveal import PromptRevealTemplate
from .multi_scene import MultiSceneTemplate
from .viral_text_centric import ViralTextCentricTemplate

TEMPLATES = {
    "prompt_reveal":         PromptRevealTemplate,
    "multi_scene":           MultiSceneTemplate,
    "viral_text_centric_v1": ViralTextCentricTemplate,
}


def get_template(name: str):
    """Retourne la classe de template correspondant au nom donné."""
    if name not in TEMPLATES:
        raise ValueError(
            f"Template inconnu: '{name}'. "
            f"Templates disponibles: {list(TEMPLATES.keys())}"
        )
    return TEMPLATES[name]
