import asyncio
import base64
import contextlib
import json
from collections.abc import AsyncIterator
from datetime import date

from mcp import ClientSession
from mcp.shared.memory import create_client_server_memory_streams
from mcp.types import ImageContent, TextContent
from starlette.testclient import TestClient

from balneabilidade_sc_mcp.bulletin import parse_bulletin_text
from balneabilidade_sc_mcp.errors import ImaProviderUnavailable
from balneabilidade_sc_mcp.server import create_server, create_streamable_http_app

from .conftest import (
    FETCHED_AT,
    MUNICIPALITIES,
    make_analyses,
    make_csv_export,
    make_provider,
)

MINI = """RELATÓRIO Nº 99
DATA: 13/11/2026
Porto Belo
Praia de Perequê (Ponto 03)
09/11/2026 PRÓPRIA
"""


@contextlib.asynccontextmanager
async def mcp_session(provider) -> AsyncIterator[ClientSession]:
    server = create_server(provider)
    async with create_client_server_memory_streams() as (client_streams, server_streams):
        task = asyncio.create_task(
            server._lowlevel_server.run(
                server_streams[0],
                server_streams[1],
                server._lowlevel_server.create_initialization_options(),
            )
        )
        try:
            async with ClientSession(*client_streams) as session:
                await session.initialize()
                yield session
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task


async def test_server_instructions_include_vision_policy() -> None:
    server = create_server(make_provider())
    assert "vision_fallback" in server.instructions
    assert "get_bulletin_page" in server.instructions
    assert "real-time" in server.instructions


async def test_server_lists_all_tools() -> None:
    async with mcp_session(make_provider()) as session:
        result = await session.list_tools()
        assert {tool.name for tool in result.tools} == {
            "search_beaches",
            "get_sampling_points",
            "get_bathing_status",
            "get_bathing_history",
            "get_bulletin_page",
        }


async def test_all_tools_advertise_read_only_public_data_annotations() -> None:
    async with mcp_session(make_provider()) as session:
        result = await session.list_tools()
    assert len(result.tools) == 5
    for tool in result.tools:
        assert tool.annotations is not None
        assert tool.annotations.read_only_hint is True
        assert tool.annotations.open_world_hint is True
        assert tool.annotations.destructive_hint is False


def test_streamable_http_app_initializes_and_discovers_tools() -> None:
    app = create_streamable_http_app(make_provider())
    headers = {"accept": "application/json, text/event-stream", "content-type": "application/json"}
    with TestClient(app, base_url="http://127.0.0.1") as client:
        initialized = client.post(
            "/mcp",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "repository-test", "version": "1.0.0"},
                },
            },
        )
        assert initialized.status_code == 200
        initialize_result = initialized.json()["result"]
        assert initialize_result["serverInfo"]["name"] == "balneabilidade-sc-mcp"
        assert initialize_result["protocolVersion"] == "2025-03-26"

        tools = client.post(
            "/mcp",
            headers=headers,
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        )
        assert tools.status_code == 200
        advertised = tools.json()["result"]["tools"]
        assert {tool["name"] for tool in advertised} == {
            "search_beaches",
            "get_sampling_points",
            "get_bathing_status",
            "get_bathing_history",
            "get_bulletin_page",
        }
        assert all(tool["annotations"]["readOnlyHint"] is True for tool in advertised)


async def test_search_is_ambiguous_across_municipalities() -> None:
    async with mcp_session(make_provider()) as session:
        result = await session.call_tool("search_beaches", {"query": "praia brava"})
        assert result.is_error is False
        payload = json.loads(result.content[0].text)
        assert payload["ambiguous"] is True
        assert len(payload["matches"]) == 2
        assert {match["municipality"] for match in payload["matches"]} == {
            "Florianópolis",
            "Itajaí",
        }


async def test_sampling_points_and_status_payloads() -> None:
    provider = make_provider(
        history_exports={("Porto Belo", "Praia de Perequê", 2026): make_csv_export()},
        analyses=make_analyses(),
    )
    async with mcp_session(provider) as session:
        points = await session.call_tool(
            "get_sampling_points",
            {"beach": "Praia de Perequê", "municipality": "Porto Belo"},
        )
        assert points.is_error is False
        points_payload = json.loads(points.content[0].text)
        assert points_payload["beach"]["points"][0]["point_id"].startswith("00000000")

        status = await session.call_tool(
            "get_bathing_status",
            {"beach": "Praia de Perequê", "municipality": "Porto Belo"},
        )
        assert status.is_error is False
        status_payload = json.loads(status.content[0].text)
        assert status_payload["summary"]["status"] == "proper"
        assert len(status_payload["points"]) == 3
        assert status_payload["points"][0]["point_name"] == "Ponto 03"
        assert status_payload["points"][0]["sample_date"] == "2026-11-09"


async def test_history_payload_and_error_response() -> None:
    provider = make_provider(history_exports={("Porto Belo", "Praia de Perequê", 2026): make_csv_export()})
    async with mcp_session(provider) as session:
        history = await session.call_tool(
            "get_bathing_history",
            {
                "beach": "Praia de Perequê",
                "municipality": "Porto Belo",
                "from_date": "2026-01-01",
                "to_date": "2026-11-14",
                "limit": 2,
            },
        )
        assert history.is_error is False
        payload = json.loads(history.content[0].text)
        assert len(payload["records"]) == 2
        assert payload["next_cursor"] == "2"
        assert payload["records"][0]["municipality"] == "Porto Belo"
        assert payload["records"][0]["ecoli"]["unit"] == "NMP/100mL"

        error = await session.call_tool(
            "get_bathing_status", {"beach": "No Existe", "municipality": "Porto Belo"}
        )
        assert error.is_error is True
        assert "no beach matched" in error.content[0].text


async def test_history_provider_outage_is_a_tool_error() -> None:
    provider = make_provider(history_error=ImaProviderUnavailable("CSV down"))
    async with mcp_session(provider) as session:
        result = await session.call_tool(
            "get_bathing_history", {"beach": "Praia de Perequê", "municipality": "Porto Belo"}
        )
        assert result.is_error is True
        assert "CSV down" in result.content[0].text


async def test_no_data_status_is_explicit_not_proper() -> None:
    async with mcp_session(make_provider()) as session:
        result = await session.call_tool(
            "get_bathing_status",
            {"beach": "Praia Brava", "municipality": "Florianópolis"},
        )
        assert result.is_error is False
        payload = json.loads(result.content[0].text)
        assert payload["summary"]["status"] == "unknown"
        assert payload["points"][0]["freshness"] == "unknown"


async def test_portuguese_accented_search() -> None:
    async with mcp_session(make_provider()) as session:
        result = await session.call_tool("search_beaches", {"query": "Praia de Perequê"})
        assert result.is_error is False
        payload = json.loads(result.content[0].text)
        assert payload["matches"][0]["beach_key"] == "porto-belo|praia-de-pereque"


async def test_bulletin_page_returns_png_image_content() -> None:
    async with mcp_session(make_provider()) as session:
        result = await session.call_tool("get_bulletin_page", {"page": 1, "dpi": 100})
        assert result.is_error is False
        image_blocks = [block for block in result.content if isinstance(block, ImageContent)]
        text_blocks = [block for block in result.content if isinstance(block, TextContent)]
        assert len(image_blocks) == 1
        assert len(text_blocks) == 1
        raw = base64.b64decode(image_blocks[0].data)
        assert raw.startswith(b"\x89PNG")
        assert result.structured_content["page"] == 1


async def test_incomplete_bulletin_exposes_vision_fallback_then_page() -> None:
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
        analyses=make_analyses(),
    )
    async with mcp_session(provider) as session:
        status = await session.call_tool(
            "get_bathing_status",
            {"beach": "Praia de Perequê", "municipality": "Porto Belo"},
        )
        payload = json.loads(status.content[0].text)
        assert payload["vision_fallback"]["page_count"] == 1
        page = await session.call_tool("get_bulletin_page", {"page": 1})
        assert any(isinstance(block, ImageContent) for block in page.content)
