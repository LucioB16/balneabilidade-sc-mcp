"""Per-point dated analyses (last five) from /relatorio/analisesPonto.

This endpoint is undocumented but is called by the portal itself. It is a
cross-check/fallback: it has no bulletin publication date or exclusion context
and can include a sample the bulletin later discards.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime, timedelta

from .cache import Cache, utcnow
from .errors import ImaInvalidArgument, ImaSchemaError
from .http import ImaHttpClient
from .models import AnalysesResult, AnalysesSample, Ecoli
from .normalization import (
    classification_from_label,
    parse_br_date,
    parse_ecoli,
    parse_float,
)

ANALYSES_PATH = "/relatorio/analisesPonto"
ANALYSES_URL = "https://balneabilidade.ima.sc.gov.br/relatorio/analisesPonto"
ANALYSES_TTL = timedelta(hours=1)


def parse_analyses(
    payload: bytes | str,
    *,
    point_id: str,
    fetched_at: datetime,
    source_url: str = ANALYSES_URL,
    stale: bool = False,
) -> AnalysesResult:
    text = payload.decode("utf-8", errors="replace") if isinstance(payload, bytes) else payload
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ImaSchemaError("analyses response is not valid JSON") from exc
    if not isinstance(data, list):
        raise ImaSchemaError("analyses response is not a JSON array")
    samples: list[AnalysesSample] = []
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            raise ImaSchemaError(f"analyses item {index} is not an object")
        raw_date = str(item.get("DATA", "")).strip()
        if not raw_date:
            raise ImaSchemaError(f"analyses item {index} has no DATA")
        try:
            sample_date = parse_br_date(raw_date)
        except ValueError as exc:
            raise ImaSchemaError(f"analyses item {index} has invalid DATA {raw_date!r}") from exc
        raw_label = str(item.get("CONDICAO", "")).strip()
        result_raw = str(item.get("RESULTADO", "")).strip() or None
        value, qualifier, raw_ecoli = parse_ecoli(result_raw)
        samples.append(
            AnalysesSample(
                sample_date=sample_date,
                classification=classification_from_label(raw_label),
                raw_classification=raw_label,
                rain=str(item.get("CHUVA", "")).strip() or None,
                result_raw=result_raw,
                ecoli=Ecoli.from_parts(value, qualifier, raw_ecoli),
                water_temp_c=parse_float(str(item.get("TEMP_AGUA", "")).strip() or None),
            )
        )
    samples.sort(key=lambda sample: sample.sample_date, reverse=True)
    return AnalysesResult(
        point_id=point_id,
        samples=tuple(samples),
        fetched_at=fetched_at,
        source_url=source_url,
        stale=stale,
    )


class AnalysesRepository:
    def __init__(
        self,
        http: ImaHttpClient,
        cache: Cache,
        *,
        ttl: timedelta = ANALYSES_TTL,
        clock: Callable[[], datetime] = utcnow,
    ) -> None:
        self._http = http
        self._cache = cache
        self._ttl = ttl
        self._clock = clock

    async def fetch(self, point_id: str) -> AnalysesResult:
        if not point_id.strip():
            raise ImaInvalidArgument("point_id is required")
        cache_key = f"analyses:{point_id}"
        cached = await self._cache.get(cache_key)
        if cached is not None:
            return parse_analyses(
                cached.data,
                point_id=point_id,
                fetched_at=cached.fetched_at,
            )
        try:
            response = await self._http.post_form(ANALYSES_PATH, {"codigo": point_id})
        except Exception:
            stale = await self._cache.get(cache_key, allow_stale=True)
            if stale is None:
                raise
            result = parse_analyses(
                stale.data,
                point_id=point_id,
                fetched_at=stale.fetched_at,
                stale=True,
            )
            return result
        result = parse_analyses(
            response.content,
            point_id=point_id,
            fetched_at=response.fetched_at,
        )
        await self._cache.set(cache_key, response.content, response.content_type, self._ttl)
        return result
