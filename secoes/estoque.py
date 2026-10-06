from html import escape

import pandas as pd
import streamlit as st

from componentes import card, formatar_moeda_br, icone_svg, titulo_secao


def _numero(valor: float, casas: int = 1) -> str:
    return f"{valor:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _renderizar_alertas(estoque: pd.DataFrame) -> None:
    sem_estoque = estoque[estoque["estoque_atual"] <= 0]
    em_risco = estoque[
        (estoque["estoque_atual"] > 0)
        & (estoque["dias_estoque"] <= 15)
    ]
    sem_estoque_com_perda = estoque[
        (estoque["estoque_atual"] <= 0)
        & (estoque["receita_potencial_perdida"] > 0)
    ]
    alertas = pd.concat([sem_estoque, em_risco]).drop_duplicates(
        subset="sku"
    ).sort_values("dias_estoque", ascending=True)

    linhas = []
    for _, produto in alertas.head(8).iterrows():
        status = str(produto["status_estoque"])
        classe = (
            "mi-stock-alert-danger"
            if status in {"Sem estoque", "Crítico"}
            else "mi-stock-alert-warning"
        )
        cobertura = (
            "Sem giro"
            if produto["dias_estoque"] == float("inf")
            else f"{_numero(float(produto['dias_estoque']))} dias"
        )
        perda = float(produto["receita_potencial_perdida"])
        perda_html = (
            formatar_moeda_br(perda)
            if perda > 0
            else "—"
        )
        linhas.append(
            f"""
            <div class="mi-stock-alert-row">
                <div class="mi-stock-alert-product">
                    <strong>{escape(str(produto['produto']))}</strong>
                    <span>SKU {escape(str(produto['sku']))}</span>
                </div>
                <span class="mi-stock-alert-state {classe}">
                    {escape(status)}
                </span>
                <span>{_numero(float(produto['estoque_atual']), 0)} un.</span>
                <span>{cobertura}</span>
                <strong>{perda_html}</strong>
            </div>
            """
        )

    resumo_perda = (
        f"{len(sem_estoque_com_perda)} produtos · "
        f"{formatar_moeda_br(float(sem_estoque_com_perda['receita_potencial_perdida'].sum()))}"
        if not sem_estoque_com_perda.empty
        else "Nenhuma venda potencial perdida estimada neste período."
    )
    estado_vazio = (
        '<div class="mi-stock-empty-state">'
        f'{icone_svg("check-circle", tamanho=16)}'
        "Sem produtos em risco de ruptura neste período."
        "</div>"
        if not linhas
        else ""
    )
    html_linhas = "".join(linhas)

    with st.container(border=True):
        st.html(
            f"""
            <div class="mi-chart-heading mi-dashboard-panel">
                <div class="mi-chart-title">Alertas de estoque</div>
                <div class="mi-chart-subtitle">
                    Ruptura e venda potencial perdida · {escape(resumo_perda)}
                </div>
            </div>
            <div class="mi-stock-alert-header">
                <span>Produto · SKU</span>
                <span>Status</span>
                <span>Estoque</span>
                <span>Cobertura</span>
                <span>Venda perdida</span>
            </div>
            <div class="mi-stock-alert-list">
                {html_linhas}{estado_vazio}
            </div>
            """
        )


def _renderizar_estoque_parado(estoque_parado: pd.DataFrame) -> None:
    linhas = []
    for _, produto in estoque_parado.sort_values(
        "valor_estoque",
        ascending=False,
    ).head(8).iterrows():
        cobertura = (
            "Sem giro"
            if produto["dias_estoque"] == float("inf")
            else f"{_numero(float(produto['dias_estoque']))} dias"
        )
        linhas.append(
            f"""
            <div class="mi-stock-idle-row">
                <div class="mi-stock-idle-product">
                    <strong>{escape(str(produto['produto']))}</strong>
                    <span>SKU {escape(str(produto['sku']))}</span>
                </div>
                <span>{_numero(float(produto['estoque_atual']), 0)} un.</span>
                <span>{_numero(float(produto['media_vendas_dia']), 2)}</span>
                <span>{cobertura}</span>
                <strong>{formatar_moeda_br(produto['valor_estoque'])}</strong>
            </div>
            """
        )
    conteudo = (
        "".join(linhas)
        if linhas
        else (
            '<div class="mi-stock-empty-state">'
            f'{icone_svg("check-circle", tamanho=16)}'
            "Nenhum produto atende ao critério de estoque parado."
            "</div>"
        )
    )
    with st.container(border=True):
        st.html(
            f"""
            <div class="mi-chart-heading mi-dashboard-panel">
                <div class="mi-chart-title">Estoque parado</div>
                <div class="mi-chart-subtitle">
                    Sem giro ou com mais de 45 dias de cobertura
                </div>
            </div>
            <div class="mi-stock-idle-header">
                <span>Produto · SKU</span>
                <span>Estoque</span>
                <span>Vendas/dia</span>
                <span>Cobertura</span>
                <span>Capital parado</span>
            </div>
            <div class="mi-stock-idle-list">{conteudo}</div>
            """
        )


def mostrar_estoque(estoque: pd.DataFrame) -> None:
    titulo_secao(
        "Estoque",
        "Disponibilidade, risco de ruptura e capital imobilizado.",
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
    valor_total = float(estoque["valor_estoque"].sum())
    unidades = float(estoque["estoque_atual"].sum())

    indicadores = [
        (
            "Valor em estoque",
            formatar_moeda_br(valor_total),
            "chart-coins",
            "Valor das unidades disponíveis ao custo cadastrado.",
            "normal",
        ),
        (
            "Unidades disponíveis",
            _numero(unidades, 0),
            "package",
            "Soma das unidades atualmente disponíveis.",
            "normal",
        ),
        (
            "Risco de ruptura",
            f"{len(produtos_em_risco)} produtos"
            if not produtos_em_risco.empty
            else "Tudo certo",
            "target" if not produtos_em_risco.empty else "check-circle",
            "Produtos com estoque positivo e até 15 dias de cobertura.",
            "negative" if not produtos_em_risco.empty else "positive",
        ),
        (
            "Sem estoque",
            f"{len(sem_estoque)} produtos"
            if not sem_estoque.empty
            else "Tudo certo",
            "package" if not sem_estoque.empty else "check-circle",
            "Produtos cuja quantidade disponível é zero.",
            "negative" if not sem_estoque.empty else "positive",
        ),
        (
            "Capital parado",
            formatar_moeda_br(capital_parado),
            "chart-average",
            "Produtos sem venda ou com mais de 45 dias de cobertura.",
            "neutral" if capital_parado > 0 else "positive",
        ),
    ]
    for coluna, (rotulo, valor, icone, contexto, semantica) in zip(
        st.columns(5, gap="small"),
        indicadores,
    ):
        with coluna:
            card(
                rotulo,
                valor,
                icone,
                contexto,
                tipo=semantica,
                peso="operacional",
                cor_valor=(
                    semantica
                    if semantica in {"positive", "negative", "neutral"}
                    else "normal"
                ),
                tooltip=contexto,
            )

    with st.expander(
        "Sobre o saldo importado e as estimativas",
        icon=":material/info:",
        expanded=False,
    ):
        st.caption(
            "O saldo importado prevalece por marketplace. Sem filtro de "
            "marketplace, os saldos importados são somados; produtos sem "
            "saldo importado continuam com a estimativa calculada pelo "
            "cadastro e pelas vendas. Capital parado considera produtos "
            "com estoque e sem vendas no período ou mais de 45 dias de "
            "cobertura. A venda potencial perdida é estimada pelo giro "
            "médio e pelo estoque inicial cadastrado; sem histórico diário "
            "de saldo, não confirma quando a ruptura ocorreu."
        )

    _renderizar_alertas(estoque)
    _renderizar_estoque_parado(estoque_parado)
