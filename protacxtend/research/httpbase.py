"""Async HTTP base for scientific API clients: retries, rate limiting, caching.

All source adapters inherit ``AsyncApiClient``:

  * async retry loop on 429 / 5xx / timeouts with exponential backoff + jitter
  * optional per-client rate delay (NCBI ~3 req/s without key) + concurrency
    semaphore
  * disk JSON cache keyed by (client name, request hash), TTL configurable
  * structured error reporting (retrieval code never crashes on a source)
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import random
import time
from pathlib import Path
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger("protacpilot.research.http")


class ClientError(Exception):
    def __init__(self, message: str, kind: str = "request_error", status: int | None = None):
        super().__init__(message)
        self.kind = kind
        self.status = status


class AsyncApiClient:
    name = "base"

    def __init__(self, base_url: str, *, cache_dir: Path, ttl_s: int,
                 user_agent: str = "", headers: dict[str, str] | None = None,
                 timeout_s: float = 25.0, connect_timeout_s: float = 10.0,
                 max_retries: int = 2, backoff_base_s: float = 1.2,
                 rate_delay_s: float = 0.0, semaphore: asyncio.Semaphore | None = None,
                 cache_enabled: bool = True, client: httpx.AsyncClient | None = None):
        self.base_url = (base_url or "").rstrip("/")
        self.cache_dir = Path(cache_dir) / self.name
        self.cache_ttl_s = ttl_s
        self.timeout = httpx.Timeout(timeout_s, connect=connect_timeout_s)
        self.headers = {"User-Agent": user_agent or "protacpilot-research/0.1"}
        if headers:
            self.headers.update(headers)
        self.max_retries = max_retries
        self.backoff_base_s = backoff_base_s
        self.rate_delay_s = rate_delay_s
        self._semaphore = semaphore
        self.cache_enabled = cache_enabled
        self._http = client or httpx.AsyncClient(timeout=self.timeout,
                                                 headers=self.headers,
                                                 follow_redirects=True)
        self._owns_http = client is None
        self._last_request_monotonic = 0.0

    # ── cache ──────────────────────────────────────────────────────────────
    def _cache_key(self, *parts: str) -> str:
        h = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:24]
        return h

    def _cache_path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.json"

    def _cache_get(self, key: str) -> Any | None:
        if not self.cache_enabled:
            return None
        try:
            path = self._cache_path(key)
            if not path.exists():
                return None
            meta = json.loads(path.read_text(encoding="utf-8"))
            if time.time() - meta.get("ts", 0) > self.cache_ttl_s:
                return None
            return meta.get("payload")
        except Exception:
            return None

    def _cache_set(self, key: str, payload: Any) -> None:
        if not self.cache_enabled:
            return
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            tmp = self._cache_path(key).with_suffix(".tmp")
            tmp.write_text(json.dumps({"ts": time.time(), "payload": payload}), encoding="utf-8")
            tmp.replace(self._cache_path(key))
        except Exception as exc:  # cache must never break retrieval
            logger.debug("cache write failed (%s): %s", self.name, exc)

    # ── rate limiting ──────────────────────────────────────────────────────
    async def _throttle(self) -> None:
        if self._semaphore is not None:
            await self._semaphore.acquire()
        try:
            if self.rate_delay_s > 0:
                wait = self.rate_delay_s - (time.monotonic() - self._last_request_monotonic)
                if wait > 0:
                    await asyncio.sleep(wait)
        finally:
            if self._semaphore is not None:
                self._semaphore.release()
        self._last_request_monotonic = time.monotonic()

    # ── request with retries ───────────────────────────────────────────────
    async def _request(self, method: str, url: str, *, params: dict[str, Any] | None = None,
                       json_body: dict[str, Any] | None = None,
                       headers: dict[str, str] | None = None) -> httpx.Response:
        cache_key = self._cache_key(method, url,
                                    json.dumps(params or {}, sort_keys=True),
                                    json.dumps(json_body or {}, sort_keys=True))
        if method.upper() == "GET":
            cached = self._cache_get(cache_key)
            if cached is not None:
                return _CachedResponse(cached)

        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                if self._semaphore is not None:
                    await self._semaphore.acquire()
                try:
                    if self.rate_delay_s > 0:
                        wait = self.rate_delay_s - (time.monotonic() - self._last_request_monotonic)
                        if wait > 0:
                            await asyncio.sleep(wait)
                    resp = await self._http.request(method, url, params=params,
                                                    json=json_body, headers=headers)
                finally:
                    if self._semaphore is not None:
                        self._semaphore.release()
                self._last_request_monotonic = time.monotonic()

                if resp.status_code in (429, 500, 502, 503, 504):
                    raise httpx.HTTPStatusError(
                        f"HTTP {resp.status_code}", request=resp.request, response=resp)
                if resp.status_code >= 400:
                    raise ClientError(f"HTTP {resp.status_code}: {resp.text[:200]}",
                                      kind="http", status=resp.status_code)
                if method.upper() == "GET":
                    self._cache_set(cache_key, _response_payload(resp))
                return resp
            except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
                last_exc = exc
                if attempt >= self.max_retries:
                    break
                delay = min(8.0, 0.5 * (self.backoff_base_s ** attempt)) + random.uniform(0, 0.4)
                logger.debug("[%s] retry %d after %.2fs (%s)", self.name, attempt + 1, delay,
                             type(exc).__name__)
                await asyncio.sleep(delay)
        raise last_exc or ClientError("request failed", kind="request_error")

    async def get_json(self, path_or_url: str, params: dict[str, Any] | None = None,
                       headers: dict[str, str] | None = None) -> Any:
        url = path_or_url if path_or_url.startswith("http") else f"{self.base_url}{path_or_url}"
        resp = await self._request("GET", url, params=params, headers=headers)
        return _response_payload(resp)

    async def get_text(self, path_or_url: str, params: dict[str, Any] | None = None) -> str:
        url = path_or_url if path_or_url.startswith("http") else f"{self.base_url}{path_or_url}"
        resp = await self._request("GET", url, params=params, headers={"Accept": "*/*"})
        return resp.text

    async def post_json(self, path_or_url: str, json_body: dict[str, Any]) -> Any:
        url = path_or_url if path_or_url.startswith("http") else f"{self.base_url}{path_or_url}"
        resp = await self._request("POST", url, json_body=json_body)
        return _response_payload(resp)

    async def aclose(self) -> None:
        if self._owns_http:
            await self._http.aclose()


class _CachedResponse:
    """Stand-in for httpx.Response built from a cached JSON payload."""

    def __init__(self, payload: Any):
        self._payload = payload

    @property
    def status_code(self) -> int:
        return 200

    @property
    def text(self) -> str:
        return json.dumps(self._payload)

    def json(self) -> Any:
        return self._payload

    def raise_for_status(self) -> None:
        return None


def _response_payload(resp: httpx.Response) -> Any:
    try:
        return resp.json()
    except Exception:
        return {"_raw_text": resp.text[:200_000]}
