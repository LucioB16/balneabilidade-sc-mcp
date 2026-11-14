import httpx
import pytest

from balneabilidade_sc_mcp.errors import ImaHTTPError, ImaNetworkError, ImaNotFound, ImaResponseTooLarge
from balneabilidade_sc_mcp.http import ImaHttpClient


async def test_retries_server_error_then_succeeds() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(503, content=b"busy")
        return httpx.Response(200, headers={"content-type": "text/html"}, content=b"[]")

    client = ImaHttpClient(
        transport=httpx.MockTransport(handler), retries=1, retry_delay_seconds=0
    )
    response = await client.get("/relatorio/mapa")
    assert response.status_code == 200
    assert response.content == b"[]"
    assert response.content_type == "text/html"
    assert len(calls) == 2


async def test_404_is_typed_not_found() -> None:
    client = ImaHttpClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(404)), retries=0
    )
    with pytest.raises(ImaNotFound):
        await client.get("/relatorio/downloadPDF/2026-11-12")


async def test_client_error_is_typed_http_error_without_retry() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(403)

    client = ImaHttpClient(transport=httpx.MockTransport(handler), retries=2, retry_delay_seconds=0)
    with pytest.raises(ImaHTTPError) as exc_info:
        await client.get("/x")
    assert exc_info.value.status_code == 403
    assert len(calls) == 1


async def test_response_size_limit() -> None:
    client = ImaHttpClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, content=b"12345")),
        max_bytes=3,
    )
    with pytest.raises(ImaResponseTooLarge):
        await client.get("/x")


async def test_transport_error_retries_and_raises_network_error() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        raise httpx.ConnectError("boom")

    client = ImaHttpClient(
        transport=httpx.MockTransport(handler), retries=1, retry_delay_seconds=0
    )
    with pytest.raises(ImaNetworkError):
        await client.get("/x")
    assert len(calls) == 2


async def test_post_form_preserves_portal_characters() -> None:
    captured: list[bytes] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request.content)
        return httpx.Response(200, headers={"content-type": "text/csv"}, content=b"ok")

    client = ImaHttpClient(transport=httpx.MockTransport(handler))
    response = await client.post_form(
        "/relatorio/exportarCSV", {"municipioID": "Porto Belo", "localID": "Praia de Perequê"}
    )
    assert response.content == b"ok"
    assert b"municipioID=Porto+Belo" in captured[0]
    assert b"localID=Praia+de+Perequ%C3%AA" in captured[0]
