import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from armazenamento import (
    _ler_csv_local,
    invalidar_cache_importacao,
    ler_dataset,
)
from dados_periodo import _calcular_series_financeiras_diarias


class TestCacheDashboard(unittest.TestCase):
    def setUp(self) -> None:
        _ler_csv_local.clear()
        _calcular_series_financeiras_diarias.clear()

    def tearDown(self) -> None:
        _ler_csv_local.clear()
        _calcular_series_financeiras_diarias.clear()

    def test_leitura_local_reavalia_arquivo_alterado_e_opcoes_csv(self) -> None:
        with tempfile.TemporaryDirectory() as diretorio:
            caminho = Path(diretorio) / "dados.csv"
            caminho.write_text("codigo\n001\n", encoding="utf-8")

            with patch.dict(os.environ, {"MI_ENV": "local"}):
                texto = ler_dataset(caminho, dtype={"codigo": "string"})
                numerico = ler_dataset(caminho)
                self.assertEqual(texto.loc[0, "codigo"], "001")
                self.assertEqual(numerico.loc[0, "codigo"], 1)

                estatuto = caminho.stat()
                caminho.write_text("codigo\n002\n", encoding="utf-8")
                os.utime(
                    caminho,
                    ns=(estatuto.st_atime_ns, estatuto.st_mtime_ns),
                )
                invalidar_cache_importacao()

                atualizado = ler_dataset(
                    caminho,
                    dtype={"codigo": "string"},
                )

        self.assertEqual(atualizado.loc[0, "codigo"], "002")

    def test_series_diarias_refletem_kpis_com_custo_e_anuncios(self) -> None:
        pedidos = pd.DataFrame(
            [
                {
                    "data": "2025-01-01",
                    "sku": "SKU-1",
                    "quantidade": 2,
                    "faturamento_bruto": 100.0,
                    "desconto": 5.0,
                    "taxa_marketplace": 2.0,
                    "frete_vendedor": 1.0,
                    "marketplace": "Mercado Livre",
                    "produto": "Produto 1",
                },
                {
                    "data": "2025-01-02",
                    "sku": "SKU-1",
                    "quantidade": 1,
                    "faturamento_bruto": 40.0,
                    "desconto": 0.0,
                    "taxa_marketplace": 1.0,
                    "frete_vendedor": 0.0,
                    "marketplace": "Mercado Livre",
                    "produto": "Produto 1",
                },
            ]
        )
        produtos = pd.DataFrame(
            [{"sku": "SKU-1", "produto": "Produto 1", "custo_unitario": 20.0}]
        )
        publicidade = pd.DataFrame(
            [
                {
                    "data": "2025-01-01",
                    "sku": "SKU-1",
                    "marketplace": "Mercado Livre",
                    "investimento": 10.0,
                }
            ]
        )

        series = _calcular_series_financeiras_diarias(
            pedidos,
            produtos,
            publicidade,
            date(2025, 1, 1),
            date(2025, 1, 2),
            None,
            None,
        )

        self.assertEqual(series["bruto"], [100.0, 40.0])
        self.assertEqual(series["liquido"], [92.0, 39.0])
        self.assertEqual(series["resultado"], [42.0, 19.0])
        self.assertAlmostEqual(series["margem"][0], 42 / 95 * 100)
        self.assertAlmostEqual(series["margem"][1], 19 / 40 * 100)


if __name__ == "__main__":
    unittest.main()
