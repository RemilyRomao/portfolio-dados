/* =============================================================================
   Silver incremental com dedup e overlap
   Origem: bronze.nota_fiscal (atual) + bronze.nota_fiscal_hist (histórico)
   Destino: silver.nota_fiscal  |  Chave natural: empresa, tipo, serie, numero
============================================================================= */
SET NOCOUNT ON;                              -- não devolve "n linhas afetadas"
SET XACT_ABORT ON;                           -- qualquer erro desfaz a transação inteira

DECLARE @OverlapMinutes INT = 10;            -- OVERLAP: volta 10 min antes da última carga
DECLARE @dt_ultima_carga DATETIME;           -- WATERMARK: até onde a Silver já está atualizada

-- Ponto de partida = maior dt_carga da Silver menos o overlap
SELECT @dt_ultima_carga = DATEADD(MINUTE, -@OverlapMinutes, MAX(dt_carga))
FROM silver.nota_fiscal;

-- 1) Só as CHAVES que mudaram desde o watermark (atual + histórico)
IF OBJECT_ID('tempdb..#chaves') IS NOT NULL DROP TABLE #chaves;

SELECT DISTINCT cd_empresa, tp_documento, cd_serie, nr_lancamento
INTO #chaves
FROM (
    SELECT cd_empresa, tp_documento, cd_serie, nr_lancamento
    FROM bronze.nota_fiscal      WHERE dt_carga >= @dt_ultima_carga
    UNION                                    -- UNION (sem ALL) já remove repetidas
    SELECT cd_empresa, tp_documento, cd_serie, nr_lancamento
    FROM bronze.nota_fiscal_hist WHERE dt_carga >= @dt_ultima_carga
) x;

-- Índice clusterizado único na temp: os JOINs seguintes ficam rápidos
CREATE UNIQUE CLUSTERED INDEX ix_chaves
    ON #chaves (cd_empresa, tp_documento, cd_serie, nr_lancamento);

BEGIN TRY
    BEGIN TRAN;                              -- tudo ou nada

    -- 2) REPLACE-BY-KEY, parte 1: apaga da Silver as chaves que serão regravadas
    DELETE s
    FROM silver.nota_fiscal s
    JOIN #chaves c
      ON  c.cd_empresa = s.cd_empresa AND c.tp_documento  = s.tp_documento
      AND c.cd_serie   = s.cd_serie   AND c.nr_lancamento = s.nr_lancamento;

    -- 3) Junta atual + histórico só dessas chaves e escolhe a versão mais recente
    WITH fonte AS (
        SELECT b.* FROM bronze.nota_fiscal b
        JOIN #chaves c
          ON  c.cd_empresa = b.cd_empresa AND c.tp_documento  = b.tp_documento
          AND c.cd_serie   = b.cd_serie   AND c.nr_lancamento = b.nr_lancamento
        UNION ALL                            -- mantém tudo: quem decide é o dedup
        SELECT h.* FROM bronze.nota_fiscal_hist h
        JOIN #chaves c
          ON  c.cd_empresa = h.cd_empresa AND c.tp_documento  = h.tp_documento
          AND c.cd_serie   = h.cd_serie   AND c.nr_lancamento = h.nr_lancamento
    ),
    dedup AS (
        SELECT f.*,
               ROW_NUMBER() OVER (
                   PARTITION BY f.cd_empresa, f.tp_documento,
                                f.cd_serie, f.nr_lancamento    -- um grupo por documento
                   ORDER BY f.dt_record  DESC,                 -- 1º: alteração mais recente na origem
                            f.hr_record  DESC,                 -- 2º: hora da alteração
                            f.dt_carga   DESC,                 -- 3º: carga mais recente
                            f.dt_emissao DESC                  -- 4º: desempate final (determinístico)
               ) AS rn
        FROM fonte f
    )
    -- 4) REPLACE-BY-KEY, parte 2: insere só a versão vencedora
    INSERT INTO silver.nota_fiscal (cd_empresa, tp_documento, cd_serie, nr_lancamento,
                                    dt_emissao, vl_total, dt_record, hr_record, dt_carga)
    SELECT cd_empresa, tp_documento, cd_serie, nr_lancamento,
           dt_emissao, vl_total, dt_record, hr_record, dt_carga
    FROM dedup
    WHERE rn = 1;

    COMMIT TRAN;                             -- confirma delete + insert juntos
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0 ROLLBACK TRAN;        -- erro: a Silver fica exatamente como estava
    THROW;                                   -- relança: a task do orquestrador falha e alerta
END CATCH;
