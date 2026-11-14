import httpx

from balneabilidade_sc_mcp.analyses import ANALYSES_URL, AnalysesRepository, parse_analyses
from balneabilidade_sc_mcp.cache import MemoryCache
from balneabilidade_sc_mcp.http import ImaHttpClient
from balneabilidade_sc_mcp.models import Classification

from .conftest import FETCHED_AT, make_analyses


def test_empty_analyses_array_is_valid_no_data() -> None:
    result = parse_analyses(
        b"[]",
        point_id="00000000-0000-4000-8000-000000000003",
        fetched_at=FETCHED_AT,
        source_url=ANALYSES_URL,
    )
    assert result.samples == ()


def test_analyses_parse_dates_and_labels() -> None:
    result = make_analyses()
    assert len(result.samples) == 5
    assert result.samples[0].sample_date.isoformat() == "2026-11-09"
    assert result.samples[0].classification is Classification.PROPER
    assert result.samples[0].ecoli is not None
    assert result.samples[0].ecoli.value == 373


async def test_analyses_repository_caches_empty_result() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, headers={"content-type": "application/json"}, content=b"[]")

    http = ImaHttpClient(transport=httpx.MockTransport(handler))
    repository = AnalysesRepository(http, MemoryCache())
    first = await repository.fetch("00000000-0000-4000-8000-000000000003")
    second = await repository.fetch("00000000-0000-4000-8000-000000000003")
    assert first.samples == ()
    assert second.samples == ()
    assert len(calls) == 1
