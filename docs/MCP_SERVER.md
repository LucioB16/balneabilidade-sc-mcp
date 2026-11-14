# MCP server — local stdio

**Status:** implemented and verified over local stdio. Remote HTTP deployment is **not** implemented or authorized.

The server wraps the provider with five MCP tools, keeps all diagnostics on stderr, and returns explicit tool errors for invalid/ambiguous queries and provider outages.

Related: [Provider](PROVIDER.md) · [Product contract](PRODUCT_CONTRACT.md) · [Discovery report](DISCOVERY_REPORT.md)

## What the client model actually sees

The LLM client does **not** automatically read `README.md` or the files under `docs/`. At runtime it receives:

1. the `initialize` server `instructions` (which now include the point-level and vision-fallback policy);
2. the `tools/list` names, descriptions and JSON schemas;
3. the `tools/call` text/structured/image results;
4. only those resources/prompts the client chooses to read (this server currently exposes none).

The repository documents are for developers. The operational policy is deliberately duplicated in the MCP `instructions` and tool descriptions so the model can act without reading the repo. When `vision_fallback` is present, its `instructions` field repeats the fallback procedure in the tool response itself.

## Install and run

```bash
uv sync --extra mcp
uv run balneabilidade-sc-mcp
```

Equivalent module entry point:

```bash
uv run python -m balneabilidade_sc_mcp.server
```

The process speaks MCP over stdin/stdout. It is not meant to be run interactively; configure it in an MCP client.

## Verified client configuration (Windows)

Replace the path with the checkout location:

```json
{
  "mcpServers": {
    "balneabilidade-sc": {
      "command": "E:\\Proyectos\\balneabilidade-sc-mcp\\.venv\\Scripts\\balneabilidade-sc-mcp.exe",
      "args": []
    }
  }
}
```

Alternative using uv:

```json
{
  "mcpServers": {
    "balneabilidade-sc": {
      "command": "uv",
      "args": ["--directory", "E:\\Proyectos\\balneabilidade-sc-mcp", "run", "balneabilidade-sc-mcp"]
    }
  }
}
```

The console entry point is declared as `balneabilidade-sc-mcp = "balneabilidade_sc_mcp.server:main"`.

## Tools

| Tool | Purpose |
|---|---|
| `search_beaches` | Find monitored beaches by name, with municipality disambiguation. |
| `get_sampling_points` | List IMA point UUIDs, locations and coordinates for a resolved beach. |
| `get_bathing_status` | Latest **dated** published result per point plus a conservative beach summary. |
| `get_bathing_history` | Dated CSV history, bounded range and pagination. |
| `get_bulletin_page` | Render one bulletin PDF page as PNG for vision-capable clients; only after `vision_fallback`. |

The four domain tools are the product contract. `get_bulletin_page` is a fallback capability, not the primary status path.

## Status semantics

- `classification`: `proper`, `improper`, `indeterminate` or `unknown`.
- `freshness`: `current`, `carried_forward`, `excluded`, `stale`, `unverified` or `unknown`.
- `summary.status`: `proper`, `improper`, `mixed`, `partial` or `unknown`.
- A point-level `improper` prevents a `proper` beach summary.
- `bulletin_date`, `sample_date`, `data_age_days` and `source` are always present for dated results.
- No tool says "safe now"; use "latest published sample dated …".
- `get_bathing_history` preserves raw point names and E. coli unit/qualifiers, distinguishes `years_without_data` from `years_unavailable`, deduplicates exact rows and exposes `unmatched_names` instead of guessing a renamed point.

## Vision fallback (PDF parser offload)

The deterministic pypdf parser is always primary. When it cannot produce a trustworthy point table, the provider does **not** invent rows:

- If more than `max(2, 5%)` of catalog points are missing, or any heading has no parseable date/verdict, the status result includes `vision_fallback` metadata:
  - `reason`, `bulletin_date`, `source_url`, `page_count`, `pages_available` and instructions.
- The MCP server does not call an LLM itself. A client whose model has vision can call `get_bulletin_page(bulletin_date, page, dpi)` and read the PNG. It must mark pages it cannot read as unverified.
- The server continues to return CSV/analyses fallback status with `bulletin_unverified=true`; it never upgrades the result to a clean "proper" beach because a vision model might read the page.
- Current live bulletin 53/2026 parses 260/260 rows, so the fallback is not triggered in the normal path.

This is deliberate: PDF extraction failure is a data-quality state, not an invitation to guess.

## Logging and safety

- MCP stdio carries protocol messages on stdout. The server logs only to stderr; no `print()` is used.
- `mcp 2.3.0`/`MCPServer` is the verified SDK; `mcp.server.mcpserver.exceptions.ToolError` produces `is_error` tool responses.
- Tool failures are explicit: ambiguous beach, invalid range, provider outage, no data.
- Local stdio is the MVP. There is no authentication, access control or abuse prevention for remote deployment; do not expose this server over a network without a separate security review.
- No IMA credentials are used. The data license remains unresolved; see the discovery report.

## Verification performed

- `uv run pytest`: **71 offline tests** (provider + MCP in-memory client), no network.
- `uv run ruff check src tests`: OK.
- `uv run mypy src`: OK.
- Real stdio handshake with the MCP `ClientSession` + `stdio_client`:
  - listed all five tools;
  - `search_beaches` returned the two Praia Brava candidates;
  - `get_bathing_status` for Perequê returned `proper`, 3 points and bulletin 2026-11-13;
  - stderr contained only diagnostics, no stdout protocol contamination.
- Console entry point starts and exits cleanly on EOF.
- Clean clone of commit 8770a29: uv sync --extra mcp started the console; uv sync --extra dev passed 71 tests, ruff, format, mypy and build; a live stdio client discovered all five tools and ran status/history.

## Known limitations

- The server has no hosted transport, authentication or rate limiting.
- The client configuration path is machine-specific; adjust it for the user's checkout.
- The vision fallback returns images but does not itself produce structured rows; that remains the client model's responsibility and must be clearly labelled.
- Public packaging, licensing, CI and release metadata are documented in RELEASE.md and ATTRIBUTION.md.
