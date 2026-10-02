import streamlit as st

from componentes import animar_pagina, cabecalho_pagina
from dados_periodo import (
    classificar_produtos,
    obter_analise_estoque,
    obter_desempenho_produtos
)
from secoes.estoque import mostrar_estoque
from secoes.produtos import mostrar_produtos


# =========================================================
# ANIMAÇÃO DA PÁGINA
# =========================================================

animar_pagina("produtos_estoque")


cabecalho_pagina(
    "Produtos & Estoque",
    "Desempenho dos produtos e disponibilidade de estoque.",
    "▦"
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


# =========================
# DADOS DO PERÍODO
# =========================

produtos = obter_desempenho_produtos(
    data_inicio,
    data_fim,
    produto_selecionado,
    marketplace_selecionado
)
estoque = obter_analise_estoque(
    data_inicio,
    data_fim,
    produto_selecionado,
    marketplace_selecionado
)
produtos = classificar_produtos(produtos, estoque)


# =========================
# ESTOQUE
# =========================

st.caption(
    "O saldo importado prevalece por marketplace. Sem filtro de marketplace, "
    "os saldos importados são somados; produtos sem saldo importado continuam "
    "com a estimativa calculada pelo cadastro e pelas vendas."
)
mostrar_estoque(estoque)


# =========================
# PRODUTOS
# =========================

mostrar_produtos(produtos)