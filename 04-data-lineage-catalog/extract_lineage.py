"""
Versão simplificada do extrator de linhagem: SQL Server + SSRS -> grafo (nodes/edges) em JSON.
Uso: python extract_lineage.py  (variáveis DW_HOST, DW_USER, DW_PASS, DW_DB, REPORT_DB)
"""
import json
import os
import re

import pymssql

CAMADAS = ("bronze", "silver", "gold", "aux")
REF = re.compile(r"\b(?:FROM|JOIN)\s+\[?(\w+)\]?\s*\.\s*\[?(\w+)\]?", re.IGNORECASE)   # schema.tabela após FROM/JOIN


def conectar(db):
    return pymssql.connect(server=os.environ["DW_HOST"], user=os.environ["DW_USER"],
                           password=os.environ["DW_PASS"], database=db)   # credencial só em variável de ambiente


def tabelas(cur):
    cur.execute("""
        SELECT TABLE_SCHEMA, TABLE_NAME
        FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_SCHEMA IN ('bronze','silver','gold','aux')
    """)
    return [f"{s}.{t}" for s, t in cur.fetchall()]


def definicoes_gold(cur):
    cur.execute("""
        SELECT s.name, o.name, m.definition          -- código de views/procedures da Gold
        FROM sys.sql_modules m
        JOIN sys.objects o ON m.object_id = o.object_id
        JOIN sys.schemas s ON o.schema_id = s.schema_id
        WHERE s.name = 'gold' AND o.type IN ('V','P')
    """)
    return {f"{s}.{n}": d for s, n, d in cur.fetchall() if d}


def relatorios(cur):
    cur.execute("""
        SELECT Path, CAST(CAST(Content AS varbinary(max)) AS varchar(max))
        FROM dbo.Catalog
        WHERE Type = 2 AND Content IS NOT NULL       -- Type 2 = relatório
    """)
    saida = {}
    for path, xml in cur.fetchall():
        queries = re.findall(r"<CommandText>(.*?)</CommandText>", xml or "", re.S)   # só a query
        saida[path] = " ".join(queries)                                              # resto do RDL descartado
    return saida


def referencias(sql):
    sql = re.sub(r"--.*?$|/\*.*?\*/", "", sql, flags=re.S | re.M)   # ignora comentários
    return {f"{s.lower()}.{t}" for s, t in REF.findall(sql) if s.lower() in CAMADAS}


def main():
    with conectar(os.environ["DW_DB"]) as conn:
        cur = conn.cursor()
        nodes = [{"id": t, "group": t.split(".")[0]} for t in tabelas(cur)]
        edges = [{"from": r, "to": obj, "kind": "etl"}
                 for obj, sql in definicoes_gold(cur).items() for r in referencias(sql) if r != obj]
    with conectar(os.environ["REPORT_DB"]) as conn:
        for path, sql in relatorios(conn.cursor()).items():
            nodes.append({"id": path, "group": "report"})
            edges += [{"from": r, "to": path, "kind": "consumo"} for r in referencias(sql)]
    edges = sorted({(e["from"], e["to"], e["kind"]) for e in edges})                # dedup + ordem determinística
    grafo = {"nodes": nodes, "edges": [{"from": f, "to": t, "kind": k} for f, t, k in edges]}
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(grafo, f, ensure_ascii=False, indent=2)
    print(f"{len(nodes)} nós, {len(edges)} arestas")


if __name__ == "__main__":
    main()
