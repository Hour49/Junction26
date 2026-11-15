"""The one way the Gemini adapters open a request: `urllib.request.urlopen`, and a bounded retry
for the two answers that mean "try again in a moment" (429 too many requests, 503 unavailable).

Every call the adapters make is a read: the same request asked twice gives an answer of the same
kind and the spend guard charges only a reply that came back, so asking again is safe. At most
`RETRIES` more tries, after `DELAYS` seconds (3 s in all). Any other failure (402, 400, 5xx other
than 503, a timeout, a reset, a reply that is not JSON) is raised at once for the caller to name:
a timeout already waited its full time, and a 402 will not clear in seconds.
"""

import time
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

RETRIED = frozenset({429, 503})
DELAYS = (1.0, 2.0)


def urlopen(
    request: urllib.request.Request,
    timeout: float,
    sleep: Callable[[float], None] | None = None,
) -> Any:
    """The response (a context manager, as `urllib.request.urlopen` gives it)."""
    for delay in DELAYS:
        try:
            return urllib.request.urlopen(request, timeout=timeout)
        except urllib.error.HTTPError as error:
            if error.code not in RETRIED:
                raise
            error.close()
            (sleep or time.sleep)(delay)  # looked up now, so a test can replace it
    return urllib.request.urlopen(request, timeout=timeout)
