import streamlit as st


def mostrar_insights(periodo, card):

    st.divider()

    st.subheader(
        "🧠 Insights da operação"
    )

    if periodo.empty:
        st.info(
            "Não há vendas para o produto, marketplace e período "
            "selecionados."
        )
        return

    melhor_dia = periodo.loc[
        periodo["faturamento"].idxmax()
    ]


    pior_dia = periodo.loc[
        periodo["faturamento"].idxmin()
    ]


    media_diaria = periodo["faturamento"].mean()


    i1, i2, i3 = st.columns(3)


    with i1:

        card(
            "Melhor dia de vendas",
            melhor_dia["data"].strftime("%d/%m/%Y"),
            "📈",
            f"R$ {melhor_dia['faturamento']:,.2f}"
        )


    with i2:

        card(
            "Menor faturamento",
            pior_dia["data"].strftime("%d/%m/%Y"),
            "📉",
            f"R$ {pior_dia['faturamento']:,.2f}"
        )


    with i3:

        card(
            "Média diária",
            f"R$ {media_diaria:,.2f}",
            "📊",
            "Faturamento médio"
        )