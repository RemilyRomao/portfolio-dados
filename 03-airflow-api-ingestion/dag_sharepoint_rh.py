"""
DAG sharepoint_rh: lê planilhas novas de uma biblioteca do SharePoint (Microsoft Graph),
grava na camada aux e gera a tabela Gold dos indicadores de RH.
Versão genérica e anonimizada de uma DAG em produção (Airflow 3).
"""
import io
from datetime import datetime

import msal                                   # autenticação Microsoft (OAuth2)
import pandas as pd                           # leitura e validação das planilhas
import pymssql                                # conexão com o SQL Server
import requests                               # chamadas HTTP ao Microsoft Graph
from airflow import DAG
from airflow.providers.standard.operators.empty import EmptyOperator
from airflow.providers.standard.operators.python import BranchPythonOperator, PythonOperator
from airflow.sdk.bases.hook import BaseHook

CONN_GRAPH = "cnn_sharepoint"                 # Connection do Airflow: tenant_id, client_id, client_secret
CONN_DW = "cnn_dw"                            # Connection do SQL Server de destino
GRAPH = "https://graph.microsoft.com/v1.0"
SITE_HOST = "<tenant>.sharepoint.com"         # site e pasta parametrizados
SITE_PATH = "/sites/<site>"
PASTA = "<pasta das planilhas>"
COLUNAS = ["ano", "mes", "matricula", "centro_custo", "cod_evento", "desc_evento", "horas", "valor"]

INSERT_SQL = """
INSERT INTO aux.rh_horas_extras (ano, mes, matricula, centro_custo, cod_evento,
                                 desc_evento, horas, valor, arquivo_origem)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
"""


def _graph_session():
    conn = BaseHook.get_connection(CONN_GRAPH)                # credencial fora do código
    extra = conn.extra_dejson
    app = msal.ConfidentialClientApplication(                 # login de APLICAÇÃO (app-only)
        extra["client_id"],
        authority=f"https://login.microsoftonline.com/{extra['tenant_id']}",
        client_credential=extra.get("client_secret") or conn.password,
    )
    token = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
    if "access_token" not in token:                           # falha com motivo claro
        raise RuntimeError(f"Falha ao obter token: {token.get('error')}")
    s = requests.Session()                                    # reaproveita a conexão HTTP
    s.headers["Authorization"] = f"Bearer {token['access_token']}"
    return s


def _drive_id(s):
    site = s.get(f"{GRAPH}/sites/{SITE_HOST}:{SITE_PATH}")   # acha o site
    site.raise_for_status()
    drives = s.get(f"{GRAPH}/sites/{site.json()['id']}/drives")
    drives.raise_for_status()
    return drives.json()["value"][0]["id"]                    # biblioteca de documentos


def _listar_arquivos(s, drive_id):
    url = f"{GRAPH}/drives/{drive_id}/root:/{requests.utils.quote(PASTA)}:/children"
    arquivos = []
    while url:                                                # PAGINAÇÃO
        r = s.get(url)
        r.raise_for_status()                                  # 401/403/500 vira erro na hora
        payload = r.json()
        arquivos += [i for i in payload["value"] if "file" in i and i["name"].lower().endswith(".xlsx")]
        url = payload.get("@odata.nextLink")                  # próxima página (None = fim)
    return arquivos


def _db():
    c = BaseHook.get_connection(CONN_DW)
    return pymssql.connect(server=c.host, user=c.login, password=c.password, database=c.schema)


def _ja_carregados(conn):
    with conn.cursor() as cur:                                # IDEMPOTÊNCIA por arquivo
        cur.execute("SELECT DISTINCT arquivo_origem FROM aux.rh_horas_extras")
        return {r[0] for r in cur.fetchall()}


def verificar_novos():
    s = _graph_session()
    arquivos = _listar_arquivos(s, _drive_id(s))
    conn = _db()
    try:
        novos = [a for a in arquivos if a["name"] not in _ja_carregados(conn)]
    finally:
        conn.close()
    print(f"Arquivos novos: {[a['name'] for a in novos]}")
    return "carregar_aux" if novos else "encerrar"            # BRANCH: processa ou encerra


def carregar_aux():
    s = _graph_session()
    drive_id = _drive_id(s)
    conn = _db()
    try:
        existentes = _ja_carregados(conn)
        with conn.cursor() as cur:
            for a in _listar_arquivos(s, drive_id):
                if a["name"] in existentes:
                    continue
                r = s.get(f"{GRAPH}/drives/{drive_id}/items/{a['id']}/content")
                r.raise_for_status()
                df = pd.read_excel(io.BytesIO(r.content))     # lê em memória, sem gravar em disco
                if len(df.columns) != len(COLUNAS):           # QUALIDADE: layout mudou?
                    print(f"AVISO: {a['name']} fora do layout; pulando.")
                    continue
                df.columns = COLUNAS
                df["arquivo_origem"] = a["name"]              # LINHAGEM: de qual arquivo veio
                cur.executemany(INSERT_SQL, list(df.itertuples(index=False, name=None)))  # insert em lote
                print(f"{a['name']}: {len(df)} linhas.")
        conn.commit()
    finally:
        conn.close()


def gerar_gold():
    conn = _db()
    try:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE gold.rh_horas_extras;")
            cur.execute("""
                INSERT INTO gold.rh_horas_extras (ano, mes, centro_custo, horas, valor)
                SELECT ano, mes, centro_custo, SUM(horas), SUM(valor)
                FROM aux.rh_horas_extras
                GROUP BY ano, mes, centro_custo;
            """)
        conn.commit()
    finally:
        conn.close()


with DAG(
    dag_id="sharepoint_rh",
    schedule="0 21 * * *",                    # todo dia às 21h
    start_date=datetime(2025, 1, 1),
    catchup=False,                            # não reprocessa o passado
    default_args={"retries": 2},              # + on_failure_callback com alerta no Teams
    tags=["sharepoint", "rh", "gold"],
) as dag:
    verificar = BranchPythonOperator(task_id="verificar_novos", python_callable=verificar_novos)
    encerrar = EmptyOperator(task_id="encerrar")
    carregar = PythonOperator(task_id="carregar_aux", python_callable=carregar_aux)
    gold = PythonOperator(task_id="gerar_gold", python_callable=gerar_gold)

    verificar >> [carregar, encerrar]         # o branch escolhe um caminho
    carregar >> gold                          # a Gold só roda se houve carga
