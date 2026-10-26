"""The one egress helper the avito module uses: the Accept-Language a
session sends. Avito is a Russian site, so the scraper announces the
language list Chrome sends on a Russian machine (a browser language that
disagrees with the connection's country is a common bot signal).
"""
RUSSIAN = "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7"


def accept_language(proxy=None, country=None):
    """Accept-Language for a session on `proxy` (any proxy, or none)."""
    return RUSSIAN
