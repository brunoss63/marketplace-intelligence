import unittest

import pandas as pd
from streamlit.testing.v1 import AppTest

from secoes.marketplace import _marcar_comparacoes_por_produto


def _executar_pagina_marketplaces(
    pedidos: list[dict[str, object]],
    produtos: list[dict[str, object]],
) -> AppTest:
    codigo = """
from datetime import date
import pandas as pd
import streamlit as st
import secoes.marketplace as marketplace

st.session_state['data_inicio'] = date(2026, 9, 1)
st.session_state['data_fim'] = date(2026, 9, 30)
st.session_state['produto_global'] = 'Todos os produtos'
st.session_state['marketplace_global'] = 'Todos'

pedidos = pd.DataFrame(__PEDIDOS__)
produtos = pd.DataFrame(__PRODUTOS__)
publicidade = pd.DataFrame(columns=[
    'data', 'marketplace', 'sku', 'investimento', 'receita_atribuida'
])

def ler_dataset(caminho):
    return {
        'dados/pedidos.csv': pedidos,
        'dados/produtos.csv': produtos,
        'dados/publicidade.csv': publicidade,
    }[caminho]

marketplace.ler_dataset = ler_dataset
marketplace.mostrar_marketplace()
"""
    codigo = codigo.replace("__PEDIDOS__", repr(pedidos))
    codigo = codigo.replace("__PRODUTOS__", repr(produtos))
    return AppTest.from_string(codigo).run(timeout=15)


class TestComparacaoPorProduto(unittest.TestCase):
    def test_so_compara_quando_os_dois_canais_tem_vendas(self) -> None:
        produtos = pd.DataFrame(
            [
                {
                    "produto": "Somente Mercado Livre",
                    "margem_mercado livre": 24.0,
                    "margem_shopee": 0.0,
                    "pedidos_mercado livre": 3,
                    "pedidos_shopee": 0,
                },
                {
                    "produto": "Somente Shopee",
                    "margem_mercado livre": 0.0,
                    "margem_shopee": 31.0,
                    "pedidos_mercado livre": 0,
                    "pedidos_shopee": 2,
                },
                {
                    "produto": "Ambos",
                    "margem_mercado livre": 24.0,
                    "margem_shopee": 31.0,
                    "pedidos_mercado livre": 3,
                    "pedidos_shopee": 2,
                },
            ]
        )

        resultado = _marcar_comparacoes_por_produto(produtos)

        self.assertEqual(
            resultado["melhor_canal"].tolist(),
            ["Sem comparação", "Sem comparação", "Shopee"],
        )
        self.assertTrue(pd.isna(resultado.loc[0, "diferença_margem"]))
        self.assertTrue(pd.isna(resultado.loc[1, "diferença_margem"]))
        self.assertEqual(resultado.loc[2, "diferença_margem"], 7.0)
        self.assertNotIn("tem_comparacao", produtos.columns)

    def test_canal_unico_renderiza_resumo_e_convite_sem_comparativo(self) -> None:
        app = _executar_pagina_marketplaces(
            [
                {
                    "data": "2026-09-16",
                    "status": "Concluído",
                    "produto": "Produto A",
                    "marketplace": "Mercado Livre",
                    "sku": "SKU-A",
                    "quantidade": 2,
                    "faturamento_bruto": 200.0,
                    "desconto": 10.0,
                    "taxa_marketplace": 20.0,
                    "frete_vendedor": 5.0,
                    "id_pedido": "PED-1",
                },
            ],
            [
                {
                    "sku": "SKU-A",
                    "produto": "Produto A",
                    "custo_unitario": 50.0,
                },
            ],
        )

        self.assertFalse(app.exception)
        conteudo = "\n".join(
            [element.value for element in app.get("html")]
            + [element.value for element in app.markdown]
        )
        self.assertIn("Faturamento bruto", conteudo)
        self.assertIn("Em breve", conteudo)
        self.assertIn("Participação por canal", conteudo)
        self.assertIn("100,0% da operação", conteudo)
        self.assertIn("mi-clean-group-row", conteudo)
        self.assertIn("Financeiro", conteudo)
        self.assertIn("Operacional", conteudo)
        self.assertIn("mi-clean-header-status-dot", conteudo)
        self.assertNotIn("<th class=\"\">Líder</th>", conteudo)
        self.assertEqual(len(app.get("plotly_chart")), 0)

    def test_dois_canais_renderizam_comparativo_e_produtos_sem_par(self) -> None:
        pedidos = []
        produtos = [
            {
                "sku": "SKU-A",
                "produto": "Produto A",
                "custo_unitario": 50.0,
            },
            {
                "sku": "SKU-B",
                "produto": "Produto B",
                "custo_unitario": 50.0,
            },
        ]
        for marketplace, sku, nome in (
            ("Mercado Livre", "SKU-A", "Produto A"),
            ("Shopee", "SKU-A", "Produto A"),
            ("Mercado Livre", "SKU-B", "Produto B"),
        ):
            pedidos.append(
                {
                    "data": "2026-09-16",
                    "status": "Concluído",
                    "produto": nome,
                    "marketplace": marketplace,
                    "sku": sku,
                    "quantidade": 1,
                    "faturamento_bruto": 200.0,
                    "desconto": 10.0,
                    "taxa_marketplace": 20.0,
                    "frete_vendedor": 5.0,
                    "id_pedido": f"PED-{sku}",
                }
            )

        app = _executar_pagina_marketplaces(pedidos, produtos)

        self.assertFalse(app.exception)
        conteudo = "\n".join(
            [element.value for element in app.get("html")]
            + [element.value for element in app.markdown]
        )
        self.assertIn("Comparativo visual dos canais", conteudo)
        self.assertIn("Participação por canal", conteudo)
        self.assertIn("Financeiro", conteudo)
        self.assertIn("Operacional", conteudo)
        self.assertIn("mi-clean-table-compact", conteudo)
        self.assertIn("max-width:760px", conteudo)
        self.assertIn("padding: 6px 10px", conteudo)
        self.assertIn("mi-clean-header-status-dot", conteudo)
        self.assertIn("Faturamento", conteudo)
        self.assertIn("Unidades", conteudo)
        self.assertIn("Melhor canal por produto", conteudo)
        self.assertIn("Sem comparação", conteudo)
        self.assertEqual(len(app.get("plotly_chart")), 4)
        self.assertFalse(app.exception)


if __name__ == "__main__":
    unittest.main()
