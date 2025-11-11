# app.py
import unicodedata
import pandas as pd
import streamlit as st

# BigQuery
from google.cloud import bigquery
from google.oauth2 import service_account

# ===================== Config =====================
st.set_page_config(page_title="Calculadora de Margem", layout="wide", page_icon="📊")

PROJECT_ID = "bi-beyoung"
DATASET    = "silver_layer"
TABLE      = "google_sheets_average_cost_by_product_branch"  # colunas: year_month, branch, sku, average_cost

SCOPES = [
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/bigquery",
]

# ===================== Utils =====================
def fmt_currency(v: float) -> str:
    try:
        return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return f"R$ {v:.2f}"

def fmt_int(n: int) -> str:
    return f"{int(n):,}".replace(",", ".")

def normalize(s: str) -> str:
    if s is None:
        return ""
    s = str(s).strip().lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.replace("\u00a0", " ")
    s = " ".join(s.split())
    return s

# ===================== Auth via st.secrets =====================
def get_bq_client_from_secrets(project_id: str) -> bigquery.Client:
    if "gcp_service_account" not in st.secrets:
        raise RuntimeError(
            "gcp_service_account não encontrado em st.secrets. "
            "Crie .streamlit/secrets.toml com a seção [gcp_service_account]."
        )
    sa_info = dict(st.secrets["gcp_service_account"])
    creds = service_account.Credentials.from_service_account_info(sa_info, scopes=SCOPES)
    return bigquery.Client(project=project_id, credentials=creds)

@st.cache_data(ttl=300)
def fetch_cost_table(client: bigquery.Client, project_id: str, dataset: str, table: str) -> pd.DataFrame:
    query = f"""
        SELECT
          CAST(year_month AS STRING) AS year_month,
          CAST(branch     AS STRING) AS branch,
          CAST(sku        AS STRING) AS sku,
          SAFE_CAST(average_cost AS FLOAT64) AS average_cost
        FROM `{project_id}.{dataset}.{table}`
        WHERE sku IS NOT NULL AND branch IS NOT NULL AND year_month IS NOT NULL
    """
    df = client.query(query).to_dataframe()
    df["year_month"] = df["year_month"].str.slice(0, 7)  # força YYYY-MM
    df = df.dropna(subset=["year_month", "branch", "sku"]).drop_duplicates().reset_index(drop=True)
    return df

# ---- Card visual ----
def big_metric(label: str, value_str: str):
    st.markdown(
        f"""
        <div style="padding:10px 12px;border-radius:12px;border:1px solid rgba(255,255,255,0.15);">
          <div style="font-size:0.85rem;opacity:0.8;margin-bottom:4px;">{label}</div>
          <div style="font-size:1.6rem;font-weight:700;line-height:1;">{value_str}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ===================== App =====================
st.title("📊 Calculadora de Margem")

tab_exist, tab_new = st.tabs(["Produto existente", "Produto novo"])

# --------- ABA 1: PRODUTO EXISTENTE (BigQuery via st.secrets) ---------
with tab_exist:
    try:
        bq = get_bq_client_from_secrets(PROJECT_ID)
        df_cost = fetch_cost_table(bq, PROJECT_ID, DATASET, TABLE)
    except Exception as e:
        df_cost = None
        st.error(f"Erro ao autenticar/carregar do BigQuery: {e}")

    if df_cost is None or df_cost.empty:
        st.warning("Tabela do BigQuery vazia ou inacessível. Verifique projeto/dataset/tabela e permissões.")
    else:
        # Seletores em cascata: Mês -> Filial -> SKU
        meses = sorted(df_cost["year_month"].unique())
        c1, c2, c3 = st.columns(3)
        with c1:
            sel_month = st.selectbox("Mês (year_month)", options=meses, index=max(len(meses)-1, 0), key="bq_mes")
        df_m = df_cost[df_cost["year_month"] == sel_month]

        with c2:
            branches = sorted(df_m["branch"].unique())
            sel_branch = st.selectbox("Filial (branch)", options=branches, key="bq_branch")
        df_mb = df_m[df_m["branch"] == sel_branch]

        with c3:
            skus = sorted(df_mb["sku"].unique())
            sel_sku = st.selectbox("SKU", options=skus, key="bq_sku")

        # Custo médio da combinação selecionada
        row = df_mb[df_mb["sku"] == sel_sku].head(1)
        custo_medio = float(row["average_cost"].iloc[0]) if not row.empty else 0.0

        # Input de preço e cálculo
        preco = st.number_input("Preço de venda (R$)", min_value=0.0, step=1.0, format="%.2f", key="preco_existente")
        st.text_input("Custo médio (R$) — BigQuery", value=f"{custo_medio:.2f}", disabled=True, key="custo_existente")

        lucro = max(preco - custo_medio, 0.0)
        margem = (lucro / preco * 100.0) if preco > 0 else 0.0

        m1, m2 = st.columns(2)
        with m1: big_metric("Lucro bruto", fmt_currency(lucro))
        with m2: big_metric("Margem bruta", f"{margem:.2f}%")

# --------- ABA 2: PRODUTO NOVO (como já estava) ---------
with tab_new:
    st.caption("Preço, desconto (R$/%), impostos por região, custos, quantidade e split SP/ES.")

    # Entradas básicas
    preco_novo = st.number_input("Preço de venda (R$)", min_value=0.0, step=1.0, format="%.2f", key="preco_novo")

    col_custos = st.columns(2)
    with col_custos[0]:
        custo_sp = st.number_input("Custo SP (R$)", min_value=0.0, step=1.0, format="%.2f", key="custo_sp")
    with col_custos[1]:
        custo_es = st.number_input("Custo ES (R$)", min_value=0.0, step=1.0, format="%.2f", key="custo_es")

    # Desconto (tipo + valor)
    col_desc = st.columns(2)
    with col_desc[0]:
        desc_tipo = st.radio("Tipo de desconto", options=["%", "R$"], horizontal=True, key="desc_tipo")
    with col_desc[1]:
        desc_valor = st.number_input(f"Desconto ({desc_tipo})", min_value=0.0, step=0.5, format="%.2f", key="desc_valor")

    # Quantidade e split
    qtd_vendas = st.number_input("Quantidade de Vendas (un.)", min_value=0, step=1, value=0, key="qtd_vendas")
    pct_sp = st.number_input("% SP", min_value=0.0, max_value=100.0, step=1.0, value=50.0, format="%.2f", key="pct_sp")
    pct_es = st.number_input("% ES", min_value=0.0, max_value=100.0, step=1.0, value=50.0, format="%.2f", key="pct_es")

    # Impostos
    col_imp = st.columns(2)
    with col_imp[0]:
        imposto_sp_pct = st.number_input("Imposto SP (%)", min_value=0.0, max_value=100.0, step=0.5, value=0.0, format="%.2f", key="imp_sp")
    with col_imp[1]:
        imposto_es_pct = st.number_input("Imposto ES (%)", min_value=0.0, max_value=100.0, step=0.5, value=0.0, format="%.2f", key="imp_es")

    # Split normalizado
    total_pct = pct_sp + pct_es
    if total_pct == 0:
        st.warning("Percentuais somam 0%. Usando 50% / 50%.")
        w_sp, w_es = 0.5, 0.5
    else:
        w_sp = pct_sp / total_pct
        w_es = pct_es / total_pct

    un_sp = int(round(qtd_vendas * w_sp))
    un_es = int(qtd_vendas - un_sp)

    # Preço líquido após desconto
    if desc_tipo == "%":
        preco_liq = preco_novo * (1 - desc_valor / 100.0)
    else:
        preco_liq = max(preco_novo - desc_valor, 0.0)

    # Cálculos regionais
    receita_sp = preco_liq * un_sp
    receita_es = preco_liq * un_es

    imp_sp_val = receita_sp * (imposto_sp_pct / 100.0)
    imp_es_val = receita_es * (imposto_es_pct / 100.0)

    custo_sp_total = custo_sp * un_sp
    custo_es_total = custo_es * un_es

    lucro_sp = receita_sp - imp_sp_val - custo_sp_total
    lucro_es = receita_es - imp_es_val - custo_es_total

    margem_sp = (lucro_sp / receita_sp * 100.0) if receita_sp > 0 else 0.0
    margem_es = (lucro_es / receita_es * 100.0) if receita_es > 0 else 0.0

    # Totais (com Receita Líquida e Lucro Bruto)
    faturamento = preco_novo * (un_sp + un_es)
    descontos_totais = max(preco_novo - preco_liq, 0.0) * (un_sp + un_es)
    receita_total = receita_sp + receita_es
    imp_total = imp_sp_val + imp_es_val
    receita_liquida = faturamento - descontos_totais - imp_total
    custo_total = custo_sp_total + custo_es_total
    lucro_bruto_total = receita_liquida - custo_total
    margem_total = (lucro_bruto_total / receita_liquida * 100.0) if receita_liquida > 0 else 0.0

    # Tabela por região
    st.markdown("---")
    st.subheader("📊 Resultados por Região")
    df_reg = pd.DataFrame([
        {"Região": "SP", "Valor de venda": preco_novo, "Valor após os descontos": preco_liq,
         "Quantidade de unidades vendidas": un_sp, "Receita": receita_sp, "Impostos": imp_sp_val,
         "Custos": custo_sp_total, "Lucro": lucro_sp, "Margem": margem_sp},
        {"Região": "ES", "Valor de venda": preco_novo, "Valor após os descontos": preco_liq,
         "Quantidade de unidades vendidas": un_es, "Receita": receita_es, "Impostos": imp_es_val,
         "Custos": custo_es_total, "Lucro": lucro_es, "Margem": margem_es},
    ])
    st.dataframe(
        df_reg.style.format({
            "Valor de venda": fmt_currency,
            "Valor após os descontos": fmt_currency,
            "Quantidade de unidades vendidas": lambda v: fmt_int(v),
            "Receita": fmt_currency, "Impostos": fmt_currency, "Custos": fmt_currency,
            "Lucro": fmt_currency, "Margem": lambda v: f"{v:.2f}%"
        }),
        width="stretch", hide_index=True
    )

    # Totais
    st.markdown("---")
    st.subheader("🧮 Totais")
    t1, t2, t3, t4, t5, t6, t7 = st.columns(7)
    with t1: big_metric("Unidades", fmt_int(un_sp + un_es))
    with t2: big_metric("Faturamento", fmt_currency(faturamento))
    with t3: big_metric("Impostos totais", fmt_currency(imp_total))
    with t4: big_metric("Receita Líquida", fmt_currency(receita_liquida))
    with t5: big_metric("( - ) CMV", fmt_currency(custo_total))
    with t6: big_metric("Lucro Bruto", fmt_currency(lucro_bruto_total))
    with t7: big_metric("Margem Bruta", f"{margem_total:.2f}%")
