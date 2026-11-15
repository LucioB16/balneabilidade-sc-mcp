# Remote Streamable HTTP

The package now exposes the existing five MCP tools through stateless Streamable
HTTP while keeping the default stdio command unchanged. The HTTP transport is
intended for a trusted HTTPS reverse proxy or container host; do not publish a
development server directly.

## Local smoke check

Install the optional MCP extra and run the HTTP entry point:

```bash
uv sync --extra mcp
BALNEABILIDADE_ALLOWED_HOSTS=127.0.0.1,127.0.0.1:* \
BALNEABILIDADE_ALLOWED_ORIGINS=http://127.0.0.1:*,http://localhost:* \
BALNEABILIDADE_CACHE_DIR=.cache/balneabilidade \
uv run balneabilidade-sc-mcp-http
```

The endpoint is `http://127.0.0.1:8000/mcp`. The production deployment must
terminate TLS at its HTTPS ingress and set the host allowlist to its exact
public hostname (including the port only if the proxy sends one). Set
`BALNEABILIDADE_ALLOWED_ORIGINS` to the exact browser origins that need access;
server-to-server requests without an `Origin` header are accepted. Do not use
wildcard hosts or disable DNS rebinding protection for a public deployment.

The HTTP app uses the same `create_server()` registration and lifespan as
stdio, with JSON responses and stateless sessions. Its default provider paces
outbound IMA requests at 0.2 seconds per process and uses the existing TTL file
cache. Set `BALNEABILIDADE_CACHE_DIR` to writable persistent storage when the
host provides it; `/tmp` is suitable only for an ephemeral cache.

## Public hosting requirements

- Expose only `/mcp` over stable HTTPS and verify MCP initialization,
  `tools/list`, and tool calls from the actual ChatGPT connection.
- Keep the endpoint read-only and configure ingress request limits. The
  provider pacing is process-local, not a global limit across replicas.
- Prefer a single replica with a persistent cache unless the host adds a
  shared cache and a global IMA request limiter. Serverless ephemeral files do
  not provide shared caching or global pacing.
- Keep access logs disabled or minimize them. The service makes no user account
  and should not log raw MCP requests; host-level logs and retention still
  depend on the chosen provider.
- Do not claim that published samples are real-time. Responses retain sample
  date, bulletin date, source, per-point verdicts, and freshness information.

This document describes the server capability, not a deployed production URL.
Only add a verified public HTTPS endpoint to a distributable `mcp.json` after
the host is selected and the connection is tested.
