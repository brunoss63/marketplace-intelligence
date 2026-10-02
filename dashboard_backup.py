import streamlit as st
import pandas as pd
import plotly.express as px


# =========================================================
# CONFIGURAÇÃO DA PÁGINA
# =========================================================

st.set_page_config(
    page_title="Dashboard Marketplace",
    layout="wide"
)


# =========================================================
# CARREGAR DADOS
# =========================================================

indicadores = pd.read_csv(
    "dados/indicadores.csv"
)

periodo = pd.read_csv(
    "dados/analise_periodo.csv"
)

marketplaces = pd.read_csv(
    "dados/desempenho_marketplaces.csv"
)

estoque = pd.read_csv(
    "dados/analise_estoque.csv"
)


# =========================================================
# TÍTULO
# =========================================================

st.title("📊 Dashboard Marketplace")

st.subheader(
    "Visão geral da operação"
)


# =========================================================
# INDICADORES PRINCIPAIS
# =========================================================

linha = indicadores.iloc[0]


col1, col2, col3, col4, col5, col6 = st.columns(6)


col1.metric(
    "Faturamento",
    f"R$ {linha['faturamento']:,.2f}"
)

col2.metric(
    "Pedidos",
    f"{linha['pedidos']:,}"
)

col3.metric(
    "Ticket Médio",
    f"R$ {linha['ticket_medio']:,.2f}"
)

col4.metric(
    "Resultado",
    f"R$ {linha['resultado']:,.2f}"
)

col5.metric(
    "Margem",
    f"{linha['margem']:.2f}%"
)

col6.metric(
    "ROAS",
    f"{linha['roas']:.2f}"
)


# =========================================================
# EVOLUÇÃO DE FATURAMENTO
# =========================================================

st.divider()

st.subheader(
    "Evolução de faturamento"
)

periodo["data"] = pd.to_datetime(
    periodo["data"]
)

grafico_faturamento = px.line(
    periodo,
    x="data",
    y="faturamento",
    markers=True,
    title="Faturamento diário"
)

st.plotly_chart(
    grafico_faturamento,
    use_container_width=True
)


# =========================================================
# MARKETPLACES
# =========================================================

st.divider()

col_a, col_b = st.columns(2)


with col_a:

    st.subheader(
        "Desempenho por marketplace"
    )

    grafico_marketplace = px.bar(
        marketplaces,
        x="marketplace",
        y="faturamento",
        title="Faturamento"
    )

    st.plotly_chart(
        grafico_marketplace,
        use_container_width=True
    )


with col_b:

    st.subheader(
        "Resultado por marketplace"
    )

    grafico_resultado = px.pie(
        marketplaces,
        names="marketplace",
        values="resultado",
        title="Distribuição do resultado"
    )

    st.plotly_chart(
        grafico_resultado,
        use_container_width=True
    )


# =========================================================
# ALERTAS DE ESTOQUE
# =========================================================

st.divider()

st.subheader(
    "🚨 Alertas de estoque"
)


criticos = estoque[
    estoque["status_estoque"] == "Crítico"
]


if len(criticos) > 0:

    st.warning(
        f"{len(criticos)} produtos precisam de atenção."
    )

    st.dataframe(
        criticos[
            [
                "produto",
                "estoque_atual",
                "dias_estoque",
                "status_estoque"
            ]
        ],
        hide_index=True
    )

else:

    st.success(
        "Nenhum produto crítico."
    )