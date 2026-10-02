import streamlit as st
import pandas as pd
import plotly.express as px


# =========================================================
# CONFIGURAÇÃO
# =========================================================

st.set_page_config(
    page_title="Marketplace Analytics",
    page_icon="🏍️",
    layout="wide"
)


# =========================================================
# FUNÇÕES DE FORMATAÇÃO
# =========================================================

def moeda(valor):
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def numero(valor):
    return f"{int(valor):,}".replace(",", ".")


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


linha = indicadores.iloc[0]


# =========================================================
# CABEÇALHO
# =========================================================

st.title("🏍️ Marketplace Analytics")

st.caption(
    "Visão de desempenho da operação digital | Setembro/2026"
)


st.divider()


# =========================================================
# CARDS PRINCIPAIS
# =========================================================

st.subheader("Resumo da operação")


col1, col2, col3, col4 = st.columns(4)


with col1:
    st.metric(
        "💰 Faturamento",
        moeda(linha["faturamento"])
    )


with col2:
    st.metric(
        "📦 Pedidos",
        numero(linha["pedidos"])
    )


with col3:
    st.metric(
        "📈 Resultado",
        moeda(linha["resultado"])
    )


with col4:
    st.metric(
        "🎯 Margem",
        f"{linha['margem']:.1f}%"
    )


# =========================================================
# INFORMAÇÕES COMPLEMENTARES
# =========================================================

col1, col2 = st.columns(2)


with col1:

    st.info(
        f"""
        **Ticket médio**

        {moeda(linha['ticket_medio'])}
        """
    )


with col2:

    st.info(
        f"""
        **Retorno sobre publicidade (ROAS)**

        {linha['roas']:.2f}x
        """
    )


# =========================================================
# EVOLUÇÃO
# =========================================================

st.divider()

st.subheader(
    "📊 Evolução de faturamento"
)


periodo["data"] = pd.to_datetime(
    periodo["data"]
)


grafico_faturamento = px.line(
    periodo,
    x="data",
    y="faturamento",
    markers=True
)


grafico_faturamento.update_layout(
    height=400
)


st.plotly_chart(
    grafico_faturamento,
    use_container_width=True
)


# =========================================================
# MARKETPLACES
# =========================================================

st.divider()

st.subheader(
    "🛒 Canais de venda"
)


col_a, col_b = st.columns(2)


with col_a:

    grafico_marketplace = px.bar(
        marketplaces,
        x="marketplace",
        y="faturamento"
    )


    st.plotly_chart(
        grafico_marketplace,
        use_container_width=True
    )


with col_b:

    grafico_resultado = px.pie(
        marketplaces,
        names="marketplace",
        values="resultado"
    )


    st.plotly_chart(
        grafico_resultado,
        use_container_width=True
    )


# =========================================================
# ESTOQUE
# =========================================================

st.divider()

st.subheader(
    "🚨 Produtos que precisam de atenção"
)


criticos = estoque[
    estoque["status_estoque"] == "Crítico"
]


if len(criticos) > 0:

    st.warning(
        f"{len(criticos)} produtos com estoque crítico."
    )


    tabela = criticos[
        [
            "produto",
            "estoque_atual",
            "dias_estoque",
            "status_estoque"
        ]
    ].copy()


    tabela.columns = [
        "Produto",
        "Estoque Atual",
        "Dias de Estoque",
        "Situação"
    ]


    st.dataframe(
        tabela,
        hide_index=True,
        use_container_width=True
    )


else:

    st.success(
        "Nenhum produto crítico."
    )