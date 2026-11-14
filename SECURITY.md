# Security policy

## Scope and deployment

This project is a **local stdio MCP server** plus a Python provider. It does not
ship a network listener, authentication layer, multi-user access control or
rate limiter. Do not expose it directly to the internet or to untrusted users.

## Data and safety

- The server reads public IMA/SC pages and PDFs. Treat all upstream content as
  untrusted input; the provider validates shapes and never executes upstream
  HTML.
- Bathing-water results are **dated samples published by IMA/SC**, not real-time sensing
  and not a medical or safety guarantee. See the README caveats.
- No IMA credentials, API keys or private data are required or accepted.

## Reporting

Please open a private security advisory through GitHub Security Advisories for
the repository, or contact the maintainer through the GitHub profile. Avoid
publishing exploit details before a fix is available.

## Dependency and supply-chain posture

- Runtime dependencies are declared in pyproject.toml and locked in uv.lock.
- CI installs from the lockfile and runs offline tests only; the default CI does
  not call IMA.
- PDF rendering uses PyMuPDF; report parsing is local. Do not accept PDFs from
  untrusted remote callers in a future hosted deployment without isolation.
