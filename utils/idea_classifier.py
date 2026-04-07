"""
utils/idea_classifier.py — Classification locale d'idées Instagram Reels.

Retourne le type, l'angle dominant et les templates de hooks adaptés.
100% local, sans API, basé sur scoring de mots-clés pondérés.

12 types couverts :
  before_after_time · prompt_reveal · tool_demo · comparison
  data_workflow · budget_finance · career_work · controversial_opinion
  build_in_public · storytelling_personal · educational_explainer · reactive_reply
"""
from __future__ import annotations

# ─────────────────────────────────────────────────────────────────────────────
# Taxonomy : 12 types × (keywords, angle, templates A/B/C)
# ─────────────────────────────────────────────────────────────────────────────

# Format keywords : list of (keyword_string, weight)
# Les poids permettent de prioriser les signaux forts.

CATEGORIES: dict[str, dict] = {

    "before_after_time": {
        "label": "Avant / Après Temps",
        "label_en": "Before / After Time",
        "angle": "gain de temps",
        "angle_en": "time saving",
        "keywords": [
            ("→", 3), ("h →", 4), ("min →", 4), ("heures à", 3), ("minutes à", 3),
            ("rapport", 2), ("tâche", 2), ("prenait", 3), ("prend", 1),
            ("système", 1), ("automatisé", 2), ("coupé", 2), ("réduit", 2),
            ("workflow", 2), ("gain de temps", 4), ("avant :", 3), ("après :", 3),
            ("before", 2), ("time saved", 3), ("took me", 3), ("used to take", 3),
            ("2h", 3), ("45 min", 3), ("8 minutes", 3), ("15 min", 2),
        ],
        "abc_templates": {
            "A": [
                "Cette tâche me prenait 45 min",
                "J'ai coupé 2h de boulot par jour",
                "Mon rapport se fait maintenant tout seul",
                "Je gagne 1h par jour sur ça",
                # EN
                "This used to take me 45 minutes",
                "I cut 2 hours of work per day",
            ],
            "B": [
                "Voilà le système que j'utilise",
                "Un truc simple que j'ai découvert",
                "Personne ne fait ça. Ça prend 8 min.",
                "La méthode que j'aurais voulu connaître avant",
                # EN
                "Here's the system I use",
                "Nobody does this. It takes 8 minutes.",
            ],
            "C": [
                "2h → 8 minutes",
                "Avant : 2h. Maintenant : 8 min.",
                "45 min de boulot → 3 clics",
                "Mon rapport de 2h. Fait en 8 min.",
                # EN
                "2 hours → 8 minutes",
                "My 2h report. Done in 8 min.",
            ],
        },
    },

    "prompt_reveal": {
        "label": "Prompt Reveal",
        "label_en": "Prompt Reveal",
        "angle": "découverte",
        "angle_en": "discovery",
        "keywords": [
            ("prompt", 5), ("chatgpt", 2), ("claude", 2), ("gpt", 2),
            ("le prompt", 5), ("mon prompt", 5), ("ce prompt", 4),
            ("exact que j'utilise", 5), ("pour mes emails", 3), ("j'utilise", 1),
            ("copie", 2), ("template de prompt", 4),
        ],
        "abc_templates": {
            "A": [
                "Le prompt exact que j'utilise",
                "Mon prompt pour les emails clients",
                "J'utilise ça depuis 3 mois",
                "Le prompt complet, c'est ici",
                # EN
                "The exact prompt I use",
                "My prompt for client emails",
            ],
            "B": [
                "Le prompt que personne ne partage",
                "Ce prompt m'a surpris moi-même",
                "J'ai testé 20 prompts. Un seul marche vraiment.",
                "Voilà pourquoi mon prompt est différent",
                # EN
                "The prompt nobody shares",
                "I tested 20 prompts. Only one actually works.",
            ],
            "C": [
                "Ce prompt me fait gagner 1h/jour",
                "Ce prompt fait ça en 30 sec",
                "J'ai trouvé le prompt parfait. Le voilà.",
                "Ce prompt change tout. Vraiment.",
                # EN
                "This prompt saves me 1h/day",
                "This prompt does it in 30 sec",
            ],
        },
    },

    "tool_demo": {
        "label": "Démo Outil",
        "label_en": "Tool Demo",
        "angle": "découverte",
        "angle_en": "discovery",
        "keywords": [
            ("testé", 3), ("outil", 4), ("tool", 4), ("app", 2),
            ("logiciel", 3), ("j'ai testé", 5), ("bluffant", 3),
            ("démo", 3), ("demo", 3), ("fonctionne", 2), ("remplace", 3),
            ("en 2 minutes", 4), ("en 5 minutes", 3), ("marche", 2),
            ("ce truc", 2), ("cette app", 3), ("ce logiciel", 3),
        ],
        "abc_templates": {
            "A": [
                "J'ai testé ça pendant 30 jours",
                "Cet outil fait ça tout seul",
                "Je l'utilise tous les jours maintenant",
                "Ça remplace complètement X",
                # EN
                "I tested this for 30 days",
                "This tool does it automatically",
            ],
            "B": [
                "Je pensais que c'était nul. J'avais tort.",
                "Ça m'a pris 5 min à comprendre. Puis plus jamais sans.",
                "Tout le monde en parle. Personne ne montre vraiment.",
                "J'ai testé. Voilà ce qui se passe vraiment.",
                # EN
                "I thought it was useless. I was wrong.",
                "Everyone talks about it. Nobody shows the real thing.",
            ],
            "C": [
                "En 2 minutes. Vraiment.",
                "J'ai testé. C'est bluffant.",
                "Cet outil fait X en 30 sec.",
                "Ça m'a choqué. En bien.",
                # EN
                "2 minutes. For real.",
                "I tested it. Jaw-dropping.",
            ],
        },
    },

    "comparison": {
        "label": "Comparaison",
        "label_en": "Comparison",
        "angle": "découverte",
        "angle_en": "discovery",
        "keywords": [
            ("vs", 4), ("versus", 4), ("ou", 1), ("comparaison", 4),
            ("différence", 3), ("lequel", 3), ("gagnant", 3),
            ("j'ai testé les deux", 5), ("le meilleur", 2), ("est mort", 4),
            ("remplace", 3), ("vs.", 4), ("compare", 3),
        ],
        "abc_templates": {
            "A": [
                "J'ai testé X et Y. Voilà ce que j'ai trouvé.",
                "La différence entre X et Y",
                "X ou Y ? J'ai testé les deux.",
                "J'utilise X. Pas Y. Voilà pourquoi.",
                # EN
                "I tested X and Y. Here's what I found.",
                "X or Y? I tested both.",
            ],
            "B": [
                "Le gagnant m'a surpris",
                "Je pensais que X gagnait. J'avais tort.",
                "La vraie différence que personne ne montre",
                "Après 1 mois avec les deux. Le résultat.",
                # EN
                "The winner surprised me",
                "I thought X would win. I was wrong.",
            ],
            "C": [
                "X est mort. Voilà ce qui le remplace.",
                "X vs Y — le résultat m'a surpris",
                "J'ai testé les deux. Un seul gagne vraiment.",
                "VLOOKUP est mort.",
                # EN
                "X is dead. Here's what replaced it.",
                "I tested both. Only one actually wins.",
            ],
        },
    },

    "data_workflow": {
        "label": "Data / Workflow",
        "label_en": "Data / Workflow",
        "angle": "gain de temps",
        "angle_en": "time saving",
        "keywords": [
            ("python", 5), ("power bi", 5), ("excel", 5), ("vlookup", 5),
            ("data", 3), ("sql", 5), ("pandas", 5), ("dashboard", 4),
            ("formule", 4), ("tableau", 2), ("analyse", 2), ("script", 3),
            ("automation", 3), ("automatisé", 2), ("macro", 4),
            ("power query", 5), ("pivot", 4), ("index match", 5),
        ],
        "abc_templates": {
            "A": [
                "Cette formule remplace 3 onglets",
                "En Python : 10 lignes pour ça",
                "Mon dashboard se met à jour tout seul",
                "J'ai automatisé ça en 15 min",
                # EN
                "This formula replaces 3 sheets",
                "In Python: 10 lines for that",
            ],
            "B": [
                "Ce que VLOOKUP ne peut pas faire",
                "La vraie puissance de Power BI",
                "Je faisais ça à la main. Puis j'ai découvert ça.",
                "Pourquoi j'ai arrêté Excel pour ça",
                # EN
                "What VLOOKUP can't do",
                "I used to do this by hand. Then I found this.",
            ],
            "C": [
                "VLOOKUP est mort.",
                "En Python : 10 lignes. En Excel : 2h.",
                "Ce dashboard fait X tout seul.",
                "J'ai remplacé 4 fichiers Excel par 1 script.",
                # EN
                "VLOOKUP is dead.",
                "Python: 10 lines. Excel: 2 hours.",
            ],
        },
    },

    "budget_finance": {
        "label": "Budget / Finance",
        "label_en": "Budget / Finance",
        "angle": "gain d'argent",
        "angle_en": "money saving",
        "keywords": [
            ("budget", 5), ("argent", 5), ("chf", 5), ("€", 4), ("$", 4),
            ("dépenses", 5), ("économies", 4), ("économiser", 4),
            ("finance", 4), ("salaire", 4), ("revenus", 3), ("coût", 3),
            ("factures", 4), ("analysé mes dépenses", 5), ("analysé mes", 4),
            ("spending", 4), ("expenses", 4), ("money", 4), ("savings", 4),
        ],
        "abc_templates": {
            "A": [
                "J'ai analysé mes dépenses du mois",
                "ChatGPT a géré mon budget",
                "Voilà où va vraiment mon argent",
                "J'ai réduit mes dépenses de X en 30 jours",
                # EN
                "I analyzed my monthly spending",
                "ChatGPT managed my budget",
            ],
            "B": [
                "Ce que j'ai trouvé m'a surpris",
                "Je croyais maîtriser mon budget. Pas du tout.",
                "ChatGPT a trouvé un truc que j'avais raté",
                "Ce que l'IA a trouvé dans mes relevés",
                # EN
                "What I found surprised me",
                "I thought I controlled my budget. Not at all.",
            ],
            "C": [
                "Tu perds CHF 400 sans le voir",
                "Ton argent fuit déjà",
                "Ce que ChatGPT a trouvé m'a choqué",
                "J'avais X de pertes cachées. L'IA les a trouvées.",
                # EN
                "You're losing $400 without seeing it",
                "What ChatGPT found shocked me",
            ],
        },
    },

    "career_work": {
        "label": "Carrière / Travail",
        "label_en": "Career / Work",
        "angle": "douleur",
        "angle_en": "pain",
        "keywords": [
            ("job", 3), ("carrière", 4), ("linkedin", 5), ("cv", 4),
            ("employeur", 4), ("promotion", 4), ("augmentation", 4),
            ("travail", 2), ("chef", 2), ("poste", 2), ("side income", 5),
            ("freelance", 4), ("postuler", 4), ("recruteur", 4),
            ("resume", 4), ("career", 4), ("salary", 4), ("raise", 4),
        ],
        "abc_templates": {
            "A": [
                "Ce que mon profil LinkedIn a changé",
                "J'ai gagné X de plus en faisant ça",
                "La vraie raison pour laquelle on ne me rappelle pas",
                "J'ai arrêté de postuler. Ça a marché.",
                # EN
                "What changed my LinkedIn profile",
                "I earn X more doing this",
            ],
            "B": [
                "La vraie raison derrière les refus",
                "Ce que les recruteurs ne disent pas",
                "Ce que j'aurais fait différemment",
                "Personne ne m'a expliqué ça. J'ai dû le trouver.",
                # EN
                "The real reason behind rejections",
                "What recruiters don't tell you",
            ],
            "C": [
                "Si t'as pas de side income, tu prends un risque",
                "Ton patron peut te remplacer demain",
                "J'ai changé de job sans postuler",
                "Ce que mon chef ne sait pas que je fais",
                # EN
                "If you don't have side income, you're at risk",
                "Your boss can replace you tomorrow",
            ],
        },
    },

    "controversial_opinion": {
        "label": "Opinion / Controverse",
        "label_en": "Controversial Opinion",
        "angle": "opinion forte",
        "angle_en": "strong opinion",
        "keywords": [
            ("faux", 4), ("erreur", 3), ("personne ne dit", 4),
            ("la vraie raison", 4), ("tout le monde", 3), ("mythe", 4),
            ("opinion", 3), ("en réalité", 4), ("si t'as pas", 4),
            ("risque", 2), ("vérité", 4), ("mais en réalité", 4),
            ("tu crois que", 4), ("arrête de", 3), ("unpopular opinion", 5),
            ("hot take", 5), ("controversial", 4),
        ],
        "abc_templates": {
            "A": [
                "La vraie raison derrière X",
                "Ce que personne ne dit sur X",
                "Mon opinion sur X (honnête)",
                "Voilà ce que j'en pense vraiment",
                # EN
                "The real reason behind X",
                "What nobody says about X",
            ],
            "B": [
                "Tout le monde pense X. Je pense le contraire.",
                "La vérité sur X qu'on ne te dit pas",
                "Ça va faire réagir. Mais c'est ma vraie opinion.",
                "J'ai changé d'avis sur X. Voilà pourquoi.",
                # EN
                "Everyone thinks X. I think the opposite.",
                "The truth about X nobody tells you.",
            ],
            "C": [
                "Tu crois que X. Faux.",
                "Si t'as pas X, tu prends un risque énorme.",
                "Tout le monde fait X. C'est une erreur.",
                "La vraie raison de X. Et c'est inconfortable.",
                # EN
                "You think X. Wrong.",
                "Everyone does X. It's a mistake.",
            ],
        },
    },

    "build_in_public": {
        "label": "Build in Public",
        "label_en": "Build in Public",
        "angle": "preuve réelle",
        "angle_en": "real proof",
        "keywords": [
            ("fail", 4), ("chiffres", 4), ("0 vente", 5), ("semaine 1", 5),
            ("mois 1", 5), ("lancé", 2), ("0€", 4), ("0$", 4),
            ("side project", 4), ("mon projet", 2), ("les vrais chiffres", 5),
            ("transparent", 4), ("bilan", 4), ("build", 3), ("launching", 3),
            ("week 1", 5), ("month 1", 5), ("real numbers", 5),
        ],
        "abc_templates": {
            "A": [
                "Voilà les vrais chiffres de ce mois",
                "Bilan de 30 jours : ce que j'ai appris",
                "Mois 3 : voilà où j'en suis",
                "J'ai lancé ça. Voilà ce qui s'est passé.",
                # EN
                "Here are the real numbers this month",
                "Month 3 update: here's where I am",
            ],
            "B": [
                "Ce que personne ne montre dans les bilans",
                "La partie que j'aurais préféré cacher",
                "Le vrai coût de lancer quelque chose",
                "Ce que j'ai appris de mon plus gros fail",
                # EN
                "What nobody shows in their updates",
                "The part I would have preferred to hide",
            ],
            "C": [
                "Mon plus gros fail du mois",
                "Semaine 1 : 0 vente",
                "J'ai lancé avec 0€. Voilà ce qui s'est passé.",
                "Les vrais chiffres. Pas les beaux.",
                # EN
                "My biggest fail this month",
                "Week 1: 0 sales",
            ],
        },
    },

    "storytelling_personal": {
        "label": "Storytelling Personnel",
        "label_en": "Personal Storytelling",
        "angle": "preuve réelle",
        "angle_en": "real proof",
        "keywords": [
            ("il y a", 3), ("il y a 3 mois", 5), ("il y a 1 an", 5),
            ("j'ai appris", 3), ("ma vie", 3), ("mon histoire", 4),
            ("ce qui m'a changé", 4), ("j'avais tort", 4),
            ("j'ai fait l'erreur", 4), ("le truc qui a tout changé", 4),
            ("3 years ago", 5), ("6 months ago", 5), ("i was wrong", 4),
            ("changed everything for me", 4),
        ],
        "abc_templates": {
            "A": [
                "Il y a 3 mois, je faisais ça à la main",
                "Ce que j'aurais voulu savoir avant",
                "J'ai fait une erreur. Voilà ce que j'ai appris.",
                "Le truc qui a tout changé pour moi",
                # EN
                "3 months ago I was doing this by hand",
                "What I wish I had known before",
            ],
            "B": [
                "Ce que personne ne m'avait dit",
                "La vraie raison derrière ma décision",
                "Ce que j'ai compris après X mois",
                "Pourquoi j'ai tout arrêté et recommencé",
                # EN
                "What nobody had told me",
                "The real reason behind my decision",
            ],
            "C": [
                "J'avais tort. Complètement.",
                "Il y a 3 mois, je perdais X heures sur ça",
                "Le moment qui a tout changé",
                "J'ai fait l'erreur. Voilà ce que j'ai perdu.",
                # EN
                "I was wrong. Completely.",
                "3 months ago I was wasting hours on this",
            ],
        },
    },

    "educational_explainer": {
        "label": "Éducation / Explication",
        "label_en": "Educational / Explainer",
        "angle": "autorité",
        "angle_en": "authority",
        "keywords": [
            ("c'est quoi", 4), ("expliqué", 4), ("comprendre", 3),
            ("formation", 3), ("appris", 2), ("tutoriel", 4), ("tuto", 3),
            ("la différence entre", 4), ("en 30 secondes", 4),
            ("4 étapes", 4), ("comment ça marche", 4), ("définition", 3),
            ("explained", 4), ("how it works", 4), ("in 30 seconds", 4),
            ("the difference between", 4), ("step by step", 3),
        ],
        "abc_templates": {
            "A": [
                "X expliqué en 30 secondes",
                "La différence entre X et Y, simplement",
                "En 4 étapes. C'est tout.",
                "Voilà comment ça marche vraiment",
                # EN
                "X explained in 30 seconds",
                "The difference between X and Y, simply",
            ],
            "B": [
                "Ce que X veut vraiment dire",
                "Le truc que personne n'explique sur X",
                "Pourquoi X est mal compris",
                "Ce que j'aurais voulu qu'on m'explique sur X",
                # EN
                "What X really means",
                "The thing nobody explains about X",
            ],
            "C": [
                "X mal expliqué partout. La vraie version ici.",
                "La plupart des gens font faux sur X",
                "Ce que X signifie vraiment. Pas la version wiki.",
                "Tout le monde parle de X. 90% ne comprennent pas.",
                # EN
                "X explained wrong everywhere. The real version here.",
                "Most people are wrong about X",
            ],
        },
    },

    "reactive_reply": {
        "label": "Réponse / Réactivité",
        "label_en": "Reactive Reply",
        "angle": "autorité",
        "angle_en": "authority",
        "keywords": [
            ("tu m'as demandé", 5), ("beaucoup me demandent", 5),
            ("réponse à", 4), ("on m'a posé", 4), ("dm", 3),
            ("commentaire", 2), ("vous m'avez demandé", 5),
            ("j'ai reçu", 2), ("suite à", 3), ("reply", 3),
            ("you asked me", 5), ("a lot of you", 5), ("someone asked", 4),
        ],
        "abc_templates": {
            "A": [
                "Beaucoup me demandent comment X",
                "Tu m'as demandé comment je fais X",
                "La réponse à votre question sur X",
                "Ça revient souvent dans mes DM",
                # EN
                "A lot of you ask me how to X",
                "You asked me how I do X",
            ],
            "B": [
                "Vous m'avez posé cette question 50 fois",
                "Je n'avais pas encore répondu à ça",
                "La vraie réponse à X. Enfin.",
                "Ce que je réponds vraiment quand on me demande X",
                # EN
                "You asked this 50 times. Here's the answer.",
                "I hadn't answered this yet",
            ],
            "C": [
                "On m'a posé cette question 50 fois. La voilà.",
                "Vous voulez savoir. Voilà.",
                "La vraie réponse. Pas la version polie.",
                "J'ai évité cette question. Plus maintenant.",
                # EN
                "You asked this 50 times. Here it is.",
                "The real answer. Not the polished version.",
            ],
        },
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# Descriptions des angles
# ─────────────────────────────────────────────────────────────────────────────

ANGLE_DESCRIPTIONS: dict[str, str] = {
    "gain de temps":  "Montre une transformation concrète de durée : avant/après en minutes ou heures.",
    "gain d'argent":  "Montre un résultat financier chiffré : économies, revenus, coûts évités.",
    "douleur":        "Attaque une douleur réelle que le viewer ressent aujourd'hui.",
    "curiosité":      "Crée un gap d'information que le viewer veut combler.",
    "autorité":       "Montre que tu sais quelque chose que les autres ne savent pas.",
    "découverte":     "Révèle quelque chose que le viewer ne connaissait pas encore.",
    "opinion forte":  "Prend une position tranchée sur un sujet controversé.",
    "preuve réelle":  "Montre des données réelles, des chiffres vrais, une expérience personnelle.",
    # EN
    "time saving":    "Show a concrete duration transformation: before/after in minutes or hours.",
    "money saving":   "Show a concrete financial result: savings, income, avoided costs.",
    "pain":           "Hit a real pain that the viewer feels today.",
    "discovery":      "Reveal something the viewer didn't know yet.",
    "authority":      "Show you know something others don't.",
    "strong opinion": "Take a clear, controversial position on a topic.",
    "real proof":     "Show real data, real numbers, personal experience.",
}


# ─────────────────────────────────────────────────────────────────────────────
# Classifier
# ─────────────────────────────────────────────────────────────────────────────

def classify_idea(idea: str) -> dict:
    """
    Classifie une idée dans l'un des 12 types.

    Retourne :
    {
        "type":       str,          # clé du type (ex: "before_after_time")
        "label":      str,          # libellé FR
        "label_en":   str,          # libellé EN
        "angle":      str,          # angle dominant FR
        "angle_en":   str,          # angle dominant EN
        "confidence": float,        # 0.0–1.0
        "templates":  dict,         # {"A": [...], "B": [...], "C": [...]}
        "scores":     dict,         # scores bruts par catégorie (debug)
    }
    """
    idea_lower = idea.lower()
    scores: dict[str, float] = {}

    for cat_name, cat_data in CATEGORIES.items():
        score = 0.0
        for kw, weight in cat_data["keywords"]:
            if kw in idea_lower:
                score += weight
        scores[cat_name] = score

    best_cat   = max(scores, key=lambda k: scores[k])
    best_score = scores[best_cat]

    # Fallback si aucun signal : "prompt_reveal" (cœur de @ownyourtime.ai)
    if best_score == 0:
        best_cat   = "prompt_reveal"
        confidence = 0.3
    else:
        total      = sum(max(s, 0.0) for s in scores.values()) or 1.0
        confidence = round(min(1.0, best_score / total), 2)

    cat = CATEGORIES[best_cat]
    return {
        "type":       best_cat,
        "label":      cat["label"],
        "label_en":   cat["label_en"],
        "angle":      cat["angle"],
        "angle_en":   cat["angle_en"],
        "confidence": confidence,
        "templates":  cat["abc_templates"],
        "scores":     scores,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Context builder — pour injection dans les prompts Claude
# ─────────────────────────────────────────────────────────────────────────────

def build_type_context(classification: dict, lang: str = "fr") -> str:
    """
    Construit le bloc de contexte à injecter dans le prompt Claude.
    Inclut le type, l'angle et des exemples de hooks par variant.
    """
    if classification.get("confidence", 0) < 0.25:
        return ""  # Trop incertain → ne pas biaiser Claude

    if lang == "en":
        label  = classification.get("label_en", classification.get("label", ""))
        angle  = classification.get("angle_en", classification.get("angle", ""))
        prefix = "CONTENT TYPE"
        tmpl_h = "Hook examples per variant"
        note   = "Generate hooks that match this content type and speak naturally to this audience."
    else:
        label  = classification.get("label", "")
        angle  = classification.get("angle", "")
        prefix = "TYPE DE CONTENU"
        tmpl_h = "Exemples de hooks par variante"
        note   = "Génère des hooks qui correspondent à ce type de contenu et sonnent naturellement."

    templates = classification.get("templates", {})
    lines = [
        f"── {prefix} : {label}  |  ANGLE : {angle} ──",
        f"{tmpl_h} :",
    ]
    for variant in ("A", "B", "C"):
        examples = templates.get(variant, [])
        # Filtrer les exemples dans la bonne langue
        if lang == "en":
            # Prendre les exemples EN (les derniers dans la liste)
            shown = [e for e in examples if not any(
                fr_char in e for fr_char in ["é", "è", "à", "ê", "ç", "ù", "â", "î", "ô", "û"]
            )][:2]
        else:
            # Prendre les exemples FR (les premiers dans la liste, pas EN)
            shown = [e for e in examples if any(
                c in e for c in ["é", "è", "à", "ê", "ç", "ù", "â", "î", "ô", "û"]
            ) or not any(
                # exclude obviously English ones
                kw in e.lower() for kw in [" i ", " i've", " you ", "here's", "tested"]
            )][:2]
        if shown:
            lines.append(f"  {variant} → " + " / ".join(f'"{e}"' for e in shown))

    lines.append(note)
    lines.append("")
    return "\n".join(lines)


def build_ab_type_context(classification: dict, lang: str = "fr") -> str:
    """
    Contexte plus détaillé pour le mode A/B testing.
    Inclut les 3 templates par variante pour guider le ton de chaque version.
    """
    if classification.get("confidence", 0) < 0.25:
        return ""

    if lang == "en":
        label  = classification.get("label_en", classification.get("label", ""))
        angle  = classification.get("angle_en", classification.get("angle", ""))
        prefix = "CONTENT TYPE"
        desc   = "Use these hook templates as tone reference per version:"
    else:
        label  = classification.get("label", "")
        angle  = classification.get("angle", "")
        prefix = "TYPE DE CONTENU"
        desc   = "Utilise ces templates comme référence de ton par version :"

    templates = classification.get("templates", {})
    lines = [
        f"── {prefix} : {label}  |  ANGLE : {angle} ──",
        desc,
    ]
    for variant, v_label in [("A", "Simple/Safe"), ("B", "Intrigue/Curiosité"), ("C", "Interruption/Direct")]:
        examples = templates.get(variant, [])[:2]
        if examples:
            lines.append(f"  {variant} ({v_label}) → " + " / ".join(f'"{e}"' for e in examples))
    lines.append("")
    return "\n".join(lines)
