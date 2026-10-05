import unittest
from datetime import date
from decimal import Decimal
from unittest.mock import Mock, patch

import pandas as pd

import armazenamento
import sincronizacao_mercadolivre as sincronizacao


class TestNormalizacaoPedidosMercadoLivre(unittest.TestCase):
    def test_converte_pedido_com_desconto_em_linhas_canonicas(self) -> None:
        registros = sincronizacao._normalizar_pedidos(
            [
                {
                    "id": 123,
                    "date_created": "2026-09-10T10:00:00.000-03:00",
                    "status": "paid",
                    "currency_id": "BRL",
                    "order_items": [
                        {
                            "item": {
                                "id": "MLB123",
                                "seller_custom_field": "SKU-1",
                                "title": "Produto de teste",
                            },
                            "quantity": 2,
                            "unit_price": 90,
                            "full_unit_price": 100,
                        },
                    ],
                },
            ],
            date(2026, 9, 10),
            date(2026, 9, 10),
        )

        self.assertEqual(len(registros), 1)
        linha = registros.iloc[0]
        self.assertEqual(linha["id_pedido"], "123")
        self.assertEqual(linha["sku"], "SKU-1")
        self.assertEqual(linha["quantidade"], Decimal("2"))
        self.assertEqual(linha["faturamento_bruto"], Decimal("200"))
        self.assertEqual(linha["desconto"], Decimal("20"))
        self.assertEqual(linha["status"], "Concluído")

    def test_ignora_pedidos_fora_do_periodo_solicitado(self) -> None:
        registros = sincronizacao._normalizar_pedidos(
            [
                {
                    "id": 123,
                    "date_created": "2026-09-09T23:59:59-03:00",
                    "status": "paid",
                    "order_items": [
                        {
                            "item": {"id": "MLB123", "title": "Produto"},
                            "quantity": 1,
                            "unit_price": 50,
                        },
                    ],
                },
            ],
            date(2026, 9, 10),
            date(2026, 9, 10),
        )

        self.assertTrue(registros.empty)

    def test_rejeita_moeda_diferente_de_brl(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "somente valores em BRL"):
            sincronizacao._normalizar_pedidos(
                [
                    {
                        "id": 123,
                        "date_created": "2026-09-10T10:00:00-03:00",
                        "status": "paid",
                        "currency_id": "USD",
                        "order_items": [
                            {
                                "item": {"id": "MLB123", "title": "Produto"},
                                "quantity": 1,
                                "unit_price": 50,
                            },
                        ],
                    },
                ],
                date(2026, 9, 10),
                date(2026, 9, 10),
            )

    def test_agrega_linhas_repetidas_para_respeitar_chave_do_banco(self) -> None:
        registros = sincronizacao._normalizar_pedidos(
            [
                {
                    "id": 123,
                    "date_created": "2026-09-10T10:00:00-03:00",
                    "status": "paid",
                    "order_items": [
                        {
                            "item": {
                                "id": "MLB123",
                                "seller_custom_field": "SKU-1",
                                "title": "Produto",
                            },
                            "quantity": 1,
                            "unit_price": 10,
                        },
                        {
                            "item": {
                                "id": "MLB123",
                                "seller_custom_field": "SKU-1",
                                "title": "Produto",
                            },
                            "quantity": 2,
                            "unit_price": 20,
                        },
                    ],
                },
            ],
            date(2026, 9, 10),
            date(2026, 9, 10),
        )

        self.assertEqual(len(registros), 1)
        self.assertEqual(registros.iloc[0]["quantidade"], Decimal("3"))
        self.assertEqual(registros.iloc[0]["faturamento_bruto"], Decimal("50"))
        self.assertEqual(
            registros.iloc[0]["preco_unitario"],
            Decimal("50") / Decimal("3"),
        )


class TestSincronizacaoPedidosMercadoLivre(unittest.TestCase):
    @patch("sincronizacao_mercadolivre.salvar_importacao")
    @patch("sincronizacao_mercadolivre._requisitar_json")
    def test_pagina_pedidos_e_preserva_taxas_e_frete_manualmente_importados(
        self,
        requisitar: Mock,
        salvar: Mock,
    ) -> None:
        requisitar.side_effect = [
            {
                "results": [
                    {
                        "id": 1,
                        "date_created": "2026-09-10T10:00:00-03:00",
                        "status": "confirmed",
                        "order_items": [
                            {
                                "item": {"id": "MLB1", "title": "Produto"},
                                "quantity": 1,
                                "unit_price": 40,
                            },
                        ],
                    },
                    {
                        "id": 2,
                        "date_created": "2026-09-10T11:00:00-03:00",
                        "status": "paid",
                        "order_items": [
                            {
                                "item": {"id": "MLB2", "title": "Outro"},
                                "quantity": 1,
                                "unit_price": 60,
                            },
                        ],
                    },
                ],
                "paging": {"total": 3},
            },
            {
                "results": [
                    {
                        "id": 3,
                        "date_created": "2026-09-10T12:00:00-03:00",
                        "status": "cancelled",
                        "order_items": [
                            {
                                "item": {"id": "MLB3", "title": "Cancelado"},
                                "quantity": 1,
                                "unit_price": 10,
                            },
                        ],
                    },
                ],
                "paging": {"total": 3},
            },
        ]
        salvar.return_value = {
            "inseridos": 3,
            "atualizados": 0,
            "total": 3,
        }

        with patch.object(sincronizacao, "_LIMITE_PEDIDOS", 2):
            resultado = sincronizacao.sincronizar_pedidos(
                "access-token",
                "seller-1",
                date(2026, 9, 10),
                date(2026, 9, 10),
            )

        self.assertEqual(resultado["total"], 3)
        self.assertEqual(requisitar.call_count, 2)
        self.assertEqual(requisitar.call_args_list[0].args[2]["offset"], 0)
        self.assertEqual(requisitar.call_args_list[1].args[2]["offset"], 2)
        salvar.assert_called_once()
        self.assertEqual(salvar.call_args.args[0], "Pedidos")
        self.assertEqual(
            salvar.call_args.kwargs["preservar_campos"],
            {"taxa_marketplace", "frete_vendedor"},
        )
        self.assertEqual(
            salvar.call_args.args[1].iloc[0]["status"],
            "Em andamento",
        )

    def test_rejeita_intervalo_de_datas_invertido(self) -> None:
        with self.assertRaisesRegex(ValueError, "data inicial"):
            sincronizacao.sincronizar_pedidos(
                "access-token",
                "seller-1",
                date(2026, 9, 11),
                date(2026, 9, 10),
            )

    @patch("sincronizacao_mercadolivre.requests.get")
    def test_requisicao_envia_access_token_como_bearer(
        self,
        get: Mock,
    ) -> None:
        resposta = Mock()
        resposta.ok = True
        resposta.json.return_value = {"id": "seller-1"}
        get.return_value = resposta

        resultado = sincronizacao._requisitar_json(
            "access-token",
            "/users/me",
        )

        self.assertEqual(resultado, {"id": "seller-1"})
        self.assertEqual(
            get.call_args.kwargs["headers"]["Authorization"],
            "Bearer access-token",
        )
        self.assertEqual(get.call_args.kwargs["timeout"], (5, 20))


class TestSincronizacaoProdutosMercadoLivre(unittest.TestCase):
    @patch("sincronizacao_mercadolivre.salvar_importacao")
    @patch("sincronizacao_mercadolivre._requisitar_json")
    def test_importa_publicacao_e_variacao_sem_sobrescrever_custos(
        self,
        requisitar: Mock,
        salvar: Mock,
    ) -> None:
        requisitar.side_effect = [
            {
                "results": ["MLB123"],
                "paging": {"total": 1},
            },
            [
                {
                    "code": 200,
                    "body": {
                        "id": "MLB123",
                        "title": "Produto com variação",
                        "price": 80,
                        "variations": [
                            {
                                "id": 456,
                                "seller_custom_field": "SKU-456",
                                "available_quantity": 7,
                            },
                        ],
                    },
                },
            ],
        ]
        salvar.side_effect = [
            {"inseridos": 1, "atualizados": 0, "total": 1},
            {"inseridos": 1, "atualizados": 0, "total": 1},
        ]

        resultado = sincronizacao.sincronizar_produtos_e_estoque(
            "access-token",
            "seller-1",
        )

        self.assertEqual(resultado["produtos"]["total"], 1)
        self.assertEqual(resultado["estoque"]["total"], 1)
        produto = salvar.call_args_list[0].args[1].iloc[0]
        self.assertEqual(produto["sku"], "SKU-456")
        self.assertEqual(produto["preco_venda"], Decimal("80"))
        self.assertEqual(
            salvar.call_args_list[0].kwargs["preservar_campos"],
            {"categoria", "custo_unitario", "estoque_inicial"},
        )
        self.assertEqual(salvar.call_args_list[1].args[0], "Estoque")
        self.assertEqual(
            salvar.call_args_list[1].args[1].iloc[0]["estoque_atual"],
            Decimal("7"),
        )

    def test_rejeita_sku_duplicado_em_publicacoes_ativas(self) -> None:
        publicacoes = [
            {
                "id": "MLB123",
                "title": "Produto A",
                "price": 80,
                "seller_custom_field": "SKU-1",
                "available_quantity": 4,
            },
            {
                "id": "MLB456",
                "title": "Produto B",
                "price": 90,
                "seller_custom_field": "SKU-1",
                "available_quantity": 3,
            },
        ]

        with self.assertRaisesRegex(RuntimeError, "SKU-1"):
            sincronizacao._normalizar_publicacoes(publicacoes)


class TestPersistenciaComCamposPreservados(unittest.TestCase):
    @patch("armazenamento._limpar_cache_dados")
    @patch("armazenamento._ler_tabela", return_value=[])
    @patch("armazenamento.obter_tenant_id", return_value="tenant-1")
    @patch("armazenamento.obter_cliente_supabase")
    def test_upsert_omite_campos_que_devem_ser_preservados(
        self,
        obter_cliente: Mock,
        obter_tenant: Mock,
        ler_tabela: Mock,
        limpar_cache: Mock,
    ) -> None:
        registros = pd.DataFrame([
            {
                "marketplace": "Mercado Livre",
                "sku": "SKU-1",
                "produto": "Produto",
                "categoria": "",
                "custo_unitario": 0,
                "preco_venda": 80,
                "estoque_inicial": 0,
            },
        ])

        armazenamento.salvar_importacao(
            "Produtos",
            registros,
            preservar_campos={"custo_unitario", "estoque_inicial"},
        )

        payload = (
            obter_cliente.return_value.table.return_value.upsert.call_args.args[0]
        )
        self.assertNotIn("unit_cost", payload[0])
        self.assertNotIn("initial_stock", payload[0])
        self.assertEqual(payload[0]["sale_price"], 80)
        obter_tenant.assert_called()
        ler_tabela.assert_called_once()
        limpar_cache.assert_called_once()


if __name__ == "__main__":
    unittest.main()
