# Attribution and data licensing

## IMA/SC official data

The data is published by the **Instituto do Meio Ambiente de Santa Catarina
(IMA/SC)** at <https://balneabilidade.ima.sc.gov.br/>.

No explicit data-reuse license, terms of use or open-data statement was found
on the portal or in the Santa Catarina open-data catalog during the 2026-11-14
discovery. Public availability is not a reuse license. This repository does not
redistribute IMA PDFs, CSV exports or bulk datasets; the provider fetches them
at runtime. Any future dataset publication requires a separate, deliberate
licensing decision.

When reporting a result, preserve the official source and dates, for example:
"Instituto do Meio Ambiente de Santa Catarina (IMA/SC), Relatório 53/2026,
sample 2026-11-09, <https://balneabilidade.ima.sc.gov.br/relatorio/downloadPDF/2026-11-13>."

## Marola reference implementation

[marola-dev/marola-app](https://github.com/marola-dev/marola-app) is an MIT
reference, not a dependency. Its IMA JSON/PDF adapters and issue #57 were
reviewed at commit 7061a08e643c5fe05485cb2917be405f5b1ab8c4. No Marola source
code is copied into this repository; the design notes are attribution in
[docs/DISCOVERY_REPORT.md](DISCOVERY_REPORT.md). If code is copied later, the
MIT copyright and permission notice must be retained.

## Project code

Project source code and documentation are licensed under the MIT License; see
[LICENSE](../LICENSE). The MIT license does not apply to IMA/SC data or to
third-party material.
