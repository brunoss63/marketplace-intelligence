import unittest
from datetime import date
from decimal import Decimal
from unittest.mock import Mock, patch

import pandas as pd

import sincronizacao_shopee


class TestSincronizacaoShopee(unittest.TestCase):
    def test_normaliza_pedidos_da_shopee_para_formato_canonico(self) -> None:
        registros = sincronizacao_shopee._normalizar_pedidos(
            [
                {
                    "order_sn": "SO-1001",
                    "create_time": "2024-10-05T10:00:00-03:00",
                    "order_status": "PAID",
                    "order_detail": [
                        {
                            "item_name": "Camiseta X",
                            "item_sku": "SKU-1",
                            "quantity": 2,
                            "unit_price": 50,
                        }
                    ],
                }
            ],
            date(2024, 10, 5),
            date(2024, 10, 5),
        )

        self.assertEqual(len(registros), 1)
        linha = registros.iloc[0]
        self.assertEqual(linha["id_pedido"], "SO-1001")
        self.assertEqual(linha["sku"], "SKU-1")
        self.assertEqual(linha["quantidade"], Decimal("2"))
        self.assertEqual(linha["faturamento_bruto"], Decimal("100"))
        self.assertEqual(linha["status"], "Concluído")

    @patch("sincronizacao_shopee.salvar_importacao")
    @patch("sincronizacao_shopee._buscar_pedidos")
    def test_sincronizar_pedidos_chama_salvar_importacao(
        self,
        buscar_mock: Mock,
        salvar_mock: Mock,
    ) -> None:
        buscar_mock.return_value = [
            {
                "order_sn": "SO-2001",
                "create_time": "2024-10-05T10:00:00-03:00",
                "order_status": "PAID",
                "order_detail": [
                    {
                        "item_name": "Teclado",
                        "item_sku": "SK-9",
                        "quantity": 1,
                        "unit_price": 75,
                    }
                ],
            }
        ]
        salvar_mock.return_value = {"inseridos": 1, "atualizados": 0, "total": 1}

        resultado = sincronizacao_shopee.sincronizar_pedidos(
            "token-x",
            date(2024, 10, 5),
            date(2024, 10, 5),
        )

        self.assertEqual(resultado["total"], 1)
        self.assertEqual(salvar_mock.call_args.args[0], "Pedidos")
        self.assertEqual(
            salvar_mock.call_args.kwargs["preservar_campos"],
            {"taxa_marketplace", "frete_vendedor"},
        )

    @patch("sincronizacao_shopee.salvar_importacao")
    @patch("sincronizacao_shopee._buscar_produtos")
    def test_sincronizar_produtos_e_estoque_cria_dataframes_canonicos(
        self,
        buscar_produtos_mock: Mock,
        salvar_mock: Mock,
    ) -> None:
        buscar_produtos_mock.return_value = [
            {
                "item_id": "100",
                "item_name": "Mouse Gamer",
                "shop_sku": "SKU-MOUSE",
                "stock": 25,
                "price": 120,
            }
        ]
        salvar_mock.side_effect = [
            {"inseridos": 1, "atualizados": 0, "total": 1},
            {"inseridos": 1, "atualizados": 0, "total": 1},
        ]

        resultado = sincronizacao_shopee.sincronizar_produtos_e_estoque("token-y")

        self.assertEqual(resultado["produtos"]["total"], 1)
        self.assertEqual(resultado["estoque"]["total"], 1)
        self.assertEqual(salvar_mock.call_count, 2)


if __name__ == "__main__":
    unittest.main()
