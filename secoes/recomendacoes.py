import streamlit as st
from componentes import hero
from dados_periodo import obter_analise_estoque, obter_desempenho_produtos

def mostrar_recomendacoes(data_inicio, data_fim):

    # =========================
    # DADOS
    # =========================

    produtos = obter_desempenho_produtos(data_inicio, data_fim)
    estoque = obter_analise_estoque(data_inicio, data_fim)

    # =========================
    # ANÁLISES
    # =========================

    sem_estoque = estoque[
    estoque["estoque_atual"] <= 0
    ].copy()

    estoque_critico = estoque[
    (estoque["estoque_atual"] > 0) &
    (estoque["dias_estoque"] <= 7)
    ].copy()

    estoque_critico = estoque_critico.sort_values(
    "dias_estoque",
    ascending=True
    )

    mediana_faturamento = produtos["faturamento"].median()

    oportunidades = produtos[
    (produtos["faturamento"] > mediana_faturamento) &
    (produtos["roas"] == 0)
    ].copy()

    oportunidades = oportunidades.sort_values(
    "faturamento",
    ascending=False
    )

    # =========================
    # INDICADORES
    # =========================

    total_sem_estoque = len(sem_estoque)
    total_estoque_critico = len(estoque_critico)
    total_oportunidades = len(oportunidades)

    total_pontos = (
    total_sem_estoque +
    total_estoque_critico +
    total_oportunidades
    )

    # =========================
    # HERO
    # =========================

    hero(
    "Centro de Inteligência",
    (
        f"{data_inicio.strftime('%d/%m/%Y')} → "
        f"{data_fim.strftime('%d/%m/%Y')}"
    ),
    total_sem_estoque,
    total_estoque_critico,
    total_oportunidades,
    total_pontos,
    "Ações imediatas",
    "Pontos de atenção",
    "Oportunidades",
    "Pontos identificados"
    )

    # =========================
    # ESTILO DOS CARDS
    # =========================

    st.markdown(
    """
    <style>

    .mi-recommendation-card {

        position: relative;

        overflow: hidden;

        transition:
            transform 220ms ease,
            box-shadow 220ms ease,
            border-color 220ms ease,
            background 220ms ease;

    }

    .mi-recommendation-card [style*="font-size:10px"] {
        font-size: 12px !important;
    }

    .mi-recommendation-card [style*="font-size:11px"] {
        font-size: 13px !important;
    }

    .mi-recommendation-card [style*="font-size:12px"] {
        font-size: 14px !important;
    }

    .mi-recommendation-card [style*="font-size:13px"] {
        font-size: 15px !important;
    }

    .mi-recommendation-card [style*="font-size:14px"] {
        font-size: 16px !important;
    }

    .mi-recommendation-card [style*="font-size:17px"] {
        font-size: 19px !important;
    }

    .mi-recommendation-card [style*="font-size:18px"] {
        font-size: 20px !important;
    }


    .mi-recommendation-card:hover {

        transform:
            translateY(-5px)
            scale(1.005);

        box-shadow:
            0 18px 38px rgba(0,0,0,0.38);

        background:
            linear-gradient(
                145deg,
                #26364D,
                #141D2D
            );

    }


    .mi-recommendation-glow {

        position: absolute;

        width: 180px;
        height: 180px;

        right: -90px;
        top: -90px;

        pointer-events: none;

        opacity: 0;

        transition:
            opacity 250ms ease,
            transform 400ms ease;

    }


    .mi-recommendation-card:hover
    .mi-recommendation-glow {

        opacity: 1;

        transform:
            scale(1.3);

    }


    .mi-recommendation-glow-red {

        background:
            radial-gradient(
                circle,
                rgba(239,68,68,0.18),
                transparent 70%
            );

    }


    .mi-recommendation-glow-orange {

        background:
            radial-gradient(
                circle,
                rgba(245,158,11,0.18),
                transparent 70%
            );

    }


    .mi-recommendation-glow-blue {

        background:
            radial-gradient(
                circle,
                rgba(59,130,246,0.18),
                transparent 70%
            );

    }

    </style>
    """,
    unsafe_allow_html=True
    )

    # =========================
    # AÇÕES IMEDIATAS
    # =========================

    if total_sem_estoque > 0:

        st.markdown("### 🔴 Ações imediatas")

        col1, col2 = st.columns(2, gap="large")

        for index, (_, produto) in enumerate(
            sem_estoque.iterrows()
        ):

            coluna = col1 if index % 2 == 0 else col2

            with coluna:

                st.html(
                    f"""
                    <div class="mi-recommendation-card" style="
                        background:linear-gradient(
                            145deg,
                            #1E293B,
                            #111827
                        );
                        padding:18px 20px;
                        border-radius:16px;
                        border-left:4px solid #EF4444;
                        border-top:1px solid rgba(255,255,255,0.06);
                        border-right:1px solid rgba(255,255,255,0.06);
                        border-bottom:1px solid rgba(255,255,255,0.06);
                        margin-bottom:14px;
                        box-sizing:border-box;
                    ">

                        <div class="mi-recommendation-glow mi-recommendation-glow-red"></div>

                        <div style="
                            position:relative;
                            z-index:1;
                        ">

                            <div style="
                                color:#EF4444;
                                font-size:11px;
                                font-weight:700;
                                text-transform:uppercase;
                                letter-spacing:0.5px;
                                margin-bottom:7px;
                            ">
                                ESTOQUE CRÍTICO
                            </div>

                            <div style="
                                color:white;
                                font-size:17px;
                                font-weight:700;
                                margin-bottom:5px;
                            ">
                                {produto["produto"]}
                            </div>

                            <div style="
                                color:#94A3B8;
                                font-size:12px;
                                margin-bottom:14px;
                            ">
                                Produto indisponível para novas vendas
                            </div>

                            <div style="
                                display:flex;
                                justify-content:space-between;
                                align-items:center;
                                gap:12px;
                            ">

                                <div>
                                    <div style="
                                        color:#64748B;
                                        font-size:10px;
                                    ">
                                        Situação
                                    </div>

                                    <div style="
                                        color:#EF4444;
                                        font-size:14px;
                                        font-weight:700;
                                        margin-top:2px;
                                    ">
                                        0 unidades
                                    </div>
                                </div>

                                <div style="
                                    color:#CBD5E1;
                                    font-size:12px;
                                    font-weight:600;
                                ">
                                    → Priorizar reposição
                                </div>

                            </div>

                        </div>

                    </div>
                    """
                )

        # =========================
        # PONTOS DE ATENÇÃO
        # =========================

        if total_estoque_critico > 0:

            st.markdown("### 🟠 Pontos de atenção")

            col1, col2 = st.columns(2, gap="large")

            for index, (_, produto) in enumerate(
                estoque_critico.iterrows()
            ):

                coluna = col1 if index % 2 == 0 else col2

                with coluna:

                    st.html(
                        f"""
                        <div class="mi-recommendation-card" style="
                            background:linear-gradient(
                                145deg,
                                #1E293B,
                                #111827
                            );
                            padding:18px 20px;
                            border-radius:16px;
                            border-left:4px solid #F59E0B;
                            border-top:1px solid rgba(255,255,255,0.06);
                            border-right:1px solid rgba(255,255,255,0.06);
                            border-bottom:1px solid rgba(255,255,255,0.06);
                            margin-bottom:14px;
                            box-sizing:border-box;
                        ">

                            <div class="mi-recommendation-glow mi-recommendation-glow-orange"></div>

                            <div style="
                                position:relative;
                                z-index:1;
                            ">

                                <div style="
                                    color:#F59E0B;
                                    font-size:11px;
                                    font-weight:700;
                                    text-transform:uppercase;
                                    letter-spacing:0.5px;
                                    margin-bottom:7px;
                                ">
                                    COBERTURA LIMITADA
                                </div>

                                <div style="
                                    color:white;
                                    font-size:17px;
                                    font-weight:700;
                                    margin-bottom:10px;
                                ">
                                    {produto["produto"]}
                                </div>

                                <div style="
                                    display:flex;
                                    justify-content:space-between;
                                    align-items:end;
                                    gap:12px;
                                ">

                                    <div>

                                        <div style="
                                            color:#64748B;
                                            font-size:10px;
                                        ">
                                            Estoque atual
                                        </div>

                                        <div style="
                                            color:white;
                                            font-size:18px;
                                            font-weight:700;
                                            margin-top:2px;
                                        ">
                                            {produto["estoque_atual"]:.0f}
                                        </div>

                                    </div>

                                    <div>

                                        <div style="
                                            color:#64748B;
                                            font-size:10px;
                                        ">
                                            Cobertura estimada
                                        </div>

                                        <div style="
                                            color:#F59E0B;
                                            font-size:18px;
                                            font-weight:700;
                                            margin-top:2px;
                                        ">
                                            {produto["dias_estoque"]:.1f} dias
                                        </div>

                                    </div>

                                    <div style="
                                        color:#CBD5E1;
                                        font-size:12px;
                                        font-weight:600;
                                        text-align:right;
                                    ">
                                        → Monitorar reposição
                                    </div>

                                </div>

                            </div>

                        </div>
                        """
                    )

            # =========================
            # OPORTUNIDADES
            # =========================

            if total_oportunidades > 0:

                st.markdown("### 🔵 Oportunidades")

                col1, col2 = st.columns(2, gap="large")

                for index, (_, produto) in enumerate(
                    oportunidades.iterrows()
                ):

                    coluna = col1 if index % 2 == 0 else col2

                    with coluna:

                        st.html(
                            f"""
                            <div class="mi-recommendation-card" style="
                                background:linear-gradient(
                                    145deg,
                                    #1E293B,
                                    #111827
                                );
                                padding:18px 20px;
                                border-radius:16px;
                                border-left:4px solid #3B82F6;
                                border-top:1px solid rgba(255,255,255,0.06);
                                border-right:1px solid rgba(255,255,255,0.06);
                                border-bottom:1px solid rgba(255,255,255,0.06);
                                margin-bottom:14px;
                                box-sizing:border-box;
                            ">

                                <div class="mi-recommendation-glow mi-recommendation-glow-blue"></div>

                                <div style="
                                    position:relative;
                                    z-index:1;
                                ">

                                    <div style="
                                        color:#3B82F6;
                                        font-size:11px;
                                        font-weight:700;
                                        text-transform:uppercase;
                                        letter-spacing:0.5px;
                                        margin-bottom:7px;
                                    ">
                                        OPORTUNIDADE
                                    </div>

                                    <div style="
                                        color:white;
                                        font-size:17px;
                                        font-weight:700;
                                        margin-bottom:10px;
                                    ">
                                        {produto["produto"]}
                                    </div>

                                    <div style="
                                        display:flex;
                                        justify-content:space-between;
                                        align-items:end;
                                        gap:12px;
                                    ">

                                        <div>

                                            <div style="
                                                color:#64748B;
                                                font-size:10px;
                                            ">
                                                Faturamento
                                            </div>

                                            <div style="
                                                color:white;
                                                font-size:18px;
                                                font-weight:700;
                                                margin-top:2px;
                                            ">
                                                R$ {produto["faturamento"]:,.0f}
                                            </div>

                                        </div>

                                        <div>

                                            <div style="
                                                color:#64748B;
                                                font-size:10px;
                                            ">
                                                Margem
                                            </div>

                                            <div style="
                                                color:#22C55E;
                                                font-size:18px;
                                                font-weight:700;
                                                margin-top:2px;
                                            ">
                                                {produto["margem"]:.1f}%
                                            </div>

                                        </div>

                                        <div style="
                                            color:#CBD5E1;
                                            font-size:12px;
                                            font-weight:600;
                                            text-align:right;
                                        ">
                                            → Avaliar campanha
                                        </div>

                                    </div>

                                </div>

                            </div>
                            """
                        )

                # =========================
                # LEITURA DA OPERAÇÃO
                # =========================

                st.divider()

                st.subheader("💡 Leitura da operação")

                mensagens = []

                if total_sem_estoque > 0:

                    mensagens.append(
                        f"{total_sem_estoque} produtos já atingiram ruptura de estoque."
                    )

                    if total_estoque_critico > 0:

                        mensagens.append(
                            f"{total_estoque_critico} produtos possuem cobertura estimada inferior a 7 dias."
                        )

                        if total_oportunidades > 0:

                            mensagens.append(
                                f"{total_oportunidades} produtos apresentam faturamento acima da mediana sem investimento publicitário identificado."
                            )

                            for mensagem in mensagens:

                                st.markdown(
                                    f"""
                                    <div style="
                                        background:#1E293B;
                                        padding:13px 16px;
                                        border-radius:12px;
                                        margin-bottom:8px;
                                        border:1px solid rgba(255,255,255,0.06);
                                        color:#CBD5E1;
                                        font-size:13px;
                                    ">
                                        • {mensagem}
                                    </div>
                                    """,
                                    unsafe_allow_html=True
                                )