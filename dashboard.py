import streamlit as st

from autenticacao import _limpar_sessao, exigir_autenticacao
from armazenamento import obter_cliente_supabase
from componentes import (
    aplicar_estilo,
    marca_sidebar,
    renderizar_indicador_conexoes,
    renderizar_perfil_sidebar,
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
    page_icon=":material/analytics:",
    layout="wide"
)

aplicar_estilo()
marca_sidebar()
exigir_autenticacao()
capturar_callback_oauth()
capturar_callback_oauth_shopee()
processar_callback_oauth()
processar_callback_shopee()


paginas = [
    st.Page(
        "paginas/visao_geral.py",
        title="Visão Geral",
        icon=":material/dashboard:"
    ),
    st.Page(
        "paginas/vendas_pedidos.py",
        title="Vendas & Pedidos",
        icon=":material/receipt_long:"
    ),
    st.Page(
        "paginas/marketplaces.py",
        title="Marketplaces",
        icon=":material/storefront:"
    ),
    st.Page(
        "paginas/produtos_estoque.py",
        title="Produtos & Estoque",
        icon=":material/inventory_2:"
    ),
    st.Page(
        "paginas/inteligencia.py",
        title="Inteligência",
        icon=":material/insights:"
    ),
    st.Page(
        "paginas/importar_dados.py",
        title="Importar dados",
        icon=":material/upload_file:"
    ),
    st.Page(
        "paginas/administracao.py",
        title="Administração",
        icon=":material/admin_panel_settings:"
    ),
]


pg = st.navigation(paginas)
# Filtros compartilhados aparecem antes de cada página e persistem
# durante a navegação multipágina.
renderizar_filtros_globais()
if renderizar_perfil_sidebar(
    st.session_state.get("_mi_user_name", "Conta"),
):
    with st.spinner("Encerrando sua sessão..."):
        obter_cliente_supabase().auth.sign_out()
    _limpar_sessao()
    st.rerun()

with st.sidebar.container(key="mi-sidebar-footer"):
    renderizar_indicador_conexoes(container=st)

with st.container(key="mi-page-content"):
    pg.run()