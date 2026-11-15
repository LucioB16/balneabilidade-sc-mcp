"""Runnable stateless Streamable HTTP entry point for hosted MCP clients."""

from __future__ import annotations

import os

import uvicorn

from .server import create_streamable_http_app

app = create_streamable_http_app()


def main() -> None:
    """Serve the MCP app on the host and port supplied by the runtime."""

    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host=host, port=port, log_level="info", access_log=False)


if __name__ == "__main__":
    main()
