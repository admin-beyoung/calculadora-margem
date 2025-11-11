# app.py
import streamlit as st
import pandas as pd
import unicodedata

# ================= Config =================
st.set_page_config(page_title="Calculadora de Margem", layout="wide", page_icon="📊")

# ================= CSS (espaços + alinhamento dos inputs) =================
st.markdown("""
<style>
/* inputs com menos espaço vertical entre label e campo */
.stRadio > label, .stNumberInput > label, .stTextInput > label { margin-bottom: 0.25rem !important; }
.block-container { padding-top: 1.25rem; padding-bottom: 2rem; }

/* radios mais juntinhos */
div[role="radiogroup"] { gap: 0.25rem !important; }

/* alinhar o valor do input com o texto do label (inclui Desconto) */
div[data-baseweb="input"] > div:first-child { padding-left: 0.35rem !important; }
</style>
""", unsafe_allow_html=True)

# Planilha pública (Produto existente)
SHEET_ID = "19-evG-LmVdYxHXNgaeAzAOk3DNzX5G8znqcIdQwgni0"
SHEET_NAME = None  # None => primeira aba; use "HARDINPUT" p/ forçar

# ================= Utils =================
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

@st.cache_data(ttl=300)
def fetch_sheet_public(sheet_id: str, sheet_name: str | None = None) -> pd.DataFrame:
    url = (
        f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
        if sheet_name else
        f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv"
    )
    df = pd.read_csv(url, dtype=str)
    df.columns = [normalize(c) for c in df.columns]
    return df

def parse_money_ptbr(x: str) -> float:
    if x is None:
        return 0.0
    s = str(x)
    s = s.replace(".", "").replace(",", ".")
    s = "".join(ch for ch in s if (ch.isdigit() or ch in ".-"))
    try:
        return float(s)
    except:
        return 0.0

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

# ================= App =================
st.title("📊 Calculadora de Margem")

tab_exist, tab_new = st.tabs(["Produto existente", "Produto novo"])

# --------- ABA 1: PRODUTO EXISTENTE ---------
with tab_exist:
    try:
        df = fetch_sheet_public(SHEET_ID, SHEET_NAME)
    except Exception as e:
        df = None
        st.error(f"Erro ao carregar planilha pública: {e}")

    if df is None or df.empty:
        st.warning("Planilha vazia ou inacessível.")
    else:
        st.caption("Fonte: Google Sheets")

        # Detecta colunas
        candidates_prod   = ["produto", "produto_nome", "nome", "sku", "codigo", "código", "item"]
        candidates_cost   = ["custo", "custo medio", "custo médio", "custo unitario",
                             "custo unitário", "average_cost", "preco_custo", "preço de custo"]
        candidates_branch = ["branch", "filial"]

        col_prod   = next((c for c in candidates_prod if c in df.columns), None)
        col_cost   = next((c for c in candidates_cost if c in df.columns), None)
        col_branch = next((c for c in candidates_branch if c in df.columns), None)

        if not col_prod or not col_cost:
            st.warning(f"Não encontrei colunas de produto/custo. Colunas: {list(df.columns)}")
        else:
            produtos = (
                df[col_prod].astype(str).str.strip()
                .replace({"": None}).dropna().drop_duplicates().tolist()
            )

            # ===== BLOCO: Produto =====
            st.markdown("#### Produto")
            produto_sel = st.selectbox("Produto (digite para buscar)", options=produtos, key="produto_existente")

            # Busca custos por branch
            df_prod = df[df[col_prod] == produto_sel].copy()
            custo_sp_val = None
            custo_es_val = None
            if col_branch and not df_prod.empty:
                row_sp = df_prod[df_prod[col_branch].astype(str) == "VP-01"]
                if not row_sp.empty:
                    custo_sp_val = parse_money_ptbr(str(row_sp[col_cost].iloc[0]))
                row_es = df_prod[df_prod[col_branch].astype(str) == "VP-06"]
                if not row_es.empty:
                    custo_es_val = parse_money_ptbr(str(row_es[col_cost].iloc[0]))

            # ===== Linha 1: Preço | Quantidade | Tipo de desconto + Desconto (colados)
            col_l1_c1, col_l1_c2, col_l1_c3 = st.columns([1, 1, 1])
            with col_l1_c1:
                preco_exist = st.number_input("Preço de venda (R$)", min_value=0.0, step=1.0,
                                              format="%.2f", key="preco_existente_val")
            with col_l1_c2:
                qtd_vendas_exist = st.number_input("Quantidade de vendas (un.)", min_value=0, step=1, value=0,
                                                   key="qtd_exist")
            with col_l1_c3:
                st.markdown("**Tipo de desconto &nbsp;&nbsp;&nbsp;&nbsp; Desconto**", unsafe_allow_html=True)
                c31, c32 = st.columns([0.2, 0.8], gap="small")
                with c31:
                    desc_tipo_exist = st.radio(
                        "", options=["%", "R$"], horizontal=True,
                        label_visibility="collapsed", key="desc_tipo_exist"
                    )
                with c32:
                    desc_valor_exist = st.number_input(
                        "", min_value=0.0, step=0.5, format="%.2f",
                        label_visibility="collapsed", key="desc_valor_exist"
                    )

            # ===== Linha 2: Custo SP | %SP | Imposto SP
            col_l2_c1, col_l2_c2, col_l2_c3 = st.columns([1, 1, 1])
            with col_l2_c1:
                st.text_input("Custo São Paulo (VP-01)",
                              value=("—" if custo_sp_val is None else f"{custo_sp_val:.2f}"),
                              disabled=True, key="custo_sp_ro")
            with col_l2_c2:
                pct_sp_exist = st.number_input("% SP", min_value=0.0, max_value=100.0,
                                               value=50.0, step=1.0, format="%.2f", key="pct_sp_exist")
            with col_l2_c3:
                imposto_sp_pct_exist = st.number_input("Imposto SP (%)", min_value=0.0, max_value=100.0,
                                                       value=0.0, step=0.5, format="%.2f", key="imp_sp_exist")

            # ===== Linha 3: Custo ES | %ES | Imposto ES
            col_l3_c1, col_l3_c2, col_l3_c3 = st.columns([1, 1, 1])
            with col_l3_c1:
                st.text_input("Custo Espírito Santo (VP-06)",
                              value=("—" if custo_es_val is None else f"{custo_es_val:.2f}"),
                              disabled=True, key="custo_es_ro")
            with col_l3_c2:
                pct_es_exist = st.number_input("% ES", min_value=0.0, max_value=100.0,
                                               value=50.0, step=1.0, format="%.2f", key="pct_es_exist")
            with col_l3_c3:
                imposto_es_pct_exist = st.number_input("Imposto ES (%)", min_value=0.0, max_value=100.0,
                                                       value=0.0, step=0.5, format="%.2f", key="imp_es_exist")

            st.markdown("---")

            # ======= Cálculo
            if desc_tipo_exist == "%":
                preco_liq_exist = preco_exist * (1 - desc_valor_exist / 100.0)
            else:
                preco_liq_exist = max(preco_exist - desc_valor_exist, 0.0)

            soma_pct = pct_sp_exist + pct_es_exist
            if soma_pct == 0:
                w_sp, w_es = 0.5, 0.5
                st.warning("Percentuais somam 0%. Usando 50%/50%.")
            else:
                w_sp = pct_sp_exist / soma_pct
                w_es = pct_es_exist / soma_pct

            un_sp = int(round(qtd_vendas_exist * w_sp))
            un_es = int(qtd_vendas_exist - un_sp)

            custo_sp_unit = custo_sp_val or 0.0
            custo_es_unit = custo_es_val or 0.0

            receita_sp = preco_liq_exist * un_sp
            receita_es = preco_liq_exist * un_es
            imp_sp_val = receita_sp * (imposto_sp_pct_exist / 100.0)
            imp_es_val = receita_es * (imposto_es_pct_exist / 100.0)
            custo_sp_total = custo_sp_unit * un_sp
            custo_es_total = custo_es_unit * un_es
            lucro_sp = receita_sp - imp_sp_val - custo_sp_total
            lucro_es = receita_es - imp_es_val - custo_es_total
            margem_sp = (lucro_sp / receita_sp * 100.0) if receita_sp > 0 else 0.0
            margem_es = (lucro_es / receita_es * 100.0) if receita_es > 0 else 0.0

            faturamento = preco_exist * (un_sp + un_es)
            descontos_totais = (preco_exist - preco_liq_exist) * (un_sp + un_es)
            imp_total = imp_sp_val + imp_es_val
            receita_liquida = faturamento - descontos_totais - imp_total
            custo_total = custo_sp_total + custo_es_total
            lucro_bruto_total = receita_liquida - custo_total
            margem_total = (lucro_bruto_total / receita_liquida * 100.0) if receita_liquida > 0 else 0.0

            # ======= Resultados por Região (TABELA)
            st.subheader("📊 Resultados por Região")
            df_reg_exist = pd.DataFrame([
                {"Região": "SP", "Valor de venda": preco_exist, "Valor após os descontos": preco_liq_exist,
                 "Quantidade de unidades vendidas": un_sp, "Receita": receita_sp, "Impostos": imp_sp_val,
                 "Custos": custo_sp_total, "Lucro": lucro_sp, "Margem": margem_sp},
                {"Região": "ES", "Valor de venda": preco_exist, "Valor após os descontos": preco_liq_exist,
                 "Quantidade de unidades vendidas": un_es, "Receita": receita_es, "Impostos": imp_es_val,
                 "Custos": custo_es_total, "Lucro": lucro_es, "Margem": margem_es},
            ])
            st.dataframe(
                df_reg_exist.style.format({
                    "Valor de venda": fmt_currency,
                    "Valor após os descontos": fmt_currency,
                    "Quantidade de unidades vendidas": lambda v: fmt_int(v),
                    "Receita": fmt_currency, "Impostos": fmt_currency,
                    "Custos": fmt_currency, "Lucro": fmt_currency,
                    "Margem": lambda v: f"{v:.2f}%"
                }),
                width="stretch", hide_index=True
            )

            # ======= Totais
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

# --------- ABA 2: PRODUTO NOVO ---------
with tab_new:
    # ===== BLOCO: Produto =====
    st.markdown("#### Produto")
    nome_produto = st.text_input("Nome do produto", placeholder="Ex.: Sérum X 30ml")

    # ===== Linha 1: Preço | Quantidade | Tipo de desconto + Desconto (colados)
    col2_l1_c1, col2_l1_c2, col2_l1_c3 = st.columns([1, 1, 1])
    with col2_l1_c1:
        preco_novo = st.number_input("Preço de venda (R$)", min_value=0.0, step=1.0, format="%.2f")
    with col2_l1_c2:
        qtd_vendas = st.number_input("Quantidade de vendas (un.)", min_value=0, step=1, value=0)
    with col2_l1_c3:
        st.markdown("**Tipo de desconto &nbsp;&nbsp;&nbsp;&nbsp; Desconto**", unsafe_allow_html=True)
        c31, c32 = st.columns([0.2, 0.8], gap="small")
        with c31:
            desc_tipo = st.radio("", options=["%", "R$"], horizontal=True, label_visibility="collapsed")
        with c32:
            desc_valor = st.number_input("", min_value=0.0, step=0.5, format="%.2f",
                                         label_visibility="collapsed")

    # ===== Linha 2: Custo SP | %SP | Imposto SP
    col2_l2_c1, col2_l2_c2, col2_l2_c3 = st.columns([1, 1, 1])
    with col2_l2_c1:
        custo_sp = st.number_input("Custo São Paulo (R$)", min_value=0.0, step=1.0, format="%.2f")
    with col2_l2_c2:
        pct_sp = st.number_input("% SP", min_value=0.0, max_value=100.0, value=50.0, step=1.0, format="%.2f")
    with col2_l2_c3:
        imposto_sp_pct = st.number_input("Imposto SP (%)", min_value=0.0, max_value=100.0,
                                         value=0.0, step=0.5, format="%.2f")

    # ===== Linha 3: Custo ES | %ES | Imposto ES
    col2_l3_c1, col2_l3_c2, col2_l3_c3 = st.columns([1, 1, 1])
    with col2_l3_c1:
        custo_es = st.number_input("Custo Espírito Santo (R$)", min_value=0.0, step=1.0, format="%.2f")
    with col2_l3_c2:
        pct_es = st.number_input("% ES", min_value=0.0, max_value=100.0, value=50.0, step=1.0, format="%.2f")
    with col2_l3_c3:
        imposto_es_pct = st.number_input("Imposto ES (%)", min_value=0.0, max_value=100.0,
                                         value=0.0, step=0.5, format="%.2f")

    st.markdown("---")

    # ======= Cálculo
    if desc_tipo == "%":
        preco_liq = preco_novo * (1 - desc_valor / 100.0)
    else:
        preco_liq = max(preco_novo - desc_valor, 0.0)

    soma_pct2 = pct_sp + pct_es
    if soma_pct2 == 0:
        w_sp2, w_es2 = 0.5, 0.5
        st.warning("Percentuais somam 0%. Usando 50%/50%.")
    else:
        w_sp2 = pct_sp / soma_pct2
        w_es2 = pct_es / soma_pct2

    un_sp2 = int(round(qtd_vendas * w_sp2))
    un_es2 = int(qtd_vendas - un_sp2)

    receita_sp2 = preco_liq * un_sp2
    receita_es2 = preco_liq * un_es2
    imp_sp_val2 = receita_sp2 * (imposto_sp_pct / 100.0)
    imp_es_val2 = receita_es2 * (imposto_es_pct / 100.0)
    custo_sp_total2 = custo_sp * un_sp2
    custo_es_total2 = custo_es * un_es2
    lucro_sp2 = receita_sp2 - imp_sp_val2 - custo_sp_total2
    lucro_es2 = receita_es2 - imp_es_val2 - custo_es_total2
    margem_sp2 = (lucro_sp2 / receita_sp2 * 100.0) if receita_sp2 > 0 else 0.0
    margem_es2 = (lucro_es2 / receita_es2 * 100.0) if receita_es2 > 0 else 0.0

    faturamento2 = preco_novo * (un_sp2 + un_es2)
    descontos_totais2 = (preco_novo - preco_liq) * (un_sp2 + un_es2)
    imp_total2 = imp_sp_val2 + imp_es_val2
    receita_liquida2 = faturamento2 - descontos_totais2 - imp_total2
    custo_total2 = custo_sp_total2 + custo_es_total2
    lucro_bruto2 = receita_liquida2 - custo_total2
    margem_total2 = (lucro_bruto2 / receita_liquida2 * 100.0) if receita_liquida2 > 0 else 0.0

    # ======= Resultados por Região (TABELA)
    st.subheader("📊 Resultados por Região")
    df_reg2 = pd.DataFrame([
        {"Região": "SP", "Valor de venda": preco_novo, "Valor após os descontos": preco_liq,
         "Quantidade de unidades vendidas": un_sp2, "Receita": receita_sp2, "Impostos": imp_sp_val2,
         "Custos": custo_sp_total2, "Lucro": lucro_sp2, "Margem": margem_sp2},
        {"Região": "ES", "Valor de venda": preco_novo, "Valor após os descontos": preco_liq,
         "Quantidade de unidades vendidas": un_es2, "Receita": receita_es2, "Impostos": imp_es_val2,
         "Custos": custo_es_total2, "Lucro": lucro_es2, "Margem": margem_es2},
    ])
    st.dataframe(
        df_reg2.style.format({
            "Valor de venda": fmt_currency,
            "Valor após os descontos": fmt_currency,
            "Quantidade de unidades vendidas": lambda v: fmt_int(v),
            "Receita": fmt_currency, "Impostos": fmt_currency,
            "Custos": fmt_currency, "Lucro": fmt_currency,
            "Margem": lambda v: f"{v:.2f}%"
        }),
        width="stretch", hide_index=True
    )

    # ======= Totais
    st.markdown("---")
    st.subheader("🧮 Totais")
    t1, t2, t3, t4, t5, t6, t7 = st.columns(7)
    with t1: big_metric("Unidades", fmt_int(un_sp2 + un_es2))
    with t2: big_metric("Faturamento", fmt_currency(faturamento2))
    with t3: big_metric("Impostos totais", fmt_currency(imp_total2))
    with t4: big_metric("Receita Líquida", fmt_currency(receita_liquida2))
    with t5: big_metric("( - ) CMV", fmt_currency(custo_total2))
    with t6: big_metric("Lucro Bruto", fmt_currency(lucro_bruto2))
    with t7: big_metric("Margem Bruta", f"{margem_total2:.2f}%")
