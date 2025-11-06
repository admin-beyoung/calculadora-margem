# app.py
import streamlit as st
import pandas as pd
import unicodedata

# =============== Config ===============
st.set_page_config(page_title="Calculadora de Margem", layout="wide", page_icon="📊")

SHEET_ID = "1C_rUy26WhRnx4XDoYHhV-PNCNHFOPyU5ZHnl2pQ_LXU"
SHEET_NAME = None  # usa a primeira aba da planilha pública

# =============== Utils ===============
def fmt_currency(v: float) -> str:
    """Formata número para R$ (pt-BR) com milhar."""
    try:
        return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return f"R$ {v:.2f}"

def fmt_int(n: int) -> str:
    """Inteiro com separador de milhar pt-BR."""
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

@st.cache_data(ttl=300)
def fetch_sheet_products(sheet_id: str, sheet_name: str | None = None) -> pd.DataFrame:
    """Lê planilha pública via CSV export e retorna colunas produto / custo_medio."""
    url = (f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
           if sheet_name else f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv")
    df = pd.read_csv(url, dtype=str)

    df.columns = [normalize(c) for c in df.columns]
    col_prod = "produto" if "produto" in df.columns else df.columns[0]
    candidatos = ["custo medio", "custo médio", "custo", "custo unitario", "custo unitário"]
    col_custo = next((c for c in candidatos if c in df.columns), df.columns[1] if len(df.columns) > 1 else df.columns[0])

    out = df[[col_prod, col_custo]].copy()
    out.columns = ["produto", "custo_medio_raw"]
    out["produto_key"] = out["produto"].map(normalize)

    cm = (out["custo_medio_raw"].astype(str)
          .str.replace(".", "", regex=False)
          .str.replace(",", ".", regex=False))
    out["custo_medio"] = pd.to_numeric(cm, errors="coerce").fillna(0.0)

    out = out.dropna(subset=["produto_key"]).drop_duplicates(subset=["produto_key"], keep="first").reset_index(drop=True)
    return out[["produto", "produto_key", "custo_medio"]]

# ---- Card visual para números grandes (não trunca) ----
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

# =============== App ===============
st.title("📊 Calculadora de Margem")

tab_exist, tab_new = st.tabs(["Produto existente", "Produto novo"])

# --------- ABA 1: PRODUTO EXISTENTE ---------
with tab_exist:
    try:
        df = fetch_sheet_products(SHEET_ID, SHEET_NAME)
    except Exception as e:
        df = None
        st.error(f"Não foi possível carregar a planilha pública: {e}")

    if df is None or df.empty:
        st.warning("Planilha vazia ou inacessível.")
    else:
        produtos = df["produto"].tolist()
        produto_sel = st.selectbox("Produto (da planilha)", options=produtos, key="produto_existente")

        custo_medio = float(
            df.loc[df["produto"] == produto_sel, "custo_medio"].iloc[0]
        )

        preco = st.number_input("Preço de venda (R$)", min_value=0.0, step=1.0, format="%.2f", key="preco_existente")
        st.text_input("Custo médio (R$)", value=f"{custo_medio:.2f}", disabled=True, key="custo_existente")

        lucro = max(preco - custo_medio, 0.0)
        margem = (lucro / preco * 100.0) if preco > 0 else 0.0

        c1, c2 = st.columns(2)
        with c1:
            big_metric("Lucro bruto", fmt_currency(lucro))
        with c2:
            st.metric("Margem bruta", f"{margem:.2f}%")

# --------- ABA 2: PRODUTO NOVO ---------
with tab_new:
    st.caption("Preço, desconto (R$/%), impostos por região, custos, quantidade e split SP/ES.")

    # === Entradas básicas ===
    preco_novo = st.number_input("Preço de venda (R$)", min_value=0.0, step=1.0, format="%.2f", key="preco_novo")

    col_custos = st.columns(2)
    with col_custos[0]:
        custo_sp = st.number_input("Custo SP (R$)", min_value=0.0, step=1.0, format="%.2f", key="custo_sp")
    with col_custos[1]:
        custo_es = st.number_input("Custo ES (R$)", min_value=0.0, step=1.0, format="%.2f", key="custo_es")

    # === Desconto (tipo + valor) ===
    col_desc = st.columns(2)
    with col_desc[0]:
        desc_tipo = st.radio("Tipo de desconto", options=["%", "R$"], horizontal=True, key="desc_tipo")
    with col_desc[1]:
        desc_valor = st.number_input(f"Desconto ({desc_tipo})", min_value=0.0, step=0.5, format="%.2f", key="desc_valor")

    # === Quantidade e split ===
    qtd_vendas = st.number_input("Quantidade de Vendas (un.)", min_value=0, step=1, value=0, key="qtd_vendas")
    pct_sp = st.number_input("% SP", min_value=0.0, max_value=100.0, step=1.0, value=50.0, format="%.2f", key="pct_sp")
    pct_es = st.number_input("% ES", min_value=0.0, max_value=100.0, step=1.0, value=50.0, format="%.2f", key="pct_es")

    # === Impostos ===
    col_imp = st.columns(2)
    with col_imp[0]:
        imposto_sp_pct = st.number_input("Imposto SP (%)", min_value=0.0, max_value=100.0, step=0.5, value=0.0, format="%.2f", key="imp_sp")
    with col_imp[1]:
        imposto_es_pct = st.number_input("Imposto ES (%)", min_value=0.0, max_value=100.0, step=0.5, value=0.0, format="%.2f", key="imp_es")

    # === Normalização de split ===
    total_pct = pct_sp + pct_es
    if total_pct == 0:
        st.warning("Percentuais somam 0%. Usando 50% / 50%.")
        w_sp, w_es = 0.5, 0.5
    else:
        w_sp = pct_sp / total_pct
        w_es = pct_es / total_pct

    un_sp = int(round(qtd_vendas * w_sp))
    un_es = int(qtd_vendas - un_sp)

    # === Aplicação do desconto ===
    if desc_tipo == "%":
        preco_liq = preco_novo * (1 - desc_valor / 100.0)
    else:
        preco_liq = max(preco_novo - desc_valor, 0.0)

    # === Cálculos regionais ===
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

    # ===== Totais (agora com Receita Líquida e Lucro Bruto) =====
    faturamento = preco_novo * (un_sp + un_es)  # preço cheio x unidades totais
    descontos_totais = max(preco_novo - preco_liq, 0.0) * (un_sp + un_es)
    receita_total = receita_sp + receita_es                    # receita após descontos
    imp_total = imp_sp_val + imp_es_val
    receita_liquida = faturamento - descontos_totais - imp_total
    custo_total = custo_sp_total + custo_es_total              # ( - ) CMV
    lucro_bruto_total = receita_liquida - custo_total
    margem_total = (lucro_bruto_total / receita_liquida * 100.0) if receita_liquida > 0 else 0.0

    # ======= Resultados por Região (TABELA) =======
    st.markdown("---")
    st.subheader("📊 Resultados por Região")

    df_reg = pd.DataFrame([
        {
            "Região": "SP",
            "Valor de venda": preco_novo,
            "Valor após os descontos": preco_liq,
            "Quantidade de unidades vendidas": un_sp,
            "Receita": receita_sp,
            "Impostos": imp_sp_val,
            "Custos": custo_sp_total,
            "Lucro": lucro_sp,
            "Margem": margem_sp,
        },
        {
            "Região": "ES",
            "Valor de venda": preco_novo,
            "Valor após os descontos": preco_liq,
            "Quantidade de unidades vendidas": un_es,
            "Receita": receita_es,
            "Impostos": imp_es_val,
            "Custos": custo_es_total,
            "Lucro": lucro_es,
            "Margem": margem_es,
        },
    ])

    st.dataframe(
        df_reg.style.format({
            "Valor de venda": fmt_currency,
            "Valor após os descontos": fmt_currency,
            "Quantidade de unidades vendidas": lambda v: fmt_int(v),
            "Receita": fmt_currency,
            "Impostos": fmt_currency,
            "Custos": fmt_currency,
            "Lucro": fmt_currency,
            "Margem": lambda v: f"{v:.2f}%"
        }),
        width="stretch",
        hide_index=True
    )

    # ======= Totais =======
    st.markdown("---")
    st.subheader("🧮 Totais")
    t1, t2, t3, t4, t5, t6, t7 = st.columns(7)
    with t1:
        big_metric("Unidades", fmt_int(un_sp + un_es))
    with t2:
        big_metric("Faturamento", fmt_currency(faturamento))
    with t3:
        big_metric("Impostos totais", fmt_currency(imp_total))
    with t4:
        big_metric("Receita Líquida", fmt_currency(receita_liquida))
    with t5:
        big_metric("( - ) CMV", fmt_currency(custo_total))
    with t6:
        big_metric("Lucro Bruto", fmt_currency(lucro_bruto_total))
    with t7:
        big_metric("Margem Bruta", f"{margem_total:.2f}%")
