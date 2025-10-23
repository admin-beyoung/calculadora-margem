# app.py
import streamlit as st
import pandas as pd
import numpy as np
import unicodedata

# =====================================
# Config
# =====================================
st.set_page_config(page_title="Calculadora de Margem", layout="wide", page_icon="📊")

SHEET_ID = "1C_rUy26WhRnx4XDoYHhV-PNCNHFOPyU5ZHnl2pQ_LXU"
SHEET_NAME = None  # usa a primeira aba da planilha pública

# =====================================
# Utils
# =====================================
def fmt_currency(v: float) -> str:
    try:
        return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return f"R$ {v:.2f}"

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
    """Lê planilha pública via CSV export e retorna colunas produto/custo_medio; tolerante a vírgula decimal."""
    url = (f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
           if sheet_name else f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv")
    df = pd.read_csv(url, dtype=str)

    df.columns = [normalize(c) for c in df.columns]
    col_prod = "produto" if "produto" in df.columns else df.columns[0]
    # custo: tenta "custo medio" → "custo médio" → qualquer "custo" → coluna B
    col_custo = ("custo medio" if "custo medio" in df.columns else
                 ("custo médio" if "custo médio" in df.columns else
                  (next((c for c in df.columns if "custo" in c), df.columns[1] if len(df.columns) > 1 else df.columns[0]))))

    out = df[[col_prod, col_custo]].copy()
    out.columns = ["produto", "custo_medio_raw"]
    out["produto"] = out["produto"].astype(str).str.strip()
    out["produto_key"] = out["produto"].map(normalize)

    cm = (out["custo_medio_raw"].astype(str)
          .str.replace(".", "", regex=False)     # remove milhares pt-BR
          .str.replace(",", ".", regex=False)    # vírgula -> ponto
          .str.replace(r"[^\d\.\-]", "", regex=True))
    out["custo_medio"] = pd.to_numeric(cm, errors="coerce").fillna(0.0)

    out = out.dropna(subset=["produto_key"]).drop_duplicates(subset=["produto_key"], keep="first").reset_index(drop=True)
    return out[["produto", "produto_key", "custo_medio"]]

def calcula_resultado(
    preco_venda: float,
    desconto_tipo: str,  # "%" | "R$"
    desconto_valor: float,
    impostos_tipo: str,  # "%" | "R$"
    impostos_valor: float,
    em_sp: bool,
    custo_medio: float,
    fator_sp: float = 1.0,
    fator_outros: float = 0.5,
):
    # desconto
    desconto_abs = preco_venda * (desconto_valor/100.0) if desconto_tipo == "%" else desconto_valor
    preco_liquido = max(preco_venda - desconto_abs, 0.0)

    # fator regional
    fator_regional = fator_sp if em_sp else fator_outros
    receita_pos_regiao = preco_liquido * fator_regional

    # impostos
    impostos_final = (receita_pos_regiao * (max(impostos_valor, 0.0)/100.0)
                      if impostos_tipo == "%" else max(impostos_valor, 0.0))

    lucro_bruto = receita_pos_regiao - impostos_final - custo_medio
    margem_bruta = (lucro_bruto/receita_pos_regiao*100.0) if receita_pos_regiao > 0 else 0.0

    return {
        "desconto_abs": desconto_abs,
        "preco_liquido": preco_liquido,
        "fator_regional": fator_regional,
        "receita_pos_regiao": receita_pos_regiao,
        "impostos_final": impostos_final,
        "custo_medio": custo_medio,
        "lucro_bruto": lucro_bruto,
        "margem_bruta": margem_bruta,
    }

def sensibilidade_incremental(
    preco_venda: float,
    desconto_tipo: str,
    desconto_valor: float,
    impostos_tipo: str,
    impostos_valor: float,
    em_sp: bool,
    custo_medio: float,
    fator_sp: float,
    fator_outros: float,
    steps: int = 5,
    inc_pct: float = 5.0,    # pontos percentuais por passo
    inc_abs: float = 10.0    # R$ por passo
) -> pd.DataFrame:
    """
    Gera 5 linhas simulando descontos incrementais em relação ao desconto atual.
    %  -> soma +5 pp a cada linha
    R$ -> soma +R$10 a cada linha
    """
    rows = []
    for i in range(1, steps + 1):
        if desconto_tipo == "%":
            novo_desc = min(desconto_valor + inc_pct * i, 100.0)  # trava em 100%
            label = f"{novo_desc:.0f}%"
        else:
            novo_desc = max(desconto_valor + inc_abs * i, 0.0)
            label = fmt_currency(novo_desc)

        r = calcula_resultado(
            preco_venda=preco_venda,
            desconto_tipo=desconto_tipo,
            desconto_valor=novo_desc,
            impostos_tipo=impostos_tipo,
            impostos_valor=impostos_valor,
            em_sp=em_sp,
            custo_medio=custo_medio,
            fator_sp=fator_sp,
            fator_outros=fator_outros,
        )
        rows.append({
            "Cenário": i,
            "Desconto aplicado": label,
            "Preço líquido": r["preco_liquido"],
            "Receita pós fator": r["receita_pos_regiao"],
            "Impostos": r["impostos_final"],
            "Custo médio": r["custo_medio"],
            "Lucro bruto": r["lucro_bruto"],
            "Margem bruta (%)": r["margem_bruta"],
        })
    df = pd.DataFrame(rows)
    return df

# =====================================
# Auth simples
# =====================================
if "authed" not in st.session_state:
    st.session_state.authed = False

with st.sidebar:
    st.subheader("🔐 Acesso")
    if not st.session_state.authed:
        access = st.text_input("Senha", type="password")
        if st.button("Entrar"):
            if access == "123by":
                st.session_state.authed = True
                st.success("Acesso permitido.")
            else:
                st.error("Senha inválida.")
    else:
        st.success("Acesso validado")

st.title("📊 Calculadora de Margem")

if not st.session_state.authed:
    st.info("Informe a senha na barra lateral para acessar a calculadora.")
    st.stop()

# =====================================
# Carrega planilha (para aba de produto existente)
# =====================================
df_planilha = None
produtos = []
prod_key_map = {}
try:
    df_planilha = fetch_sheet_products(SHEET_ID, SHEET_NAME)
    produtos = df_planilha["produto"].tolist()
    prod_key_map = dict(zip(df_planilha["produto"], df_planilha["produto_key"]))
except Exception as e:
    st.warning(f"Não foi possível carregar a planilha pública: {e}")

# =====================================
# Abas
# =====================================
tab_exist, tab_new = st.tabs(["Produto existente", "Produto novo"])

# --------- ABA 1: PRODUTO EXISTENTE ---------
with tab_exist:
    if df_planilha is None or len(produtos) == 0:
        st.error("A planilha não está acessível ou não possui dados. Verifique o compartilhamento e os cabeçalhos (A: produto, B: custo medio).")
    else:
        with st.form("form_exist", clear_on_submit=False):
            st.markdown("#### Selecione o produto")
            c1, c2, c3 = st.columns([2, 2, 2])
            with c1:
                produto_sel = st.selectbox("Produto (da planilha)", options=produtos, index=0)
                dentro_fora_sp = st.radio("Venda em São Paulo?", options=("Sim", "Não"), horizontal=True)
            with c2:
                # custo fixo da planilha
                custo_medio_exist = float(
                    df_planilha.loc[
                        df_planilha["produto_key"] == normalize(prod_key_map.get(produto_sel, produto_sel)),
                        "custo_medio"
                    ].iloc[0]
                )
                preco_exist = st.number_input("Preço de venda (R$)", min_value=0.0, step=1.0, format="%.2f", key="preco_exist")
                st.number_input("Custo médio (R$) — planilha", value=custo_medio_exist, format="%.2f",
                                disabled=True, help="Vinculado à coluna B: 'custo medio'.")
            with c3:
                fator_sp_exist = st.number_input("Fator SP", min_value=0.0, value=1.0, step=0.1, key="fsp_exist")
                fator_outros_exist = st.number_input("Fator fora de SP", min_value=0.0, value=0.5, step=0.1, key="fout_exist")

            st.markdown("---")
            st.markdown("#### Regras comerciais")
            d1, d2 = st.columns(2)
            with d1:
                st.markdown("**Desconto**")
                desc_tipo_exist = st.radio("Tipo de desconto", options=["%", "R$"], horizontal=True, key="desc_tipo_exist")
                desc_valor_exist = st.number_input("Desconto (%)" if desc_tipo_exist == "%" else "Desconto (R$)",
                                                   min_value=0.0, max_value=100.0 if desc_tipo_exist == "%" else None,
                                                   step=0.5 if desc_tipo_exist == "%" else 1.0,
                                                   format="%.2f", key="desc_valor_exist")
            with d2:
                st.markdown("**Impostos**")
                imp_tipo_exist = st.radio("Tipo de impostos", options=["%", "R$"], horizontal=True, key="imp_tipo_exist")
                imp_valor_exist = st.number_input("Impostos (%)" if imp_tipo_exist == "%" else "Impostos (R$)",
                                                  min_value=0.0, max_value=100.0 if imp_tipo_exist == "%" else None,
                                                  step=0.5 if imp_tipo_exist == "%" else 1.0,
                                                  format="%.2f", key="imp_valor_exist")

            st.markdown("---")
            submit_exist = st.form_submit_button("Calcular (produto existente)", use_container_width=True)

        if submit_exist:
            errs = []
            if preco_exist <= 0: errs.append("Preço de venda deve ser maior que zero.")
            if desc_tipo_exist == "%" and desc_valor_exist > 100: errs.append("Desconto em % não pode exceder 100%.")
            if imp_tipo_exist == "%" and imp_valor_exist > 100: errs.append("Impostos em % não pode exceder 100%.")
            if errs:
                for e in errs: st.error(e); st.stop()

            res = calcula_resultado(
                preco_venda=preco_exist,
                desconto_tipo=desc_tipo_exist,
                desconto_valor=desc_valor_exist,
                impostos_tipo=imp_tipo_exist,
                impostos_valor=imp_valor_exist,
                em_sp=(dentro_fora_sp == "Sim"),
                custo_medio=custo_medio_exist,
                fator_sp=fator_sp_exist,
                fator_outros=fator_outros_exist,
            )

            st.subheader("Resultados")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Preço líquido", fmt_currency(res["preco_liquido"]))
            m2.metric("Receita pós fator", fmt_currency(res["receita_pos_regiao"]), help=f"Fator: {res['fator_regional']:.2f}")
            m3.metric("Impostos", fmt_currency(res["impostos_final"]))
            m4.metric("Custo médio (planilha)", fmt_currency(res["custo_medio"]))
            k1, k2 = st.columns(2)
            k1.metric("Lucro bruto", fmt_currency(res["lucro_bruto"]))
            k2.metric("Margem bruta", f"{res['margem_bruta']:.2f}%")

            # ===== Nova análise de sensibilidade (incremental no desconto)
            st.markdown("### 🔎 Análise de sensibilidade (incremental no desconto)")
            df_inc = sensibilidade_incremental(
                preco_venda=preco_exist,
                desconto_tipo=desc_tipo_exist,
                desconto_valor=desc_valor_exist,
                impostos_tipo=imp_tipo_exist,
                impostos_valor=imp_valor_exist,
                em_sp=(dentro_fora_sp == "Sim"),
                custo_medio=custo_medio_exist,
                fator_sp=fator_sp_exist,
                fator_outros=fator_outros_exist,
                steps=5, inc_pct=5.0, inc_abs=10.0
            )
            st.dataframe(
                df_inc.style.format({
                    "Preço líquido": fmt_currency,
                    "Receita pós fator": fmt_currency,
                    "Impostos": fmt_currency,
                    "Custo médio": fmt_currency,
                    "Lucro bruto": fmt_currency,
                    "Margem bruta (%)": "{:.2f}"
                })
            )

            st.download_button(
                "⬇️ CSV (sensibilidade incremental)",
                data=df_inc.to_csv(index=False).encode("utf-8"),
                file_name="sensibilidade_incremental_existente.csv",
                mime="text/csv",
                use_container_width=True
            )

# --------- ABA 2: PRODUTO NOVO ---------
with tab_new:
    with st.form("form_new", clear_on_submit=False):
        st.markdown("#### Dados do produto novo")
        c1, c2, c3 = st.columns([2, 2, 2])
        with c1:
            nome_produto_new = st.text_input("Nome do produto")
            dentro_fora_sp_new = st.radio("Venda em São Paulo?", options=("Sim", "Não"), horizontal=True, key="sp_new")
        with c2:
            preco_new = st.number_input("Preço de venda (R$)", min_value=0.0, step=1.0, format="%.2f", key="preco_new")
            custo_medio_new = st.number_input("Custo médio (R$)", min_value=0.0, step=1.0, format="%.2f", key="custo_new")
        with c3:
            fator_sp_new = st.number_input("Fator SP", min_value=0.0, value=1.0, step=0.1, key="fsp_new")
            fator_outros_new = st.number_input("Fator fora de SP", min_value=0.0, value=0.5, step=0.1, key="fout_new")

        st.markdown("---")
        st.markdown("#### Regras comerciais")
        d1, d2 = st.columns(2)
        with d1:
            st.markdown("**Desconto**")
            desc_tipo_new = st.radio("Tipo de desconto", options=["%", "R$"], horizontal=True, key="desc_tipo_new")
            desc_valor_new = st.number_input("Desconto (%)" if desc_tipo_new == "%" else "Desconto (R$)",
                                             min_value=0.0, max_value=100.0 if desc_tipo_new == "%" else None,
                                             step=0.5 if desc_tipo_new == "%" else 1.0,
                                             format="%.2f", key="desc_valor_new")
        with d2:
            st.markdown("**Impostos**")
            imp_tipo_new = st.radio("Tipo de impostos", options=["%", "R$"], horizontal=True, key="imp_tipo_new")
            imp_valor_new = st.number_input("Impostos (%)" if imp_tipo_new == "%" else "Impostos (R$)",
                                            min_value=0.0, max_value=100.0 if imp_tipo_new == "%" else None,
                                            step=0.5 if imp_tipo_new == "%" else 1.0,
                                            format="%.2f", key="imp_valor_new")

        st.markdown("---")
        submit_new = st.form_submit_button("Calcular (produto novo)", use_container_width=True)

    if submit_new:
        errs = []
        if preco_new <= 0: errs.append("Preço de venda deve ser maior que zero.")
        if custo_medio_new < 0: errs.append("Custo médio não pode ser negativo.")
        if desc_tipo_new == "%" and desc_valor_new > 100: errs.append("Desconto em % não pode exceder 100%.")
        if imp_tipo_new == "%" and imp_valor_new > 100: errs.append("Impostos em % não pode exceder 100%.")
        if errs:
            for e in errs: st.error(e); st.stop()

        res_new = calcula_resultado(
            preco_venda=preco_new,
            desconto_tipo=desc_tipo_new,
            desconto_valor=desc_valor_new,
            impostos_tipo=imp_tipo_new,
            impostos_valor=imp_valor_new,
            em_sp=(dentro_fora_sp_new == "Sim"),
            custo_medio=custo_medio_new,
            fator_sp=fator_sp_new,
            fator_outros=fator_outros_new,
        )

        st.subheader("Resultados (produto novo)")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Preço líquido", fmt_currency(res_new["preco_liquido"]))
        m2.metric("Receita pós fator", fmt_currency(res_new["receita_pos_regiao"]), help=f"Fator: {res_new['fator_regional']:.2f}")
        m3.metric("Impostos", fmt_currency(res_new["impostos_final"]))
        m4.metric("Custo médio", fmt_currency(res_new["custo_medio"]))
        k1, k2 = st.columns(2)
        k1.metric("Lucro bruto", fmt_currency(res_new["lucro_bruto"]))
        k2.metric("Margem bruta", f"{res_new['margem_bruta']:.2f}%")

        # ===== Nova análise de sensibilidade (incremental no desconto)
        st.markdown("### 🔎 Análise de sensibilidade (incremental no desconto)")
        df_inc_new = sensibilidade_incremental(
            preco_venda=preco_new,
            desconto_tipo=desc_tipo_new,
            desconto_valor=desc_valor_new,
            impostos_tipo=imp_tipo_new,
            impostos_valor=imp_valor_new,
            em_sp=(dentro_fora_sp_new == "Sim"),
            custo_medio=custo_medio_new,
            fator_sp=fator_sp_new,
            fator_outros=fator_outros_new,
            steps=5, inc_pct=5.0, inc_abs=10.0
        )
        st.dataframe(
            df_inc_new.style.format({
                "Preço líquido": fmt_currency,
                "Receita pós fator": fmt_currency,
                "Impostos": fmt_currency,
                "Custo médio": fmt_currency,
                "Lucro bruto": fmt_currency,
                "Margem bruta (%)": "{:.2f}"
            })
        )

        st.download_button(
            "⬇️ CSV (sensibilidade incremental)",
            data=df_inc_new.to_csv(index=False).encode("utf-8"),
            file_name="sensibilidade_incremental_novo.csv",
            mime="text/csv",
            use_container_width=True
        )
