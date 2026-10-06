import json
import unittest
from urllib.parse import quote
from unittest.mock import patch

from autenticacao import (
    _COOKIE_SESSAO,
    _ler_sessao_cookie,
    _persistir_sessao_cookie,
)
from streamlit.testing.v1 import AppTest


class _CookieManagerFake:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.last_set: tuple[str, str, dict[str, object]] | None = None

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


class TestAuthSessionPersistence(unittest.TestCase):
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
            _persistir_sessao_cookie(cookies, "access", "refresh")

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
