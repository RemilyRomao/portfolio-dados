-- Carga de uma tabela Gold usando a troca. A task roda com autocommit desligado.
TRUNCATE TABLE gold.fato_vendas__carga;        -- 1) limpa a cópia

INSERT INTO gold.fato_vendas__carga (id_venda, dt_venda, id_cliente, vl_venda)   -- 2) carrega a cópia
SELECT s.id_venda, s.dt_venda, s.id_cliente, s.vl_venda                          --    (os relatórios seguem
FROM silver.vendas s;                                                            --     lendo a oficial)

EXEC dbo.usp_trocar_tabela 'gold', 'fato_vendas';   -- 3) troca em milissegundos (sempre a última instrução)
