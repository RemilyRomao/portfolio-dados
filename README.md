# Portfólio de Engenharia e Analytics — Remily Romão

Analista de BI / Analytics Engineer. Padrões que uso em produção num Data Warehouse corporativo em arquitetura medalhão (Bronze/Silver/Gold), com Apache Airflow, SQL Server, Oracle, Python e Power BI.

> Todo o código aqui é uma versão **genérica e anonimizada** de soluções reais: nenhum nome de empresa, servidor, credencial ou dado de cliente.

## Projetos

| # | Projeto | O que mostra | Stack |
|---|---|---|---|
| 01 | [Carga incremental com dedup e overlap](01-incremental-dedup-overlap/) | Watermark, janela de overlap, replace-by-key, ROW_NUMBER determinístico, transação | T-SQL |
| 02 | [Troca de tabela sem downtime](02-zero-downtime-table-swap/) | `ALTER TABLE SWITCH` + `WAIT_AT_LOW_PRIORITY`: relatório nunca vê tabela vazia ou travada | T-SQL, SSRS |
| 03 | [Ingestão de API com Airflow](03-airflow-api-ingestion/) | DAG com branch, OAuth2 app-only (MSAL/Microsoft Graph), paginação, idempotência por arquivo | Python, Airflow 3 |
| 04 | [Catálogo de dados e linhagem](04-data-lineage-catalog/) | Grafo de linhagem gerado dos metadados do SQL Server e do SSRS, freshness em cascata | Python, SQL, JSON |

## Resultados reais por trás destes padrões

- Tempo médio dos relatórios na janela de carga: **15,7 s → 0,2 s**; execuções acima de 30 s: **266 → 0** (projeto 02).
- Catálogo com **633 objetos** e **1.268 ligações** de linhagem, atualizado diariamente (projeto 04).
- Carga incremental resiliente a transações longas no Oracle e a carimbos de data inconsistentes na origem (projeto 01).

## Contato

[LinkedIn](https://linkedin.com/in/remily-romao)
