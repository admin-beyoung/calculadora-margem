# app.py
import streamlit as st
import pandas as pd
import unicodedata

# ================= Config =================
st.set_page_config(page_title="Calculadora de Margem", layout="wide", page_icon="📊")

# Planilha pública
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

def parse_number_loose(x: str) -> float:
    """
    Interpreta valores em en-US (1234.56) ou pt-BR (1.234,56) e com/sem 'R$'.
    """
    if x is None:
        return 0.0
    s = str(x).strip().replace("R$", "").replace("\u00a0", "").replace(" ", "")
    try:
        return float(s)
    except:
        return parse_money_ptbr(s)

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
        candidates_prod  = ["produto", "produto_nome", "nome", "sku", "codigo", "código", "item"]
        candidates_cost  = ["custo", "custo medio", "custo médio", "custo unitario",
                            "custo unitário", "average_cost", "average cost",
                            "preco_custo", "preço de custo"]
        candidates_branch = ["branch", "filial"]
        candidates_prod_name = [  # <---- NOVO BLOCO
            "product_name",
            "product name",
            "nome_produto",
            "nome produto",
            "descricao",
            "descrição",
        ]

        col_prod       = next((c for c in candidates_prod if c in df.columns), None)
        col_cost       = next((c for c in candidates_cost if c in df.columns), None)
        col_branch     = next((c for c in candidates_branch if c in df.columns), None)
        col_avg_price  = "average_price" if "average_price" in df.columns else None
        col_prod_name  = next((c for c in candidates_prod_name if c in df.columns), None)  # <---- ALTERADO

        if not col_prod or not col_cost:
            st.warning(f"Não encontrei colunas de produto/custo. Colunas: {list(df.columns)}")
        else:
            # Select de produto (com busca ao digitar)
            produtos = (
                df[col_prod].astype(str).str.strip()
                .replace({"": None}).dropna().drop_duplicates().tolist()
            )
            produto_sel = st.selectbox("Produto (digite para buscar)", options=produtos, key="produto_existente")

            # Subconjunto do produto
            df_prod = df[df[col_prod].astype(str).str.strip() == str(produto_sel).strip()].copy()

            # ===== Nome do produto vindo da planilha (product_name ou similares) =====
            nome_produto_planilha = ""
            if col_prod_name and not df_prod.empty:
                serie_nome = (
                    df_prod[col_prod_name].astype(str)
                    .str.strip()
                    .replace({"": None, "nan": None})
                    .dropna()
                )
                if not serie_nome.empty:
                    nome_produto_planilha = serie_nome.iloc[0]

            st.text_input(
                "Nome do produto (planilha)",
                value=nome_produto_planilha,
                disabled=True
            )
            # ============================================================

            # Captura custos por branch: SP (VP-01) e ES (VP-06)
            custo_sp_val = None
            custo_es_val = None
            row_sp = None
            row_es = None
            if col_branch and not df_prod.empty:
                branch_series = df_prod[col_branch].astype(str).str.strip().str.upper()
                row_sp = df_prod[branch_series == "VP-01"]
                row_es = df_prod[branch_series == "VP-06"]

                if not row_sp.empty:
                    custo_sp_val = parse_money_ptbr(str(row_sp[col_cost].iloc[0]))
                if not row_es.empty:
                    custo_es_val = parse_money_ptbr(str(row_es[col_cost].iloc[0]))

            # ===== Preço de venda: somente da planilha (average_price da VP-01) =====
            preco_exist_default = 0.0
            if col_avg_price and not df_prod.empty:
                # tenta primeiro pegar o average_price da VP-01 (igual ao custo)
                serie_preco_sp = pd.Series(dtype=str)
                if row_sp is not None and not row_sp.empty:
                    serie_preco_sp = (
                        row_sp[col_avg_price].astype(str)
                        .str.strip()
                        .replace({"": None, "nan": None})
                        .dropna()
                    )
                if not serie_preco_sp.empty:
                    preco_exist_default = parse_number_loose(serie_preco_sp.iloc[0]) or 0.0
                else:
                    # fallback: qualquer average_price do produto
                    serie_preco = (
                        df_prod[col_avg_price].astype(str)
                        .str.strip()
                        .replace({"": None, "nan": None})
                        .dropna()
                    )
                    if not serie_preco.empty:
                        preco_exist_default = parse_number_loose(serie_preco.iloc[0]) or 0.0

            # Exibe o preço de venda como TEXTO somente leitura (sempre atualiza)
            st.text_input(
                "Preço de venda (R$)",
                value=f"{preco_exist_default:.2f}",
                disabled=True
            )
            # Valor efetivo usado nos cálculos
            preco_exist = float(preco_exist_default)
            # ===============================================================

            # Campos imutáveis com os custos encontrados
            csp, ces = st.columns(2)
            with csp:
                st.text_input("Custo São Paulo (VP-01)",
                              value=("—" if custo_sp_val is None else f"{custo_sp_val:.2f}"),
                              disabled=True)
            with ces:
                st.text_input("Custo Espírito Santo (VP-06)",
                              value=("—" if custo_es_val is None else f"{custo_es_val:.2f}"),
                              disabled=True)

            # ===== Entradas (COM desconto, igual à aba 2) =====
            col_desc_exist = st.columns(2)
            with col_desc_exist[0]:
                desc_tipo_exist = st.radio("Tipo de desconto", options=["%", "R$"], horizontal=True, key="desc_tipo_exist")
            with col_desc_exist[1]:
                desc_valor_exist = st.number_input(f"Desconto ({desc_tipo_exist})", min_value=0.0, step=0.5,
                                                   format="%.2f", key="desc_valor_exist")

            # Distribuição e impostos
            qtd_vendas_exist = st.number_input("Quantidade de Vendas (un.)", min_value=0, step=1, value=0,
                                               key="qtd_exist")
            pct_sp_exist = st.number_input("% SP", min_value=0.0, max_value=100.0, step=1.0, value=50.0,
                                           format="%.2f", key="pct_sp_exist")
            pct_es_exist = st.number_input("% ES", min_value=0.0, max_value=100.0, step=1.0, value=50.0,
                                           format="%.2f", key="pct_es_exist")

            col_imp_exist = st.columns(2)
            with col_imp_exist[0]:
                imposto_sp_pct_exist = st.number_input("Imposto SP (%)", min_value=0.0, max_value=100.0,
                                                       step=0.5, value=0.0, format="%.2f", key="imp_sp_exist")
            with col_imp_exist[1]:
                imposto_es_pct_exist = st.number_input("Imposto ES (%)", min_value=0.0, max_value=100.0,
                                                       step=0.5, value=0.0, format="%.2f", key="imp_es_exist")

            # Split normalizado
            total_pct_exist = pct_sp_exist + pct_es_exist
            if total_pct_exist == 0:
                w_sp, w_es = 0.5, 0.5
                st.warning("Percentuais somam 0%. Usando 50%/50%.")
            else:
                w_sp = pct_sp_exist / total_pct_exist
                w_es = pct_es_exist / total_pct_exist

            un_sp = int(round(qtd_vendas_exist * w_sp))
            un_es = int(qtd_vendas_exist - un_sp)

            # Preço líquido COM desconto
            if desc_tipo_exist == "%":
                preco_liq = preco_exist * (1 - desc_valor_exist / 100.0)
            else:
                preco_liq = max(preco_exist - desc_valor_exist, 0.0)

            # Cálculos regionais
            receita_sp = preco_liq * un_sp
            receita_es = preco_liq * un_es

            imp_sp_val = receita_sp * (imposto_sp_pct_exist / 100.0)
            imp_es_val = receita_es * (imposto_es_pct_exist / 100.0)

            # Custos por região (se ausente, considera 0)
            custo_sp_unit = custo_sp_val or 0.0
            custo_es_unit = custo_es_val or 0.0
            custo_sp_total = custo_sp_unit * un_sp
            custo_es_total = custo_es_unit * un_es

            lucro_sp = receita_sp - imp_sp_val - custo_sp_total
            lucro_es = receita_es - imp_es_val - custo_es_total
            margem_sp = (lucro_sp / receita_sp * 100.0) if receita_sp > 0 else 0.0
            margem_es = (lucro_es / receita_es * 100.0) if receita_es > 0 else 0.0

            # Totais
            faturamento = preco_exist * (un_sp + un_es)
            descontos_totais = (preco_exist - preco_liq) * (un_sp + un_es)
            imp_total = imp_sp_val + imp_es_val
            receita_liquida = faturamento - descontos_totais - imp_total
            custo_total = custo_sp_total + custo_es_total
            lucro_bruto_total = receita_liquida - custo_total
            margem_total = (lucro_bruto_total / receita_liquida * 100.0) if receita_liquida > 0 else 0.0

            # ======= Tabela por região =======
            st.markdown("---")
            st.subheader("📊 Resultados por Região")

            df_reg_exist = pd.DataFrame([
                {"Região": "SP", "Valor de venda": preco_exist, "Valor após os descontos": preco_liq,
                 "Quantidade de unidades vendidas": un_sp, "Receita": receita_sp, "Impostos": imp_sp_val,
                 "Custos": custo_sp_total, "Lucro": lucro_sp, "Margem": margem_sp},
                {"Região": "ES", "Valor de venda": preco_exist, "Valor após os descontos": preco_liq,
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

            # ======= Totais =======
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

            # ======= Download em planilha (CSV) - PRODUTO EXISTENTE =======
            st.markdown("---")
            df_export_exist = df_reg_exist.copy()
            df_export_exist.loc[len(df_export_exist)] = {
                "Região": "TOTAL",
                "Valor de venda": preco_exist,
                "Valor após os descontos": preco_liq,
                "Quantidade de unidades vendidas": un_sp + un_es,
                "Receita": receita_sp + receita_es,
                "Impostos": imp_total,
                "Custos": custo_total,
                "Lucro": lucro_bruto_total,
                "Margem": margem_total,
            }
            csv_exist = df_export_exist.to_csv(index=False, sep=";", encoding="utf-8-sig")
            st.download_button(
                "📥 Baixar resultados",
                data=csv_exist,
                file_name="resultado_produto_existente.csv",
                mime="text/csv",
            )

# --------- ABA 2: PRODUTO NOVO (inclui nome do produto) ---------
with tab_new:
    st.caption("Simulador para novos produtos.")

    nome_produto_novo = st.text_input("Nome do produto")

    preco_novo = st.number_input("Preço de venda (R$)", min_value=0.0, step=1.0, format="%.2f")

    col_custos = st.columns(2)
    with col_custos[0]:
        custo_sp = st.number_input("Custo SP (R$)", min_value=0.0, step=1.0, format="%.2f")
    with col_custos[1]:
        custo_es = st.number_input("Custo ES (R$)", min_value=0.0, step=1.0, format="%.2f")

    col_desc = st.columns(2)
    with col_desc[0]:
        desc_tipo = st.radio("Tipo de desconto", options=["%", "R$"], horizontal=True)
    with col_desc[1]:
        desc_valor = st.number_input(f"Desconto ({desc_tipo})", min_value=0.0, step=0.5, format="%.2f")

    qtd_vendas = st.number_input("Quantidade de Vendas (un.)", min_value=0, step=1, value=0)
    pct_sp = st.number_input("% SP", min_value=0.0, max_value=100.0, step=1.0, value=50.0, format="%.2f")
    pct_es = st.number_input("% ES", min_value=0.0, max_value=100.0, step=1.0, value=50.0, format="%.2f")

    col_imp = st.columns(2)
    with col_imp[0]:
        imposto_sp_pct = st.number_input("Imposto SP (%)", min_value=0.0, max_value=100.0, step=0.5, format="%.2f")
    with col_imp[1]:
        imposto_es_pct = st.number_input("Imposto ES (%)", min_value=0.0, max_value=100.0, step=0.5, format="%.2f")

    total_pct = pct_sp + pct_es
    w_sp = pct_sp / total_pct if total_pct else 0.5
    w_es = pct_es / total_pct if total_pct else 0.5
    un_sp = int(qtd_vendas * w_sp)
    un_es = int(qtd_vendas - un_sp)

    if desc_tipo == "%":
        preco_liq = preco_novo * (1 - desc_valor / 100.0)
    else:
        preco_liq = max(preco_novo - desc_valor, 0.0)

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

    faturamento = preco_novo * (un_sp + un_es)
    descontos_totais = (preco_novo - preco_liq) * (un_sp + un_es)
    receita_total = receita_sp + receita_es
    imp_total = imp_sp_val + imp_es_val
    receita_liquida = faturamento - descontos_totais - imp_total
    custo_total = custo_sp_total + custo_es_total
    lucro_bruto = receita_liquida - custo_total
    margem_total = (lucro_bruto / receita_liquida * 100.0) if receita_liquida > 0 else 0.0

    # ======= Resultados por Região (TABELA) =======
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
            "Receita": fmt_currency, "Impostos": fmt_currency,
            "Custos": fmt_currency, "Lucro": fmt_currency,
            "Margem": lambda v: f"{v:.2f}%"
        }),
        width="stretch", hide_index=True
    )

    # ======= Totais =======
    st.markdown("---")
    st.subheader("🧮 Totais")
    t1, t2, t3, t4, t5, t6, t7 = st.columns(7)
    with t1: big_metric("Unidades", fmt_int(un_sp + un_es))
    with t2: big_metric("Faturamento", fmt_currency(faturamento))
    with t3: big_metric("Impostos totais", fmt_currency(imp_total))
    with t4: big_metric("Receita Líquida", fmt_currency(receita_liquida))
    with t5: big_metric("( - ) CMV", fmt_currency(custo_total))
    with t6: big_metric("Lucro Bruto", fmt_currency(lucro_bruto))
    with t7: big_metric("Margem Bruta", f"{margem_total:.2f}%")

    # ======= Download em planilha (CSV) - PRODUTO NOVO =======
    st.markdown("---")
    df_export_new = df_reg.copy()
    df_export_new.loc[len(df_export_new)] = {
        "Região": "TOTAL",
        "Valor de venda": preco_novo,
        "Valor após os descontos": preco_liq,
        "Quantidade de unidades vendidas": un_sp + un_es,
        "Receita": receita_sp + receita_es,
        "Impostos": imp_total,
        "Custos": custo_total,
        "Lucro": lucro_bruto,
        "Margem": margem_total,
    }
    csv_new = df_export_new.to_csv(index=False, sep=";", encoding="utf-8-sig")
    st.download_button(
        "📥 Baixar resultados",
        data=csv_new,
        file_name="resultado_produto_novo.csv",
        mime="text/csv",
    )
