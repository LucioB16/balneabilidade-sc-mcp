# Release and installation notes

## Version

Current release: **0.1.0** (2026-11-14).

The version is declared in `pyproject.toml` and `src/balneabilidade_sc_mcp/__init__.py`.
The MCP server reports it in its initialization metadata.

## Install from a clean checkout

Requirements: Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/LucioB16/balneabilidade-sc-mcp.git
cd balneabilidade-sc-mcp
uv sync --extra mcp
uv run balneabilidade-sc-mcp
```

The last command starts the **stdio** MCP server and waits for a client. To run
the test suite and linters, use `uv sync --extra dev` and the commands in the
README.

## MCP client configuration

Use the console entry point, or `uv --directory`:

```json
{
  "mcpServers": {
    "balneabilidade-sc": {
      "command": "uv",
      "args": ["--directory", "/absolute/path/to/balneabilidade-sc-mcp", "run", "balneabilidade-sc-mcp"]
    }
  }
}
```

On Windows, the absolute path to `.venv\\Scripts\\balneabilidade-sc-mcp.exe`
also works. Adjust paths for the user's checkout.

## Release checklist

1. Update `CHANGELOG.md`, `pyproject.toml` and `__version__`.
2. Run `uv lock`, `uv run ruff check src tests`, `uv run mypy src`, `uv run pytest`.
3. Run `uv build` and verify the wheel/sdist install in a clean environment.
4. Verify a clean clone and a stdio handshake with the official MCP client.
5. Confirm `gh repo view` reports PUBLIC and CI is green.
6. Tag the release (for example `v0.1.0`) and publish release notes.

## Streamable HTTP

A remote Streamable HTTP transport is **not implemented or authorized**. It is
only a possible future option; it would require authentication, authorization,
abuse prevention and a separate security review before any public deployment.
