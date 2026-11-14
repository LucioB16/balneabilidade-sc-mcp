from datetime import date

from balneabilidade_sc_mcp.bulletin import PypdfExtractor, parse_bulletin_text

from .conftest import FETCHED_AT, read_fixture


def test_synthetic_pdf_extracts_and_parses() -> None:
    extracted = PypdfExtractor().extract(read_fixture("synthetic_bulletin.pdf"))
    assert extracted.failed_pages == ()
    assert "DATA: 13/11/2026" in extracted.text
    bulletin = parse_bulletin_text(
        extracted.text,
        source_url="https://example.test/bulletin.pdf",
        fetched_at=FETCHED_AT,
        bulletin_date_hint=date(2026, 11, 13),
        known_municipalities=("Porto Belo", "Bombinhas"),
    )
    assert bulletin.report_number == "53"
    assert bulletin.bulletin_date == date(2026, 11, 13)
    assert len(bulletin.rows) == 2
    assert bulletin.rows[0].municipality == "Porto Belo"
    assert bulletin.rows[0].classification.value == "proper"
    assert bulletin.rows[1].classification.value == "improper"
