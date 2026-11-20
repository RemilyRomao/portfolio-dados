# 04 — Catálogo de dados e linhagem automáticos

## Problema

Com mais de 500 tabelas em Bronze, Silver e Gold e dezenas de relatórios, ninguém sabia responder com segurança "de onde vem este número?" ou "quem quebra se eu mudar esta tabela?".

## Solução

Um catálogo que **se gera sozinho** a partir dos metadados, sem cadastro manual:

1. **Extração:** lê do SQL Server as tabelas e colunas (`INFORMATION_SCHEMA`), o código das views e procedures (`sys.sql_modules`), os índices e o `MAX(dt_carga)` de cada tabela. Do Report Server, lê os relatórios publicados (`dbo.Catalog`) e a query de cada dataset.
2. **Linhagem:** extrai as tabelas referenciadas em cada query (`FROM`/`JOIN`) e no SQL das cargas, e gera as arestas "A alimenta B".
3. **Freshness em cascata:** uma tabela Gold pode ter rodado hoje e ainda trazer dado velho se a Bronze dela parou. O grafo propaga o pior sinal da cadeia e aponta **qual elo quebrou**.
4. **Publicação:** um `data.json` desenhado como grafo numa página web, atualizado por uma DAG diária.

Fotografia real: **633 objetos** (238 Bronze, 228 Silver, 111 Gold, 53 relatórios) e **1.268 ligações**.

## Decisões de engenharia

- **Só metadados:** o RDL é lido em memória e só a query é guardada; a string de conexão (que pode conter senha) é descartada.
- **Determinismo:** a ordem dos pais é ordenada para dois builds com a mesma entrada darem o mesmo resultado.
- **Dev × prod no mesmo mapa:** mostra o que só existe em homologação.
- **Testes:** cada módulo tem teste automatizado.

## Arquivo

- [`extract_lineage.py`](extract_lineage.py): versão simplificada da extração e da linhagem.
