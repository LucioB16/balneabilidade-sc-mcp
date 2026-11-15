"""Polite async HTTP client for the IMA/SC portal.

The portal is not a documented API: it can answer JSON with a text/html
content type, set a PHP session cookie, and return HTML error pages. This
client centralizes timeouts, bounded retries, response-size limits, redirects
and typed errors so adapters do not each invent their own policy.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx

from .errors import (
    ImaHTTPError,
    ImaNetworkError,
    ImaNotFound,
    ImaResponseTooLarge,
)

DEFAULT_USER_AGENT = "balneabilidade-sc-mcp/0.1 (research; polite; GitHub LucioB16/balneabilidade-sc-mcp)"
DEFAULT_MAX_BYTES = 10_000_000


@dataclass(frozen=True)
class HttpResponse:
    status_code: int
    content_type: str
    content: bytes
    url: str
    fetched_at: datetime

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", errors="replace")


class ImaHttpClient:
    def __init__(
        self,
        base_url: str = "https://balneabilidade.ima.sc.gov.br",
        *,
        timeout_seconds: float = 30.0,
        retries: int = 2,
        max_bytes: int = DEFAULT_MAX_BYTES,
        retry_delay_seconds: float = 0.25,
        min_request_interval_seconds: float = 0.0,
        user_agent: str = DEFAULT_USER_AGENT,
        transport: httpx.AsyncBaseTransport | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.base_url = base_url.rstrip("/") + "/"
        self.retries = max(0, retries)
        self.max_bytes = max_bytes
        self.retry_delay_seconds = max(0.0, retry_delay_seconds)
        self.min_request_interval_seconds = max(0.0, min_request_interval_seconds)
        self._request_pace_lock = asyncio.Lock()
        self._next_request_at = 0.0
        self._clock = clock
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(timeout_seconds),
            headers={"User-Agent": user_agent, "Accept": "*/*"},
            follow_redirects=True,
            transport=transport,
        )

    async def __aenter__(self) -> ImaHttpClient:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _pace_request(self) -> None:
        if self.min_request_interval_seconds == 0:
            return
        loop = asyncio.get_running_loop()
        async with self._request_pace_lock:
            now = loop.time()
            delay = max(0.0, self._next_request_at - now)
            if delay:
                await asyncio.sleep(delay)
            self._next_request_at = loop.time() + self.min_request_interval_seconds

    async def get(self, path: str, *, max_bytes: int | None = None) -> HttpResponse:
        return await self._request("GET", path, max_bytes=max_bytes)

    async def post_form(
        self,
        path: str,
        form: Mapping[str, str],
        *,
        max_bytes: int | None = None,
    ) -> HttpResponse:
        return await self._request("POST", path, form=form, max_bytes=max_bytes)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        form: Mapping[str, str] | None = None,
        max_bytes: int | None = None,
    ) -> HttpResponse:
        url = self.base_url + path.lstrip("/")
        limit = max_bytes if max_bytes is not None else self.max_bytes
        attempt = 0
        while True:
            delay = min(5.0, self.retry_delay_seconds * (2**attempt))
            try:
                await self._pace_request()
                response = await self._client.request(method, path.lstrip("/"), data=form)
            except httpx.TimeoutException as exc:
                if attempt < self.retries:
                    attempt += 1
                    await asyncio.sleep(delay)
                    continue
                raise ImaNetworkError(f"timeout after {self.retries + 1} attempts: {url}") from exc
            except httpx.TransportError as exc:
                if attempt < self.retries:
                    attempt += 1
                    await asyncio.sleep(delay)
                    continue
                raise ImaNetworkError(f"transport failure after {self.retries + 1} attempts: {url}") from exc

            if response.status_code == 404:
                raise ImaNotFound(f"not found: {url}")
            if response.status_code == 429 or response.status_code >= 500:
                if attempt < self.retries:
                    retry_after = _retry_after_seconds(response.headers.get("retry-after"))
                    attempt += 1
                    await asyncio.sleep(retry_after if retry_after is not None else delay)
                    continue
                raise ImaHTTPError(response.status_code, url)
            if response.status_code >= 400:
                raise ImaHTTPError(response.status_code, url)

            content = response.content
            if len(content) > limit:
                raise ImaResponseTooLarge(url, limit)
            declared = response.headers.get("content-length")
            if declared and declared.isdigit() and int(declared) > limit:
                raise ImaResponseTooLarge(url, limit)
            return HttpResponse(
                status_code=response.status_code,
                content_type=response.headers.get("content-type", ""),
                content=content,
                url=str(response.url),
                fetched_at=self._clock(),
            )


def _retry_after_seconds(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        seconds = float(value.strip())
    except ValueError:
        return None
    return min(5.0, max(0.0, seconds))
