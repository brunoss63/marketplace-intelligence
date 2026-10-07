from datetime import date, datetime

import pandas as pd
import streamlit as st

from armazenamento import ler_dataset


def _data_no_intervalo(
    valor: object,
    padrao: date,
    data_minima: date | None,
    data_maxima: date | None,
) -> date:
    if isinstance(valor, datetime):
        data = valor.date()
    elif isinstance(valor, date):
        data = valor
    else:
        data = padrao

    if data_minima is not None and data < data_minima:
        data = data_minima
    if data_maxima is not None and data > data_maxima:
        data = data_maxima
    return data


def renderizar_filtros_globais() -> None:
    """Renderiza os filtros compartilhados antes do conteúdo de cada página."""

    pedidos = ler_dataset("dados/pedidos.csv")
    produtos = ler_dataset("dados/produtos.csv")
    pedidos["data"] = pd.to_datetime(pedidos["data"])

    pedidos_validos = pedidos[
        pedidos["status"] == "Concluído"
    ].copy()
    datas_validas = pedidos_validos["data"].dropna()
    if datas_validas.empty:
        data_minima = None
        data_maxima = None
        data_padrao = date.today()
    else:
        data_minima = datas_validas.min().date()
        data_maxima = datas_validas.max().date()
        data_padrao = data_maxima

    st.session_state["data_inicio"] = _data_no_intervalo(
        st.session_state.get("data_inicio", data_minima or data_padrao),
        data_minima or data_padrao,
        data_minima,
        data_maxima,
    )
    st.session_state["data_fim"] = _data_no_intervalo(
        st.session_state.get("data_fim", data_maxima or data_padrao),
        data_maxima or data_padrao,
        data_minima,
        data_maxima,
    )

    opcao_todos_produtos = "Todos os produtos"
    nomes_produtos = sorted(
        produtos["produto"].dropna().astype(str).unique().tolist(),
        key=str.casefold
    )
    opcoes_produtos = [opcao_todos_produtos, *nomes_produtos]
    if st.session_state.get("produto_global") not in opcoes_produtos:
        st.session_state["produto_global"] = opcao_todos_produtos

    opcao_todos_marketplaces = "Todos"
    nomes_marketplaces = sorted(
        pedidos_validos["marketplace"].dropna().astype(str).unique().tolist(),
        key=str.casefold
    )
    opcoes_marketplaces = [opcao_todos_marketplaces, *nomes_marketplaces]
    if st.session_state.get("marketplace_global") == (
        "Todos os marketplaces"
    ):
        st.session_state["marketplace_global"] = opcao_todos_marketplaces
    if st.session_state.get("marketplace_global") not in opcoes_marketplaces:
        st.session_state["marketplace_global"] = opcao_todos_marketplaces

    with st.container(key="mi-global-filters"):
        if datas_validas.empty:
            st.info(
                "Ainda não há pedidos concluídos. Importe seus arquivos "
                "pela página “Importar dados” para habilitar os indicadores."
            )
        st.markdown(
            '<div class="mi-global-filters-anchor"></div>',
            unsafe_allow_html=True
        )
        col_inicio, col_fim, col_produto, col_marketplace = st.columns(
            [1.4, 1.4, 3.2, 2.2],
            gap="small"
        )
        with col_inicio:
            st.date_input(
                "Data inicial",
                key="data_inicio",
                min_value=data_minima,
                max_value=data_maxima,
                format="DD/MM/YYYY"
            )
        with col_fim:
            st.date_input(
                "Data final",
                key="data_fim",
                min_value=data_minima,
                max_value=data_maxima,
                format="DD/MM/YYYY"
            )
        with col_produto:
            st.selectbox(
                "Produto",
                opcoes_produtos,
                key="produto_global"
            )
        with col_marketplace:
            st.selectbox(
                "Marketplace",
                opcoes_marketplaces,
                key="marketplace_global"
            )

        data_inicio = st.session_state["data_inicio"]
        data_fim = st.session_state["data_fim"]
        if data_inicio > data_fim:
            st.error(
                "A data inicial não pode ser posterior à data final."
            )
