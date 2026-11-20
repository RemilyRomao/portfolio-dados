# 02 — Troca de tabela sem downtime (ALTER TABLE SWITCH)

## Problema

Relatórios SSRS ficavam lentos sempre entre os minutos :10 e :29 de cada hora. A análise do `ReportServer.ExecutionLog3` (tempo de banco × processamento × renderização), cruzada com o horário das DAGs, mostrou que a causa não era a query: era a carga horária da Gold (TRUNCATE + INSERT) travando a leitura.

## Solução

Carregar numa cópia (`<tabela>__carga`) e, no fim, trocar a cópia pela oficial com `ALTER TABLE ... SWITCH`, que só mexe em metadados e leva milissegundos.

- `WAIT_AT_LOW_PRIORITY (MAX_DURATION = N MINUTES, ABORT_AFTER_WAIT = SELF)`: espera o lock sem enfileirar quem está lendo; se estourar o tempo, desiste a própria carga, que é refeita no retry.
- Quem consulta vê a versão antiga completa até o COMMIT e a nova depois: **nunca tabela vazia nem presa**.
- `UPDATE STATISTICS ... WITH INDEX` depois da troca: o SWITCH não leva as estatísticas, e atualizar só as de índice mantém o lock curto.

## Resultado

| Janela de carga | Antes | Depois |
|---|---|---|
| Tempo médio de banco por relatório | 15,7 s | **0,2 s** |
| Execuções acima de 30 s | 266 | **0** |

## Arquivos

- [`usp_trocar_tabela.sql`](usp_trocar_tabela.sql): a procedure de troca.
- [`exemplo_task_gold.sql`](exemplo_task_gold.sql): como uma carga Gold usa a troca.
