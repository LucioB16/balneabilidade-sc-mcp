from datetime import date

import httpx
import pytest

from balneabilidade_sc_mcp.bulletin import (
    BulletinRepository,
    PypdfExtractor,
    parse_bulletin_text,
    parse_index,
)
from balneabilidade_sc_mcp.cache import MemoryCache
from balneabilidade_sc_mcp.errors import ImaSchemaError
from balneabilidade_sc_mcp.http import ImaHttpClient

from .conftest import FETCHED_AT, MUNICIPALITIES, make_bulletin, read_fixture


def test_current_bulletin_parses_rows_municipalities_and_exclusions() -> None:
    bulletin = make_bulletin()
    assert bulletin.report_number == "53"
    assert bulletin.bulletin_date == date(2026, 11, 13)
    assert bulletin.collection_dates == (
        date(2026, 11, 9),
        date(2026, 11, 10),
        date(2026, 11, 11),
    )
    assert len(bulletin.rows) == 9
    assert bulletin.excluded_point_numbers == frozenset({83, 94, 96})
    assert bulletin.discarded_point_numbers == frozenset({83})
    assert "Ponto 83" in bulletin.exclusion_text
    by_point = {(row.beach, row.point_name): row for row in bulletin.rows}
    assert by_point[("Lagoa Boca da Barra - Na foz do Canal do Linguado", "Ponto 02")].municipality == (
        "Balneário Barra do Sul"
    )
    assert by_point[("Praia de Zimbros", "Ponto 09")].classification.value == "improper"


def test_off_season_bulletin_uses_monthly_collection_date() -> None:
    bulletin = make_bulletin("bulletin_46_2026.txt")
    assert bulletin.report_number == "46"
    assert bulletin.bulletin_date == date(2026, 9, 24)
    assert bulletin.collection_dates == (date(2026, 9, 21),)
    assert len(bulletin.rows) == 2
    assert bulletin.rows[0].sample_date == date(2026, 8, 26)


def test_bulletin_without_date_or_hint_fails_loudly() -> None:
    with pytest.raises(ImaSchemaError):
        parse_bulletin_text(
            "RELATÓRIO Nº 1\nPraia X (Ponto 01)\n09/11/2026 PRÓPRIA",
            source_url="https://example.test/bulletin.pdf",
            fetched_at=FETCHED_AT,
        )


def test_failed_pdf_page_is_a_warning_not_a_fatal_error() -> None:
    bulletin = parse_bulletin_text(
        read_fixture("bulletin_53_2026.txt").decode(),
        source_url="https://example.test/bulletin.pdf",
        fetched_at=FETCHED_AT,
        bulletin_date_hint=date(2026, 11, 13),
        known_municipalities=MUNICIPALITIES,
        failed_pages=(19,),
    )
    assert any("failed to extract" in warning for warning in bulletin.warnings)


def test_index_latest_date() -> None:
    html = """
    <a href="https://balneabilidade.ima.sc.gov.br/relatorio/downloadPDF/2026-11-06">x</a>
    <a href="https://balneabilidade.ima.sc.gov.br/relatorio/downloadPDF/2026-11-13">y</a>
    """
    index = parse_index(html, fetched_at=FETCHED_AT)
    assert index.latest == date(2026, 11, 13)
    with pytest.raises(ImaSchemaError):
        parse_index("<html>no links</html>", fetched_at=FETCHED_AT)


async def test_bulletin_repository_discovers_and_caches_pdf() -> None:
    calls: list[httpx.Request] = []
    pdf = read_fixture("synthetic_bulletin.pdf")
    html = b'<a href="/relatorio/downloadPDF/2026-11-13">x</a>'

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.url.path == "/":
            return httpx.Response(200, headers={"content-type": "text/html"}, content=html)
        if request.url.path == "/relatorio/downloadPDF/2026-11-13":
            return httpx.Response(200, headers={"content-type": "application/pdf"}, content=pdf)
        return httpx.Response(404)

    http = ImaHttpClient(transport=httpx.MockTransport(handler))
    cache = MemoryCache()
    repository = BulletinRepository(http, cache, extractor=PypdfExtractor())
    assert await repository.latest_date() == date(2026, 11, 13)
    bulletin = await repository.fetch(known_municipalities=("Porto Belo", "Bombinhas"))
    assert len(bulletin.rows) == 2
    assert bulletin.rows[0].municipality == "Porto Belo"
    await repository.fetch(known_municipalities=("Porto Belo", "Bombinhas"))
    assert len(calls) == 2
