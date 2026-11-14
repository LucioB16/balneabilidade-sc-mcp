from datetime import date, datetime, time

from balneabilidade_sc_mcp.models import (
    Classification,
    CsvExport,
    CsvSample,
    Ecoli,
    Qualifier,
)
from balneabilidade_sc_mcp.provider import SAO_PAULO, ImaProvider

from .conftest import FETCHED_AT, make_provider


def test_sao_paulo_is_utc_minus_three() -> None:
    offset = datetime(2026, 11, 14, tzinfo=SAO_PAULO).utcoffset()
    assert offset is not None
    assert offset.total_seconds() == -3 * 3600


async def test_renamed_or_unknown_point_is_reported_as_unmatched() -> None:
    renamed = CsvSample(
        municipality="Porto Belo",
        beach="Praia de Perequê",
        point_name="Ponto 03 - renomeado",
        sample_date=date(2026, 11, 9),
        sample_time=time(10, 0),
        classification=Classification.PROPER,
        raw_classification="PRÓPRIA",
        ecoli=Ecoli(value=10, qualifier=Qualifier.EXACT, raw="10"),
        rain="Ausente",
        wind="Sul",
        tide="Enchente",
        water_temp_c=21.0,
        air_temp_c=20.0,
    )
    export = CsvExport(
        municipality="Porto Belo",
        beach="Praia de Perequê",
        year=2026,
        samples=(renamed,),
        no_data_points=(),
        header=("Municipio",) * 13,
        fetched_at=FETCHED_AT,
        source_url="https://example.test/csv",
    )
    provider = make_provider(history_exports={("Porto Belo", "Praia de Perequê", 2026): export})
    result = await provider.get_bathing_history(
        "Praia de Perequê",
        municipality="Porto Belo",
        from_date=date(2026, 1, 1),
        to_date=date(2026, 11, 14),
    )
    assert result.records == ()
    assert result.unmatched_samples == 1
    assert result.coverage.years_without_data == (2026,)


async def test_provider_is_async_context_manager() -> None:
    provider = make_provider()
    async with provider as entered:
        assert isinstance(entered, ImaProvider)
