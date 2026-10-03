from __future__ import annotations

from base64 import urlsafe_b64encode
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from secrets import token_urlsafe
from time import sleep
from typing import Any
from urllib.parse import urlencode, urlparse
from uuid import uuid4

from cryptography.fernet import Fernet, InvalidToken
import requests
import streamlit as st
from postgrest.exceptions import APIError

from autenticacao import obter_configuracao, obter_origem_configuracao
from armazenamento import (
    is_database_mode,
    obter_cliente_supabase,
    obter_tenant_id,
)


_CHAVE_CALLBACK = "_mi_ml_oauth_callback"
_CHAVE_URL_AUTORIZACAO = "_mi_ml_authorization_url"
_URL_AUTORIZACAO = "https://auth.mercadolivre.com.br/authorization"
_URL_TOKEN = "https://api.mercadolibre.com/oauth/token"
_URL_USUARIO = "https://api.mercadolibre.com/users/me"
_NOME_MARKETPLACE = "Mercado Livre"
_CLIENT_ID_APLICACAO_DEV = "6066488581881437"
_ANTECEDENCIA_REFRESH = timedelta(minutes=2)
_TIMEOUT_REQUISICAO = (5, 15)


def _obter_usuario_id() -> str:
    usuario_id = st.session_state.get("_mi_supabase_user_id")
    if not usuario_id:
        raise RuntimeError(
            "A identidade autenticada não está disponível. Entre novamente."
        )
    return str(usuario_id)


def _obter_configuracao_ml() -> dict[str, str]:
    ambiente = obter_configuracao("MI_ENV")
    if ambiente != "development":
        raise RuntimeError(
            "A integração Mercado Livre está disponível somente no ambiente "
            "development até que uma aplicação de produção seja configurada."
        )

    nomes = {
        "client_id": "MERCADOLIVRE_DEV_CLIENT_ID",
        "client_secret": "MERCADOLIVRE_DEV_CLIENT_SECRET",
        "redirect_uri": "MERCADOLIVRE_DEV_REDIRECT_URI",
        "token_encryption_key": "MERCADOLIVRE_DEV_TOKEN_ENCRYPTION_KEY",
    }
    configuracao = {
        chave: obter_configuracao(nome)
        for chave, nome in nomes.items()
    }
    ausentes = [
        nomes[chave]
        for chave, valor in configuracao.items()
        if not valor or not str(valor).strip()
    ]
    if ausentes:
        raise RuntimeError(
            "Configure estes secrets de desenvolvimento antes de conectar o "
            "Mercado Livre: " + ", ".join(ausentes) + "."
        )
    valores = {chave: str(valor) for chave, valor in configuracao.items()}
    redirect_uri = valores["redirect_uri"]
    redirect = urlparse(redirect_uri)
    if (
        redirect_uri != redirect_uri.strip()
        or redirect.scheme != "https"
        or not redirect.netloc
        or redirect.username
        or redirect.password
        or redirect.query
        or redirect.fragment
    ):
        raise RuntimeError(
            "MERCADOLIVRE_DEV_REDIRECT_URI precisa ser uma URL HTTPS fixa, "
            "sem credenciais, query string ou fragmento, e corresponder "
            "exatamente ao cadastro do aplicativo."
        )
    return valores


def _fernet() -> Fernet:
    chave = _obter_configuracao_ml()["token_encryption_key"]
    try:
        return Fernet(chave.encode("ascii"))
    except (UnicodeEncodeError, ValueError) as erro:
        raise RuntimeError(
            "MERCADOLIVRE_DEV_TOKEN_ENCRYPTION_KEY não é uma chave Fernet "
            "válida. Preserve a chave existente para não perder acesso aos "
            "tokens já armazenados."
        ) from erro


def _criptografar(valor: str) -> str:
    return _fernet().encrypt(valor.encode("utf-8")).decode("ascii")


def _descriptografar(valor: str) -> str:
    try:
        return _fernet().decrypt(valor.encode("ascii")).decode("utf-8")
    except (InvalidToken, UnicodeEncodeError, UnicodeDecodeError) as erro:
        raise RuntimeError(
            "Não foi possível descriptografar as credenciais do Mercado "
            "Livre. Verifique a chave Fernet configurada para este ambiente."
        ) from erro


def _agora_utc() -> datetime:
    return datetime.now(timezone.utc)


def _formatar_data_hora(valor: datetime) -> str:
    return valor.astimezone(timezone.utc).isoformat()


def _gerar_pkce() -> tuple[str, str]:
    verificador = token_urlsafe(64)
    resumo = sha256(verificador.encode("ascii")).digest()
    desafio = urlsafe_b64encode(resumo).rstrip(b"=").decode("ascii")
    return verificador, desafio


def _url_de_autorizacao(
    client_id: str,
    redirect_uri: str,
    state: str,
    code_challenge: str,
) -> str:
    parametros = urlencode(
        {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
    )
    return f"{_URL_AUTORIZACAO}?{parametros}"


def iniciar_conexao_mercadolivre() -> str:
    if not is_database_mode():
        raise RuntimeError(
            "A conexão com marketplaces exige o ambiente Supabase DEV."
        )

    configuracao = _obter_configuracao_ml()
    tenant_id = obter_tenant_id()
    usuario_id = _obter_usuario_id()
    cliente = obter_cliente_supabase()
    agora = _agora_utc()
    (
        cliente.table("marketplace_oauth_transactions")
        .delete()
        .eq("tenant_id", tenant_id)
        .eq("user_id", usuario_id)
        .lt("expires_at", _formatar_data_hora(agora))
        .execute()
    )

    state = token_urlsafe(32)
    verificador, desafio = _gerar_pkce()
    (
        cliente.table("marketplace_oauth_transactions")
        .insert({
            "state_hash": sha256(state.encode("ascii")).hexdigest(),
            "tenant_id": tenant_id,
            "user_id": usuario_id,
            "code_verifier_encrypted": _criptografar(verificador),
            "expires_at": _formatar_data_hora(agora + timedelta(minutes=10)),
        })
        .execute()
    )
    return _url_de_autorizacao(
        configuracao["client_id"],
        configuracao["redirect_uri"],
        state,
        desafio,
    )


def _query_parametro_unico(nome: str) -> str:
    valores = st.query_params.get_all(nome)
    if len(valores) != 1:
        return ""
    return valores[0]


def capturar_callback_oauth() -> None:
    nomes = ("code", "state", "error", "error_description")
    if not any(nome in st.query_params for nome in nomes):
        return

    callback = {
        nome: _query_parametro_unico(nome)
        for nome in nomes
    }
    st.session_state[_CHAVE_CALLBACK] = callback
    for nome in nomes:
        if nome in st.query_params:
            del st.query_params[nome]


def _consumir_transacao_oauth(state: str) -> dict[str, Any]:
    state_hash = sha256(state.encode("utf-8")).hexdigest()
    resposta = (
        obter_cliente_supabase()
        .table("marketplace_oauth_transactions")
        .delete()
        .eq("state_hash", state_hash)
        .eq("tenant_id", obter_tenant_id())
        .eq("user_id", _obter_usuario_id())
        .select("*")
        .execute()
    )
    linhas = resposta.data or []
    if len(linhas) != 1:
        raise RuntimeError(
            "A resposta OAuth não corresponde a uma autorização pendente "
            "desta conta. Inicie a conexão novamente."
        )

    transacao = linhas[0]
    expira_em = datetime.fromisoformat(
        str(transacao["expires_at"]).replace("Z", "+00:00")
    )
    if expira_em <= _agora_utc():
        raise RuntimeError(
            "A autorização expirou. Inicie a conexão com o Mercado Livre "
            "novamente."
        )
    return transacao


def _token_da_resposta(dados: Any) -> dict[str, str | int]:
    if not isinstance(dados, dict):
        raise RuntimeError(
            "O Mercado Livre retornou uma resposta OAuth inválida."
        )

    access_token = dados.get("access_token")
    refresh_token = dados.get("refresh_token")
    user_id = dados.get("user_id")
    expires_in = dados.get("expires_in")
    scope = dados.get("scope")
    if (
        not isinstance(access_token, str)
        or not access_token
        or not isinstance(refresh_token, str)
        or not refresh_token
        or user_id is None
        or not str(user_id).strip()
        or isinstance(expires_in, bool)
        or not isinstance(expires_in, int)
        or expires_in <= 0
        or not isinstance(scope, str)
    ):
        raise RuntimeError(
            "A resposta OAuth do Mercado Livre não contém os campos "
            "necessários para persistir a conexão."
        )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user_id": str(user_id),
        "expires_in": expires_in,
        "scope": scope,
    }


def _mensagem_erro_oauth(status_code: int, corpo: Any) -> str:
    codigo = corpo.get("error") if isinstance(corpo, dict) else None
    if (
        not isinstance(codigo, str)
        or not codigo
        or len(codigo) > 80
        or not all(
            caractere.isalnum() or caractere in "._-"
            for caractere in codigo
        )
    ):
        codigo = None

    mensagem = (
        "O Mercado Livre recusou a solicitação OAuth "
        f"(HTTP {status_code}"
    )
    if codigo:
        mensagem += f", código {codigo}"
    mensagem += ")."

    orientacoes = {
        "invalid_grant": (
            " O código pode ter expirado ou já ter sido usado; se ocorrer "
            "novamente, confira também a URI de redirecionamento e o PKCE."
        ),
        "invalid_client": (
            " Confira se o Client ID e o Client Secret atuais pertencem ao "
            "mesmo aplicativo e estão atualizados nos secrets do Streamlit."
        ),
        "invalid_request": (
            " Confira a configuração do fluxo OAuth e a URI de "
            "redirecionamento cadastrada."
        ),
        "unauthorized_client": (
            " Confira se o aplicativo permite o fluxo Authorization Code."
        ),
    }
    return mensagem + orientacoes.get(codigo, "")


def _diagnostico_invalid_client() -> str:
    client_id = obter_configuracao("MERCADOLIVRE_DEV_CLIENT_ID")
    id_corresponde = client_id == _CLIENT_ID_APLICACAO_DEV
    origem_client_id = obter_origem_configuracao(
        "MERCADOLIVRE_DEV_CLIENT_ID"
    )
    origem_client_secret = obter_origem_configuracao(
        "MERCADOLIVRE_DEV_CLIENT_SECRET"
    )
    return (
        " Diagnóstico seguro: Client ID lido de "
        f"{origem_client_id} (corresponde ao app DEV: "
        f"{'sim' if id_corresponde else 'não'}); Client Secret lido de "
        f"{origem_client_secret}. Nenhum valor secreto foi exibido."
    )


def _solicitar_token(dados: dict[str, str]) -> dict[str, str | int]:
    try:
        resposta = requests.post(
            _URL_TOKEN,
            data=dados,
            headers={"Accept": "application/json"},
            timeout=_TIMEOUT_REQUISICAO,
        )
    except requests.RequestException as erro:
        raise RuntimeError(
            "Não foi possível comunicar com o serviço OAuth do Mercado "
            "Livre. Verifique a conexão e tente novamente."
        ) from erro

    try:
        corpo = resposta.json()
    except requests.JSONDecodeError as erro:
        if not resposta.ok:
            raise RuntimeError(
                "O Mercado Livre recusou a solicitação OAuth "
                f"(HTTP {resposta.status_code}) e retornou uma resposta "
                "inválida."
            ) from erro
        raise RuntimeError(
            "O serviço OAuth do Mercado Livre retornou uma resposta inválida."
        ) from erro
    if not resposta.ok:
        codigo_erro = corpo.get("error") if isinstance(corpo, dict) else None
        diagnostico = (
            _diagnostico_invalid_client()
            if codigo_erro == "invalid_client"
            else ""
        )
        raise RuntimeError(
            _mensagem_erro_oauth(resposta.status_code, corpo) + diagnostico
        )
    return _token_da_resposta(corpo)


def _trocar_codigo(
    codigo: str,
    verificador: str,
) -> dict[str, str | int]:
    configuracao = _obter_configuracao_ml()
    return _solicitar_token({
        "grant_type": "authorization_code",
        "client_id": configuracao["client_id"],
        "client_secret": configuracao["client_secret"],
        "code": codigo,
        "redirect_uri": configuracao["redirect_uri"],
        "code_verifier": verificador,
    })


def _salvar_tokens(
    tokens: dict[str, str | int],
    tenant_id: str,
) -> None:
    cliente = obter_cliente_supabase()
    conta_id = str(tokens["user_id"])
    conexoes = (
        cliente.table("marketplace_connections")
        .select("external_user_id")
        .eq("tenant_id", tenant_id)
        .eq("marketplace", _NOME_MARKETPLACE)
        .limit(1)
        .execute()
        .data
        or []
    )
    if conexoes and str(conexoes[0]["external_user_id"]) != conta_id:
        raise RuntimeError(
            "Este tenant já possui uma conexão do Mercado Livre com outra "
            "conta. Remova a conexão atual antes de vincular uma conta "
            "diferente."
        )

    agora = _agora_utc()
    payload = {
        "tenant_id": tenant_id,
        "marketplace": _NOME_MARKETPLACE,
        "external_user_id": conta_id,
        "access_token_encrypted": _criptografar(
            str(tokens["access_token"])
        ),
        "refresh_token_encrypted": _criptografar(
            str(tokens["refresh_token"])
        ),
        "scope": str(tokens["scope"]),
        "expires_at": _formatar_data_hora(
            agora + timedelta(seconds=int(tokens["expires_in"]))
        ),
        "updated_at": _formatar_data_hora(agora),
        "refresh_lease_id": None,
        "refresh_lease_until": None,
    }
    (
        cliente.table("marketplace_connections")
        .upsert(payload, on_conflict="tenant_id,marketplace")
        .execute()
    )


def processar_callback_oauth() -> None:
    callback = st.session_state.pop(_CHAVE_CALLBACK, None)
    if not isinstance(callback, dict):
        return

    state = str(callback.get("state", ""))
    if not state:
        st.error(
            "A resposta do Mercado Livre não incluiu o estado de segurança. "
            "Inicie a conexão novamente."
        )
        return

    try:
        transacao = _consumir_transacao_oauth(state)
        erro_provedor = str(callback.get("error", ""))
        if erro_provedor:
            st.error(
                "O Mercado Livre não autorizou a conexão. Inicie novamente "
                "se desejar."
            )
            return

        codigo = str(callback.get("code", ""))
        if not codigo:
            raise RuntimeError(
                "O Mercado Livre não retornou um código de autorização."
            )
        verificador = _descriptografar(
            str(transacao["code_verifier_encrypted"])
        )
        tokens = _trocar_codigo(codigo, verificador)
        _salvar_tokens(tokens, obter_tenant_id())
    except (APIError, RuntimeError) as erro:
        mensagem = erro.message if isinstance(erro, APIError) else str(erro)
        st.error(f"Não foi possível concluir a conexão com o Mercado Livre: {mensagem}")
        return

    st.session_state.pop(_CHAVE_URL_AUTORIZACAO, None)
    st.success(
        "Conta Mercado Livre conectada. As credenciais foram armazenadas "
        "criptografadas no tenant DEV."
    )


def _obter_conexao(
    *,
    incluir_tokens: bool = False,
) -> dict[str, Any] | None:
    colunas = (
        "external_user_id,access_token_encrypted,refresh_token_encrypted,"
        "expires_at,scope,refresh_lease_id,refresh_lease_until"
        if incluir_tokens
        else "external_user_id,expires_at,scope"
    )
    conexoes = (
        obter_cliente_supabase()
        .table("marketplace_connections")
        .select(colunas)
        .eq("tenant_id", obter_tenant_id())
        .eq("marketplace", _NOME_MARKETPLACE)
        .limit(1)
        .execute()
        .data
        or []
    )
    if not conexoes:
        return None
    return conexoes[0]


def _expira_em(conexao: dict[str, Any]) -> datetime:
    return datetime.fromisoformat(
        str(conexao["expires_at"]).replace("Z", "+00:00")
    )


def _reivindicar_lock_refresh(lease_id: str) -> bool:
    resposta = (
        obter_cliente_supabase()
        .rpc(
            "claim_marketplace_token_refresh",
            {
                "target_tenant_id": obter_tenant_id(),
                "target_lease_id": lease_id,
            },
        )
        .execute()
    )
    return resposta.data is True


def _liberar_lock_refresh(lease_id: str) -> None:
    (
        obter_cliente_supabase()
        .rpc(
            "release_marketplace_token_refresh",
            {
                "target_tenant_id": obter_tenant_id(),
                "target_lease_id": lease_id,
            },
        )
        .execute()
    )


def _renovar_tokens(
    conexao: dict[str, Any],
    tenant_id: str,
) -> str:
    lease_id = str(uuid4())
    if not _reivindicar_lock_refresh(lease_id):
        for _ in range(10):
            sleep(0.5)
            conexao_atualizada = _obter_conexao(incluir_tokens=True)
            if conexao_atualizada is None:
                raise RuntimeError(
                    "A conexão com o Mercado Livre foi removida."
                )
            if _expira_em(conexao_atualizada) > (
                _agora_utc() + _ANTECEDENCIA_REFRESH
            ):
                return _descriptografar(
                    str(conexao_atualizada["access_token_encrypted"])
                )
        raise RuntimeError(
            "A renovação do token já está em andamento. Tente novamente "
            "em alguns segundos."
        )

    try:
        conexao = _obter_conexao(incluir_tokens=True)
        if conexao is None:
            raise RuntimeError(
                "A conexão com o Mercado Livre foi removida."
            )
        configuracao = _obter_configuracao_ml()
        tokens = _solicitar_token({
            "grant_type": "refresh_token",
            "client_id": configuracao["client_id"],
            "client_secret": configuracao["client_secret"],
            "refresh_token": _descriptografar(
                str(conexao["refresh_token_encrypted"])
            ),
        })
        if str(tokens["user_id"]) != str(conexao["external_user_id"]):
            raise RuntimeError(
                "O Mercado Livre retornou uma conta diferente durante a "
                "renovação. Desconecte e autorize a conta correta."
            )

        agora = _agora_utc()
        resposta = (
            obter_cliente_supabase()
            .table("marketplace_connections")
            .update({
                "access_token_encrypted": _criptografar(
                    str(tokens["access_token"])
                ),
                "refresh_token_encrypted": _criptografar(
                    str(tokens["refresh_token"])
                ),
                "scope": str(tokens["scope"]),
                "expires_at": _formatar_data_hora(
                    agora + timedelta(seconds=int(tokens["expires_in"]))
                ),
                "updated_at": _formatar_data_hora(agora),
                "refresh_lease_id": None,
                "refresh_lease_until": None,
            })
            .eq("tenant_id", tenant_id)
            .eq("marketplace", _NOME_MARKETPLACE)
            .eq("refresh_lease_id", lease_id)
            .select("external_user_id")
            .execute()
        )
        if not resposta.data:
            raise RuntimeError(
                "O token foi renovado, mas não foi possível persistir a "
                "rotação segura no banco. Reautorize a conta antes de "
                "continuar."
            )
        return str(tokens["access_token"])
    finally:
        _liberar_lock_refresh(lease_id)


def obter_access_token_mercadolivre() -> str:
    if not is_database_mode():
        raise RuntimeError(
            "A API do Mercado Livre exige uma conexão no ambiente Supabase DEV."
        )
    tenant_id = obter_tenant_id()
    conexao = _obter_conexao(incluir_tokens=True)
    if conexao is None:
        raise RuntimeError("Nenhuma conta do Mercado Livre está conectada.")
    if _expira_em(conexao) <= _agora_utc() + _ANTECEDENCIA_REFRESH:
        return _renovar_tokens(conexao, tenant_id)
    return _descriptografar(str(conexao["access_token_encrypted"]))


def _validar_conexao() -> str:
    access_token = obter_access_token_mercadolivre()
    try:
        resposta = requests.get(
            _URL_USUARIO,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=_TIMEOUT_REQUISICAO,
        )
    except requests.RequestException as erro:
        raise RuntimeError(
            "Não foi possível comunicar com a API do Mercado Livre."
        ) from erro

    if not resposta.ok:
        raise RuntimeError(
            "A API do Mercado Livre recusou a validação da conexão "
            f"(HTTP {resposta.status_code}). Reautorize a conta se o token "
            "tiver sido revogado."
        )
    try:
        dados = resposta.json()
    except requests.JSONDecodeError as erro:
        raise RuntimeError(
            "A API do Mercado Livre retornou uma resposta inválida."
        ) from erro

    if not isinstance(dados, dict) or not dados.get("id"):
        raise RuntimeError(
            "A API do Mercado Livre não retornou o identificador da conta."
        )
    conta_id = str(dados["id"])
    conexao = _obter_conexao()
    if conexao is None or str(conexao["external_user_id"]) != conta_id:
        raise RuntimeError(
            "A conta retornada pela API não corresponde à conexão armazenada."
        )
    return conta_id


def _remover_conexao() -> None:
    (
        obter_cliente_supabase()
        .table("marketplace_connections")
        .delete()
        .eq("tenant_id", obter_tenant_id())
        .eq("marketplace", _NOME_MARKETPLACE)
        .execute()
    )
    st.session_state.pop(_CHAVE_URL_AUTORIZACAO, None)


def mostrar_conexao_mercadolivre() -> None:
    if not is_database_mode():
        return

    st.subheader("Conexão com o Mercado Livre")
    try:
        _obter_configuracao_ml()
        conexao = _obter_conexao()
    except (APIError, RuntimeError) as erro:
        mensagem = erro.message if isinstance(erro, APIError) else str(erro)
        st.info(mensagem)
        return

    if conexao is None:
        st.caption(
            "Conecte sua conta para habilitar a leitura de dados pelo "
            "Mercado Livre. A autorização é feita no site oficial."
        )
        if st.button(
            "Iniciar conexão com Mercado Livre",
            key="mi_ml_start_connection",
        ):
            try:
                st.session_state[_CHAVE_URL_AUTORIZACAO] = (
                    iniciar_conexao_mercadolivre()
                )
            except (APIError, RuntimeError) as erro:
                mensagem = (
                    erro.message if isinstance(erro, APIError) else str(erro)
                )
                st.error(mensagem)
        url_autorizacao = st.session_state.get(_CHAVE_URL_AUTORIZACAO)
        if isinstance(url_autorizacao, str) and url_autorizacao:
            st.link_button(
                "Autorizar no Mercado Livre",
                url_autorizacao,
                type="primary",
            )
        return

    st.success(
        "Conta conectada — identificador Mercado Livre: "
        f"{conexao['external_user_id']}."
    )
    expiracao = _expira_em(conexao)
    st.caption(
        "Token de acesso expira em "
        f"{expiracao.astimezone().strftime('%d/%m/%Y %H:%M %Z')}. "
        "A renovação será feita antes de uma chamada à API."
    )
    coluna_validar, coluna_remover = st.columns(2)
    with coluna_validar:
        if st.button(
            "Validar conexão",
            key="mi_ml_validate_connection",
        ):
            try:
                conta_id = _validar_conexao()
            except (APIError, RuntimeError) as erro:
                mensagem = erro.message if isinstance(erro, APIError) else str(erro)
                st.error(mensagem)
            else:
                st.success(
                    f"Conexão válida para a conta Mercado Livre {conta_id}."
                )
    with coluna_remover:
        if st.button(
            "Remover conexão deste painel",
            key="mi_ml_remove_connection",
        ):
            try:
                _remover_conexao()
            except APIError as erro:
                st.error(
                    "Não foi possível remover a conexão do tenant: "
                    f"{erro.message}"
                )
            else:
                st.success(
                    "Credenciais removidas do tenant. Para revogar a "
                    "autorização no Mercado Livre, faça isso também nas "
                    "configurações da sua conta."
                )
                st.rerun()
