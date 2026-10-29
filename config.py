"""Configuration for the Avito Scraper. Everything can be set with an
environment variable; the defaults work out of the box.

    PORT         port the API listens on (default 8000)
    AVITO_PROXY  proxy URL for every request, e.g. http://user:pass@host:port
                 (default: none — direct). Avito rate-limits busy IPs with a
                 captcha page; the scraper answers its proof-of-work check by
                 itself and retries a captcha on a fresh connection. For steady
                 volume, point this at a rotating Russian residential proxy, so
                 every retry leaves from a new IP.

Everything else below is a plain constant with a working default — edit it
here if you need to.
"""
import os

PORT = int(os.environ.get("PORT", "8000"))

# Retry policy for transport errors and blocks (every request).
MAX_RETRIES = 3
RETRY_BACKOFF = 2          # seconds, multiplied by the attempt number

# The proof-of-work difficulty the scraper answers (Avito asks for 3: ~4,000
# hashes, ~10 ms). Above this a challenge is treated as a block.
AVITO_MAX_POW_COMPLEXITY = 5


def avito_proxy():
    """The proxy for one session (None = direct)."""
    return os.environ.get("AVITO_PROXY") or None
