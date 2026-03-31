# Module des templates de reels
from .prompt_reveal import PromptRevealTemplate

TEMPLATES = {
    "prompt_reveal": PromptRevealTemplate,
}


def get_template(name: str):
    """Retourne la classe de template correspondant au nom donné."""
    if name not in TEMPLATES:
        raise ValueError(f"Template inconnu: '{name}'. Templates disponibles: {list(TEMPLATES.keys())}")
    return TEMPLATES[name]
