<p align="center">
  <sub><a href="README.md">English</a> · <a href="README.es-AR.md">Español (AR)</a> · <strong>Português (BR)</strong></sub>
</p>

<p align="center">
  <img src="assets/brand/wave-mark.svg" width="64" alt="Marca de onda do Balneabilidade SC MCP">
</p>

# Balneabilidade SC MCP

<p align="center">
  <strong>Pergunte ao seu agente como está a água da praia.</strong><br>
  Um servidor MCP local com amostras datadas publicadas pelo IMA/SC, ponto a ponto.
</p>

<p align="center">
  <a href="#instalação">Instalação</a> ·
  <a href="#instalação-manual">Instalação manual</a> ·
  <a href="#ferramentas">Ferramentas</a> ·
  <a href="#o-que-uma-resposta-inclui">Resposta</a>
</p>

<p align="center">
  <a href="https://github.com/LucioB16/balneabilidade-sc-mcp/actions/workflows/ci.yml"><img src="https://github.com/LucioB16/balneabilidade-sc-mcp/actions/workflows/ci.yml/badge.svg" alt="Status do CI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-0B6E99" alt="Licença MIT"></a>
</p>

> **Amostras datadas, não leituras ao vivo.** O cartão abaixo mostra um trecho real de uma resposta MCP. A amostra foi coletada em 2026-11-09 e publicada em 2026-11-13, então não descreve a água de hoje. O IMA/SC coleta semanalmente na temporada e mensalmente fora dela.

| Última amostra publicada | Praia de Zimbros · Bombinhas |
|:--|:--|
| Ponto 09 | `improper` · 1.046 NMP/100mL |
| Ponto 10 | `proper` · 789 NMP/100mL |
| Data da amostra | 2026-11-09 |
| Boletim | 2026-11-13 |
| Resumo da praia | `mixed` (os pontos não concordam) |

A resposta lista cada ponto com sua data de amostra e seu boletim. Um ponto não decide a praia.

## O que você pode perguntar

- “Qual é o último resultado publicado para a Praia de Zimbros e de quando é a amostra?”
- “Mostre cada ponto de coleta; as condições são mistas?”
- “Mostre o histórico de 2025 da Praia de Zimbros, com datas e valores de laboratório.”
- “Quais praias se chamam Praia Brava?” A resposta lista candidatos quando várias compartilham o nome.

## Instalação

### Instalação com seu agente

Copie este prompt para um agente de programação. Ele inclui o repositório e o guia de instalação, então o agente não precisa procurar nenhum dos dois.

```text
Instale o servidor MCP Balneabilidade SC a partir de:
https://github.com/LucioB16/balneabilidade-sc-mcp

Guia de instalação:
https://github.com/LucioB16/balneabilidade-sc-mcp/blob/main/docs/MCP_SERVER.md

Faça isso localmente. Não procure o projeto nem a documentação em outro lugar.

Requisitos:
- Clone o repositório em uma pasta que eu confirmar.
- Use uv: execute `uv sync --extra dev` e `uv run pytest`.
- Registre um servidor MCP stdio local chamado `balneabilidade-sc`:
  `uv --directory <caminho> run balneabilidade-sc-mcp`
- Se você não puder editar a configuração do meu cliente MCP, mostre o JSON exato e onde colá-lo.
- Verifique se o cliente lista as cinco ferramentas e faça uma consulta para "Praia de Zimbros", município "Bombinhas".
- Mostre a configuração e a saída da verificação.

Não exponha o servidor à rede. Peça confirmação antes de modificar arquivos fora do projeto ou configuração global. Não instale globalmente. Não faça commit de credenciais ou configuração local.
```

Se o `uv` não estiver instalado, peça confirmação antes de instalá-lo. A instalação manual está abaixo.

### Instalação manual

```bash
git clone https://github.com/LucioB16/balneabilidade-sc-mcp.git
cd balneabilidade-sc-mcp
uv sync --extra mcp
uv run balneabilidade-sc-mcp
```

O último comando inicia o servidor stdio e espera um cliente. Os logs vão para stderr; stdout transporta o protocolo MCP.

Adicione a um cliente MCP com `uv --directory` (ajuste o caminho absoluto):

```json
{
  "mcpServers": {
    "balneabilidade-sc": {
      "command": "uv",
      "args": [
        "--directory",
        "/caminho/absoluto/para/balneabilidade-sc-mcp",
        "run",
        "balneabilidade-sc-mcp"
      ]
    }
  }
}
```

No Windows, o executável instalado também funciona:

```json
{
  "mcpServers": {
    "balneabilidade-sc": {
      "command": "C:\\caminho\\para\\balneabilidade-sc-mcp\\.venv\\Scripts\\balneabilidade-sc-mcp.exe",
      "args": []
    }
  }
}
```

## Ferramentas

| Ferramenta | Entradas principais | O que retorna |
|:--|:--|:--|
| `search_beaches` | `query`, `municipality` opcional, `limit` | Praias candidatas, município, quantidade de pontos e tipo de correspondência |
| `get_sampling_points` | `beach`, `municipality` opcional | UUIDs dos pontos, localizações e coordenadas |
| `get_bathing_status` | `beach`, `municipality` opcional, `point_id` | Último resultado datado por ponto, resumo da praia, frescor e procedência |
| `get_bathing_history` | `beach`, `municipality` opcional, `point_id`, `from_date`, `to_date`, `limit`, `cursor` | Registros CSV datados com qualificadores, unidade, nomes brutos e cobertura |
| `get_bulletin_page` | `page`, `bulletin_date` opcional, `dpi` | Página PNG apenas para o fallback de visão |

## O que uma resposta inclui

Cada resultado datado por ponto inclui:

| Campo | Significado |
|:--|:--|
| `classification` | `proper`, `improper`, `indeterminate` ou `unknown` |
| `freshness` | `current`, `carried_forward`, `excluded`, `stale`, `unverified` ou `unknown` |
| `sample_date` | Data em que a amostra foi coletada |
| `bulletin_date` | Data do boletim que a publicou, quando conhecida |
| `source` / `source_url` | `bulletin_pdf`, `csv`, `analyses`, `catalog` ou `cache`, além da URL de origem |
| `summary.status` | `proper`, `improper`, `mixed`, `partial` ou `unknown` |

Um ponto que o IMA/SC não coletou, ou cuja amostra foi descartada, não é apresentado como atual. O ponto mantém o rótulo bruto e uma marca explícita de frescor. Qualquer ponto impróprio impede que o resumo da praia seja `proper`.

## Histórico

`get_bathing_history` lê os CSV publicados pelo IMA/SC:

- intervalo `from_date`/`to_date` inclusivo e ordem decrescente;
- paginação limitada com cursor;
- nomes brutos dos pontos, localização e `csv_year`;
- valores de E. coli com qualificadores `<20`/`<10`/`> 24196` e unidade `NMP/100mL`;
- `years_without_data` separado de `years_unavailable`;
- linhas duplicadas exatas são deduplicadas e contadas;
- mudanças de nome são expostas em `unmatched_names`, não adivinhadas;
- se CSV e o último boletim discordarem sobre a mesma amostra, o veredito do boletim é mantido e um warning é retornado.

O histórico vem dos CSV publicados pelo IMA/SC. O PDF do último boletim é a referência para o estado atual.

## Exemplos

Português:

- “Qual é o último resultado publicado para a Praia de Zimbros, em Bombinhas?”
- “Mostre cada ponto de coleta e o histórico de 2025.”

Espanhol:

- “¿Cuál es el último resultado publicado para Praia de Zimbros, en Bombinhas?”
- “Mostrame cada punto de muestreo y el historial de 2025.”

Uma resposta útil informa o ponto, a data da amostra e a data do boletim. Não diz “está segura agora”.

## Fallback de visão

O parser determinístico do PDF é o caminho principal. Se não conseguir validar uma tabela de pontos confiável, `get_bathing_status` inclui metadados `vision_fallback`. Um cliente com modelo que tenha visão pode chamar `get_bulletin_page` e ler as páginas PNG originais. O servidor só devolve imagens de páginas. Não chama um LLM nem cria linhas, e deixa o status sem mudanças.

## Desenvolvimento

```bash
uv sync --extra dev
uv run pytest
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src
uv build
```

A suíte offline tem 71 testes e nunca chama o IMA. A sonda de descoberta é separada e somente leitura:

```bash
python scripts/discovery_probe.py
```

O CI executa lint, format check, mypy, testes offline e build do pacote em Python 3.11 e 3.12. Não precisa de credenciais e não faz chamadas ao IMA.

## Dados, atribuição e licença

A fonte é o **Instituto do Meio Ambiente de Santa Catarina (IMA/SC)**, <https://balneabilidade.ima.sc.gov.br/>. Cite sempre o órgão, o número do relatório/boletim, a data da amostra e a URL de origem.

Não foi confirmada uma licença de reutilização para o material do IMA/SC. Este repositório não redistribui PDFs, exportações CSV ou datasets em massa; o provedor os obtém em runtime. Veja [docs/ATTRIBUTION.md](docs/ATTRIBUTION.md) antes de publicar dados derivados.

O código e a documentação têm licença MIT. A licença não cobre os dados do IMA/SC. Veja [LICENSE](LICENSE).

## Limitações

- O parse do PDF depende do layout. O fallback de visão é do cliente; o servidor não faz OCR.
- O histórico vem de CSV; o PDF é a referência apenas para o último boletim.
- Os joins por nome exato expõem mudanças em vez de adivinhá-las; um ponto renomeado pode aparecer como unmatched.
- O servidor escuta apenas em stdio local. Não tem transporte remoto, autenticação, controle de acesso ou rate limiting. Não o exponha à internet sem uma revisão de segurança separada.
- O provedor usa um cache TTL pequeno em vez de um banco de dados.
- Isto não é uma garantia médica nem de segurança.

## Documentação

- [Relatório de descoberta](docs/DISCOVERY_REPORT.md)
- [Contrato do produto](docs/PRODUCT_CONTRACT.md)
- [Provedor](docs/PROVIDER.md)
- [Servidor MCP](docs/MCP_SERVER.md)
- [Notas de release](docs/RELEASE.md)
- [Atribuição e licença de dados](docs/ATTRIBUTION.md)
- [Política de segurança](SECURITY.md)

## Estrutura do projeto

```text
src/balneabilidade_sc_mcp/
  provider.py       reconciliação de fontes, frescor, histórico
  bulletin.py       índice do portal, parse de PDF, exclusões
  history.py        exportação e parse de CSV
  catalog.py        catálogo do mapa e matching
  server.py         ferramentas MCP stdio
  pdf_vision.py     renderização PNG de fallback
docs/               descoberta, contrato, provedor, servidor, release, atribuição
tests/              71 testes offline com fixtures sintéticos
```
