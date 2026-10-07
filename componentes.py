import copy
import re
import unicodedata
from html import escape
import json
from dataclasses import dataclass
from datetime import date
from math import ceil, floor, isfinite, log10
from typing import Sequence

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from postgrest.exceptions import APIError
from plotly.utils import PlotlyJSONEncoder
from status_conexoes import obter_status_conexoes, texto_ultima_sincronizacao


DESIGN_TOKENS = {
    "color-brand": "#73A9FF",
    "color-brand-strong": "#4F91F5",
    "color-background": "#0F172A",
    "color-surface": "#121C2B",
    "color-surface-raised": "#1E293B",
    "color-text": "#F1F5F9",
    "color-text-muted": "#8FA1B8",
    "color-border": "#263449",
    "color-success": "#4ADE80",
    "color-warning": "#F6C85F",
    "color-danger": "#FF806D",
    "color-info": "#64C7E6",
    "radius-control": "8px",
    "radius-card": "14px",
}

PALETA_DADOS = (
    "#73A9FF",
    "#4FD1B5",
    "#B69CFF",
    "#F6C85F",
    "#FF8E7A",
    "#64C7E6",
    "#A6D977",
)

PALETA_MARKETPLACES = {
    "Mercado Livre": PALETA_DADOS[0],
    "Shopee": PALETA_DADOS[1],
}


@dataclass(frozen=True)
class LinhaParticipacaoCanal:
    marketplace: str
    valor: str
    participacao: float | None
    cor: str
    em_breve: bool = False
    lider: bool = False


def formatar_moeda_br(valor: object) -> str:
    numero = pd.to_numeric(valor, errors="coerce")
    if pd.isna(numero):
        return "—"
    sinal = "-" if numero < 0 else ""
    return (
        f"{sinal}R$ {abs(float(numero)):,.2f}"
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )


def formatar_percentual_br(valor: object, casas: int = 1) -> str:
    numero = pd.to_numeric(valor, errors="coerce")
    if pd.isna(numero):
        return "—"
    return f"{numero:.{casas}f}%".replace(".", ",")


def formatar_multiplicador_br(valor: object, casas: int = 2) -> str:
    numero = pd.to_numeric(valor, errors="coerce")
    if pd.isna(numero):
        return "—"
    return f"{numero:.{casas}f}x".replace(".", ",")


def renderizar_card_participacao_canal(
    titulo: str,
    linhas: Sequence[LinhaParticipacaoCanal],
    *,
    subtitulo: str = "Participação por canal",
    compacto: bool = False,
) -> None:
    """Renderiza participação por canal no card compartilhado do dashboard."""
    classe_entrada, atraso = proxima_animacao_entrada_pagina()
    html_linhas = []
    for linha in linhas:
        percentual = linha.participacao
        percentual_texto = (
            f"{percentual:.1f}% da operação".replace(".", ",")
            if percentual is not None
            else "—"
        )
        valor_html = (
            escape(linha.valor)
            if linha.em_breve or not classe_entrada
            else _html_valor_animado(
                linha.valor,
                atraso,
                iniciar_oculto=bool(classe_entrada),
            )
        )
        participacao_html = (
            escape(percentual_texto)
            if linha.em_breve or not classe_entrada
            else _html_valor_animado(
                percentual_texto,
                atraso,
                iniciar_oculto=bool(classe_entrada),
            )
        )
        largura = (
            min(max(percentual or 0.0, 0.0), 100.0)
            if not linha.em_breve
            else 0.0
        )
        classe_lider = " mi-channel-row-leader" if linha.lider else ""
        badge_lider = (
            '<span class="mi-channel-leader-badge">Líder</span>'
            if linha.lider
            else ""
        )
        badge_em_breve = (
            '<span class="mi-channel-coming-badge">Em breve</span>'
            if linha.em_breve
            else ""
        )
        nome_canal = escape(linha.marketplace)
        classe_entrada_barra = (
            " mi-entry-progress" if classe_entrada else ""
        )
        html_linhas.append(
            f"""
            <div class="mi-channel-row{classe_lider}">
                <div class="mi-channel-row-heading">
                    <span class="mi-channel-row-name">
                        <span class="mi-channel-row-swatch"
                              style="background:{escape(linha.cor)}"></span>
                        {nome_canal}
                    </span>
                    {badge_lider}{badge_em_breve}
                </div>
                <div class="mi-channel-row-value-row">
                    <span class="mi-channel-single-value">{valor_html}</span>
                    <span class="mi-channel-single-share">
                        {participacao_html}
                    </span>
                </div>
                <div class="mi-channel-single-track">
                    <div class="mi-channel-single-progress{classe_entrada_barra}"
                         style="--mi-progress-target:{largura:.1f}%;
                                width:{largura:.1f}%;
                                --mi-entry-delay:{atraso}ms;
                                background:{escape(linha.cor)};"></div>
                </div>
            </div>
            """
        )

    modo_compacto = " mi-channel-comparison-card" if compacto else ""
    st.html(
        f"""
        <section class="mi-channel-single{modo_compacto}
                        {' mi-entry-card' if classe_entrada else ''}"
                 style="--mi-entry-delay:{atraso}ms">
            <header class="mi-channel-single-heading">
                <div class="mi-channel-single-title">{escape(titulo)}</div>
                <div class="mi-channel-single-subtitle">
                    {escape(subtitulo)}
                </div>
            </header>
            <div class="mi-channel-rows">{''.join(html_linhas)}</div>
        </section>
        """
    )


_ICONES_SVG = {
    "chart-coins": (
        '<circle cx="8" cy="8" r="5.5"/>'
        '<path d="M8 5.5v5M10 6.5c-.5-.6-1.2-.9-2-.9-1.1 0-2 .5-2 1.4s.8 1.2 2 1.5 2 .7 2 1.6-.9 1.4-2 1.4c-.9 0-1.7-.4-2.2-1"/>'
        '<path d="M13 10.5a5.5 5.5 0 1 1-4.5 5.4M13 13v5h5"/>'
    ),
    "chart-up": (
        '<path d="M3 17.5 8 12l3.5 3.5L19 7"/>'
        '<path d="M13.5 7H19v5.5M3 21h18"/>'
    ),
    "chart-pie": (
        '<path d="M11 3.1A9 9 0 1 0 20.9 13H11z"/>'
        '<path d="M14 3.1V10h6.9A9 9 0 0 0 14 3.1Z"/>'
    ),
    "shopping-bag": (
        '<path d="M5 8h14l1 13H4L5 8Z"/>'
        '<path d="M9 9V6a3 3 0 0 1 6 0v3"/>'
    ),
    "file-text": (
        '<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/>'
        '<path d="M14 3v6h6M8 13h8M8 17h8"/>'
    ),
    "package": (
        '<path d="m12 3 9 5-9 5-9-5 9-5Z"/>'
        '<path d="M3 8v9l9 5 9-5V8M12 13v9M7.5 5.5l9 5"/>'
    ),
    "target": (
        '<circle cx="12" cy="12" r="9"/>'
        '<circle cx="12" cy="12" r="5"/>'
        '<circle cx="12" cy="12" r="1"/>'
        '<path d="m14 10 6-6m-4 0h4v4"/>'
    ),
    "megaphone": (
        '<path d="m3 11 17-6v14L3 13v-2Z"/>'
        '<path d="m7 14 2 7h4l-2-8M20 10a3 3 0 0 1 0 4"/>'
    ),
    "trophy": (
        '<path d="M8 21h8M12 17v4M7 4h10v5a5 5 0 0 1-10 0V4Z"/>'
        '<path d="M7 6H4v2a4 4 0 0 0 4 4M17 6h3v2a4 4 0 0 1-4 4"/>'
    ),
    "chart-down": (
        '<path d="M3 6.5 8 12l3.5-3.5L19 17"/>'
        '<path d="M13.5 17H19v-5.5M3 21h18"/>'
    ),
    "chart-average": (
        '<path d="M3 18h18M5 14l4-4 3 2 7-7"/>'
        '<circle cx="5" cy="14" r="1"/><circle cx="19" cy="5" r="1"/>'
    ),
    "check-circle": (
        '<circle cx="12" cy="12" r="9"/>'
        '<path d="m8 12 2.5 2.5L16 9"/>'
    ),
}

_VARIANTES_BADGE = {
    "empty",
    "error",
    "info",
    "loading",
    "negative",
    "neutral",
    "positive",
    "success",
    "warning",
}


def icone_svg(nome: str, *, tamanho: int = 18) -> str:
    """Retorna um ícone SVG line icon da biblioteca visual do produto."""
    if nome not in _ICONES_SVG:
        raise ValueError(f"Ícone não registrado no design system: {nome}")
    if tamanho < 1:
        raise ValueError("tamanho deve ser maior que zero.")

    return (
        f'<svg class="mi-icon" width="{tamanho}" height="{tamanho}" '
        'viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" '
        f'aria-hidden="true">{_ICONES_SVG[nome]}</svg>'
    )


def badge_html(
    texto: str,
    variante: str = "neutral",
    *,
    icone: str | None = None
) -> str:
    """Monta o HTML seguro de um badge semântico reutilizável."""
    if variante not in _VARIANTES_BADGE:
        raise ValueError(f"Variante de badge não reconhecida: {variante}")

    indicador = (
        icone_svg(icone, tamanho=13)
        if icone
        else '<span class="mi-badge-dot" aria-hidden="true"></span>'
    )
    return (
        f'<span class="mi-badge mi-badge-{variante}">'
        f'{indicador}<span>{escape(str(texto))}</span></span>'
    )


def renderizar_skeleton_dashboard(
    *,
    incluir_tabela: bool = True,
) -> None:
    metricas_principais = "".join(
        '<div class="mi-skeleton mi-skeleton-kpi mi-skeleton-primary"></div>'
        for _ in range(4)
    )
    metricas_operacionais = "".join(
        '<div class="mi-skeleton mi-skeleton-kpi mi-skeleton-secondary"></div>'
        for _ in range(5)
    )
    tabela = (
        '<div class="mi-skeleton mi-skeleton-table"></div>'
        if incluir_tabela
        else ""
    )
    st.markdown(
        f"""
        <div class="mi-dashboard-skeleton" aria-label="Carregando indicadores">
            <div class="mi-skeleton mi-skeleton-summary"></div>
            <div class="mi-skeleton-grid mi-skeleton-grid-primary">
                {metricas_principais}
            </div>
            <div class="mi-skeleton-grid mi-skeleton-grid-secondary">
                {metricas_operacionais}
            </div>
            <div class="mi-skeleton-grid mi-skeleton-grid-charts">
                <div class="mi-skeleton mi-skeleton-chart"></div>
                <div class="mi-skeleton mi-skeleton-chart"></div>
            </div>
            {tabela}
        </div>
        """,
        unsafe_allow_html=True
    )


def renderizar_skeleton_vendas_pedidos() -> None:
    cards = "".join(
        '<div class="mi-skeleton mi-skeleton-order-card"></div>'
        for _ in range(6)
    )
    st.html(
        f"""
        <div class="mi-orders-skeleton" aria-label="Carregando pedidos">
            <div class="mi-skeleton-grid mi-skeleton-grid-orders">
                {cards}
            </div>
            <div class="mi-skeleton mi-skeleton-orders-table"></div>
        </div>
        """
    )


def renderizar_skeleton_marketplaces() -> None:
    cards = "".join(
        '<div class="mi-skeleton mi-skeleton-marketplace-card"></div>'
        for _ in range(3)
    )
    st.html(
        f"""
        <div class="mi-marketplace-skeleton"
             aria-label="Carregando indicadores dos canais">
            <div class="mi-skeleton mi-skeleton-marketplace-table"></div>
            <div class="mi-skeleton-grid mi-skeleton-marketplace-participation">
                {cards}
            </div>
        </div>
        """
    )


def renderizar_skeleton_produtos(aba: str = "Estoque") -> None:
    if aba == "Desempenho":
        rankings = "".join(
            '<div class="mi-skeleton mi-skeleton-product-ranking"></div>'
            for _ in range(2)
        )
        destaques = "".join(
            '<div class="mi-skeleton mi-skeleton-product-kpi"></div>'
            for _ in range(3)
        )
        conteudo = (
            '<div class="mi-skeleton-grid mi-skeleton-product-rankings">'
            f"{rankings}</div>"
            '<div class="mi-skeleton-grid mi-skeleton-product-highlights">'
            f"{destaques}</div>"
        )
    elif aba == "Portfólio":
        conteudo = (
            '<div class="mi-skeleton mi-skeleton-product-controls"></div>'
            '<div class="mi-skeleton mi-skeleton-product-controls"></div>'
            '<div class="mi-skeleton mi-skeleton-product-portfolio-table"></div>'
            '<div class="mi-skeleton mi-skeleton-product-pagination"></div>'
        )
    else:
        cards = "".join(
            '<div class="mi-skeleton mi-skeleton-product-kpi"></div>'
            for _ in range(5)
        )
        conteudo = (
            '<div class="mi-skeleton-grid mi-skeleton-product-kpis">'
            f"{cards}</div>"
            '<div class="mi-skeleton-grid mi-skeleton-product-stock-panels">'
            '<div class="mi-skeleton mi-skeleton-product-stock-panel"></div>'
            '<div class="mi-skeleton mi-skeleton-product-stock-panel"></div>'
            "</div>"
        )
    st.html(
        f"""
        <div class="mi-product-skeleton mi-product-skeleton-{escape(aba.lower())}"
             aria-label="Carregando produtos e estoque">
            {conteudo}
        </div>
        """
    )


def _obter_marketplaces_conectados() -> list[str] | None:
    from armazenamento import (
        is_database_mode,
        obter_cliente_supabase,
        obter_tenant_id,
    )

    if not is_database_mode():
        return None

    resposta = (
        obter_cliente_supabase()
        .table("marketplace_connections")
        .select("marketplace")
        .eq("tenant_id", obter_tenant_id())
        .execute()
    )
    marketplaces = {
        str(linha["marketplace"])
        for linha in resposta.data or []
        if linha.get("marketplace")
    }
    return sorted(marketplaces, key=str.casefold)


def texto_status_conexoes(marketplaces: list[str] | None) -> str:
    if marketplaces is None:
        return "Conexões indisponíveis neste ambiente"
    quantidade = len(marketplaces)
    if quantidade == 0:
        return "Nenhum marketplace conectado"
    substantivo = "marketplace" if quantidade == 1 else "marketplaces"
    return f"{quantidade} {substantivo} conectado" + (
        "" if quantidade == 1 else "s"
    )


def renderizar_indicador_conexoes(container=None) -> None:
    """Renderiza os status compartilhados no rodapé da sidebar."""
    destino = container if container is not None else st.sidebar
    status_marketplaces = obter_status_conexoes()
    destinos_estilo = {
        "connected": "conectado",
        "syncing": "sincronizando",
        "attention": "atencao",
        "error": "erro",
        "disconnected": "desconectado",
        "coming_soon": "em-breve",
    }
    with destino.container(key="mi-sidebar-connection-status"):
        for status in status_marketplaces:
            instante = texto_ultima_sincronizacao(
                status.ultima_sincronizacao
            )
            ajuda = f"{status.marketplace} · {status.rotulo}"
            if instante:
                ajuda = f"{ajuda} · {instante}"
            elif status.mensagem:
                ajuda = f"{ajuda} · {status.mensagem}"
            with destino.container(
                key=(
                    "mi-sidebar-status-"
                    f"{destinos_estilo[status.estado]}"
                )
            ):
                destino.page_link(
                    "paginas/marketplaces.py",
                    label=(
                        f"**{status.marketplace}** · "
                        f"_{status.rotulo}_"
                    ),
                    help=ajuda,
                    width="stretch",
                )
def _animacao_grafico(figura: go.Figure) -> tuple[go.Figure, str] | None:
    figura_inicial = copy.deepcopy(figura)
    traces_pizza = []
    traces_barras = []
    traces_linha = []

    for indice, trace in enumerate(figura.data):
        if trace.type == "pie" and trace.values is not None:
            valores = list(trace.values)
            if any(float(valor) > 0 for valor in valores):
                traces_pizza.append((indice, valores))
        elif trace.type == "bar" and trace.y is not None:
            valores = list(trace.y)
            if valores:
                traces_barras.append((indice, valores))
        elif (
            trace.type == "scatter"
            and getattr(trace, "mode", None)
            and "lines" in trace.mode
            and trace.x is not None
            and len(trace.x) > 1
        ):
            traces_linha.append((indice, list(trace.x)))

    if traces_pizza:
        frames = []
        indices = []
        for indice, valores in traces_pizza:
            figura_inicial.data[indice].values = [0] * len(valores)
            frames.append({"values": valores})
            indices.append(indice)
        animacao = {
            "data": frames,
            "traces": indices
        }
    elif traces_linha:
        valores_x = [
            valor
            for _, valores in traces_linha
            for valor in valores
        ]
        serie_x = pd.Series(valores_x)
        if pd.api.types.is_datetime64_any_dtype(serie_x.dtype) or all(
            isinstance(valor, date) for valor in valores_x
        ):
            datas = pd.to_datetime(serie_x, errors="coerce")
            if datas.isna().any():
                return None
            minimo = datas.min()
            maximo = datas.max()
            diferenca = maximo - minimo
            if diferenca <= pd.Timedelta(0):
                return None
            margem = diferenca * 0.04
            eixo_completo = [
                (minimo - margem).isoformat(),
                (maximo + margem).isoformat()
            ]
            eixo_inicial = [
                (minimo - margem).isoformat(),
                (minimo + diferenca * 0.04).isoformat()
            ]
        else:
            numericos = pd.to_numeric(serie_x, errors="coerce")
            if numericos.isna().any():
                return None
            minimo = float(numericos.min())
            maximo = float(numericos.max())
            diferenca = maximo - minimo
            if not isfinite(diferenca) or diferenca <= 0:
                return None
            margem = diferenca * 0.04
            eixo_completo = [
                minimo - margem,
                maximo + margem
            ]
            eixo_inicial = [
                minimo - margem,
                minimo + diferenca * 0.04
            ]

        figura_inicial.update_xaxes(range=eixo_inicial, autorange=False)
        animacao = {
            "layout": {
                "xaxis": {
                    "range": eixo_completo,
                    "autorange": False
                }
            }
        }
    elif traces_barras:
        frames = []
        indices = []
        valores_barras = []
        for indice, valores in traces_barras:
            figura_inicial.data[indice].y = [0] * len(valores)
            frames.append({"y": valores})
            indices.append(indice)
            valores_barras.extend(valores)

        valores_numericos = pd.to_numeric(
            pd.Series(valores_barras),
            errors="coerce"
        ).dropna().tolist()
        valores_finitos = [
            float(valor)
            for valor in valores_numericos
            if isfinite(float(valor))
        ]
        if valores_finitos and all(
            valor >= 0 for valor in valores_finitos
        ):
            maior_valor = max(valores_finitos)
            figura_inicial.update_yaxes(
                range=[0, maior_valor * 1.1 if maior_valor > 0 else 1],
                autorange=False
            )

        animacao = {
            "data": frames,
            "traces": indices
        }
    else:
        return None

    animacao_json = json.dumps(
        animacao,
        cls=PlotlyJSONEncoder,
        separators=(",", ":")
    ).replace("</", "<\\/")
    script = f"""
        var grafico = document.getElementById('{{plot_id}}');
        var quadro = {animacao_json};
        var duracao = window.matchMedia(
            '(prefers-reduced-motion: reduce)'
        ).matches ? 0 : 1100;
        window.requestAnimationFrame(function() {{
            Plotly.animate(grafico, [quadro], {{
                mode: 'immediate',
                frame: {{duration: duracao, redraw: true}},
                transition: {{
                    duration: duracao,
                    easing: 'cubic-in-out'
                }}
            }});
        }});
    """
    return figura_inicial, script


def grafico_dashboard(
    figura: go.Figure,
    altura: int | None = None,
    *,
    titulo: str = "",
    subtitulo: str = "",
    hover_sobre_area: bool = False,
    rodape_html: str | None = None,
    visual_minimal: bool = False,
    linha_suave: bool = False,
    apenas_exportar: bool = False,
    respiro_eixo_y: bool = False,
    eixo_y_moeda: bool = False,
    eixo_y_inteiro: bool = False,
) -> None:
    """Renderiza um gráfico em um painel compacto e padronizado."""

    indice_animacao = st.session_state.get("_mi_chart_animation_index", 0)
    st.session_state["_mi_chart_animation_index"] = indice_animacao + 1
    animar_entrada = False
    atraso_animacao = min(indice_animacao * 110, 550)

    tem_linha = any(
        trace.type == "scatter"
        and getattr(trace, "mode", None)
        and "lines" in trace.mode
        for trace in figura.data
    )

    layout = {
        "template": "plotly_dark",
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
        "font": {
            "family": "Inter, Segoe UI, sans-serif",
            "color": "#A8B6C9",
            "size": 12
        },
        "colorway": list(PALETA_DADOS),
        "hoverlabel": {
            "bgcolor": "#0B1220",
            "bordercolor": DESIGN_TOKENS["color-brand"],
            "font": {
                "color": "#F8FAFC",
                "family": "Inter, Segoe UI, sans-serif",
                "size": 12
            },
            "align": "left",
            "namelength": -1,
        },
        "hovermode": "x unified" if tem_linha else "closest",
        "hoverdistance": 24,
        "spikedistance": -1,
        "dragmode": False,
    }
    if altura is not None:
        layout["height"] = altura

    figura.update_layout(**layout)
    classe_entrada, atraso_entrada = proxima_animacao_entrada_pagina()
    estilo_entrada = (
        f' style="--mi-entry-delay:{atraso_entrada}ms"'
        if classe_entrada
        else ""
    )
    cor_grade = (
        "rgba(148, 163, 184, 0.035)"
        if visual_minimal
        else "rgba(148, 163, 184, 0.10)"
    )
    figura.update_xaxes(
        gridcolor=cor_grade,
        linecolor="rgba(148, 163, 184, 0.16)",
        rangeslider_visible=False,
        fixedrange=True,
        zeroline=False,
        showline=False,
        ticks="outside",
        ticklen=3,
        tickcolor="rgba(148, 163, 184, 0.22)"
    )
    figura.update_layout(xaxis_title="", yaxis_title="")
    figura.update_yaxes(
        gridcolor=cor_grade,
        linecolor="rgba(148, 163, 184, 0.16)",
        fixedrange=True,
        zeroline=False,
        showline=False,
        ticks="outside",
        ticklen=3,
        tickcolor="rgba(148, 163, 184, 0.22)"
    )
    if tem_linha:
        figura.update_xaxes(
            unifiedhovertitle_text="<b>%{x|%d/%m}</b>",
            hoverformat="%d/%m",
            tickformat="%d/%m",
            nticks=6,
        )

    if respiro_eixo_y and tem_linha:
        figura.update_layout(margin={"l": 50, "r": 150, "t": 48, "b": 52})
        valores_y = [
            float(valor)
            for trace in figura.data
            if trace.type == "scatter" and trace.y is not None
            for valor in pd.to_numeric(
                pd.Series(trace.y),
                errors="coerce",
            ).dropna()
            if isfinite(float(valor))
        ]
        if valores_y:
            menor = min(valores_y)
            maior = max(valores_y)
            escala = max(abs(menor), abs(maior), 1.0)
            folga = max((maior - menor) * .055, escala * .035)
            minimo = menor - folga if menor < 0 else -escala * .035
            maximo = maior + max(folga, escala * .06)
            if menor >= 0 and (eixo_y_moeda or eixo_y_inteiro):
                rough_step = max(maior / 4, 1)
                magnitude = 10 ** floor(log10(rough_step))
                step = next(
                    (
                        multiplier * magnitude
                        for multiplier in (1, 2, 5, 10)
                        if multiplier * magnitude >= rough_step
                    ),
                    10 * magnitude,
                )
                ticks = [
                    indice * step
                    for indice in range(max(ceil(maior / step), 1) + 1)
                ]
                maximo = max(maximo, ticks[-1] + escala * .025)
                figura.update_yaxes(
                    tickmode="array",
                    tickvals=ticks,
                    ticktext=[
                        (
                            "R$ "
                            if eixo_y_moeda
                            else ""
                        )
                        + f"{valor:,.0f}".replace(",", ".")
                        for valor in ticks
                    ],
                )
            figura.update_yaxes(
                range=[minimo, maximo],
                tickformat=".0f" if eixo_y_inteiro else None,
            )

    for trace in figura.data:
        if trace.type == "scatter":
            modo = getattr(trace, "mode", None) or "lines"
            metadados = trace.meta if isinstance(trace.meta, dict) else {}
            linha_auxiliar = bool(metadados.get("mi_auxiliary"))
            if "lines" in modo:
                cor_linha = (
                    getattr(trace.line, "color", None)
                    or PALETA_DADOS[0]
                )
                if cor_linha.startswith("#") and len(cor_linha) == 7:
                    cor_preenchimento = (
                        "rgba("
                        f"{int(cor_linha[1:3], 16)}, "
                        f"{int(cor_linha[3:5], 16)}, "
                        f"{int(cor_linha[5:7], 16)}, 0.14)"
                    )
                else:
                    cor_preenchimento = "rgba(115, 169, 255, 0.14)"

                estilo_preenchimento = (
                    {
                        "fillgradient": {
                            "type": "vertical",
                            "colorscale": [
                                [
                                    0,
                                    cor_preenchimento.replace(
                                        ", 0.14)",
                                        ", 0.015)",
                                    ),
                                ],
                                [
                                    1,
                                    cor_preenchimento.replace(
                                        ", 0.14)",
                                        ", 0.24)",
                                    ),
                                ],
                            ],
                        }
                    }
                    if visual_minimal and not linha_auxiliar
                    else {"fillcolor": cor_preenchimento}
                )
                if linha_auxiliar:
                    trace.update(
                        line={
                            "width": 1.5,
                            "shape": "spline",
                            "smoothing": 0.2,
                            "dash": "dot",
                        },
                        fill="none",
                        hoveron="points",
                    )
                else:
                    trace.update(
                        mode="lines+markers" if visual_minimal else modo,
                        line={
                            "width": 2.2 if linha_suave else 2.5,
                            "shape": "spline",
                            "smoothing": 0.2 if linha_suave else 0.45,
                        },
                        fill="tozeroy",
                        **estilo_preenchimento,
                        hoveron=(
                            "points+fills"
                            if hover_sobre_area
                            else "points"
                        )
                    )
                figura.update_xaxes(
                    showspikes=tem_linha,
                    spikemode="across",
                    spikesnap="cursor",
                    spikecolor="rgba(148, 163, 184, 0.38)",
                    spikethickness=1
                )
            if "markers" in modo or (visual_minimal and not linha_auxiliar):
                trace.update(
                    marker={
                        "size": 4,
                        "color": getattr(trace.line, "color", PALETA_DADOS[0]),
                        "line": {
                            "color": "#DCEAFF",
                            "width": 0.7
                        }
                    }
                )
        elif trace.type == "bar":
            trace.update(
                marker={
                    "line": {
                        "color": "rgba(255,255,255,0.14)",
                        "width": 1
                    }
                }
            )

    figura.update_layout(
        legend={
            "font": {"color": "#A8B6C9", "size": 12},
            "bgcolor": "rgba(0,0,0,0)"
        }
    )

    altura_grafico = (
        altura
        or figura.layout.height
        or 320
    )
    if visual_minimal:
        altura_grafico = max(altura_grafico, 300)
    figura.update_layout(height=altura_grafico)
    animacao = (
        _animacao_grafico(figura)
        if animar_entrada
        else None
    )

    with st.container(border=True):
        classe_animacao = ""
        if animar_entrada:
            classe_animacao = f" mi-chart-enter-{indice_animacao}"
            st.html(
                f"""
                <style>
                    @keyframes mi-chart-build {{
                        from {{
                            opacity: 0;
                            transform: translateY(14px) scale(.985);
                        }}
                        to {{
                            opacity: 1;
                            transform: translateY(0) scale(1);
                        }}
                    }}
                    .stVerticalBlock:has(
                        > [data-testid="stElementContainer"]
                        .mi-chart-enter-{indice_animacao}
                    ) {{
                        animation: mi-chart-build 720ms
                            cubic-bezier(.22,.61,.36,1) both;
                        animation-delay: {atraso_animacao}ms;
                    }}
                    @media (prefers-reduced-motion: reduce) {{
                        .stVerticalBlock:has(
                            > [data-testid="stElementContainer"]
                            .mi-chart-enter-{indice_animacao}
                        ) {{
                            animation: none;
                        }}
                    }}
                </style>
                """
            )

        st.markdown(
            f"""
            <div class="mi-chart-heading{
                ' mi-chart-minimal' if visual_minimal else ''
            }{' mi-entry-chart' if classe_entrada else ''}"{estilo_entrada}>
                <div class="mi-chart-title">{escape(titulo)}</div>
                <div class="mi-chart-subtitle{classe_animacao}">
                    {escape(subtitulo)}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        config = {
            "responsive": True,
            "displayModeBar": "hover",
            "displaylogo": False,
            "scrollZoom": False,
            "doubleClick": False,
            "editable": False,
            "staticPlot": False,
            "modeBarButtonsToRemove": [
                "select2d",
                "lasso2d",
                "zoomIn2d",
                "zoomOut2d",
                "autoScale2d",
            ],
        }
        if apenas_exportar:
            config["modeBarButtons"] = [["toImage"]]
            config["toImageButtonOptions"] = {
                "format": "png",
                "filename": "marketplace-intelligence",
                "scale": 2,
            }
        if visual_minimal:
            config["displaylogo"] = False
        if visual_minimal:
            st.plotly_chart(
                figura,
                width="stretch",
                height=altura_grafico,
                config=config,
            )
        else:
            st.plotly_chart(
                figura,
                use_container_width=True,
                height=altura_grafico,
                config=config,
            )

        if rodape_html:
            st.markdown(rodape_html, unsafe_allow_html=True)


def marca_sidebar() -> None:
    st.sidebar.markdown(
        """
        <div class="mi-sidebar-brand">
            <div class="mi-sidebar-brand-icon">▥</div>
            <div>
                <div class="mi-sidebar-brand-title">
                    Marketplace<br>Intelligence
                </div>
                <div class="mi-sidebar-brand-caption">
                    BI PARA MARKETPLACE
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


def renderizar_painel_login() -> None:
    st.markdown(
        f"""
        <section class="mi-login-story">
            <div class="mi-login-story-brand">
                <span class="mi-login-story-mark">{icone_svg("chart-up", tamanho=22)}</span>
                <span>MARKETPLACE INTELLIGENCE</span>
            </div>
            <div class="mi-login-story-copy">
                <span class="mi-login-story-eyebrow">INTELIGÊNCIA PARA DECIDIR</span>
                <h1>Clareza para<br>mover sua operação.</h1>
                <p>
                    Vendas, marketplaces e desempenho reunidos em uma visão
                    confiável do seu negócio.
                </p>
            </div>
            <div class="mi-login-story-foot">
                <span class="mi-login-lock">{icone_svg("package", tamanho=15)}</span>
                Ambiente privado para sua operação
            </div>
            <span class="mi-login-orbit mi-login-orbit-one"></span>
            <span class="mi-login-orbit mi-login-orbit-two"></span>
        </section>
        """,
        unsafe_allow_html=True
    )


def renderizar_aviso_login(mensagem: str) -> None:
    st.markdown(
        '<div class="mi-login-notice" role="status">'
        '<span class="mi-login-notice-title">Sessão encerrada</span>'
        f"<span>{escape(mensagem)}</span>"
        "</div>",
        unsafe_allow_html=True,
    )


def renderizar_perfil_sidebar(
    nome: str,
    *,
    container=None,
) -> bool:
    nome_seguro = escape(nome)
    iniciais = "".join(
        parte[0] for parte in nome.split()[:2] if parte
    ).upper() or "?"

    destino = container if container is not None else st.sidebar
    with destino.container(key="mi-sidebar-account"):
        avatar, perfil = st.columns([0.8, 4.2], vertical_alignment="top")
        with avatar:
            st.markdown(
                f"""
                <span class="mi-sidebar-avatar">{escape(iniciais)}</span>
                """,
                unsafe_allow_html=True
            )
        with perfil:
            st.markdown(
                f"""
                <div class="mi-sidebar-user-copy">
                    <span class="mi-sidebar-user-name">{nome_seguro}</span>
                    <span class="mi-sidebar-account-active">
                        <span></span>Conta ativa
                    </span>
                </div>
                """,
                unsafe_allow_html=True
            )
            logout = st.button(
                "Sair",
                icon=":material/logout:",
                key="mi_logout_sidebar",
                type="tertiary",
                help="Encerrar sessão",
                width="content",
            )

    return logout


def cabecalho_pagina(
    titulo: str,
    subtitulo: str,
    icone: str,
    *,
    contexto: str = "",
) -> None:
    contexto_html = (
        f'<div class="mi-page-context">{escape(contexto)}</div>'
        if contexto
        else ""
    )
    html = f"""
    <header class="mi-page-heading">
        <div class="mi-page-heading-icon">{escape(icone)}</div>
        <div class="mi-page-heading-copy">
            <div class="mi-page-eyebrow">MARKETPLACE INTELLIGENCE</div>
            <h1 class="mi-page-title">{escape(titulo)}</h1>
            <p class="mi-page-subtitle">{escape(subtitulo)}</p>
            {contexto_html}
        </div>
    </header>
    """
    st.html(html)


def titulo_secao(titulo: str, subtitulo: str) -> None:
    st.html(
        f"""
        <header class="mi-section-heading">
            <h2 class="mi-section-heading-title">{escape(titulo)}</h2>
            <p class="mi-section-heading-subtitle">{escape(subtitulo)}</p>
        </header>
        """
    )


def tabela_limpa(
    tabela: pd.DataFrame,
    badges: dict[str, dict[str, str]] | None = None,
    *,
    chave: str,
    linhas_por_pagina: int = 10,
    colunas_discretas: tuple[str, ...] = (),
    badges_cabecalho: dict[str, tuple[str, str]] | None = None,
    grupos_linhas: dict[str, str] | None = None,
    pontos_cabecalho: tuple[str, ...] = (),
    largura_maxima_px: int | None = None,
    largura_minima_px: int = 640,
    borda_externa: bool = True,
) -> None:
    """Renderiza uma tabela paginada no padrão visual do dashboard."""

    if linhas_por_pagina < 1:
        raise ValueError("linhas_por_pagina deve ser maior que zero.")

    estado_pagina = f"tabela_{chave}_pagina"
    total_linhas = len(tabela)
    total_paginas = max(
        (total_linhas + linhas_por_pagina - 1) // linhas_por_pagina,
        1
    )
    pagina = min(
        max(st.session_state.get(estado_pagina, 0), 0),
        total_paginas - 1
    )
    st.session_state[estado_pagina] = pagina

    if total_linhas > linhas_por_pagina:
        inicio = pagina * linhas_por_pagina
        fim = min(inicio + linhas_por_pagina, total_linhas)
        tabela = tabela.iloc[inicio:fim]

    def classe_valor(coluna: str, texto: str) -> str | None:
        nome_coluna = "".join(
            caractere
            for caractere in unicodedata.normalize("NFKD", coluna.casefold())
            if not unicodedata.combining(caractere)
        )
        if "taxa" in nome_coluna:
            return "negative"
        if "margem" not in nome_coluna:
            return None

        correspondencia = re.search(r"[-+]?\d[\d.,]*", texto)
        if correspondencia is None:
            return None
        numero = correspondencia.group()
        if "," in numero and "." in numero:
            numero = numero.replace(".", "").replace(",", ".")
        elif "," in numero:
            numero = numero.replace(",", ".")
        try:
            valor_numerico = float(numero)
        except ValueError:
            return None
        if valor_numerico == 0:
            return None

        return "positive" if valor_numerico > 0 else "negative"

    def coluna_alinhada_esquerda(coluna: str) -> bool:
        nome_coluna = "".join(
            caractere
            for caractere in unicodedata.normalize("NFKD", coluna.casefold())
            if not unicodedata.combining(caractere)
        )
        return "produto" in nome_coluna or "categoria" in nome_coluna

    badges = badges or {}
    badges_cabecalho = badges_cabecalho or {}
    grupos_linhas = grupos_linhas or {}
    colunas_discretas = set(colunas_discretas)
    pontos_cabecalho = set(pontos_cabecalho)
    cabecalho_html = []
    for coluna in tabela.columns:
        nome_coluna = str(coluna)
        classes = []
        if coluna_alinhada_esquerda(nome_coluna):
            classes.append("mi-clean-text-column")
        if nome_coluna in colunas_discretas:
            classes.append("mi-clean-discreet-column")
        classe = " ".join(classes)
        titulo = escape(nome_coluna)
        if nome_coluna in pontos_cabecalho:
            titulo = (
                '<span class="mi-clean-header-status-dot" '
                'aria-hidden="true"></span>' + titulo
            )
        if nome_coluna in badges_cabecalho:
            texto_badge, variante_badge = badges_cabecalho[nome_coluna]
            titulo += (
                '<span class="mi-clean-badge '
                f'{escape(variante_badge)} mi-clean-header-badge">'
                f"{escape(texto_badge)}</span>"
            )
        cabecalho_html.append(
            f'<th class="{classe}">{titulo}</th>'
        )
    cabecalhos = "".join(cabecalho_html)

    linhas = []
    for _, linha in tabela.iterrows():
        nome_linha = str(linha.iloc[0]) if len(linha) else ""
        grupo = grupos_linhas.get(nome_linha)
        if grupo:
            linhas.append(
                '<tr class="mi-clean-group-row">'
                f'<th colspan="{len(tabela.columns)}">'
                f"{escape(grupo)}</th></tr>"
            )
        celulas = []
        for coluna in tabela.columns:
            valor = linha[coluna]
            texto = "" if pd.isna(valor) else str(valor)
            badge_classes = badges.get(coluna, {})

            if texto in badge_classes:
                conteudo = (
                    f'<span class="mi-clean-badge '
                    f'{escape(badge_classes[texto])}">'
                    f"{escape(texto)}</span>"
                )
            else:
                classe = classe_valor(coluna, texto)
                if classe is None:
                    conteudo = escape(texto)
                else:
                    conteudo = (
                        f'<span class="mi-clean-value-{classe}">'
                        f"{escape(texto)}</span>"
                    )

            classe_coluna = (
                "mi-clean-text-column"
                if coluna_alinhada_esquerda(str(coluna))
                else ""
            )
            if str(coluna) in colunas_discretas:
                classe_coluna = f"{classe_coluna} mi-clean-discreet-column".strip()
            celulas.append(
                f'<td class="{classe_coluna}">{conteudo}</td>'
            )

        linhas.append(f"<tr>{''.join(celulas)}</tr>")

    classe_borda = "" if borda_externa else " mi-clean-table-plain"
    estilo_largura = (
        f"max-width:{largura_maxima_px}px;"
        if largura_maxima_px is not None
        else ""
    )
    st.html(
        f"""
        <style>
            .mi-clean-table-wrap {{
                width: 100%;
                {estilo_largura}
                margin-right: auto;
                margin-left: auto;
                overflow-x: auto;
                border-top: 1px solid #263449;
                border-bottom: 1px solid #263449;
            }}
            .mi-clean-table-wrap.mi-clean-table-plain {{
                border-top: 0;
                border-bottom: 0;
            }}
            .mi-clean-table {{
                width: 100%;
                min-width: {largura_minima_px}px;
                border-collapse: collapse;
                color: #D7E0EE;
                font-family: inherit;
                font-size: 12px;
            }}
            .mi-clean-table th {{
                padding: 10px 12px;
                border-bottom: 1px solid #263449;
                color: #8292A8;
                font-size: 12px;
                font-weight: 700;
                letter-spacing: .06em;
                text-transform: uppercase;
                text-align: right;
                white-space: nowrap;
            }}
            .mi-clean-table th:first-child,
            .mi-clean-table td:first-child {{
                text-align: left;
            }}
            .mi-clean-table tbody tr {{
                border-bottom: 1px solid rgba(51, 65, 85, .62);
                transition: background-color 160ms ease;
            }}
            .mi-clean-table tbody tr:last-child {{
                border-bottom: 0;
            }}
            .mi-clean-table tbody tr:hover {{
                background: rgba(148, 163, 184, .045);
            }}
            .mi-clean-table .mi-clean-group-row th {{
                padding: 12px 12px 5px;
                border-bottom: 0;
                color: #8FA1B8;
                font-size: 12px;
                font-weight: 650;
                letter-spacing: .035em;
                text-align: left;
            }}
            .mi-clean-table .mi-clean-group-row:first-child th {{
                padding-top: 8px;
            }}
            .mi-clean-header-status-dot {{
                display: inline-block;
                width: 7px;
                height: 7px;
                border-radius: 50%;
                margin: 0 7px 1px 0;
                background: #4ADE80;
                vertical-align: middle;
            }}
            .mi-clean-table td {{
                padding: 9px 12px;
                line-height: 1.35;
                text-align: right;
                white-space: nowrap;
                font-variant-numeric: tabular-nums;
            }}
            .mi-clean-table td:first-child {{
                color: #A8B6C9;
                font-variant-numeric: normal;
            }}
            .mi-clean-badge {{
                display: inline-block;
                padding: 3px 7px;
                border-radius: 4px;
                font-size: 12px;
                font-weight: 650;
            }}
            .mi-clean-header-badge {{
                margin-left: 7px;
                padding: 2px 6px;
                font-size: 11px;
                font-weight: 600;
                letter-spacing: 0;
                text-transform: none;
                vertical-align: 1px;
            }}
            .mi-clean-badge.ml {{
                border: 1px solid rgba(115, 169, 255, .2);
                background: rgba(115, 169, 255, .11);
                color: #A8CAFF;
            }}
            .mi-clean-badge.shopee {{
                border: 1px solid rgba(79, 209, 181, .2);
                background: rgba(79, 209, 181, .1);
                color: #88E3CD;
            }}
            .mi-clean-badge.urgent {{
                background: rgba(244, 81, 58, .13);
                color: #FF806D;
            }}
            .mi-clean-badge.warning {{
                background: rgba(245, 183, 0, .13);
                color: #F5B700;
            }}
            .mi-clean-badge.positive {{
                background: rgba(34, 197, 94, .12);
                color: #4ADE80;
            }}
            .mi-clean-badge.info {{
                background: rgba(56, 189, 248, .12);
                color: #7DD3FC;
            }}
            .mi-clean-badge.muted {{
                background: rgba(148, 163, 184, .12);
                color: #CBD5E1;
            }}
            .mi-clean-badge.tie {{
                background: rgba(148, 163, 184, .12);
                color: #CBD5E1;
            }}
            .mi-clean-value-positive {{
                color: #4ADE80;
                font-weight: 600;
                text-shadow: 0 0 8px rgba(74, 222, 128, .16);
            }}
            .mi-clean-value-negative {{
                color: #FF6B6B;
                font-weight: 600;
                text-shadow: 0 0 8px rgba(255, 107, 107, .15);
            }}
            .mi-clean-text-column {{
                text-align: left !important;
            }}
            .mi-clean-discreet-column {{
                color: #8292A8 !important;
                font-size: 12px;
            }}
            @media (max-width: 700px) {{
                .mi-clean-table {{
                    font-size: 12px;
                }}
                .mi-clean-table th,
                .mi-clean-table td {{
                    padding: 8px 7px;
                }}
            }}
        </style>
        <div class="mi-clean-table-wrap{classe_borda}">
            <table class="mi-clean-table">
                <thead><tr>{cabecalhos}</tr></thead>
                <tbody>{''.join(linhas)}</tbody>
            </table>
        </div>
        """
    )

    if total_linhas > linhas_por_pagina:
        controles = st.columns([12, 1, 1])
        with controles[0]:
            st.caption(f"Página {pagina + 1} de {total_paginas}")
        with controles[1]:
            st.button(
                "‹",
                key=f"{estado_pagina}_anterior",
                help="Página anterior",
                disabled=pagina == 0,
                on_click=_alterar_pagina_tabela,
                args=(estado_pagina, -1)
            )
        with controles[2]:
            st.button(
                "›",
                key=f"{estado_pagina}_proxima",
                help="Próxima página",
                disabled=pagina >= total_paginas - 1,
                on_click=_alterar_pagina_tabela,
                args=(estado_pagina, 1)
            )


def _alterar_pagina_tabela(chave_estado: str, variacao: int) -> None:
    st.session_state[chave_estado] = (
        st.session_state.get(chave_estado, 0) + variacao
    )


# =========================================================
# CARD KPI
# =========================================================

def proxima_animacao_entrada_pagina() -> tuple[str, int]:
    if (
        st.session_state.get("_mi_active_page")
        not in {
            "visao_geral",
            "vendas_pedidos",
            "marketplaces",
            "produtos_estoque",
        }
        or not st.session_state.get("_mi_page_entering", False)
    ):
        return "", 0

    indice = st.session_state.get("_mi_page_entry_index", 0)
    st.session_state["_mi_page_entry_index"] = indice + 1
    return "mi-entry-card", indice * 55


def _html_valor_animado(
    valor: str,
    atraso: int,
    *,
    iniciar_oculto: bool = False,
) -> str:
    texto = str(valor)
    correspondencia = re.search(r"[-+]?\d[\d.,]*", texto)
    if correspondencia is None:
        return escape(texto)

    token = correspondencia.group()
    casas_decimais = (
        len(token.rsplit(",", 1)[1])
        if "," in token
        else 0
    )
    normalizado = token.replace(".", "").replace(",", ".")
    try:
        alvo = float(normalizado)
    except ValueError:
        return escape(texto)
    if not isfinite(alvo):
        return escape(texto)

    prefixo = texto[:correspondencia.start()]
    sufixo = texto[correspondencia.end():]
    prefixo = prefixo.replace(" ", "\u00a0")
    final_seguro = escape(texto)
    estilo_inicial = (
        ' style="visibility:hidden"' if iniciar_oculto else ""
    )
    return (
        f'<span class="mi-count-value" '
        f'data-mi-final="{final_seguro}" '
        f'data-mi-target="{alvo:.12g}" '
        f'data-mi-decimals="{casas_decimais}" '
        f'data-mi-prefix="{escape(prefixo)}" '
        f'data-mi-suffix="{escape(sufixo)}" '
        f'data-mi-delay="{atraso}"{estilo_inicial}>'
        f"{final_seguro}</span>"
        '<span class="mi-count-final" aria-hidden="true" '
        'style="display:none!important">'
        f"{final_seguro}</span>"
    )


def renderizar_animacoes_entrada_pagina() -> None:
    """Aplica animações apenas ao entrar nas páginas que as suportam."""
    if (
        st.session_state.get("_mi_active_page")
        not in {
            "visao_geral",
            "vendas_pedidos",
            "marketplaces",
            "produtos_estoque",
        }
        or not st.session_state.get("_mi_page_entering", False)
    ):
        return

    st.html(
        """
        <style>
            @keyframes mi-overview-entry {
                from { opacity: 0; transform: translateY(9px); }
                to { opacity: 1; transform: translateY(0); }
            }
            @keyframes mi-overview-fade {
                from { opacity: 0; }
                to { opacity: 1; }
            }
            @keyframes mi-marketplace-progress {
                from { width: 0; }
                to { width: var(--mi-progress-target); }
            }
            .mi-entry-card {
                animation: mi-overview-entry 420ms
                    cubic-bezier(.22,.61,.36,1) backwards;
                animation-delay: var(--mi-entry-delay, 0ms);
            }
            .mi-entry-chart {
                animation: mi-overview-entry 420ms
                    cubic-bezier(.22,.61,.36,1) backwards;
                animation-delay: var(--mi-entry-delay, 0ms);
            }
            .mi-entry-progress {
                animation: mi-marketplace-progress 850ms
                    cubic-bezier(.2,.75,.25,1) both;
                animation-delay: var(--mi-entry-delay, 0ms);
            }
            .mi-count-value,
            .mi-count-final {
                font-variant-numeric: tabular-nums;
            }
            @media (prefers-reduced-motion: no-preference) {
                [data-testid="stVerticalBlockBorderWrapper"]:has(
                    .mi-entry-chart
                ) .js-plotly-plot {
                    visibility: hidden;
                }
            }
            @media (prefers-reduced-motion: reduce) {
                .mi-entry-card,
                .mi-entry-chart {
                    animation: mi-overview-fade 180ms ease-out both;
                    animation-delay: 0ms;
                    transform: none;
                }
                .mi-entry-progress {
                    animation: none;
                    width: var(--mi-progress-target);
                }
            }
        </style>
        <script>
            (() => {
                if (window.__miEntryAnimationsInitialized) return;
                window.__miEntryAnimationsInitialized = true;

                const main = document.querySelector(
                    '[data-testid="stMain"]'
                ) || document.body;
                const reduzido = window.matchMedia(
                    '(prefers-reduced-motion: reduce)'
                ).matches;
                const valoresAnimados = new WeakSet();
                const graficosAnimados = new WeakSet();
                const graficosAguardando = new WeakSet();
                const tentativasGrafico = new WeakMap();
                const formatar = (elemento, numero) => {
                    const casas = Number(elemento.dataset.miDecimals || 0);
                    const formato = new Intl.NumberFormat('pt-BR', {
                        minimumFractionDigits: casas,
                        maximumFractionDigits: casas
                    });
                    return (elemento.dataset.miPrefix || '')
                        + formato.format(numero)
                        + (elemento.dataset.miSuffix || '');
                };

                const animarValor = elemento => {
                    if (
                        valoresAnimados.has(elemento)
                        || !elemento.closest('.mi-entry-card')
                    ) return;
                    valoresAnimados.add(elemento);
                    const final = elemento.dataset.miFinal;
                    if (reduzido) {
                        elemento.textContent = final;
                        elemento.style.visibility = 'visible';
                        return;
                    }
                    try {
                        const alvo = Number(elemento.dataset.miTarget);
                        const atraso = Number(elemento.dataset.miDelay || 0);
                        if (!Number.isFinite(alvo)) {
                            elemento.textContent = final;
                            elemento.style.visibility = 'visible';
                            return;
                        }
                        window.setTimeout(() => {
                            try {
                                const inicio = performance.now();
                                const duracao = 1000;
                                const quadro = agora => {
                                    try {
                                        const progresso = Math.min(
                                            (agora - inicio) / duracao,
                                            1
                                        );
                                        const desaceleracao =
                                            1 - Math.pow(1 - progresso, 3);
                                        elemento.textContent = progresso >= 1
                                            ? final
                                            : formatar(
                                                elemento,
                                                alvo * desaceleracao
                                            );
                                        elemento.style.visibility = 'visible';
                                        if (progresso < 1) {
                                            window.requestAnimationFrame(quadro);
                                        }
                                    } catch (_) {
                                        elemento.textContent = final;
                                        elemento.style.visibility = 'visible';
                                    }
                                };
                                elemento.textContent = formatar(elemento, 0);
                                elemento.style.visibility = 'visible';
                                window.requestAnimationFrame(quadro);
                            } catch (_) {
                                elemento.textContent = final;
                                elemento.style.visibility = 'visible';
                            }
                        }, atraso);
                    } catch (_) {
                        elemento.textContent = final;
                        elemento.style.visibility = 'visible';
                    }
                };

                const agendarTentativaGrafico = titulo => {
                    if (graficosAguardando.has(titulo)) return;
                    graficosAguardando.add(titulo);
                    window.setTimeout(() => {
                        graficosAguardando.delete(titulo);
                        const tentativas = (
                            tentativasGrafico.get(titulo) || 0
                        ) + 1;
                        tentativasGrafico.set(titulo, tentativas);
                        if (tentativas >= 30) {
                            const bloco = titulo.closest(
                                '[data-testid="stVerticalBlockBorderWrapper"]'
                            ) || titulo.closest(
                                '[data-testid="stVerticalBlock"]'
                            );
                            const grafico = bloco?.querySelector(
                                '.js-plotly-plot'
                            );
                            if (grafico) {
                                grafico.style.visibility = 'visible';
                                graficosAnimados.add(titulo);
                            }
                            return;
                        }
                        animarGraficos();
                    }, 100);
                };

                const animarGraficos = () => {
                    for (const titulo of main.querySelectorAll(
                        '.mi-entry-chart'
                    )) {
                        if (reduzido || graficosAnimados.has(titulo)) continue;
                        const bloco = titulo.closest(
                            '[data-testid="stVerticalBlockBorderWrapper"]'
                        ) || titulo.closest('[data-testid="stVerticalBlock"]');
                        const grafico = bloco?.querySelector('.js-plotly-plot');
                        const barras = [
                            ...(grafico?.querySelectorAll(
                                '.barlayer .point'
                            ) || [])
                        ];
                        if (barras.length) {
                            grafico.style.visibility = 'visible';
                            barras.forEach((barra, indice) => {
                                barra.style.transformBox = 'fill-box';
                                barra.style.transformOrigin = 'center bottom';
                                const entradaBarra = barra.animate(
                                    [
                                        { transform: 'scaleY(0)', opacity: .5 },
                                        { transform: 'scaleY(1)', opacity: 1 }
                                    ],
                                    {
                                        duration: 520,
                                        delay: indice * 65,
                                        easing: 'cubic-bezier(.2,.75,.25,1)',
                                        fill: 'forwards'
                                    }
                                );
                                entradaBarra.onfinish = () =>
                                    entradaBarra.cancel();
                            });
                            graficosAnimados.add(titulo);
                            continue;
                        }
                        const fatias = [
                            ...(grafico?.querySelectorAll(
                                '.pielayer .slice .surface'
                            ) || [])
                        ];
                        if (fatias.length) {
                            grafico.style.visibility = 'visible';
                            fatias.forEach((fatia, indice) => {
                                fatia.style.transformBox = 'fill-box';
                                fatia.style.transformOrigin = 'center';
                                const entradaFatia = fatia.animate(
                                    [
                                        {
                                            transform: 'scale(.08) rotate(-35deg)',
                                            opacity: .2
                                        },
                                        {
                                            transform: 'scale(1) rotate(0)',
                                            opacity: 1
                                        }
                                    ],
                                    {
                                        duration: 680,
                                        delay: indice * 80,
                                        easing: 'cubic-bezier(.2,.75,.25,1)',
                                        fill: 'forwards'
                                    }
                                );
                                entradaFatia.onfinish = () =>
                                    entradaFatia.cancel();
                            });
                            graficosAnimados.add(titulo);
                            continue;
                        }
                        const serie = grafico?.querySelector(
                            '.scatterlayer .trace'
                        );
                        const linha = serie?.querySelector('.js-line');
                        if (!linha || typeof linha.getTotalLength !== 'function') {
                            if (grafico) {
                                agendarTentativaGrafico(titulo);
                            }
                            continue;
                        }
                        try {
                            const comprimento = linha.getTotalLength();
                            if (!Number.isFinite(comprimento) || comprimento <= 0) {
                                agendarTentativaGrafico(titulo);
                                continue;
                            }
                            grafico.style.visibility = 'visible';
                            const preenchimento = serie.querySelector('.js-fill');
                            const pontos = [...serie.querySelectorAll('.point')];
                            linha.style.strokeDasharray =
                                `${comprimento} ${comprimento}`;
                            linha.style.strokeDashoffset = String(comprimento);
                            const desenho = linha.animate(
                                [
                                    { strokeDashoffset: comprimento },
                                    { strokeDashoffset: 0 }
                                ],
                                { duration: 650, easing: 'ease-out', fill: 'forwards' }
                            );
                            desenho.onfinish = () => {
                                linha.style.strokeDasharray = '';
                                linha.style.strokeDashoffset = '';
                                desenho.cancel();
                            };
                            if (preenchimento) {
                                const entradaPreenchimento = preenchimento.animate(
                                    [{ opacity: 0 }, { opacity: 1 }],
                                    {
                                        duration: 380,
                                        delay: 520,
                                        easing: 'ease-out',
                                        fill: 'forwards'
                                    }
                                );
                                entradaPreenchimento.onfinish = () =>
                                    entradaPreenchimento.cancel();
                            }
                            const intervalo = pontos.length > 1
                                ? 360 / (pontos.length - 1)
                                : 0;
                            pontos.forEach((ponto, indice) => {
                                const entradaPonto = ponto.animate(
                                    [{ opacity: 0 }, { opacity: 1 }],
                                    {
                                        duration: 170,
                                        delay: 820 + indice * intervalo,
                                        easing: 'ease-out',
                                        fill: 'forwards'
                                    }
                                );
                                entradaPonto.onfinish = () => entradaPonto.cancel();
                            });
                            graficosAnimados.add(titulo);
                        } catch (_) {
                            linha.style.strokeDasharray = '';
                            linha.style.strokeDashoffset = '';
                            serie.querySelectorAll('.point').forEach(ponto => {
                                ponto.style.opacity = '';
                            });
                            serie.querySelectorAll('.js-fill').forEach(area => {
                                area.style.opacity = '';
                            });
                            grafico.style.visibility = 'visible';
                            graficosAnimados.add(titulo);
                        }
                    }
                };

                const processarElementos = () => {
                    main.querySelectorAll('.mi-count-value').forEach(
                        animarValor
                    );
                    animarGraficos();
                };
                processarElementos();
                new MutationObserver(processarElementos).observe(main, {
                    childList: true,
                    subtree: true
                });
            })();
        </script>
        """,
        unsafe_allow_javascript=True,
    )


def renderizar_card_insight(
    titulo: str,
    valor: str,
    contexto: str,
    icone: str,
    *,
    variante: str = "neutral",
) -> None:
    """Renderiza um insight com hierarquia compatível com os KPIs."""
    if variante not in {"positive", "negative", "neutral"}:
        raise ValueError(f"Variante de insight não reconhecida: {variante}")

    classe_entrada, atraso = proxima_animacao_entrada_pagina()
    valor_html = (
        _html_valor_animado(
            valor,
            atraso,
            iniciar_oculto=bool(classe_entrada),
        )
        if st.session_state.get("_mi_active_page")
        in {
            "visao_geral",
            "vendas_pedidos",
            "marketplaces",
            "produtos_estoque",
        }
        else valor
    )
    st.html(
        f"""
        <article class="mi-insight-card mi-insight-{variante} {classe_entrada}"
                 style="--mi-entry-delay:{atraso}ms">
            <div class="mi-insight-heading">
                <span class="mi-insight-icon">{icone_svg(icone, tamanho=18)}</span>
                <span class="mi-insight-title">{escape(titulo)}</span>
            </div>
            <div class="mi-insight-value">{valor_html}</div>
            <div class="mi-insight-context">{escape(contexto)}</div>
        </article>
        <style>
            .mi-insight-card {{
                min-height: 118px;
                padding: 13px 15px;
                border: 1px solid rgba(143, 161, 184, .12);
                border-top: 2px solid rgba(115, 169, 255, .44);
                border-radius: var(--mi-radius-card);
                background:
                    linear-gradient(145deg, rgba(115, 169, 255, .055), transparent 62%),
                    var(--mi-color-surface);
                box-shadow: 0 5px 16px rgba(0, 0, 0, .14);
                transition:
                    transform 180ms ease,
                    border-color 180ms ease,
                    box-shadow 180ms ease;
            }}
            .mi-insight-card:hover {{
                transform: translateY(-2px);
                border-color: rgba(115, 169, 255, .28);
                box-shadow: 0 10px 22px rgba(0, 0, 0, .22);
            }}
            .mi-insight-heading {{
                display: flex;
                align-items: center;
                gap: 8px;
                color: var(--mi-color-text-muted);
                font-size: 12px;
                line-height: 16px;
            }}
            .mi-insight-icon {{
                display: inline-flex;
                color: var(--mi-color-brand);
            }}
            .mi-insight-value {{
                overflow: hidden;
                margin-top: 9px;
                color: #E8EEF7;
                font-size: clamp(22px, 1.8vw, 27px);
                font-weight: 700;
                letter-spacing: -.025em;
                line-height: 1.15;
                text-overflow: ellipsis;
                white-space: nowrap;
            }}
            .mi-insight-value,
            .mi-card-value {{
                font-variant-numeric: tabular-nums;
            }}
            .mi-count-final {{
                position: absolute;
                width: 1px;
                height: 1px;
                overflow: hidden;
                clip-path: inset(50%);
                white-space: nowrap;
            }}
            .mi-insight-context {{
                overflow: hidden;
                margin-top: 5px;
                color: #A8B6C9;
                font-size: 12px;
                line-height: 16px;
                text-overflow: ellipsis;
                white-space: nowrap;
            }}
            .mi-insight-positive .mi-insight-icon {{
                color: var(--mi-color-success);
            }}
            .mi-insight-negative {{
                border-top-color: rgba(255, 128, 109, .6);
            }}
            .mi-insight-negative .mi-insight-icon {{
                color: var(--mi-color-danger);
            }}
            .mi-insight-neutral .mi-insight-icon {{
                color: var(--mi-color-brand);
            }}
            @media (prefers-reduced-motion: reduce) {{
                .mi-insight-card {{
                    transition: none;
                }}
            }}
        </style>
        """
    )


def card(
    titulo,
    valor,
    icone,
    descricao="",
    tipo="normal",
    tooltip="",
    *,
    peso: str = "normal",
    sparkline: list[float] | None = None,
    cor_valor: str = "normal",
):

    if peso not in {"normal", "principal", "operacional"}:
        raise ValueError(f"Peso visual de card não reconhecido: {peso}")
    if cor_valor not in {"normal", "positive", "negative", "neutral"}:
        raise ValueError(f"Cor de valor não reconhecida: {cor_valor}")

    icone_html = (
        icone_svg(icone)
        if isinstance(icone, str) and icone in _ICONES_SVG
        else escape(str(icone))
    )
    indicador_tooltip = (
        '<span class="mi-card-info" tabindex="0" '
        'aria-label="Mais informações">'
        f'<span class="mi-card-info-symbol">'
        "i</span>"
        f'<span class="mi-card-tooltip">'
        f'{escape(str(tooltip))}</span></span>'
        if tooltip
        else ""
    )
    sparkline_html = ""
    if sparkline and len(sparkline) > 1:
        valores_sparkline = [
            float(valor)
            for valor in sparkline
            if isfinite(float(valor))
        ]
        if len(valores_sparkline) > 1:
            minimo = min(valores_sparkline)
            intervalo = max(valores_sparkline) - minimo
            pontos = " ".join(
                f"{indice * 100 / (len(valores_sparkline) - 1):.1f},"
                f"{22 - ((valor - minimo) / intervalo * 20 if intervalo else 10):.1f}"
                for indice, valor in enumerate(valores_sparkline)
            )
            sparkline_html = (
                '<svg class="mi-card-sparkline" viewBox="0 0 100 24" '
                'preserveAspectRatio="none" aria-hidden="true">'
                f'<polyline points="{pontos}"/></svg>'
            )
    descricao_html = (
        f'<div class="mi-card-description">{descricao}</div>'
        if descricao
        else ""
    )

    classe_entrada, atraso = proxima_animacao_entrada_pagina()
    valor_html = (
        _html_valor_animado(
            valor,
            atraso,
            iniciar_oculto=bool(classe_entrada),
        )
        if st.session_state.get("_mi_active_page")
        in {"visao_geral", "vendas_pedidos", "produtos_estoque"}
        else valor
    )
    html = f"""
    <div class="mi-card mi-card-{tipo} mi-card-{peso}
                mi-card-value-{cor_valor} {classe_entrada}"
         style="--mi-entry-delay:{atraso}ms">

        <div class="mi-card-glow-clip">
            <div class="mi-card-glow"></div>
        </div>

        <div class="mi-card-content">

            <div class="mi-card-header">

                <span class="mi-card-icon">
                    {icone_html}
                </span>

                <span class="mi-card-title">
                    {titulo}
                </span>
                {indicador_tooltip}

            </div>

            <div class="mi-card-value">
                {valor_html}
            </div>

            {sparkline_html}

            {descricao_html}

        </div>

    </div>

    <style>

        /* =====================================================
           ANIMAÇÃO DE ENTRADA
           ===================================================== */

        /* =====================================================
           CARD
           ===================================================== */

        .mi-card {{

            position: relative;

            overflow: visible;

            background:
                linear-gradient(
                    145deg,
                    #1E293B,
                    #111827
                );

            padding: 14px 16px;

            border-radius: var(--mi-radius-card);

            min-height: 104px;

            border:
                1px solid rgba(255,255,255,0.08);

            box-shadow:
                0 8px 24px rgba(0,0,0,0.20);

            box-sizing: border-box;

            margin-bottom: 8px;

            transition:
                transform 220ms ease,
                box-shadow 220ms ease,
                border-color 220ms ease,
                background 220ms ease;

        }}

        .mi-card-principal {{
            height: 112px;
            min-height: 112px;
            overflow: visible;
            padding: 12px 14px;
            border-color: rgba(115, 169, 255, .28);
            border-top: 2px solid rgba(115, 169, 255, .7);
            background:
                linear-gradient(
                    145deg,
                    rgba(115, 169, 255, .1),
                    transparent 68%
                ),
                linear-gradient(145deg, #1E293B, #111827);
            box-shadow:
                0 5px 16px rgba(0, 0, 0, .15),
                inset 0 1px 0 rgba(255, 255, 255, .035);
        }}

        .mi-card-principal .mi-card-content {{
            display: flex;
            height: 100%;
            flex-direction: column;
            align-items: flex-start;
        }}

        .mi-card-principal .mi-card-header {{
            width: 100%;
            min-height: 16px;
            margin: 0;
        }}

        .mi-card-principal .mi-card-icon {{
            display: none;
        }}

        .mi-card-principal .mi-card-title {{
            color: #A8B8CC;
            font-size: 12px;
            font-weight: 600;
            line-height: 16px;
        }}

        .mi-card-principal .mi-card-info {{
            width: 13px;
            height: 13px;
            margin-left: 0;
            font-size: 9px;
        }}

        .mi-card-principal .mi-card-info-symbol {{
            font-size: 8px;
            font-style: normal;
        }}

        .mi-card-principal .mi-card-value {{
            position: relative;
            z-index: 2;
            margin: 3px 0 0;
            color: #DCEAFF;
            font-size: clamp(23px, 1.85vw, 31px);
            line-height: 1.08;
            letter-spacing: -.035em;
            white-space: nowrap;
        }}

        .mi-card-operacional.mi-card-value-positive .mi-card-value {{
            color: #8AE3A8;
        }}

        .mi-card-operacional.mi-card-value-negative .mi-card-value {{
            color: #FF9A91;
        }}

        .mi-card-operacional.mi-card-value-neutral .mi-card-value {{
            color: #C5D0DE;
        }}

        .mi-card-principal.mi-card-value-positive .mi-card-value {{
            color: #8AE3A8;
        }}

        .mi-card-principal.mi-card-value-negative .mi-card-value {{
            color: #FF9A91;
        }}

        .mi-card-principal.mi-card-value-neutral .mi-card-value {{
            color: #C5D0DE;
        }}

        .mi-card-operacional {{
            height: 92px;
            min-height: 92px;
            overflow: visible;
            padding: 10px 12px;
            background: linear-gradient(145deg, #192536, #111827);
            box-shadow: 0 3px 11px rgba(0, 0, 0, .13);
        }}

        .mi-card-operacional .mi-card-content {{
            display: grid;
            height: 100%;
            grid-template-columns: minmax(0, 1fr) 17px 15px;
            grid-template-rows: 17px 1fr 16px;
            grid-template-areas:
                "title icon info"
                "value value value"
                "description description description";
            align-items: center;
        }}

        .mi-card-operacional .mi-card-header {{
            display: contents;
        }}

        .mi-card-operacional .mi-card-title {{
            grid-area: title;
            overflow: hidden;
            color: #9AAABD;
            font-size: 12px;
            line-height: 16px;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}

        .mi-card-operacional .mi-card-icon {{
            width: 18px;
            height: 18px;
            grid-area: icon;
            justify-self: end;
        }}

        .mi-card-operacional .mi-card-icon .mi-icon {{
            width: 16px;
            height: 16px;
            color: #7893B5;
        }}

        .mi-card-operacional .mi-card-info {{
            position: static;
            grid-area: info;
            width: 13px;
            height: 13px;
            font-size: 9px;
        }}

        .mi-card-operacional .mi-card-info-symbol {{
            font-size: 8px;
        }}

        .mi-card-operacional .mi-card-value {{
            min-width: 0;
            grid-area: value;
            margin: 0;
            color: #E8EEF7;
            font-size: clamp(20px, 1.5vw, 23px);
            line-height: 1.1;
            letter-spacing: -.02em;
            white-space: nowrap;
        }}

        .mi-card-operacional .mi-card-description {{
            min-width: 0;
            grid-area: description;
            overflow: hidden;
            color: #8597AD;
            font-size: 12px;
            line-height: 15px;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}

        .mi-card-sparkline {{
            position: absolute;
            right: 9px;
            bottom: 7px;
            z-index: 1;
            width: 42%;
            height: 25px;
            margin: 0;
            opacity: .11;
            pointer-events: none;
        }}

        .mi-card-sparkline polyline {{
            fill: none;
            stroke: var(--mi-color-brand);
            stroke-width: 1.5;
            stroke-linecap: round;
            stroke-linejoin: round;
            vector-effect: non-scaling-stroke;
        }}


        /* =====================================================
           HOVER
           ===================================================== */

        .mi-card:hover {{

            transform:
                translateY(-3px);

            z-index: 20;

            box-shadow:
                0 18px 38px rgba(0,0,0,0.38);

            border-color:
                rgba(115,169,255,0.34);

            background:
                linear-gradient(
                    145deg,
                    #26364D,
                    #141D2D
                );

        }}

        [data-testid="stElementContainer"]:has(.mi-card:hover) {{
            position: relative;
            z-index: 80;
        }}


        /* =====================================================
           BRILHO
           ===================================================== */

        .mi-card-glow-clip {{

            position: absolute;

            inset: 0;

            overflow: hidden;

            border-radius: inherit;

            pointer-events: none;

        }}

        .mi-card-glow {{

            position: absolute;

            width: 160px;
            height: 160px;

            right: -80px;
            top: -80px;

            background:
                radial-gradient(
                    circle,
                    rgba(59,130,246,0.20),
                    transparent 70%
                );

            opacity: 0;

            pointer-events: none;

            transition:
                opacity 250ms ease,
                transform 400ms ease;

        }}


        .mi-card:hover .mi-card-glow {{

            opacity: 1;

            transform:
                scale(1.35);

        }}


        /* =====================================================
           CONTEÚDO
           ===================================================== */

        .mi-card-content {{

            position: relative;

            z-index: 1;

        }}


        .mi-card-header {{

            display: flex;

            align-items: center;

            gap: 8px;

            margin-bottom: 5px;

        }}


        .mi-card-icon {{

            display: inline-flex;
            width: 22px;
            height: 22px;
            flex: 0 0 22px;
            align-items: center;
            justify-content: center;

            transition:
                transform 220ms ease;

        }}

        .mi-card-icon .mi-icon {{
            width: 20px;
            height: 20px;
            color: var(--mi-color-brand);
        }}


        .mi-card:hover .mi-card-icon {{

            transform:
                scale(1.12)
                translateY(-1px);

        }}


        .mi-card-title {{

            color: #94A3B8;

            font-size: 14px;

            line-height: 20px;

        }}

        .mi-card-info {{

            position: relative;

            display: inline-flex;

            align-items: center;

            justify-content: center;

            width: 15px;
            height: 15px;
            flex: 0 0 15px;

            border: 1px solid #64748B;

            border-radius: 50%;

            color: #94A3B8;

            font-size: 10px;
            font-weight: 700;

            line-height: 1;

            cursor: pointer;

            transition:
                color 180ms ease,
                border-color 180ms ease,
                background 180ms ease,
                box-shadow 180ms ease;

        }}

        .mi-card-info-symbol {{

            display: inline-block;

            font-size: 10px;

            font-weight: 800;

            line-height: 1;

            transform: translateY(-.25px);

        }}

        .mi-card-info:hover,
        .mi-card-info:focus-visible {{

            border-color: #60A5FA;

            background: rgba(59, 130, 246, .16);

            color: #DBEAFE;

            box-shadow: 0 0 12px rgba(59, 130, 246, .28);

            outline: none;

        }}

        .mi-card-tooltip {{

            position: absolute;

            bottom: calc(100% + 12px);

            left: 50%;

            z-index: 30;

            width: max-content;

            max-width: min(280px, calc(100vw - 36px));

            padding: 10px 12px;

            border: 1px solid rgba(96, 165, 250, .42);

            border-radius: 8px;

            background: rgba(11, 18, 32, .97);

            box-shadow:
                0 12px 28px rgba(0, 0, 0, .42),
                0 0 18px rgba(59, 130, 246, .12);

            color: #E2E8F0;

            font-size: 12px;

            font-weight: 450;

            line-height: 1.5;

            text-align: left;

            white-space: normal;

            opacity: 0;

            visibility: hidden;

            pointer-events: none;

            transform: translate(-50%, 7px) scale(.97);

            transform-origin: bottom center;

            transition:
                opacity 170ms ease,
                transform 220ms cubic-bezier(.2, .7, .2, 1),
                visibility 170ms ease;

        }}

        .mi-card-tooltip::after {{

            position: absolute;

            top: 100%;

            left: 50%;

            width: 8px;

            height: 8px;

            border-right: 1px solid rgba(96, 165, 250, .42);

            border-bottom: 1px solid rgba(96, 165, 250, .42);

            background: #0B1220;

            content: "";

            transform: translate(-50%, -50%) rotate(45deg);

        }}

        .mi-card-info:hover .mi-card-tooltip,
        .mi-card-info:focus-visible .mi-card-tooltip {{

            opacity: 1;

            visibility: visible;

            transform: translate(-50%, 0) scale(1);

        }}


        .mi-card-value {{

            color: white;

            font-size: 27px;

            font-weight: 700;

            line-height: 32px;

            margin-bottom: 3px;

        }}

        .mi-count-value {{
            font-variant-numeric: tabular-nums;
        }}

        .mi-count-final {{
            position: absolute;
            width: 1px;
            height: 1px;
            overflow: hidden;
            clip-path: inset(50%);
            white-space: nowrap;
        }}


        .mi-card-description {{

            color: #64748B;

            font-size: 12px;

            line-height: 18px;

        }}

        .mi-card-principal .mi-card-description {{
            position: relative;
            z-index: 2;
            max-width: 78%;
            overflow: hidden;
            margin-top: auto;
            font-size: 12px;
            font-weight: 550;
            line-height: 15px;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}

        .mi-card-description:empty {{
            display: none;
        }}


        .mi-card-positive .mi-card-description {{

            color: #4ADE80;

        }}


        .mi-card-negative .mi-card-description {{

            color: #FB7185;

        }}


        .mi-card-neutral .mi-card-description {{
            color: #A0AEC0;

        }}

    </style>
    """

    st.html(html)


# =========================================================
# HERO
# =========================================================

def hero(
    titulo,
    periodo,
    valor1,
    valor2,
    valor3,
    valor4,
    label1,
    label2,
    label3,
    label4
):

    html = f"""
    <div class="mi-hero">

        <div class="mi-hero-glow"></div>

        <div class="mi-hero-content">

            <div class="mi-hero-title">
                {titulo}
            </div>

            <div class="mi-hero-period">
                {periodo}
            </div>

            <div class="mi-hero-metrics">

                <div class="mi-hero-metric">
                    <div class="mi-hero-label">
                        {label1}
                    </div>

                    <div class="mi-hero-value">
                        {valor1}
                    </div>
                </div>

                <div class="mi-hero-metric">
                    <div class="mi-hero-label">
                        {label2}
                    </div>

                    <div class="mi-hero-value">
                        {valor2}
                    </div>
                </div>

                <div class="mi-hero-metric">
                    <div class="mi-hero-label">
                        {label3}
                    </div>

                    <div class="mi-hero-value">
                        {valor3}
                    </div>
                </div>

                <div class="mi-hero-metric mi-hero-highlight">
                    <div class="mi-hero-label">
                        {label4}
                    </div>

                    <div class="mi-hero-value">
                        {valor4}
                    </div>
                </div>

            </div>

        </div>

    </div>

    <style>

        /* =====================================================
           ANIMAÇÃO
           ===================================================== */

        @keyframes mi-hero-enter {{

            from {{
                opacity: 0;

                transform:
                    translateX(-45px)
                    translateY(12px)
                    scale(0.985);

                filter: blur(3px);
            }}

            to {{
                opacity: 1;

                transform:
                    translateX(0)
                    translateY(0)
                    scale(1);

                filter: blur(0);
            }}

        }}


        /* =====================================================
           HERO
           ===================================================== */

        .mi-hero {{

            position: relative;

            overflow: hidden;

            background:
                linear-gradient(
                    135deg,
                    #1E293B 0%,
                    #111827 55%,
                    #0F172A 100%
                );

            padding: 24px 28px;

            border-radius: 20px;

            margin-bottom: 22px;

            border:
                1px solid rgba(255,255,255,0.08);

            box-shadow:
                0 10px 30px rgba(0,0,0,0.25);

            box-sizing: border-box;

            transition:
                transform 260ms ease,
                box-shadow 260ms ease,
                border-color 260ms ease;

        }}


        /* =====================================================
           HOVER
           ===================================================== */

        .mi-hero:hover {{

            transform:
                translateY(-4px);

            box-shadow:
                0 18px 45px rgba(0,0,0,0.38);

            border-color:
                rgba(96,165,250,0.25);

        }}


        /* =====================================================
           GLOW
           ===================================================== */

        .mi-hero-glow {{

            position: absolute;

            width: 260px;
            height: 260px;

            right: -100px;
            top: -130px;

            background:
                radial-gradient(
                    circle,
                    rgba(59,130,246,0.18),
                    transparent 70%
                );

            pointer-events: none;

            opacity: 0.45;

            transition:
                transform 500ms ease,
                opacity 300ms ease;

        }}


        .mi-hero:hover .mi-hero-glow {{

            transform:
                scale(1.5);

            opacity:
                0.85;

        }}


        /* =====================================================
           CONTEÚDO
           ===================================================== */

        .mi-hero-content {{

            position: relative;

            z-index: 1;

        }}


        .mi-hero-title {{

            color: #94A3B8;

            font-size: 14px;

            line-height: 20px;

        }}


        .mi-hero-period {{

            color: white;

            font-size: 17px;

            font-weight: 600;

            margin-top: 2px;

            line-height: 22px;

        }}


        .mi-hero-metrics {{

            display: grid;

            grid-template-columns:
                repeat(4, 1fr);

            gap: 24px;

            margin-top: 22px;

        }}


        .mi-hero-metric {{

            transition:
                transform 220ms ease;

        }}


        .mi-hero:hover .mi-hero-metric {{

            transform:
                translateY(-2px);

        }}


        .mi-hero-label {{

            color: #94A3B8;

            font-size: 12px;

            line-height: 18px;

        }}


        .mi-hero-value {{

            color: white;

            font-size: 30px;

            font-weight: 700;

            line-height: 36px;

            transition:
                text-shadow 220ms ease,
                transform 220ms ease;

        }}


        .mi-hero-highlight .mi-hero-value {{

            color: #22C55E;

        }}


        .mi-hero:hover
        .mi-hero-highlight
        .mi-hero-value {{

            text-shadow:
                0 0 18px rgba(34,197,94,0.28);

            transform:
                translateX(2px);

        }}

    </style>
    """

    st.html(html)


# =========================================================
# ANIMAÇÃO DE ENTRADA DA PÁGINA
# =========================================================

def animar_pagina(nome):

    nome = nome.replace("-", "_").replace(" ", "_")
    pagina_anterior = st.session_state.get("_mi_active_page")
    entrou_na_pagina = pagina_anterior != nome
    st.session_state["_mi_active_page"] = nome
    st.session_state["_mi_page_entering"] = entrou_na_pagina
    st.session_state["_mi_chart_animation_index"] = 0
    if entrou_na_pagina:
        st.session_state["_mi_page_entry_index"] = 0
        st.html(
            """
            <style>
                @keyframes mi-page-content-enter {
                    from {
                        opacity: 0;
                        transform: translateY(5px);
                    }
                    to {
                        opacity: 1;
                        transform: translateY(0);
                    }
                }
                .st-key-mi-page-content {
                    animation: mi-page-content-enter 180ms ease-out both;
                }
                @media (prefers-reduced-motion: reduce) {
                    .st-key-mi-page-content {
                        animation: none;
                    }
                }
            </style>
            """
        )


def animar_elementos_rolagem() -> None:
    """Revela painéis suavemente ao entrarem na área visível da página."""

    st.html(
        """
        <style>
            @media (prefers-reduced-motion: no-preference) {
                [data-testid="stMainBlockContainer"] .mi-scroll-reveal {
                    opacity: 0;
                    transform: translateY(14px);
                    transition:
                        opacity 360ms ease,
                        transform 360ms cubic-bezier(.2, .7, .2, 1);
                    will-change: opacity, transform;
                }
                [data-testid="stMainBlockContainer"]
                .mi-scroll-reveal.mi-scroll-visible {
                    opacity: 1;
                    transform: translateY(0);
                }
            }
        </style>
        <script>
            (() => {
                if (
                    window.__miScrollRevealInitialized
                    || !("IntersectionObserver" in window)
                ) return;
                const main = document.querySelector(
                    '[data-testid="stMain"]'
                );
                if (!main) return;
                window.__miScrollRevealInitialized = true;
                const selector = [
                    '[data-testid="stMainBlockContainer"]'
                        + ' > [data-testid="stVerticalBlock"]'
                        + ' > [data-testid="stElementContainer"]',
                    '[data-testid="stMainBlockContainer"]'
                        + ' > [data-testid="stVerticalBlock"]'
                        + ' > [data-testid="stLayoutWrapper"]'
                ].join(",");
                const observeNewPanels = () => {
                    document.querySelectorAll(selector).forEach((panel) => {
                        if (panel.querySelector(".mi-global-filters-anchor")) {
                            if (panel.dataset.miScrollObserved) {
                                observer.unobserve(panel);
                                panel.classList.remove(
                                    "mi-scroll-reveal",
                                    "mi-scroll-visible"
                                );
                                delete panel.dataset.miScrollObserved;
                            }
                            return;
                        }
                        if (panel.dataset.miScrollObserved) return;
                        panel.dataset.miScrollObserved = "true";
                        panel.classList.add("mi-scroll-reveal");
                        observer.observe(panel);
                    });
                };
                const observer = new IntersectionObserver((entries) => {
                    entries.forEach((entry) => {
                        entry.target.classList.toggle(
                            "mi-scroll-visible",
                            entry.isIntersecting
                        );
                    });
                }, {threshold: 0.08, rootMargin: "0px 0px -4% 0px"});
                observeNewPanels();
                new MutationObserver(observeNewPanels).observe(main, {
                    childList: true,
                    subtree: true
                });
            })();
        </script>
        """,
        unsafe_allow_javascript=True,
    )


# =========================================================
# ESTILO GLOBAL
# =========================================================

def aplicar_estilo():

    tokens_css = ";".join(
        f"--mi-{nome}: {valor}"
        for nome, valor in DESIGN_TOKENS.items()
    )
    st.markdown(
        f"<style>:root {{{tokens_css}}}</style>",
        unsafe_allow_html=True
    )

    st.markdown(
        """

        <style>


        /* =====================================================
           FUNDO
           ===================================================== */

        .stApp {

            background-color:
                var(--mi-color-background);

        }

        .stButton > button,
        [data-testid="stBaseButton-primary"] {
            border-radius: var(--mi-radius-control);
            border-color: var(--mi-color-border);
            transition:
                background-color 160ms ease,
                border-color 160ms ease,
                color 160ms ease,
                box-shadow 160ms ease,
                transform 160ms ease;
        }

        [data-testid="stBaseButton-primary"] {
            border-color: var(--mi-color-brand-strong);
            background: linear-gradient(
                145deg,
                #5B9BF4,
                var(--mi-color-brand-strong) 72%
            );
            color: #FFFFFF;
            box-shadow: 0 3px 10px rgba(79, 145, 245, .12);
        }

        .stButton > button:not(:disabled):hover,
        [data-testid="stBaseButton-primary"]:not(:disabled):hover {
            border-color: var(--mi-color-brand);
            color: var(--mi-color-text);
            box-shadow:
                0 0 0 1px rgba(115, 169, 255, .22),
                0 0 18px rgba(79, 145, 245, .2);
            transform: translateY(-1px);
        }

        .stButton > button:not(:disabled):active,
        [data-testid="stBaseButton-primary"]:not(:disabled):active {
            transform: translateY(0);
            box-shadow:
                inset 0 2px 5px rgba(10, 31, 63, .3),
                0 0 0 1px rgba(115, 169, 255, .24);
        }

        [data-testid="stBaseButton-primary"]:disabled {
            opacity: .52;
            filter: saturate(.7);
        }

        .stButton > button:disabled {
            cursor: not-allowed;
            opacity: .48;
            transform: none;
        }

        [data-testid="stBaseButton-primary"][aria-busy="true"] {
            cursor: progress;
            opacity: .72;
        }

        .stButton > button[aria-busy="true"] {
            cursor: progress;
            opacity: .76;
        }

        [data-testid="stTextInput"] input,
        [data-testid="stTextArea"] textarea,
        [data-testid="stNumberInput"] input,
        [data-testid="stDateInput"] input,
        [data-testid="stSelectbox"] [role="combobox"],
        [data-testid="stMultiSelect"] [role="combobox"] {
            border-color: var(--mi-color-border);
            border-radius: var(--mi-radius-control);
            background-color: var(--mi-color-surface);
            color: var(--mi-color-text);
            transition:
                border-color 160ms ease,
                box-shadow 160ms ease;
        }

        [data-testid="stTextInput"] input:focus,
        [data-testid="stTextArea"] textarea:focus,
        [data-testid="stNumberInput"] input:focus,
        [data-testid="stDateInput"] input:focus,
        [data-testid="stSelectbox"] [role="combobox"]:focus,
        [data-testid="stMultiSelect"] [role="combobox"]:focus {
            border-color: var(--mi-color-brand);
            box-shadow: 0 0 0 1px rgba(115, 169, 255, .24);
        }

        [data-testid="stTextInput"] input[aria-invalid="true"],
        [data-testid="stTextArea"] textarea[aria-invalid="true"],
        [data-testid="stNumberInput"] input[aria-invalid="true"] {
            border-color: var(--mi-color-danger);
            box-shadow: 0 0 0 1px rgba(255, 128, 109, .2);
        }

        [data-testid="stFileUploader"] section {
            padding: 14px 16px;
            border: 1px dashed var(--mi-color-border);
            border-radius: var(--mi-radius-card);
            background: var(--mi-color-surface);
            transition:
                border-color 160ms ease,
                background-color 160ms ease;
        }

        [data-testid="stFileUploader"] section:hover {
            border-color: var(--mi-color-brand);
            background: rgba(115, 169, 255, .04);
        }

        [aria-busy="true"] {
            cursor: progress;
        }

        a,
        a:visited {
            color: #8DB9F8;
            text-decoration-color: rgba(141, 185, 248, .38);
            transition:
                color 150ms ease,
                text-decoration-color 150ms ease;
        }

        a:hover,
        a:focus-visible {
            color: #C5DEFF;
            text-decoration-color: currentColor;
        }

        :focus-visible {
            outline: 2px solid rgba(115, 169, 255, .72);
            outline-offset: 2px;
        }

        [data-testid="stSlider"] [role="slider"] {
            border-color: var(--mi-color-brand);
            background: var(--mi-color-brand-strong);
            box-shadow: 0 0 0 2px rgba(79, 145, 245, .16);
        }

        [data-testid="stSlider"] [data-baseweb="slider"] > div > div {
            background: var(--mi-color-brand-strong);
        }

        [data-testid="stTabs"] [role="tab"] {
            color: var(--mi-color-text-muted);
            transition: color 150ms ease, background-color 150ms ease;
        }

        [data-testid="stTabs"] [role="tab"]:hover,
        [data-testid="stTabs"] [role="tab"][aria-selected="true"] {
            color: var(--mi-color-brand);
        }

        [data-testid="stTabs"] [data-baseweb="tab-highlight"] {
            background: var(--mi-color-brand-strong);
        }

        .mi-skeleton-grid {
            display: grid;
            gap: 12px;
            margin-bottom: 9px;
        }

        .mi-skeleton-grid-primary {
            grid-template-columns: repeat(4, minmax(0, 1fr));
        }

        .mi-skeleton-grid-secondary {
            grid-template-columns: repeat(5, minmax(0, 1fr));
        }

        .mi-skeleton-grid-charts {
            grid-template-columns: 2fr 1fr;
            margin-top: 15px;
        }

        .mi-skeleton-grid-orders {
            grid-template-columns: repeat(6, minmax(0, 1fr));
            margin-bottom: 12px;
        }

        .mi-skeleton {
            position: relative;
            overflow: hidden;
            border: 1px solid rgba(143, 161, 184, .1);
            border-radius: var(--mi-radius-card);
            background: linear-gradient(
                145deg,
                rgba(30, 41, 59, .9),
                rgba(18, 28, 43, .9)
            );
        }

        .mi-skeleton::after {
            position: absolute;
            inset: 0;
            background: linear-gradient(
                100deg,
                transparent 20%,
                rgba(115, 169, 255, .08) 48%,
                transparent 76%
            );
            content: "";
            transform: translateX(-100%);
            animation: mi-skeleton-shimmer 1.6s ease-in-out infinite;
        }

        .mi-skeleton-summary {
            height: 64px;
            margin-bottom: 12px;
        }

        .mi-skeleton-kpi {
            height: 136px;
        }

        .mi-skeleton-secondary {
            height: 90px;
        }

        .mi-skeleton-chart {
            height: 280px;
        }

        .mi-skeleton-table {
            height: 220px;
            margin-top: 18px;
        }

        .mi-skeleton-order-card {
            height: 92px;
        }

        .mi-skeleton-orders-table {
            height: 360px;
        }

        .mi-skeleton-marketplace-table {
            height: 440px;
            margin: 8px 0 18px;
        }

        .mi-skeleton-marketplace-participation {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 14px;
        }

        .mi-skeleton-marketplace-card {
            height: 270px;
            border-radius: var(--mi-radius-card);
        }

        .mi-skeleton-product-kpis {
            display: grid;
            grid-template-columns: repeat(5, minmax(0, 1fr));
            gap: 10px;
            margin-bottom: 16px;
        }

        .mi-skeleton-product-kpi {
            height: 92px;
        }

        .mi-skeleton-product-rankings {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 14px;
        }

        .mi-skeleton-product-ranking {
            height: 370px;
        }

        .mi-skeleton-product-highlights {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 10px;
            margin-top: 16px;
        }

        .mi-skeleton-product-stock-panels {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 14px;
            margin-top: 16px;
        }

        .mi-skeleton-product-stock-panel {
            height: 300px;
        }

        .mi-skeleton-product-controls {
            height: 42px;
            margin-bottom: 10px;
        }

        .mi-skeleton-product-portfolio-table {
            height: 385px;
        }

        .mi-skeleton-product-pagination {
            height: 38px;
            margin-top: 10px;
        }

        @media (max-width: 900px) {
            .mi-skeleton-product-kpis {
                grid-template-columns: repeat(3, minmax(0, 1fr));
            }
            .mi-skeleton-product-highlights {
                grid-template-columns: 1fr;
            }
        }

        @media (max-width: 680px) {
            .mi-skeleton-product-kpis {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
            .mi-skeleton-product-rankings {
                grid-template-columns: 1fr;
            }
            .mi-skeleton-product-stock-panels {
                grid-template-columns: 1fr;
            }
        }

        div[data-testid="stVerticalBlock"]:has(
            .mi-orders-table-anchor
        ) [data-testid="stDataFrame"] {
            overflow: hidden;
            border: 1px solid rgba(143, 161, 184, .12);
            border-radius: var(--mi-radius-card);
            background: rgba(18, 28, 43, .35);
        }

        @media (max-width: 1100px) {
            .mi-skeleton-grid-orders {
                grid-template-columns: repeat(3, minmax(0, 1fr));
            }
        }

        @media (max-width: 680px) {
            .mi-skeleton-grid-orders {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
        }

        @keyframes mi-skeleton-shimmer {
            to { transform: translateX(100%); }
        }

        @media (prefers-reduced-motion: reduce) {
            .mi-skeleton::after {
                animation: none;
            }
        }

        .stApp:has(.mi-login-layout) [data-testid="stSidebar"] {
            display: none;
        }

        .stApp:has(.mi-login-layout) [data-testid="stMainBlockContainer"] {
            display: flex;
            min-height: 100vh;
            flex-direction: column;
            justify-content: center;
            padding: clamp(20px, 4vh, 42px) clamp(20px, 6vw, 88px);
        }

        .mi-login-layout {
            width: 100%;
            max-width: 1040px;
            height: 0;
            margin: 0 auto;
        }

        .stApp:has(.mi-login-layout) [data-testid="stHorizontalBlock"] {
            width: 100%;
            max-width: 1040px;
            align-items: stretch;
            gap: clamp(20px, 5vw, 68px);
            margin: 0 auto;
        }

        .mi-login-story {
            position: relative;
            isolation: isolate;
            display: flex;
            min-height: 560px;
            overflow: hidden;
            flex-direction: column;
            justify-content: flex-start;
            gap: clamp(42px, 7vh, 60px);
            padding: clamp(26px, 3.5vw, 42px);
            border: 1px solid rgba(115, 169, 255, .18);
            border-radius: 24px;
            background:
                radial-gradient(
                    circle at 78% 24%,
                    rgba(79, 145, 245, .2),
                    transparent 36%
                ),
                linear-gradient(145deg, #17263B 0%, #111B2A 58%, #101827 100%);
            box-shadow:
                0 28px 70px rgba(0, 0, 0, .28),
                inset 0 1px 0 rgba(255, 255, 255, .04);
        }

        .mi-login-story::before {
            position: absolute;
            z-index: 0;
            top: -18%;
            left: -16%;
            width: 112%;
            height: 108%;
            border-radius: 42%;
            background:
                radial-gradient(ellipse at 35% 35%,
                    rgba(66, 142, 255, .58) 0%,
                    rgba(66, 142, 255, .2) 28%,
                    transparent 62%),
                radial-gradient(ellipse at 70% 55%,
                    rgba(58, 205, 220, .38) 0%,
                    rgba(58, 205, 220, .13) 31%,
                    transparent 66%),
                radial-gradient(ellipse at 54% 80%,
                    rgba(137, 104, 255, .3) 0%,
                    transparent 55%);
            content: "";
            filter: blur(32px) saturate(1.2);
            opacity: .9;
            pointer-events: none;
            animation: mi-login-smoke-drift 11s ease-in-out infinite alternate;
        }

        .mi-login-story::after {
            position: absolute;
            z-index: 0;
            top: 8%;
            left: 25%;
            width: 90%;
            height: 78%;
            border-radius: 48%;
            background:
                radial-gradient(ellipse at 40% 40%,
                    rgba(101, 172, 255, .34) 0%,
                    transparent 58%),
                radial-gradient(ellipse at 75% 65%,
                    rgba(74, 219, 201, .27) 0%,
                    transparent 55%);
            content: "";
            filter: blur(42px) saturate(1.25);
            opacity: .74;
            pointer-events: none;
            animation: mi-login-smoke-bloom 15s ease-in-out infinite alternate;
        }

        @keyframes mi-login-smoke-drift {
            0% { transform: translate(-8%, -7%) rotate(-8deg) scale(.88, .92); }
            50% { transform: translate(8%, 3%) rotate(5deg) scale(1.05, 1.1); }
            100% { transform: translate(2%, 12%) rotate(-3deg) scale(.98, 1.04); }
        }

        @keyframes mi-login-smoke-bloom {
            from { transform: translate(12%, -8%) rotate(12deg) scale(.82); }
            to { transform: translate(-12%, 14%) rotate(-9deg) scale(1.16); }
        }

        @media (prefers-reduced-motion: reduce) {
            .mi-login-story::before,
            .mi-login-story::after {
                animation: none;
                transform: translate(3%, 4%);
            }
        }

        .mi-login-story-brand {
            position: relative;
            z-index: 1;
            display: flex;
            align-items: center;
            gap: 11px;
            color: #DCE9FB;
            font-size: 10px;
            font-weight: 750;
            letter-spacing: .11em;
        }

        .mi-login-story-mark {
            display: grid;
            width: 40px;
            height: 40px;
            place-items: center;
            border: 1px solid rgba(115, 169, 255, .28);
            border-radius: 12px;
            background: rgba(115, 169, 255, .11);
            color: var(--mi-color-brand);
        }

        .mi-login-story-copy,
        .mi-login-story-foot {
            position: relative;
            z-index: 1;
        }

        .mi-login-story-eyebrow {
            color: #8DB9F8;
            font-size: 9px;
            font-weight: 750;
            letter-spacing: .17em;
        }

        .mi-login-story-copy h1 {
            margin: 15px 0 14px;
            color: #F5F8FE;
            font-size: clamp(32px, 4vw, 48px);
            font-weight: 650;
            letter-spacing: -.045em;
            line-height: 1.08;
        }

        .mi-login-story-copy p {
            max-width: 350px;
            margin: 0;
            color: #A5B5CA;
            font-size: 13px;
            line-height: 1.7;
        }

        .mi-login-story-foot {
            display: inline-flex;
            align-items: center;
            gap: 9px;
            margin-top: auto;
            color: #A5B5CA;
            font-size: 12px;
        }

        .mi-login-lock {
            display: inline-flex;
            color: var(--mi-color-success);
        }

        .mi-login-orbit {
            position: absolute;
            width: 300px;
            height: 300px;
            border: 1px solid rgba(115, 169, 255, .08);
            border-radius: 50%;
            pointer-events: none;
        }

        .mi-login-orbit-one {
            top: 15%;
            right: -31%;
        }

        .mi-login-orbit-two {
            top: 25%;
            right: -42%;
            width: 390px;
            height: 390px;
        }

        .stApp:has(.mi-login-intro-once) .mi-login-story {
            animation: mi-login-rise 560ms cubic-bezier(.22,.61,.36,1) both;
        }

        .stApp:has(.mi-login-intro-once) .st-key-mi-login-card {
            animation: mi-login-rise 560ms 120ms
                cubic-bezier(.22,.61,.36,1) both;
        }

        @keyframes mi-login-rise {
            from { opacity: 0; transform: translateY(16px); }
            to { opacity: 1; transform: translateY(0); }
        }

        @media (prefers-reduced-motion: reduce) {
            .stApp:has(.mi-login-intro-once) .mi-login-story,
            .stApp:has(.mi-login-intro-once) .st-key-mi-login-card {
                animation: none;
            }
        }

        .st-key-mi-login-card {
            display: flex;
            min-height: 560px;
            flex-direction: column;
            justify-content: center;
            padding: clamp(12px, 2vw, 28px);
        }

        .mi-login-card-heading {
            margin-bottom: 24px;
        }

        .mi-login-card-kicker {
            margin-bottom: 9px;
            color: var(--mi-color-brand);
            font-size: 9px;
            font-weight: 750;
            letter-spacing: .16em;
        }

        .mi-login-card-title {
            margin: 0;
            color: var(--mi-color-text);
            font-size: clamp(25px, 3vw, 31px);
            font-weight: 650;
            letter-spacing: -.035em;
            line-height: 1.2;
        }

        .mi-login-card-subtitle {
            margin: 9px 0 0;
            color: var(--mi-color-text-muted);
            font-size: 12px;
            line-height: 1.6;
        }

        .st-key-mi-login-card [data-testid="stForm"] {
            padding: 0;
            border: 0;
            background: transparent;
        }

        .st-key-mi-login-card [data-testid="stTextInput"] {
            margin-bottom: 13px;
        }

        .st-key-mi-login-card [data-testid="stTextInput"] label {
            margin-bottom: 6px;
            color: #C4D0DF;
            font-size: 11px;
            font-weight: 600;
        }

        .st-key-mi-login-card [data-testid="stTextInput"] input {
            min-height: 46px;
            padding: 0 13px;
            border-color: #2B3B52;
            border-radius: 9px;
            background: #101A29;
            font-size: 13px;
        }

        .st-key-mi_login_submit [data-testid="stFormSubmitButton"] button {
            position: relative;
            overflow: hidden;
            width: 100%;
            min-height: 52px;
            margin-top: 9px;
            border: 1px solid rgba(132, 174, 225, .4);
            border-radius: 12px;
            background:
                linear-gradient(112deg, #234F89 0%, #2D65A7 48%,
                    #3B75B6 100%);
            color: #FFFFFF;
            font-size: 13px;
            font-weight: 720;
            letter-spacing: .025em;
            box-shadow:
                0 8px 20px rgba(24, 65, 115, .22),
                inset 0 1px 0 rgba(255, 255, 255, .14);
            transition:
                transform 160ms ease,
                border-color 160ms ease,
                box-shadow 160ms ease,
                filter 160ms ease;
        }

        .st-key-mi-login-card
        .st-key-mi_login_submit
        [data-testid="stFormSubmitButton"] button:not(:disabled):hover {
            border-color: rgba(157, 193, 235, .62);
            box-shadow:
                0 10px 24px rgba(24, 65, 115, .3),
                0 0 16px rgba(66, 119, 180, .18),
                inset 0 1px 0 rgba(255, 255, 255, .16);
            filter: brightness(1.035);
            transform: translateY(-1px);
        }

        .st-key-mi-login-card
        .st-key-mi_login_submit
        [data-testid="stFormSubmitButton"] button:not(:disabled):active {
            transform: translateY(0);
            filter: brightness(.98);
        }

        .st-key-mi_login_submit
        [data-testid="stFormSubmitButton"] button::before {
            position: absolute;
            top: -80%;
            left: -35%;
            width: 28%;
            height: 260%;
            background: linear-gradient(
                90deg,
                transparent,
                rgba(255, 255, 255, .24),
                transparent
            );
            content: "";
            transform: rotate(22deg);
            transition: left 520ms ease;
            pointer-events: none;
        }

        .st-key-mi_login_submit
        [data-testid="stFormSubmitButton"] button:not(:disabled):hover::before {
            left: 110%;
        }

        .st-key-mi_password_recovery_submit
        [data-testid="stFormSubmitButton"] button {
            min-height: 42px;
            margin-top: 3px;
            padding: 0 14px;
            border: 1px solid rgba(115, 169, 255, .22);
            border-radius: 9px;
            background: rgba(23, 38, 59, .48);
            color: #AFC2DA;
            font-size: 11px;
            font-weight: 600;
            transition:
                background-color 160ms ease,
                border-color 160ms ease,
                color 160ms ease;
        }

        .st-key-mi_password_recovery_submit
        [data-testid="stFormSubmitButton"] button:not(:disabled):hover {
            border-color: rgba(115, 156, 204, .4);
            background: rgba(32, 55, 83, .62);
            color: #D7E2F0;
        }

        .mi-login-notice {
            display: flex;
            flex-wrap: wrap;
            align-items: baseline;
            gap: 4px 8px;
            margin: 0 0 22px;
            padding: 10px 13px;
            border: 1px solid rgba(115, 169, 255, .15);
            border-radius: 10px;
            background: rgba(23, 38, 59, .62);
            color: #A9B9CE;
            font-size: 12px;
            line-height: 1.5;
        }

        .mi-login-notice-title {
            color: #D7E4F5;
            font-weight: 650;
        }

        .st-key-mi-login-card [data-testid="stAlert"] {
            margin-top: 16px;
            border-radius: 10px;
        }

        @media (max-width: 760px) {
            .stApp:has(.mi-login-layout) [data-testid="stMainBlockContainer"] {
                padding: 18px 16px;
            }

            .stApp:has(.mi-login-layout) [data-testid="stHorizontalBlock"] {
                flex-direction: column;
                gap: 8px;
            }

            .mi-login-story {
                min-height: 215px;
                gap: 20px;
                padding: 22px;
                border-radius: 18px;
            }

            .mi-login-story-copy h1 {
                margin: 12px 0 8px;
                font-size: 30px;
            }

            .mi-login-story-copy p {
                max-width: 420px;
                font-size: 11px;
            }

            .mi-login-story-foot {
                display: none;
            }

            .st-key-mi-login-card {
                min-height: auto;
                padding: 16px 8px 8px;
            }
        }

        .mi-icon {
            display: inline-block;
            flex: 0 0 auto;
            vertical-align: middle;
        }

        .mi-badge {
            display: inline-flex;
            min-height: 22px;
            align-items: center;
            gap: 6px;
            padding: 3px 8px;
            border: 1px solid transparent;
            border-radius: 999px;
            font-size: 11px;
            font-weight: 600;
            line-height: 1.2;
            white-space: nowrap;
        }

        .mi-badge-dot {
            width: 6px;
            height: 6px;
            flex: 0 0 6px;
            border-radius: 50%;
            background: currentColor;
        }

        .mi-badge-success,
        .mi-badge-positive {
            border-color: rgba(74, 222, 128, .22);
            background: rgba(74, 222, 128, .08);
            color: var(--mi-color-success);
        }

        .mi-badge-warning,
        .mi-badge-loading {
            border-color: rgba(246, 200, 95, .24);
            background: rgba(246, 200, 95, .08);
            color: var(--mi-color-warning);
        }

        .mi-badge-error,
        .mi-badge-negative {
            border-color: rgba(255, 128, 109, .24);
            background: rgba(255, 128, 109, .08);
            color: var(--mi-color-danger);
        }

        .mi-badge-info {
            border-color: rgba(100, 199, 230, .22);
            background: rgba(100, 199, 230, .08);
            color: var(--mi-color-info);
        }

        .mi-badge-empty,
        .mi-badge-neutral {
            border-color: rgba(143, 161, 184, .18);
            background: rgba(143, 161, 184, .06);
            color: var(--mi-color-text-muted);
        }

        .st-key-mi-page-content [data-testid="stSpinner"] {
            width: fit-content;
            max-width: min(360px, 100%);
            gap: 10px;
            padding: 11px 15px;
            border: 1px solid rgba(115, 169, 255, .14);
            border-radius: 12px;
            background:
                linear-gradient(
                    115deg,
                    rgba(22, 35, 53, .96),
                    rgba(17, 27, 42, .9)
                );
            box-shadow: 0 8px 24px rgba(0, 0, 0, .16);
            color: var(--mi-color-text-muted);
            font-size: 12px;
        }

        .st-key-mi-page-content [data-testid="stSpinner"] svg {
            color: #73A9FF;
        }

        .st-key-mi-sidebar-connection-status {
            display: flex;
            flex-direction: column;
            gap: 3px;
            padding: 8px 2px 7px;
        }

        .st-key-mi-sidebar-footer {
            flex: 0 0 auto;
            margin-top: auto;
            padding: 7px 0 4px;
            background: transparent;
            box-shadow: none;
        }

        [data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {
            display: flex;
            min-height: 100%;
            flex-direction: column;
        }

        [data-testid="stSidebar"] [data-testid="stSidebarUserContent"]
        > div {
            flex: 0 0 auto;
        }

        [data-testid="stSidebar"] .st-key-mi-sidebar-footer {
            margin-top: auto;
        }

        .st-key-mi-sidebar-status-conectado a::before,
        .st-key-mi-sidebar-status-sincronizando a::before,
        .st-key-mi-sidebar-status-atencao a::before,
        .st-key-mi-sidebar-status-erro a::before,
        .st-key-mi-sidebar-status-desconectado a::before,
        .st-key-mi-sidebar-status-em-breve a::before {
            width: 7px;
            height: 7px;
            flex: 0 0 7px;
            border-radius: 50%;
            background: currentColor;
            content: "";
        }

        .st-key-mi-sidebar-status-conectado a::before {
            color: var(--mi-color-success) !important;
        }

        .st-key-mi-sidebar-status-sincronizando a::before {
            color: var(--mi-color-info) !important;
            animation: mi-sidebar-status-pulse 1.5s ease-in-out infinite;
        }

        .st-key-mi-sidebar-status-atencao a::before {
            color: var(--mi-color-warning) !important;
        }

        .st-key-mi-sidebar-status-erro a::before,
        .st-key-mi-sidebar-status-desconectado a::before {
            color: var(--mi-color-danger) !important;
        }

        .st-key-mi-sidebar-status-em-breve a::before {
            color: #7F8A9A !important;
        }

        @keyframes mi-sidebar-status-pulse {
            50% { opacity: .48; }
        }

        [data-testid="stSidebar"] .st-key-mi-sidebar-status-conectado a,
        [data-testid="stSidebar"] .st-key-mi-sidebar-status-sincronizando a,
        [data-testid="stSidebar"] .st-key-mi-sidebar-status-atencao a,
        [data-testid="stSidebar"] .st-key-mi-sidebar-status-erro a,
        [data-testid="stSidebar"] .st-key-mi-sidebar-status-desconectado a,
        [data-testid="stSidebar"] .st-key-mi-sidebar-status-em-breve a {
            display: flex;
            min-height: 27px;
            align-items: center;
            gap: 8px;
            padding: 3px 7px;
            border: 1px solid transparent;
            border-radius: 7px;
            background: rgba(143, 161, 184, .025);
            color: #D3DCE8;
            font-size: 12px;
            font-weight: 600;
            text-decoration: none;
            transition:
                border-color 150ms ease,
                background-color 150ms ease,
                color 150ms ease;
        }

        [data-testid="stSidebar"] .st-key-mi-sidebar-status-em-breve a {
            background: transparent;
            color: #8D9AAF;
            opacity: .78;
        }

        [data-testid="stSidebar"] .st-key-mi-sidebar-connection-status a p {
            margin: 0;
            font-size: 12px;
            line-height: 1.3;
        }

        [data-testid="stSidebar"] .st-key-mi-sidebar-connection-status a strong {
            color: #DCE5F0;
            font-weight: 650;
        }

        [data-testid="stSidebar"] .st-key-mi-sidebar-connection-status a em {
            color: #91A0B4;
            font-size: 12px;
            font-style: normal;
            font-weight: 450;
        }

        [data-testid="stSidebar"] .st-key-mi-sidebar-status-conectado a,
        [data-testid="stSidebar"] .st-key-mi-sidebar-status-sincronizando a,
        [data-testid="stSidebar"] .st-key-mi-sidebar-status-atencao a,
        [data-testid="stSidebar"] .st-key-mi-sidebar-status-erro a,
        [data-testid="stSidebar"] .st-key-mi-sidebar-status-desconectado a,
        [data-testid="stSidebar"] .st-key-mi-sidebar-status-em-breve a {
            border-color: transparent;
            background-color: transparent;
            box-shadow: none;
        }

        [data-testid="stSidebar"] .st-key-mi-sidebar-status-conectado a:hover,
        [data-testid="stSidebar"] .st-key-mi-sidebar-status-sincronizando a:hover,
        [data-testid="stSidebar"] .st-key-mi-sidebar-status-atencao a:hover,
        [data-testid="stSidebar"] .st-key-mi-sidebar-status-erro a:hover,
        [data-testid="stSidebar"] .st-key-mi-sidebar-status-desconectado a:hover,
        [data-testid="stSidebar"] .st-key-mi-sidebar-status-em-breve a:hover {
            border-color: rgba(143, 161, 184, .1);
            background: rgba(143, 161, 184, .045);
            box-shadow: none;
        }

        .st-key-mi-sidebar-status-em-breve a::before {
            color: #7F8A9A !important;
        }

        .st-key-mi-sidebar-status-sincronizando a:focus-visible,
        .st-key-mi-sidebar-status-conectado a:focus-visible,
        .st-key-mi-sidebar-status-atencao a:focus-visible,
        .st-key-mi-sidebar-status-erro a:focus-visible,
        .st-key-mi-sidebar-status-desconectado a:focus-visible,
        .st-key-mi-sidebar-status-em-breve a:focus-visible {
            outline: 2px solid rgba(115, 169, 255, .58);
            outline-offset: 2px;
        }

        [data-testid="stSidebar"][aria-expanded="false"]
        .st-key-mi-sidebar-status-conectado a,
        [data-testid="stSidebar"][aria-expanded="false"]
        .st-key-mi-sidebar-status-sincronizando a,
        [data-testid="stSidebar"][aria-expanded="false"]
        .st-key-mi-sidebar-status-atencao a,
        [data-testid="stSidebar"][aria-expanded="false"]
        .st-key-mi-sidebar-status-erro a,
        [data-testid="stSidebar"][aria-expanded="false"]
        .st-key-mi-sidebar-status-desconectado a,
        [data-testid="stSidebar"][aria-expanded="false"]
        .st-key-mi-sidebar-status-em-breve a {
            width: 32px;
            min-height: 32px;
            justify-content: center;
            overflow: hidden;
            padding: 0;
            border-color: transparent;
            border-radius: 50%;
            background: transparent;
            color: transparent;
            font-size: 0;
            box-shadow: none;
        }

        [data-testid="stSidebar"][aria-expanded="false"]
        .st-key-mi-sidebar-status-conectado,
        [data-testid="stSidebar"][aria-expanded="false"]
        .st-key-mi-sidebar-status-sincronizando,
        [data-testid="stSidebar"][aria-expanded="false"]
        .st-key-mi-sidebar-status-atencao,
        [data-testid="stSidebar"][aria-expanded="false"]
        .st-key-mi-sidebar-status-erro,
        [data-testid="stSidebar"][aria-expanded="false"]
        .st-key-mi-sidebar-status-desconectado,
        [data-testid="stSidebar"][aria-expanded="false"]
        .st-key-mi-sidebar-status-em-breve {
            width: 32px;
            flex: 0 0 32px;
        }

        [data-testid="stSidebar"][aria-expanded="false"]
        .st-key-mi-sidebar-connection-status a p {
            display: none;
        }

        [data-testid="stSidebar"][aria-expanded="false"]
        .st-key-mi-sidebar-status-conectado a::before,
        [data-testid="stSidebar"][aria-expanded="false"]
        .st-key-mi-sidebar-status-sincronizando a::before,
        [data-testid="stSidebar"][aria-expanded="false"]
        .st-key-mi-sidebar-status-atencao a::before,
        [data-testid="stSidebar"][aria-expanded="false"]
        .st-key-mi-sidebar-status-erro a::before,
        [data-testid="stSidebar"][aria-expanded="false"]
        .st-key-mi-sidebar-status-desconectado a::before,
        [data-testid="stSidebar"][aria-expanded="false"]
        .st-key-mi-sidebar-status-em-breve a::before {
            width: 9px;
            height: 9px;
            flex-basis: 9px;
        }

        [data-testid="stSidebar"][aria-expanded="false"]
        .st-key-mi-sidebar-connection-status {
            flex-direction: row;
            justify-content: center;
            gap: 6px;
            padding: 6px 0 3px;
            border-top: 0;
        }

        @media (prefers-reduced-motion: reduce) {
            .st-key-mi-sidebar-status-sincronizando [data-testid="stIconMaterial"] {
                animation: none;
            }
            .st-key-mi-sidebar-status-sincronizando a::before {
                animation: none;
            }
        }

        .mi-sidebar-user {
            display: flex;
            min-width: 0;
            align-items: center;
            gap: 10px;
            padding: 9px 2px;
        }

        .mi-sidebar-avatar {
            display: grid;
            width: 34px;
            height: 34px;
            flex: 0 0 34px;
            place-items: center;
            border: 1px solid rgba(115, 169, 255, .3);
            border-radius: 50%;
            background: linear-gradient(
                145deg,
                rgba(115, 169, 255, .2),
                rgba(115, 169, 255, .07)
            );
            color: #C8DEFF;
            font-size: 11px;
            font-weight: 700;
        }

        .mi-sidebar-user-copy {
            display: flex;
            min-width: 0;
            flex-direction: column;
            gap: 3px;
        }

        .mi-sidebar-user-name {
            overflow: hidden;
            color: var(--mi-color-text);
            font-size: 12px;
            font-weight: 650;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

        .mi-sidebar-account-active {
            display: inline-flex;
            align-items: center;
            gap: 5px;
            color: var(--mi-color-text-muted);
            font-size: 10px;
        }

        .mi-sidebar-account-active span {
            width: 6px;
            height: 6px;
            border-radius: 50%;
            background: var(--mi-color-success);
            box-shadow: 0 0 7px rgba(74, 222, 128, .35);
        }

        .st-key-mi_logout_sidebar [data-testid="stBaseButton-tertiary"] {
            width: auto;
            min-width: 56px;
            min-height: 30px;
            padding: 0 7px;
            border: 1px solid transparent;
            border-radius: 8px;
            background: transparent;
            color: var(--mi-color-text-muted);
            box-shadow: none;
        }

        .st-key-mi_logout_sidebar {
            margin-top: 5px;
        }

        .st-key-mi_logout_sidebar
        [data-testid="stBaseButton-tertiary"]:hover {
            border-color: rgba(255, 128, 109, .18);
            background: rgba(255, 128, 109, .06);
            color: var(--mi-color-danger);
            box-shadow: none;
            transform: none;
        }

        div[data-testid="stVerticalBlock"]:has(
            > [data-testid="stElementContainer"] .mi-chart-heading
        ),

        div[data-testid="stVerticalBlock"]:has(
            > [data-testid="stElementContainer"] .mi-dashboard-panel
        ) {

            background: rgba(18, 28, 43, .14);

            border-color: rgba(115, 169, 255, .12);

            border-radius: var(--mi-radius-card);

            box-shadow: 0 3px 12px rgba(0,0,0,0.08);

            transition:
                transform 260ms cubic-bezier(.2,.7,.2,1),
                border-color 260ms ease,
                box-shadow 260ms ease,
                background 260ms ease;

        }

        div[data-testid="stVerticalBlock"]:has(
            > [data-testid="stElementContainer"] .mi-chart-heading
        ):hover,

        div[data-testid="stVerticalBlock"]:has(
            > [data-testid="stElementContainer"] .mi-dashboard-panel
        ):hover {

            border-color: rgba(115,169,255,0.24);

            box-shadow:
                0 7px 18px rgba(0,0,0,0.14),
                0 0 12px rgba(115,169,255,0.06);

        }

        .mi-chart-heading {

            min-height: 42px;

            padding: 1px 1px 8px;

            margin-bottom: 5px;

        }

        .mi-section-heading {
            margin: 18px 0 12px;
            scroll-margin-top: 120px;
        }

        .main .mi-section-heading-title {
            margin: 0;
            color: #E8EEF7;
            font-size: 18px !important;
            font-weight: 650 !important;
            line-height: 1.35 !important;
            letter-spacing: -.015em;
        }

        .mi-section-heading-subtitle {
            margin: 3px 0 0;
            color: #8FA1B8;
            font-size: 12px;
            line-height: 1.45;
        }

        .mi-filter-chip-row {
            display: flex;
            min-height: 36px;
            align-items: center;
            flex-wrap: wrap;
            gap: 7px;
        }

        .mi-order-open-instruction {
            display: flex;
            min-height: 38px;
            align-items: center;
            gap: 9px;
            color: #A8B6C9;
            font-size: 12px;
            line-height: 1.4;
        }

        .mi-order-open-instruction .mi-icon {
            flex: 0 0 auto;
            color: var(--mi-color-brand);
        }

        .mi-empty-state {
            display: flex;
            min-height: 180px;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            gap: 8px;
            margin: 8px 0;
            padding: 24px;
            border: 1px dashed rgba(143, 161, 184, .2);
            border-radius: var(--mi-radius-card);
            background: rgba(18, 28, 43, .35);
            color: #8FA1B8;
            font-size: 12px;
            text-align: center;
        }

        .mi-empty-state strong {
            color: #E8EEF7;
            font-size: 14px;
        }

        .mi-empty-state-icon {
            display: inline-flex;
            color: var(--mi-color-brand);
        }

        .mi-connection-manager-row {
            display: flex;
            min-height: 32px;
            align-items: center;
            gap: 10px;
            color: #E8EEF7;
            font-size: 13px;
        }

        .mi-connection-manager-note {
            margin: 3px 0 10px 2px;
            color: #A8B6C9;
            font-size: 12px;
            line-height: 1.45;
        }

        .main [data-testid="stExpander"] > details > summary {
            border: 1px solid transparent;
            border-radius: 10px;
            box-shadow: none;
        }

        .main [data-testid="stExpander"] > details > summary:focus {
            border-color: transparent;
            box-shadow: none;
            outline: none;
        }

        .main [data-testid="stExpander"] > details > summary:focus-visible {
            border-color: rgba(115, 169, 255, .35);
            box-shadow: 0 0 0 2px rgba(115, 169, 255, .12);
            outline: 2px solid transparent;
            outline-offset: 2px;
        }

        .mi-marketplace-table-entering {
            display: none;
        }

        .mi-product-table-entering {
            display: none;
        }

        div[data-testid="stElementContainer"]:has(.mi-product-table-entering)
        + div[data-testid="stElementContainer"]:has([data-testid="stDataFrame"]) {
            animation: mi-overview-entry 420ms
                cubic-bezier(.22,.61,.36,1) backwards;
            animation-delay: 70ms;
        }

        div[data-testid="stVerticalBlockBorderWrapper"]:has(
            .mi-marketplace-table-entering
        ) {
            animation: mi-overview-entry 420ms
                cubic-bezier(.22,.61,.36,1) backwards;
            animation-delay: var(--mi-entry-delay, 0ms);
        }

        .mi-marketplace-invite {
            display: flex;
            align-items: center;
            gap: 8px;
            margin: 10px 0 2px;
            color: #A8B6C9;
            font-size: 12px;
            line-height: 1.45;
        }

        .mi-marketplace-invite .mi-icon {
            color: var(--mi-color-brand);
        }

        @media (prefers-reduced-motion: reduce) {
            div[data-testid="stElementContainer"]:has(.mi-product-table-entering)
            + div[data-testid="stElementContainer"]:has([data-testid="stDataFrame"]) {
                animation: mi-overview-fade 180ms ease-out both;
                animation-delay: 0ms;
            }

            div[data-testid="stVerticalBlockBorderWrapper"]:has(
                .mi-marketplace-table-entering
            ) {
                animation: mi-overview-fade 180ms ease-out both;
                animation-delay: 0ms;
            }
        }

        .mi-connection-danger-separator {
            height: 1px;
            margin: 12px 0 8px;
            background: rgba(143, 161, 184, .12);
        }

        .st-key-mi_ml_remove_connection button {
            min-height: 32px;
            padding: 4px 8px;
            border: 1px solid transparent;
            background: transparent;
            color: #A8B6C9;
            font-size: 12px;
        }

        .st-key-mi_ml_remove_connection button:hover {
            border-color: rgba(255, 128, 109, .2);
            background: rgba(255, 128, 109, .07);
            color: #FF806D;
        }

        .mi-pagination-label {
            display: flex;
            min-height: 36px;
            align-items: center;
            color: #A8B6C9;
            font-size: 12px;
        }

        .mi-order-detail-header {
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 16px;
            padding: 2px 0 14px;
            border-bottom: 1px solid rgba(143, 161, 184, .14);
        }

        @keyframes mi-order-detail-enter {
            from { opacity: 0; transform: translateY(7px); }
            to { opacity: 1; transform: translateY(0); }
        }

        @keyframes mi-order-detail-fade {
            from { opacity: 0; }
            to { opacity: 1; }
        }

        .mi-order-detail-enter {
            animation: mi-order-detail-enter 220ms
                cubic-bezier(.22,.61,.36,1) both;
            animation-delay: var(--mi-detail-delay, 0ms);
        }

        @media (prefers-reduced-motion: reduce) {
            .mi-order-detail-enter {
                animation: mi-order-detail-fade 140ms ease-out both;
                animation-delay: 0ms;
            }
        }

        .mi-order-detail-id {
            margin: 0;
            color: #F1F5F9;
            font-size: 21px;
            font-weight: 700;
            line-height: 1.25;
        }

        .mi-order-detail-meta {
            margin-top: 6px;
            color: #A8B6C9;
            font-size: 12px;
            line-height: 1.5;
        }

        .mi-order-detail-section {
            margin-top: 14px;
            padding: 14px;
            border: 1px solid rgba(143, 161, 184, .12);
            border-radius: var(--mi-radius-card);
            background: rgba(18, 28, 43, .72);
        }

        .mi-order-detail-section-title {
            margin: 0 0 9px;
            color: #CBD5E1;
            font-size: 12px;
            font-weight: 650;
            letter-spacing: .025em;
        }

        .mi-order-detail-row {
            display: flex;
            justify-content: space-between;
            gap: 16px;
            padding: 5px 0;
            color: #A8B6C9;
            font-size: 12px;
            line-height: 1.5;
        }

        .mi-order-detail-row strong {
            color: #E8EEF7;
            font-size: 13px;
            font-variant-numeric: tabular-nums;
            text-align: right;
        }

        .mi-order-detail-total {
            margin-top: 4px;
            padding-top: 9px;
            border-top: 1px solid rgba(143, 161, 184, .16);
            color: #E8EEF7;
        }

        .mi-order-detail-result-positive { color: #4ADE80 !important; }
        .mi-order-detail-result-negative { color: #FF806D !important; }
        .mi-order-detail-cancelled { border-color: rgba(246, 200, 95, .22); }

        .mi-chart-heading.mi-chart-minimal {
            min-height: 42px;
            padding: 0 2px 7px;
            border: 0;
            margin: 0 0 4px;
        }

        div[data-testid="stVerticalBlockBorderWrapper"]:has(.mi-chart-heading) {
            overflow: visible;
            border: 1px solid rgba(115, 169, 255, .12);
            border-radius: var(--mi-radius-card);
            background: rgba(18, 28, 43, .3);
            box-shadow: 0 4px 14px rgba(0, 0, 0, .09);
            transition:
                border-color 180ms ease,
                box-shadow 180ms ease,
                background-color 180ms ease;
        }

        div[data-testid="stVerticalBlockBorderWrapper"]:has(.mi-chart-heading):hover {
            border-color: rgba(115, 169, 255, .24);
            background: rgba(18, 28, 43, .42);
            box-shadow: 0 8px 20px rgba(0, 0, 0, .16);
        }

        div[data-testid="stVerticalBlockBorderWrapper"]:has(.mi-chart-minimal),
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.mi-chart-minimal)
        [data-testid="stPlotlyChart"] {
            overflow: visible !important;
        }

        div[data-testid="stVerticalBlock"]:has(.mi-chart-minimal)
        .modebar-container {
            opacity: 0;
            transition: opacity 140ms ease;
        }

        div[data-testid="stVerticalBlock"]:has(.mi-chart-minimal):hover
        .modebar-container,
        div[data-testid="stVerticalBlock"]:has(.mi-chart-minimal)
        .modebar-container:hover {
            opacity: 1;
        }

        div[data-testid="stVerticalBlock"]:has(.mi-chart-minimal)
        .modebar-btn {
            border-radius: 5px;
            background: rgba(15, 23, 42, .92);
            color: #CAD7E8 !important;
        }

        div[data-testid="stVerticalBlock"]:has(.mi-chart-minimal)
        .modebar-btn:hover {
            background: #1E293B !important;
            color: var(--mi-color-brand) !important;
        }

        .mi-comparison-banner {
            display: flex;
            min-height: 34px;
            align-items: center;
            gap: 9px;
            padding: 7px 11px;
            border: 1px solid rgba(100, 199, 230, .16);
            border-radius: 9px;
            margin: 2px 0 10px;
            background: rgba(100, 199, 230, .045);
            color: #A7B8CA;
            font-size: 12px;
            line-height: 1.35;
        }

        .mi-comparison-banner-partial {
            border-color: rgba(246, 200, 95, .2);
            background: rgba(246, 200, 95, .055);
        }

        .mi-comparison-banner-partial .mi-comparison-banner-icon {
            border-color: rgba(246, 200, 95, .42);
            color: var(--mi-color-warning);
        }

        .mi-comparison-banner-icon {
            display: inline-grid;
            width: 15px;
            height: 15px;
            flex: 0 0 15px;
            place-items: center;
            border: 1px solid rgba(100, 199, 230, .42);
            border-radius: 50%;
            color: #78CFE8;
            font-size: 9px;
            font-weight: 700;
        }

        .mi-channel-single {
            display: flex;
            min-height: 390px;
            flex-direction: column;
            justify-content: center;
            padding: 14px 16px;
            border: 1px solid rgba(115, 169, 255, .12);
            border-radius: var(--mi-radius-card);
            background:
                linear-gradient(
                    145deg,
                    rgba(115, 169, 255, .045),
                    transparent 58%
                );
        }

        .mi-channel-comparison-card {
            min-height: 270px;
            justify-content: flex-start;
            padding: 15px 16px;
        }

        .mi-channel-comparison-card .mi-channel-single-heading {
            margin-bottom: 13px;
        }

        .mi-channel-comparison-card .mi-channel-row {
            opacity: 1;
        }

        .mi-channel-row {
            margin-top: 10px;
        }

        .mi-channel-row:first-child {
            margin-top: 0;
        }

        .mi-channel-row-heading {
            display: flex;
            min-height: 22px;
            align-items: center;
            justify-content: space-between;
            gap: 8px;
        }

        .mi-channel-row-name {
            display: inline-flex;
            align-items: center;
            gap: 7px;
            color: #DCE5F0;
            font-size: 12px;
            font-weight: 600;
        }

        .mi-channel-row-swatch {
            width: 8px;
            height: 8px;
            flex: 0 0 8px;
            border-radius: 50%;
        }

        .mi-channel-row-leader {
            padding: 8px 9px 9px;
            border: 1px solid rgba(115, 169, 255, .12);
            border-radius: 9px;
            background: rgba(115, 169, 255, .035);
        }

        .mi-channel-leader-badge,
        .mi-channel-coming-badge {
            color: #A8B6C9;
            font-size: 12px;
            line-height: 1.2;
        }

        .mi-channel-single-value,
        .mi-channel-single-share {
            font-variant-numeric: tabular-nums;
        }

        .mi-channel-row-value-row {
            display: flex;
            align-items: baseline;
            justify-content: space-between;
            gap: 8px;
            margin-top: 3px;
        }

        .mi-channel-row-value-row .mi-channel-single-value {
            font-size: 17px;
        }

        .mi-channel-single-heading {
            margin-bottom: 20px;
        }

        .mi-channel-single-title {
            color: #F1F5F9;
            font-size: 13px;
            font-weight: 650;
        }

        .mi-channel-single-subtitle {
            margin-top: 3px;
            color: #8292A8;
            font-size: 12px;
        }

        .mi-channel-single-label {
            margin-bottom: 5px;
            color: #8FA1B8;
            font-size: 12px;
        }

        .mi-channel-single-name {
            overflow-wrap: anywhere;
            color: #DDEBFC;
            font-size: 16px;
            font-weight: 650;
        }

        .mi-channel-single-value-row {
            display: flex;
            align-items: baseline;
            justify-content: space-between;
            gap: 8px;
            margin-top: 15px;
        }

        .mi-channel-single-value {
            color: #F1F5F9;
            font-size: 20px;
            font-weight: 700;
            letter-spacing: -.025em;
            white-space: nowrap;
        }

        .mi-channel-single-share {
            color: #A8B8CC;
            font-size: 12px;
            white-space: nowrap;
        }

        .mi-channel-single-track {
            height: 7px;
            overflow: hidden;
            border-radius: 99px;
            margin-top: 10px;
            background: rgba(143, 161, 184, .14);
        }

        .mi-channel-single-progress {
            height: 100%;
            border-radius: inherit;
        }

        .mi-operation-summary {
            padding: 13px 15px 14px;
            margin: 5px 0 12px;
            border: 1px solid var(--mi-color-border);
            border-radius: 10px;
            background:
                linear-gradient(
                    110deg,
                    rgba(115, 169, 255, .07),
                    transparent 45%
                ),
                var(--mi-color-surface);
        }

        .mi-operation-summary-title {
            margin-bottom: 10px;
            color: var(--mi-color-text-muted);
            font-size: 9px;
            font-weight: 750;
            letter-spacing: .11em;
            text-transform: uppercase;
        }

        .mi-operation-summary-list {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(165px, 1fr));
            gap: 7px;
        }

        .mi-summary-chip {
            display: flex;
            min-height: 39px;
            align-items: center;
            gap: 9px;
            padding: 7px 9px;
            border: 1px solid rgba(143, 161, 184, .12);
            border-radius: 7px;
            background: rgba(15, 23, 42, .45);
            color: #C6D2E0;
            font-size: 10px;
            line-height: 1.35;
        }

        .mi-summary-chip-icon {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            color: #9FB0C4;
        }

        .mi-summary-chip-copy {
            display: flex;
            min-width: 0;
            flex-direction: column;
            gap: 2px;
        }

        .mi-summary-chip-value {
            color: #E4EDF8;
            font-size: 11px;
            font-weight: 700;
        }

        .mi-summary-chip-label {
            color: var(--mi-color-text-muted);
            font-size: 9px;
        }

        .mi-summary-chip.positive .mi-summary-chip-value,
        .mi-summary-chip.positive .mi-summary-chip-icon {
            color: var(--mi-color-success);
        }

        .mi-summary-chip.negative .mi-summary-chip-value,
        .mi-summary-chip.negative .mi-summary-chip-icon {
            color: var(--mi-color-danger);
        }

        .mi-summary-chip.neutral .mi-summary-chip-value,
        .mi-summary-chip.neutral .mi-summary-chip-icon {
            color: var(--mi-color-info);
        }

        .mi-chart-title {

            color: #F1F5F9;

            font-family:
                Inter,
                "Segoe UI Variable",
                "Segoe UI",
                Arial,
                sans-serif;

            font-size: 13px;

            font-weight: 650;

            letter-spacing: -.01em;

            line-height: 19px;

        }

        .mi-chart-title .mi-icon {
            margin-right: 6px;
            color: var(--mi-color-brand);
            vertical-align: -3px;
        }

        .mi-chart-subtitle {

            color: #8292A8;

            font-size: 12px;
            line-height: 16px;

        }

        .mi-stock-list {

            margin-top: 7px;

        }

        .mi-stock-row {

            display: flex;

            align-items: center;

            justify-content: space-between;

            gap: 12px;

            padding: 9px 2px;

            border-bottom: 1px solid rgba(51, 65, 85, .62);

        }

        .mi-stock-row:last-child {

            border-bottom: 0;

        }

        .mi-stock-product {

            display: flex;

            flex-direction: column;

            min-width: 0;

            gap: 2px;

        }

        .mi-stock-name {

            color: #E2E8F0;

            font-size: 13px;

            font-weight: 600;

        }

        .mi-stock-sku {

            color: #8292A8;

            font-size: 10px;

        }

        .mi-stock-facts {

            display: flex;

            align-items: center;

            justify-content: flex-end;

            flex-wrap: wrap;

            gap: 8px;

            color: #A8B6C9;

            font-size: 11px;

            white-space: nowrap;

        }

        .mi-stock-detail b {

            color: #E2E8F0;

            font-weight: 650;

        }

        .mi-stock-value {

            color: #F5B700;

            font-weight: 700;

        }

        .mi-stock-status {

            border-radius: 4px;

            padding: 3px 6px;

            font-size: 10px;

            font-weight: 650;

        }

        .mi-stock-status-critical {

            background: rgba(244, 81, 58, .13);

            color: #FF806D;

        }

        .mi-stock-status-warning {

            background: rgba(245, 183, 0, .13);

            color: #F5B700;

        }

        .mi-stock-empty {

            padding: 17px 2px 10px;

            color: #8292A8;

            font-size: 12px;

        }

        .mi-stock-alert-header,
        .mi-stock-alert-row,
        .mi-stock-idle-header,
        .mi-stock-idle-row {
            display: grid;
            grid-template-columns: minmax(170px, 1.6fr) repeat(4, minmax(90px, 1fr));
            align-items: center;
            gap: 10px;
        }

        .mi-stock-alert-header,
        .mi-stock-idle-header {
            padding: 8px 2px;
            border-bottom: 1px solid rgba(143, 161, 184, .16);
            color: #A8B6C9;
            font-size: 12px;
            font-weight: 650;
        }

        .mi-stock-alert-row,
        .mi-stock-idle-row {
            min-height: 44px;
            padding: 6px 2px;
            border-bottom: 1px solid rgba(51, 65, 85, .45);
            color: #C5D0DE;
            font-size: 12px;
            font-variant-numeric: tabular-nums;
        }

        .mi-stock-alert-product,
        .mi-stock-idle-product {
            display: flex;
            min-width: 0;
            flex-direction: column;
            gap: 2px;
        }

        .mi-stock-alert-product strong,
        .mi-stock-idle-product strong {
            color: #E2E8F0;
            font-size: 12px;
            overflow-wrap: anywhere;
        }

        .mi-stock-alert-product span,
        .mi-stock-idle-product span {
            color: #A8B6C9;
            font-size: 12px;
        }

        .mi-stock-alert-state {
            width: fit-content;
            font-size: 12px;
            font-weight: 650;
        }

        .mi-stock-alert-danger {
            color: #FF806D;
        }

        .mi-stock-alert-warning {
            color: #F6C85F;
        }

        .mi-stock-idle-row > strong {
            color: #73A9FF;
            font-size: 12px;
        }

        .mi-stock-empty-state {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 12px 2px;
            color: #A8B6C9;
            font-size: 12px;
        }

        .mi-stock-empty-state .mi-icon {
            flex: 0 0 auto;
            color: #4ADE80;
        }

        @media (max-width: 760px) {
            .mi-stock-alert-header,
            .mi-stock-alert-row,
            .mi-stock-idle-header,
            .mi-stock-idle-row {
                grid-template-columns: minmax(120px, 1.3fr) repeat(2, minmax(75px, 1fr));
            }
            .mi-stock-alert-header span:nth-child(n + 4),
            .mi-stock-alert-row > span:nth-of-type(n + 3),
            .mi-stock-idle-header span:nth-child(n + 4),
            .mi-stock-idle-row > span:nth-of-type(n + 3) {
                display: none;
            }
        }

        [data-testid="stPlotlyChart"] {

            overflow: hidden;

            border: 0;

            background: transparent;

        }

        [data-testid="stMainBlockContainer"] {
            width: 100%;
            max-width: none;
            padding: .5rem clamp(1rem, 2vw, 2rem) 1rem;
            gap: 0.75rem;
        }

        [data-testid="stVerticalBlock"] {

            gap: 0.8rem;

        }


        /* =====================================================
           TEXTOS
           ===================================================== */

        h1,
        h2,
        h3,
        p {

            color:
                white;

        }

        .main,
        section[data-testid="stSidebar"] {
            font-family:
                Inter,
                "Segoe UI Variable",
                "Segoe UI",
                Arial,
                sans-serif;
        }

        .main h1,
        .main h2,
        .main h3 {
            color: #F1F5F9;
            font-family:
                Inter,
                "Segoe UI Variable",
                "Segoe UI",
                Arial,
                sans-serif !important;
            letter-spacing: -.02em;
        }

        .main h2 {
            font-size: 22px !important;
            font-weight: 650 !important;
            line-height: 1.25 !important;
        }

        .main h3 {
            font-size: 18px !important;
            font-weight: 650 !important;
            line-height: 1.3 !important;
        }

        .mi-page-heading {
            position: relative;
            display: flex;
            align-items: center;
            gap: 14px;
            padding: 8px 0 17px;
            margin-bottom: 4px;
            border-bottom: 1px solid #263449;
        }

        .mi-page-heading::after {
            position: absolute;
            bottom: -1px;
            left: 0;
            width: 54px;
            height: 2px;
            border-radius: 2px;
            background: linear-gradient(90deg, #60A5FA, #3B82F6);
            content: "";
        }

        .mi-page-heading-icon {
            display: inline-flex;
            width: 31px;
            height: 31px;
            flex: 0 0 31px;
            align-items: center;
            justify-content: center;
            border: 1px solid rgba(115, 169, 255, .2);
            border-radius: 9px;
            background: rgba(115, 169, 255, .08);
            color: var(--mi-color-brand);
            font-size: 17px;
        }

        .mi-page-heading-copy {
            min-width: 0;
        }

        .mi-page-eyebrow {
            margin-bottom: 4px;
            color: #8FA1B8;
            font-size: 12px;
            font-weight: 700;
            letter-spacing: .1em;
            line-height: 1.3;
        }

        .mi-page-title {
            margin: 0;
            color: #F1F5F9;
            font-family:
                Inter,
                "Segoe UI Variable",
                "Segoe UI",
                Arial,
                sans-serif !important;
            font-size: clamp(22px, 1.65vw, 27px) !important;
            font-weight: 650 !important;
            letter-spacing: -.025em;
            line-height: 1.18 !important;
        }

        .mi-page-subtitle {
            margin: 6px 0 0;
            color: #8FA1B8;
            font-family:
                Inter,
                "Segoe UI Variable",
                "Segoe UI",
                Arial,
                sans-serif !important;
            font-size: 12px !important;
            line-height: 1.45 !important;
        }

        .mi-page-context {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            margin-top: 9px;
            padding: 4px 8px;
            border: 1px solid rgba(115, 169, 255, .17);
            border-radius: 6px;
            background: rgba(115, 169, 255, .06);
            color: #BBD5F8;
            font-size: 12px;
            font-weight: 600;
            letter-spacing: .015em;
        }

        .mi-page-context::before {
            width: 6px;
            height: 6px;
            border-radius: 50%;
            background: var(--mi-color-brand);
            content: "";
        }

        div[data-testid="stLayoutWrapper"]:has(.mi-global-filters-anchor) {
            position: sticky;
            top: 0;
            z-index: 1000;
            padding: 6px 8px 10px;
            border-bottom: 1px solid #263449;
            background: #0F172A;
            box-shadow: 0 6px 16px rgba(0, 0, 0, .2);
            backdrop-filter: blur(10px);
        }

        .mi-pie-summary {
            display: flex;
            flex-direction: column;
            gap: 7px;
            padding: 0 12px 6px;
        }

        .mi-pie-summary-row {
            display: flex;
            min-width: 0;
            align-items: center;
            justify-content: space-between;
            gap: 10px;
            color: #D7E0EE;
            font-size: 12px;
            line-height: 1.4;
        }

        .mi-pie-summary-label {
            display: flex;
            min-width: max-content;
            align-items: center;
            gap: 7px;
            font-size: 12px;
            white-space: nowrap;
        }

        .mi-pie-summary-swatch {
            width: 8px;
            height: 8px;
            flex: 0 0 8px;
            border-radius: 2px;
        }

        .mi-pie-summary-amount {
            color: #F1F5F9;
            font-size: 12px;
            font-weight: 650;
            white-space: nowrap;
        }

        .mi-pie-summary-share {
            margin-left: 6px;
            color: #8FA1B8;
            font-size: 12px;
            font-weight: 400;
            white-space: nowrap;
        }

        div[data-testid="stLayoutWrapper"]:has(
            .mi-global-filters-anchor
        ) label {
            height: 15px !important;
            min-height: 15px !important;
            margin: 0;
            padding: 0;
            color: #8292A8;
            font-size: 12px !important;
            font-weight: 700;
            letter-spacing: .025em;
            line-height: 14px !important;
            text-transform: uppercase;
            cursor: pointer;
        }

        div[data-testid="stLayoutWrapper"]:has(
            .mi-global-filters-anchor
        ) label p {
            height: 14px;
            margin: 0;
            font-size: 12px !important;
            line-height: 14px !important;
        }

        div[data-testid="stLayoutWrapper"]:has(
            .mi-global-filters-anchor
        ) [data-testid="stDateInput"],
        div[data-testid="stLayoutWrapper"]:has(
            .mi-global-filters-anchor
        ) [data-testid="stSelectbox"] {
            padding: 5px 7px;
            border: 1px solid #263449;
            border-radius: 6px;
            background: linear-gradient(145deg, #151F2E, #121C2B);
            transition:
                border-color 160ms ease,
                background-color 160ms ease,
                box-shadow 160ms ease;
        }

        div[data-testid="stLayoutWrapper"]:has(
            .mi-global-filters-anchor
        ) [data-testid="stDateInput"]:hover,
        div[data-testid="stLayoutWrapper"]:has(
            .mi-global-filters-anchor
        ) [data-testid="stSelectbox"]:hover {
            border-color: #3B82F6;
            box-shadow: 0 0 0 1px rgba(59, 130, 246, .12);
        }

        div[data-testid="stLayoutWrapper"]:has(
            .mi-global-filters-anchor
        ) [data-testid="stVerticalBlock"] {
            gap: .12rem;
        }

        div[data-testid="stLayoutWrapper"]:has(
            .mi-global-filters-anchor
        ) [data-testid="stDateInputField"] {
            height: 30px !important;
            min-height: 30px !important;
            border: 1px solid #2B3B52;
            border-radius: 4px;
            background: #0F172A;
            cursor: pointer !important;
        }

        div[data-testid="stLayoutWrapper"]:has(
            .mi-global-filters-anchor
        ) [data-testid="stDateInputField"] [role="spinbutton"] {
            cursor: pointer !important;
        }

        div[data-testid="stLayoutWrapper"]:has(
            .mi-global-filters-anchor
        ) [data-testid="stSelectbox"] [role="group"] {
            height: 30px !important;
            min-height: 30px !important;
            border-color: #2B3B52;
            border-radius: 4px !important;
            background: #0F172A;
            cursor: pointer !important;
        }

        div[data-testid="stLayoutWrapper"]:has(
            .mi-global-filters-anchor
        ) [data-baseweb="select"] [role="combobox"] {
            height: 28px !important;
            min-height: 28px !important;
            padding: 0 8px;
            color: #E2E8F0;
            font-size: 12px !important;
            cursor: pointer !important;
        }

        div[data-testid="stLayoutWrapper"]:has(
            .mi-global-filters-anchor
        ) [data-testid="stSelectbox"] [role="combobox"] {
            height: 28px !important;
            min-height: 28px !important;
            padding: 0 8px;
            color: #E2E8F0;
            font-size: 12px !important;
            cursor: pointer !important;
        }

        div[data-testid="stLayoutWrapper"]:has(
            .mi-global-filters-anchor
        ) [data-testid="stSelectbox"] button {
            cursor: pointer !important;
        }

        div[data-testid="stLayoutWrapper"]:has(
            .mi-global-filters-anchor
        ) [data-testid="stDateInput"] input {
            height: 28px !important;
            min-height: 28px !important;
            padding: 4px 8px;
            border: 0;
            border-radius: 4px;
            background: transparent;
            color: #E2E8F0;
            font-size: 12px;
            cursor: pointer !important;
        }

        .stVerticalBlock:has(
            > [data-testid="stElementContainer"] .mi-table-filters-anchor
        ) label {
            height: 15px !important;
            min-height: 15px !important;
            margin: 0;
            padding: 0;
            color: #8292A8;
            font-size: 12px !important;
            font-weight: 700;
            letter-spacing: .025em;
            line-height: 14px !important;
            text-transform: uppercase;
            cursor: pointer;
        }

        .stVerticalBlock:has(
            > [data-testid="stElementContainer"] .mi-table-filters-anchor
        ) label p {
            height: 14px;
            margin: 0;
            font-size: 12px !important;
            line-height: 14px !important;
        }

        .stVerticalBlock:has(
            > [data-testid="stElementContainer"] .mi-table-filters-anchor
        ) [data-testid="stTextInput"],
        .stVerticalBlock:has(
            > [data-testid="stElementContainer"] .mi-table-filters-anchor
        ) [data-testid="stSelectbox"] {
            padding: 5px 7px;
            border: 1px solid #263449;
            border-radius: 6px;
            background: linear-gradient(145deg, #151F2E, #121C2B);
            min-height: 38px;
            transition:
                border-color 160ms ease,
                background-color 160ms ease,
                box-shadow 160ms ease;
        }

        .stVerticalBlock:has(
            > [data-testid="stElementContainer"] .mi-table-filters-anchor
        ) [data-testid="stTextInput"]:hover,
        .stVerticalBlock:has(
            > [data-testid="stElementContainer"] .mi-table-filters-anchor
        ) [data-testid="stSelectbox"]:hover {
            border-color: #3B82F6;
            box-shadow: 0 0 0 1px rgba(59, 130, 246, .12);
        }

        .stVerticalBlock:has(
            > [data-testid="stElementContainer"] .mi-table-filters-anchor
        ) [data-testid="stVerticalBlock"] {
            gap: .12rem;
        }

        .stVerticalBlock:has(
            > [data-testid="stElementContainer"] .mi-table-filters-anchor
        ) [data-testid="stTextInput"] input {
            height: 36px !important;
            min-height: 36px !important;
            padding: 4px 8px;
            border: 1px solid #2B3B52;
            border-radius: 4px;
            background: #0F172A;
            color: #E2E8F0;
            font-size: 12px;
        }

        .stVerticalBlock:has(
            > [data-testid="stElementContainer"] .mi-table-filters-anchor
        ) [data-testid="stSelectbox"] [role="group"] {
            height: 38px !important;
            min-height: 38px !important;
            border-color: #2B3B52;
            border-radius: 4px !important;
            background: #0F172A;
            cursor: pointer !important;
        }

        .stVerticalBlock:has(
            > [data-testid="stElementContainer"] .mi-table-filters-anchor
        ) [data-testid="stSelectbox"] [role="combobox"] {
            height: 36px !important;
            min-height: 36px !important;
            padding: 0 8px;
            color: #E2E8F0;
            font-size: 12px !important;
            cursor: pointer !important;
        }

        .stVerticalBlock:has(
            > [data-testid="stElementContainer"] .mi-table-filters-anchor
        ) [data-testid="stSelectbox"] button {
            cursor: pointer !important;
        }

        @media (max-width: 1100px) {
            div[data-testid="stLayoutWrapper"]:has(
                .mi-global-filters-anchor
            ) [data-testid="stHorizontalBlock"] {
                display: grid;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 6px 10px;
            }

            div[data-testid="stLayoutWrapper"]:has(
                .mi-global-filters-anchor
            ) [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
                width: 100% !important;
                min-width: 0;
                flex: initial !important;
            }
        }

        header[data-testid="stHeader"] {
            height: 0;
            min-height: 0;
            background: transparent;
        }

        header[data-testid="stHeader"] [data-testid="stToolbar"] {
            display: none;
        }

        header[data-testid="stHeader"]
        [data-testid="stToolbar"]:has(
            [data-testid="stExpandSidebarButton"]
        ) {
            position: fixed;
            top: 0;
            left: 0;
            z-index: 10001;
            display: block !important;
            width: 48px;
            height: 48px;
            background: transparent;
        }

        header[data-testid="stHeader"]
        [data-testid="stToolbar"]:has(
            [data-testid="stExpandSidebarButton"]
        ) [data-testid="stToolbarActions"],
        header[data-testid="stHeader"]
        [data-testid="stToolbar"]:has(
            [data-testid="stExpandSidebarButton"]
        ) [data-testid="stAppDeployButton"],
        header[data-testid="stHeader"]
        [data-testid="stToolbar"]:has(
            [data-testid="stExpandSidebarButton"]
        ) [data-testid="stMainMenu"],
        header[data-testid="stHeader"]
        [data-testid="stToolbar"]:has(
            [data-testid="stExpandSidebarButton"]
        ) [data-testid="stStatusWidget"] {
            display: none !important;
        }

        header[data-testid="stHeader"]
        [data-testid="stToolbar"]:has(
            [data-testid="stExpandSidebarButton"]
        ) [data-testid="stExpandSidebarButton"] {
            position: fixed;
            top: 8px;
            left: 8px;
            z-index: 10002;
            display: flex !important;
            width: 36px;
            height: 36px;
            visibility: visible !important;
            border: 1px solid #334155;
            border-radius: 8px;
            background: #111B2A;
            color: #CBD5E1;
            box-shadow: 0 4px 12px rgba(0, 0, 0, .3);
        }

        header[data-testid="stHeader"]
        [data-testid="stToolbar"]:has(
            [data-testid="stExpandSidebarButton"]
        ) [data-testid="stExpandSidebarButton"]:hover {
            border-color: rgba(96, 165, 250, .65);
            background: #17263A;
            color: #93C5FD;
        }

        /* =====================================================
           SIDEBAR
           ===================================================== */

        section[data-testid="stSidebar"] {

            background-color:
                #0B1220;

        }

        section[data-testid="stSidebar"] [data-testid="stSidebarContent"] {
            display: flex;
            flex-direction: column;
            overflow-x: hidden;
        }

        section[data-testid="stSidebar"] [data-testid="stSidebarHeader"] {
            margin-bottom: 4px;
        }

        section[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] {
            visibility: visible !important;
            opacity: 1 !important;
        }

        section[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] button {
            width: 32px;
            height: 32px;
            border: 1px solid transparent;
            border-radius: 7px;
            color: #A8B6C9;
        }

        section[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] button:hover {
            border-color: #334155;
            background: #111B2A;
            color: #E2E8F0;
        }

        section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {
            display: contents;
        }

        section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"]
        > div:has(.mi-sidebar-brand) {
            order: 0;
            flex: 0 0 auto;
        }

        section[data-testid="stSidebar"] .st-key-mi-sidebar-account {
            order: 2;
            flex: 0 0 auto;
            padding-top: 8px;
        }

        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] {
            order: 1;
            min-height: 0;
            min-width: 0;
            flex: 0 1 auto;
            overflow-y: auto;
            overflow-x: hidden;
        }

        section[data-testid="stSidebar"] .st-key-mi-sidebar-footer {
            order: 3;
            flex: 0 0 auto;
            margin-top: auto;
            padding-bottom: 12px;
        }

        .mi-sidebar-brand {
            display: flex;
            align-items: center;
            gap: 11px;
            padding: 5px 2px 12px;
            margin-bottom: 6px;
            border-bottom: 1px solid #263449;
        }

        .mi-sidebar-brand-icon {
            display: grid;
            width: 34px;
            height: 34px;
            flex: 0 0 34px;
            place-items: center;
            border: 1px solid rgba(96, 165, 250, .25);
            border-radius: 10px;
            background: linear-gradient(
                145deg,
                rgba(59, 130, 246, .2),
                rgba(59, 130, 246, .07)
            );
            color: #60A5FA;
            font-size: 22px;
            font-weight: 700;
            box-shadow: inset 0 1px 0 rgba(255, 255, 255, .05);
        }

        .mi-sidebar-brand-title {
            color: #F1F5F9;
            font-size: 13px;
            font-weight: 700;
            line-height: 1.15;
        }

        .mi-sidebar-brand-caption {
            margin-top: 4px;
            color: #8292A8;
            font-size: 8px;
            font-weight: 700;
            letter-spacing: .1em;
        }

        .mi-sidebar-section-title {
            margin: 10px 0 6px;
            color: #8292A8;
            font-size: 9px;
            font-weight: 700;
            letter-spacing: .1em;
        }

        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] {
            padding-top: 3px;
        }

        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] ul {
            width: 100%;
            min-width: 0;
            gap: 2px;
        }

        section[data-testid="stSidebar"] [data-testid="stDateInput"] label {
            color: #A8B6C9;
            font-size: 11px;
        }

        section[data-testid="stSidebar"] [data-testid="stDateInput"] input {
            min-height: 36px;
            border-color: #263449;
            border-radius: 7px;
            background: #111B2A;
            color: #E2E8F0;
            font-size: 12px;
        }


        section[data-testid="stSidebar"]
        a[data-testid="stSidebarNavLink"] {

            min-height: 36px;
            min-width: 0;
            box-sizing: border-box;

            border-radius: 8px;

            transition:
                background-color 180ms ease,
                border-color 180ms ease,
                color 180ms ease;

            border-left:
                3px solid transparent;

            color: #A8B6C9;
            font-family:
                Inter,
                "Segoe UI Variable",
                "Segoe UI",
                Arial,
                sans-serif !important;
            font-size: 12px !important;
            font-weight: 550;
            letter-spacing: -.005em;
            line-height: 1.25;

        }

        section[data-testid="stSidebar"]
        a[data-testid="stSidebarNavLink"] p {
            margin: 0;
            font-family:
                Inter,
                "Segoe UI Variable",
                "Segoe UI",
                Arial,
                sans-serif !important;
            font-size: 12px !important;
            font-weight: inherit !important;
            line-height: 1.25 !important;
            transition:
                color 180ms ease,
                transform 180ms ease;
        }

        section[data-testid="stSidebar"]
        a[data-testid="stSidebarNavLink"] [data-testid="stIconMaterial"] {
            color: #91A7C2;
            transition:
                color 180ms ease,
                transform 180ms cubic-bezier(.2, .7, .2, 1);
        }

        section[data-testid="stSidebar"]
        a[data-testid="stSidebarNavLink"]:not([aria-current="page"]):hover,
        section[data-testid="stSidebar"]
        a[data-testid="stSidebarNavLink"]:not([aria-current="page"]):focus-visible {

            background:
                linear-gradient(
                    100deg,
                    rgba(68, 112, 171, .16),
                    rgba(42, 72, 111, .07)
                );

            border-left:
                3px solid rgba(115, 169, 255, .62);

            color: #D7E5F7;
        }

        section[data-testid="stSidebar"]
        a[data-testid="stSidebarNavLink"]:not([aria-current="page"]):hover p,
        section[data-testid="stSidebar"]
        a[data-testid="stSidebarNavLink"]:not([aria-current="page"]):focus-visible p {
            color: #E6F0FF;
            transform: translateX(2px);
        }

        section[data-testid="stSidebar"]
        a[data-testid="stSidebarNavLink"]:not([aria-current="page"]):hover
        [data-testid="stIconMaterial"],
        section[data-testid="stSidebar"]
        a[data-testid="stSidebarNavLink"]:not([aria-current="page"]):focus-visible
        [data-testid="stIconMaterial"] {
            color: #9FC5FF;
            transform: translateX(2px);
        }

        @media (prefers-reduced-motion: reduce) {
            section[data-testid="stSidebar"]
            a[data-testid="stSidebarNavLink"],
            section[data-testid="stSidebar"]
            a[data-testid="stSidebarNavLink"] p,
            section[data-testid="stSidebar"]
            a[data-testid="stSidebarNavLink"] [data-testid="stIconMaterial"] {
                transition: none;
            }
        }


        section[data-testid="stSidebar"]
        a[data-testid="stSidebarNavLink"][aria-current="page"] {

            background:
                linear-gradient(
                    100deg,
                    rgba(59,130,246,0.2),
                    rgba(59,130,246,0.06)
                );

            border-left:
                3px solid #60A5FA;

            box-shadow:
                inset 0 0 18px rgba(59,130,246,0.06);

            color: #DBEAFE;
            font-weight: 650;

        }

        @media (max-width: 700px) {
            [data-testid="stMainBlockContainer"] {
                padding-top: .5rem;
                padding-right: .75rem;
                padding-left: .75rem;
            }

            div[data-testid="stLayoutWrapper"]:has(
                .mi-global-filters-anchor
            ) {
                padding: 4px 4px 7px;
            }

            .mi-page-heading {
                gap: 11px;
                padding-bottom: 13px;
            }

            .mi-page-heading-icon {
                width: 39px;
                height: 39px;
                flex-basis: 39px;
                border-radius: 10px;
                font-size: 18px;
            }

            .mi-page-title {
                font-size: 22px !important;
            }

            .mi-page-subtitle {
                font-size: 11px;
            }
        }

        </style>

        """,

        unsafe_allow_html=True
    )


# =========================================================
# CARD DESTAQUE
# =========================================================

def card_destaque(
    titulo,
    produto,
    valor,
    icone,
    descricao
):

    html = f"""
    <div class="mi-highlight">

        <div class="mi-highlight-glow"></div>

        <div class="mi-highlight-content">

            <div class="mi-highlight-top">

                <span class="mi-highlight-icon">
                    {icone}
                </span>

                <span class="mi-highlight-title">
                    {titulo}
                </span>

            </div>

            <div class="mi-highlight-product">
                {produto}
            </div>

            <div class="mi-highlight-value">
                {valor}
            </div>

            <div class="mi-highlight-description">
                {descricao}
            </div>

        </div>

    </div>

    <style>

        /* =====================================================
           ANIMAÇÃO
           ===================================================== */

        @keyframes mi-highlight-enter {{

            from {{

                opacity: 0;

                transform:
                    translateY(18px)
                    scale(0.98);

                filter:
                    blur(1.5px);

            }}

            to {{

                opacity: 1;

                transform:
                    translateY(0)
                    scale(1);

                filter:
                    blur(0);

            }}

        }}


        /* =====================================================
           CARD
           ===================================================== */

        .mi-highlight {{

            position: relative;

            overflow: hidden;

            min-height: 170px;

            padding: 18px;

            box-sizing: border-box;

            border-radius: 16px;

            background:
                linear-gradient(
                    145deg,
                    #1E293B,
                    #111827
                );

            border:
                1px solid rgba(255,255,255,0.08);

            box-shadow:
                0 8px 24px rgba(0,0,0,0.20);

            transition:
                transform 220ms ease,
                box-shadow 220ms ease,
                border-color 220ms ease;

        }}


        .mi-highlight:hover {{

            transform:
                translateY(-5px);

            box-shadow:
                0 16px 34px rgba(0,0,0,0.35);

            border-color:
                rgba(96,165,250,0.25);

        }}


        /* =====================================================
           GLOW
           ===================================================== */

        .mi-highlight-glow {{

            position: absolute;

            width: 180px;
            height: 180px;

            right: -90px;
            top: -90px;

            background:
                radial-gradient(
                    circle,
                    rgba(59,130,246,0.18),
                    transparent 70%
                );

            opacity:
                0;

            pointer-events:
                none;

            transition:
                opacity 250ms ease,
                transform 400ms ease;

        }}


        .mi-highlight:hover .mi-highlight-glow {{

            opacity:
                1;

            transform:
                scale(1.3);

        }}


        /* =====================================================
           CONTEÚDO
           ===================================================== */

        .mi-highlight-content {{

            position:
                relative;

            z-index:
                1;

        }}


        .mi-highlight-top {{

            display:
                flex;

            align-items:
                center;

            gap:
                8px;

            margin-bottom:
                12px;

        }}


        .mi-highlight-icon {{

            font-size:
                22px;

            line-height:
                22px;

            transition:
                transform 220ms ease;

        }}


        .mi-highlight:hover
        .mi-highlight-icon {{

            transform:
                scale(1.12);

        }}


        .mi-highlight-title {{

            color:
                #94A3B8;

            font-size:
                14px;

            line-height:
                20px;

        }}


        .mi-highlight-product {{

            color:
                white;

            font-size:
                18px;

            font-weight:
                600;

            line-height:
                24px;

            margin-bottom:
                8px;

        }}


        .mi-highlight-value {{

            color:
                #22C55E;

            font-size:
                28px;

            font-weight:
                700;

            line-height:
                34px;

            margin-bottom:
                5px;

        }}


        .mi-highlight-description {{

            color:
                #64748B;

            font-size:
                12px;

            line-height:
                18px;

        }}

    </style>
    """

    st.html(html)


# =========================================================
# CARD DE RECOMENDAÇÃO
# =========================================================

def card_recomendacao(
    tipo,
    produto,
    destaque,
    descricao,
    icone
):

    html = f"""
    <div class="mi-recommendation">

        <div class="mi-recommendation-glow"></div>

        <div class="mi-recommendation-content">

            <div class="mi-recommendation-header">

                <span class="mi-recommendation-icon">
                    {icone}
                </span>

                <span class="mi-recommendation-type">
                    {tipo}
                </span>

            </div>

            <div class="mi-recommendation-product">
                {produto}
            </div>

            <div class="mi-recommendation-highlight">
                {destaque}
            </div>

            <div class="mi-recommendation-description">
                {descricao}
            </div>

        </div>

    </div>

    <style>

        /* =====================================================
           ANIMAÇÃO
           ===================================================== */

        @keyframes mi-recommendation-enter {{

            from {{

                opacity: 0;

                transform:
                    translateY(14px)
                    scale(0.985);

            }}

            to {{

                opacity: 1;

                transform:
                    translateY(0)
                    scale(1);

            }}

        }}


        /* =====================================================
           CARD
           ===================================================== */

        .mi-recommendation {{

            position: relative;

            overflow: hidden;

            padding: 18px;

            border-radius: 16px;

            background:
                linear-gradient(
                    145deg,
                    #1E293B,
                    #111827
                );

            border:
                1px solid rgba(255,255,255,0.08);

            box-shadow:
                0 8px 24px rgba(0,0,0,0.20);

            transition:
                transform 220ms ease,
                box-shadow 220ms ease,
                border-color 220ms ease;

        }}


        .mi-recommendation:hover {{

            transform:
                translateY(-4px);

            box-shadow:
                0 15px 32px rgba(0,0,0,0.34);

            border-color:
                rgba(96,165,250,0.24);

        }}


        /* =====================================================
           GLOW
           ===================================================== */

        .mi-recommendation-glow {{

            position: absolute;

            width: 180px;
            height: 180px;

            right: -90px;
            top: -90px;

            background:
                radial-gradient(
                    circle,
                    rgba(59,130,246,0.16),
                    transparent 70%
                );

            opacity:
                0;

            pointer-events:
                none;

            transition:
                opacity 250ms ease,
                transform 400ms ease;

        }}


        .mi-recommendation:hover
        .mi-recommendation-glow {{

            opacity:
                1;

            transform:
                scale(1.3);

        }}


        /* =====================================================
           CONTEÚDO
           ===================================================== */

        .mi-recommendation-content {{

            position:
                relative;

            z-index:
                1;

        }}


        .mi-recommendation-header {{

            display:
                flex;

            align-items:
                center;

            gap:
                8px;

            margin-bottom:
                12px;

        }}


        .mi-recommendation-icon {{

            font-size:
                21px;

        }}


        .mi-recommendation-type {{

            color:
                #94A3B8;

            font-size:
                14px;

        }}


        .mi-recommendation-product {{

            color:
                white;

            font-size:
                18px;

            font-weight:
                600;

            margin-bottom:
                8px;

        }}


        .mi-recommendation-highlight {{

            color:
                #60A5FA;

            font-size:
                20px;

            font-weight:
                700;

            margin-bottom:
                6px;

        }}


        .mi-recommendation-description {{

            color:
                #64748B;

            font-size:
                12px;

            line-height:
                18px;

        }}

    </style>
    """

    st.html(html)