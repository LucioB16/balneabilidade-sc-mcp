# IMA/SC Discovery Report

**Status:** NOT STARTED — complete in Phase 1 before provider implementation.  
**Investigation date / timezone:** TBD (`America/Sao_Paulo` for official sampling dates; also record test UTC timestamp).  
**Public repository URL and checked commit:** TBD.

## 1. Reproducible HTTP evidence
Fill a row for every endpoint actually tested. Log method, URL, sanitized input, status code, content type, response shape, timing, date and any error. Do **not** mark a hypothesis as confirmed merely because Marola uses it.

| Endpoint | Test date (UTC) | Request (sanitized) | Result/status/Content-Type | Shape/evidence | Conclusion |
|---|---|---|---|---|---|
| `/relatorio/mapa` | TBD | TBD | TBD | TBD | TBD |
| `/municipio/getMunicipios` | TBD | TBD | TBD | TBD | TBD |
| `/local/getLocaisByMunicipio` | TBD | TBD | TBD | TBD | TBD |
| `/pontoColeta/getPontosByLocal` | TBD | TBD | TBD | TBD | TBD |
| `/registro/anosAnalisados` | TBD | TBD | TBD | TBD | TBD |
| `/relatorio/exportarCSV` | TBD | TBD | TBD | TBD | TBD |
| `/relatorio/historico` | TBD | TBD | TBD | TBD | TBD |
| latest `/relatorio/downloadPDF/<date>` | TBD | TBD | TBD | TBD | TBD |

## 2. Source precedence and reconciliation
- Map JSON: confirmed content and date availability = TBD
- CSV: which identifier/name fields are required = TBD; dated measurements = TBD
- PDF: latest report discovered dynamically = TBD; date per point = TBD
- Join key: point ID vs normalized municipality + beach + point name = TBD
- Reconciliation conflicts and incomplete joins = TBD
- Freshness policy (with specific evidence/justification) = TBD

## 3. Sampled locations and failure cases
Record at least three actually monitored beach/municipality cases, with same-named beaches and multiple sampling points if present. Do not invent results.

## 4. Legal/operational notes
IMA usage terms, licensing and attribution; endpoint reliability; cache and polite polling; CORS only if relevant; fallback outage plan; confidence = TBD.

## 5. Decision record (implement only after phase approval)
- Recommended provider routes and reasons: TBD
- Alternatives rejected and reasons: TBD
- SDK/runtime pinned version and transport: TBD
- Remaining blockers and mitigations: TBD
- Repro commands and redacted example outputs: TBD
- Commit SHA(s), CI/test evidence, published URL: TBD
