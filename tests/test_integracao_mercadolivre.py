import unittest
from base64 import urlsafe_b64encode
from hashlib import sha256
from urllib.parse import parse_qs, urlparse
from unittest.mock import Mock, patch

from cryptography.fernet import Fernet, InvalidToken

import autenticacao
import integracao_mercadolivre as integracao


class TestIntegracaoMercadoLivre(unittest.TestCase):
    def test_url_de_autorizacao_inclui_estado_e_pkce_s256(self) -> None:
        url = integracao._url_de_autorizacao(
            "app-id",
            "https://marketplace-intelligence-dev.streamlit.app/",
            "state-seguro",
            "desafio-pkce",
        )

        parametros = parse_qs(urlparse(url).query)
        self.assertEqual(
            urlparse(url).scheme,
            "https",
        )
        self.assertEqual(
            urlparse(url).netloc,
            "auth.mercadolivre.com.br",
        )
        self.assertEqual(parametros["response_type"], ["code"])
        self.assertEqual(parametros["client_id"], ["app-id"])
        self.assertEqual(
            parametros["redirect_uri"],
            ["https://marketplace-intelligence-dev.streamlit.app/"],
        )
        self.assertEqual(parametros["state"], ["state-seguro"])
        self.assertEqual(parametros["code_challenge"], ["desafio-pkce"])
        self.assertEqual(parametros["code_challenge_method"], ["S256"])

    def test_configuracao_exige_redirect_https_fixo(self) -> None:
        valores = {
            "MI_ENV": "development",
            "MERCADOLIVRE_DEV_CLIENT_ID": "app-id",
            "MERCADOLIVRE_DEV_CLIENT_SECRET": "app-secret",
            "MERCADOLIVRE_DEV_REDIRECT_URI": (
                "https://marketplace-intelligence-dev.streamlit.app/"
            ),
            "MERCADOLIVRE_DEV_TOKEN_ENCRYPTION_KEY": (
                Fernet.generate_key().decode("ascii")
            ),
        }
        def obter_valor_configuracao(
            nome: str,
            *,
            preferir_secrets: bool = False,
        ) -> str | None:
            if nome != "MI_ENV":
                self.assertTrue(preferir_secrets)
            return valores.get(nome)

        with patch.object(
            integracao,
            "obter_configuracao",
            side_effect=obter_valor_configuracao,
        ):
            configuracao = integracao._obter_configuracao_ml()
        self.assertEqual(
            configuracao["redirect_uri"],
            "https://marketplace-intelligence-dev.streamlit.app/",
        )

        valores["MERCADOLIVRE_DEV_REDIRECT_URI"] = (
            "https://example.com/callback?code=dynamic"
        )
        with patch.object(
            integracao,
            "obter_configuracao",
            side_effect=obter_valor_configuracao,
        ):
            with self.assertRaisesRegex(RuntimeError, "URL HTTPS fixa"):
                integracao._obter_configuracao_ml()

    def test_configuracao_prod_seleciona_secrets_e_callback_proprios(self) -> None:
        chave = Fernet.generate_key().decode("ascii")
        valores = {
            "MI_ENV": "production",
            "MERCADOLIVRE_PROD_CLIENT_ID": "prod-app-id",
            "MERCADOLIVRE_PROD_CLIENT_SECRET": "prod-app-secret",
            "MERCADOLIVRE_PROD_REDIRECT_URI": integracao._REDIRECT_URI_PROD,
            "MERCADOLIVRE_PROD_TOKEN_ENCRYPTION_KEY": chave,
        }
        nomes_lidos: list[str] = []

        def obter_valor_configuracao(
            nome: str,
            *,
            preferir_secrets: bool = False,
        ) -> str | None:
            nomes_lidos.append(nome)
            if nome != "MI_ENV":
                self.assertTrue(preferir_secrets)
            return valores.get(nome)

        with patch.object(
            integracao,
            "obter_configuracao",
            side_effect=obter_valor_configuracao,
        ):
            configuracao = integracao._obter_configuracao_ml()

        self.assertEqual(configuracao["client_id"], "prod-app-id")
        self.assertEqual(configuracao["client_secret"], "prod-app-secret")
        self.assertEqual(
            configuracao["redirect_uri"],
            "https://marketplace-intelligence-live.streamlit.app/",
        )
        self.assertEqual(configuracao["token_encryption_key"], chave)
        url_autorizacao = integracao._url_de_autorizacao(
            configuracao["client_id"],
            configuracao["redirect_uri"],
            "prod-state",
            "prod-pkce",
        )
        self.assertEqual(
            parse_qs(urlparse(url_autorizacao).query)["redirect_uri"],
            [integracao._REDIRECT_URI_PROD],
        )
        self.assertEqual(
            set(nomes_lidos),
            {
                "MI_ENV",
                "MERCADOLIVRE_PROD_CLIENT_ID",
                "MERCADOLIVRE_PROD_CLIENT_SECRET",
                "MERCADOLIVRE_PROD_REDIRECT_URI",
                "MERCADOLIVRE_PROD_TOKEN_ENCRYPTION_KEY",
            },
        )

    def test_diagnostico_invalid_client_seleciona_secrets_prod(self) -> None:
        with patch(
            "integracao_mercadolivre.obter_configuracao",
            side_effect=lambda nome, **_: {
                "MI_ENV": "production",
                "MERCADOLIVRE_PROD_CLIENT_ID": "prod-app-id",
            }.get(nome),
        ) as obter_configuracao:
            with patch(
                "integracao_mercadolivre.obter_origem_configuracao",
                return_value="Streamlit Secrets",
            ) as obter_origem:
                mensagem = integracao._diagnostico_invalid_client()

        self.assertIn("aplicação PROD selecionada", mensagem)
        self.assertNotIn("prod-app-id", mensagem)
        self.assertEqual(
            [call.args[0] for call in obter_configuracao.call_args_list],
            ["MI_ENV", "MERCADOLIVRE_PROD_CLIENT_ID"],
        )
        self.assertEqual(
            [call.args[0] for call in obter_origem.call_args_list],
            [
                "MERCADOLIVRE_PROD_CLIENT_ID",
                "MERCADOLIVRE_PROD_CLIENT_SECRET",
            ],
        )

    def test_configuracao_prod_rejeita_callback_diferente(self) -> None:
        valores = {
            "MI_ENV": "production",
            "MERCADOLIVRE_PROD_CLIENT_ID": "prod-app-id",
            "MERCADOLIVRE_PROD_CLIENT_SECRET": "prod-app-secret",
            "MERCADOLIVRE_PROD_REDIRECT_URI": (
                "https://example.com/callback"
            ),
            "MERCADOLIVRE_PROD_TOKEN_ENCRYPTION_KEY": (
                Fernet.generate_key().decode("ascii")
            ),
        }
        with patch.object(
            integracao,
            "obter_configuracao",
            side_effect=lambda nome, **_: valores.get(nome),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "MERCADOLIVRE_PROD_REDIRECT_URI precisa ser exatamente",
            ):
                integracao._obter_configuracao_ml()

    def test_geracao_pkce_usa_sha256_base64_url_sem_padding(self) -> None:
        verificador, desafio = integracao._gerar_pkce()
        desafio_esperado = (
            urlsafe_b64encode(sha256(verificador.encode("ascii")).digest())
            .rstrip(b"=")
            .decode("ascii")
        )

        self.assertGreaterEqual(len(verificador), 43)
        self.assertLessEqual(len(verificador), 128)
        self.assertEqual(desafio, desafio_esperado)
        self.assertNotIn("=", desafio)

    def test_criptografa_e_descriptografa_credencial(self) -> None:
        chave = Fernet.generate_key().decode("ascii")
        with patch.object(
            integracao,
            "_obter_configuracao_ml",
            return_value={"token_encryption_key": chave},
        ):
            token_cifrado = integracao._criptografar("token-de-teste")
            token = integracao._descriptografar(token_cifrado)

        self.assertNotEqual(token_cifrado, "token-de-teste")
        self.assertEqual(token, "token-de-teste")

    def test_criptografia_prod_usa_chave_independente_da_dev(self) -> None:
        chave_prod = Fernet.generate_key().decode("ascii")
        chave_dev = Fernet.generate_key().decode("ascii")
        valores = {
            "MI_ENV": "production",
            "MERCADOLIVRE_PROD_CLIENT_ID": "prod-app-id",
            "MERCADOLIVRE_PROD_CLIENT_SECRET": "prod-app-secret",
            "MERCADOLIVRE_PROD_REDIRECT_URI": integracao._REDIRECT_URI_PROD,
            "MERCADOLIVRE_PROD_TOKEN_ENCRYPTION_KEY": chave_prod,
        }
        with patch.object(
            integracao,
            "obter_configuracao",
            side_effect=lambda nome, **_: valores.get(nome),
        ):
            token = integracao._criptografar("token-prod")

        self.assertEqual(Fernet(chave_prod).decrypt(token.encode()), b"token-prod")
        with self.assertRaises(InvalidToken):
            Fernet(chave_dev).decrypt(token.encode())

    @patch("integracao_mercadolivre.is_database_mode", return_value=False)
    def test_status_integracao_mercadolivre_indica_ambiente_dev(
        self,
        _: Mock,
    ) -> None:
        self.assertIn("DEV", integracao.status_integracao_mercadolivre())

    def test_status_integracao_mercadolivre_informa_conexao(self) -> None:
        with patch("integracao_mercadolivre.is_database_mode", return_value=True):
            with patch("integracao_mercadolivre._obter_configuracao_ml") as obter_configuracao:
                with patch("integracao_mercadolivre._obter_conexao") as obter_conexao:
                    obter_configuracao.return_value = {
                        "client_id": "app-id",
                        "client_secret": "app-secret",
                        "redirect_uri": "https://example.com/callback",
                        "token_encryption_key": Fernet.generate_key().decode("ascii"),
                    }
                    obter_conexao.return_value = {
                        "external_user_id": "123456",
                        "expires_at": (
                            integracao._agora_utc() + integracao.timedelta(days=1)
                        ).isoformat(),
                    }

                    status = integracao.status_integracao_mercadolivre()

                    self.assertIn("Conectada", status)
                    self.assertIn("123456", status)
                    self.assertIn("válido até", status)

    def test_resposta_oauth_exige_access_e_refresh_token(self) -> None:
        resposta = {
            "access_token": "access-test",
            "refresh_token": "refresh-test",
            "user_id": 123,
            "expires_in": 21600,
            "scope": "read write",
        }

        tokens = integracao._token_da_resposta(resposta)

        self.assertEqual(tokens["access_token"], "access-test")
        self.assertEqual(tokens["refresh_token"], "refresh-test")
        self.assertEqual(tokens["user_id"], "123")
        self.assertEqual(tokens["expires_in"], 21600)

        with self.assertRaisesRegex(RuntimeError, "campos necessários"):
            integracao._token_da_resposta({
                **resposta,
                "refresh_token": "",
            })

    @patch("integracao_mercadolivre.requests.post")
    def test_solicita_token_com_timeout_e_valida_resposta(
        self,
        post: Mock,
    ) -> None:
        resposta = Mock()
        resposta.ok = True
        resposta.json.return_value = {
            "access_token": "access-test",
            "refresh_token": "refresh-test",
            "user_id": 123,
            "expires_in": 21600,
            "scope": "read write",
        }
        post.return_value = resposta

        tokens = integracao._solicitar_token({
            "grant_type": "authorization_code",
            "client_id": "app-id",
        })

        self.assertEqual(tokens["user_id"], "123")
        post.assert_called_once_with(
            "https://api.mercadolibre.com/oauth/token",
            data={
                "grant_type": "authorization_code",
                "client_id": "app-id",
            },
            headers={"Accept": "application/json"},
            timeout=(5, 15),
        )

    @patch("integracao_mercadolivre.requests.post")
    def test_rejeicao_oauth_exibe_codigo_sem_detalhes_brutos(
        self,
        post: Mock,
    ) -> None:
        resposta = Mock()
        resposta.ok = False
        resposta.status_code = 400
        resposta.json.return_value = {
            "error": "invalid_grant",
            "error_description": "sensitive-provider-details",
        }
        post.return_value = resposta

        with self.assertRaisesRegex(
            RuntimeError,
            "HTTP 400, código invalid_grant",
        ) as contexto:
            integracao._solicitar_token({"grant_type": "authorization_code"})

        self.assertNotIn("sensitive-provider-details", str(contexto.exception))

    @patch("integracao_mercadolivre.obter_origem_configuracao")
    @patch("integracao_mercadolivre.obter_configuracao")
    @patch("integracao_mercadolivre.requests.post")
    def test_invalid_client_exibe_diagnostico_sem_expor_secret(
        self,
        post: Mock,
        obter_configuracao: Mock,
        obter_origem: Mock,
    ) -> None:
        obter_configuracao.side_effect = lambda nome, **_: {
            "MI_ENV": "development",
            "MERCADOLIVRE_DEV_CLIENT_ID": "6066488581881437",
        }.get(nome)
        obter_origem.side_effect = [
            "Streamlit Secrets",
            "Streamlit Secrets",
        ]
        resposta = Mock()
        resposta.ok = False
        resposta.status_code = 400
        resposta.json.return_value = {"error": "invalid_client"}
        post.return_value = resposta

        with self.assertRaisesRegex(
            RuntimeError,
            "Client ID lido de Streamlit Secrets",
        ) as contexto:
            integracao._solicitar_token({"grant_type": "authorization_code"})

        mensagem = str(contexto.exception)
        self.assertIn("corresponde ao app DEV: sim", mensagem)
        self.assertIn("Client Secret lido de Streamlit Secrets", mensagem)
        self.assertNotIn("6066488581881437", mensagem)


class TestPrioridadeSegredos(unittest.TestCase):
    @patch.object(autenticacao, "_valor_segredo_streamlit")
    @patch.object(autenticacao.os.environ, "get")
    def test_streamlit_secrets_tem_prioridade_quando_solicitado(
        self,
        variavel_ambiente: Mock,
        segredo_streamlit: Mock,
    ) -> None:
        variavel_ambiente.return_value = "valor-antigo"
        segredo_streamlit.return_value = "valor-atual"

        valor = autenticacao.obter_configuracao(
            "MERCADOLIVRE_DEV_CLIENT_SECRET",
            preferir_secrets=True,
        )
        origem = autenticacao.obter_origem_configuracao(
            "MERCADOLIVRE_DEV_CLIENT_SECRET",
            preferir_secrets=True,
        )

        self.assertEqual(valor, "valor-atual")
        self.assertEqual(origem, "Streamlit Secrets")

    @patch.object(autenticacao, "_valor_segredo_streamlit", return_value=None)
    @patch.object(autenticacao.os.environ, "get", return_value="fallback")
    def test_variavel_ambiente_continua_como_fallback(
        self,
        variavel_ambiente: Mock,
        segredo_streamlit: Mock,
    ) -> None:
        valor = autenticacao.obter_configuracao(
            "MERCADOLIVRE_DEV_CLIENT_SECRET",
            preferir_secrets=True,
        )

        self.assertEqual(valor, "fallback")
        variavel_ambiente.assert_called_once_with(
            "MERCADOLIVRE_DEV_CLIENT_SECRET"
        )
        segredo_streamlit.assert_called_once_with(
            "MERCADOLIVRE_DEV_CLIENT_SECRET"
        )


if __name__ == "__main__":
    unittest.main()
