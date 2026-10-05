import streamlit as st

from autenticacao import exigir_autenticacao
from componentes import (
    animar_elementos_rolagem,
    aplicar_estilo,
    marca_sidebar,
)
from filtros import renderizar_filtros_globais
from integracao_mercadolivre import (
    capturar_callback_oauth,
    processar_callback_oauth,
)
from integracao_shopee import (
    capturar_callback_oauth_shopee,
    processar_callback_shopee,
)


st.set_page_config(
    page_title="Marketplace Intelligence",
    page_icon="🏍️",
    layout="wide"
)

aplicar_estilo()
marca_sidebar()
exigir_autenticacao()
capturar_callback_oauth()
capturar_callback_oauth_shopee()
processar_callback_oauth()
processar_callback_shopee()
animar_elementos_rolagem()


paginas = [
    st.Page(
        "paginas/visao_geral.py",
        title="Visão Geral",
        icon="🏠"
    ),
    st.Page(
        "paginas/vendas_pedidos.py",
        title="Vendas & Pedidos",
        icon="🧾"
    ),
    st.Page(
        "paginas/marketplaces.py",
        title="Marketplaces",
        icon="🏪"
    ),
    st.Page(
        "paginas/produtos_estoque.py",
        title="Produtos & Estoque",
        icon="📦"
    ),
    st.Page(
        "paginas/inteligencia.py",
        title="Inteligência",
        icon="🧠"
    ),
    st.Page(
        "paginas/importar_dados.py",
        title="Importar dados",
        icon="⬆️"
    ),
    st.Page(
        "paginas/administracao.py",
        title="Administração",
        icon="🛡️"
    ),
]


pg = st.navigation(paginas)

# Filtros compartilhados aparecem antes de cada página e persistem
# durante a navegação multipágina.
renderizar_filtros_globais()

pg.run()