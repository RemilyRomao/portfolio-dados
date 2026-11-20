/* =============================================================================
   dbo.usp_trocar_tabela
   Coloca <schema>.<tabela>__carga no lugar da oficial com ALTER TABLE SWITCH.
   Pré-requisito: <tabela>__carga e <tabela>__descarte com a mesma estrutura
   e os mesmos índices da oficial, no mesmo filegroup.
   Compatível com SQL Server 2016+.
============================================================================= */
CREATE OR ALTER PROCEDURE dbo.usp_trocar_tabela
    @schema         sysname,
    @tabela         sysname,
    @max_espera_min int = 3                  -- quanto tempo esperar o lock, em baixa prioridade
AS
BEGIN
    SET NOCOUNT ON;                          -- não devolve "n linhas afetadas"
    SET XACT_ABORT ON;                       -- qualquer erro desfaz a transação inteira

    -- QUOTENAME protege os nomes (evita SQL injection e nomes com espaço)
    DECLARE @oficial  nvarchar(400) = QUOTENAME(@schema) + N'.' + QUOTENAME(@tabela);
    DECLARE @carga    nvarchar(400) = QUOTENAME(@schema) + N'.' + QUOTENAME(@tabela + N'__carga');
    DECLARE @descarte nvarchar(400) = QUOTENAME(@schema) + N'.' + QUOTENAME(@tabela + N'__descarte');
    DECLARE @sql      nvarchar(max);
    DECLARE @inicio   datetime2(3) = SYSDATETIME();

    -- As três tabelas precisam existir
    IF OBJECT_ID(@oficial, N'U') IS NULL OR OBJECT_ID(@carga, N'U') IS NULL
       OR OBJECT_ID(@descarte, N'U') IS NULL
        THROW 50010, 'Tabela oficial ou de apoio ausente.', 1;

    IF @max_espera_min < 1
        THROW 50011, '@max_espera_min deve ser >= 1.', 1;

    SET @sql = N'TRUNCATE TABLE ' + @descarte + N';';       -- limpa sobra de troca anterior
    EXEC sys.sp_executesql @sql;

    BEGIN TRAN;
        SET @sql = N'ALTER TABLE ' + @oficial + N' SWITCH TO ' + @descarte          -- versão antiga sai
                 + N' WITH (WAIT_AT_LOW_PRIORITY (MAX_DURATION = '
                 + CAST(@max_espera_min AS nvarchar(10))
                 + N' MINUTES, ABORT_AFTER_WAIT = SELF));'                         -- não bloqueia quem lê
                 + N' ALTER TABLE ' + @carga + N' SWITCH TO ' + @oficial + N';';    -- versão nova entra
        EXEC sys.sp_executesql @sql;
    COMMIT TRAN;                             -- leitores veem a antiga até aqui e a nova depois

    SET @sql = N'TRUNCATE TABLE ' + @descarte + N';';       -- descarta a versão antiga
    EXEC sys.sp_executesql @sql;

    -- O SWITCH não leva as estatísticas: atualiza só as dos índices (rápido)
    SET @sql = N'UPDATE STATISTICS ' + @oficial + N' WITH INDEX;';
    EXEC sys.sp_executesql @sql;

    PRINT CONCAT(N'Troca concluída em ', @oficial, N' (',
                 DATEDIFF(MILLISECOND, @inicio, SYSDATETIME()), N' ms).');
END
