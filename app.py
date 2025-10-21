# app.py
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from io import StringIO

# =====================================
# Config / helpers
# =====================================
st.set_page_config(page_title="Calculadora de Margem", layout="wide", page_icon="📊")

def fmt_currency(v: float) -> str:
    try:
        return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return f"R$ {v:.2f}"

def calcula_resultado(
    preco_venda: float,
    desconto_tipo: str,
    desconto_valor: float,
    em_sp: bool,
    impostos_percent: float,
    impostos_valor_abs: float,
    custo_medio: float,
    fator_sp: float = 1.0,
    fator_outros: float = 0.5,
):
    # Desconto
    if desconto_tipo == "%":
        desconto_abs = preco_venda * (desconto_valor / 100.0)
    else:
        desconto_abs = desconto_valor

    preco_liquido = max(preco_venda - desconto_abs, 0.0)

    # Fator regional
    fator_regional = fator_sp if em_sp else fator_outros
    receita_pos_regiao = preco_liquido * fator_regional

    # Impostos: usa valor absoluto se informado
    impostos_percent_val = max(impostos_percent, 0.0)
    impostos_calc_percent = receita_pos_regiao * (impostos_percent_val / 100.0)
    impostos_final = impostos_valor_abs if impostos_valor_abs > 0 else impostos_calc_percent

    # Lucro e margem
    lucro_bruto = receita_pos_regiao - impostos_final - custo_medio
    margem_bruta = (lucro_bruto / receita_pos_regiao * 100.0) if receita_pos_regiao > 0 else 0.0

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

def tabela_sensibilidade(preco, em_sp, impostos_percent, custo,
                         desconto_base=0, desconto_tipo="%",
                         fator_sp=1.0, fator_outros=0.5):
    """
    Gera dataset bruto e tabela pivô (margem %) por variação de desconto x variação de custo.
    Sem erros de duplicidade e com rótulos amigáveis.
    """
    variacoes_pp = np.array([-5, -2, 0, 2, 5], dtype=float)     # passos no desconto
    custos_mult = np.array([0.9, 0.95, 1.0, 1.05, 1.10], dtype=float)

    # Descontos efetivos (deduplicados)
    if desconto_tipo == "%":
        descontos_efetivos = sorted({max(desconto_base + v, 0.0) for v in variacoes_pp})
        desc_labels = {d: f"{d:.0f}%"}
        desc_to_value = lambda d: d
    else:
        # 1 pp ~ 1% do preço como incremento
        descontos_efetivos = sorted({max(desconto_base + (v/100.0)*preco, 0.0) for v in variacoes_pp})
        def _fmt_currency(v: float) -> str:
            return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        desc_labels = {d: _fmt_currency(d)}
        desc_to_value = lambda d: d

    rows = []
    for d in descontos_efetivos:
        for km in custos_mult:
            r = calcula_resultado(
                preco_venda=preco,
                desconto_tipo=desconto_tipo,
                desconto_valor=desc_to_value(d),
                em_sp=em_sp,
                impostos_percent=impostos_percent,
                impostos_valor_abs=0.0,
                custo_medio=custo * km,
                fator_sp=fator_sp,
                fator_outros=fator_outros,
            )
            rows.append({
                "desc_val": d,                               # chave numérica
                "cost_mult": km,                             # chave numérica
                "Desconto": desc_labels[d],
                "Custo": f"{int((km-1)*100):+d}%",
                "Margem Bruta (%)": round(r["margem_bruta"], 2),
                "Lucro Bruto": r["lucro_bruto"],
                "Preço Líquido": r["preco_liquido"],
            })

    df = pd.DataFrame(rows).drop_duplicates(subset=["desc_val", "cost_mult"], keep="last")

    tabela = pd.pivot_table(
        df,
        index="Desconto",
        columns="Custo",
        values="Margem Bruta (%)",
        aggfunc="mean"
    )

    # Ordenações visuais
    tabela = tabela.sort_index()
    tabela = tabela[sorted(tabela.columns, key=lambda c: int(c.replace("%","")))]

    return df, tabela

# =====================================
# Auth simples (session_state)
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
        st.success("Acesso já validado.")

st.title("📊 Calculadora de Margem")

if not st.session_state.authed:
    st.info("Informe a senha na barra lateral para acessar a calculadora.")
    st.stop()

# =====================================
# Formulário de inputs
# =====================================
with st.form("form_calc", clear_on_submit=False):
    st.subheader("🧮 Parâmetros da Proposta")
    c1, c2, c3 = st.columns(3)
    with c1:
        nome_produto = st.text_input("Nome do produto", placeholder="Ex.: Sérum Vitamina C 30ml")
        preco = st.number_input("Preço de venda (R$)", min_value=0.0, step=1.0, format="%.2f")
        dentro_fora_sp = st.radio("Venda em São Paulo?", options=("Sim", "Não"), horizontal=True)
    with c2:
        desconto_tipo = st.radio("Tipo de desconto", options=["%", "R$"], horizontal=True)
        if desconto_tipo == "%":
            desconto_valor = st.number_input("Desconto (%)", min_value=0.0, max_value=100.0, step=1.0, format="%.2f")
        else:
            desconto_valor = st.number_input("Desconto (R$)", min_value=0.0, step=1.0, format="%.2f")

        impostos_percent = st.number_input("Impostos gerais (%)", min_value=0.0, max_value=100.0, step=0.5, value=0.0, format="%.2f",
                                           help="Se você preencher um valor absoluto em R$, ele prevalece sobre o %.")
    with c3:
        impostos_abs = st.number_input("Impostos (R$) — opcional", min_value=0.0, step=1.0, format="%.2f")
        custo_medio = st.number_input("Custo médio (R$)", min_value=0.0, step=1.0, format="%.2f")
        fator_sp = st.number_input("Fator SP", min_value=0.0, value=1.0, step=0.1, help="Regra interna. Padrão 1.0")
        fator_outros = st.number_input("Fator fora de SP", min_value=0.0, value=0.5, step=0.1, help="Regra interna. Padrão 0.5")

    submitted = st.form_submit_button("Calcular", use_container_width=True)

if submitted:
    # Validações básicas
    errors = []
    if preco <= 0:
        errors.append("Preço de venda deve ser maior que zero.")
    if custo_medio < 0:
        errors.append("Custo médio não pode ser negativo.")
    if desconto_tipo == "%" and desconto_valor > 100:
        errors.append("Desconto em % não pode exceder 100%.")
    if errors:
        for e in errors:
            st.error(e)
        st.stop()

    res = calcula_resultado(
        preco_venda=preco,
        desconto_tipo=desconto_tipo,
        desconto_valor=desconto_valor,
        em_sp=(dentro_fora_sp == "Sim"),
        impostos_percent=impostos_percent,
        impostos_valor_abs=impostos_abs,
        custo_medio=custo_medio,
        fator_sp=fator_sp,
        fator_outros=fator_outros,
    )

    st.markdown("---")
    st.subheader("Resultados")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Preço líquido (pós desconto)", fmt_currency(res["preco_liquido"]))
    m2.metric("Receita pós fator regional", fmt_currency(res["receita_pos_regiao"]), help=f"Fator aplicado: {res['fator_regional']:.2f}")
    m3.metric("Impostos", fmt_currency(res["impostos_final"]))
    m4.metric("Custo médio", fmt_currency(res["custo_medio"]))

    k1, k2 = st.columns(2)
    k1.metric("Lucro bruto", fmt_currency(res["lucro_bruto"]))
    k2.metric("Margem bruta (%)", f"{res['margem_bruta']:.2f}%")

    with st.expander("Ver detalhamento textual"):
        st.text(f"Produto: {nome_produto or '-'}")
        st.text(f"Preço de Venda: {fmt_currency(preco)}")
        if desconto_tipo == "%":
            st.text(f"Desconto: {desconto_valor:.2f}%  (={fmt_currency(res['desconto_abs'])})")
        else:
            st.text(f"Desconto: {fmt_currency(res['desconto_abs'])}")
        st.text(f"Preço Líquido: {fmt_currency(res['preco_liquido'])}")
        st.text(f"Fator Regional aplicado: {res['fator_regional']:.2f}")
        st.text(f"Receita Pós Fator Regional: {fmt_currency(res['receita_pos_regiao'])}")
        st.text(f"Impostos Considerados: {fmt_currency(res['impostos_final'])}")
        st.text(f"Custo Médio: {fmt_currency(res['custo_medio'])}")
        st.text(f"Lucro Bruto: {fmt_currency(res['lucro_bruto'])}")
        st.text(f"Margem Bruta: {res['margem_bruta']:.2f}%")

    # =====================================
    # Sensibilidade + Heatmap + Export
    # =====================================
    st.markdown("### 🔎 Análise de sensibilidade")

    df_raw, tabela = tabela_sensibilidade(
        preco=preco,
        em_sp=(dentro_fora_sp == "Sim"),
        impostos_percent=impostos_percent,
        custo=custo_medio,
        desconto_base=desconto_valor if desconto_tipo == "%" else desconto_valor,
        desconto_tipo=desconto_tipo,
        fator_sp=fator_sp,
        fator_outros=fator_outros
    )

    st.caption("Margem Bruta (%) por variação de desconto (linhas) e custo (colunas).")
    st.dataframe(tabela.style.format("{:.2f}"))

    # ---- Heatmap (matplotlib) ----
    st.caption("Heatmap da Margem Bruta (%)")
    fig, ax = plt.subplots()
    im = ax.imshow(tabela.values, aspect="auto")
    ax.set_xticks(range(len(tabela.columns)))
    ax.set_yticks(range(len(tabela.index)))
    ax.set_xticklabels(list(tabela.columns))
    ax.set_yticklabels(list(tabela.index))
    ax.set_xlabel("Variação de Custo")
    ax.set_ylabel("Desconto")
    cbar = fig.colorbar(im, ax=ax)
    cbar.set_label("Margem Bruta (%)")
    st.pyplot(fig, use_container_width=True)

    # ---- Exportações CSV ----
    cexp1, cexp2 = st.columns(2)
    with cexp1:
        csv_raw = df_raw.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="⬇️ Baixar CSV (dados brutos)",
            data=csv_raw,
            file_name="sensibilidade_bruto.csv",
            mime="text/csv",
            use_container_width=True
        )
    with cexp2:
        csv_tbl = tabela.reset_index().to_csv(index=False).encode("utf-8")
        st.download_button(
            label="⬇️ Baixar CSV (tabela pivô)",
            data=csv_tbl,
            file_name="sensibilidade_pivo.csv",
            mime="text/csv",
            use_container_width=True
        )

    # =====================================
    # Proposta (copiar/colar)
    # =====================================
    st.markdown("### ✉️ Enviar proposta")
    proposta = f"""
PROPOSTA COMERCIAL
Produto: {nome_produto or '-'}
Preço de venda: {fmt_currency(preco)}
Desconto: {"{:.2f}%".format(desconto_valor) if desconto_tipo=="%" else fmt_currency(res['desconto_abs'])}
Preço líquido: {fmt_currency(res['preco_liquido'])}
Região: {"São Paulo" if dentro_fora_sp == "Sim" else "Outros"} (fator {res['fator_regional']:.2f})
Receita pós fator: {fmt_currency(res['receita_pos_regiao'])}
Impostos: {fmt_currency(res['impostos_final'])}
Custo médio: {fmt_currency(res['custo_medio'])}
Lucro bruto: {fmt_currency(res['lucro_bruto'])}
Margem bruta: {res['margem_bruta']:.2f}%
""".strip()

    st.code(proposta, language="markdown")

    if st.button("ENVIAR PROPOSTA", use_container_width=True):
        st.success("✅ Proposta pronta! Copie o texto acima e envie pelo seu canal preferido.")

# Rodapé
st.markdown("---")
st.caption("Fontes externas típicas: CMV, preço de venda (site) • App por Streamlit")
