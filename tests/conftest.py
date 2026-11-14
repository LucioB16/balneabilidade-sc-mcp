from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import pytest

from balneabilidade_sc_mcp.analyses import ANALYSES_URL, parse_analyses
from balneabilidade_sc_mcp.bulletin import BulletinBundle, parse_bulletin_text
from balneabilidade_sc_mcp.cache import MemoryCache
from balneabilidade_sc_mcp.catalog import parse_catalog
from balneabilidade_sc_mcp.history import CSV_URL, parse_csv
from balneabilidade_sc_mcp.http import ImaHttpClient
from balneabilidade_sc_mcp.models import (
    AnalysesResult,
    Bulletin,
    Catalog,
    CsvExport,
)
from balneabilidade_sc_mcp.provider import ImaProvider

FIXTURES = Path(__file__).parent / "fixtures"
FETCHED_AT = datetime(2026, 11, 14, 22, 0, tzinfo=UTC)
TODAY = date(2026, 11, 14)
MUNICIPALITIES = (
    "Porto Belo",
    "Bombinhas",
    "Florianópolis",
    "Itajaí",
    "Balneário Barra do Sul",
)


def read_fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def make_catalog() -> Catalog:
    return parse_catalog(
        read_fixture("catalog.json"),
        fetched_at=FETCHED_AT,
        source_url="https://balneabilidade.ima.sc.gov.br/relatorio/mapa",
    )


def make_bulletin(name: str = "bulletin_53_2026.txt") -> Bulletin:
    return parse_bulletin_text(
        read_fixture(name).decode("utf-8"),
        source_url="https://balneabilidade.ima.sc.gov.br/relatorio/downloadPDF/2026-11-13",
        fetched_at=FETCHED_AT,
        bulletin_date_hint=date(2026, 11, 13) if "53" in name else date(2026, 9, 24),
        known_municipalities=MUNICIPALITIES,
    )


def make_csv_export(
    municipality: str = "Porto Belo",
    beach: str = "Praia de Perequê",
    year: int = 2026,
) -> CsvExport:
    return parse_csv(
        read_fixture("pereque_2026.csv"),
        municipality=municipality,
        beach=beach,
        year=year,
        fetched_at=FETCHED_AT,
        source_url=CSV_URL,
    )


def empty_csv_export(municipality: str, beach: str, year: int) -> CsvExport:
    return CsvExport(
        municipality=municipality,
        beach=beach,
        year=year,
        samples=(),
        no_data_points=(),
        header=(
            "Municipio",
            "Balneario",
            "Ponto Coleta",
            "Localização",
            "Data",
            "Hora",
            "Vento",
            "Maré",
            "Chuva",
            "Água (ºC}",
            "Ar (ºC}",
            "E. coli NMP*/100ml",
            "Condição",
        ),
        fetched_at=FETCHED_AT,
        source_url=CSV_URL,
    )


def make_analyses(point_id: str = "00000000-0000-4000-8000-000000000003") -> AnalysesResult:
    return parse_analyses(
        read_fixture("analyses_pereque.json"),
        point_id=point_id,
        fetched_at=FETCHED_AT,
        source_url=ANALYSES_URL,
    )


class FakeCatalogRepository:
    def __init__(self, catalog: Catalog) -> None:
        self.catalog = catalog

    async def load(self, *, force: bool = False) -> Catalog:
        return self.catalog


class FakeBulletinRepository:
    def __init__(self, bulletin: Bulletin | None = None, error: Exception | None = None) -> None:
        self.bulletin = bulletin
        self.error = error

    async def fetch(self, bulletin_date: date | None = None, *, known_municipalities=()) -> Bulletin:
        if self.error is not None:
            raise self.error
        if self.bulletin is None:
            raise RuntimeError("fake bulletin not configured")
        return self.bulletin

    async def fetch_bundle(
        self, bulletin_date: date | None = None, *, known_municipalities=()
    ) -> BulletinBundle:
        bulletin = await self.fetch(bulletin_date, known_municipalities=known_municipalities)
        return BulletinBundle(bulletin=bulletin, pdf_bytes=read_fixture("synthetic_bulletin.pdf"))

    async def pdf_bytes(self, bulletin_date: date | None = None) -> bytes:
        return read_fixture("synthetic_bulletin.pdf")

    async def page_count(self, bulletin_date: date | None = None) -> int:
        from balneabilidade_sc_mcp.pdf_vision import pdf_page_count

        return pdf_page_count(read_fixture("synthetic_bulletin.pdf"))

    async def render_page(self, bulletin_date: date | None, page_number: int, *, dpi: int = 120):
        from balneabilidade_sc_mcp.pdf_vision import render_pdf_page

        return render_pdf_page(read_fixture("synthetic_bulletin.pdf"), page_number, dpi=dpi)

    async def latest_date(self) -> date:
        if self.error is not None:
            raise self.error
        if self.bulletin is None:
            raise RuntimeError("fake bulletin not configured")
        return self.bulletin.bulletin_date


class FakeHistoryRepository:
    def __init__(self, exports: dict[tuple[str, str, int], CsvExport] | None = None,
                 error: Exception | None = None) -> None:
        self.exports = exports or {}
        self.error = error

    async def fetch(self, municipality: str, beach: str, year: int) -> CsvExport:
        if self.error is not None:
            raise self.error
        return self.exports.get(
            (municipality, beach, year), empty_csv_export(municipality, beach, year)
        )


class FakeAnalysesRepository:
    def __init__(self, result: AnalysesResult | None = None, error: Exception | None = None) -> None:
        self.result = result
        self.error = error

    async def fetch(self, point_id: str) -> AnalysesResult:
        if self.error is not None:
            raise self.error
        if self.result is None:
            raise RuntimeError("fake analyses not configured")
        return self.result


def make_provider(
    *,
    catalog: Catalog | None = None,
    bulletin: Bulletin | None = None,
    history_exports: dict[tuple[str, str, int], CsvExport] | None = None,
    analyses: AnalysesResult | None = None,
    bulletin_error: Exception | None = None,
    history_error: Exception | None = None,
) -> ImaProvider:
    http = ImaHttpClient(transport=httpx.MockTransport(lambda request: httpx.Response(500)))
    return ImaProvider(
        http=http,
        cache=MemoryCache(),
        catalog_repository=FakeCatalogRepository(catalog or make_catalog()),
        bulletin_repository=FakeBulletinRepository(
            bulletin if bulletin is not None else make_bulletin(),
            error=bulletin_error,
        ),
        history_repository=FakeHistoryRepository(history_exports or {}, error=history_error),
        analyses_repository=FakeAnalysesRepository(analyses, error=None),
        today=lambda: TODAY,
    )


@pytest.fixture
def catalog() -> Catalog:
    return make_catalog()


@pytest.fixture
def bulletin() -> Bulletin:
    return make_bulletin()


@pytest.fixture
def pereque_export() -> CsvExport:
    return make_csv_export()


@pytest.fixture
def provider(pereque_export: CsvExport) -> ImaProvider:
    return make_provider(
        history_exports={("Porto Belo", "Praia de Perequê", 2026): pereque_export},
        analyses=make_analyses(),
    )
