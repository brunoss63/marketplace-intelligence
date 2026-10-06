from datetime import date
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


class TestPaginaVendasPedidos(unittest.TestCase):
    pagina = (
        Path(__file__).resolve().parents[1]
        / "paginas"
        / "vendas_pedidos.py"
    )

    def _executar(self, app: AppTest) -> AppTest:
        with patch.dict(os.environ, {"MI_ENV": "local"}):
            return app.run(timeout=60)

    def _abrir_pagina(self) -> AppTest:
        app = AppTest.from_file(str(self.pagina))
        app.session_state["data_inicio"] = date(2026, 9, 1)
        app.session_state["data_fim"] = date(2026, 9, 30)
        app.session_state["produto_global"] = "Todos os produtos"
        app.session_state["marketplace_global"] = "Todos"
        return self._executar(app)

    def test_renderiza_resumo_tabela_e_controles_de_ordenacao(self) -> None:
        app = self._abrir_pagina()

        self.assertFalse(app.exception)
        self.assertEqual(len(app.dataframe), 1)
        self.assertEqual(len(app.dataframe[0].value), 15)
        self.assertEqual(
            [seletor.label for seletor in app.selectbox],
            ["Status do pedido", "Ordenar por", "Itens por página"],
        )

        html = "\n".join(item.value for item in app.get("html"))
        self.assertIn("mi-card-operacional", html)
        self.assertIn("mi-entry-card", html)
        self.assertTrue(app.get("download_button"))

        seletor_ordenacao = next(
            seletor
            for seletor in app.selectbox
            if seletor.label == "Ordenar por"
        )
        seletor_ordenacao.select("Marketplace")
        self._executar(app)
        self.assertEqual(
            app.session_state["vendas_pedidos_ordenar_por"],
            "Marketplace",
        )
        self.assertNotIn(
            "mi-entry-card",
            "\n".join(item.value for item in app.get("html")),
        )

        tamanho_pagina = next(
            seletor
            for seletor in app.selectbox
            if seletor.label == "Itens por página"
        )
        tamanho_pagina.select(30)
        self._executar(app)
        self.assertGreater(len(app.dataframe[0].value), 15)
        self.assertLessEqual(len(app.dataframe[0].value), 30)
        self.assertFalse(app.exception)

    def test_selecao_abre_detalhe_e_navega_sem_sair_da_pagina(self) -> None:
        app = self._abrir_pagina()
        app.session_state["vendas_pedidos_grid_0"] = {
            "selection": {"rows": [0], "columns": [], "cells": []}
        }
        self._executar(app)

        self.assertFalse(app.exception)
        self.assertEqual(len(app.get("dialog")), 1)
        html = "\n".join(item.value for item in app.get("html"))
        self.assertIn("Composição financeira", html)
        self.assertIn("Margem percentual", html)

        proximo = next(
            botao for botao in app.button if botao.label == "Próximo →"
        )
        proximo.click()
        self._executar(app)
        self.assertEqual(
            app.session_state["_vendas_pedidos_detalhe_indice"],
            1,
        )
        self.assertEqual(len(app.get("dialog")), 1)
        self.assertFalse(app.exception)

        fechar = next(
            botao for botao in app.button if botao.label == "Fechar"
        )
        fechar.click()
        self._executar(app)
        self.assertFalse(app.session_state["_vendas_pedidos_detalhe_aberto"])
        self.assertEqual(len(app.get("dialog")), 0)
        self.assertFalse(app.exception)

    def test_busca_sem_resultados_tem_acao_para_limpar(self) -> None:
        app = self._abrir_pagina()
        app.text_input[0].set_value("pedido-que-nao-existe")
        self._executar(app)

        self.assertFalse(app.exception)
        self.assertEqual(len(app.dataframe), 0)
        html = "\n".join(item.value for item in app.get("html"))
        self.assertIn("Nenhum pedido encontrado", html)
        self.assertNotIn("mi-entry-card", html)

        limpar = next(
            botao for botao in app.button if botao.label == "Limpar filtros"
        )
        limpar.click()
        self._executar(app)
        self.assertEqual(len(app.dataframe), 1)
        self.assertEqual(app.session_state["vendas_pedidos_busca"], "")
        self.assertFalse(app.exception)

    def test_instrucao_botao_e_abertura_pelo_numero(self) -> None:
        app = self._abrir_pagina()
        html = "\n".join(item.value for item in app.get("html"))
        self.assertIn(
            "Marque a caixa à esquerda de um pedido para ver os detalhes",
            html,
        )
        self.assertIn('class="mi-icon"', html)

        botao_detalhes = next(
            botao for botao in app.button if botao.label == "Ver detalhes"
        )
        self.assertTrue(botao_detalhes.disabled)
        self.assertEqual(app.session_state["vendas_pedidos_pagina"], 0)

        primeiro_pedido = str(app.dataframe[0].value.iloc[0]["Pedido"])
        app.text_input[1].set_value(primeiro_pedido)
        abrir = next(
            botao for botao in app.button if botao.label == "Abrir pedido"
        )
        abrir.click()
        self._executar(app)

        self.assertEqual(len(app.get("dialog")), 1)
        self.assertEqual(
            app.session_state["_vendas_pedidos_detalhe_indice"],
            0,
        )
        self.assertEqual(app.session_state["vendas_pedidos_pagina"], 0)
        self.assertEqual(app.session_state["vendas_pedidos_busca"], "")
        self.assertFalse(app.exception)

    def test_numero_fora_dos_filtros_mostra_mensagem_sem_abrir_dialogo(self) -> None:
        app = self._abrir_pagina()
        app.text_input[1].set_value("pedido-inexistente")
        abrir = next(
            botao for botao in app.button if botao.label == "Abrir pedido"
        )
        abrir.click()
        self._executar(app)

        self.assertEqual(len(app.get("dialog")), 0)
        self.assertTrue(
            any(
                "não encontrado nos pedidos filtrados" in alerta.value
                for alerta in app.info
            )
        )
        self.assertEqual(app.session_state["vendas_pedidos_pagina"], 0)
        self.assertFalse(app.exception)


if __name__ == "__main__":
    unittest.main()
