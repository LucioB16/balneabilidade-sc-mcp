import json

import httpx
import pytest

from balneabilidade_sc_mcp.cache import MemoryCache
from balneabilidade_sc_mcp.catalog import (
    CATALOG_CACHE_KEY,
    CatalogRepository,
    parse_catalog,
    resolve_beach,
    search_beaches,
)
from balneabilidade_sc_mcp.errors import ImaAmbiguousQuery, ImaInvalidArgument, ImaNotFound, ImaSchemaError
from balneabilidade_sc_mcp.http import ImaHttpClient

from .conftest import FETCHED_AT, read_fixture


def test_catalog_counts_and_groups(catalog) -> None:
    assert len(catalog.points) == 11
    assert len(catalog.beaches) == 8
    pereque = resolve_beach(catalog, "Praia de Perequê")
    assert pereque.point_count == 3
    assert pereque.municipality == "Porto Belo"


def test_search_folds_accents_and_finds_duplicate_names(catalog) -> None:
    matches = search_beaches(catalog, "praia brava")
    assert len(matches) == 2
    assert {match.beach.municipality for match in matches} == {"Florianópolis", "Itajaí"}
    assert all(match.match_type == "exact" for match in matches)

    one = search_beaches(catalog, "PRAIA BRAVA", municipality="Itajaí")
    assert len(one) == 1
    assert one[0].beach.municipality == "Itajaí"

    pereque = search_beaches(catalog, "PEREQUE")
    assert len(pereque) == 1
    assert pereque[0].beach.name == "Praia de Perequê"


def test_resolve_ambiguous_beach_never_guesses(catalog) -> None:
    with pytest.raises(ImaAmbiguousQuery):
        resolve_beach(catalog, "Praia Brava")
    resolved = resolve_beach(catalog, "Praia Brava", municipality="Florianópolis")
    assert resolved.point_count == 1


def test_invalid_catalog_payloads() -> None:
    with pytest.raises(ImaSchemaError):
        parse_catalog(b"{not json", fetched_at=FETCHED_AT)
    with pytest.raises(ImaSchemaError):
        parse_catalog(b"{}", fetched_at=FETCHED_AT)
    with pytest.raises(ImaSchemaError):
        parse_catalog(
            json.dumps([{"CODIGO": "bad", "MUNICIPIO": "X", "BALNEARIO": "Y", "PONTO_NOME": "P"}]).encode(),
            fetched_at=FETCHED_AT,
        )


def test_duplicate_point_uuid_is_skipped_with_warning() -> None:
    payload = json.loads(read_fixture("catalog.json"))
    payload.append(dict(payload[0]))
    parsed = parse_catalog(json.dumps(payload).encode(), fetched_at=FETCHED_AT)
    assert len(parsed.points) == 11
    assert any("duplicate point" in warning for warning in parsed.warnings)


def test_search_and_resolve_validation(catalog) -> None:
    with pytest.raises(ImaInvalidArgument):
        search_beaches(catalog, "   ")
    with pytest.raises(ImaInvalidArgument):
        search_beaches(catalog, "praia", limit=0)
    with pytest.raises(ImaNotFound):
        resolve_beach(catalog, "does not exist")


async def test_catalog_repository_caches_map_request() -> None:
    calls: list[httpx.Request] = []
    payload = read_fixture("catalog.json")

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, headers={"content-type": "text/html"}, content=payload)

    http = ImaHttpClient(transport=httpx.MockTransport(handler))
    cache = MemoryCache()
    repository = CatalogRepository(http, cache)
    first = await repository.load()
    second = await repository.load()
    assert len(first.points) == 11
    assert len(second.points) == 11
    assert len(calls) == 1
    assert calls[0].method == "POST"
    assert str(calls[0].url).endswith("/relatorio/mapa")
    assert CATALOG_CACHE_KEY
