"""MCP server exposing the IMA/SC provider over local stdio.

The server has no stdout logging: stdio carries the MCP protocol, so every
diagnostic goes to stderr. The deterministic provider remains authoritative;
vision fallback is opt-in through get_bulletin_page for clients that can read
images.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from typing import Any, cast

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import CallToolResult, ImageContent, TextContent, ToolAnnotations
from starlette.applications import Starlette

from . import __version__
from .errors import ImaError
from .http import ImaHttpClient
from .provider import ImaProvider
from .serialization import status_to_dict, to_jsonable

LOGGER = logging.getLogger("balneabilidade_sc_mcp")


def _fail(exc: Exception) -> ToolError:
    LOGGER.info("tool error: %s", exc)
    return ToolError(str(exc))


READ_ONLY_PUBLIC_DATA = ToolAnnotations(
    read_only_hint=True,
    open_world_hint=True,
    destructive_hint=False,
)


def create_server(provider: ImaProvider | None = None) -> MCPServer:
    """Build an MCPServer around a provider (injectable for tests)."""

    provider = provider or ImaProvider()

    @asynccontextmanager
    async def provider_lifespan(_: MCPServer) -> AsyncIterator[dict[str, ImaProvider]]:
        async with provider:
            yield {"provider": provider}

    server = MCPServer(
        name="balneabilidade-sc-mcp",
        title="Balneabilidade Santa Catarina (IMA/SC)",
        version=__version__,
        lifespan=provider_lifespan,
        instructions=(
            "Use IMA/SC's official published bathing-water data for Santa Catarina, Brazil. "
            "Always say that results are dated published samples, never real-time readings. "
            "Preserve each sampling point and report sample date, bulletin date, source and data age. "
            "Do not hide mixed, partial, unknown, stale or excluded results; never infer a proper result. "
            "Resolve duplicate beach names by municipality before checking status. "
            "If vision_fallback is present, only a vision-capable client may read the original page via "
            "get_bulletin_page; mark unreadable rows as unverified. Never use the map's undated CONDICAO "
            "as current status. Answer in the user's language (English, español rioplatense or português brasileiro). "
            "The service is independent and is not developed, operated or endorsed by IMA/SC."
        ),
    )

    @server.tool(
        name="search_beaches",
        description=(
            "Find beaches monitored by IMA/SC by name and municipality; returns candidates and never "
            "chooses silently between duplicate names. Busca praias monitoradas pelo IMA/SC por nome e "
            "município; devolve candidatos e não escolhe silenciosamente entre nomes repetidos. Busca "
            "playas monitoreadas por IMA/SC por nombre y municipio; devuelve candidatos y no elige "
            "silenciosamente entre nombres repetidos."
        ),
        annotations=READ_ONLY_PUBLIC_DATA,
    )
    async def search_beaches(query: str, municipality: str | None = None, limit: int = 10) -> dict[str, Any]:
        try:
            matches = await provider.search_beaches(query, municipality=municipality, limit=limit)
        except ImaError as exc:
            raise _fail(exc) from exc
        return {
            "provider": "IMA/SC",
            "query": query,
            "matches": [
                {
                    "beach_key": match.beach.key,
                    "beach_name": match.beach.name,
                    "municipality": match.beach.municipality,
                    "point_count": match.beach.point_count,
                    "match_type": match.match_type,
                }
                for match in matches
            ],
            "ambiguous": len(matches) > 1,
            "fetched_at": datetime.now(UTC).isoformat(),
            "warnings": [],
        }

    @server.tool(
        name="get_sampling_points",
        description=(
            "List all IMA/SC sampling points for an unambiguously resolved beach, including UUID, "
            "location and coordinates when published. Liste todos os pontos de coleta do IMA/SC para "
            "uma praia identificada sem ambiguidade, incluindo UUID, localização e coordenadas quando "
            "publicadas. Lista todos los puntos de muestreo de IMA/SC para una playa resuelta sin "
            "ambigüedad, con UUID, ubicación y coordenadas cuando estén publicadas."
        ),
        annotations=READ_ONLY_PUBLIC_DATA,
    )
    async def get_sampling_points(
        beach: str, municipality: str | None = None, include_hidden: bool = False
    ) -> dict[str, Any]:
        try:
            resolved = await provider.get_sampling_points(
                beach, municipality=municipality, include_hidden=include_hidden
            )
        except ImaError as exc:
            raise _fail(exc) from exc
        beach_payload = to_jsonable(resolved)
        if isinstance(beach_payload, dict):
            beach_payload["point_count"] = resolved.point_count
        return {
            "provider": "IMA/SC",
            "beach": beach_payload,
            "fetched_at": datetime.now(UTC).isoformat(),
            "warnings": [],
        }

    @server.tool(
        name="get_bathing_status",
        description=(
            "Return the latest dated IMA/SC result for every sampling point, with sample date, bulletin "
            "date, freshness, source and a conservative beach summary. This is not real-time. "
            "Retorna o resultado datado mais recente do IMA/SC para cada ponto, com datas da coleta e do "
            "boletim, atualidade, fonte e resumo conservador da praia; não é tempo real. Devuelve el "
            "último resultado fechado de IMA/SC por punto, con fechas de muestra y boletín, antigüedad, "
            "fuente y resumen conservador; no es tiempo real. If PDF parsing is incomplete, report "
            "vision_fallback and do not invent rows."
        ),
        annotations=READ_ONLY_PUBLIC_DATA,
    )
    async def get_bathing_status(
        beach: str,
        municipality: str | None = None,
        point_id: str | None = None,
    ) -> dict[str, Any]:
        try:
            result = await provider.get_bathing_status(beach, municipality=municipality, point_id=point_id)
        except ImaError as exc:
            raise _fail(exc) from exc
        return status_to_dict(result)

    @server.tool(
        name="get_bathing_history",
        description=(
            "Return dated IMA/SC history for a beach or sampling point within an inclusive date range, "
            "newest first and paginated. Distinguish years with no data from years unavailable. Retorne o "
            "histórico datado do IMA/SC por praia ou ponto, no período inclusivo, do mais recente ao mais "
            "antigo e com paginação; diferencie anos sem dados de anos indisponíveis. Devuelve el "
            "historial fechado de IMA/SC por playa o punto en un rango inclusivo, en orden descendente "
            "y paginado; distingue años sin datos de años no disponibles."
        ),
        annotations=READ_ONLY_PUBLIC_DATA,
    )
    async def get_bathing_history(
        beach: str,
        municipality: str | None = None,
        point_id: str | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
        limit: int = 50,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        try:
            result = await provider.get_bathing_history(
                beach,
                municipality=municipality,
                point_id=point_id,
                from_date=from_date,
                to_date=to_date,
                limit=limit,
                cursor=cursor,
            )
        except ImaError as exc:
            raise _fail(exc) from exc
        return cast(dict[str, Any], to_jsonable(result))

    @server.tool(
        name="get_bulletin_page",
        description=(
            "Render one page of an official IMA/SC bulletin PDF as PNG. Use it when a vision-capable "
            "client needs to inspect a page, especially after vision_fallback; do not invent unreadable "
            "rows. Renderize uma página do boletim oficial do IMA/SC como PNG para inspeção por um "
            "cliente com visão; não invente linhas ilegíveis. Renderiza una página del boletín oficial "
            "del IMA/SC como PNG para que un cliente con visión la inspeccione; no inventes filas ilegibles."
        ),
        annotations=READ_ONLY_PUBLIC_DATA,
    )
    async def get_bulletin_page(
        page: int = 1,
        bulletin_date: date | None = None,
        dpi: int = 120,
    ) -> CallToolResult:
        try:
            rendered = await provider.get_bulletin_page(bulletin_date, page, dpi)
        except ImaError as exc:
            raise _fail(exc) from exc
        caption = {
            "provider": "IMA/SC",
            "bulletin_date": bulletin_date.isoformat() if bulletin_date else "latest",
            "page": rendered.page_number,
            "page_count": rendered.page_count,
            "mime_type": rendered.mime_type,
            "width": rendered.width,
            "height": rendered.height,
            "note": "Página del boletín original para lectura por visión.",
        }
        return CallToolResult(
            content=[
                TextContent(type="text", text=json.dumps(caption, ensure_ascii=False)),
                ImageContent(
                    type="image",
                    data=base64.b64encode(rendered.data).decode("ascii"),
                    mime_type=rendered.mime_type,
                ),
            ],
            structured_content=caption,
        )

    return server


def create_streamable_http_app(
    provider: ImaProvider | None = None,
    *,
    streamable_http_path: str = "/mcp",
) -> Starlette:
    """Build a stateless Streamable HTTP ASGI app using the same tools as stdio."""

    provider = provider or ImaProvider(http=ImaHttpClient(min_request_interval_seconds=0.2))
    server = create_server(provider)
    allowed_hosts = [
        value.strip()
        for value in os.environ.get(
            "BALNEABILIDADE_ALLOWED_HOSTS",
            "127.0.0.1,127.0.0.1:*,localhost,localhost:*,[::1],[::1]:*",
        ).split(",")
        if value.strip()
    ]
    allowed_origins = [
        value.strip()
        for value in os.environ.get(
            "BALNEABILIDADE_ALLOWED_ORIGINS",
            "http://127.0.0.1:*,http://localhost:*,http://[::1]:*",
        ).split(",")
        if value.strip()
    ]
    return server.streamable_http_app(
        streamable_http_path=streamable_http_path,
        json_response=True,
        stateless_http=True,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=allowed_hosts,
            allowed_origins=allowed_origins,
        ),
    )


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    LOGGER.info("starting balneabilidade-sc-mcp over stdio")

    async def run() -> None:
        server = create_server(ImaProvider())
        await server.run_stdio_async()

    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        LOGGER.info("interrupted")


if __name__ == "__main__":
    main()
