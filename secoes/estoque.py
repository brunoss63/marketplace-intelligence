from html import escape

import pandas as pd
import streamlit as st

from componentes import card, tabela_limpa


def _moeda(valor: float) -> str:
    return (
        f"R$ {valor:,.0f}"
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )


def _moeda_com_centavos(valor: float) -> str:
    return (
        f"R$ {valor:,.2f}"
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )


def _lista_produtos(
    produtos: pd.DataFrame,
    *,
    vazio: str,
    mostrar_cobertura: bool
) -> str:
    if produtos.empty:
        return (
            '<div class="mi-stock-empty">'
            f"{escape(vazio)}</div>"
        )

    itens = []
    for _, produto in produtos.iterrows():
        nome = escape(str(produto["produto"]))
        sku = escape(str(produto["sku"]))
        estoque_atual = f'{produto["estoque_atual"]:,.0f}'.replace(",", ".")
        vendas_dia = f'{produto["media_vendas_dia"]:.1f}'

        if mostrar_cobertura:
            cobertura = f'{produto["dias_estoque"]:.1f} dias'
            detalhe = (
                f'<span class="mi-stock-detail">'
                f'Cobertura <b>{cobertura}</b></span>'
            )
            status = escape(str(produto["status_estoque"]))
            estado = (
                "mi-stock-status-critical"
                if status in {"Crítico", "Sem estoque"}
                else "mi-stock-status-warning"
            )
            detalhe += (
                f'<span class="mi-stock-status {estado}">'
                f"{status}</span>"
            )
        else:
            valor = _moeda(float(produto["valor_estoque"]))
            detalhe = (
                f'<span class="mi-stock-detail">'
                f'Vendas/dia <b>{vendas_dia}</b></span>'
                f'<span class="mi-stock-value">{valor}</span>'
            )

        itens.append(
            f"""
            <div class="mi-stock-row">
                <div class="mi-stock-product">
                    <span class="mi-stock-name">{nome}</span>
                    <span class="mi-stock-sku">{sku}</span>
                </div>
                <div class="mi-stock-facts">
                    <span class="mi-stock-detail">
                        Estoque <b>{estoque_atual}</b>
                    </span>
                    {detalhe}
                </div>
            </div>
            """
        )

    return "".join(itens)


def _painel_prioridade(
    titulo: str,
    subtitulo: str,
    produtos: pd.DataFrame,
    *,
    vazio: str,
    mostrar_cobertura: bool
) -> None:
    conteudo = _lista_produtos(
        produtos,
        vazio=vazio,
        mostrar_cobertura=mostrar_cobertura
    )

    with st.container(border=True):
        st.markdown(
            f"""
            <div class="mi-chart-heading mi-dashboard-panel">
                <div class="mi-chart-title">{escape(titulo)}</div>
                <div class="mi-chart-subtitle">{escape(subtitulo)}</div>
            </div>
            <div class="mi-stock-list">{conteudo}</div>
            """,
            unsafe_allow_html=True
        )


def mostrar_estoque(estoque: pd.DataFrame) -> None:
    st.markdown("### 📦 Gestão de estoque")
    st.caption(
        "Cobertura calculada com a média diária de vendas no período "
        "selecionado. Use os alertas para priorizar reposição e revisar "
        "capital imobilizado."
    )

    sem_estoque = estoque[estoque["estoque_atual"] <= 0]
    produtos_em_risco = estoque[
        (estoque["estoque_atual"] > 0)
        & (estoque["dias_estoque"] <= 15)
    ]
    estoque_parado = estoque[
        (estoque["estoque_atual"] > 0)
        & (
            (estoque["media_vendas_dia"] == 0)
            | (estoque["dias_estoque"] > 45)
        )
    ]

    capital_parado = float(estoque_parado["valor_estoque"].sum())
    valor_total_estoque = float(estoque["valor_estoque"].sum())
    unidades_disponiveis = float(estoque["estoque_atual"].sum())

    colunas = st.columns(5, gap="small")
    indicadores = [
        (
            "Valor em estoque",
            _moeda(valor_total_estoque),
            "💰",
            "Valor do estoque disponível ao custo unitário cadastrado.",
            "normal"
        ),
        (
            "Unidades disponíveis",
            f"{unidades_disponiveis:,.0f}".replace(",", "."),
            "📦",
            "Soma das unidades atualmente disponíveis de todos os produtos.",
            "normal"
        ),
        (
            "Risco de ruptura",
            f"{len(produtos_em_risco)} produtos",
            "⚠️",
            "Produtos com estoque positivo e cobertura estimada de até 15 dias.",
            "negative" if not produtos_em_risco.empty else "positive"
        ),
        (
            "Sem estoque",
            f"{len(sem_estoque)} produtos",
            "🚫",
            "Produtos cuja quantidade disponível calculada é zero.",
            "negative" if not sem_estoque.empty else "positive"
        ),
        (
            "Capital parado",
            _moeda(capital_parado),
            "⏳",
            "Valor ao custo em produtos sem vendas no período ou com mais de "
            "45 dias de cobertura estimada.",
            "neutral" if capital_parado > 0 else "positive"
        )
    ]

    for coluna, indicador in zip(colunas, indicadores):
        titulo, valor, icone, explicacao, tipo = indicador
        with coluna:
            card(
                titulo,
                valor,
                icone,
                f"{len(estoque_parado)} produtos"
                if titulo == "Capital parado"
                else "",
                tipo,
                tooltip=explicacao
            )

    st.caption(
        "Capital parado considera produtos com estoque e sem vendas no "
        "período ou mais de 45 dias de cobertura. A venda potencial perdida "
        "é estimada pelo giro médio e pelo estoque inicial cadastrado; sem "
        "histórico diário de saldo, não confirma quando a ruptura ocorreu."
    )

    col_risco, col_parado = st.columns(2, gap="medium")
    with col_risco:
        produtos_para_repor = pd.concat(
            [sem_estoque, produtos_em_risco]
        ).drop_duplicates(subset="sku")
        _painel_prioridade(
            "⚠️ Risco de ruptura",
            "Sem estoque ou com até 15 dias de cobertura; priorizados pela urgência",
            produtos_para_repor.sort_values(
                "dias_estoque",
                ascending=True
            ).head(6),
            vazio="Nenhum produto sem estoque ou com cobertura abaixo de 15 dias.",
            mostrar_cobertura=True
        )

    with col_parado:
        _painel_prioridade(
            "⏳ Estoque parado",
            "Produtos sem giro ou com mais de 45 dias de cobertura",
            estoque_parado.sort_values(
                "valor_estoque",
                ascending=False
            ).head(6),
            vazio="Nenhum produto atende ao critério de estoque parado.",
            mostrar_cobertura=False
        )

    with st.container(border=True):
        st.markdown(
            """
            <div class="mi-chart-heading mi-dashboard-panel">
                <div class="mi-chart-title">📉 Venda potencial perdida</div>
                <div class="mi-chart-subtitle">
                    Estimativa de receita associada a produtos sem estoque
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        sem_estoque_com_perda = estoque[
            (estoque["estoque_atual"] <= 0)
            & (estoque["receita_potencial_perdida"] > 0)
        ].copy(        )
        if sem_estoque_com_perda.empty:
            st.caption(
                "Nenhuma venda potencial perdida estimada neste período."
            )
        else:
            st.markdown(
                '<div class="mi-table-filters-anchor"></div>',
                unsafe_allow_html=True,
            )
            filtro_busca, filtro_ordem = st.columns(
                [2, 1],
                gap="small"
            )
            with filtro_busca:
                busca_perda = st.text_input(
                    "Buscar produto ou SKU",
                    placeholder="Digite um produto ou SKU...",
                    key="estoque_perda_busca"
                ).strip()
            with filtro_ordem:
                ordem_perda = st.selectbox(
                    "Ordenar por",
                    [
                        "Maior venda potencial",
                        "Mais dias sem estoque",
                        "Maior venda diária"
                    ],
                    key="estoque_perda_ordenacao"
                )

            filtrado_perda = sem_estoque_com_perda
            if busca_perda:
                corresponde = (
                    filtrado_perda["produto"].astype(str).str.contains(
                        busca_perda,
                        case=False,
                        regex=False,
                        na=False
                    )
                    | filtrado_perda["sku"].astype(str).str.contains(
                        busca_perda,
                        case=False,
                        regex=False,
                        na=False
                    )
                )
                filtrado_perda = filtrado_perda[corresponde]

            ordem_perda_colunas = {
                "Maior venda potencial": (
                    "receita_potencial_perdida",
                    False
                ),
                "Mais dias sem estoque": (
                    "dias_sem_estoque_estimados",
                    False
                ),
                "Maior venda diária": ("media_vendas_dia", False)
            }
            coluna_ordem, crescente = ordem_perda_colunas[ordem_perda]
            filtrado_perda = filtrado_perda.sort_values(
                coluna_ordem,
                ascending=crescente
            )
            st.caption(
                f"{len(filtrado_perda)} produtos encontrados · "
                "valores estimados para o período selecionado"
            )

            tabela_perda = filtrado_perda[
                [
                    "produto",
                    "sku",
                    "estoque_atual",
                    "media_vendas_dia",
                    "dias_sem_estoque_estimados",
                    "receita_potencial_perdida"
                ]
            ].copy()
            tabela_perda.columns = [
                "Produto",
                "SKU",
                "Estoque",
                "Vendas/dia",
                "Dias sem estoque",
                "Venda potencial perdida"
            ]
            tabela_perda["Estoque"] = tabela_perda["Estoque"].map(
                lambda valor: f"{valor:.0f}"
            )
            tabela_perda["Vendas/dia"] = tabela_perda["Vendas/dia"].map(
                lambda valor: f"{valor:.2f}"
            )
            tabela_perda["Dias sem estoque"] = tabela_perda[
                "Dias sem estoque"
            ].map(lambda valor: f"{valor:.0f}")
            tabela_perda["Venda potencial perdida"] = tabela_perda[
                "Venda potencial perdida"
            ].map(_moeda_com_centavos)

            tabela_limpa(
                tabela_perda,
                chave="venda_potencial_perdida"
            )

    with st.container(border=True):
        st.markdown(
            """
            <div class="mi-chart-heading mi-dashboard-panel">
                <div class="mi-chart-title">📋 Tabela de estoque</div>
                <div class="mi-chart-subtitle">
                    Pesquise e filtre os produtos para planejar a reposição
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        st.markdown(
            '<div class="mi-table-filters-anchor"></div>',
            unsafe_allow_html=True,
        )
        filtro_texto, filtro_status, ordenacao = st.columns(
            [2, 1, 1],
            gap="small"
        )
        with filtro_texto:
            busca = st.text_input(
                "Buscar produto ou SKU",
                placeholder="Digite um produto ou SKU...",
                key="estoque_busca"
            ).strip()
        with filtro_status:
            opcoes_status = ["Todos"] + sorted(
                estoque["status_estoque"].dropna().unique().tolist()
            )
            status_selecionado = st.selectbox(
                "Status",
                opcoes_status,
                key="estoque_filtro_status"
            )
        with ordenacao:
            ordem_selecionada = st.selectbox(
                "Ordenar por",
                [
                    "Menor cobertura",
                    "Maior valor em estoque",
                    "Maior venda diária"
                ],
                key="estoque_ordenacao"
            )

        filtrado = estoque.copy()
        if busca:
            corresponde = (
                filtrado["produto"].astype(str).str.contains(
                    busca,
                    case=False,
                    regex=False,
                    na=False
                )
                | filtrado["sku"].astype(str).str.contains(
                    busca,
                    case=False,
                    regex=False,
                    na=False
                )
            )
            filtrado = filtrado[corresponde]
        if status_selecionado != "Todos":
            filtrado = filtrado[
                filtrado["status_estoque"] == status_selecionado
            ]

        ordem_colunas = {
            "Menor cobertura": ("dias_estoque", True),
            "Maior valor em estoque": ("valor_estoque", False),
            "Maior venda diária": ("media_vendas_dia", False)
        }
        coluna_ordem, crescente = ordem_colunas[ordem_selecionada]
        filtrado = filtrado.sort_values(
            coluna_ordem,
            ascending=crescente
        )

        st.caption(f"{len(filtrado)} produtos encontrados")

        tabela = filtrado[
            [
                "produto",
                "sku",
                "estoque_atual",
                "media_vendas_dia",
                "dias_estoque",
                "ponto_reposicao",
                "valor_estoque",
                "status_estoque"
            ]
        ].copy()
        tabela.columns = [
            "Produto",
            "SKU",
            "Estoque",
            "Vendas/dia",
            "Cobertura",
            "Ponto de reposição",
            "Valor em estoque",
            "Status"
        ]
        tabela["Estoque"] = tabela["Estoque"].map(
            lambda valor: f"{valor:.0f}"
        )
        tabela["Vendas/dia"] = tabela["Vendas/dia"].map(
            lambda valor: f"{valor:.2f}"
        )
        tabela["Cobertura"] = tabela["Cobertura"].map(
            lambda valor: (
                "Sem giro"
                if valor == float("inf")
                else f"{valor:.1f} dias"
            )
        )
        tabela["Ponto de reposição"] = tabela[
            "Ponto de reposição"
        ].map(lambda valor: f"{valor:.0f}")
        tabela["Valor em estoque"] = tabela["Valor em estoque"].map(
            _moeda
        )

        tabela_limpa(
            tabela,
            badges={
                "Status": {
                    "Sem estoque": "urgent",
                    "Crítico": "urgent",
                    "Atenção": "warning",
                    "Normal": "positive",
                    "Sem vendas": "muted"
                }
            },
            chave="diagnostico_estoque"
        )
