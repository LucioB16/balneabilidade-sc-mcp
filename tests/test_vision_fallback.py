from datetime import date

from balneabilidade_sc_mcp.bulletin import parse_bulletin_text
from balneabilidade_sc_mcp.errors import ImaPdfParseIncomplete
from balneabilidade_sc_mcp.models import BeachStatus, Freshness

from .conftest import (
    FETCHED_AT,
    MUNICIPALITIES,
    make_analyses,
    make_csv_export,
    make_provider,
    read_fixture,
)

MINI = """RELATÓRIO Nº 99
DATA: 13/11/2026
Porto Belo
Praia de Perequê (Ponto 03)
09/11/2026 PRÓPRIA
"""


async def test_incomplete_bulletin_exposes_vision_fallback() -> None:
    bulletin = parse_bulletin_text(
        MINI,
        source_url="https://example.test/mini.pdf",
        fetched_at=FETCHED_AT,
        bulletin_date_hint=date(2026, 11, 13),
        known_municipalities=MUNICIPALITIES,
    )
    provider = make_provider(
        bulletin=bulletin,
        history_exports={("Porto Belo", "Praia de Perequê", 2026): make_csv_export()},
    )
    result = await provider.get_bathing_status("Praia de Perequê", municipality="Porto Belo")
    assert result.vision_fallback is not None
    assert result.vision_fallback.page_count == 1
    assert result.vision_fallback.pages_available == (1,)
    assert "get_bulletin_page" in result.vision_fallback.instructions
    assert result.summary.status is BeachStatus.PARTIAL


async def test_parse_failure_exposes_vision_fallback_and_csv_fallback() -> None:
    pdf = read_fixture("synthetic_bulletin.pdf")
    error = ImaPdfParseIncomplete(
        "no rows",
        pdf_bytes=pdf,
        bulletin_date=date(2026, 11, 13),
        source_url="https://example.test/broken.pdf",
    )
    provider = make_provider(
        bulletin_error=error,
        history_exports={("Porto Belo", "Praia de Perequê", 2026): make_csv_export()},
        analyses=make_analyses(),
    )
    result = await provider.get_bathing_status("Praia de Perequê", municipality="Porto Belo")
    assert result.vision_fallback is not None
    assert result.vision_fallback.page_count == 1
    assert result.bulletin_unverified is True
    assert result.summary.status is BeachStatus.PARTIAL
    assert all(status.freshness is Freshness.UNVERIFIED for status in result.points)


async def test_provider_can_render_a_page_for_vision_client() -> None:
    provider = make_provider()
    page = await provider.get_bulletin_page(page=1, dpi=100)
    assert page.page_number == 1
    assert page.data.startswith(b"\x89PNG")
