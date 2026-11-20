# 03 — Ingestão de planilhas do SharePoint com Airflow e Microsoft Graph

## Problema

A área de RH publica planilhas mensais numa biblioteca do SharePoint. Os indicadores dependiam de alguém baixar e consolidar à mão.

## Solução (DAG diária)

1. **Branch:** lista os arquivos via Microsoft Graph e compara com os já carregados. Sem arquivo novo, a DAG encerra.
2. **Autenticação app-only (OAuth2 client credentials) com MSAL:** credenciais só na Connection do Airflow, nunca no código.
3. **Paginação** com `@odata.nextLink` e `raise_for_status` para falhar cedo (401/403/500).
4. **Qualidade:** valida o layout (quantidade de colunas) antes de gravar; arquivo fora do padrão é pulado e logado.
5. **Linhagem e idempotência:** o nome do arquivo vira a coluna `arquivo_origem`; arquivo já carregado nunca entra de novo.
6. **Gold:** só roda se houve carga.
7. **Alerta:** callback de falha no Teams, com retries.

## Arquivo

- [`dag_sharepoint_rh.py`](dag_sharepoint_rh.py)
