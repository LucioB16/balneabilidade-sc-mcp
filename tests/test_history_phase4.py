from dataclasses import replace
from datetime import date, time

from balneabilidade_sc_mcp.errors import ImaProviderUnavailable
from balneabilidade_sc_mcp.models import (
    BeachStatus,
    Classification,
    CsvExport,
    CsvSample,
    Ecoli,
)
from balneabilidade_sc_mcp.normalization import parse_ecoli

from .conftest import FETCHED_AT, make_csv_export, make_provider


def sample(
    point_name: str,
    day: date,
    *,
    at: time = time(10, 0),
    classification: Classification = Classification.PROPER,
    label: str = "PRÓPRIA",
    ecoli: str = "10",
    location: str = "Local de prueba",
) -> CsvSample:
    value, qualifier, raw = parse_ecoli(ecoli)
    return CsvSample(
        municipality="Porto Belo",
        beach="Praia de Perequê",
        point_name=point_name,
        sample_date=day,
        sample_time=at,
        classification=classification,
        raw_classification=label,
        ecoli=Ecoli.from_parts(value, qualifier, raw),
        rain="Ausente",
        wind="Sul",
        tide="Enchente",
        water_temp_c=21.0,
        air_temp_c=20.0,
        location=location,
    )


def export(year: int, samples: tuple[CsvSample, ...]) -> CsvExport:
    return CsvExport(
        municipality="Porto Belo",
        beach="Praia de Perequê",
        year=year,
        samples=samples,
        no_data_points=(),
        header=("Municipio",) * 13,
        fetched_at=FETCHED_AT,
        source_url="https://example.test/csv",
    )


async def test_year_boundary_is_inclusive_and_ordered() -> None:
    exports = {
        ("Porto Belo", "Praia de Perequê", 2025): export(
            2025, (sample("Ponto 03", date(2025, 12, 31), at=time(23, 59)),)
        ),
        ("Porto Belo", "Praia de Perequê", 2026): export(
            2026, (sample("Ponto 03", date(2026, 1, 1), at=time(0, 5)),)
        ),
    }
    provider = make_provider(history_exports=exports)
    result = await provider.get_bathing_history(
        "Praia de Perequê",
        municipality="Porto Belo",
        from_date=date(2025, 12, 31),
        to_date=date(2026, 1, 1),
        limit=10,
    )
    assert [record.sample_date for record in result.records] == [
        date(2026, 1, 1),
        date(2025, 12, 31),
    ]
    assert result.records[0].sample_time == time(0, 5)
    assert result.records[1].sample_time == time(23, 59)
    assert result.coverage.years_with_data == (2025, 2026)
    first = result.records[0]
    assert first.municipality == "Porto Belo"
    assert first.beach == "Praia de Perequê"
    assert first.raw_point_name == "Ponto 03"
    assert first.location == "Local de prueba"
    assert first.csv_year == 2026
    assert first.ecoli is not None
    assert first.ecoli.unit == "NMP/100mL"


async def test_duplicate_measurement_is_deduped_and_counted() -> None:
    duplicate = sample("Ponto 03", date(2026, 11, 9))
    provider = make_provider(
        history_exports={("Porto Belo", "Praia de Perequê", 2026): export(2026, (duplicate, duplicate))}
    )
    result = await provider.get_bathing_history(
        "Praia de Perequê",
        municipality="Porto Belo",
        from_date=date(2026, 1, 1),
        to_date=date(2026, 11, 14),
    )
    assert len(result.records) == 1
    assert result.duplicate_samples == 1
    assert any("duplicate CSV" in warning for warning in result.warnings)


async def test_missing_years_are_explicit() -> None:
    exports = {
        ("Porto Belo", "Praia de Perequê", 2024): export(2024, ()),
        ("Porto Belo", "Praia de Perequê", 2025): export(
            2025, (sample("Ponto 03", date(2025, 12, 31)),)
        ),
        ("Porto Belo", "Praia de Perequê", 2026): export(2026, ()),
    }
    provider = make_provider(history_exports=exports)
    result = await provider.get_bathing_history(
        "Praia de Perequê",
        municipality="Porto Belo",
        from_date=date(2024, 1, 1),
        to_date=date(2026, 11, 14),
    )
    assert result.coverage.years_requested == (2024, 2025, 2026)
    assert result.coverage.years_with_data == (2025,)
    assert result.coverage.years_without_data == (2024, 2026)
    assert result.coverage.years_unavailable == ()


async def test_partial_year_outage_is_transparent() -> None:
    exports = {
        ("Porto Belo", "Praia de Perequê", 2026): export(
            2026, (sample("Ponto 03", date(2026, 11, 9)),)
        )
    }
    provider = make_provider(
        history_exports=exports,
        history_error_years={2025: ImaProviderUnavailable("2025 down")},
    )
    result = await provider.get_bathing_history(
        "Praia de Perequê",
        municipality="Porto Belo",
        from_date=date(2025, 1, 1),
        to_date=date(2026, 11, 14),
    )
    assert len(result.records) == 1
    assert result.coverage.years_unavailable == (2025,)
    assert any("2025" in warning for warning in result.warnings)


async def test_naming_drift_is_exposed_not_guessed() -> None:
    drifted = sample("Ponto 03 (antigo)", date(2026, 11, 9))
    provider = make_provider(
        history_exports={("Porto Belo", "Praia de Perequê", 2026): export(2026, (drifted,))}
    )
    result = await provider.get_bathing_history(
        "Praia de Perequê",
        municipality="Porto Belo",
        from_date=date(2026, 1, 1),
        to_date=date(2026, 11, 14),
    )
    assert result.records == ()
    assert result.unmatched_samples == 1
    assert result.unmatched_names == ("Ponto 03 (antigo)",)
    assert result.coverage.years_without_data == (2026,)


async def test_qualifiers_and_raw_units_are_preserved() -> None:
    samples = (
        sample("Ponto 03", date(2026, 11, 9), ecoli="<20"),
        sample("Ponto 04", date(2026, 11, 9), ecoli="> 24196"),
    )
    provider = make_provider(
        history_exports={("Porto Belo", "Praia de Perequê", 2026): export(2026, samples)}
    )
    result = await provider.get_bathing_history(
        "Praia de Perequê",
        municipality="Porto Belo",
        from_date=date(2026, 1, 1),
        to_date=date(2026, 11, 14),
    )
    by_point = {record.point_name: record for record in result.records}
    assert by_point["Ponto 03"].ecoli is not None
    assert by_point["Ponto 03"].ecoli.value == 20
    assert by_point["Ponto 03"].ecoli.raw == "<20"
    assert by_point["Ponto 03"].ecoli.unit == "NMP/100mL"
    assert by_point["Ponto 04"].ecoli is not None
    assert by_point["Ponto 04"].ecoli.value == 24196
    assert by_point["Ponto 04"].ecoli.qualifier.value == "above"


async def test_status_conflicting_csv_verdict_keeps_bulletin_and_warns() -> None:
    base = make_csv_export()
    conflicted = tuple(
        replace(item, classification=Classification.IMPROPER, raw_classification="IMPRÓPRIA")
        if item.point_name == "Ponto 03" and item.sample_date == date(2026, 11, 9)
        else item
        for item in base.samples
    )
    provider = make_provider(
        history_exports={
            ("Porto Belo", "Praia de Perequê", 2026): replace(base, samples=conflicted)
        },
        analyses=None,
    )
    result = await provider.get_bathing_status("Praia de Perequê", municipality="Porto Belo")
    assert result.summary.status is BeachStatus.PROPER
    point_03 = next(point for point in result.points if point.point.point_name == "Ponto 03")
    assert point_03.classification is Classification.PROPER
    assert any("CSV classification differs" in warning for warning in point_03.warnings)
