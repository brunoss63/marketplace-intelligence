import datetime
import unittest

from componentes import (
    PALETA_DADOS,
    PALETA_MARKETPLACES,
    badge_html,
    icone_svg,
)
from componentes import texto_status_conexoes
from autenticacao import _nome_exibicao


class TestDesignSystem(unittest.TestCase):
    def test_icones_svg_usam_estilo_line_consistente(self) -> None:
        nomes = {
            "chart-coins",
            "chart-pie",
            "chart-up",
            "chart-average",
            "chart-down",
            "file-text",
            "megaphone",
            "package",
            "shopping-bag",
            "target",
            "trophy",
        }

        for nome in nomes:
            with self.subTest(nome=nome):
                svg = icone_svg(nome)
                self.assertIn('viewBox="0 0 24 24"', svg)
                self.assertIn('stroke="currentColor"', svg)
                self.assertIn('aria-hidden="true"', svg)

    def test_icone_desconhecido_e_rejeitado(self) -> None:
        with self.assertRaisesRegex(ValueError, "Ícone não registrado"):
            icone_svg("nao-existe")

    def test_badge_escapa_texto_e_valida_variante(self) -> None:
        badge = badge_html("<Conta>", "success")

        self.assertIn("&lt;Conta&gt;", badge)
        self.assertIn("mi-badge-success", badge)
        with self.assertRaisesRegex(ValueError, "Variante de badge"):
            badge_html("Conta", "custom")

    def test_paleta_de_dados_tem_cores_unicas(self) -> None:
        self.assertGreaterEqual(len(PALETA_DADOS), 5)
        self.assertEqual(len(PALETA_DADOS), len(set(PALETA_DADOS)))
        self.assertTrue(all(cor.startswith("#") for cor in PALETA_DADOS))

    def test_paleta_de_marketplaces_usa_cores_do_design_system(self) -> None:
        self.assertEqual(PALETA_MARKETPLACES["Mercado Livre"], PALETA_DADOS[0])
        self.assertEqual(PALETA_MARKETPLACES["Shopee"], PALETA_DADOS[1])

    def test_status_de_conexoes_nao_confunde_indisponivel_com_zero(self) -> None:
        self.assertEqual(
            texto_status_conexoes(None),
            "Conexões indisponíveis neste ambiente",
        )
        self.assertEqual(
            texto_status_conexoes([]),
            "Nenhum marketplace conectado",
        )
        self.assertEqual(
            texto_status_conexoes(["Shopee"]),
            "1 marketplace conectado",
        )
        self.assertEqual(
            texto_status_conexoes(["Mercado Livre", "Shopee"]),
            "2 marketplaces conectados",
        )

    def test_nome_de_conta_prioriza_metadados_e_tem_fallback(self) -> None:
        class Usuario:
            user_metadata = {"full_name": "Bruno Silva"}

        self.assertEqual(_nome_exibicao(Usuario(), "bruno@example.com"), "Bruno Silva")
        self.assertEqual(_nome_exibicao(object(), "bruno.silva@example.com"), "Bruno Silva")
        self.assertEqual(_nome_exibicao(object(), ""), "Conta")

    def test_cabecalho_pagina_renderiza_componente_html_nativo(self) -> None:
        from streamlit.testing.v1 import AppTest

        source = (
            "from componentes import cabecalho_pagina\n"
            "cabecalho_pagina("
            "'Visão Geral', 'Panorama executivo', '◫', "
            "contexto='Período analisado · 01/09/2026 – 30/09/2026')\n"
        )
        app = AppTest.from_string(source).run()

        self.assertFalse(app.exception)
        self.assertEqual(len(app.get("html")), 1)
        self.assertEqual(len(app.markdown), 0)
        html = app.get("html")[0].value
        self.assertIn("Panorama executivo", html)
        self.assertIn("Período analisado", html)
        self.assertEqual(html.count("<div"), html.count("</div>"))

    def test_card_de_participacao_renderiza_html_em_vez_de_bloco_de_codigo(self) -> None:
        from streamlit.testing.v1 import AppTest

        app = AppTest.from_string(
            "from componentes import ("
            "LinhaParticipacaoCanal, renderizar_card_participacao_canal)\n"
            "renderizar_card_participacao_canal('Faturamento', ["
            "LinhaParticipacaoCanal("
            "'Mercado Livre', 'R$ 1.099,50', 100.0, '#73A9FF')])\n"
        ).run()

        self.assertFalse(app.exception)
        self.assertEqual(len(app.get("html")), 1)
        self.assertEqual(len(app.get("code")), 0)
        self.assertIn("<section class=", app.get("html")[0].value)
        self.assertIn("R$ 1.099,50", app.get("html")[0].value)

    def test_perfil_da_sidebar_tem_logout_direto_sem_popover(self) -> None:
        from streamlit.testing.v1 import AppTest

        app = AppTest.from_string(
            "from componentes import renderizar_perfil_sidebar\n"
            "renderizar_perfil_sidebar('Bruno Silva')\n"
        ).run()

        self.assertFalse(app.exception)
        self.assertEqual(len(app.get("popover")), 0)
        self.assertEqual([botao.label for botao in app.button], ["Sair"])

    def test_skeleton_renderiza_placeholders_de_kpis_e_graficos(self) -> None:
        from streamlit.testing.v1 import AppTest

        app = AppTest.from_string(
            "from componentes import renderizar_skeleton_dashboard\n"
            "renderizar_skeleton_dashboard()\n"
        ).run()

        self.assertFalse(app.exception)
        conteudo = "\n".join(element.value for element in app.markdown)
        self.assertIn("mi-skeleton-kpi", conteudo)
        self.assertIn("mi-skeleton-chart", conteudo)

    def test_login_tem_botao_aviso_discreto_e_luz_ambiente(self) -> None:
        from streamlit.testing.v1 import AppTest

        app = AppTest.from_string(
            "from componentes import aplicar_estilo, renderizar_aviso_login\n"
            "aplicar_estilo()\n"
            "renderizar_aviso_login("
            "'Sua sessão expirou. Entre novamente para continuar.')\n"
        ).run(timeout=15)

        self.assertFalse(app.exception)
        conteudo = "\n".join(item.value for item in app.get("markdown"))
        self.assertIn(".mi-login-notice", conteudo)
        self.assertIn("rgba(23, 38, 59, .62)", conteudo)
        self.assertIn(".st-key-mi_login_submit", conteudo)
        self.assertIn(".st-key-mi_password_recovery_submit", conteudo)
        self.assertIn("min-height: 560px", conteudo)
        self.assertIn("max-width: 1040px", conteudo)
        self.assertIn("#234F89", conteudo)
        self.assertIn("#3B75B6", conteudo)
        self.assertIn("rgba(66, 119, 180, .18)", conteudo)
        self.assertIn(".mi-login-story::before", conteudo)
        self.assertIn(".mi-login-story::after", conteudo)
        self.assertIn("mi-login-smoke-drift", conteudo)
        self.assertIn("mi-login-smoke-bloom", conteudo)
        self.assertIn("prefers-reduced-motion: reduce", conteudo)
        self.assertIn("Sessão encerrada", conteudo)
        self.assertIn("Sua sessão expirou.", conteudo)
        self.assertIn("role=\"status\"", conteudo)

    def test_sidebar_oculta_overflow_horizontal_e_usa_fundo_uniforme(self) -> None:
        from streamlit.testing.v1 import AppTest

        app = AppTest.from_string(
            "from componentes import aplicar_estilo\n"
            "aplicar_estilo()\n"
        ).run(timeout=15)

        self.assertFalse(app.exception)
        estilos = "\n".join(item.value for item in app.get("markdown"))
        self.assertIn("section[data-testid=\"stSidebar\"]", estilos)
        self.assertIn("overflow-x: hidden", estilos)
        self.assertIn(".st-key-mi-sidebar-footer", estilos)
        self.assertIn("background: transparent", estilos)
        self.assertIn("box-shadow: none", estilos)
        self.assertIn(".st-key-mi_logout_sidebar", estilos)
        self.assertIn(".st-key-mi-page-content [data-testid=\"stSpinner\"]", estilos)
        self.assertIn(
            'a[data-testid="stSidebarNavLink"]:not([aria-current="page"]):hover',
            estilos,
        )
        self.assertIn("rgba(68, 112, 171, .16)", estilos)
        self.assertIn("translateX(2px)", estilos)
        self.assertIn("prefers-reduced-motion: reduce", estilos)

    def test_kpi_principal_tem_layout_compacto_e_cor_semantica(self) -> None:
        from streamlit.testing.v1 import AppTest

        app = AppTest.from_string(
            "from componentes import card\n"
            "card('Resultado', 'R$ 125,00', 'chart-up', "
            "'↗ +18,4% vs período anterior', 'positive', "
            "peso='principal', sparkline=[10, 12, 9], "
            "cor_valor='negative')\n"
        ).run()

        self.assertFalse(app.exception)
        html = "\n".join(item.value for item in app.get("html"))
        self.assertIn("mi-card-principal", html)
        self.assertIn("mi-card-value-negative", html)
        self.assertIn("height: 112px", html)
        self.assertIn("overflow: visible", html)
        self.assertIn(".mi-card-tooltip", html)
        self.assertIn("z-index: 80", html)
        self.assertIn("mi-card-sparkline", html)
        self.assertIn("vs período anterior", html)

    def test_card_insight_tem_valor_dominante_e_contexto_legivel(self) -> None:
        from streamlit.testing.v1 import AppTest

        app = AppTest.from_string(
            "from componentes import renderizar_card_insight\n"
            "renderizar_card_insight("
            "'Melhor dia', 'R$ 213,94', "
            "'terça, 22/09 · 3,9x a média diária', "
            "'trophy', variante='positive')\n"
        ).run(timeout=15)

        self.assertFalse(app.exception)
        html = "\n".join(item.value for item in app.get("html"))
        self.assertIn("mi-insight-positive", html)
        self.assertIn("R$ 213,94", html)
        self.assertIn("terça, 22/09", html)

    def test_animacao_de_entrada_nao_reinicia_em_reruns_da_pagina(self) -> None:
        from streamlit.testing.v1 import AppTest

        app = AppTest.from_string(
            "import datetime\n"
            "import streamlit as st\n"
            "from componentes import ("
            "animar_pagina, card, renderizar_animacoes_entrada_pagina)\n"
            "animar_pagina('visao_geral')\n"
            "renderizar_animacoes_entrada_pagina()\n"
            "st.date_input('Data', value=datetime.date(2026, 9, 15))\n"
            "produto = st.selectbox('Produto', ['Todos', 'Produto B'])\n"
            "st.selectbox('Marketplace', ['Todos', 'Shopee'])\n"
            "valor = 'R$ 1.099,50' if produto == 'Todos' else 'R$ 213,94'\n"
            "card('Faturamento', valor, 'chart-coins', "
            "peso='principal')\n"
        ).run(timeout=15)

        self.assertFalse(app.exception)
        primeiro_html = "\n".join(item.value for item in app.get("html"))
        self.assertIn("mi-entry-card", primeiro_html)
        self.assertIn('data-mi-final="R$ 1.099,50"', primeiro_html)
        self.assertIn('style="visibility:hidden"', primeiro_html)
        self.assertIn(".mi-count-final", primeiro_html)
        self.assertIn('class="mi-count-final" aria-hidden="true" style="display:none!important"', primeiro_html)
        self.assertIn("1099.5", primeiro_html)

        app.date_input[0].set_value(datetime.date(2026, 9, 16))
        app.selectbox[0].select("Produto B")
        app.selectbox[1].select("Shopee")
        app.run(timeout=15)
        segundo_html = "\n".join(item.value for item in app.get("html"))
        self.assertNotIn("mi-entry-card", segundo_html)
        self.assertIn("R$ 213,94", segundo_html)

    def test_insights_formatam_valores_e_contam_dias_sem_vendas(self) -> None:
        from streamlit.testing.v1 import AppTest

        app = AppTest.from_string(
            "import pandas as pd\n"
            "from secoes.insights import mostrar_insights\n"
            "periodo = pd.DataFrame({"
            "'data': pd.to_datetime(['2026-09-22', '2026-09-23', '2026-09-24']),"
            "'faturamento': [50.0, 0.0, 100.0]})\n"
            "pedidos = pd.DataFrame({"
            "'produto': ['Produto A', 'Produto B'],"
            "'faturamento_bruto': [50.0, 100.0],"
            "'quantidade': [1, 4]})\n"
            "mostrar_insights(periodo, pedidos)\n"
        ).run(timeout=15)

        self.assertFalse(app.exception)
        html = "\n".join(item.value for item in app.get("html"))
        self.assertIn("Dias sem vendas", html)
        self.assertIn("1 dia", html)
        self.assertIn("R$ 100,00", html)
        self.assertIn("quinta, 24/09", html)
        self.assertIn("Produto campeão por receita", html)
        self.assertIn("Produto B · 4 un.", html)
        self.assertNotIn("R$ 100.00", html)

    def test_animacao_de_pagina_fica_limitada_ao_conteudo(self) -> None:
        from streamlit.testing.v1 import AppTest

        app = AppTest.from_string(
            "import streamlit as st\n"
            "from componentes import animar_pagina\n"
            "animar_pagina('visao-geral')\n"
            "st.write(st.session_state['_mi_page_entering'])\n"
        ).run(timeout=15)

        self.assertFalse(app.exception)
        html = "\n".join(item.value for item in app.get("html"))
        self.assertNotIn(".stAppViewContainer", html)
        self.assertIn(".st-key-mi-page-content", html)
        self.assertIn("mi-page-content-enter", html)
        self.assertTrue(app.session_state["_mi_page_entering"])

        app.run(timeout=15)
        self.assertFalse(app.exception)
        self.assertFalse(app.session_state["_mi_page_entering"])
        segundo_html = "\n".join(item.value for item in app.get("html"))
        self.assertNotIn("mi-page-content-enter", segundo_html)

    def test_grafico_minimal_usa_preenchimento_gradiente(self) -> None:
        from streamlit.testing.v1 import AppTest

        app = AppTest.from_string(
            "import plotly.graph_objects as go\n"
            "from componentes import ("
            "animar_pagina, grafico_dashboard, "
            "renderizar_animacoes_entrada_pagina)\n"
            "animar_pagina('visao_geral')\n"
            "renderizar_animacoes_entrada_pagina()\n"
            "fig = go.Figure(go.Scatter("
            "x=['2026-09-16', '2026-09-17', '2026-09-18'], y=[1, 5, 7], "
            "mode='lines', line={'color': '#73A9FF'}))\n"
            "grafico_dashboard(fig, titulo='Evolução', "
            "visual_minimal=True, linha_suave=True, "
            "apenas_exportar=True, respiro_eixo_y=True, "
            "eixo_y_inteiro=True)\n"
            "assert fig.layout.yaxis.range[0] < 0\n"
            "assert list(fig.layout.yaxis.tickvals) == [0, 2, 4, 6, 8]\n"
            "assert fig.layout.height >= 300\n"
            "assert fig.data[0].mode == 'lines+markers'\n"
            "assert fig.layout.xaxis.unifiedhovertitle.text == "
            "'<b>%{x|%d/%m}</b>'\n"
        ).run(timeout=15)

        self.assertFalse(app.exception)
        self.assertEqual(len(app.get("plotly_chart")), 1)
        html = "\n".join(item.value for item in app.get("html"))
        self.assertIn(".mi-entry-chart", html)
        self.assertIn("visibility: hidden", html)
        self.assertIn("new MutationObserver(processarElementos)", html)
        self.assertIn("mi-chart-minimal", "\n".join(
            item.value for item in app.markdown
        ))


if __name__ == "__main__":
    unittest.main()
