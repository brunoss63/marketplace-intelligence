import unittest
from base64 import urlsafe_b64encode
from hashlib import sha256
from urllib.parse import parse_qs, urlparse
from unittest.mock import Mock, patch

from cryptography.fernet import Fernet

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
        with patch.object(
            integracao,
            "obter_configuracao",
            side_effect=valores.get,
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
            side_effect=valores.get,
        ):
            with self.assertRaisesRegex(RuntimeError, "URL HTTPS fixa"):
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
        obter_configuracao.return_value = "6066488581881437"
        obter_origem.side_effect = [
            "Streamlit Secrets",
            "variável de ambiente",
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
        self.assertIn("Client Secret lido de variável de ambiente", mensagem)
        self.assertNotIn("6066488581881437", mensagem)


if __name__ == "__main__":
    unittest.main()
