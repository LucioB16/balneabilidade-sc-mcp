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
import sys
from datetime import UTC, date, datetime
from typing import Any, cast

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import CallToolResult, ImageContent, TextContent

from . import __version__
from .errors import ImaError
from .provider import ImaProvider
from .serialization import status_to_dict, to_jsonable

LOGGER = logging.getLogger("balneabilidade_sc_mcp")


def _fail(exc: Exception) -> ToolError:
    LOGGER.info("tool error: %s", exc)
    return ToolError(str(exc))


def create_server(provider: ImaProvider | None = None) -> MCPServer:
    """Build an MCPServer around a provider (injectable for tests)."""

    provider = provider or ImaProvider()
    server = MCPServer(
        name="balneabilidade-sc-mcp",
        title="Balneabilidade Santa Catarina (IMA/SC)",
        version=__version__,
        instructions=(
            "Consulta la balneabilidade oficial de Santa Catarina (IMA/SC) por "
            "playa y punto de muestreo. Los resultados son muestras fechadas, no "
            "tiempo real. Trabaja siempre por punto: una playa puede tener resultados "
            "mixtos. Si una respuesta incluye vision_fallback, el parser determinista del "
            "PDF quedó incompleto: solo si tu cliente tiene visión, llama a "
            "get_bulletin_page para leer las páginas PNG; no inventes filas y marca como "
            "no verificadas las páginas que no puedas leer. No uses la CONDICAO del mapa "
            "como estado actual. Preguntas en español o português son bienvenidas."
        ),
    )

    @server.tool(
        name="search_beaches",
        description=(
            "Busca playas monitoreadas por IMA/SC por nombre, con desambiguación por "
            "municipio. Devuelve candidatos; no elige una playa si hay nombres repetidos."
        ),
    )
    async def search_beaches(
        query: str, municipality: str | None = None, limit: int = 10
    ) -> dict[str, Any]:
        try:
            matches = await provider.search_beaches(
                query, municipality=municipality, limit=limit
            )
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
            "Lista los puntos de muestreo de una playa, con UUID, ubicación y "
            "coordenadas cuando IMA las publica. La playa debe resolverse sin ambigüedad."
        ),
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
            "Devuelve el último resultado oficial FECHADO por punto de muestreo, "
            "con fecha de muestra, fecha de boletín, frescura y resumen conservador "
            "de la playa. No es una medición en tiempo real. Si el parser del PDF "
            "queda incompleto, incluye vision_fallback para que un cliente con visión "
            "lea las páginas originales."
        ),
    )
    async def get_bathing_status(
        beach: str,
        municipality: str | None = None,
        point_id: str | None = None,
    ) -> dict[str, Any]:
        try:
            result = await provider.get_bathing_status(
                beach, municipality=municipality, point_id=point_id
            )
        except ImaError as exc:
            raise _fail(exc) from exc
        return status_to_dict(result)

    @server.tool(
        name="get_bathing_history",
        description=(
            "Devuelve historial oficial fechado por playa/punto, con rango inclusivo, "
            "orden descendente y paginación acotada. No inventa años sin datos."
        ),
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
            "Renderiza una página del boletín PDF como imagen PNG. Úsala solo si "
            "get_bathing_status devuelve vision_fallback y tu cliente tiene visión; "
            "no inventes filas que no puedas leer."
        ),
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


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    LOGGER.info("starting balneabilidade-sc-mcp over stdio")

    async def run() -> None:
        async with ImaProvider() as provider:
            server = create_server(provider)
            await server.run_stdio_async()

    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        LOGGER.info("interrupted")


if __name__ == "__main__":
    main()

