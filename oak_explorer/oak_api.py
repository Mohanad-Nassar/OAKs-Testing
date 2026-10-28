"""A small client for Oak's Open API (https://open-api.thenational.academy/docs).

Needs an API key, passed in or read from the OAK_API_KEY environment variable.
"""

import json
import os
import re
import time
import urllib.error
import urllib.request

API = "https://open-api.thenational.academy/api/v0"


class OakAPIError(RuntimeError):
    pass


class Unavailable(OakAPIError):
    """Oak won't serve this item: unknown, not published yet, or blocked for copyright."""


class OakAPI:
    def __init__(self, key: str | None = None) -> None:
        self.key = key or os.environ.get("OAK_API_KEY")
        if not self.key:
            raise OakAPIError("Set OAK_API_KEY to your Oak Open API key.")
        self.requests = 0

    def get(self, path: str) -> tuple[object, str | None]:
        """GET a JSON resource; returns the body and the rel="next" URL, if any."""
        url = path if path.startswith("http") else f"{API}{path}"
        req = urllib.request.Request(
            url, headers={"Authorization": f"Bearer {self.key}", "User-Agent": "oak-explorer/0.1"}
        )
        for attempt in range(4):
            self.requests += 1
            try:
                with urllib.request.urlopen(req) as resp:
                    if int(resp.headers.get("X-RateLimit-Remaining", "1")) < 5:
                        raise OakAPIError("Oak API rate limit nearly used up; try again in an hour.")
                    match = re.search(r'<([^>]+)>;\s*rel="next"', resp.headers.get("Link", ""))
                    return json.load(resp), match.group(1) if match else None
            except urllib.error.HTTPError as exc:
                if exc.code in (400, 404):
                    raise Unavailable(f"{url}: {exc.read()[:200].decode(errors='replace')}") from exc
                if exc.code == 401:
                    raise OakAPIError("Oak API rejected the key (401). Check OAK_API_KEY.") from exc
                if exc.code == 429 or exc.code >= 500:
                    time.sleep(2**attempt)
                    continue
                raise
        raise OakAPIError(f"Giving up on {url}")

    def get_one(self, path: str):
        return self.get(path)[0]

    def get_all(self, path: str) -> list:
        """Follow rel="next" pagination and concatenate the pages."""
        items: list = []
        url: str | None = path
        while url:
            page, url = self.get(url)
            items.extend(page)
        return items
