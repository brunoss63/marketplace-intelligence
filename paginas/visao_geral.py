from html import escape

import streamlit as st
import pandas as pd
import plotly.express as px

from armazenamento import ler_dataset
from componentes import (
    card,
    animar_pagina,
    grafico_dashboard,
    cabecalho_pagina,
    tabela_limpa,
)
from dados_periodo import (
    obter_kpis_financeiros,
    obter_periodo_anterior
)

from secoes.insights import mostrar_insights


def _moeda_br(valor: float) -> str:
    return (
        f"R$ {valor:,.2f}"
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )


# ============================================================
# CONFIGURAÇÃO DA PÁGINA
# ============================================================

animar_pagina("visao_geral")

cabecalho_pagina(
    "Visão Geral",
    "Panorama executivo da operação nos marketplaces.",
    "◫"
)


# ============================================================
# CARREGAMENTO DOS DADOS
# ============================================================

pedidos = ler_dataset("dados/pedidos.csv")
if "desconto" not in pedidos.columns:
    pedidos["desconto"] = 0.0

pedidos["data"] = pd.to_datetime(pedidos["data"])


# ============================================================
# FILTRO DE STATUS
# ============================================================

pedidos_validos = pedidos[
    pedidos["status"] == "Concluído"
].copy()


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
# APLICAÇÃO DO FILTRO
# ============================================================

pedidos_periodo = pedidos_validos[
    (pedidos_validos["data"].dt.date >= data_inicio)
    & (pedidos_validos["data"].dt.date <= data_fim)
].copy()
if produto_selecionado is not None:
    pedidos_periodo = pedidos_periodo[
        pedidos_periodo["produto"] == produto_selecionado
    ].copy()
if marketplace_selecionado is not None:
    pedidos_periodo = pedidos_periodo[
        pedidos_periodo["marketplace"] == marketplace_selecionado
    ].copy()


# ============================================================
# INDICADORES FINANCEIROS
# ============================================================

kpis = obter_kpis_financeiros(
    data_inicio,
    data_fim,
    produto_selecionado,
    marketplace_selecionado
)

inicio_anterior, fim_anterior = obter_periodo_anterior(
    data_inicio,
    data_fim
)

kpis_anterior = obter_kpis_financeiros(
    inicio_anterior,
    fim_anterior,
    produto_selecionado,
    marketplace_selecionado
)

faturamento = kpis["faturamento_bruto"]
faturamento_liquido = kpis["faturamento_liquido"]
resultado = kpis["resultado"]
margem = kpis["margem"]
pedidos_total = int(kpis["pedidos"])
unidades = kpis["unidades"]
ticket_medio = kpis["ticket_medio"]
roas = kpis["roas"]
investimento_publicidade = kpis["investimento_publicidade"]


def variacao_percentual(
    atual: float,
    anterior: float
) -> float | None:
    if anterior == 0:
        return None

    return (atual - anterior) / abs(anterior) * 100


def texto_variacao(
    atual: float,
    anterior: float
) -> str:
    variacao = variacao_percentual(atual, anterior)

    if variacao is None:
        return "Sem base no período anterior"

    sinal = "▲" if variacao > 0 else "▼" if variacao < 0 else "•"
    return f"{sinal} {abs(variacao):.1f}% vs período anterior"


def tipo_variacao(
    atual: float,
    anterior: float,
    maior_e_melhor: bool = True
) -> str:
    if anterior == 0 or atual == anterior:
        return "neutral"

    aumentou = atual > anterior
    positivo = aumentou if maior_e_melhor else not aumentou
    return "positive" if positivo else "negative"


# ============================================================
# RESUMO DA OPERAÇÃO
# ============================================================

def resumo_variacao(
    indicador: str,
    atual: float,
    anterior: float,
    maior_e_melhor: bool | None = True
) -> tuple[str, str]:
    variacao = variacao_percentual(atual, anterior)
    if variacao is None:
        return f"{indicador}: sem base no período anterior", "neutral"

    if variacao == 0:
        texto = f"{indicador} se manteve (0.0%) vs período anterior"
    else:
        direcao = "subiu" if variacao > 0 else "caiu"
        texto = (
            f"{indicador} {direcao} {abs(variacao):.1f}% "
            "vs período anterior"
        )
    estilo = (
        "neutral"
        if maior_e_melhor is None
        else tipo_variacao(atual, anterior, maior_e_melhor)
    )
    return texto, estilo


resumo_itens = [
    resumo_variacao(
        "Faturamento líquido",
        faturamento_liquido,
        kpis_anterior["faturamento_liquido"]
    ),
    resumo_variacao(
        "Pedidos",
        kpis["pedidos"],
        kpis_anterior["pedidos"]
    ),
    resumo_variacao(
        "Ticket médio",
        ticket_medio,
        kpis_anterior["ticket_medio"]
    ),
    resumo_variacao(
        "Margem após custos e anúncios",
        margem,
        kpis_anterior["margem"]
    ),
    resumo_variacao(
        "Investimento em anúncios",
        investimento_publicidade,
        kpis_anterior["investimento_publicidade"],
        maior_e_melhor=None
    )
]

chips_html = "".join(
    (
        f'<span class="mi-summary-chip {estilo}">'
        f"{escape(texto)}</span>"
    )
    for texto, estilo in resumo_itens
)

st.html(
    f"""
    <style>
        .mi-operation-summary {{
            background: #121C2B;
            border: 1px solid #263449;
            border-radius: 9px;
            padding: 11px 13px 12px;
            margin: 5px 0 12px;
        }}
        .mi-operation-summary-title {{
            color: #A8B6C9;
            font-size: 10px;
            font-weight: 700;
            letter-spacing: .07em;
            text-transform: uppercase;
            margin-bottom: 9px;
        }}
        .mi-operation-summary-list {{
            display: flex;
            flex-wrap: wrap;
            gap: 7px;
        }}
        .mi-summary-chip {{
            display: inline-flex;
            align-items: center;
            border: 1px solid #2B3B52;
            border-radius: 5px;
            background: #172334;
            color: #CBD5E1;
            padding: 6px 9px;
            font-size: 10px;
            line-height: 1.3;
        }}
        .mi-summary-chip.positive {{
            border-color: rgba(34, 197, 94, .28);
            color: #4ADE80;
        }}
        .mi-summary-chip.negative {{
            border-color: rgba(244, 63, 94, .28);
            color: #FB7185;
        }}
        .mi-summary-chip.neutral {{
            color: #FBBF24;
        }}
    </style>
    <div class="mi-operation-summary">
        <div class="mi-operation-summary-title">Resumo da operação</div>
        <div class="mi-operation-summary-list">{chips_html}</div>
    </div>
    """
)


# ============================================================
# KPIs PRINCIPAIS
# ============================================================

col1, col2, col3, col4 = st.columns(
    4,
    gap="medium"
)


with col1:

    card(
        "Faturamento bruto",
        _moeda_br(faturamento),
        "💰",
        texto_variacao(
            faturamento,
            kpis_anterior["faturamento_bruto"]
        ),
        tipo_variacao(
            faturamento,
            kpis_anterior["faturamento_bruto"]
        ),
        tooltip=(
            "Soma do valor bruto dos pedidos concluídos no período, "
            "antes de descontar custos."
        )
    )


with col2:

    card(
        "Faturamento líquido",
        _moeda_br(faturamento_liquido),
        "💵",
        texto_variacao(
            faturamento_liquido,
            kpis_anterior["faturamento_liquido"]
        ),
        tipo_variacao(
            faturamento_liquido,
            kpis_anterior["faturamento_liquido"]
        ),
        tooltip=(
            "Faturamento bruto menos descontos concedidos, taxas do "
            "marketplace e frete pago pelo vendedor."
        )
    )

with col3:

    card(
        "Resultado após custos e anúncios",
        _moeda_br(resultado),
        "📈",
        texto_variacao(
            resultado,
            kpis_anterior["resultado"]
        ),
        tipo_variacao(
            resultado,
            kpis_anterior["resultado"]
        ),
        tooltip=(
            "Estimativa após descontar descontos concedidos, custo dos "
            "produtos, taxas, frete do vendedor e publicidade do faturamento "
            "bruto."
        )
    )

with col4:

    card(
        "Margem após custos e anúncios",
        f"{margem:.1f}%",
        "📊",
        texto_variacao(
            margem,
            kpis_anterior["margem"]
        ),
        tipo_variacao(
            margem,
            kpis_anterior["margem"]
        ),
        tooltip=(
            "Percentual da receita após descontos comerciais que resta "
            "depois de custos dos produtos, taxas, frete e publicidade."
        )
    )

col1, col2, col3, col4, col5 = st.columns(5, gap="small")

with col1:
    card(
        "Pedidos",
        f"{pedidos_total:,}".replace(",", "."),
        "🛒",
        texto_variacao(
            kpis["pedidos"],
            kpis_anterior["pedidos"]
        ),
        tipo_variacao(
            kpis["pedidos"],
            kpis_anterior["pedidos"]
        ),
        tooltip="Quantidade de pedidos concluídos no período selecionado."
    )

with col2:
    card(
        "Unidades vendidas",
        f"{unidades:,.0f}".replace(",", "."),
        "📦",
        texto_variacao(
            unidades,
            kpis_anterior["unidades"]
        ),
        tipo_variacao(
            unidades,
            kpis_anterior["unidades"]
        ),
        tooltip="Quantidade total de unidades vendidas nos pedidos concluídos."
    )

with col3:
    card(
        "Ticket médio",
        f"R$ {ticket_medio:,.2f}".replace(",", "X")
        .replace(".", ",")
        .replace("X", "."),
        "🎯",
        texto_variacao(ticket_medio, kpis_anterior["ticket_medio"]),
        tipo_variacao(ticket_medio, kpis_anterior["ticket_medio"]),
        tooltip=(
            "Faturamento bruto dividido pela quantidade de pedidos "
            "concluídos."
        )
    )

with col4:
    card(
        "ROAS Publicidade",
        f"{roas:.2f}",
        "📢",
        texto_variacao(roas, kpis_anterior["roas"]),
        tipo_variacao(roas, kpis_anterior["roas"]),
        tooltip=(
            "Receita atribuída à publicidade dividida pelo investimento "
            "em anúncios. Ex.: 5,15 significa R$ 5,15 atribuídos por "
            "cada R$ 1,00 investido."
        )
    )

with col5:
    card(
        "Investimento em anúncios",
        _moeda_br(investimento_publicidade),
        "📣",
        texto_variacao(
            investimento_publicidade,
            kpis_anterior["investimento_publicidade"]
        ),
        tipo_variacao(
            investimento_publicidade,
            kpis_anterior["investimento_publicidade"],
            maior_e_melhor=False
        ),
        tooltip="Valor investido em anúncios durante o período selecionado."
    )

# ============================================================
# GRÁFICOS PRINCIPAIS
# ============================================================

st.divider()

col_grafico, col_canais = st.columns(
    [2, 1],
    gap="medium"
)


pedidos_diarios = (
    pedidos_periodo
    .assign(data=pedidos_periodo["data"].dt.normalize())
    .groupby("data")
    .agg(
        faturamento=("faturamento_bruto", "sum"),
        pedidos=("id_pedido", "count"),
    )
    .reindex(
        pd.date_range(data_inicio, data_fim, freq="D"),
        fill_value=0,
    )
    .rename_axis("data")
    .reset_index()
)

periodo = pedidos_diarios[["data", "faturamento"]]


with col_grafico:
    grafico = px.line(
        periodo,
        x="data",
        y="faturamento"
    )

    grafico.update_traces(
        line_color="#3B82F6",
        hovertemplate=(
            "Faturamento: <b>R$ %{y:,.2f}</b>"
            "<extra></extra>"
        )
    )

    grafico.update_xaxes(hoverformat="%d/%m/%Y")

    grafico.update_layout(
        height=270,
        template="plotly_dark",
        xaxis_title="",
        yaxis_title="",
        hovermode="x unified",
        transition={
            "duration": 500,
            "easing": "cubic-in-out"
        },
        margin=dict(
            l=20,
            r=20,
            t=20,
            b=20
        )
    )


    grafico_dashboard(
        grafico,
        titulo="Evolução do Faturamento",
        subtitulo="Faturamento bruto ao longo do tempo",
        hover_sobre_area=True
    )


with col_canais:
    faturamento_canais = (
        pedidos_periodo
        .groupby("marketplace", as_index=False)["faturamento_bruto"]
        .sum()
        .rename(columns={"faturamento_bruto": "faturamento"})
    )

    grafico_canais = px.pie(
        faturamento_canais,
        names="marketplace",
        values="faturamento",
        hole=0.64,
        color="marketplace",
        color_discrete_map={
            "Mercado Livre": "#F5B700",
            "Shopee": "#F4513A"
        }
    )

    total_faturamento_canais = faturamento_canais[
        "faturamento"
    ].sum()
    cores_canais = {
        "Mercado Livre": "#F5B700",
        "Shopee": "#F4513A"
    }
    linhas_legenda = []
    for _, linha in faturamento_canais.iterrows():
        marketplace = str(linha["marketplace"])
        valor = float(linha["faturamento"])
        participacao = (
            valor / total_faturamento_canais * 100
            if total_faturamento_canais > 0
            else 0
        )
        valor_formatado = (
            f"R$ {valor:,.2f}"
            .replace(",", "X")
            .replace(".", ",")
            .replace("X", ".")
        )
        cor = cores_canais.get(marketplace, "#A8B6C9")
        linhas_legenda.append(
            f'<div class="mi-pie-summary-row">'
            f'<span class="mi-pie-summary-label">'
            f'<span class="mi-pie-summary-swatch" '
            f'style="background:{cor}"></span>'
            f"{escape(marketplace)}</span>"
            f'<span><span class="mi-pie-summary-amount">'
            f"{valor_formatado}</span>"
            f'<span class="mi-pie-summary-share">'
            f"({participacao:.1f}%)</span></span></div>"
        )
    legenda_canais_html = (
        '<div class="mi-pie-summary">'
        f"{''.join(linhas_legenda)}</div>"
    )

    grafico_canais.update_traces(
        textinfo="none",
        hovertemplate=(
            "%{label}: <b>R$ %{value:,.2f}</b> "
            "<span style='color:#A8B6C9'>(%{percent})</span>"
            "<extra></extra>"
        ),
        sort=False
    )

    grafico_canais.update_layout(
        height=210,
        template="plotly_dark",
        showlegend=False,
        transition={
            "duration": 500,
            "easing": "cubic-in-out"
        },
        margin=dict(
            l=8,
            r=8,
            t=8,
            b=0
        )
    )
    grafico_canais.update_traces(
        domain={"x": [0.08, 0.92], "y": [0.02, 0.98]}
    )

    grafico_dashboard(
        grafico_canais,
        titulo="Faturamento por Marketplace",
        subtitulo="Participação por canal",
        rodape_html=legenda_canais_html
    )


col_pedidos, col_resumo = st.columns(
    [2, 1],
    gap="medium"
)

with col_pedidos:
    grafico_pedidos = px.area(
        pedidos_diarios,
        x="data",
        y="pedidos"
    )
    grafico_pedidos.update_traces(
        line_color="#F97316",
        hovertemplate=(
            "Pedidos: <b>%{y}</b><extra></extra>"
        )
    )
    grafico_pedidos.update_xaxes(hoverformat="%d/%m/%Y")
    grafico_pedidos.update_layout(
        height=240,
        template="plotly_dark",
        xaxis_title="",
        yaxis_title="",
        margin=dict(l=20, r=20, t=20, b=20)
    )
    grafico_dashboard(
        grafico_pedidos,
        titulo="Evolução dos Pedidos",
        subtitulo="Quantidade de pedidos ao longo do tempo",
        hover_sobre_area=True
    )

with col_resumo:
    st.markdown(
        """
        <style>
            div[data-testid="stVerticalBlockBorderWrapper"]:has(
                .mi-period-summary-heading
            ) {
                background: #121C2B;
                border-color: #263449;
                border-radius: 8px;
                box-shadow: 0 5px 16px rgba(0, 0, 0, 0.18);
                transition:
                    transform 220ms cubic-bezier(.2, .7, .2, 1),
                    border-color 220ms ease,
                    box-shadow 220ms ease;
            }
            div[data-testid="stVerticalBlockBorderWrapper"]:has(
                .mi-period-summary-heading
            ):hover {
                transform: translateY(-2px);
                border-color: rgba(96, 165, 250, 0.48);
                box-shadow:
                    0 11px 24px rgba(0, 0, 0, 0.27),
                    0 0 17px rgba(59, 130, 246, 0.09);
            }
        </style>
        """,
        unsafe_allow_html=True
    )

    with st.container(border=True):
        st.markdown(
            """
            <div class="mi-chart-heading mi-period-summary-heading">
                <div class="mi-chart-title">📌 Resumo do período</div>
                <div class="mi-chart-subtitle">
                    Taxas, frete e investimento em publicidade
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        st.metric(
            "Taxas do marketplace",
            _moeda_br(kpis["taxas"])
        )
        st.metric(
            "Frete do vendedor",
            _moeda_br(kpis["frete"])
        )
        st.metric(
            "Publicidade",
            _moeda_br(investimento_publicidade)
        )


# ============================================================
# INSIGHTS
# ============================================================

mostrar_insights(
    periodo,
    card
)

st.divider()
st.markdown("### 🧾 Vendas recentes")
st.caption("Pedidos concluídos mais recentes dentro dos filtros selecionados.")
if pedidos_periodo.empty:
    st.info("Não há vendas no período e nos filtros selecionados.")
else:
    vendas_recentes = pedidos_periodo.sort_values(
        ["data", "id_pedido"],
        ascending=[False, False],
    ).head(10)[
        [
            "id_pedido",
            "data",
            "marketplace",
            "produto",
            "quantidade",
            "faturamento_bruto",
            "desconto",
        ]
    ].copy()
    vendas_recentes["data"] = vendas_recentes["data"].dt.strftime("%d/%m/%Y")
    vendas_recentes["faturamento_bruto"] = vendas_recentes[
        "faturamento_bruto"
    ].map(
        lambda valor: (
            f"R$ {valor:,.2f}"
            .replace(",", "X")
            .replace(".", ",")
            .replace("X", ".")
        )
    )
    vendas_recentes["desconto"] = vendas_recentes["desconto"].fillna(0).map(
        lambda valor: (
            f"R$ {valor:,.2f}"
            .replace(",", "X")
            .replace(".", ",")
            .replace("X", ".")
        )
    )
    vendas_recentes = vendas_recentes.rename(
        columns={
            "id_pedido": "Pedido",
            "data": "Data",
            "marketplace": "Marketplace",
            "produto": "Produto",
            "quantidade": "Unidades",
            "faturamento_bruto": "Total bruto",
            "desconto": "Desconto",
        }
    )
    tabela_limpa(
        vendas_recentes,
        badges={
            "Marketplace": {
                "Mercado Livre": "ml",
                "Shopee": "shopee",
            }
        },
        chave="visao_geral_vendas_recentes",
        linhas_por_pagina=10,
    )

st.page_link(
    "paginas/vendas_pedidos.py",
    label="Ver todas as vendas e pedidos",
    icon="🧾",
)