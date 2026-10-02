from html import escape

import streamlit as st
import pandas as pd
import plotly.express as px
from componentes import grafico_dashboard, tabela_limpa
from armazenamento import ler_dataset


def mostrar_marketplace():

    st.divider()

    # ============================================================
    # FILTRO GLOBAL
    # ============================================================

    data_inicio = st.session_state.get("data_inicio")
    data_fim = st.session_state.get("data_fim")
    produto_selecionado = st.session_state.get("produto_global")
    if produto_selecionado == "Todos os produtos":
        produto_selecionado = None
    marketplace_selecionado = st.session_state.get("marketplace_global")
    if marketplace_selecionado == "Todos":
        marketplace_selecionado = None

    if data_inicio is None or data_fim is None:

        st.warning(
            "Selecione um período na barra lateral."
        )

        st.stop()


    # ============================================================
    # CARREGAMENTO DOS DADOS
    # ============================================================

    pedidos = ler_dataset("dados/pedidos.csv")
    produtos = ler_dataset("dados/produtos.csv")
    publicidade = ler_dataset("dados/publicidade.csv")

    if "desconto" not in pedidos.columns:
        pedidos["desconto"] = 0.0
    pedidos["desconto"] = pd.to_numeric(
        pedidos["desconto"],
        errors="coerce",
    ).fillna(0)
    pedidos["data"] = pd.to_datetime(pedidos["data"])
    publicidade["data"] = pd.to_datetime(publicidade["data"])


    # ============================================================
    # FILTRO DOS DADOS
    # ============================================================

    pedidos_validos = pedidos[
        pedidos["status"] == "Concluído"
    ].copy()
    if produto_selecionado is not None:
        pedidos_validos = pedidos_validos[
            pedidos_validos["produto"] == produto_selecionado
        ].copy()
    if marketplace_selecionado is not None:
        pedidos_validos = pedidos_validos[
            pedidos_validos["marketplace"] == marketplace_selecionado
        ].copy()


    pedidos_periodo = pedidos_validos[
        (pedidos_validos["data"].dt.date >= data_inicio)
        & (pedidos_validos["data"].dt.date <= data_fim)
    ].copy()


    publicidade_periodo = publicidade[
        (publicidade["data"].dt.date >= data_inicio)
        & (publicidade["data"].dt.date <= data_fim)
    ].copy()
    if produto_selecionado is not None:
        skus_selecionados = produtos.loc[
            produtos["produto"] == produto_selecionado,
            "sku"
        ]
        publicidade_periodo = publicidade_periodo[
            publicidade_periodo["sku"].isin(skus_selecionados)
        ].copy()
    if marketplace_selecionado is not None:
        publicidade_periodo = publicidade_periodo[
            publicidade_periodo["marketplace"] == marketplace_selecionado
        ].copy()


    # ============================================================
    # CUSTO DOS PRODUTOS
    # ============================================================

    pedidos_periodo = pedidos_periodo.merge(
        produtos[
            [
                "sku",
                "custo_unitario"
            ]
        ],
        on="sku",
        how="left"
    )


    pedidos_periodo["custo_produto"] = (
        pedidos_periodo["quantidade"]
        * pedidos_periodo["custo_unitario"]
    )


    # ============================================================
    # CÁLCULO POR MARKETPLACE
    # ============================================================

    resumo = []

    for marketplace in ["Mercado Livre", "Shopee"]:

        pedidos_marketplace = pedidos_periodo[
            pedidos_periodo["marketplace"] == marketplace
        ].copy()


        publicidade_marketplace = publicidade_periodo[
            publicidade_periodo["marketplace"] == marketplace
        ].copy()


        faturamento = pedidos_marketplace[
            "faturamento_bruto"
        ].sum()


        pedidos_total = len(
            pedidos_marketplace
        )


        custo_produtos = pedidos_marketplace[
            "custo_produto"
        ].sum()


        taxas = pedidos_marketplace[
            "taxa_marketplace"
        ].sum()

        descontos = pedidos_marketplace[
            "desconto"
        ].sum()

        frete = pedidos_marketplace[
            "frete_vendedor"
        ].sum()

        investimento_publicidade = publicidade_marketplace[
            "investimento"
        ].sum()


        receita_publicidade = publicidade_marketplace[
            "receita_atribuida"
        ].sum()


        resultado = (
            faturamento
            - descontos
            - custo_produtos
            - taxas
            - frete
            - investimento_publicidade
        )


        margem = (
            (
                resultado / (faturamento - descontos)
            ) * 100
            if faturamento - descontos > 0
            else 0
        )


        roas = (
            receita_publicidade
            / investimento_publicidade
            if investimento_publicidade > 0
            else 0
        )

        ticket_medio = (
            (faturamento - descontos) / pedidos_total
            if pedidos_total > 0
            else 0
        )


        resumo.append(
            {
                "marketplace": marketplace,
                "tem_vendas": pedidos_total > 0,
                "tem_publicidade": not publicidade_marketplace.empty,
                "faturamento": faturamento,
                "descontos": descontos,
                "pedidos": pedidos_total,
                "unidades": pedidos_marketplace["quantidade"].sum(),
                "ticket_medio": ticket_medio,
                "taxas": taxas,
                "margem": margem,
                "roas": roas,
                "investimento_publicidade": investimento_publicidade,
                "resultado": resultado
            }
        )


    dados = pd.DataFrame(resumo)

    # ============================================================
    # COMPARATIVO DE INDICADORES
    # ============================================================

    frete_por_marketplace = (
        pedidos_periodo.groupby("marketplace")["frete_vendedor"]
        .sum()
    )
    faturamento_liquido = (
        dados["faturamento"] - dados["descontos"] - dados["taxas"]
        - dados["marketplace"].map(
            frete_por_marketplace
        )
    ).fillna(0)
    dados["faturamento_liquido"] = faturamento_liquido
    dados["resultado_vendas"] = dados["resultado"]
    dados["taxa_percentual"] = (
        dados["taxas"]
        .div(dados["faturamento"].replace(0, pd.NA))
        .mul(100)
        .fillna(0)
    )
    comparativo = dados.set_index("marketplace")

    metricas = [
        ("Faturamento bruto", "faturamento", "currency", False),
        ("Faturamento líquido", "faturamento_liquido", "currency", False),
        ("Descontos", "descontos", "currency", True),
        ("Pedidos", "pedidos", "integer", False),
        ("Unidades", "unidades", "integer", False),
        ("Ticket médio", "ticket_medio", "currency", False),
        ("Resultado das vendas", "resultado_vendas", "currency", False),
        ("Margem das vendas", "margem", "percent", False),
        (
            "Investimento em publicidade",
            "investimento_publicidade",
            "currency",
            None
        ),
        ("ROAS", "roas", "number", False),
        ("Taxas", "taxas", "currency", True),
        ("Taxa %", "taxa_percentual", "percent", True)
    ]

    def moeda_br(valor: float) -> str:
        return (
            f"R$ {valor:,.2f}"
            .replace(",", "X")
            .replace(".", ",")
            .replace("X", ".")
        )

    publicidade_metricas = {
        "investimento_publicidade",
        "roas",
    }
    tabela_comparativa = []
    for titulo, coluna, formato, menor_melhor in metricas:
        mercado_livre = comparativo.loc["Mercado Livre", coluna]
        shopee = comparativo.loc["Shopee", coluna]
        if coluna in publicidade_metricas:
            ml_disponivel = bool(
                comparativo.loc["Mercado Livre", "tem_publicidade"]
            )
            shopee_disponivel = bool(
                comparativo.loc["Shopee", "tem_publicidade"]
            )
            if coluna == "roas":
                ml_disponivel = ml_disponivel and (
                    comparativo.loc["Mercado Livre", "investimento_publicidade"]
                    > 0
                )
                shopee_disponivel = shopee_disponivel and (
                    comparativo.loc["Shopee", "investimento_publicidade"] > 0
                )
        else:
            ml_disponivel = bool(
                comparativo.loc["Mercado Livre", "tem_vendas"]
            )
            shopee_disponivel = bool(
                comparativo.loc["Shopee", "tem_vendas"]
            )

        def formatar_valor(valor: float, disponivel: bool) -> str:
            if not disponivel or pd.isna(valor):
                return "Sem dados"
            if formato == "currency":
                return moeda_br(valor)
            if formato == "percent":
                return f"{valor:.1f}%"
            if formato == "number":
                return f"{valor:.2f}x"
            if formato == "integer":
                return f"{valor:,.0f}".replace(",", ".")
            return f"{valor:.2f}"

        valor_ml = formatar_valor(mercado_livre, ml_disponivel)
        valor_shopee = formatar_valor(shopee, shopee_disponivel)

        if not ml_disponivel or not shopee_disponivel:
            lider_texto = "Dados insuficientes"
        elif menor_melhor is None:
            lider_texto = "Informativo"
        elif mercado_livre == shopee:
            lider = "Empate"
            lider_texto = lider
        elif (mercado_livre < shopee) == menor_melhor:
            lider = "Mercado Livre"
            lider_texto = lider
        else:
            lider = "Shopee"
            lider_texto = lider
        if menor_melhor and lider_texto not in {"Empate", "Informativo"}:
            lider_texto = f"{lider_texto} (menor)"

        tabela_comparativa.append(
            {
                "Indicador": titulo,
                "Mercado Livre": valor_ml,
                "Shopee": valor_shopee,
                "Líder": lider_texto
            }
        )

    with st.container(border=True):
        st.markdown(
            """
            <div class="mi-chart-heading mi-dashboard-panel">
                <div class="mi-chart-title">📊 Comparativo de indicadores</div>
                <div class="mi-chart-subtitle">
                    Valores e liderança de cada métrica no período selecionado
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        tabela_limpa(
            pd.DataFrame(tabela_comparativa),
            badges={
                "Mercado Livre": {"Sem dados": "muted"},
                "Shopee": {"Sem dados": "muted"},
                "Líder": {
                    "Mercado Livre": "ml",
                    "Mercado Livre (menor)": "ml",
                    "Shopee": "shopee",
                    "Shopee (menor)": "shopee",
                    "Empate": "tie",
                    "Dados insuficientes": "muted",
                    "Informativo": "muted",
                }
            },
            chave="comparativo_marketplaces",
            linhas_por_pagina=len(tabela_comparativa)
        )
        st.caption(
            "“Sem dados” indica que não há pedidos concluídos ou relatório "
            "de publicidade para aquele marketplace no período selecionado."
        )

    # ============================================================
    # DESEMPENHO POR PRODUTO E CANAL
    # ============================================================

    produto_canal = pedidos_periodo.groupby(
        ["sku", "produto", "marketplace"],
        as_index=False
    ).agg(
        pedidos=("id_pedido", "count"),
        unidades=("quantidade", "sum"),
        faturamento=("faturamento_bruto", "sum"),
        custo_produtos=("custo_produto", "sum"),
        taxas=("taxa_marketplace", "sum"),
        frete=("frete_vendedor", "sum"),
        descontos=("desconto", "sum"),
    )

    publicidade_produto_canal = publicidade_periodo.groupby(
        ["sku", "marketplace"],
        as_index=False
    ).agg(
        publicidade=("investimento", "sum"),
        receita_atribuida=("receita_atribuida", "sum")
    )

    produto_canal = produto_canal.merge(
        publicidade_produto_canal,
        on=["sku", "marketplace"],
        how="left"
    )

    produto_canal[
        ["publicidade", "receita_atribuida"]
    ] = produto_canal[
        ["publicidade", "receita_atribuida"]
    ].fillna(0)

    produto_canal["resultado"] = (
        produto_canal["faturamento"]
        - produto_canal["descontos"]
        - produto_canal["custo_produtos"]
        - produto_canal["taxas"]
        - produto_canal["frete"]
        - produto_canal["publicidade"]
    )
    produto_canal["margem"] = (
        produto_canal["resultado"]
        .div(
            (produto_canal["faturamento"] - produto_canal["descontos"])
            .where(
                (produto_canal["faturamento"] - produto_canal["descontos"])
                .ne(0)
            )
        )
        .mul(100)
        .fillna(0)
    )
    produto_canal["ticket_medio"] = (
        (produto_canal["faturamento"] - produto_canal["descontos"])
        .div(produto_canal["pedidos"].replace(0, pd.NA))
        .fillna(0)
    )

    tabela_canais = produto_canal.pivot(
        index=["sku", "produto"],
        columns="marketplace",
        values=["margem", "faturamento", "pedidos", "unidades"]
    ).reset_index()
    tabela_canais.columns = [
        "_".join(coluna).strip("_").lower()
        if isinstance(coluna, tuple)
        else coluna
        for coluna in tabela_canais.columns
    ]

    for coluna in [
        "margem_mercado livre",
        "margem_shopee",
        "faturamento_mercado livre",
        "faturamento_shopee",
        "pedidos_mercado livre",
        "pedidos_shopee",
        "unidades_mercado livre",
        "unidades_shopee"
    ]:
        if coluna not in tabela_canais:
            tabela_canais[coluna] = 0

    colunas_numericas = [
        "margem_mercado livre",
        "margem_shopee",
        "faturamento_mercado livre",
        "faturamento_shopee",
        "pedidos_mercado livre",
        "pedidos_shopee",
        "unidades_mercado livre",
        "unidades_shopee"
    ]
    tabela_canais[colunas_numericas] = (
        tabela_canais[colunas_numericas].fillna(0)
    )

    tabela_canais["melhor_canal"] = tabela_canais.apply(
        lambda linha: (
            "Mercado Livre"
            if linha["margem_mercado livre"] >= linha["margem_shopee"]
            else "Shopee"
        ),
        axis=1
    )
    tabela_canais["diferença_margem"] = (
        tabela_canais["margem_mercado livre"]
        - tabela_canais["margem_shopee"]
    ).abs()


    # ============================================================
    # PAINEL COMPACTO DOS CANAIS
    # ============================================================

    st.divider()
    st.subheader("🏪 Comparativo visual dos canais")

    col_grafico, col_participacao = st.columns(
        [2, 1],
        gap="medium"
    )

    with col_grafico:
        grafico_faturamento = px.bar(
            dados,
            x="marketplace",
            y="faturamento",
            color="marketplace",
            color_discrete_map={
                "Mercado Livre": "#F5B700",
                "Shopee": "#F4513A"
            }
        )
        grafico_faturamento.update_traces(
            hovertemplate=(
                "<b>%{x}</b><br>"
                "Faturamento: R$ %{y:,.2f}<extra></extra>"
            )
        )
        grafico_faturamento.update_layout(
            height=190,
            template="plotly_dark",
            showlegend=False,
            xaxis_title="",
            yaxis_title="",
            transition={"duration": 500, "easing": "cubic-in-out"},
            margin=dict(l=20, r=20, t=8, b=12)
        )
        grafico_dashboard(
            grafico_faturamento,
            titulo="Faturamento por Canal",
            subtitulo="Comparação de faturamento entre os marketplaces"
        )

    with col_participacao:
        grafico_resultado = px.pie(
            dados,
            names="marketplace",
            values="faturamento",
            hole=0.68,
            color="marketplace",
            color_discrete_map={
                "Mercado Livre": "#F5B700",
                "Shopee": "#F4513A"
            }
        )
        grafico_resultado.update_traces(
            textinfo="percent",
            hovertemplate=(
                "<b>%{label}</b><br>"
                "Faturamento: R$ %{value:,.2f}<br>"
                "Participação: %{percent}<extra></extra>"
            )
        )
        grafico_resultado.update_layout(
            height=170,
            template="plotly_dark",
            showlegend=False,
            transition={"duration": 500, "easing": "cubic-in-out"},
            margin=dict(l=8, r=8, t=4, b=4)
        )
        grafico_resultado.update_traces(
            domain={"x": [0.08, 0.92], "y": [0.04, 0.96]}
        )
        itens_legenda = []
        for _, linha in dados.iterrows():
            canal = str(linha["marketplace"])
            cor = {
                "Mercado Livre": "#F5B700",
                "Shopee": "#F4513A"
            }.get(canal, "#A8B6C9")
            itens_legenda.append(
                '<span style="display:inline-flex;align-items:center;'
                'gap:5px;">'
                f'<span style="width:8px;height:8px;border-radius:2px;'
                f'background:{cor};"></span>'
                f'{escape(canal)}</span>'
            )
        legenda_participacao = "".join(itens_legenda)
        legenda_participacao_html = (
            '<div style="display:flex;justify-content:center;'
            'align-items:center;gap:12px;flex-wrap:wrap;'
            'margin:-2px 0 2px;color:#A8B6C9;'
            'font-size:9px;line-height:1.3;">'
            f"{legenda_participacao}</div>"
        )
        grafico_dashboard(
            grafico_resultado,
            titulo="Participação no Faturamento",
            subtitulo="Divisão do faturamento entre os canais",
            rodape_html=legenda_participacao_html
        )

    col_unidades, col_pedidos = st.columns(2, gap="medium")

    for coluna, titulo, campo, rotulo in [
        (col_unidades, "📦 Unidades por canal", "unidades", "Unidades"),
        (col_pedidos, "🛒 Pedidos por canal", "pedidos", "Pedidos")
    ]:
        with coluna:
            grafico = px.bar(
                dados,
                x="marketplace",
                y=campo,
                color="marketplace",
                color_discrete_map={
                    "Mercado Livre": "#F5B700",
                    "Shopee": "#F4513A"
                }
            )
            grafico.update_traces(
                hovertemplate=(
                    "<b>%{x}</b><br>"
                    f"{rotulo}: %{{y}}<extra></extra>"
                )
            )
            grafico.update_layout(
                height=165,
                template="plotly_dark",
                showlegend=False,
                xaxis_title="",
                yaxis_title="",
                margin=dict(l=20, r=20, t=8, b=12)
            )
            grafico_dashboard(
                grafico,
                titulo=titulo,
                subtitulo=f"Comparação de {rotulo.lower()} entre canais"
            )

    # ============================================================
    # MELHOR CANAL POR PRODUTO
    # ============================================================

    tabela = tabela_canais[
        [
            "produto",
            "melhor_canal",
            "margem_mercado livre",
            "margem_shopee",
            "diferença_margem",
            "faturamento_mercado livre",
            "faturamento_shopee"
        ]
    ].copy()
    tabela.columns = [
        "Produto",
        "Melhor canal",
        "Margem Mercado Livre",
        "Margem Shopee",
        "Diferença de margem",
        "Faturamento Mercado Livre",
        "Faturamento Shopee"
    ]
    tabela["Margem Mercado Livre"] = tabela[
        "Margem Mercado Livre"
    ].map(lambda valor: f"{valor:.1f}%")
    tabela["Margem Shopee"] = tabela["Margem Shopee"].map(
        lambda valor: f"{valor:.1f}%"
    )
    tabela["Diferença de margem"] = tabela[
        "Diferença de margem"
    ].map(lambda valor: f"{valor:.1f} p.p.")
    tabela["Faturamento Mercado Livre"] = tabela[
        "Faturamento Mercado Livre"
    ].map(lambda valor: f"R$ {valor:,.0f}")
    tabela["Faturamento Shopee"] = tabela[
        "Faturamento Shopee"
    ].map(lambda valor: f"R$ {valor:,.0f}")

    with st.container(border=True):
        st.markdown(
            """
            <div class="mi-chart-heading mi-dashboard-panel">
                <div class="mi-chart-title">🧭 Melhor canal por produto</div>
                <div class="mi-chart-subtitle">
                    Margem após custo dos produtos, taxas, frete do vendedor
                    e publicidade atribuída; resultado estimado, não é o
                    repasse líquido recebido.
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        tabela_limpa(
            tabela,
            badges={
                "Melhor canal": {
                    "Mercado Livre": "ml",
                    "Shopee": "shopee"
                }
            },
            chave="melhor_canal_produto"
        )