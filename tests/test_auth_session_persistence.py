import json
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from urllib.parse import quote
from unittest.mock import patch

from cryptography.fernet import Fernet

from autenticacao import (
    _CHAVE_ID_SESSAO_PROD,
    _COOKIE_SESSAO,
    _COOKIE_SESSAO_PROD,
    _hash_id_sessao_prod,
    _ler_sessao_cookie,
    _limpar_sessao,
    _preparar_cookie_sessao,
    _persistir_sessao_prod,
    _persistir_sessao_cookie,
    _restaurar_sessao_persistente,
    _revogar_sessao_prod,
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

    def test_id_sessao_prod_e_hashado_antes_de_usar_no_banco(self) -> None:
        session_id = "a" * 43
        self.assertEqual(len(_hash_id_sessao_prod(session_id)), 64)
        with self.assertRaises(RuntimeError):
            _hash_id_sessao_prod("access-token")

    def test_sessao_prod_persiste_somente_tokens_cifrados_e_id_no_cookie(
        self,
    ) -> None:
        chave = Fernet.generate_key()
        fernet = Fernet(chave)
        cookies = _CookieManagerFake()
        persisted_rows: list[dict[str, str]] = []
        table = SimpleNamespace(
            insert=lambda dados: (
                persisted_rows.append(dados)
                or SimpleNamespace(
                    select=lambda _: SimpleNamespace(
                        execute=lambda: SimpleNamespace(
                            data=[{"session_hash": dados["session_hash"]}]
                        )
                    )
                )
            )
        )
        cliente = SimpleNamespace(table=lambda _: table)
        session_state: dict[str, object] = {}

        with (
            patch("autenticacao.st.session_state", session_state),
            patch("autenticacao._cookie_seguro", return_value=True),
            patch(
                "autenticacao.obter_configuracao",
                return_value=chave.decode("ascii"),
            ),
        ):
            _persistir_sessao_prod(
                cookies,
                cliente,
                "access-token",
                "refresh-token",
                "user-id",
            )

        session_id = session_state[_CHAVE_ID_SESSAO_PROD]
        self.assertEqual(cookies.values[_COOKIE_SESSAO_PROD], session_id)
        self.assertEqual(cookies.values.keys(), {_COOKIE_SESSAO_PROD})
        persisted = persisted_rows[0]
        self.assertNotIn("access-token", persisted["access_token_encrypted"])
        self.assertNotIn("refresh-token", persisted["refresh_token_encrypted"])
        expires_at = datetime.fromisoformat(persisted["expires_at"])
        self.assertGreater(expires_at, datetime.now(timezone.utc))
        self.assertLessEqual(
            expires_at,
            datetime.now(timezone.utc) + timedelta(days=30, minutes=1),
        )
        self.assertEqual(
            fernet.decrypt(
                persisted["access_token_encrypted"].encode("ascii")
            ).decode("utf-8"),
            "access-token",
        )
        self.assertEqual(
            fernet.decrypt(
                persisted["refresh_token_encrypted"].encode("ascii")
            ).decode("utf-8"),
            "refresh-token",
        )
        self.assertEqual(
            persisted["session_hash"],
            _hash_id_sessao_prod(str(session_id)),
        )
        self.assertIsNotNone(cookies.last_set)
        assert cookies.last_set is not None
        cookie_name, cookie_value, cookie_options = cookies.last_set
        self.assertEqual(cookie_name, _COOKIE_SESSAO_PROD)
        self.assertEqual(cookie_value, session_id)
        self.assertEqual(cookie_options["max_age"], 30 * 24 * 60 * 60)
        self.assertEqual(cookie_options["path"], "/")
        self.assertIs(cookie_options["secure"], True)
        self.assertEqual(cookie_options["same_site"], "lax")

    def test_sessao_prod_e_restaurada_e_revogada_por_hash(self) -> None:
        chave = Fernet.generate_key()
        fernet = Fernet(chave)
        session_id = "b" * 43
        registro = {
            "access_token_encrypted": fernet.encrypt(
                b"access-token"
            ).decode("ascii"),
            "refresh_token_encrypted": fernet.encrypt(
                b"refresh-token"
            ).decode("ascii"),
        }
        chamadas: list[tuple[str, dict[str, str]]] = []

        class _Rpc:
            def __init__(self, nome: str, parametros: dict[str, str]) -> None:
                self.nome = nome
                self.parametros = parametros

            def execute(self) -> SimpleNamespace:
                chamadas.append((self.nome, self.parametros))
                return SimpleNamespace(data=[registro])

        cliente = SimpleNamespace(
            rpc=lambda nome, parametros: _Rpc(nome, parametros)
        )
        cookies = _CookieManagerFake()
        session_state: dict[str, object] = {}

        with (
            patch("autenticacao.st.session_state", session_state),
            patch(
                "autenticacao.st.context",
                SimpleNamespace(
                    cookies={_COOKIE_SESSAO_PROD: session_id}
                ),
            ),
            patch(
                "autenticacao.obter_configuracao",
                return_value=chave.decode("ascii"),
            ),
            patch("autenticacao._configuracao", return_value="production"),
            patch(
                "autenticacao._credenciais_supabase",
                return_value=("https://example.supabase.co", "anon-key"),
            ),
            patch("autenticacao.create_client", return_value=cliente),
        ):
            sessao = _restaurar_sessao_persistente(cliente, cookies)
            _revogar_sessao_prod(session_id)

        self.assertEqual(sessao, ("access-token", "refresh-token"))
        self.assertEqual(session_state[_CHAVE_ID_SESSAO_PROD], session_id)
        self.assertEqual(
            chamadas,
            [
                (
                    "restore_auth_session",
                    {"target_session_hash": _hash_id_sessao_prod(session_id)},
                ),
                (
                    "revoke_auth_session",
                    {"target_session_hash": _hash_id_sessao_prod(session_id)},
                ),
            ],
        )

    def test_refresh_atualiza_tokens_cifrados_da_sessao_existente(self) -> None:
        chave = Fernet.generate_key()
        fernet = Fernet(chave)
        session_id = "d" * 43
        cookies = _CookieManagerFake()
        cookies.values[_COOKIE_SESSAO_PROD] = session_id
        dados_atualizados: dict[str, str] = {}
        filtros: dict[str, str] = {}

        class _Query:
            def update(self, dados: dict[str, str]) -> "_Query":
                dados_atualizados.update(dados)
                return self

            def eq(self, coluna: str, valor: str) -> "_Query":
                filtros[coluna] = valor
                return self

            def select(self, colunas: str) -> "_Query":
                del colunas
                return self

            def execute(self) -> SimpleNamespace:
                return SimpleNamespace(
                    data=[{"session_hash": filtros["session_hash"]}]
                )

        cliente = SimpleNamespace(table=lambda _: _Query())
        session_state: dict[str, object] = {
            _CHAVE_ID_SESSAO_PROD: session_id,
        }
        with (
            patch("autenticacao.st.session_state", session_state),
            patch("autenticacao._cookie_seguro", return_value=True),
            patch(
                "autenticacao.obter_configuracao",
                return_value=chave.decode("ascii"),
            ),
        ):
            _persistir_sessao_prod(
                cookies,
                cliente,
                "new-access-token",
                "new-refresh-token",
                "user-id",
            )

        self.assertEqual(
            filtros,
            {
                "session_hash": _hash_id_sessao_prod(session_id),
                "user_id": "user-id",
            },
        )
        self.assertNotIn("expires_at", dados_atualizados)
        self.assertEqual(
            fernet.decrypt(
                dados_atualizados["access_token_encrypted"].encode("ascii")
            ).decode("utf-8"),
            "new-access-token",
        )
        self.assertEqual(
            fernet.decrypt(
                dados_atualizados["refresh_token_encrypted"].encode("ascii")
            ).decode("utf-8"),
            "new-refresh-token",
        )
        self.assertIsNone(cookies.last_set)

    def test_logout_revoga_sessao_prod_e_remove_cookie(self) -> None:
        session_id = "c" * 43
        cookies = _CookieManagerFake()
        cookies.values[_COOKIE_SESSAO_PROD] = session_id
        chamadas: list[tuple[str, dict[str, str]]] = []

        class _Rpc:
            def __init__(self, nome: str, parametros: dict[str, str]) -> None:
                self.nome = nome
                self.parametros = parametros

            def execute(self) -> SimpleNamespace:
                chamadas.append((self.nome, self.parametros))
                return SimpleNamespace(data=None)

        cliente = SimpleNamespace(
            rpc=lambda nome, parametros: _Rpc(nome, parametros)
        )
        session_state: dict[str, object] = {
            _CHAVE_ID_SESSAO_PROD: session_id,
            "_mi_auth_cookie_manager": cookies,
            "_mi_supabase_access_token": "access",
        }
        with (
            patch("autenticacao.st.session_state", session_state),
            patch("autenticacao._configuracao", return_value="production"),
            patch(
                "autenticacao._credenciais_supabase",
                return_value=("https://example.supabase.co", "anon-key"),
            ),
            patch("autenticacao.create_client", return_value=cliente),
        ):
            _limpar_sessao()

        self.assertEqual(
            chamadas,
            [
                (
                    "revoke_auth_session",
                    {"target_session_hash": _hash_id_sessao_prod(session_id)},
                )
            ],
        )
        self.assertNotIn(_COOKIE_SESSAO_PROD, cookies.values)
        self.assertNotIn("_mi_supabase_access_token", session_state)
        self.assertNotIn(_CHAVE_ID_SESSAO_PROD, session_state)

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
