"""Canonical municipality/beach/point catalog from /relatorio/mapa.

The map response is the only single request that exposes every IMA point UUID
and its coordinates. Its undated CONDICAO is deliberately discarded here: this
module builds identity, not status.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from datetime import datetime, timedelta

from .cache import Cache, utcnow
from .errors import ImaAmbiguousQuery, ImaInvalidArgument, ImaNotFound, ImaSchemaError
from .http import ImaHttpClient
from .models import BeachMatch, Catalog, CatalogBeach, CatalogPoint
from .normalization import fold

MAP_PATH = "/relatorio/mapa"
MAP_URL = "https://balneabilidade.ima.sc.gov.br/relatorio/mapa"
CATALOG_CACHE_KEY = "catalog:relatorio:mapa"


def parse_catalog(
    payload: bytes | str,
    *,
    fetched_at: datetime,
    source_url: str = MAP_URL,
    stale: bool = False,
) -> Catalog:
    raw = payload.decode("utf-8", errors="replace") if isinstance(payload, bytes) else payload
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ImaSchemaError("map response is not valid JSON") from exc
    if not isinstance(data, list):
        raise ImaSchemaError("map response is not a JSON array")

    points: list[CatalogPoint] = []
    seen: set[str] = set()
    warnings: list[str] = []
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            warnings.append(f"map item {index} is not an object")
            continue
        point_id = str(item.get("CODIGO", "")).strip()
        municipality = str(item.get("MUNICIPIO", "")).strip()
        beach = str(item.get("BALNEARIO", "")).strip()
        point_name = str(item.get("PONTO_NOME", "")).strip()
        if not point_id or not municipality or not beach or not point_name:
            warnings.append(f"map item {index} lacks CODIGO/MUNICIPIO/BALNEARIO/PONTO_NOME")
            continue
        try:
            uuid.UUID(point_id)
        except ValueError:
            warnings.append(f"map item {index} has a non-UUID CODIGO: {point_id!r}")
            continue
        if point_id in seen:
            warnings.append(f"duplicate point CODIGO skipped: {point_id}")
            continue
        seen.add(point_id)
        location = str(item.get("LOCALIZACAO", "") or "").strip()
        latitude = _coordinate(item.get("LATITUDE"), -90.0, 90.0)
        longitude = _coordinate(item.get("LONGITUDE"), -180.0, 180.0)
        hidden = str(item.get("OCULTAR", "N")).strip().upper() == "Y"
        points.append(
            CatalogPoint(
                point_id=point_id,
                municipality=municipality,
                beach=beach,
                point_name=point_name,
                location=location,
                latitude=latitude,
                longitude=longitude,
                hidden=hidden,
            )
        )
    if not points:
        raise ImaSchemaError("map response contained no usable points")
    return Catalog(
        points=tuple(points),
        fetched_at=fetched_at,
        source_url=source_url,
        stale=stale,
        warnings=tuple(warnings),
    )


def _coordinate(value: object, low: float, high: float) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(str(value).strip())
    except ValueError:
        return None
    if not low <= parsed <= high:
        return None
    return parsed


class CatalogRepository:
    def __init__(
        self,
        http: ImaHttpClient,
        cache: Cache,
        *,
        ttl: timedelta = timedelta(hours=24),
        clock: Callable[[], datetime] = utcnow,
    ) -> None:
        self._http = http
        self._cache = cache
        self._ttl = ttl
        self._clock = clock

    async def load(self, *, force: bool = False) -> Catalog:
        if not force:
            cached = await self._cache.get(CATALOG_CACHE_KEY)
            if cached is not None:
                return parse_catalog(
                    cached.data,
                    fetched_at=cached.fetched_at,
                    source_url=MAP_URL,
                    stale=False,
                )
        try:
            response = await self._http.post_form(MAP_PATH, {})
        except Exception:
            stale = await self._cache.get(CATALOG_CACHE_KEY, allow_stale=True)
            if stale is None:
                raise
            catalog = parse_catalog(
                stale.data,
                fetched_at=stale.fetched_at,
                source_url=MAP_URL,
                stale=True,
            )
            return _with_warning(catalog, "catalog refresh failed; serving stale catalog")
        catalog = parse_catalog(
            response.content,
            fetched_at=response.fetched_at,
            source_url=MAP_URL,
            stale=False,
        )
        await self._cache.set(
            CATALOG_CACHE_KEY,
            response.content,
            response.content_type,
            self._ttl,
        )
        return catalog


def _with_warning(catalog: Catalog, warning: str) -> Catalog:
    return Catalog(
        points=catalog.points,
        fetched_at=catalog.fetched_at,
        source_url=catalog.source_url,
        stale=catalog.stale,
        warnings=(*catalog.warnings, warning),
    )


def search_beaches(
    catalog: Catalog,
    query: str,
    *,
    municipality: str | None = None,
    limit: int = 10,
) -> tuple[BeachMatch, ...]:
    needle = fold(query)
    if not needle:
        raise ImaInvalidArgument("query must not be empty")
    if not 1 <= limit <= 20:
        raise ImaInvalidArgument("limit must be between 1 and 20")
    ranked: list[tuple[int, BeachMatch]] = []
    for beach in catalog.beaches:
        if all(point.hidden for point in beach.points):
            continue
        if municipality is not None and fold(beach.municipality) != fold(municipality):
            continue
        folded_name = fold(beach.name)
        folded_key = fold(beach.key)
        if needle in (folded_key, folded_name):
            score, match_type = 0, "exact"
        elif folded_name.startswith(needle):
            score, match_type = 1, "prefix"
        elif needle in folded_name:
            score, match_type = 2, "contains"
        else:
            continue
        ranked.append((score, BeachMatch(beach=beach, match_type=match_type)))
    ranked.sort(key=lambda item: (item[0], fold(item[1].beach.municipality), fold(item[1].beach.name)))
    return tuple(match for _, match in ranked[:limit])


def resolve_beach(
    catalog: Catalog,
    beach: str,
    *,
    municipality: str | None = None,
) -> CatalogBeach:
    folded = fold(beach)
    if not folded:
        raise ImaInvalidArgument("beach must not be empty")
    candidates: list[CatalogBeach] = []
    for item in catalog.beaches:
        if all(point.hidden for point in item.points):
            continue
        if municipality is not None and fold(item.municipality) != fold(municipality):
            continue
        if folded in (fold(item.key), fold(item.name)):
            candidates.append(item)
    if not candidates:
        raise ImaNotFound(f"no beach matched {beach!r}")
    if len(candidates) > 1:
        raise ImaAmbiguousQuery(beach, candidates)
    return candidates[0]


def find_point(beach: CatalogBeach, point_id: str | None) -> CatalogPoint:
    if point_id is None:
        raise ImaInvalidArgument("point_id is required here")
    for point in beach.points:
        if point.point_id == point_id:
            return point
    raise ImaNotFound(f"point {point_id!r} does not belong to {beach.name!r}")
