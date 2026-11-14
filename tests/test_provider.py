from datetime import date

import pytest

from balneabilidade_sc_mcp.errors import (
    ImaAmbiguousQuery,
    ImaInvalidArgument,
    ImaProviderUnavailable,
)
from balneabilidade_sc_mcp.models import BeachStatus, Classification, Freshness, Source

from .conftest import make_analyses, make_csv_export, make_provider


async def test_perequee_returns_all_points_with_dated_values() -> None:
    export = make_csv_export()
    provider = make_provider(
        history_exports={("Porto Belo", "Praia de Perequê", 2026): export},
        analyses=make_analyses(),
    )
    result = await provider.get_bathing_status("Praia de Perequê", municipality="Porto Belo")
    assert result.bulletin is not None
    assert result.bulletin.bulletin_date == date(2026, 11, 13)
    assert result.bulletin_unverified is False
    assert result.summary.status is BeachStatus.PROPER
    assert result.summary.points_total == 3
    assert result.summary.points_current == 3
    by_point = {status.point.point_name: status for status in result.points}
    assert by_point["Ponto 03"].sample_date == date(2026, 11, 9)
    assert by_point["Ponto 03"].classification is Classification.PROPER
    assert by_point["Ponto 03"].freshness is Freshness.CURRENT
    assert by_point["Ponto 03"].ecoli is not None
    assert by_point["Ponto 03"].ecoli.value == 373
    assert by_point["Ponto 05"].ecoli is not None
    assert by_point["Ponto 05"].ecoli.value == 20
    assert by_point["Ponto 05"].ecoli.qualifier.value == "below"
    assert by_point["Ponto 04"].ecoli is None
    assert all(status.value_source is Source.CSV for status in result.points if status.ecoli)


async def test_zimbros_is_mixed_not_proper() -> None:
    provider = make_provider()
    result = await provider.get_bathing_status("Praia de Zimbros", municipality="Bombinhas")
    assert result.summary.status is BeachStatus.MIXED
    assert result.summary.has_improper is True
    by_point = {status.point.point_name: status for status in result.points}
    assert by_point["Ponto 09"].classification is Classification.IMPROPER
    assert by_point["Ponto 10"].classification is Classification.PROPER


async def test_excluded_and_carried_points_are_not_current() -> None:
    provider = make_provider()
    excluded = await provider.get_bathing_status(
        "Praia de Ponta das Canas", municipality="Florianópolis"
    )
    point_83 = excluded.points[0]
    assert point_83.freshness is Freshness.EXCLUDED
    assert point_83.classification is Classification.UNKNOWN
    assert point_83.raw_classification == "IMPRÓPRIA"
    assert excluded.summary.status is BeachStatus.UNKNOWN

    carried = await provider.get_bathing_status("Beira-Mar Norte", municipality="Florianópolis")
    point_94 = carried.points[0]
    assert point_94.freshness is Freshness.CARRIED_FORWARD
    assert point_94.classification is Classification.IMPROPER
    assert point_94.sample_age_at_bulletin_days == 25
    assert carried.summary.status is BeachStatus.IMPROPER

    old = await provider.get_bathing_status("Lagoa da Conceição", municipality="Florianópolis")
    assert old.points[0].freshness is Freshness.CARRIED_FORWARD
    assert old.points[0].sample_age_at_bulletin_days == 171


async def test_ambiguous_name_and_missing_bulletin_row() -> None:
    provider = make_provider()
    with pytest.raises(ImaAmbiguousQuery):
        await provider.get_bathing_status("Praia Brava")
    missing = await provider.get_bathing_status("Praia Brava", municipality="Florianópolis")
    assert missing.summary.status is BeachStatus.UNKNOWN
    assert missing.points[0].freshness is Freshness.UNKNOWN
    assert any("missing" in warning for warning in missing.warnings)


async def test_point_filter_returns_only_requested_point() -> None:
    provider = make_provider(
        history_exports={("Porto Belo", "Praia de Perequê", 2026): make_csv_export()}
    )
    result = await provider.get_bathing_status(
        "Praia de Perequê",
        municipality="Porto Belo",
        point_id="00000000-0000-4000-8000-000000000003",
    )
    assert len(result.points) == 1
    assert result.points[0].point.point_name == "Ponto 03"
    assert result.summary.points_total == 1


async def test_without_bulletin_falls_back_to_unverified_csv() -> None:
    provider = make_provider(
        bulletin_error=ImaProviderUnavailable("bulletin down"),
        history_exports={("Porto Belo", "Praia de Perequê", 2026): make_csv_export()},
        analyses=make_analyses(),
    )
    result = await provider.get_bathing_status("Praia de Perequê", municipality="Porto Belo")
    assert result.bulletin is None
    assert result.bulletin_unverified is True
    assert result.latest_source is Source.CSV
    assert result.summary.status is BeachStatus.PARTIAL
    assert all(status.freshness is Freshness.UNVERIFIED for status in result.points)
    assert result.points[0].classification is Classification.PROPER


async def test_history_pagination_and_coverage() -> None:
    provider = make_provider(
        history_exports={("Porto Belo", "Praia de Perequê", 2026): make_csv_export()}
    )
    first = await provider.get_bathing_history(
        "Praia de Perequê",
        municipality="Porto Belo",
        from_date=date(2026, 1, 1),
        to_date=date(2026, 11, 14),
        limit=2,
    )
    assert len(first.records) == 2
    assert first.next_cursor == "2"
    assert first.coverage.years_with_data == (2026,)
    second = await provider.get_bathing_history(
        "Praia de Perequê",
        municipality="Porto Belo",
        from_date=date(2026, 1, 1),
        to_date=date(2026, 11, 14),
        limit=2,
        cursor=first.next_cursor,
    )
    assert len(second.records) == 2
    assert second.next_cursor is None


async def test_history_point_filter_and_invalid_range() -> None:
    provider = make_provider(
        history_exports={("Porto Belo", "Praia de Perequê", 2026): make_csv_export()}
    )
    filtered = await provider.get_bathing_history(
        "Praia de Perequê",
        municipality="Porto Belo",
        point_id="00000000-0000-4000-8000-000000000003",
        from_date=date(2026, 1, 1),
        to_date=date(2026, 11, 14),
        limit=10,
    )
    assert len(filtered.records) == 3
    assert {record.point_name for record in filtered.records} == {"Ponto 03"}
    with pytest.raises(ImaInvalidArgument):
        await provider.get_bathing_history(
            "Praia de Perequê", from_date=date(2027, 1, 1), to_date=date(2027, 2, 1)
        )
    with pytest.raises(ImaInvalidArgument):
        await provider.get_bathing_history("Praia de Perequê", cursor="not-a-number")


async def test_history_provider_outage_is_explicit() -> None:
    provider = make_provider(history_error=ImaProviderUnavailable("CSV down"))
    with pytest.raises(ImaProviderUnavailable):
        await provider.get_bathing_history(
            "Praia de Perequê",
            municipality="Porto Belo",
            from_date=date(2026, 1, 1),
            to_date=date(2026, 11, 14),
        )


async def test_search_and_sampling_points() -> None:
    provider = make_provider()
    matches = await provider.search_beaches("praia brava")
    assert len(matches) == 2
    points = await provider.get_sampling_points("Praia de Perequê", municipality="Porto Belo")
    assert points.point_count == 3
