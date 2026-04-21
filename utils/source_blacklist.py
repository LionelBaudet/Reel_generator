# -*- coding: utf-8 -*-
"""
utils/source_blacklist.py — Domaines à exclure du pipeline de signaux.
Sources peu fiables, clickbait, fermes de contenu, désinformation, spam.
"""
from __future__ import annotations
from urllib.parse import urlparse

# ── Domaines blacklistés ──────────────────────────────────────────────────────
# Matching par sous-chaîne du netloc (sans www.)

BLACKLISTED_DOMAINS: list[str] = [
    # Désinformation / complotisme
    "naturalnews.com",
    "zerohedge.com",
    "infowars.com",
    "breitbart.com",
    "thegatewaypundit.com",
    # Propaganda / médias d'État non fiables
    "rt.com",
    "sputniknews.com",
    "sputnik",
    # Clickbait / fermes de contenu
    "buzzfeed.com",
    "viralnova.com",
    "upworthy.com",
    "brightside.me",
    "9gag.com",
    "boredpanda.com",
    "distractify.com",
    "shareably.net",
    "elitedaily.com",
    "thechive.com",
    "auntyacid.com",
    "goodfullness.com",
    "lifebuzz.com",
    "hefty.co",
    # Tabloïds / people
    "dailymail.co.uk",
    "thesun.co.uk",
    "mirror.co.uk",
    "tmz.com",
    "pagesix.com",
    "gala.fr",
    "voici.fr",
    "public.fr",
    # Communiqués de presse déguisés en news
    "businesswire.com",
    "prnewswire.com",
    "globenewswire.com",
    "accesswire.com",
    "einpresswire.com",
    "prlog.org",
    # SEO spam / listes / contenu bas de gamme
    "listverse.com",
    "ranker.com",
    "cracked.com",
    # Crypto/finance spam
    "coindesk.com",    # borderline mais trop niche
    "cointelegraph.com",
    "cryptonews.com",
    "beincrypto.com",
]

# Patterns à exclure dans n'importe quel domaine
_BLACKLIST_PATTERNS: list[str] = [
    "casino", "betting", "forex-", "crypto-pump", "nft-drop",
    "clickbait", "spammy", "contentfarm",
]


def is_blacklisted_domain(url: str) -> bool:
    """
    Retourne True si l'URL appartient à un domaine ou pattern blacklisté.
    """
    if not url:
        return False
    try:
        netloc = urlparse(url).netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
    except Exception:
        return False

    for bl in BLACKLISTED_DOMAINS:
        if bl in netloc:
            return True
    for pattern in _BLACKLIST_PATTERNS:
        if pattern in netloc:
            return True
    return False
