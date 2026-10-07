from html import escape

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from componentes import (
    LinhaParticipacaoCanal,
    PALETA_DADOS,
    PALETA_MARKETPLACES,
    formatar_moeda_br,
    formatar_multiplicador_br,
    formatar_percentual_br,
    grafico_dashboard,
    icone_svg,
    proxima_animacao_entrada_pagina,
    renderizar_card_participacao_canal,
    tabela_limpa,
    titulo_secao,
)
from armazenamento import ler_dataset


def _marcar_comparacoes_por_produto(
    tabela_canais: pd.DataFrame,
) -> pd.DataFrame:
    tabela = tabela_canais.copy()
    tabela["tem_comparacao"] = (
        tabela["pedidos_mercado livre"].gt(0)
        & tabela["pedidos_shopee"].gt(0)
    )
    tabela["melhor_canal"] = tabela.apply(
        lambda linha: (
            (
                "Mercado Livre"
                if linha["margem_mercado livre"]
                >= linha["margem_shopee"]
                else "Shopee"
            )
            if linha["tem_comparacao"]
            else "Sem comparação"
        ),
        axis=1,
    )
    tabela["diferença_margem"] = (
        tabela["margem_mercado livre"]
        - tabela["margem_shopee"]
    ).abs()
    tabela.loc[~tabela["tem_comparacao"], "diferença_margem"] = pd.NA
    return tabela


def mostrar_marketplace(*, skeleton_slot=None):

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
        if skeleton_slot is not None:
            skeleton_slot.empty()

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
    if skeleton_slot is not None:
        skeleton_slot.empty()

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

    canais_com_vendas = dados.loc[dados["tem_vendas"], "marketplace"].tolist()
    if not canais_com_vendas:
        st.info("Não há vendas concluídas para comparar no período selecionado.")
        return

    comparativo = dados.set_index("marketplace")

    metricas = [
        ("Faturamento bruto", "faturamento", "currency", False),
        ("Faturamento líquido", "faturamento_liquido", "currency", False),
        ("Descontos", "descontos", "currency", True),
        ("Taxas", "taxas", "currency", True),
        ("Taxa %", "taxa_percentual", "percent", True),
        ("Resultado das vendas", "resultado_vendas", "currency", False),
        ("Margem das vendas", "margem", "percent", False),
        ("Pedidos", "pedidos", "integer", False),
        ("Unidades", "unidades", "integer", False),
        ("Ticket médio", "ticket_medio", "currency", False),
        (
            "Investimento em publicidade",
            "investimento_publicidade",
            "currency",
            None
        ),
        ("ROAS", "roas", "number", False),
    ]

    publicidade_metricas = {
        "investimento_publicidade",
        "roas",
    }
    tem_comparacao_canais = len(canais_com_vendas) > 1
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
                return "—"
            if formato == "currency":
                return formatar_moeda_br(valor)
            if formato == "percent":
                return formatar_percentual_br(valor)
            if formato == "number":
                return formatar_multiplicador_br(valor)
            if formato == "integer":
                return f"{valor:,.0f}".replace(",", ".")
            return f"{valor:.2f}"

        valor_ml = formatar_valor(mercado_livre, ml_disponivel)
        valor_shopee = formatar_valor(shopee, shopee_disponivel)

        linha_comparativa = {
            "Indicador": titulo,
            "Mercado Livre": valor_ml,
            "Shopee": valor_shopee,
        }
        if tem_comparacao_canais:
            if not ml_disponivel or not shopee_disponivel:
                lider_texto = "—"
            elif menor_melhor is None:
                lider_texto = "Informativo"
            elif mercado_livre == shopee:
                lider_texto = "Empate"
            else:
                lider = (
                    "Mercado Livre"
                    if (mercado_livre < shopee) == menor_melhor
                    else "Shopee"
                )
                lider_texto = (
                    f"{lider} (menor)" if menor_melhor else lider
                )
            linha_comparativa["Líder"] = lider_texto
        tabela_comparativa.append(linha_comparativa)

    mercado_livre_tem_vendas = bool(
        comparativo.loc["Mercado Livre", "tem_vendas"]
    )
    shopee_tem_vendas = bool(comparativo.loc["Shopee", "tem_vendas"])
    shopee_em_breve = not shopee_tem_vendas
    if not tem_comparacao_canais:
        for linha in tabela_comparativa:
            if not mercado_livre_tem_vendas:
                linha["Mercado Livre"] = "—"
            if not shopee_tem_vendas:
                linha["Shopee"] = "—"

    tabela_comparativa_df = pd.DataFrame(tabela_comparativa)
    coluna_comparativo, coluna_participacao = st.columns(
        [1.25, 1],
        gap="medium",
        vertical_alignment="top",
    )
    with coluna_comparativo:
        titulo_secao(
            "Comparativo de indicadores",
            "Valores dos marketplaces no período selecionado.",
        )
        classe_entrada, atraso_entrada = proxima_animacao_entrada_pagina()
        if classe_entrada:
            st.markdown(
                '<span class="mi-marketplace-table-entering" '
                f'style="--mi-entry-delay:{atraso_entrada}ms"></span>',
                unsafe_allow_html=True,
            )
        tabela_limpa(
            tabela_comparativa_df,
            badges={
                "Líder": {
                    "Mercado Livre": "ml",
                    "Mercado Livre (menor)": "ml",
                    "Shopee": "shopee",
                    "Shopee (menor)": "shopee",
                    "Empate": "tie",
                    "Informativo": "muted",
                }
            },
            chave="comparativo_marketplaces",
            linhas_por_pagina=len(tabela_comparativa),
            colunas_discretas=("Shopee",) if shopee_em_breve else (),
            badges_cabecalho=(
                {"Shopee": ("Em breve", "muted")}
                if shopee_em_breve
                else {}
            ),
            grupos_linhas={
                "Faturamento bruto": "Financeiro",
                "Pedidos": "Operacional",
            },
            pontos_cabecalho=("Mercado Livre",),
            largura_maxima_px=760,
            largura_minima_px=480,
            borda_externa=False,
            compacta=True,
        )
        if not tem_comparacao_canais:
            marketplace_ausente = (
                "Shopee" if mercado_livre_tem_vendas else "Mercado Livre"
            )
            st.markdown(
                '<div class="mi-marketplace-invite">'
                f'{icone_svg("chart-pie", tamanho=16)}'
                f'Conecte a {escape(marketplace_ausente)} para comparar canais.'
                "</div>",
                unsafe_allow_html=True,
            )

    with coluna_participacao:
        titulo_secao(
            "Participação por canal",
            "Distribuição de faturamento, pedidos e unidades.",
        )
        metricas_participacao = (
            ("Faturamento", "faturamento", "currency"),
            ("Pedidos", "pedidos", "integer"),
            ("Unidades", "unidades", "integer"),
        )
        for titulo, chave_metrica, formato in metricas_participacao:
            valores_canais = [
                (
                    marketplace,
                    float(comparativo.loc[marketplace, chave_metrica]),
                )
                for marketplace in canais_com_vendas
            ]
            valores_canais.sort(key=lambda item: item[1], reverse=True)
            total_metrica = sum(valor for _, valor in valores_canais)
            linhas_participacao = []
            for indice, (marketplace, valor) in enumerate(valores_canais):
                if formato == "currency":
                    valor_formatado = formatar_moeda_br(valor)
                else:
                    valor_formatado = f"{valor:,.0f}".replace(",", ".")
                participacao = (
                    valor / total_metrica * 100
                    if total_metrica > 0
                    else 0.0
                )
                linhas_participacao.append(
                    LinhaParticipacaoCanal(
                        marketplace=marketplace,
                        valor=valor_formatado,
                        participacao=participacao,
                        cor=PALETA_MARKETPLACES.get(
                            marketplace,
                            PALETA_DADOS[indice % len(PALETA_DADOS)],
                        ),
                        lider=(indice == 0 and len(valores_canais) > 1),
                    )
                )
            if (
                len(canais_com_vendas) == 1
                and canais_com_vendas[0] == "Mercado Livre"
            ):
                linhas_participacao.append(
                    LinhaParticipacaoCanal(
                        marketplace="Shopee",
                        valor="—",
                        participacao=None,
                        cor=PALETA_MARKETPLACES["Shopee"],
                        em_breve=True,
                    )
                )
            renderizar_card_participacao_canal(
                titulo,
                linhas_participacao,
                compacto=True,
            )

    if not tem_comparacao_canais:
        return

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

    tabela_canais = _marcar_comparacoes_por_produto(tabela_canais)


    # ============================================================
    # PAINEL COMPACTO DOS CANAIS
    # ============================================================

    titulo_secao(
        "Comparativo visual dos canais",
        "Faturamento, participação, pedidos e unidades por marketplace.",
    )

    col_grafico, col_participacao = st.columns(2, gap="medium")

    with col_grafico:
        grafico_faturamento = go.Figure(
            go.Bar(
                x=dados["marketplace"],
                y=dados["faturamento"],
                marker_color=[
                    PALETA_MARKETPLACES.get(canal, PALETA_DADOS[0])
                    for canal in dados["marketplace"]
                ],
                customdata=[
                    [formatar_moeda_br(valor)]
                    for valor in dados["faturamento"]
                ],
                hovertemplate=(
                    "<b>%{x}</b><br>"
                    "Faturamento: %{customdata[0]}<extra></extra>"
                ),
            )
        )
        grafico_faturamento.update_layout(
            height=300,
            showlegend=False,
            bargap=0.58,
            barcornerradius=4,
            margin=dict(l=24, r=20, t=8, b=26)
        )
        grafico_dashboard(
            grafico_faturamento,
            altura=300,
            titulo="Faturamento por canal",
            subtitulo="Receita bruta no período selecionado",
            eixo_y_moeda=True,
        )

    with col_participacao:
        grafico_resultado = go.Figure(
            go.Pie(
                labels=dados["marketplace"],
                values=dados["faturamento"],
                hole=0.68,
                marker_colors=[
                    PALETA_MARKETPLACES.get(canal, PALETA_DADOS[0])
                    for canal in dados["marketplace"]
                ],
                customdata=[
                    formatar_moeda_br(valor)
                    for valor in dados["faturamento"]
                ],
                textinfo="percent",
                hovertemplate=(
                    "<b>%{label}</b><br>"
                    "Faturamento: %{customdata}<br>"
                    "Participação: %{percent}<extra></extra>"
                ),
            )
        )
        grafico_resultado.update_layout(
            height=300,
            showlegend=False,
            margin=dict(l=22, r=22, t=12, b=12)
        )
        grafico_resultado.update_traces(
            domain={"x": [0.12, 0.88], "y": [0.08, 0.92]}
        )
        itens_legenda = []
        for _, linha in dados.iterrows():
            canal = str(linha["marketplace"])
            cor = PALETA_MARKETPLACES.get(canal, PALETA_DADOS[2])
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
            'font-size:12px;line-height:1.3;">'
            f"{legenda_participacao}</div>"
        )
        grafico_dashboard(
            grafico_resultado,
            altura=300,
            titulo="Participação no faturamento",
            subtitulo="Divisão da receita por canal",
            rodape_html=legenda_participacao_html
        )

    col_unidades, col_pedidos = st.columns(2, gap="medium")

    for coluna, titulo, campo, rotulo in [
        (col_unidades, "Unidades por canal", "unidades", "Unidades"),
        (col_pedidos, "Pedidos por canal", "pedidos", "Pedidos")
    ]:
        with coluna:
            grafico = px.bar(
                dados,
                x="marketplace",
                y=campo,
                color="marketplace",
                color_discrete_map=PALETA_MARKETPLACES
            )
            grafico.update_traces(
                hovertemplate=(
                    "<b>%{x}</b><br>"
                    f"{rotulo}: %{{y:.0f}}<extra></extra>"
                )
            )
            grafico.update_layout(
                height=260,
                showlegend=False,
                bargap=0.58,
                barcornerradius=4,
                margin=dict(l=24, r=20, t=8, b=26)
            )
            grafico_dashboard(
                grafico,
                altura=260,
                titulo=titulo,
                subtitulo=f"Comparação de {rotulo.lower()} entre canais"
            )

    # ============================================================
    # MELHOR CANAL POR PRODUTO
    # ============================================================

    if tabela_canais["tem_comparacao"].any():
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
        tem_comparacao = tabela_canais["tem_comparacao"].to_numpy()
        for coluna in ("Margem Mercado Livre", "Margem Shopee"):
            tabela[coluna] = [
                formatar_percentual_br(valor) if comparavel else "—"
                for valor, comparavel in zip(tabela[coluna], tem_comparacao)
            ]
        tabela["Diferença de margem"] = [
            f"{formatar_percentual_br(valor)} p.p."
            if comparavel and not pd.isna(valor)
            else "—"
            for valor, comparavel in zip(
                tabela["Diferença de margem"],
                tem_comparacao,
            )
        ]
        for coluna in ("Faturamento Mercado Livre", "Faturamento Shopee"):
            tabela[coluna] = tabela[coluna].map(formatar_moeda_br)

        titulo_secao(
            "Melhor canal por produto",
            "Margem estimada após custos, taxas, frete e publicidade.",
        )
        with st.container(border=True):
            tabela_limpa(
                tabela,
                badges={
                    "Melhor canal": {
                        "Mercado Livre": "ml",
                        "Shopee": "shopee",
                        "Sem comparação": "muted",
                    }
                },
                chave="melhor_canal_produto"
            )