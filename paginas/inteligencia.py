from html import escape

import streamlit as st

from componentes import animar_pagina, cabecalho_pagina
from dados_periodo import obter_oportunidades


def _moeda(valor: float) -> str:
    return (
        f"R$ {valor:,.2f}"
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )


def _explicacao_oportunidade(
    produto,
    classificacao: str,
    faturamento_referencia: float,
) -> str:
    unidades = float(produto["unidades"])
    faturamento = float(produto["faturamento"])
    margem = float(produto["margem"])
    estoque = float(produto["estoque_atual"])
    cobertura = float(produto["dias_estoque"])
    vendas_dia = float(produto["media_vendas_dia"])

    if classificacao == "Risco operacional":
        return (
            f"Vendeu {unidades:.0f} unidade(s) no período, mas o saldo "
            f"informado está em {estoque:.0f}. O produto pode estar sem "
            "disponibilidade para atender novas vendas."
        )
    if classificacao == "Reposição urgente":
        return (
            f"O saldo atual é de {estoque:.0f} unidade(s), equivalente a "
            f"{cobertura:.1f} dia(s) de cobertura pela média de "
            f"{vendas_dia:.2f} venda(s) por dia no período."
        )
    if classificacao == "Alta performance":
        return (
            f"Faturou {_moeda(faturamento)} — acima ou igual à mediana "
            f"do catálogo ({_moeda(faturamento_referencia)}) — e teve "
            f"margem de {margem:.1f}% (critério: pelo menos 20%)."
        )
    if classificacao == "Atenção":
        return (
            f"A margem foi de {margem:.1f}%, abaixo do limite de atenção "
            "de 15%. O faturamento no período foi "
            f"{_moeda(faturamento)} em {unidades:.0f} unidade(s)."
        )
    if classificacao == "Baixo giro":
        if unidades <= 0:
            return (
                "Não houve unidades vendidas no período selecionado. "
                f"O saldo informado é de {estoque:.0f} unidade(s), "
                "portanto não há giro observado para estimar cobertura."
            )
        return (
            f"Vendeu {unidades:.0f} unidade(s) no período e o saldo atual "
            f"representa {cobertura:.1f} dias de cobertura, acima do "
            "limite de 30 dias usado para sinalizar baixo giro."
        )
    if classificacao == "Alta margem":
        return (
            f"A margem foi de {margem:.1f}%, acima do critério de "
            "alta margem (30%). O faturamento no período foi "
            f"{_moeda(faturamento)}."
        )
    return "Classificação baseada nos dados do período selecionado."


def _acao_oportunidade(produto, classificacao: str) -> str:
    if classificacao == "Risco operacional":
        return (
            "Confirme o saldo no marketplace e no estoque físico; se "
            "estiver correto, planeje reposição antes de reativar ou "
            "impulsionar o anúncio."
        )
    if classificacao == "Reposição urgente":
        return (
            "Revise o prazo do fornecedor e planeje a reposição. A cobertura "
            "é uma estimativa baseada na média diária deste período."
        )
    if classificacao == "Alta performance":
        return (
            "Verifique se há estoque suficiente e acompanhe a margem antes "
            "de aumentar investimento ou ampliar a oferta."
        )
    if classificacao == "Atenção":
        return (
            "Revise custo cadastrado, taxas, frete e descontos antes de "
            "alterar preço; compare o detalhamento das vendas para localizar "
            "o componente que mais pesa."
        )
    if classificacao == "Baixo giro":
        if float(produto["unidades"]) <= 0:
            return (
                "Confira se o anúncio está ativo, competitivo e corretamente "
                "categorizado. Considere promoção somente após verificar "
                "preço, procura e margem."
            )
        return (
            "Revise preço, exposição e procura. Considere uma promoção apenas "
            "se a margem após desconto continuar adequada."
        )
    if classificacao == "Alta margem":
        return (
            "Avalie ampliar a exposição ou testar escala gradualmente, "
            "monitorando procura, estoque e margem."
        )
    return str(produto["acao_sugerida"])


animar_pagina("inteligencia")

data_inicio = st.session_state.get("data_inicio")
data_fim = st.session_state.get("data_fim")
produto_selecionado = st.session_state.get("produto_global")
if produto_selecionado == "Todos os produtos":
    produto_selecionado = None
marketplace_selecionado = st.session_state.get("marketplace_global")
if marketplace_selecionado == "Todos":
    marketplace_selecionado = None

if data_inicio is None or data_fim is None:
    st.warning("Selecione um período na barra lateral.")
    st.stop()

oportunidades = obter_oportunidades(
    data_inicio,
    data_fim,
    produto_selecionado,
    marketplace_selecionado
)
alertas = oportunidades[
    oportunidades["classificacao"] != "Normal"
].copy()
alertas_ativos = alertas[
    ~alertas["classificacao"].isin(["Alta performance", "Alta margem"])
]

categorias = {
    "Risco operacional": {
        "nome": "Sem estoque",
        "icone": "🔴",
        "prioridade": "URGENTE",
        "classe": "critical"
    },
    "Reposição urgente": {
        "nome": "Reposição urgente",
        "icone": "🟠",
        "prioridade": "ALTA",
        "classe": "warning"
    },
    "Alta performance": {
        "nome": "Alta performance",
        "icone": "🟢",
        "prioridade": "OPORTUNIDADE",
        "classe": "positive"
    },
    "Atenção": {
        "nome": "Margem sob atenção",
        "icone": "🟡",
        "prioridade": "ANALISAR",
        "classe": "warning"
    },
    "Baixo giro": {
        "nome": "Estoque parado",
        "icone": "🟤",
        "prioridade": "ANALISAR",
        "classe": "muted"
    },
    "Alta margem": {
        "nome": "Alta margem",
        "icone": "🔵",
        "prioridade": "OPORTUNIDADE",
        "classe": "info"
    }
}

cabecalho_pagina(
    "Inteligência",
    "Alertas e oportunidades operacionais identificados nos dados do "
    f"período de {data_inicio.strftime('%d/%m/%Y')} a "
    f"{data_fim.strftime('%d/%m/%Y')}.",
    "✦"
)

urgentes = alertas[
    alertas["classificacao"].isin(
        ["Risco operacional", "Reposição urgente"]
    )
]

with st.container(border=True):
    st.markdown(
        """
        <div class="mi-chart-heading mi-dashboard-panel">
            <div class="mi-chart-title">Resumo das oportunidades</div>
            <div class="mi-chart-subtitle">
                Prioridades calculadas a partir de vendas, margem e estoque
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    metricas = st.columns(3, gap="medium")
    metricas[0].metric("Alertas ativos", len(alertas_ativos))
    metricas[1].metric("Ruptura ou reposição urgente", len(urgentes))
    metricas[2].metric(
        "Oportunidades de desempenho",
        int(
            alertas["classificacao"].isin(
                ["Alta performance", "Alta margem"]
            ).sum()
        )
    )

st.markdown(
    """
    <style>
        .mi-opportunity-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 12px;
            margin-top: 10px;
        }
        .mi-opportunity-card {
            position: relative;
            overflow: hidden;
            min-height: 220px;
            padding: 15px 16px 14px;
            border: 1px solid #263449;
            border-left: 3px solid #64748B;
            border-radius: 8px;
            background: #121C2B;
            transition:
                transform 200ms ease,
                border-color 200ms ease,
                box-shadow 200ms ease;
        }
        .mi-opportunity-card:hover {
            transform: translateY(-2px);
            border-color: rgba(96, 165, 250, .48);
            box-shadow: 0 10px 22px rgba(0, 0, 0, .25);
        }
        .mi-opportunity-card.critical { border-left-color: #F4513A; }
        .mi-opportunity-card.warning { border-left-color: #F5B700; }
        .mi-opportunity-card.positive { border-left-color: #22C55E; }
        .mi-opportunity-card.info { border-left-color: #3B82F6; }
        .mi-opportunity-card.muted { border-left-color: #94A3B8; }
        .mi-opportunity-heading {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 8px;
            margin-bottom: 7px;
        }
        .mi-opportunity-type {
            color: #A8B6C9;
            font-size: 12px;
            font-weight: 700;
        }
        .mi-opportunity-priority {
            flex: 0 0 auto;
            padding: 3px 6px;
            border: 1px solid #334155;
            border-radius: 4px;
            color: #CBD5E1;
            font-size: 10px;
            font-weight: 700;
            letter-spacing: .04em;
        }
        .mi-opportunity-priority.critical,
        .mi-opportunity-priority.warning {
            border-color: rgba(245, 183, 0, .35);
            color: #F5B700;
        }
        .mi-opportunity-product {
            overflow: hidden;
            margin-bottom: 4px;
            color: #F1F5F9;
            font-size: 15px;
            font-weight: 650;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        .mi-opportunity-sku {
            margin-bottom: 10px;
            color: #8292A8;
            font-size: 12px;
        }
        .mi-opportunity-metrics {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 7px 12px;
        }
        .mi-opportunity-metric {
            display: flex;
            flex-direction: column;
            align-items: flex-start;
            gap: 3px;
            min-width: 0;
            padding-bottom: 6px;
            border-bottom: 1px solid rgba(51, 65, 85, .62);
            color: #8292A8;
            font-size: 12px;
        }
        .mi-opportunity-metric b {
            color: #E2E8F0;
            font-variant-numeric: tabular-nums;
            font-weight: 650;
            text-align: left;
        }
        .mi-opportunity-action {
            margin-top: 10px;
            padding: 7px 8px;
            border: 1px solid rgba(59, 130, 246, .2);
            border-radius: 5px;
            background: rgba(59, 130, 246, .08);
            color: #93C5FD;
            font-size: 12px;
            line-height: 1.5;
        }
        .mi-opportunity-reason {
            margin-top: 11px;
            color: #CBD5E1;
            font-size: 12px;
            line-height: 1.55;
        }
        .mi-opportunity-reason b {
            color: #F1F5F9;
        }
        .mi-opportunity-action b {
            color: #BFDBFE;
        }
        .mi-opportunity-method {
            margin-top: 8px;
            color: #8292A8;
            font-size: 10px;
            line-height: 1.45;
        }
        .mi-opportunity-empty {
            margin-top: 10px;
            padding: 18px;
            border: 1px solid #263449;
            border-radius: 8px;
            background: #121C2B;
            color: #A8B6C9;
            font-size: 12px;
        }
        @media (max-width: 1100px) {
            .mi-opportunity-grid {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
        }
        @media (max-width: 700px) {
            .mi-opportunity-grid {
                grid-template-columns: minmax(0, 1fr);
            }
        }
    </style>
    """,
    unsafe_allow_html=True
)

opcoes_filtro = ["Todas"] + [
    classificacao
    for classificacao in categorias
    if (alertas["classificacao"] == classificacao).any()
]

rotulos_filtro = {
    "Todas": f"Todas ({len(alertas)})",
    **{
        classificacao: (
            f"{categorias[classificacao]['icone']} "
            f"{categorias[classificacao]['nome']} "
            f"({int((alertas['classificacao'] == classificacao).sum())})"
        )
        for classificacao in opcoes_filtro
        if classificacao != "Todas"
    }
}

filtro = st.segmented_control(
    "Filtrar oportunidades por categoria",
    options=opcoes_filtro,
    format_func=lambda classificacao: rotulos_filtro[classificacao],
    selection_mode="single",
    default="Todas",
    required=True,
    label_visibility="collapsed",
    width="stretch",
    wrap=True,
    key="inteligencia_filtro_categoria"
)
if filtro is None:
    filtro = "Todas"

visiveis = (
    alertas
    if filtro == "Todas"
    else alertas[alertas["classificacao"] == filtro]
)

st.markdown(
    f"#### Oportunidades priorizadas · {len(visiveis)}"
)

if visiveis.empty:
    st.markdown(
        '<div class="mi-opportunity-empty">'
        "Nenhum alerta ou oportunidade para este filtro no período."
        "</div>",
        unsafe_allow_html=True
    )
else:
    cards = []
    faturamento_referencia = float(
        oportunidades["faturamento"].median()
    )
    for _, produto in visiveis.iterrows():
        classificacao = str(produto["classificacao"])
        categoria = categorias[classificacao]
        cobertura = (
            "Sem vendas"
            if produto["dias_estoque"] == float("inf")
            else f'{produto["dias_estoque"]:.1f} dias'
        )
        estoque_atual = f'{produto["estoque_atual"]:,.0f}'.replace(",", ".")
        vendas_dia = f'{produto["media_vendas_dia"]:.2f}'
        faturamento = _moeda(float(produto["faturamento"]))
        margem = f'{produto["margem"]:.1f}%'
        unidades = f'{produto["unidades"]:,.0f}'.replace(",", ".")
        resultado = _moeda(float(produto["resultado"]))
        sku = escape(str(produto["sku"]))
        nome = escape(str(produto["produto"]))
        explicacao = escape(
            _explicacao_oportunidade(
                produto,
                classificacao,
                faturamento_referencia,
            )
        )
        acao = escape(_acao_oportunidade(produto, classificacao))
        cor_class = categoria["classe"]

        cards.append(
            f"""
            <article class="mi-opportunity-card {cor_class}">
                <div class="mi-opportunity-heading">
                    <span class="mi-opportunity-type">
                        {categoria["icone"]} {escape(categoria["nome"])}
                    </span>
                    <span class="mi-opportunity-priority {cor_class}">
                        {escape(categoria["prioridade"])}
                    </span>
                </div>
                <div class="mi-opportunity-product">{nome}</div>
                <div class="mi-opportunity-sku">SKU {sku}</div>
                <div class="mi-opportunity-metrics">
                    <div class="mi-opportunity-metric">
                        <span>Unidades vendidas</span><b>{unidades}</b>
                    </div>
                    <div class="mi-opportunity-metric">
                        <span>Margem</span><b>{margem}</b>
                    </div>
                    <div class="mi-opportunity-metric">
                        <span>Faturamento</span><b>{faturamento}</b>
                    </div>
                    <div class="mi-opportunity-metric">
                        <span>Resultado estimado</span><b>{resultado}</b>
                    </div>
                    <div class="mi-opportunity-metric">
                        <span>Estoque</span><b>{estoque_atual} un.</b>
                    </div>
                    <div class="mi-opportunity-metric">
                        <span>Cobertura</span><b>{cobertura}</b>
                    </div>
                    <div class="mi-opportunity-metric">
                        <span>Vendas/dia</span><b>{vendas_dia}</b>
                    </div>
                </div>
                <div class="mi-opportunity-reason">
                    <b>Por que apareceu:</b> {explicacao}
                </div>
                <div class="mi-opportunity-action">
                    <b>Próximo passo sugerido:</b> {acao}
                </div>
                <div class="mi-opportunity-method">
                    Indicadores calculados para o período selecionado; cobertura
                    baseada na média diária de vendas.
                </div>
            </article>
            """
        )

    st.html(
        '<div class="mi-opportunity-grid">'
        + "".join(cards)
        + "</div>"
    )

st.caption(
    "As categorias são classificações operacionais baseadas nos dados do "
    "período. A página não indica crescimento ou queda temporal porque "
    "ainda não há comparação histórica dessas métricas por produto."
)
