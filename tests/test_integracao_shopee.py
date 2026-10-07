import unittest
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse
from unittest.mock import Mock, patch
from uuid import UUID

from cryptography.fernet import Fernet

import integracao_shopee


class TestIntegracaoShopee(unittest.TestCase):
    def test_status_indica_ambiente_dev_necessario(self) -> None:
        with patch("integracao_shopee.is_database_mode", return_value=False):
            self.assertIn("Supabase", integracao_shopee.status_integracao_shopee())

    def test_status_indica_configuracao_pendente_quando_faltam_secrets(self) -> None:
        with patch("integracao_shopee.is_database_mode", return_value=True):
            with patch("integracao_shopee.obter_configuracao") as configuracao_mock:
                configuracao_mock.side_effect = lambda nome, preferir_secrets=False: (
                    "development" if nome == "MI_ENV" else None
                )

                status = integracao_shopee.status_integracao_shopee()
                self.assertIn("Configuração pendente", status)

    def test_status_indica_oauth_pronto_quando_secrets_existem(self) -> None:
        with patch("integracao_shopee.is_database_mode", return_value=True):
            with patch("integracao_shopee.obter_configuracao") as configuracao_mock:
                with patch("integracao_shopee.obter_origem_configuracao") as origem_mock:
                    configuracao_mock.side_effect = lambda nome, preferir_secrets=False: {
                        "MI_ENV": "development",
                        "SHOPEE_APP_ID": "12345",
                        "SHOPEE_APP_SECRET": "secret",
                        "SHOPEE_REDIRECT_URI": "https://example.com/callback",
                        "SHOPEE_TOKEN_ENCRYPTION_KEY": "-T5J_7xQvR-9J7aM0DNy4_dVvS2AP-wNjX1Yw1gCejaA=",
                    }.get(nome)
                    origem_mock.side_effect = lambda nome, preferir_secrets=False: "Streamlit Secrets"

                    status = integracao_shopee.status_integracao_shopee()
                    self.assertIn("Pronta para OAuth", status)

    def test_configuracao_prod_usa_secrets_exclusivos_de_prod(self) -> None:
        chave = "-T5J_7xQvR-9J7aM0DNy4_dVvS2AP-wNjX1Yw1gCejaA="
        valores = {
            "MI_ENV": "production",
            "SHOPEE_PROD_APP_ID": "prod-app-id",
            "SHOPEE_PROD_APP_SECRET": "prod-app-secret",
            "SHOPEE_PROD_REDIRECT_URI": (
                "https://marketplace-intelligence-live.streamlit.app/"
            ),
            "SHOPEE_PROD_TOKEN_ENCRYPTION_KEY": chave,
            "SHOPEE_DEV_APP_ID": "dev-app-id",
            "SHOPEE_DEV_APP_SECRET": "dev-app-secret",
            "SHOPEE_DEV_REDIRECT_URI": (
                "https://marketplace-intelligence-dev.streamlit.app/"
            ),
            "SHOPEE_DEV_TOKEN_ENCRYPTION_KEY": "dev-key",
            "SHOPEE_APP_ID": "legacy-app-id",
            "SHOPEE_APP_SECRET": "legacy-app-secret",
            "SHOPEE_REDIRECT_URI": "https://legacy.example.com/",
            "SHOPEE_TOKEN_ENCRYPTION_KEY": "legacy-key",
        }

        with patch(
            "integracao_shopee.obter_configuracao",
            side_effect=lambda nome, preferir_secrets=False: valores.get(nome),
        ) as configuracao_mock:
            configuracao = integracao_shopee._obter_configuracao_shopee()

        self.assertEqual(configuracao["app_id"], "prod-app-id")
        self.assertEqual(configuracao["app_secret"], "prod-app-secret")
        self.assertEqual(
            configuracao["redirect_uri"],
            "https://marketplace-intelligence-live.streamlit.app/",
        )
        self.assertEqual(configuracao["token_encryption_key"], chave)
        self.assertNotIn(
            "SHOPEE_DEV_APP_ID",
            [call.args[0] for call in configuracao_mock.call_args_list],
        )
        self.assertNotIn(
            "SHOPEE_APP_ID",
            [call.args[0] for call in configuracao_mock.call_args_list],
        )

    def test_configuracao_prod_nao_usa_credenciais_dev_ou_legadas(self) -> None:
        valores = {
            "MI_ENV": "production",
            "SHOPEE_DEV_APP_ID": "dev-app-id",
            "SHOPEE_APP_ID": "legacy-app-id",
        }
        with patch(
            "integracao_shopee.obter_configuracao",
            side_effect=lambda nome, preferir_secrets=False: valores.get(nome),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "SHOPEE_PROD_APP_ID",
            ):
                integracao_shopee._obter_configuracao_shopee()

    def test_configuracao_prod_exige_callback_https(self) -> None:
        valores = {
            "MI_ENV": "production",
            "SHOPEE_PROD_APP_ID": "prod-app-id",
            "SHOPEE_PROD_APP_SECRET": "prod-app-secret",
            "SHOPEE_PROD_REDIRECT_URI": (
                "http://marketplace-intelligence-live.streamlit.app/"
            ),
            "SHOPEE_PROD_TOKEN_ENCRYPTION_KEY": (
                "-T5J_7xQvR-9J7aM0DNy4_dVvS2AP-wNjX1Yw1gCejaA="
            ),
        }
        with patch(
            "integracao_shopee.obter_configuracao",
            side_effect=lambda nome, preferir_secrets=False: valores.get(nome),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "Em production, use HTTPS",
            ):
                integracao_shopee._obter_configuracao_shopee()

    def test_configuracao_dev_prefere_secrets_com_prefixo_de_ambiente(self) -> None:
        valores = {
            "MI_ENV": "development",
            "SHOPEE_DEV_APP_ID": "dev-app-id",
            "SHOPEE_DEV_APP_SECRET": "dev-app-secret",
            "SHOPEE_DEV_REDIRECT_URI": (
                "https://marketplace-intelligence-dev.streamlit.app/"
            ),
            "SHOPEE_DEV_TOKEN_ENCRYPTION_KEY": (
                "-T5J_7xQvR-9J7aM0DNy4_dVvS2AP-wNjX1Yw1gCejaA="
            ),
            "SHOPEE_APP_ID": "legacy-app-id",
            "SHOPEE_APP_SECRET": "legacy-app-secret",
            "SHOPEE_REDIRECT_URI": "https://legacy.example.com/",
            "SHOPEE_TOKEN_ENCRYPTION_KEY": "legacy-key",
        }
        with patch(
            "integracao_shopee.obter_configuracao",
            side_effect=lambda nome, preferir_secrets=False: valores.get(nome),
        ):
            configuracao = integracao_shopee._obter_configuracao_shopee()

        self.assertEqual(configuracao["app_id"], "dev-app-id")
        self.assertEqual(
            configuracao["redirect_uri"],
            "https://marketplace-intelligence-dev.streamlit.app/",
        )

    def test_fernet_prod_usa_chave_propria_do_ambiente(self) -> None:
        chave_prod = Fernet.generate_key().decode("ascii")
        valores = {
            "MI_ENV": "production",
            "SHOPEE_PROD_TOKEN_ENCRYPTION_KEY": chave_prod,
            "SHOPEE_TOKEN_ENCRYPTION_KEY": Fernet.generate_key().decode("ascii"),
        }
        with patch(
            "integracao_shopee.obter_configuracao",
            side_effect=lambda nome, preferir_secrets=False: valores.get(nome),
        ) as configuracao_mock:
            fernet = integracao_shopee._fernet()

        valor = fernet.encrypt(b"token de teste")
        self.assertEqual(fernet.decrypt(valor), b"token de teste")
        self.assertNotIn(
            "SHOPEE_TOKEN_ENCRYPTION_KEY",
            [call.args[0] for call in configuracao_mock.call_args_list],
        )

    def test_fernet_prod_nao_faz_fallback_para_chave_legada(self) -> None:
        chave_legada = Fernet.generate_key().decode("ascii")
        valores = {
            "MI_ENV": "production",
            "SHOPEE_TOKEN_ENCRYPTION_KEY": chave_legada,
        }
        with patch(
            "integracao_shopee.obter_configuracao",
            side_effect=lambda nome, preferir_secrets=False: valores.get(nome),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "SHOPEE_PROD_TOKEN_ENCRYPTION_KEY",
            ):
                integracao_shopee._fernet()

    def test_mostrar_conexao_shopee_nao_quebra(self) -> None:
        with patch("integracao_shopee.is_database_mode", return_value=True):
            with patch("integracao_shopee.st.warning") as warning_mock:
                with patch("integracao_shopee.st.caption") as caption_mock:
                    with patch("integracao_shopee.st.info") as info_mock:
                        with patch("integracao_shopee.st.markdown") as markdown_mock:
                            with patch("integracao_shopee.obter_configuracao") as configuracao_mock:
                                configuracao_mock.side_effect = lambda nome, preferir_secrets=False: {
                                    "MI_ENV": "development",
                                    "SHOPEE_APP_ID": "12345",
                                    "SHOPEE_APP_SECRET": "secret",
                                    "SHOPEE_REDIRECT_URI": "https://example.com/callback",
                                    "SHOPEE_TOKEN_ENCRYPTION_KEY": "-T5J_7xQvR-9J7aM0DNy4_dVvS2AP-wNjX1Yw1gCejaA=",
                                }.get(nome)

                                integracao_shopee.mostrar_conexao_shopee()

                                self.assertTrue(markdown_mock.called)
                                self.assertTrue(info_mock.called or warning_mock.called)

    def test_url_de_autorizacao_shopee_inclui_pkce(self) -> None:
        url = integracao_shopee._url_de_autorizacao(
            "12345",
            "https://example.com/callback",
            "state-abc",
            "desafio-pkce",
        )

        parametros = parse_qs(urlparse(url).query)
        self.assertEqual(parametros["response_type"], ["code"])
        self.assertEqual(parametros["code_challenge"], ["desafio-pkce"])
        self.assertEqual(parametros["code_challenge_method"], ["S256"])

    def test_capturar_callback_oauth_shopee_armazen_escopo(self) -> None:
        class FakeQueryParams(dict):
            def get_all(self, nome: str):
                return [self.get(nome, "")]

        fake_params = FakeQueryParams({"code": "abc", "state": "state-123", "shop_id": "shop-42"})
        with patch.object(integracao_shopee.st, "session_state", {}) as session_state:
            with patch.object(integracao_shopee.st, "query_params", fake_params):
                integracao_shopee.capturar_callback_oauth_shopee()
                self.assertEqual(
                    session_state["_mi_shopee_oauth_callback"]["code"],
                    "abc",
                )
                self.assertEqual(
                    session_state["_mi_shopee_oauth_callback"]["shop_id"],
                    "shop-42",
                )

    @patch("integracao_shopee._obter_configuracao_shopee")
    @patch("integracao_shopee.requests.post")
    def test_troca_codigo_shopee_retorna_tokens_validos(
        self,
        post_mock: Mock,
        configuracao_mock: Mock,
    ) -> None:
        configuracao_mock.return_value = {
            "app_id": "12345",
            "app_secret": "secret",
            "redirect_uri": "https://example.com/callback",
            "token_encryption_key": "-T5J_7xQvR-9J7aM0DNy4_dVvS2AP-wNjX1Yw1gCejaA=",
        }
        post_mock.return_value.ok = True
        post_mock.return_value.json.return_value = {
            "code": 0,
            "message": "success",
            "data": {
                "access_token": "token-abc",
                "refresh_token": "token-def",
                "expires_in": 3600,
                "shop_id": "shop-42",
            },
        }

        tokens = integracao_shopee._trocar_codigo_shopee("codigo-123", "verificador-abc")

        self.assertEqual(tokens["access_token"], "token-abc")
        self.assertEqual(tokens["shop_id"], "shop-42")
        self.assertEqual(
            post_mock.call_args.kwargs["json"]["code_verifier"],
            "verificador-abc",
        )

    @patch("integracao_shopee.obter_cliente_supabase")
    @patch("integracao_shopee._criptografar", side_effect=lambda valor: valor)
    def test_salvar_tokens_shopee_usa_marketplace_shopee(
        self,
        _criptografar_mock: Mock,
        cliente_mock: Mock,
    ) -> None:
        cliente = cliente_mock.return_value
        cliente.table.return_value.upsert.return_value.execute.return_value = None

        integracao_shopee._salvar_tokens_shopee(
            {
                "access_token": "token-abc",
                "refresh_token": "token-def",
                "expires_in": 3600,
                "shop_id": "shop-42",
            },
            "tenant-123",
        )

        payload = cliente.table.return_value.upsert.call_args.kwargs["on_conflict"]
        self.assertEqual(payload, "tenant_id,marketplace")
        self.assertEqual(
            cliente.table.return_value.upsert.call_args.args[0]["marketplace"],
            "Shopee",
        )

    def test_exigir_integracao_shopee_valida_configuracao_conectada(self) -> None:
        with patch("integracao_shopee.is_database_mode", return_value=True):
            with patch("integracao_shopee._obter_configuracao_shopee"):
                with patch("integracao_shopee._obter_conexao_shopee", return_value={"external_user_id": "shop-42"}):
                    self.assertIsNone(integracao_shopee.exigir_integracao_shopee())

    @patch("integracao_shopee.obter_tenant_id", return_value="tenant-123")
    @patch("integracao_shopee.obter_cliente_supabase")
    def test_helpers_refresh_usam_rpc_com_escopo_do_tenant(
        self,
        cliente_mock: Mock,
        _tenant_mock: Mock,
    ) -> None:
        cliente_mock.return_value.rpc.return_value.execute.return_value.data = True

        self.assertTrue(
            integracao_shopee._reivindicar_lock_refresh_shopee("lease-1")
        )
        integracao_shopee._liberar_lock_refresh_shopee("lease-1")

        self.assertEqual(
            cliente_mock.return_value.rpc.call_args_list,
            [
                unittest.mock.call(
                    "claim_marketplace_token_refresh",
                    {
                        "target_tenant_id": "tenant-123",
                        "target_lease_id": "lease-1",
                    },
                ),
                unittest.mock.call(
                    "release_marketplace_token_refresh",
                    {
                        "target_tenant_id": "tenant-123",
                        "target_lease_id": "lease-1",
                    },
                ),
            ],
        )
        self.assertEqual(_tenant_mock.call_count, 2)

    @patch("integracao_shopee._liberar_lock_refresh_shopee")
    @patch("integracao_shopee.obter_cliente_supabase")
    @patch("integracao_shopee._criptografar", side_effect=lambda valor: f"enc:{valor}")
    @patch("integracao_shopee._solicitar_token_shopee")
    @patch("integracao_shopee._descriptografar", return_value="refresh-token")
    @patch("integracao_shopee._obter_configuracao_shopee")
    @patch("integracao_shopee._obter_conexao_shopee")
    @patch("integracao_shopee._reivindicar_lock_refresh_shopee", return_value=True)
    @patch("integracao_shopee.uuid4", return_value=UUID("00000000-0000-0000-0000-000000000123"))
    def test_renovar_token_usa_lease_banco_e_persiste_sob_lease(
        self,
        _uuid_mock: Mock,
        reivindicar_mock: Mock,
        conexao_mock: Mock,
        _configuracao_mock: Mock,
        _descriptografar_mock: Mock,
        solicitar_mock: Mock,
        _criptografar_mock: Mock,
        cliente_mock: Mock,
        liberar_mock: Mock,
    ) -> None:
        conexao = {
            "external_user_id": "shop-42",
            "access_token_encrypted": "enc:old-access",
            "refresh_token_encrypted": "enc:old-refresh",
            "expires_at": "2026-10-05T12:00:00+00:00",
        }
        conexao_mock.return_value = conexao
        solicitar_mock.return_value = {
            "access_token": "new-access",
            "refresh_token": "new-refresh",
            "expires_in": 3600,
            "shop_id": "shop-42",
        }
        cliente = cliente_mock.return_value
        update = (
            cliente.table.return_value.update.return_value
            .eq.return_value.eq.return_value.eq.return_value
            .select.return_value
        )
        update.execute.return_value.data = [{"external_user_id": "shop-42"}]

        token = integracao_shopee._renovar_tokens_shopee(
            conexao,
            "tenant-123",
        )

        self.assertEqual(token, "new-access")
        _uuid_mock.assert_called_once()
        reivindicar_mock.assert_called_once_with(
            "00000000-0000-0000-0000-000000000123"
        )
        _configuracao_mock.assert_called_once()
        _descriptografar_mock.assert_called_once_with("enc:old-refresh")
        self.assertEqual(_criptografar_mock.call_count, 2)
        solicitar_mock.assert_called_once()
        self.assertEqual(
            cliente.table.return_value.update.call_args.args[0][
                "access_token_encrypted"
            ],
            "enc:new-access",
        )
        update_query = cliente.table.return_value.update.return_value
        update_query.eq.assert_called_once_with("tenant_id", "tenant-123")
        update_query.eq.return_value.eq.assert_called_once_with(
            "marketplace",
            "Shopee",
        )
        update_query.eq.return_value.eq.return_value.eq.assert_called_once_with(
            "refresh_lease_id",
            "00000000-0000-0000-0000-000000000123",
        )
        liberar_mock.assert_called_once_with(
            "00000000-0000-0000-0000-000000000123"
        )

    @patch("integracao_shopee._descriptografar", return_value="rotated-access")
    @patch("integracao_shopee.sleep")
    @patch("integracao_shopee._obter_conexao_shopee")
    @patch("integracao_shopee._reivindicar_lock_refresh_shopee", return_value=False)
    def test_renovar_token_aguarda_outra_sessao_e_reusa_token_rotacionado(
        self,
        reivindicar_mock: Mock,
        conexao_mock: Mock,
        sleep_mock: Mock,
        _descriptografar_mock: Mock,
    ) -> None:
        conexao = {
            "external_user_id": "shop-42",
            "access_token_encrypted": "enc:rotated-access",
            "expires_at": (
                datetime.now(timezone.utc) + timedelta(minutes=30)
            ).isoformat(),
        }
        conexao_mock.return_value = conexao

        token = integracao_shopee._renovar_tokens_shopee(
            {"external_user_id": "shop-42"},
            "tenant-123",
        )

        self.assertEqual(token, "rotated-access")
        reivindicar_mock.assert_called_once()
        conexao_mock.assert_called_once_with(incluir_tokens=True)
        sleep_mock.assert_called_once_with(0.5)
        _descriptografar_mock.assert_called_once_with("enc:rotated-access")

    @patch("integracao_shopee._liberar_lock_refresh_shopee")
    @patch("integracao_shopee.obter_cliente_supabase")
    @patch("integracao_shopee._criptografar", side_effect=lambda valor: f"enc:{valor}")
    @patch("integracao_shopee._solicitar_token_shopee")
    @patch("integracao_shopee._descriptografar", return_value="refresh-token")
    @patch("integracao_shopee._obter_configuracao_shopee")
    @patch("integracao_shopee._obter_conexao_shopee")
    @patch("integracao_shopee._reivindicar_lock_refresh_shopee", return_value=True)
    def test_renovar_token_falha_se_perde_lease_antes_de_persistir(
        self,
        _reivindicar_mock: Mock,
        conexao_mock: Mock,
        _configuracao_mock: Mock,
        _descriptografar_mock: Mock,
        _solicitar_mock: Mock,
        criptografar_mock: Mock,
        cliente_mock: Mock,
        liberar_mock: Mock,
    ) -> None:
        conexao_mock.return_value = {
            "external_user_id": "shop-42",
            "refresh_token_encrypted": "enc:old-refresh",
        }
        _solicitar_mock.return_value = {
            "access_token": "new-access",
            "refresh_token": "new-refresh",
            "expires_in": 3600,
            "shop_id": "shop-42",
        }
        update = (
            cliente_mock.return_value.table.return_value.update.return_value
            .eq.return_value.eq.return_value.eq.return_value
            .select.return_value
        )
        update.execute.return_value.data = []

        with self.assertRaisesRegex(RuntimeError, "persistir a rotação segura"):
            integracao_shopee._renovar_tokens_shopee(
                {"external_user_id": "shop-42"},
                "tenant-123",
            )

        _reivindicar_mock.assert_called_once()
        _configuracao_mock.assert_called_once()
        _descriptografar_mock.assert_called_once_with("enc:old-refresh")
        _solicitar_mock.assert_called_once()
        self.assertEqual(criptografar_mock.call_count, 2)
        liberar_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
