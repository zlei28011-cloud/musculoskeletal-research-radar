from __future__ import annotations

import json
import logging
import random
import time
import urllib.error
import urllib.parse
import urllib.request

LOG = logging.getLogger(__name__)


class HttpClient:
    def __init__(self, user_agent: str, min_interval: float = 0.35, retries: int = 3):
        self.user_agent = user_agent
        self.min_interval = min_interval
        self.retries = retries
        self._last_request = 0.0

    def get(self, url: str, params: dict | None = None) -> bytes:
        if params:
            url = f"{url}?{urllib.parse.urlencode(params, doseq=True)}"
        for attempt in range(self.retries + 1):
            wait = self.min_interval - (time.monotonic() - self._last_request)
            if wait > 0:
                time.sleep(wait)
            request = urllib.request.Request(url, headers={"User-Agent": self.user_agent, "Accept": "application/json"})
            try:
                self._last_request = time.monotonic()
                with urllib.request.urlopen(request, timeout=30) as response:
                    return response.read()
            except (urllib.error.URLError, TimeoutError) as exc:
                if attempt >= self.retries:
                    raise
                delay = (2 ** attempt) + random.random()
                LOG.warning("HTTP retry %s/%s for %s: %s", attempt + 1, self.retries, url, exc)
                time.sleep(delay)
        raise RuntimeError("unreachable")

    def json(self, url: str, params: dict | None = None) -> dict:
        return json.loads(self.get(url, params).decode("utf-8"))
