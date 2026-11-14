# Research baseline (leads to verify live)

Last prepared: **2026-11-14**. These are **leads**, not proof of successful POST requests executed in this workspace. Recheck all claims and link to the exact upstream commit tested in `DISCOVERY_REPORT.md`.

## Official data source
- Portal: https://balneabilidade.ima.sc.gov.br/
- The official portal listed the 53/2026 report dated 2026-11-13 when checked, alongside links to historic reports. Treat this as an example, **not a hard-coded latest date**.
- Classification labels seen in official UI: `Próprio`, `Impróprio`, `Indeterminado`. Date of a sample matters; "próprio" is never an instant water sensor reading.

## Existing public clients
- Marola: https://github.com/marola-dev/marola-app (MIT at time of research). Its IMA JSON adapter: https://github.com/marola-dev/marola-app/blob/main/local/src/main/scala/marola/water/ImaScWaterQualityClient.scala
- Marola PDF fallback: https://github.com/marola-dev/marola-app/blob/main/local/src/main/scala/marola/water/ImaScPdfWaterQualityClient.scala
- Marola incident #57, created 2026-10-06: https://github.com/marola-dev/marola-app/issues/57 — reportedly the `POST /relatorio/mapa` response then contained 337 points but no dated `ANALISES`. Verify **now**; the behavior may change again.
- Historic CSV discovery and design: https://github.com/marola-dev/marola/blob/main/docs/MIPs/MIP-0056-oods-open-ocean-data-store.md — describes `POST /relatorio/exportarCSV` with `municipioID`, `localID`, `ano`, and CSV spanning years. Confirm live parameter semantics and contents.
- Archived official portal HTML/JS captured by Marola: https://github.com/marola-dev/marola-app/blob/main/oods/src/test/resources/ima-sc/index-2026-09-14.html — useful to confirm how the portal uses `.post()` and CSV export.
- Another independently implemented Python client: https://github.com/soutobias/oceanobs/blob/dev/oceanobs/water_quality/sc.py
- Official Python MCP SDK: https://github.com/modelcontextprotocol/python-sdk and https://py.sdk.modelcontextprotocol.io/ — v2 uses `MCPServer` (old v1 examples use `FastMCP`). Verify pinned stable version before coding.

## Endpoint hypotheses (verify method/body and output!)
| Candidate | Hypothesized method | Purpose | Unverified items |
|---|---|---|---|
| `/relatorio/mapa` | POST empty | All sampled points and coordinates, top-level condition | Whether dates / `ANALISES` exist, fresh content |
| `/municipio/getMunicipios` | GET or POST | Municipalities | Method and catalog schema |
| `/local/getLocaisByMunicipio` | POST `municipioID` | Beaches/locations per municipality | ID/name semantics |
| `/pontoColeta/getPontosByLocal` | POST `localID` | Points per beach | Point IDs, status and location |
| `/registro/anosAnalisados` | POST | Available history years | Response shape and extent |
| `/relatorio/exportarCSV` | POST `municipioID`,`localID`,`ano` | Dated historical records | Names vs IDs, encoding, edge cases |
| `/relatorio/historico` | POST | Historical HTML table | Full form payload |
| `/relatorio/downloadPDF/YYYY-MM-DD` | GET | Dated IMA report | Discover date from index, PDF parsing |

## Important unresolved considerations
1. API appears to be portal-internal, undocumented and possibly unstable. There is **no confirmed official public API support contract**.
2. Previous third-party checks reported missing CORS headers; server-side stdio MCP avoids browser CORS, but reconfirm only if relevant.
3. Sampling schedule is not equivalent to real-time readings. Show sample/bulletin age and no-data state rather than a binary unsupported claim.
4. A beach often has multiple sampled points. Preserve **point-level** details, and never mark the whole beach safe based on one point.
5. Do not copy extensive upstream code or datasets without reviewing license and attribution. Marola code currently appears MIT; IMA data reuse terms were not established during preliminary research.
