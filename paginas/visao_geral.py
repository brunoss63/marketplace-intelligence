from html import escape

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from armazenamento import ler_dataset
from componentes import (
    card,
    animar_pagina,
    grafico_dashboard,
    cabecalho_pagina,
    PALETA_DADOS,
    PALETA_MARKETPLACES,
    LinhaParticipacaoCanal,
    renderizar_card_participacao_canal,
    renderizar_skeleton_dashboard,
    renderizar_animacoes_entrada_pagina,
    tabela_limpa,
)
from dados_periodo import (
    obter_kpis_financeiros,
    obter_periodo_anterior,
    obter_series_financeiras_diarias,
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
    "◫",
    contexto=(
        f"Período analisado · "
        f"{st.session_state.get('data_inicio').strftime('%d/%m/%Y')} – "
        f"{st.session_state.get('data_fim').strftime('%d/%m/%Y')}"
        if st.session_state.get("data_inicio") is not None
        and st.session_state.get("data_fim") is not None
        else ""
    ),
)

skeleton_slot = st.empty()
mostrar_skeleton = not st.session_state.get("_mi_overview_loaded", False)
if mostrar_skeleton:
    with skeleton_slot.container():
        renderizar_skeleton_dashboard()


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

    skeleton_slot.empty()
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

if pedidos_periodo.empty:
    st.info("Nenhum pedido concluído encontrado no período selecionado.")


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


series_financeiras = obter_series_financeiras_diarias(
    pedidos_periodo,
    data_inicio,
    data_fim,
    produto_selecionado,
    marketplace_selecionado,
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
pedidos_periodo_anterior = pedidos_validos[
    (pedidos_validos["data"].dt.date >= inicio_anterior)
    & (pedidos_validos["data"].dt.date <= fim_anterior)
].copy()
if produto_selecionado is not None:
    pedidos_periodo_anterior = pedidos_periodo_anterior[
        pedidos_periodo_anterior["produto"] == produto_selecionado
    ].copy()
if marketplace_selecionado is not None:
    pedidos_periodo_anterior = pedidos_periodo_anterior[
        pedidos_periodo_anterior["marketplace"] == marketplace_selecionado
    ].copy()
pedidos_diarios_anterior = (
    pedidos_periodo_anterior
    .assign(data=pedidos_periodo_anterior["data"].dt.normalize())
    .groupby("data")
    .agg(
        faturamento=("faturamento_bruto", "sum"),
        pedidos=("id_pedido", "count"),
    )
    .reindex(
        pd.date_range(inicio_anterior, fim_anterior, freq="D"),
        fill_value=0,
    )
    .rename_axis("data")
    .reset_index()
)
series_financeiras["bruto"] = (
    pedidos_diarios["faturamento"].astype(float).tolist()
)
total_dias_anterior = (fim_anterior - inicio_anterior).days + 1
data_minima = pedidos["data"].min()
data_maxima = pedidos["data"].max()
if pd.isna(data_minima) or pd.isna(data_maxima):
    dias_anterior_cobertos = 0
else:
    inicio_cobertura = max(
        pd.Timestamp(inicio_anterior),
        data_minima.normalize(),
    )
    fim_cobertura = min(
        pd.Timestamp(fim_anterior),
        data_maxima.normalize(),
    )
    dias_anterior_cobertos = max(
        (fim_cobertura - inicio_cobertura).days + 1,
        0,
    )
comparacao_parcial = dias_anterior_cobertos < total_dias_anterior
skeleton_slot.empty()
st.session_state["_mi_overview_loaded"] = True


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
        return ""

    seta = "↗" if variacao > 0 else "↓" if variacao < 0 else "→"
    valor = f"{variacao:+.1f}%".replace(".", ",")
    return f"{seta} {valor} vs período anterior"


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


comparacao_disponivel = any(
    variacao_percentual(kpis[campo], kpis_anterior[campo]) is not None
    for campo in (
        "faturamento_bruto",
        "faturamento_liquido",
        "resultado",
        "margem",
        "pedidos",
        "unidades",
        "ticket_medio",
        "roas",
        "investimento_publicidade",
    )
)
if comparacao_parcial:
    texto_banner = (
        "Comparação com período anterior parcial: "
        f"{dias_anterior_cobertos} de {total_dias_anterior} dias"
    )
    classe_banner = " mi-comparison-banner-partial"
elif not comparacao_disponivel:
    texto_banner = "Sem período anterior para comparar"
    classe_banner = ""
else:
    texto_banner = ""
    classe_banner = ""

if texto_banner:
    st.markdown(
        f'<div class="mi-comparison-banner{classe_banner}">'
        '<span class="mi-comparison-banner-icon">i</span>'
        f'<span>{texto_banner}</span></div>',
        unsafe_allow_html=True,
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
        "chart-coins",
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
        ),
        peso="principal",
        sparkline=series_financeiras.get("bruto"),
    )


with col2:

    card(
        "Faturamento líquido",
        _moeda_br(faturamento_liquido),
        "chart-coins",
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
        ),
        peso="principal",
        sparkline=series_financeiras.get("liquido"),
    )

with col3:

    card(
        "Resultado após custos e anúncios",
        _moeda_br(resultado),
        "chart-up",
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
        ),
        peso="principal",
        sparkline=series_financeiras.get("resultado"),
        cor_valor=(
            "positive" if resultado > 0
            else "negative" if resultado < 0
            else "neutral"
        ),
    )

with col4:

    card(
        "Margem após custos e anúncios",
        f"{margem:.1f}%".replace(".", ","),
        "chart-pie",
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
        ),
        peso="principal",
        sparkline=series_financeiras.get("margem"),
        cor_valor=(
            "positive" if margem > 0
            else "negative" if margem < 0
            else "neutral"
        ),
    )

col1, col2, col3, col4, col5 = st.columns(5, gap="small")

with col1:
    card(
        "Pedidos",
        f"{pedidos_total:,}".replace(",", "."),
        "shopping-bag",
        texto_variacao(
            kpis["pedidos"],
            kpis_anterior["pedidos"]
        ),
        tipo_variacao(
            kpis["pedidos"],
            kpis_anterior["pedidos"]
        ),
        tooltip="Quantidade de pedidos concluídos no período selecionado.",
        peso="operacional",
    )

with col2:
    card(
        "Unidades vendidas",
        f"{unidades:,.0f}".replace(",", "."),
        "package",
        texto_variacao(
            unidades,
            kpis_anterior["unidades"]
        ),
        tipo_variacao(
            unidades,
            kpis_anterior["unidades"]
        ),
        tooltip="Quantidade total de unidades vendidas nos pedidos concluídos.",
        peso="operacional",
    )

with col3:
    card(
        "Ticket médio",
        f"R$ {ticket_medio:,.2f}".replace(",", "X")
        .replace(".", ",")
        .replace("X", "."),
        "target",
        texto_variacao(ticket_medio, kpis_anterior["ticket_medio"]),
        tipo_variacao(ticket_medio, kpis_anterior["ticket_medio"]),
        tooltip=(
            "Faturamento bruto dividido pela quantidade de pedidos "
            "concluídos."
        ),
        peso="operacional",
    )

with col4:
    card(
        "ROAS Publicidade",
        f"{roas:.2f}".replace(".", ","),
        "megaphone",
        texto_variacao(roas, kpis_anterior["roas"]),
        tipo_variacao(roas, kpis_anterior["roas"]),
        tooltip=(
            "Receita atribuída à publicidade dividida pelo investimento "
            "em anúncios. Ex.: 5,15 significa R$ 5,15 atribuídos por "
            "cada R$ 1,00 investido."
        ),
        peso="operacional",
    )

with col5:
    card(
        "Investimento em anúncios",
        _moeda_br(investimento_publicidade),
        "megaphone",
        texto_variacao(
            investimento_publicidade,
            kpis_anterior["investimento_publicidade"]
        ),
        tipo_variacao(
            investimento_publicidade,
            kpis_anterior["investimento_publicidade"],
            maior_e_melhor=False
        ),
        tooltip="Valor investido em anúncios durante o período selecionado.",
        peso="operacional",
    )

# ============================================================
# GRÁFICOS PRINCIPAIS
# ============================================================

st.divider()

col_grafico, col_canais = st.columns(
    [2, 1],
    gap="medium"
)


valores_diarios = series_financeiras.get(
    "bruto",
    pedidos_diarios["faturamento"].astype(float).tolist(),
)
periodo = pedidos_diarios[["data"]].copy()
periodo["faturamento"] = valores_diarios
periodo["valor_formatado"] = periodo["faturamento"].map(_moeda_br)


with col_grafico:
    grafico = px.line(
        periodo,
        x="data",
        y="faturamento",
        custom_data=["valor_formatado"],
    )

    grafico.update_traces(
        name="Faturamento bruto",
        mode="lines+markers",
        line_color=PALETA_DADOS[0],
        hovertemplate=(
            "Faturamento bruto: <b>%{customdata[0]}</b>"
            "<extra></extra>"
        ),
    )

    if comparacao_disponivel:
        valores_anteriores = (
            pedidos_diarios_anterior["faturamento"]
            .astype(float)
            .tolist()
        )
        datas_anterior = pd.date_range(
            inicio_anterior,
            fim_anterior,
            freq="D",
        )
        if not pd.isna(data_minima) and not pd.isna(data_maxima):
            valores_anteriores = [
                valor
                if data_minima.normalize() <= data <= data_maxima.normalize()
                else None
                for data, valor in zip(datas_anterior, valores_anteriores)
            ]
        valores_anteriores = valores_anteriores[:len(periodo)]
        grafico.add_trace(
            go.Scatter(
                x=periodo["data"],
                y=valores_anteriores,
                customdata=[
                    [_moeda_br(valor) if valor is not None else "—"]
                    for valor in valores_anteriores
                ],
                name="Período anterior",
                mode="lines",
                line={"color": PALETA_DADOS[2], "dash": "dot"},
                opacity=.62,
                meta={"mi_auxiliary": True},
                hovertemplate=(
                    "Período anterior: <b>%{customdata[0]}</b>"
                    "<extra></extra>"
                ),
            )
        )

    media_faturamento = float(periodo["faturamento"].mean())
    if media_faturamento > 0:
        grafico.add_hline(
            y=media_faturamento,
            line_dash="dot",
            line_color=PALETA_DADOS[2],
            opacity=.62,
            annotation_text=f"Média · {_moeda_br(media_faturamento)}",
            annotation_position="right",
            annotation_font={"size": 12, "color": PALETA_DADOS[2]},
            annotation_bgcolor="rgba(15, 23, 42, .88)",
            annotation_bordercolor="rgba(182, 156, 255, .22)",
            annotation_borderpad=4,
        )

    if not periodo.empty and float(periodo["faturamento"].max()) > 0:
        indice_pico = periodo["faturamento"].idxmax()
        dia_pico = periodo.loc[indice_pico]
        grafico.add_annotation(
            x=dia_pico["data"],
            y=float(dia_pico["faturamento"]),
            text="Pico",
            showarrow=True,
            arrowhead=2,
            ax=0,
            ay=-27,
            font={"size": 12, "color": PALETA_DADOS[0]},
            bgcolor="rgba(15, 23, 42, .78)",
            bordercolor="rgba(115, 169, 255, .24)",
            borderpad=3,
            yshift=4,
        )

    grafico_dashboard(
        grafico,
        titulo="Evolução do Faturamento",
        subtitulo="Faturamento bruto ao longo do tempo",
        visual_minimal=True,
        linha_suave=True,
        apenas_exportar=True,
        respiro_eixo_y=True,
        eixo_y_moeda=True,
    )


with col_canais:
    faturamento_canais = (
        pedidos_periodo
        .groupby("marketplace", as_index=False)["faturamento_bruto"]
        .sum()
        .rename(columns={"faturamento_bruto": "faturamento"})
    )

    total_faturamento_canais = faturamento_canais[
        "faturamento"
    ].sum()
    if len(faturamento_canais) == 1:
        linha = faturamento_canais.iloc[0]
        marketplace = str(linha["marketplace"])
        valor = float(linha["faturamento"])
        participacao = (
            valor / total_faturamento_canais * 100
            if total_faturamento_canais > 0
            else 0.0
        )
        cor = PALETA_MARKETPLACES.get(marketplace, PALETA_DADOS[0])
        renderizar_card_participacao_canal(
            "Faturamento por Marketplace",
            [
                LinhaParticipacaoCanal(
                    marketplace=marketplace,
                    valor=_moeda_br(valor),
                    participacao=participacao,
                    cor=cor,
                )
            ],
        )
    elif len(faturamento_canais) > 1:
        cores_canais = {
            str(nome): PALETA_MARKETPLACES.get(
                str(nome),
                PALETA_DADOS[indice % len(PALETA_DADOS)],
            )
            for indice, nome in enumerate(faturamento_canais["marketplace"])
        }
        faturamento_canais["valor_formatado"] = (
            faturamento_canais["faturamento"].map(_moeda_br)
        )
        faturamento_canais["participacao_formatada"] = (
            faturamento_canais["faturamento"]
            .div(total_faturamento_canais)
            .mul(100)
            .map(lambda valor: f"{valor:.1f}%".replace(".", ","))
            if total_faturamento_canais > 0
            else "0,0%"
        )
        grafico_canais = px.pie(
            faturamento_canais,
            names="marketplace",
            values="faturamento",
            hole=0.78,
            color="marketplace",
            color_discrete_map=cores_canais,
            color_discrete_sequence=list(PALETA_DADOS),
            custom_data=["valor_formatado", "participacao_formatada"],
        )
        grafico_canais.update_traces(
            textinfo="none",
            hovertemplate=(
                "<b>%{label}</b><br>"
                "Faturamento: <b>%{customdata[0]}</b><br>"
                "Participação: %{customdata[1]}<extra></extra>"
            ),
            sort=False,
            marker={"line": {"color": "rgba(15, 23, 42, .8)", "width": 1}},
        )
        grafico_canais.update_layout(
            height=188,
            showlegend=False,
            margin=dict(l=6, r=6, t=3, b=0),
            annotations=[
                {
                    "text": (
                        '<span style="font-size:10px;color:#8FA1B8">'
                        "Total</span><br>"
                        f'<span style="font-size:13px;color:#F1F5F9">'
                        f"<b>{escape(_moeda_br(total_faturamento_canais))}"
                        "</b></span>"
                    ),
                    "x": 0.5,
                    "y": 0.5,
                    "showarrow": False,
                    "align": "center",
                }
            ],
        )
        grafico_canais.update_traces(
            domain={"x": [0.08, 0.92], "y": [0.04, 0.96]}
        )

        linhas_legenda = []
        for _, linha in faturamento_canais.iterrows():
            nome_canal = str(linha["marketplace"])
            valor = float(linha["faturamento"])
            participacao = (
                valor / total_faturamento_canais * 100
                if total_faturamento_canais > 0
                else 0.0
            )
            participacao_formatada = (
                f"{participacao:.1f}%".replace(".", ",")
            )
            cor = cores_canais[nome_canal]
            linhas_legenda.append(
                '<div class="mi-pie-summary-row">'
                '<span class="mi-pie-summary-label">'
                f'<span class="mi-pie-summary-swatch" '
                f'style="background:{cor}"></span>'
                f"{escape(nome_canal)}</span>"
                '<span><span class="mi-pie-summary-amount">'
                f"{_moeda_br(valor)}</span>"
                '<span class="mi-pie-summary-share">'
                f"{participacao_formatada}</span></span></div>"
            )
        grafico_dashboard(
            grafico_canais,
            titulo="Faturamento por Marketplace",
            subtitulo="Participação por canal",
            rodape_html=(
                '<div class="mi-pie-summary">'
                f"{''.join(linhas_legenda)}</div>"
            ),
            visual_minimal=True,
            apenas_exportar=True,
        )
    else:
        st.info("Sem faturamento por marketplace neste período.")


col_pedidos, col_resumo = st.columns(
    [2, 1],
    gap="medium"
)

with col_pedidos:
    pedidos_diarios["pedidos_formatado"] = (
        pedidos_diarios["pedidos"].astype(int).astype(str)
    )
    grafico_pedidos = px.area(
        pedidos_diarios,
        x="data",
        y="pedidos",
        custom_data=["pedidos_formatado"],
    )
    grafico_pedidos.update_traces(
        name="Pedidos",
        mode="lines+markers",
        line_color=PALETA_DADOS[5],
        hovertemplate=(
            "Pedidos: <b>%{customdata[0]}</b><extra></extra>"
        )
    )
    if comparacao_disponivel:
        pedidos_anteriores = (
            pedidos_diarios_anterior["pedidos"]
            .astype(int)
            .tolist()
        )
        datas_anterior = pd.date_range(
            inicio_anterior,
            fim_anterior,
            freq="D",
        )
        if not pd.isna(data_minima) and not pd.isna(data_maxima):
            pedidos_anteriores = [
                valor
                if data_minima.normalize() <= data <= data_maxima.normalize()
                else None
                for data, valor in zip(datas_anterior, pedidos_anteriores)
            ]
        pedidos_anteriores = pedidos_anteriores[:len(pedidos_diarios)]
        grafico_pedidos.add_trace(
            go.Scatter(
                x=pedidos_diarios["data"],
                y=pedidos_anteriores,
                customdata=[
                    [str(valor) if valor is not None else "—"]
                    for valor in pedidos_anteriores
                ],
                name="Período anterior",
                mode="lines",
                line={"color": PALETA_DADOS[4], "dash": "dot"},
                opacity=.55,
                meta={"mi_auxiliary": True},
                hovertemplate=(
                    "Período anterior: <b>%{customdata[0]}</b> pedidos"
                    "<extra></extra>"
                ),
            )
        )
    media_pedidos = float(pedidos_diarios["pedidos"].mean())
    if media_pedidos > 0:
        media_pedidos_texto = (
            f"{media_pedidos:.1f}".replace(".", ",")
        )
        grafico_pedidos.add_hline(
            y=media_pedidos,
            line_dash="dot",
            line_color=PALETA_DADOS[5],
            opacity=.6,
            annotation_text=f"Média · {media_pedidos_texto}/dia",
            annotation_position="right",
            annotation_font={"size": 12, "color": PALETA_DADOS[5]},
            annotation_bgcolor="rgba(15, 23, 42, .88)",
            annotation_bordercolor="rgba(100, 199, 230, .22)",
            annotation_borderpad=4,
        )
    if not pedidos_diarios.empty and int(pedidos_diarios["pedidos"].max()) > 0:
        indice_pico_pedidos = pedidos_diarios["pedidos"].idxmax()
        dia_pico_pedidos = pedidos_diarios.loc[indice_pico_pedidos]
        grafico_pedidos.add_annotation(
            x=dia_pico_pedidos["data"],
            y=int(dia_pico_pedidos["pedidos"]),
            text="Pico",
            showarrow=True,
            arrowhead=2,
            ax=0,
            ay=-27,
            font={"size": 12, "color": PALETA_DADOS[5]},
            bgcolor="rgba(15, 23, 42, .78)",
            bordercolor="rgba(100, 199, 230, .24)",
            borderpad=3,
            yshift=4,
        )
    grafico_dashboard(
        grafico_pedidos,
        titulo="Evolução dos Pedidos",
        subtitulo="Quantidade de pedidos ao longo do tempo",
        visual_minimal=True,
        linha_suave=True,
        apenas_exportar=True,
        respiro_eixo_y=True,
        eixo_y_inteiro=True,
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
                border-radius: 14px;
                min-height: 390px;
                height: 100%;
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
            .mi-period-metrics {
                display: flex;
                min-height: 285px;
                flex-direction: column;
                justify-content: space-evenly;
            }
            .mi-period-metric {
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 12px;
                padding: 11px 2px;
                border-bottom: 1px solid rgba(51, 65, 85, .62);
            }
            .mi-period-metric:last-child {
                border-bottom: 0;
            }
            .mi-period-metric-label {
                color: #A8B6C9;
                font-size: 12px;
            }
            .mi-period-metric-value {
                color: #E8EEF7;
                font-size: 17px;
                font-variant-numeric: tabular-nums;
                white-space: nowrap;
            }
        </style>
        """,
        unsafe_allow_html=True
    )

    with st.container(border=True):
        st.markdown(
            f"""
            <div class="mi-chart-heading mi-period-summary-heading">
                <div class="mi-chart-title">Resumo do período</div>
                <div class="mi-chart-subtitle">
                    Taxas, frete e investimento em publicidade
                </div>
            </div>
            <div class="mi-period-metrics">
                <div class="mi-period-metric">
                    <span class="mi-period-metric-label">
                        Taxas do marketplace
                    </span>
                    <strong class="mi-period-metric-value">
                        {_moeda_br(kpis["taxas"])}
                    </strong>
                </div>
                <div class="mi-period-metric">
                    <span class="mi-period-metric-label">
                        Frete do vendedor
                    </span>
                    <strong class="mi-period-metric-value">
                        {_moeda_br(kpis["frete"])}
                    </strong>
                </div>
                <div class="mi-period-metric">
                    <span class="mi-period-metric-label">
                        Publicidade
                    </span>
                    <strong class="mi-period-metric-value">
                        {_moeda_br(investimento_publicidade)}
                    </strong>
                </div>
            </div>
            """,
                unsafe_allow_html=True
            )


# ============================================================
# INSIGHTS
# ============================================================

mostrar_insights(
    periodo,
    pedidos_periodo,
)

st.divider()
st.markdown(
    """
    <div class="mi-chart-heading">
        <div class="mi-chart-title">Vendas recentes</div>
        <div class="mi-chart-subtitle">
            Pedidos concluídos mais recentes dentro dos filtros selecionados
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)
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
    vendas_recentes["quantidade"] = (
        pd.to_numeric(vendas_recentes["quantidade"], errors="coerce")
        .fillna(0)
        .map(lambda valor: str(int(valor)))
    )
    vendas_recentes["desconto"] = vendas_recentes["desconto"].map(
        lambda valor: (
            "—"
            if pd.isna(valor) or float(valor) == 0
            else _moeda_br(float(valor))
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
        colunas_discretas=("Pedido",),
    )

st.markdown(
    """
    <style>
        .st-key-mi-all-sales-link a {
            color: #A8B6C9;
            font-size: 12px;
            text-decoration: none;
            transition: color 160ms ease, transform 160ms ease;
        }
        .st-key-mi-all-sales-link a:hover {
            color: #C5DEFF;
            transform: translateX(2px);
        }
    </style>
    """,
    unsafe_allow_html=True,
)
with st.container(
    key="mi-all-sales-link",
    horizontal=True,
    horizontal_alignment="right",
):
    st.page_link(
        "paginas/vendas_pedidos.py",
        label="Ver todas as vendas e pedidos",
        icon=":material/arrow_forward:",
        width="content",
    )

renderizar_animacoes_entrada_pagina()