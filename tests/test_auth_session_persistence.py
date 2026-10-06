import json
import unittest
from urllib.parse import quote
from unittest.mock import patch

from autenticacao import (
    _COOKIE_SESSAO,
    _ler_sessao_cookie,
    _preparar_cookie_sessao,
    _persistir_sessao_cookie,
    _usar_cookie_sessao,
)
from streamlit.testing.v1 import AppTest


class _CookieManagerFake:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.last_set: tuple[str, str, dict[str, object]] | None = None
        self.delete_count = 0

    def get(self, cookie: str) -> str | None:
        return self.values.get(cookie)

    def set(
        self,
        cookie: str,
        value: str,
        **options: object,
    ) -> None:
        self.values[cookie] = value
        self.last_set = (cookie, value, options)

    def delete(self, cookie: str, **options: object) -> None:
        del options
        self.delete_count += 1
        self.values.pop(cookie, None)


class TestAuthSessionPersistence(unittest.TestCase):
    def test_cookie_de_sessao_e_exclusivo_do_ambiente_development(self) -> None:
        self.assertTrue(_usar_cookie_sessao("development"))
        self.assertFalse(_usar_cookie_sessao("production"))

    def test_cookie_sessao_e_validado_antes_da_restauracao(self) -> None:
        cookies = _CookieManagerFake()
        cookies.values[_COOKIE_SESSAO] = json.dumps(
            {
                "access_token": "access",
                "refresh_token": "refresh",
            }
        )
        self.assertEqual(
            _ler_sessao_cookie(cookies.get(_COOKIE_SESSAO)),
            ("access", "refresh"),
        )
        self.assertEqual(
            _ler_sessao_cookie(
                quote(cookies.get(_COOKIE_SESSAO), safe="")
            ),
            ("access", "refresh"),
        )

        cookies.values[_COOKIE_SESSAO] = '{"access_token": 2}'
        self.assertIsNone(_ler_sessao_cookie(cookies.get(_COOKIE_SESSAO)))
        cookies.values[_COOKIE_SESSAO] = "not-json"
        self.assertIsNone(_ler_sessao_cookie(cookies.get(_COOKIE_SESSAO)))

    def test_cookie_e_persistido_com_expiracao_e_flags_de_navegador(self) -> None:
        cookies = _CookieManagerFake()
        with patch("autenticacao._cookie_seguro", return_value=True):
            _persistir_sessao_cookie(
                cookies,
                "access",
                "refresh",
                ambiente="development",
            )

        self.assertIsNotNone(cookies.last_set)
        assert cookies.last_set is not None
        nome, valor, opcoes = cookies.last_set
        self.assertEqual(nome, _COOKIE_SESSAO)
        self.assertEqual(
            json.loads(valor),
            {"access_token": "access", "refresh_token": "refresh"},
        )
        self.assertEqual(opcoes["max_age"], 30 * 24 * 60 * 60)
        self.assertIs(opcoes["secure"], True)
        self.assertEqual(opcoes["same_site"], "lax")
        self.assertEqual(opcoes["path"], "/")

    def test_producao_nao_persiste_tokens_em_cookie(self) -> None:
        cookies = _CookieManagerFake()
        _persistir_sessao_cookie(
            cookies,
            "access",
            "refresh",
            ambiente="production",
        )

        self.assertIsNone(cookies.last_set)
        self.assertNotIn(_COOKIE_SESSAO, cookies.values)

    def test_cookie_legado_prod_e_removido_uma_vez_por_sessao(self) -> None:
        cookies = _CookieManagerFake()
        cookies.values[_COOKIE_SESSAO] = "sessao-legada"
        session_state: dict[str, object] = {}
        with patch("autenticacao.st.session_state", session_state):
            _preparar_cookie_sessao(
                cookies,
                "production",
                cookie_contexto="sessao-legada",
            )
            _preparar_cookie_sessao(
                cookies,
                "production",
                cookie_contexto="sessao-legada",
            )

        self.assertEqual(cookies.delete_count, 1)
        self.assertNotIn(_COOKIE_SESSAO, cookies.values)
        self.assertIs(
            session_state["_mi_prod_auth_cookie_cleared"],
            True,
        )

    def test_cookie_legado_prod_ausente_nao_e_apagado(self) -> None:
        cookies = _CookieManagerFake()
        session_state: dict[str, object] = {}
        with patch("autenticacao.st.session_state", session_state):
            _preparar_cookie_sessao(
                cookies,
                "production",
                cookie_contexto=None,
            )

        self.assertEqual(cookies.delete_count, 0)
        self.assertIs(
            session_state["_mi_prod_auth_cookie_cleared"],
            True,
        )

    def test_cookie_legado_prod_contextual_sem_cache_e_expirado(self) -> None:
        cookies = _CookieManagerFake()
        session_state: dict[str, object] = {}
        with (
            patch("autenticacao.st.session_state", session_state),
            patch("autenticacao._cookie_seguro", return_value=True),
        ):
            _preparar_cookie_sessao(
                cookies,
                "production",
                cookie_contexto="sessao-legada",
            )

        self.assertEqual(cookies.delete_count, 0)
        self.assertEqual(
            cookies.last_set,
            (
                _COOKIE_SESSAO,
                "",
                {
                    "path": "/",
                    "max_age": 0,
                    "secure": True,
                    "same_site": "lax",
                },
            ),
        )
        self.assertIs(session_state["_mi_prod_auth_cookie_cleared"], True)

    def test_logout_remove_o_cookie_e_a_sessao_streamlit(self) -> None:
        codigo = """
import streamlit as st
from unittest.mock import Mock
from autenticacao import _limpar_sessao

cookies = Mock()
cookies.get.return_value = "sessao"
st.session_state["_mi_auth_cookie_manager"] = cookies
st.session_state["_mi_supabase_refresh_token"] = "refresh"
_limpar_sessao()
assert "_mi_supabase_refresh_token" not in st.session_state
assert cookies.delete.called
"""
        app = AppTest.from_string(codigo).run(timeout=20)
        self.assertFalse(app.exception)


if __name__ == "__main__":
    unittest.main()
