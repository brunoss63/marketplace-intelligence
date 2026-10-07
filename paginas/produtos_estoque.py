import streamlit as st

from componentes import (
    animar_pagina,
    cabecalho_pagina,
    renderizar_animacoes_entrada_pagina,
    renderizar_skeleton_produtos,
)
from dados_periodo import (
    classificar_produtos,
    obter_analise_estoque,
    obter_desempenho_produtos,
)
from secoes.estoque import mostrar_estoque
from secoes.produtos import mostrar_portfolio, mostrar_produtos


animar_pagina("produtos_estoque")
renderizar_animacoes_entrada_pagina()
cabecalho_pagina(
    "Produtos & Estoque",
    "Desempenho dos produtos e disponibilidade de estoque.",
    "▦",
)

data_inicio = st.session_state.get("data_inicio")
data_fim = st.session_state.get("data_fim")
produto_selecionado = st.session_state.get("produto_global")
if produto_selecionado == "Todos os produtos":
    produto_selecionado = None
marketplace_selecionado = st.session_state.get("marketplace_global")
if marketplace_selecionado == "Todos":
    marketplace_selecionado = None

if data_inicio is None or data_fim is None:
    st.warning("Selecione um período na barra lateral.")
    st.stop()

aba_ativa = st.session_state.get("produtos_estoque_aba", "Estoque")
if aba_ativa not in {"Estoque", "Desempenho", "Portfólio"}:
    aba_ativa = "Estoque"

abas = st.tabs(
    ["Estoque", "Desempenho", "Portfólio"],
    default="Estoque",
    key="produtos_estoque_aba",
    on_change="rerun",
)
aba_ativa = st.session_state.get("produtos_estoque_aba", "Estoque")
indice_aba = {
    "Estoque": 0,
    "Desempenho": 1,
    "Portfólio": 2,
}.get(aba_ativa, 0)
with abas[indice_aba]:
    skeleton = st.empty()
    with skeleton.container():
        renderizar_skeleton_produtos(aba_ativa)

produtos = obter_desempenho_produtos(
    data_inicio,
    data_fim,
    produto_selecionado,
    marketplace_selecionado,
)
estoque = obter_analise_estoque(
    data_inicio,
    data_fim,
    produto_selecionado,
    marketplace_selecionado,
)
produtos = classificar_produtos(produtos, estoque)
skeleton.empty()
aba_ativa = st.session_state.get("produtos_estoque_aba", "Estoque")

abas_visitadas = set(
    st.session_state.get("_produtos_estoque_abas_visitadas", ())
)
primeira_visita = aba_ativa not in abas_visitadas
abas_visitadas.add(aba_ativa)
st.session_state["_produtos_estoque_abas_visitadas"] = tuple(abas_visitadas)
st.session_state["_mi_active_page"] = "produtos_estoque"
st.session_state["_mi_page_entering"] = primeira_visita
st.session_state["_mi_page_entry_index"] = 0

with abas[0]:
    if aba_ativa == "Estoque":
        mostrar_estoque(estoque)
with abas[1]:
    if aba_ativa == "Desempenho":
        mostrar_produtos(produtos, estoque)
with abas[2]:
    if aba_ativa == "Portfólio":
        mostrar_portfolio(produtos, estoque)

st.session_state["_mi_page_entering"] = False
