
import streamlit as st

from componentes import (
    animar_pagina,
    cabecalho_pagina,
    renderizar_animacoes_entrada_pagina,
    renderizar_skeleton_marketplaces,
)
from integracao_mercadolivre import mostrar_conexao_mercadolivre
from secoes.marketplace import mostrar_marketplace
from status_conexoes import obter_status_conexoes


# =========================================================
# ANIMAÇÃO DA PÁGINA
# =========================================================

animar_pagina("marketplaces")
renderizar_animacoes_entrada_pagina()


# =========================================================
# MARKETPLACES
# =========================================================

cabecalho_pagina(
    "Marketplaces",
    "Desempenho e rentabilidade por canal de venda.",
    "▥"
)

_, status_shopee = obter_status_conexoes()
with st.expander(
    "Gerenciar conexões",
    expanded=False,
    icon=":material/settings_input_component:",
):
    with st.container(border=True):
        mostrar_conexao_mercadolivre()
    st.markdown(
        '<div class="mi-connection-manager-row">'
        '<strong>Shopee</strong>'
        '<span class="mi-badge mi-badge-neutral">'
        '<span class="mi-badge-dot"></span>'
        f'<span>{status_shopee.rotulo}</span></span>'
        "</div>"
        '<div class="mi-connection-manager-note">'
        "Integração em desenvolvimento."
        "</div>",
        unsafe_allow_html=True,
    )

skeleton_slot = st.empty()
with skeleton_slot.container():
    renderizar_skeleton_marketplaces()
mostrar_marketplace(skeleton_slot=skeleton_slot)