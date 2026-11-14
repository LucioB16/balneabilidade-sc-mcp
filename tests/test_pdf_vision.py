import pytest

from balneabilidade_sc_mcp.errors import ImaInvalidArgument
from balneabilidade_sc_mcp.pdf_vision import pdf_page_count, render_pdf_page

from .conftest import read_fixture


def test_render_synthetic_page_as_png() -> None:
    pdf = read_fixture("synthetic_bulletin.pdf")
    assert pdf_page_count(pdf) == 1
    page = render_pdf_page(pdf, 1, dpi=100)
    assert page.page_number == 1
    assert page.mime_type == "image/png"
    assert page.data.startswith(b"\x89PNG")
    assert page.width > 0 and page.height > 0


def test_render_rejects_out_of_range_page() -> None:
    pdf = read_fixture("synthetic_bulletin.pdf")
    with pytest.raises(ImaInvalidArgument):
        render_pdf_page(pdf, 0)
    with pytest.raises(ImaInvalidArgument):
        render_pdf_page(pdf, 2)
