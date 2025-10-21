import streamlit as st

st.set_page_config(page_title="Calculadora de Margem", layout="wide")
st.title("📊 Calculadora de Margem")

access = st.text_input("Access Token", type="password")
if access == '123by':
    st.success('SUCESSO!')
    nome_produto = st.text_input('Nome do produto:')
    preco = st.number_input('Preço de venda:')
    desconto = st.number_input('Desconto:')
    dentro_fora_sp = st.radio("Venda em São Paulo?", ("Sim", "Não"))
    impostos_gerais = st.number_input('Impostos Gerais:')
    custo_medio = st.number_input('Custom Médio:')

    if st.button('Calcular'):
        resultado = None
        if dentro_fora_sp == "Sim":
            x = 1
            resultado = (preco - desconto) * x
        else:
            x = 0.5
            resultado = (preco - desconto) * x
        resultado_final = resultado - impostos_gerais - custo_medio

        st.text(f'Produto: {nome_produto}')
        st.text(f'Preço: {preco}')
        st.text(f'Desconto: {preco - desconto}')
        st.text(f'Valor Pós Cálculo Venda: {resultado}')
        st.text(f'Valor de Impostsos: {impostos_gerais}')
        st.text(f'Custo Médio: {custo_medio}')
        st.subheader(f'Lucro Bruto: {resultado_final}')

    if st.button('ENVIAR PROPOSTA'):
        st.subheader('PROPOSTA ENVIADA')
else:
    st.warning('SENHA INVÁLIDA!')

'''
Fontes externas: CMV, Preço de venda (site)
'''


# -------------------- Sidebar (opções) --------------------
# st.sidebar.header("⚙️ Opções")
# skiprows = st.sidebar.number_input("Linhas a pular no início", min_value=0, value=9, step=1)
# skipcols_left = st.sidebar.number_input("Colunas a remover (esquerda → direita)", min_value=0, value=0, step=1)

# adicionar_coluna = st.sidebar.checkbox("Adicionar coluna fixa", value=False)
# if adicionar_coluna:
#     nome_col = st.sidebar.text_input("Nome da coluna", value="Homem Aranha")
#     valor_col = st.sidebar.text_input("Valor da coluna", value="1")

# # -------------------- Upload --------------------
# up_files = st.file_uploader("Selecione um ou mais .xlsx", type=["xlsx"], accept_multiple_files=True)

# # -------------------- Utils --------------------
# @st.cache_data(show_spinner=True)
# def ler_xlsx(file, skiprows: int, skipcols_left: int,
#              add_col: bool, nome_coluna: str, valor_coluna: str):
#     df = pd.read_excel(file, skiprows=skiprows, engine="openpyxl")

#     # Remover N primeiras colunas (da esquerda para a direita)
#     if skipcols_left > 0:
#         n = min(skipcols_left, df.shape[1])
#         df = df.iloc[:, n:]

#     # Adicionar coluna fixa (se marcado)
#     if add_col and nome_coluna:
#         df.insert(0, nome_coluna, valor_coluna)

#     # Adiciona origem do arquivo
#     df.insert(0, "arquivoOrigem", file.name)
#     return df

# def baixar_excel(df: pd.DataFrame, sheet_name: str = "dados") -> bytes:
#     buffer = io.BytesIO()
#     with pd.ExcelWriter(buffer, engine="xlsxwriter", datetime_format="yyyy-mm-dd hh:mm:ss") as writer:
#         df.to_excel(writer, index=False, sheet_name=sheet_name)
#         ws = writer.sheets[sheet_name]
#         for idx, col in enumerate(df.columns):
#             serie = df[col].astype(str)
#             max_len = max([len(col)] + [len(s) for s in serie.head(1000)])
#             ws.set_column(idx, idx, min(max_len + 2, 50))
#     buffer.seek(0)
#     return buffer.read()

# # -------------------- Processamento --------------------
# st.subheader("🛠️ Processar")
# if st.button("Concatenar"):
#     if not up_files:
#         st.warning("Envie pelo menos um arquivo.")
#     else:
#         dfs = []
#         progress = st.progress(0)
#         for i, f in enumerate(up_files, start=1):
#             df = ler_xlsx(
#                 f,
#                 skiprows,
#                 skipcols_left,
#                 adicionar_coluna,
#                 nome_col if adicionar_coluna else "",
#                 valor_col if adicionar_coluna else ""
#             )
#             dfs.append(df)
#             progress.progress(i / len(up_files))

#         if dfs:
#             df_final = pd.concat(dfs, ignore_index=True)
#             st.success(f"Concluído! Dimensões finais: {df_final.shape[0]} linhas × {df_final.shape[1]} colunas")

#             st.write("### 🔎 Preview")
#             st.dataframe(df_final.head(100), use_container_width=True)

#             st.download_button(
#                 "⬇️ Baixar Excel",
#                 data=baixar_excel(df_final),
#                 file_name="concatenado.xlsx",
#                 mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
#             )
#         else:
#             st.info("Nenhum DataFrame processado.")

# # -------------------- Dicas --------------------
# with st.expander("💡 Suporte"):
#      st.markdown(
# """
# - Carlos Massato Horibe Chinen 👨‍💻  
# - Guilherme Amato 👨‍💼  
# - Maura Chagas 👩‍💻
# """
#     )