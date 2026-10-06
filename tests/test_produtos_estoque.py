import unittest

import pandas as pd
from streamlit.testing.v1 import AppTest
from secoes.produtos import (
    _classificar_status_exibicao,
    _formatar_tabela,
    _preparar_catalogo,
)


def _dados_produto() -> tuple[pd.DataFrame, pd.DataFrame]:
    produtos = pd.DataFrame(
        [
            {
                "sku": "SKU-1",
                "produto": "Produto A",
                "categoria": "Casa",
                "canal": "Mercado Livre",
                "preco_venda": 100.0,
                "custo_unitario": 40.0,
                "pedidos": 2,
                "unidades": 3.0,
                "faturamento": 300.0,
                "descontos": 0.0,
                "taxas": 30.0,
                "frete": 10.0,
                "publicidade": 20.0,
                "resultado": -24.18,
                "margem": -10.1,
                "roas": 6.93,
                "participacao_faturamento": 100.0,
                "classificacao": "Atenção",
            },
        ]
    )
    estoque = pd.DataFrame(
        [
            {
                "sku": "SKU-1",
                "produto": "Produto A",
                "estoque_atual": 0.0,
                "media_vendas_dia": 0.35,
                "dias_estoque": 0.0,
                "ponto_reposicao": 1.75,
                "valor_estoque": 0.0,
                "status_estoque": "Sem estoque",
                "dias_sem_estoque_estimados": 2.0,
                "vendas_potenciais_perdidas": 0.7,
                "receita_potencial_perdida": 70.0,
            },
        ]
    )
    return produtos, estoque


class TestProdutosEstoque(unittest.TestCase):
    def test_status_exibido_reaproveita_faixas_existentes(self) -> None:
        casos = [
            (0, 0, 0, "Sem estoque"),
            (5, 1, 5, "Crítico"),
            (5, 1, 15, "Atenção"),
            (20, 0.35, 57, "Parado"),
            (20, 1, 20, "Normal"),
            (20, 0, float("inf"), "Parado"),
        ]
        for estoque_atual, media, dias, esperado in casos:
            with self.subTest(esperado=esperado, dias=dias):
                linha = pd.Series(
                    {
                        "estoque_atual": estoque_atual,
                        "media_vendas_dia": media,
                        "dias_estoque": dias,
                    }
                )
                self.assertEqual(_classificar_status_exibicao(linha), esperado)

    def test_tabela_formata_valores_pt_br_e_oferece_tres_visoes(self) -> None:
        produtos, estoque = _dados_produto()
        catalogo = _preparar_catalogo(produtos, estoque)

        rentabilidade = _formatar_tabela(catalogo, "Rentabilidade")
        estoque_view = _formatar_tabela(catalogo, "Estoque")
        geral = _formatar_tabela(catalogo, "Geral")

        self.assertEqual(rentabilidade.loc[0, "Resultado após anúncios"], "-R$ 24,18")
        self.assertEqual(rentabilidade.loc[0, "Margem após anúncios"], "-10,1%")
        self.assertEqual(rentabilidade.loc[0, "ROAS"], "6,93x")
        self.assertEqual(estoque_view.loc[0, "Vendas/dia"], "0,35")
        self.assertEqual(estoque_view.loc[0, "Cobertura"], "0,0 dias")
        self.assertIn("Venda potencial perdida", estoque_view.columns)
        self.assertIn("Faturamento líquido", rentabilidade.columns)
        self.assertIn("Produto", geral.columns)
        self.assertIn("SKU", geral.columns)

    def test_aba_estoque_mostra_estado_positivo_sem_emoji(self) -> None:
        _, estoque = _dados_produto()
        estoque["estoque_atual"] = 5.0
        estoque["dias_estoque"] = 18.0
        estoque["media_vendas_dia"] = 0.25
        estoque["valor_estoque"] = 200.0
        estoque["status_estoque"] = "Normal"
        estoque["receita_potencial_perdida"] = 0.0
        codigo = (
            "import pandas as pd\n"
            "from secoes.estoque import mostrar_estoque\n"
            f"estoque = pd.DataFrame({estoque.to_dict(orient='records')!r})\n"
            "mostrar_estoque(estoque)\n"
        )
        app = AppTest.from_string(codigo).run(timeout=20)

        self.assertFalse(app.exception)
        html = "\n".join(item.value for item in app.get("html"))
        self.assertIn("Tudo certo", html)
        self.assertIn("Alertas de estoque", html)
        self.assertIn("Estoque parado", html)
        self.assertNotIn("🚫", html)
        self.assertNotIn("⏳", html)

    def test_portfolio_unificado_renderiza_tabela_selecionavel(self) -> None:
        produtos, estoque = _dados_produto()
        codigo = (
            "import pandas as pd\n"
            "from secoes.produtos import mostrar_portfolio\n"
            f"produtos = pd.DataFrame({produtos.to_dict(orient='records')!r})\n"
            f"estoque = pd.DataFrame({estoque.to_dict(orient='records')!r})\n"
            "mostrar_portfolio(produtos, estoque)\n"
        )
        app = AppTest.from_string(codigo).run(timeout=20)

        self.assertFalse(app.exception)
        self.assertEqual(len(app.get("dataframe")), 1)
        self.assertIn("Geral", app.radio[0].options)
        self.assertIn("Estoque", app.radio[0].options)
        self.assertIn("Rentabilidade", app.radio[0].options)

    def test_skeleton_corresponde_a_aba_ativa(self) -> None:
        casos = [
            ("Estoque", "mi-skeleton-product-stock-panel"),
            ("Desempenho", "mi-skeleton-product-ranking"),
            ("Portfólio", "mi-skeleton-product-portfolio-table"),
        ]
        for aba, classe in casos:
            with self.subTest(aba=aba):
                app = AppTest.from_string(
                    "from componentes import renderizar_skeleton_produtos\n"
                    f"renderizar_skeleton_produtos({aba!r})\n"
                ).run(timeout=20)
                self.assertFalse(app.exception)
                html = "\n".join(item.value for item in app.get("html"))
                self.assertIn(classe, html)

    def test_rankings_renderizam_barras_para_valores_positivos(self) -> None:
        produtos, estoque = _dados_produto()
        produtos.loc[0, "margem"] = 22.5
        codigo = (
            "import pandas as pd\n"
            "import streamlit as st\n"
            "from secoes.produtos import mostrar_produtos\n"
            f"produtos = pd.DataFrame({produtos.to_dict(orient='records')!r})\n"
            f"estoque = pd.DataFrame({estoque.to_dict(orient='records')!r})\n"
            "st.session_state['_mi_active_page'] = 'produtos_estoque'\n"
            "st.session_state['_mi_page_entering'] = True\n"
            "mostrar_produtos(produtos, estoque)\n"
        )
        app = AppTest.from_string(codigo).run(timeout=20)

        self.assertFalse(app.exception)
        html = "\n".join(item.value for item in app.get("html"))
        self.assertIn("mi-product-ranking-bar-positive", html)
        self.assertIn("mi-entry-positive-bar", html)
        self.assertIn("@keyframes mi-product-positive-grow", html)
        self.assertIn("background:#73A9FF", html)
        self.assertIn("left:50%;width:50.0%", html)
        self.assertIn("22,5%", html)


if __name__ == "__main__":
    unittest.main()
