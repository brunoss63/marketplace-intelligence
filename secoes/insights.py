import pandas as pd
import streamlit as st

from componentes import renderizar_card_insight


_DIAS_SEMANA = (
    "segunda",
    "terça",
    "quarta",
    "quinta",
    "sexta",
    "sábado",
    "domingo",
)


def _moeda_br(valor: float) -> str:
    return (
        f"R$ {valor:,.2f}"
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )


def _contexto_data(data: pd.Timestamp) -> str:
    return (
        f"{_DIAS_SEMANA[data.weekday()]}, "
        f"{data.day:02d}/{data.month:02d}"
    )


def mostrar_insights(periodo: pd.DataFrame, pedidos_periodo: pd.DataFrame) -> None:
    st.divider()
    st.markdown(
        """
        <div class="mi-chart-heading">
            <div class="mi-chart-title">Insights da operação</div>
            <div class="mi-chart-subtitle">
                Destaques do período selecionado
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if periodo.empty:
        st.info(
            "Não há vendas para o produto, marketplace e período "
            "selecionados."
        )
        return

    melhor_dia = periodo.loc[periodo["faturamento"].idxmax()]
    pior_dia = periodo.loc[periodo["faturamento"].idxmin()]
    media_diaria = float(periodo["faturamento"].mean())

    contexto_melhor_dia = _contexto_data(pd.Timestamp(melhor_dia["data"]))
    if media_diaria > 0:
        proporcao_media = float(melhor_dia["faturamento"]) / media_diaria
        fator_media = f"{proporcao_media:.1f}".replace(".", ",")
        contexto_melhor_dia += f" · {fator_media}x a média diária"

    contexto_pior_dia = _contexto_data(pd.Timestamp(pior_dia["data"]))
    dias_sem_vendas = int(periodo["faturamento"].eq(0).sum())

    insights = [
        (
            "Melhor dia de vendas",
            _moeda_br(float(melhor_dia["faturamento"])),
            contexto_melhor_dia,
            "trophy",
            "positive",
        ),
        (
            "Dias sem vendas" if dias_sem_vendas else "Menor faturamento",
            (
                f"{dias_sem_vendas} "
                f"{'dia' if dias_sem_vendas == 1 else 'dias'}"
                if dias_sem_vendas
                else _moeda_br(float(pior_dia["faturamento"]))
            ),
            (
                "No período selecionado"
                if dias_sem_vendas
                else contexto_pior_dia
            ),
            "chart-down",
            "negative" if dias_sem_vendas else "neutral",
        ),
        (
            "Média diária",
            _moeda_br(media_diaria),
            "Faturamento médio por dia",
            "chart-average",
            "neutral",
        ),
    ]

    if not pedidos_periodo.empty and "produto" in pedidos_periodo:
        resumo_produtos = (
            pedidos_periodo
            .groupby("produto")
            .agg(
                receita=("faturamento_bruto", "sum"),
                unidades=("quantidade", "sum"),
            )
            .sort_values("receita", ascending=False)
        )
        if not resumo_produtos.empty:
            produto_lider = str(resumo_produtos.index[0])
            produto_unidades = int(resumo_produtos.iloc[0]["unidades"])
            insights.append(
                (
                    "Produto campeão por receita",
                    _moeda_br(float(resumo_produtos.iloc[0]["receita"])),
                    f"{produto_lider} · {produto_unidades} un.",
                    "trophy",
                    "positive",
                )
            )

    colunas = st.columns(len(insights), gap="small")
    for coluna, insight in zip(colunas, insights):
        with coluna:
            renderizar_card_insight(*insight[:4], variante=insight[4])
