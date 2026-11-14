from datetime import UTC, datetime

import httpx
import pytest

from balneabilidade_sc_mcp.cache import MemoryCache
from balneabilidade_sc_mcp.errors import ImaInvalidArgument
from balneabilidade_sc_mcp.history import CsvHistoryRepository, parse_csv
from balneabilidade_sc_mcp.http import ImaHttpClient
from balneabilidade_sc_mcp.models import Qualifier

from .conftest import FETCHED_AT, read_fixture


def _payload() -> bytes:
    return b"\xef\xbb\xbf" + read_fixture("pereque_2026.csv")


def test_csv_parses_bom_censored_values_and_sem_registros() -> None:
    export = parse_csv(
        _payload(),
        municipality="Porto Belo",
        beach="Praia de Perequê",
        year=2026,
        fetched_at=FETCHED_AT,
    )
    assert len(export.samples) == 4
    assert export.no_data_points == ("Ponto 04",)
    assert len(export.header) == 13
    ponto_05 = next(sample for sample in export.samples if sample.point_name == "Ponto 05")
    assert ponto_05.ecoli is not None
    assert ponto_05.ecoli.value == 20
    assert ponto_05.ecoli.qualifier is Qualifier.BELOW
    assert ponto_05.raw_classification == "PRÓPRIA"


def test_header_only_csv_is_valid_no_data() -> None:
    export = parse_csv(
        b"Municipio,Balneario,Ponto Coleta,Localizacao,Data,Hora,Vento,Mare,Chuva,Agua,Ar,Ecoli,Condicao\n",
        municipality="Porto Belo",
        beach="Praia de Perequê",
        year=2026,
        fetched_at=FETCHED_AT,
    )
    assert export.samples == ()
    assert export.no_data_points == ()


async def test_csv_repository_posts_form_and_caches() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(
            200, headers={"content-type": "text/csv; charset=UTF-8"}, content=_payload()
        )

    http = ImaHttpClient(transport=httpx.MockTransport(handler))
    cache = MemoryCache()
    repository = CsvHistoryRepository(http, cache)
    first = await repository.fetch("Porto Belo", "Praia de Perequê", 2026)
    second = await repository.fetch("Porto Belo", "Praia de Perequê", 2026)
    assert len(first.samples) == 4
    assert len(second.samples) == 4
    assert len(calls) == 1
    assert calls[0].method == "POST"
    assert str(calls[0].url).endswith("/relatorio/exportarCSV")
    body = calls[0].content.decode()
    assert "municipioID=Porto+Belo" in body
    assert "ano=2026" in body


async def test_csv_repository_rejects_out_of_range_year() -> None:
    repository = CsvHistoryRepository(
        ImaHttpClient(transport=httpx.MockTransport(lambda request: httpx.Response(500))),
        MemoryCache(),
        clock=lambda: datetime(2026, 11, 14, tzinfo=UTC),
    )
    with pytest.raises(ImaInvalidArgument):
        await repository.fetch("Porto Belo", "Praia de Perequê", 1999)
