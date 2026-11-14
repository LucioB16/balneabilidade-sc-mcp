# Balneabilidade SC MCP

**Project bootstrap — server not implemented yet.** Public GitHub repository creation and IMA/SC endpoint discovery are the first tasks described in [`PLAN.md`](PLAN.md).

Goal: a small MCP server that lets an AI agent retrieve the **latest published official bathing-water assessment** and **sampling history** for beaches in Santa Catarina, Brazil. It should resolve municipality, beach and monitoring point, and say exactly **when** the reported condition was measured. Official sampling reports are not real-time guarantees.

Data provider: [Instituto do Meio Ambiente de Santa Catarina (IMA/SC)](https://balneabilidade.ima.sc.gov.br/).

Technical inspiration: [marola-dev/marola-app](https://github.com/marola-dev/marola-app). The new project will be scoped to Santa Catarina water quality, not Marola's other marine features. Review licenses and source-data terms before reusing code or redistributing datasets.

## For the coding agent

Read [`AGENTS.md`](AGENTS.md) and execute the **next incomplete phase** of [`PLAN.md`](PLAN.md). Phase 1 must first create and verify a **public GitHub repository**, then conduct a reproducible integration discovery, and finally stop before implementation for approval.

Research baseline: [`docs/RESEARCH_BASELINE.md`](docs/RESEARCH_BASELINE.md)  
Evidence report: [`docs/DISCOVERY_REPORT.md`](docs/DISCOVERY_REPORT.md)  
Tool design: [`docs/PRODUCT_CONTRACT.md`](docs/PRODUCT_CONTRACT.md)

Install and client configuration instructions will be added once tested; no working MCP server is claimed at this stage.
