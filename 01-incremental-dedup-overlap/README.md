# 01 — Carga incremental com dedup e janela de overlap

## Problema

A origem (ERP em Oracle) envia o mesmo registro várias vezes (tabela atual + histórico) e carimba a data de alteração no momento do comando, não do commit. Uma carga incremental ingênua por data **perde registros** de transações longas e **duplica** registros reenviados.

## Solução

1. **Watermark:** a carga lê só o que mudou desde a última carga (`MAX(dt_carga)` da Silver).
2. **Overlap:** volta N minutos antes do watermark para recapturar o que chegou atrasado.
3. **Chaves impactadas:** descobre só as chaves que mudaram e grava numa temp com índice clusterizado.
4. **Replace-by-key:** apaga essas chaves da Silver e reinsere a versão mais recente.
5. **Dedup determinístico:** `ROW_NUMBER` com desempate completo, para o resultado não mudar entre execuções.
6. **Transação:** delete + insert juntos; qualquer erro desfaz tudo e falha a task do orquestrador.

Resultado: a carga é **idempotente** (rodar duas vezes dá o mesmo resultado).

## Arquivo

- [`silver_incremental_dedup.sql`](silver_incremental_dedup.sql)

## Por que o overlap importa

Uma transação começa às 10:50 e confirma às 10:58. O registro chega com data 10:50. Se a carga anterior rodou às 10:55 e avançou o watermark, sem overlap esse registro nunca é lido. Com overlap de 60 min, ele é relido, e o replace-by-key garante que não duplica.
