from html import escape

import pandas as pd
import streamlit as st

from componentes import card_destaque, tabela_limpa


def _moeda(valor: float) -> str:
    return (
        f"R$ {valor:,.2f}"
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )


def _ranking_visual(
    dados: pd.DataFrame,
    *,
    titulo: str,
    subtitulo: str,
    coluna_valor: str,
    formatador,
    classe: str = ""
) -> None:
    if dados.empty:
        with st.container(border=True):
            st.markdown(
                f"""
                <div class="mi-chart-heading mi-dashboard-panel">
                    <div class="mi-chart-title">{escape(titulo)}</div>
                    <div class="mi-chart-subtitle">{escape(subtitulo)}</div>
                </div>
                <div class="mi-product-ranking">
                    <div class="mi-product-ranking-empty">
                        Sem produtos com vendas no período selecionado.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        return

    maiores = dados.nlargest(10, coluna_valor).reset_index(drop=True)
    maior_valor = float(maiores[coluna_valor].max()) if not maiores.empty else 0

    linhas = []
    for indice, produto in maiores.iterrows():
        valor = float(produto[coluna_valor])
        largura = max(valor / maior_valor * 100, 2) if maior_valor > 0 else 0
        nome = escape(str(produto["produto"]))
        valor_formatado = escape(formatador(valor))
        classe_animacao = (
            " build"
            if st.session_state.get("_mi_page_entering", False)
            else ""
        )
        atraso_animacao = (
            f"animation-delay:{min(indice * 65, 585)}ms;"
            if classe_animacao
            else ""
        )
        linhas.append(
            f"""
            <div class="mi-product-ranking-row {classe}">
                <span class="mi-product-ranking-position">{indice + 1}</span>
                <span class="mi-product-ranking-name" title="{nome}">
                    {nome}
                </span>
                <span class="mi-product-ranking-bar-track">
                    <span class="mi-product-ranking-bar{classe_animacao}"
                          style="width:{largura:.1f}%;{atraso_animacao}"></span>
                </span>
                <span class="mi-product-ranking-value">
                    {valor_formatado}
                </span>
            </div>
            """
        )

    if not linhas:
        linhas.append(
            '<div class="mi-product-ranking-empty">'
            "Sem produtos com vendas no período selecionado."
            "</div>"
        )

    with st.container(border=True):
        st.markdown(
            f"""
            <div class="mi-chart-heading mi-dashboard-panel">
                <div class="mi-chart-title">{escape(titulo)}</div>
                <div class="mi-chart-subtitle">{escape(subtitulo)}</div>
            </div>
            <div class="mi-product-ranking">
                {''.join(linhas)}
            </div>
            """,
            unsafe_allow_html=True
        )


def _formatar_cobertura(valor: float) -> str:
    if valor == float("inf"):
        return "Sem giro"
    return f"{valor:.1f} dias"


def mostrar_produtos(produtos: pd.DataFrame) -> None:
    vendidos = produtos[produtos["unidades"] > 0].copy()
    catalogo = produtos.copy()

    catalogo["faturamento_liquido"] = (
        catalogo["faturamento"] - catalogo["descontos"]
        - catalogo["taxas"] - catalogo["frete"]
    )

    st.markdown("### 🏆 Desempenho dos produtos")
    st.caption(
        "Rankings e indicadores do catálogo para o período selecionado. "
        "A margem considera também o investimento em publicidade atribuído."
    )

    st.html(
        """
        <style>
            .mi-product-ranking {
                display: flex;
                flex-direction: column;
                gap: 2px;
                padding-top: 3px;
            }
            .mi-product-ranking-row {
                display: grid;
                grid-template-columns: 18px minmax(110px, 1fr)
                    minmax(45px, 90px) minmax(75px, 105px);
                align-items: center;
                gap: 9px;
                min-height: 27px;
                color: #E2E8F0;
                font-size: 12px;
            }
            .mi-product-ranking-position {
                color: #8292A8;
                font-variant-numeric: tabular-nums;
            }
            .mi-product-ranking-name {
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
            }
            .mi-product-ranking-bar-track {
                overflow: hidden;
                height: 6px;
                border-radius: 99px;
                background: #1E293B;
            }
            .mi-product-ranking-bar {
                display: block;
                height: 100%;
                border-radius: inherit;
                background: #3B82F6;
                transition: width 350ms ease;
            }
            .mi-product-ranking-bar.build {
                transform-origin: left center;
                animation: mi-ranking-build 850ms
                    cubic-bezier(.22,.61,.36,1) both;
            }
            @keyframes mi-ranking-build {
                from { transform: scaleX(0); }
                to { transform: scaleX(1); }
            }
            .mi-product-ranking-row.margin .mi-product-ranking-bar {
                background: #22C55E;
            }
            .mi-product-ranking-value {
                color: #F1F5F9;
                font-size: 12px;
                font-variant-numeric: tabular-nums;
                font-weight: 650;
                text-align: right;
                white-space: nowrap;
            }
            .mi-product-ranking-empty {
                padding: 18px 2px;
                color: #A8B6C9;
                font-size: 13px;
            }
            @media (max-width: 700px) {
                .mi-product-ranking-row {
                    grid-template-columns: 16px minmax(80px, 1fr)
                        minmax(36px, 60px) minmax(68px, 90px);
                    gap: 6px;
                    font-size: 11px;
                }
                .mi-product-ranking-value {
                    font-size: 11px;
                }
            }
            @media (prefers-reduced-motion: reduce) {
                .mi-product-ranking-bar.build {
                    animation: none;
                }
            }
        </style>
        """
    )

    ranking_faturamento, ranking_margem = st.columns(2, gap="medium")
    with ranking_faturamento:
        _ranking_visual(
            vendidos,
            titulo="Top 10 Produtos por Faturamento",
            subtitulo="Maior faturamento bruto no período",
            coluna_valor="faturamento",
            formatador=_moeda
        )
    with ranking_margem:
        _ranking_visual(
            vendidos,
            titulo="Top 10 Produtos por Margem",
            subtitulo="Maior margem após custos e anúncios",
            coluna_valor="margem",
            formatador=lambda valor: f"{valor:.1f}%",
            classe="margin"
        )

    if not vendidos.empty:
        maior_venda = vendidos.loc[vendidos["faturamento"].idxmax()]
        maior_margem = vendidos.loc[vendidos["margem"].idxmax()]
        maior_roas = vendidos.loc[vendidos["roas"].idxmax()]

        destaque_vendas, destaque_margem, destaque_roas = st.columns(3)
        with destaque_vendas:
            card_destaque(
                "Maior faturamento",
                maior_venda["produto"],
                _moeda(maior_venda["faturamento"]),
                "🏆",
                "Produto com maior faturamento bruto no período"
            )
        with destaque_margem:
            card_destaque(
                "Maior margem após anúncios",
                maior_margem["produto"],
                f'{maior_margem["margem"]:.1f}%',
                "💎",
                "Maior margem entre produtos com unidades vendidas"
            )
        with destaque_roas:
            card_destaque(
                "Melhor ROAS",
                maior_roas["produto"],
                f'{maior_roas["roas"]:.2f}x',
                "📢",
                "Maior retorno atribuído por real investido em anúncios"
            )

    st.markdown("### 📋 Portfólio de produtos")
    st.caption(
        f"Catálogo completo: {len(catalogo)} produtos, com dados cadastrais, "
        "desempenho no período e situação de estoque."
    )

    st.markdown(
        '<div class="mi-table-filters-anchor"></div>',
        unsafe_allow_html=True,
    )
    filtro_busca, filtro_categoria, filtro_status, filtro_ordem = st.columns(
        [2, 1.4, 1.2, 1.4],
        gap="small"
    )
    with filtro_busca:
        busca = st.text_input(
            "Buscar produto ou SKU",
            placeholder="Digite um produto ou SKU...",
            key="portfolio_produtos_busca"
        ).strip()
    with filtro_categoria:
        categorias = ["Todas"] + sorted(
            catalogo["categoria"].dropna().astype(str).unique().tolist()
        )
        categoria_selecionada = st.selectbox(
            "Categoria",
            categorias,
            key="portfolio_produtos_categoria"
        )
    with filtro_status:
        status_opcoes = ["Todos"] + sorted(
            catalogo["classificacao"].dropna().astype(str).unique().tolist()
        )
        status_selecionado = st.selectbox(
            "Status",
            status_opcoes,
            key="portfolio_produtos_status"
        )
    with filtro_ordem:
        ordem = st.selectbox(
            "Ordenar por",
            [
                "Maior faturamento",
                "Maior margem",
                "Maior resultado",
                "Menor cobertura"
            ],
            key="portfolio_produtos_ordem"
        )

    filtrado = catalogo.copy()
    if busca:
        condicao = (
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
        filtrado = filtrado[condicao]
    if categoria_selecionada != "Todas":
        filtrado = filtrado[
            filtrado["categoria"] == categoria_selecionada
        ]
    if status_selecionado != "Todos":
        filtrado = filtrado[
            filtrado["classificacao"] == status_selecionado
        ]

    ordem_colunas = {
        "Maior faturamento": ("faturamento", False),
        "Maior margem": ("margem", False),
        "Maior resultado": ("resultado", False),
        "Menor cobertura": ("dias_estoque", True)
    }
    coluna_ordem, crescente = ordem_colunas[ordem]
    filtrado = filtrado.sort_values(
        coluna_ordem,
        ascending=crescente
    )
    st.caption(f"{len(filtrado)} produtos encontrados")

    tabela = filtrado[
        [
            "sku",
            "produto",
            "categoria",
            "canal",
            "preco_venda",
            "custo_unitario",
            "unidades",
            "faturamento",
            "faturamento_liquido",
            "resultado",
            "margem",
            "roas",
            "estoque_atual",
            "dias_estoque",
            "classificacao"
        ]
    ].copy()
    tabela.columns = [
        "SKU",
        "Produto",
        "Categoria",
        "Canal",
        "Preço",
        "Custo unitário",
        "Unidades",
        "Faturamento bruto",
        "Faturamento líquido",
        "Resultado após anúncios",
        "Margem após anúncios",
        "ROAS",
        "Estoque",
        "Cobertura",
        "Status"
    ]

    for coluna in [
        "Preço",
        "Custo unitário",
        "Faturamento bruto",
        "Faturamento líquido",
        "Resultado após anúncios"
    ]:
        tabela[coluna] = tabela[coluna].map(_moeda)

    tabela["Unidades"] = tabela["Unidades"].map(
        lambda valor: f"{valor:,.0f}".replace(",", ".")
    )
    tabela["Margem após anúncios"] = tabela[
        "Margem após anúncios"
    ].map(lambda valor: f"{valor:.1f}%")
    tabela["ROAS"] = tabela["ROAS"].map(
        lambda valor: f"{valor:.2f}x"
    )
    tabela["Estoque"] = tabela["Estoque"].map(
        lambda valor: f"{valor:,.0f}".replace(",", ".")
    )
    tabela["Cobertura"] = tabela["Cobertura"].map(_formatar_cobertura)

    with st.container(border=True):
        st.markdown(
            """
            <div class="mi-chart-heading mi-dashboard-panel">
                <div class="mi-chart-title">📋 Tabela de produtos</div>
                <div class="mi-chart-subtitle">
                    Cadastro, vendas, rentabilidade e estoque por produto
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        tabela_limpa(
            tabela,
            badges={
                "Canal": {
                    "Mercado Livre": "ml",
                    "Shopee": "shopee",
                    "Ambos": "info",
                    "Sem vendas": "muted"
                },
                "Status": {
                    "Risco operacional": "urgent",
                    "Reposição urgente": "urgent",
                    "Alta performance": "positive",
                    "Alta margem": "info",
                    "Baixo giro": "muted",
                    "Atenção": "warning",
                    "Normal": "positive"
                }
            },
            chave="portfolio_produtos",
            linhas_por_pagina=10
        )
