import copy
import re
import unicodedata
from html import escape
import json
from datetime import date
from math import isfinite

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from plotly.utils import PlotlyJSONEncoder


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
    rodape_html: str | None = None
) -> None:
    """Renderiza um gráfico em um painel compacto e padronizado."""

    indice_animacao = st.session_state.get("_mi_chart_animation_index", 0)
    st.session_state["_mi_chart_animation_index"] = indice_animacao + 1
    animar_entrada = st.session_state.get("_mi_page_entering", False)
    atraso_animacao = min(indice_animacao * 110, 550)

    tem_linha = any(
        trace.type == "scatter"
        and getattr(trace, "mode", None)
        and "lines" in trace.mode
        for trace in figura.data
    )

    layout = {
        "template": "plotly_dark",
        "paper_bgcolor": "#121C2B",
        "plot_bgcolor": "#121C2B",
        "font": {
            "family": "Inter, Segoe UI, sans-serif",
            "color": "#A8B6C9",
            "size": 11
        },
        "colorway": [
            "#3B82F6",
            "#F4513A",
            "#F5B700",
            "#22C55E",
            "#A78BFA",
            "#06B6D4"
        ],
        "hoverlabel": {
            "bgcolor": "#0B1220",
            "bordercolor": "#3B82F6",
            "font": {
                "color": "#F8FAFC",
                "family": "Inter, Segoe UI, sans-serif",
                "size": 12
            },
            "align": "left"
        },
        "hovermode": "x unified" if tem_linha else "closest",
        "hoverdistance": 24,
        "spikedistance": -1,
        "dragmode": False,
        "transition": {
            "duration": 600,
            "easing": "cubic-in-out"
        }
    }
    if altura is not None:
        layout["height"] = altura

    figura.update_layout(**layout)
    figura.update_xaxes(
        gridcolor="rgba(148, 163, 184, 0.10)",
        linecolor="rgba(148, 163, 184, 0.16)",
        rangeslider_visible=False,
        fixedrange=True,
        zeroline=False,
        showline=False,
        ticks="outside",
        ticklen=3,
        tickcolor="rgba(148, 163, 184, 0.22)"
    )
    figura.update_yaxes(
        gridcolor="rgba(148, 163, 184, 0.10)",
        linecolor="rgba(148, 163, 184, 0.16)",
        fixedrange=True,
        zeroline=False,
        showline=False,
        ticks="outside",
        ticklen=3,
        tickcolor="rgba(148, 163, 184, 0.22)"
    )

    for trace in figura.data:
        if trace.type == "scatter":
            modo = getattr(trace, "mode", None) or "lines"
            if "lines" in modo:
                cor_linha = getattr(trace.line, "color", None) or "#3B82F6"
                if cor_linha.startswith("#") and len(cor_linha) == 7:
                    cor_preenchimento = (
                        "rgba("
                        f"{int(cor_linha[1:3], 16)}, "
                        f"{int(cor_linha[3:5], 16)}, "
                        f"{int(cor_linha[5:7], 16)}, 0.14)"
                    )
                else:
                    cor_preenchimento = "rgba(59, 130, 246, 0.14)"

                trace.update(
                    line={
                        "width": 2.5,
                        "shape": "spline",
                        "smoothing": 0.55
                    },
                    fill="tozeroy",
                    fillcolor=cor_preenchimento,
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
            if "markers" in modo:
                trace.update(
                    marker={
                        "size": 5,
                        "line": {
                            "color": "#E2E8F0",
                            "width": 1
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
            "font": {"color": "#A8B6C9", "size": 10},
            "bgcolor": "rgba(0,0,0,0)"
        }
    )

    altura_grafico = (
        altura
        or figura.layout.height
        or 320
    )
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
            <div class="mi-chart-heading">
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
            "displayModeBar": False,
            "displaylogo": False,
            "scrollZoom": False,
            "doubleClick": False,
            "editable": False,
            "staticPlot": False
        }
        if animacao is None:
            st.plotly_chart(
                figura,
                use_container_width=True,
                height=altura_grafico,
                config=config
            )
        else:
            figura_inicial, script_animacao = animacao
            html = pio.to_html(
                figura_inicial,
                config=config,
                include_plotlyjs="cdn",
                full_html=False,
                default_width="100%",
                default_height=f"{altura_grafico}px",
                post_script=script_animacao
            )
            components.html(
                html,
                height=altura_grafico,
                scrolling=False
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


def cabecalho_pagina(
    titulo: str,
    subtitulo: str,
    icone: str
) -> None:
    st.markdown(
        f"""
        <header class="mi-page-heading">
            <div class="mi-page-heading-icon">{escape(icone)}</div>
            <div class="mi-page-heading-copy">
                <div class="mi-page-eyebrow">MARKETPLACE INTELLIGENCE</div>
                <h1 class="mi-page-title">{escape(titulo)}</h1>
                <p class="mi-page-subtitle">{escape(subtitulo)}</p>
            </div>
        </header>
        """,
        unsafe_allow_html=True
    )


def tabela_limpa(
    tabela: pd.DataFrame,
    badges: dict[str, dict[str, str]] | None = None,
    *,
    chave: str,
    linhas_por_pagina: int = 10
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
    cabecalhos = "".join(
        f'<th class="{"mi-clean-text-column" if coluna_alinhada_esquerda(str(coluna)) else ""}">'
        f"{escape(str(coluna))}</th>"
        for coluna in tabela.columns
    )

    linhas = []
    for _, linha in tabela.iterrows():
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
            celulas.append(
                f'<td class="{classe_coluna}">{conteudo}</td>'
            )

        linhas.append(f"<tr>{''.join(celulas)}</tr>")

    st.html(
        f"""
        <style>
            .mi-clean-table-wrap {{
                width: 100%;
                overflow-x: auto;
                border-top: 1px solid #263449;
                border-bottom: 1px solid #263449;
            }}
            .mi-clean-table {{
                width: 100%;
                min-width: 640px;
                border-collapse: collapse;
                color: #D7E0EE;
                font-family: inherit;
                font-size: 12px;
            }}
            .mi-clean-table th {{
                padding: 10px 12px;
                border-bottom: 1px solid #263449;
                color: #8292A8;
                font-size: 9px;
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
                font-size: 10px;
                font-weight: 650;
            }}
            .mi-clean-badge.ml {{
                background: rgba(245, 183, 0, .13);
                color: #F5B700;
            }}
            .mi-clean-badge.shopee {{
                background: rgba(244, 81, 58, .13);
                color: #FF806D;
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
            @media (max-width: 700px) {{
                .mi-clean-table {{
                    font-size: 11px;
                }}
                .mi-clean-table th,
                .mi-clean-table td {{
                    padding: 8px 7px;
                }}
            }}
        </style>
        <div class="mi-clean-table-wrap">
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

def card(
    titulo,
    valor,
    icone,
    descricao="",
    tipo="normal",
    tooltip=""
):

    indicador_tooltip = (
        '<span class="mi-card-info" tabindex="0" '
        'aria-label="Mais informações">'
        '<span class="mi-card-info-symbol">!</span>'
        f'<span class="mi-card-tooltip">'
        f'{escape(str(tooltip))}</span></span>'
        if tooltip
        else ""
    )

    html = f"""
    <div class="mi-card mi-card-{tipo}">

        <div class="mi-card-glow-clip">
            <div class="mi-card-glow"></div>
        </div>

        <div class="mi-card-content">

            <div class="mi-card-header">

                <span class="mi-card-icon">
                    {icone}
                </span>

                <span class="mi-card-title">
                    {titulo}
                </span>
                {indicador_tooltip}

            </div>

            <div class="mi-card-value">
                {valor}
            </div>

            <div class="mi-card-description">
                {descricao}
            </div>

        </div>

    </div>

    <style>

        /* =====================================================
           ANIMAÇÃO DE ENTRADA
           ===================================================== */

        @keyframes mi-card-enter {{

            from {{
                opacity: 0;
                transform:
                    translateY(24px)
                    scale(0.98);
                filter: blur(1.5px);
            }}

            to {{
                opacity: 1;
                transform:
                    translateY(0)
                    scale(1);
                filter: blur(0);
            }}

        }}


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

            border-radius: 14px;

            min-height: 104px;

            border:
                1px solid rgba(255,255,255,0.08);

            box-shadow:
                0 8px 24px rgba(0,0,0,0.20);

            box-sizing: border-box;

            margin-bottom: 8px;

            animation:
                mi-card-enter
                560ms
                cubic-bezier(.22,.61,.36,1)
                both;

            transition:
                transform 220ms ease,
                box-shadow 220ms ease,
                border-color 220ms ease,
                background 220ms ease;

        }}


        /* =====================================================
           HOVER
           ===================================================== */

        .mi-card:hover {{

            transform:
                translateY(-6px)
                scale(1.015);

            z-index: 20;

            box-shadow:
                0 18px 38px rgba(0,0,0,0.38);

            border-color:
                rgba(96,165,250,0.28);

            background:
                linear-gradient(
                    145deg,
                    #26364D,
                    #141D2D
                );

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

            font-size: 22px;

            line-height: 22px;

            transition:
                transform 220ms ease;

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


        .mi-card-description {{

            color: #64748B;

            font-size: 12px;

            line-height: 18px;

        }}


        .mi-card-positive .mi-card-description {{

            color: #4ADE80;

        }}


        .mi-card-negative .mi-card-description {{

            color: #FB7185;

        }}


        .mi-card-neutral .mi-card-description {{

            color: #FBBF24;

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

            animation:
                mi-hero-enter
                700ms
                cubic-bezier(.22,.61,.36,1)
                both;

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
        st.html(
            f"""
        <style>

        @keyframes mi-page-enter-{nome} {{

            from {{
                opacity: 0;
                transform:
                    translateY(10px);
            }}

            to {{
                opacity: 1;
                transform:
                    translateY(0);
            }}

        }}

        .stAppViewContainer {{

            animation:
                mi-page-enter-{nome}
                280ms
                cubic-bezier(.22,.61,.36,1)
                both;

        }}

        @media (prefers-reduced-motion: reduce) {{
            .stAppViewContainer {{
                animation: none;
            }}
        }}
        </style>
        """,
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

    st.markdown(
        """

        <style>


        /* =====================================================
           FUNDO
           ===================================================== */

        .stApp {

            background-color:
                #0F172A;

        }

        div[data-testid="stVerticalBlock"]:has(
            > [data-testid="stElementContainer"] .mi-chart-heading
        ),

        div[data-testid="stVerticalBlock"]:has(
            > [data-testid="stElementContainer"] .mi-dashboard-panel
        ) {

            background: #121C2B;

            border-color: #263449;

            border-radius: 8px;

            box-shadow: 0 5px 16px rgba(0,0,0,0.18);

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

            transform: translateY(-4px);

            border-color: rgba(96,165,250,0.48);

            box-shadow:
                0 16px 32px rgba(0,0,0,0.32),
                0 0 22px rgba(59,130,246,0.14);

        }

        .mi-chart-heading {

            min-height: 42px;

            padding: 1px 1px 8px;

            border-bottom: 1px solid #263449;

            margin-bottom: 5px;

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

        .mi-chart-subtitle {

            color: #8292A8;

            font-size: 10px;

            line-height: 14px;

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
            display: grid;
            width: 44px;
            height: 44px;
            flex: 0 0 44px;
            place-items: center;
            border: 1px solid rgba(96, 165, 250, .2);
            border-radius: 12px;
            background:
                radial-gradient(
                    circle at 25% 15%,
                    rgba(96, 165, 250, .2),
                    transparent 70%
                ),
                #111D2D;
            color: #60A5FA;
            font-size: 20px;
            box-shadow: inset 0 1px 0 rgba(255, 255, 255, .04);
        }

        .mi-page-heading-copy {
            min-width: 0;
        }

        .mi-page-eyebrow {
            margin-bottom: 4px;
            color: #8FA1B8;
            font-size: 9px;
            font-weight: 700;
            letter-spacing: .14em;
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

        div[data-testid="stLayoutWrapper"]:has(.mi-global-filters-anchor) {
            position: sticky;
            top: 0;
            z-index: 1000;
            padding: 4px 8px 8px;
            border-bottom: 1px solid #263449;
            background: rgba(15, 23, 42, .97);
            box-shadow: 0 5px 14px rgba(0, 0, 0, .14);
            backdrop-filter: blur(14px);
        }

        .mi-pie-summary {
            display: flex;
            flex-direction: column;
            gap: 5px;
            padding: 0 8px 4px;
        }

        .mi-pie-summary-row {
            display: flex;
            min-width: 0;
            align-items: center;
            justify-content: space-between;
            gap: 4px;
            color: #D7E0EE;
            font-size: 9px;
            line-height: 1.3;
        }

        .mi-pie-summary-label {
            display: flex;
            min-width: max-content;
            align-items: center;
            gap: 4px;
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
            font-weight: 650;
            white-space: nowrap;
        }

        .mi-pie-summary-share {
            margin-left: 3px;
            color: #8FA1B8;
            font-weight: 400;
            white-space: nowrap;
        }

        div[data-testid="stLayoutWrapper"]:has(
            .mi-global-filters-anchor
        ) label {
            height: 12px !important;
            min-height: 12px !important;
            margin: 0;
            padding: 0;
            color: #8292A8;
            font-size: 9px !important;
            font-weight: 700;
            letter-spacing: .08em;
            line-height: 10px !important;
            text-transform: uppercase;
            cursor: pointer;
        }

        div[data-testid="stLayoutWrapper"]:has(
            .mi-global-filters-anchor
        ) label p {
            height: 10px;
            margin: 0;
            font-size: 9px !important;
            line-height: 10px !important;
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
            font-size: 11px !important;
            cursor: pointer !important;
        }

        div[data-testid="stLayoutWrapper"]:has(
            .mi-global-filters-anchor
        ) [data-testid="stSelectbox"] [role="combobox"] {
            height: 28px !important;
            min-height: 28px !important;
            padding: 0 8px;
            color: #E2E8F0;
            font-size: 11px !important;
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
            font-size: 11px;
            cursor: pointer !important;
        }

        .stVerticalBlock:has(
            > [data-testid="stElementContainer"] .mi-table-filters-anchor
        ) label {
            height: 12px !important;
            min-height: 12px !important;
            margin: 0;
            padding: 0;
            color: #8292A8;
            font-size: 9px !important;
            font-weight: 700;
            letter-spacing: .08em;
            line-height: 10px !important;
            text-transform: uppercase;
            cursor: pointer;
        }

        .stVerticalBlock:has(
            > [data-testid="stElementContainer"] .mi-table-filters-anchor
        ) label p {
            height: 10px;
            margin: 0;
            font-size: 9px !important;
            line-height: 10px !important;
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
            height: 28px !important;
            min-height: 28px !important;
            padding: 4px 8px;
            border: 1px solid #2B3B52;
            border-radius: 4px;
            background: #0F172A;
            color: #E2E8F0;
            font-size: 11px;
        }

        .stVerticalBlock:has(
            > [data-testid="stElementContainer"] .mi-table-filters-anchor
        ) [data-testid="stSelectbox"] [role="group"] {
            height: 30px !important;
            min-height: 30px !important;
            border-color: #2B3B52;
            border-radius: 4px !important;
            background: #0F172A;
            cursor: pointer !important;
        }

        .stVerticalBlock:has(
            > [data-testid="stElementContainer"] .mi-table-filters-anchor
        ) [data-testid="stSelectbox"] [role="combobox"] {
            height: 28px !important;
            min-height: 28px !important;
            padding: 0 8px;
            color: #E2E8F0;
            font-size: 11px !important;
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
            order: 1;
            padding-top: 8px;
            padding-bottom: 12px;
        }

        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] {
            order: 2;
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

            border-radius: 8px;

            transition:
                background-color 140ms ease,
                transform 140ms ease,
                border-color 140ms ease;

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
        }


        section[data-testid="stSidebar"]
        a[data-testid="stSidebarNavLink"]:hover {

            background-color:
                rgba(96,165,250,0.08);

            transform:
                translateX(1px);

            border-left:
                3px solid rgba(96,165,250,0.45);

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

            animation:
                mi-highlight-enter
                620ms
                cubic-bezier(.22,.61,.36,1)
                both;

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

            animation:
                mi-recommendation-enter
                620ms
                cubic-bezier(.22,.61,.36,1)
                both;

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