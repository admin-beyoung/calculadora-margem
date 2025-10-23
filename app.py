import streamlit as st
import pandas as pd
import numpy as np
import unicodedata

st.set_page_config(page_title="Calculadora de Margem", layout="wide", page_icon="📊")

SHEET_ID = "1C_rUy26WhRnx4XDoYHhV-PNCNHFOPyU5ZHnl2pQ_LXU"
SHEET_NAME = None  # primeira aba

# ---------------- utils ----------------
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
    # CSV export da planilha pública
    url = (
        f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
        if sheet_name else
        f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv"
    )
    # lê tudo como string para controlarmos a conversão (locale pt-BR)
    df = pd.read_csv(url, dtype=str)

    # normaliza cabeçalhos
    original_cols = list(df.columns)
    df.columns = [normalize(c) for c in df.columns]

    # tenta achar exatamente as colunas
    col_prod = "produto" if "produto" in df.columns else df.columns[0]
    col_custo = "custo medio" if "custo medio" in df.columns else (
        "custo médio" if "custo médio" in df.columns else
        (df.columns[1] if len(df.columns) > 1 else df.columns[0])
    )

    out = df[[col_prod, col_custo]].copy()
    out.columns = ["produto", "custo_medio_raw"]

    # limpa produto + cria chave de junção tolerante
    out["produto"] = out["produto"].astype(str).str.strip()
    out["produto_key"] = out["produto"].map(normalize)

    # trata custo (ex.: "25,00" -> 25.00; remove separador de milhar)
    cm = (
        out["custo_medio_raw"]
        .astype(str)
        .str.replace(".", "", regex=False)   # remove milhares pt-BR
        .str.replace(",", ".", regex=False)  # vírgula -> ponto
        .str.replace(r"[^\d\.\-]", "", regex=True)  # remove qualquer lixo
    )
    out["custo_medio"] = pd.to_numeric(cm, errors="coerce").fillna(0.0)

    # remove duplicados de produto
    out = out.dropna(subset=["produto_key"]).drop_duplicates(subset=["produto_key"], keep="first").reset_index(drop=True)

    # st.write({"debug_cols": original_cols, "usando": {"produto": col_prod, "custo": col_custo}})
    return out[["produto", "produto_key", "custo_medio"]]

def calcula_resultado(
    preco_venda: float,
    desconto_tipo: str,
    desconto_valor: float,
    impostos_tipo: str,
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
    impostos_final = (
        receita_pos_regiao * (max(impostos_valor, 0.0)/100.0) if impostos_tipo == "%" else
        max(impostos_valor, 0.0)
    )

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

def tabela_sensibilidade(preco, em_sp, impostos_tipo, impostos_valor, custo,
                         desconto_base=0, desconto_tipo="%", fator_sp=1.0, fator_outros=0.5):
    variacoes_pp = np.array([-5, -2, 0, 2, 5], dtype=float)
    custos_mult  = np.array([0.9, 0.95, 1.0, 1.05, 1.10], dtype=float)

    if desconto_tipo == "%":
        descontos_efetivos = sorted({max(desconto_base + v, 0.0) for v in variacoes_pp})
        desc_labels = {d: f"{d:.0f}%" for d in descontos_efetivos}
        desc_to_value = lambda d: d
    else:
        descontos_efetivos = sorted({max(desconto_base + (v/100.0)*preco, 0.0) for v in variacoes_pp})
        def _fmt_currency(v: float) -> str:
            return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        desc_labels = {d: _fmt_currency(d) for d in descontos_efetivos}
        desc_to_value = lambda d: d

    rows = []
    for d in descontos_efetivos:
        for km in custos_mult:
            r = calcula_resultado(
                preco_venda=preco,
                desconto_tipo=desconto_tipo,
                desconto_valor=desc_to_value(d),
                impostos_tipo=impostos_tipo,
                impostos_valor=impostos_valor,
                em_sp=em_sp,
                custo_medio=custo * km,
                fator_sp=fator_sp,
                fator_outros=fator_outros,
            )
            rows.append({
                "desc_val": d,
                "cost_mult": km,
                "Desconto": desc_labels[d],
                "Custo": f"{int((km-1)*100):+d}%",
                "Margem Bruta (%)": round(r["margem_bruta"], 2),
                "Lucro Bruto": r["lucro_bruto"],
                "Preço Líquido": r["preco_liquido"],
            })

    df = pd.DataFrame(rows).drop_duplicates(subset=["desc_val", "cost_mult"], keep="last")
    tabela = pd.pivot_table(df, index="Desconto", columns="Custo", values="Margem Bruta (%)", aggfunc="mean")
    tabela = tabela.sort_index()
    tabela = tabela[sorted(tabela.columns, key=lambda c: int(c.replace("%","")))]
    return df, tabela

# ---------------- auth ----------------
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
    st.info("Informe a senha na barra lateral para acessar.")
    st.stop()

# ---------------- carrega planilha ----------------
try:
    df_planilha = fetch_sheet_products(SHEET_ID, SHEET_NAME)
except Exception as e:
    st.error(f"Falha ao ler a planilha pública: {e}")
    st.stop()

produtos = df_planilha["produto"].tolist()
prod_key_map = dict(zip(df_planilha["produto"], df_planilha["produto_key"]))  # mostra bonito, busca pela key

# ---------------- formulário ----------------
with st.form("form_calc", clear_on_submit=False):
    st.markdown("#### Dados do produto & preço")
    l1c1, l1c2, l1c3 = st.columns([2, 2, 2])
    with l1c1:
        produto_sel = st.selectbox("Produto (da planilha)", options=produtos, index=0 if len(produtos) else None)
        nome_produto = st.text_input("Nome do produto (pode editar)", value=produto_sel or "")
        dentro_fora_sp = st.radio("Venda em São Paulo?", options=("Sim", "Não"), horizontal=True)
    with l1c2:
        # custo da planilha conforme seleção (somente leitura)
        custo_medio = float(
            df_planilha.loc[
                df_planilha["produto_key"] == normalize(prod_key_map.get(produto_sel, produto_sel)),
                "custo_medio"
            ].iloc[0]
        ) if produto_sel else 0.0
        preco = st.number_input("Preço de venda (R$)", min_value=0.0, step=1.0, format="%.2f")
        st.number_input("Custo médio (R$) — da planilha", value=custo_medio, format="%.2f",
                        disabled=True, help="Valor vinculado à coluna B: 'custo medio'.")
    with l1c3:
        fator_sp = st.number_input("Fator SP", min_value=0.0, value=1.0, step=0.1)
        fator_outros = st.number_input("Fator fora de SP", min_value=0.0, value=0.5, step=0.1)

    st.markdown("---")
    st.markdown("#### Regras comerciais")
    l2c1, l2c2 = st.columns(2)
    with l2c1:
        st.markdown("**Desconto**")
        desconto_tipo = st.radio("Tipo de desconto", options=["%", "R$"], horizontal=True, key="desc_tipo")
        if desconto_tipo == "%":
            desconto_valor = st.number_input("Desconto (%)", min_value=0.0, max_value=100.0, step=0.5, format="%.2f", key="desc_valor_pct")
        else:
            desconto_valor = st.number_input("Desconto (R$)", min_value=0.0, step=1.0, format="%.2f", key="desc_valor_abs")
    with l2c2:
        st.markdown("**Impostos**")
        impostos_tipo = st.radio("Tipo de impostos", options=["%", "R$"], horizontal=True, key="imp_tipo")
        if impostos_tipo == "%":
            impostos_valor = st.number_input("Impostos (%)", min_value=0.0, max_value=100.0, step=0.5, format="%.2f", key="imp_valor_pct")
        else:
            impostos_valor = st.number_input("Impostos (R$)", min_value=0.0, step=1.0, format="%.2f", key="imp_valor_abs")

    st.markdown("---")
    submitted = st.form_submit_button("Calcular", use_container_width=True)

# ---------------- resultados ----------------
if submitted:
    # validações
    errors = []
    if preco <= 0: errors.append("Preço de venda deve ser maior que zero.")
    if custo_medio < 0: errors.append("Custo médio não pode ser negativo.")
    if desconto_tipo == "%" and desconto_valor > 100: errors.append("Desconto em % não pode exceder 100%.")
    if impostos_tipo == "%" and impostos_valor > 100: errors.append("Impostos em % não pode exceder 100%.")
    if errors:
        for e in errors: st.error(e)
        st.stop()

    res = calcula_resultado(
        preco_venda=preco,
        desconto_tipo=desconto_tipo,
        desconto_valor=desconto_valor,
        impostos_tipo=impostos_tipo,
        impostos_valor=impostos_valor,
        em_sp=(dentro_fora_sp == "Sim"),
        custo_medio=custo_medio,  # sempre custo da planilha
        fator_sp=fator_sp,
        fator_outros=fator_outros,
    )

    st.markdown("---")
    st.subheader("Resultados")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Preço líquido (pós desconto)", fmt_currency(res["preco_liquido"]))
    m2.metric("Receita pós fator regional", fmt_currency(res["receita_pos_regiao"]), help=f"Fator aplicado: {res['fator_regional']:.2f}")
    m3.metric("Impostos", fmt_currency(res["impostos_final"]))
    m4.metric("Custo médio (planilha)", fmt_currency(res["custo_medio"]))

    k1, k2 = st.columns(2)
    k1.metric("Lucro bruto", fmt_currency(res["lucro_bruto"]))
    k2.metric("Margem bruta (%)", f"{res['margem_bruta']:.2f}%")

    st.markdown("### 🔎 Análise de sensibilidade")
    df_raw, tabela = tabela_sensibilidade(
        preco=preco,
        em_sp=(dentro_fora_sp == "Sim"),
        impostos_tipo=impostos_tipo,
        impostos_valor=impostos_valor,
        custo=custo_medio,
        desconto_base=desconto_valor,
        desconto_tipo=desconto_tipo,
        fator_sp=fator_sp,
        fator_outros=fator_outros
    )
    st.caption("Margem Bruta (%) por variação de desconto (linhas) e custo (colunas).")
    st.dataframe(tabela.style.format("{:.2f}"))

    st.markdown("### 📁 Exportar resultados")
    c1, c2 = st.columns(2)
    with c1:
        st.download_button("⬇️ CSV (dados brutos)", data=df_raw.to_csv(index=False).encode("utf-8"),
                           file_name="sensibilidade_bruto.csv", mime="text/csv", use_container_width=True)
    with c2:
        st.download_button("⬇️ CSV (tabela pivô)", data=tabela.reset_index().to_csv(index=False).encode("utf-8"),
                           file_name="sensibilidade_pivo.csv", mime="text/csv", use_container_width=True)
