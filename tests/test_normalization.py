from datetime import date

import pytest

from balneabilidade_sc_mcp.models import Classification
from balneabilidade_sc_mcp.normalization import (
    classification_from_label,
    fold,
    is_in_season,
    parse_br_date,
    parse_collection_dates,
    parse_ecoli,
    parse_time,
    point_number,
    slugify,
)


def test_fold_handles_unicode_case_and_whitespace() -> None:
    assert fold("Praia de Perequê") == "praia de pereque"
    assert fold("  PRAIA   DE PEREQUE ") == "praia de pereque"
    assert fold("Conceição") == "conceicao"
    assert slugify("Praia de Perequê") == "praia-de-pereque"


def test_parse_br_date_and_time() -> None:
    assert parse_br_date("09/11/2026") == date(2026, 11, 9)
    assert parse_time("09:56").hour == 9
    assert parse_time("") is None
    with pytest.raises(ValueError):
        parse_br_date("2026-11-09")


def test_parse_ecoli_preserves_censoring() -> None:
    assert parse_ecoli("<20") == (20, "below", "<20")
    assert parse_ecoli("<10") == (10, "below", "<10")
    assert parse_ecoli("> 24196") == (24196, "above", "> 24196")
    assert parse_ecoli("24196") == (24196, "exact", "24196")
    assert parse_ecoli("n/a") == (None, "unknown", "n/a")


def test_classification_labels_and_season() -> None:
    assert classification_from_label("PRÓPRIA") is Classification.PROPER
    assert classification_from_label("IMPRÓPRIO") is Classification.IMPROPER
    assert classification_from_label("Indeterminado") is Classification.INDETERMINATE
    assert classification_from_label("something else") is Classification.UNKNOWN
    assert is_in_season(date(2026, 11, 13)) is True
    assert is_in_season(date(2026, 9, 24)) is False


def test_parse_collection_dates_weekly_and_monthly() -> None:
    weekly = "Amostragens realizadas nos dias 09, 10 e 11 de novembro de 2026."
    assert parse_collection_dates(weekly) == (
        date(2026, 11, 9),
        date(2026, 11, 10),
        date(2026, 11, 11),
    )
    monthly = "10 pontos coletados no dia 21 de setembro de 2026 no município."
    assert parse_collection_dates(monthly) == (date(2026, 9, 21),)
    assert parse_collection_dates("no dates here") == ()


def test_point_number() -> None:
    assert point_number("Ponto 83") == 83
    assert point_number("not a point") is None
