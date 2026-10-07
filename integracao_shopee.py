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

from autenticacao import obter_configuracao, obter_origem_configuracao
from armazenamento import (
    is_database_mode,
    obter_cliente_supabase,
    obter_tenant_id,
)

_NOME_MARKETPLACE = "Shopee"
_CHAVE_CALLBACK = "_mi_shopee_oauth_callback"
_CHAVE_URL_AUTORIZACAO = "_mi_shopee_authorization_url"
_URL_AUTORIZACAO = "https://partner.shopeemobile.com/api/v2/shop/auth_partner"
_URL_TOKEN = "https://partner.shopeemobile.com/api/v2/auth/token/get"
_TIMEOUT_REQUISICAO = (5, 15)
_ANTECEDENCIA_REFRESH = timedelta(minutes=2)
_MENSAGEM_CREDENCIAIS_PENDENTES = (
    "A Shopee precisa de credenciais válidas do Open Platform, callback "
    "registrado e chave de criptografia para este ambiente."
)
_SUFIXOS_CONFIGURACAO = {
    "app_id": "APP_ID",
    "app_secret": "APP_SECRET",
    "redirect_uri": "REDIRECT_URI",
    "token_encryption_key": "TOKEN_ENCRYPTION_KEY",
}


def _nomes_configuracao_shopee(ambiente: str) -> dict[str, str]:
    prefixo = "SHOPEE_DEV" if ambiente == "development" else "SHOPEE_PROD"
    return {
        chave: f"{prefixo}_{sufixo}"
        for chave, sufixo in _SUFIXOS_CONFIGURACAO.items()
    }


def _obter_usuario_id() -> str:
    usuario_id = st.session_state.get("_mi_supabase_user_id")
    if not usuario_id:
        raise RuntimeError(
            "A identidade autenticada não está disponível para iniciar a "
            "autorização Shopee. Entre novamente."
        )
    return str(usuario_id)


def _agora_utc() -> datetime:
    return datetime.now(timezone.utc)


def _formatar_data_hora(valor: datetime) -> str:
    return valor.astimezone(timezone.utc).isoformat()


def _fernet() -> Fernet:
    ambiente = obter_configuracao("MI_ENV")
    if ambiente not in {"development", "production"}:
        raise RuntimeError(
            "A criptografia dos tokens Shopee exige MI_ENV como "
            "'development' ou 'production'."
        )
    nome_chave = _nomes_configuracao_shopee(ambiente)["token_encryption_key"]
    chave = obter_configuracao(nome_chave, preferir_secrets=True)
    if not chave and ambiente == "development":
        chave = obter_configuracao(
            "SHOPEE_TOKEN_ENCRYPTION_KEY",
            preferir_secrets=True,
        )
    if not chave or not str(chave).strip():
        raise RuntimeError(
            f"Configure {nome_chave} para persistir tokens da Shopee "
            "criptografados."
        )
    try:
        return Fernet(chave.encode("ascii"))
    except (UnicodeEncodeError, ValueError) as erro:
        raise RuntimeError(
            f"{nome_chave} não é uma chave Fernet válida."
        ) from erro


def _criptografar(valor: str) -> str:
    return _fernet().encrypt(valor.encode("utf-8")).decode("ascii")


def _descriptografar(valor: str) -> str:
    try:
        return _fernet().decrypt(valor.encode("ascii")).decode("utf-8")
    except (InvalidToken, UnicodeEncodeError, UnicodeDecodeError) as erro:
        raise RuntimeError(
            "Não foi possível descriptografar as credenciais da Shopee. "
            "Verifique a chave Fernet configurada para este ambiente."
        ) from erro


def _gerar_pkce() -> tuple[str, str]:
    verificador = token_urlsafe(64)
    resumo = sha256(verificador.encode("ascii")).digest()
    desafio = urlsafe_b64encode(resumo).rstrip(b"=").decode("ascii")
    return verificador, desafio


def _url_de_autorizacao(
    client_id: str,
    redirect_uri: str,
    state: str,
    code_challenge: str | None = None,
) -> str:
    parametros = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "state": state,
    }
    if code_challenge:
        parametros["code_challenge"] = code_challenge
        parametros["code_challenge_method"] = "S256"
    return f"{_URL_AUTORIZACAO}?{urlencode(parametros)}"


def _obter_configuracao_shopee() -> dict[str, str]:
    """Lê e valida as configurações necessárias do app Shopee."""
    ambiente = obter_configuracao("MI_ENV")
    if ambiente not in {"development", "production"}:
        raise RuntimeError(
            "A integração Shopee exige MI_ENV='development' ou "
            "MI_ENV='production'."
        )

    nomes_configuracao = _nomes_configuracao_shopee(ambiente)
    configuracao = {
        chave: obter_configuracao(nome, preferir_secrets=True)
        for chave, nome in nomes_configuracao.items()
    }
    if ambiente == "development":
        for campo, nome_legado in {
            "app_id": "SHOPEE_APP_ID",
            "app_secret": "SHOPEE_APP_SECRET",
            "redirect_uri": "SHOPEE_REDIRECT_URI",
            "token_encryption_key": "SHOPEE_TOKEN_ENCRYPTION_KEY",
        }.items():
            if not configuracao.get(campo):
                configuracao[campo] = obter_configuracao(
                    nome_legado,
                    preferir_secrets=True,
                )

    faltantes = [
        nomes_configuracao[campo]
        for campo in _SUFIXOS_CONFIGURACAO
        if not configuracao.get(campo)
        or not str(configuracao.get(campo, "")).strip()
    ]
    if faltantes:
        raise RuntimeError(
            f"Configure os secrets do ambiente {ambiente} antes da "
            "autenticação Shopee: "
            + ", ".join(sorted(set(faltantes)))
            + "."
        )

    valores = {chave: str(valor) for chave, valor in configuracao.items()}
    redirect_uri = valores["redirect_uri"]
    redirect = urlparse(redirect_uri)
    if (
        redirect_uri != redirect_uri.strip()
        or redirect.scheme not in {"https", "http"}
        or not redirect.netloc
        or redirect.username
        or redirect.password
        or redirect.query
        or redirect.fragment
        or (ambiente == "production" and redirect.scheme != "https")
    ):
        raise RuntimeError(
            f"{nomes_configuracao['redirect_uri']} precisa ser uma URL fixa, "
            "sem credenciais, query string ou fragmento e compatível com o "
            "callback do app. Em production, use HTTPS."
        )
    return valores


def _token_da_resposta(dados: dict[str, object]) -> dict[str, str | int]:
    if not isinstance(dados, dict):
        raise RuntimeError(
            "A resposta OAuth da Shopee não retornou um payload válido."
        )

    codigo = dados.get("code")
    mensagem = dados.get("message")
    payload = dados.get("data")
    if isinstance(payload, dict):
        access_token = payload.get("access_token")
        refresh_token = payload.get("refresh_token")
        expires_in = payload.get("expires_in")
        shop_id = payload.get("shop_id")
    else:
        access_token = None
        refresh_token = None
        expires_in = None
        shop_id = None

    if (
        not isinstance(codigo, (int, str))
        or str(codigo) != "0"
        or not isinstance(access_token, str)
        or not access_token.strip()
        or not isinstance(refresh_token, str)
        or not refresh_token.strip()
        or not isinstance(expires_in, int)
        or expires_in <= 0
    ):
        raise RuntimeError(
            "A Shopee respondeu com erro de autorização ou sem tokens válidos. "
            f"Código: {codigo}; mensagem: {mensagem or 'sem detalhe'}."
        )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_in": expires_in,
        "shop_id": str(shop_id or ""),
    }


def _solicitar_token_shopee(dados: dict[str, str]) -> dict[str, str | int]:
    try:
        resposta = requests.post(
            _URL_TOKEN,
            json=dados,
            timeout=_TIMEOUT_REQUISICAO,
        )
    except requests.RequestException as erro:
        raise RuntimeError(
            "Não foi possível comunicar com o serviço OAuth da Shopee. "
            "Verifique a rede e os secrets do Open Platform."
        ) from erro

    try:
        corpo = resposta.json()
    except requests.JSONDecodeError as erro:
        raise RuntimeError(
            "A Shopee retornou uma resposta OAuth inválida para o token."
        ) from erro

    if not resposta.ok:
        mensagem = corpo.get("message") if isinstance(corpo, dict) else None
        codigo = corpo.get("code") if isinstance(corpo, dict) else None
        raise RuntimeError(
            "A Shopee recusou a troca do código OAuth "
            f"(HTTP {resposta.status_code}; código {codigo or 'desconhecido'}; "
            f"mensagem {mensagem or 'sem detalhe'})."
        )

    return _token_da_resposta(corpo)


def _trocar_codigo_shopee(
    codigo: str,
    verificador: str | None = None,
) -> dict[str, str | int]:
    configuracao = _obter_configuracao_shopee()
    payload = {
        "app_key": configuracao["app_id"],
        "app_secret": configuracao["app_secret"],
        "code": codigo,
        "redirect_uri": configuracao["redirect_uri"],
        "grant_type": "authorization_code",
    }
    if verificador:
        payload["code_verifier"] = verificador
    return _solicitar_token_shopee(payload)


def _salvar_tokens_shopee(
    tokens: dict[str, str | int],
    tenant_id: str,
) -> None:
    cliente = obter_cliente_supabase()
    shop_id = str(tokens.get("shop_id") or "")
    if not shop_id:
        raise RuntimeError(
            "A Shopee não retornou um identificador de loja para persistir a "
            "conexão do tenant."
        )

    agora = _agora_utc()
    payload = {
        "tenant_id": tenant_id,
        "marketplace": _NOME_MARKETPLACE,
        "external_user_id": shop_id,
        "access_token_encrypted": _criptografar(str(tokens["access_token"])),
        "refresh_token_encrypted": _criptografar(str(tokens["refresh_token"])),
        "scope": "shop",
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


def _obter_conexao_shopee(*, incluir_tokens: bool = False) -> dict[str, Any] | None:
    colunas = (
        "external_user_id,access_token_encrypted,refresh_token_encrypted,"
        "expires_at,scope,refresh_lease_id,refresh_lease_until"
        if incluir_tokens
        else "external_user_id,expires_at,scope"
    )
    resposta = (
        obter_cliente_supabase()
        .table("marketplace_connections")
        .select(colunas)
        .eq("tenant_id", obter_tenant_id())
        .eq("marketplace", _NOME_MARKETPLACE)
        .limit(1)
        .execute()
    )
    conexoes = resposta.data or []
    if not conexoes:
        return None
    return conexoes[0]


def _expira_em_shopee(conexao: dict[str, Any]) -> datetime:
    valor = conexao.get("expires_at")
    if not isinstance(valor, str) or not valor.strip():
        raise RuntimeError(
            "A conexão da Shopee não está persistindo uma expiração válida. "
            "Reautorização necessária."
        )
    try:
        return datetime.fromisoformat(valor.replace("Z", "+00:00"))
    except ValueError as erro:
        raise RuntimeError(
            "A conexão da Shopee retornou uma expiração inválida. "
            "Reautorização necessária."
        ) from erro


def _reivindicar_lock_refresh_shopee(lease_id: str) -> bool:
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


def _liberar_lock_refresh_shopee(lease_id: str) -> None:
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


def _renovar_tokens_shopee(
    conexao: dict[str, Any],
    tenant_id: str,
) -> str:
    lease_id = str(uuid4())
    if not _reivindicar_lock_refresh_shopee(lease_id):
        for _ in range(10):
            sleep(0.5)
            conexao_atualizada = _obter_conexao_shopee(incluir_tokens=True)
            if conexao_atualizada is None:
                raise RuntimeError("A conexão da Shopee foi removida.")
            if _expira_em_shopee(conexao_atualizada) > (
                _agora_utc() + _ANTECEDENCIA_REFRESH
            ):
                return _descriptografar(
                    str(conexao_atualizada["access_token_encrypted"])
                )
        raise RuntimeError(
            "A renovação do token da Shopee já está em andamento. "
            "Tente novamente em alguns segundos."
        )

    try:
        conexao = _obter_conexao_shopee(incluir_tokens=True)
        if conexao is None:
            raise RuntimeError("A conexão da Shopee foi removida.")
        configuracao = _obter_configuracao_shopee()
        refresh_token = _descriptografar(
            str(conexao["refresh_token_encrypted"])
        )
        tokens = _solicitar_token_shopee({
            "app_key": configuracao["app_id"],
            "app_secret": configuracao["app_secret"],
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        })
        if str(tokens.get("shop_id") or "") and str(tokens["shop_id"]) != str(conexao["external_user_id"]):
            raise RuntimeError(
                "A loja retornada pela Shopee durante a renovação não corresponde à "
                "conexão armazenada. Reautorização necessária."
            )

        agora = _agora_utc()
        payload = {
            "access_token_encrypted": _criptografar(str(tokens["access_token"])),
            "refresh_token_encrypted": _criptografar(str(tokens["refresh_token"])),
            "expires_at": _formatar_data_hora(
                agora + timedelta(seconds=int(tokens["expires_in"]))
            ),
            "updated_at": _formatar_data_hora(agora),
        }
        resposta = (
            obter_cliente_supabase()
            .table("marketplace_connections")
            .update(payload)
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
        _liberar_lock_refresh_shopee(lease_id)


def obter_access_token_shopee() -> str:
    if not is_database_mode():
        raise RuntimeError(
            "A API da Shopee exige uma conexão em um ambiente Supabase."
        )

    tenant_id = obter_tenant_id()
    conexao = _obter_conexao_shopee(incluir_tokens=True)
    if conexao is None:
        raise RuntimeError("Nenhuma conta da Shopee está conectada.")
    if _expira_em_shopee(conexao) <= _agora_utc() + _ANTECEDENCIA_REFRESH:
        return _renovar_tokens_shopee(conexao, tenant_id)
    return _descriptografar(str(conexao["access_token_encrypted"]))


def _validar_conexao_shopee() -> str:
    access_token = obter_access_token_shopee()
    try:
        resposta = requests.get(
            "https://partner.shopeemobile.com/api/v2/shop/get_shop_info",
            params={"access_token": access_token},
            timeout=_TIMEOUT_REQUISICAO,
        )
    except requests.RequestException as erro:
        raise RuntimeError(
            "Não foi possível comunicar com a API da Shopee."
        ) from erro

    if not resposta.ok:
        raise RuntimeError(
            "A API da Shopee recusou a validação da conexão "
            f"(HTTP {resposta.status_code}). Reautorize a conta se o token "
            "tiver sido revogado."
        )
    try:
        dados = resposta.json()
    except requests.JSONDecodeError as erro:
        raise RuntimeError(
            "A API da Shopee retornou uma resposta inválida."
        ) from erro

    if not isinstance(dados, dict):
        raise RuntimeError(
            "A API da Shopee não retornou informações válidas da loja."
        )
    codigo = dados.get("code")
    if isinstance(codigo, (int, str)) and str(codigo) not in {"0", "2000"}:
        raise RuntimeError(
            "A API da Shopee rejeitou a validação da conexão. "
            f"Resposta: {dados}."
        )
    conexao = _obter_conexao_shopee()
    if conexao is None:
        raise RuntimeError("A conexão da Shopee foi removida antes da confirmação.")
    return str(conexao["external_user_id"])


def _remover_conexao_shopee() -> None:
    (
        obter_cliente_supabase()
        .table("marketplace_connections")
        .delete()
        .eq("tenant_id", obter_tenant_id())
        .eq("marketplace", _NOME_MARKETPLACE)
        .execute()
    )
    st.session_state.pop(_CHAVE_URL_AUTORIZACAO, None)


def _diagnostico_configuracao_shopee() -> str:
    """Resumo seguro da origem dos secrets sem expor valores sensíveis."""
    ambiente = obter_configuracao("MI_ENV")
    nomes_configuracao = _nomes_configuracao_shopee(ambiente)
    origens = {
        campo: obter_origem_configuracao(nome, preferir_secrets=True)
        for campo, nome in nomes_configuracao.items()
    }
    if ambiente == "development":
        for campo, nome_legado in {
            "app_id": "SHOPEE_APP_ID",
            "app_secret": "SHOPEE_APP_SECRET",
            "redirect_uri": "SHOPEE_REDIRECT_URI",
            "token_encryption_key": "SHOPEE_TOKEN_ENCRYPTION_KEY",
        }.items():
            if origens[campo] == "ausente":
                origens[campo] = obter_origem_configuracao(
                    nome_legado,
                    preferir_secrets=True,
                )
    return (
        "Diagnóstico seguro: "
        + ", ".join(
            f"{campo} em {origens[campo]}"
            for campo in sorted(origens)
        )
        + "."
    )


def _query_parametro_unico(nome: str) -> str:
    valores = st.query_params.get_all(nome)
    if len(valores) != 1:
        return ""
    return valores[0]


def capturar_callback_oauth_shopee() -> None:
    """Captura os parâmetros de retorno do callback OAuth da Shopee."""
    nomes = ("code", "state", "error", "error_description", "shop_id")
    if not any(nome in st.query_params for nome in nomes):
        return

    callback = {nome: _query_parametro_unico(nome) for nome in nomes}
    st.session_state[_CHAVE_CALLBACK] = callback
    for nome in nomes:
        if nome in st.query_params:
            del st.query_params[nome]


def iniciar_conexao_shopee() -> str:
    """Gera a URL de autorização OAuth do Open Platform Shopee."""
    if not is_database_mode():
        raise RuntimeError(
            "A conexão com marketplaces exige um ambiente Supabase."
        )

    configuracao = _obter_configuracao_shopee()
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
    url_autorizacao = _url_de_autorizacao(
        configuracao["app_id"],
        configuracao["redirect_uri"],
        state,
        desafio,
    )
    st.session_state[_CHAVE_URL_AUTORIZACAO] = url_autorizacao
    return url_autorizacao


def _consumir_transacao_oauth(state: str) -> dict[str, str]:
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
            "A resposta OAuth da Shopee não corresponde a uma autorização "
            "pendente desta conta. Inicie a conexão novamente."
        )

    transacao = linhas[0]
    expires_at = transacao.get("expires_at")
    if not isinstance(expires_at, str) or not expires_at.strip():
        raise RuntimeError(
            "A autorização da Shopee não está vinculada a uma data de expiração "
            "válida. Inicie a conexão novamente."
        )
    try:
        expira_em = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    except ValueError as erro:
        raise RuntimeError(
            "A autorização da Shopee retornou uma expiração inválida. "
            "Inicie a conexão novamente."
        ) from erro
    if expira_em <= _agora_utc():
        raise RuntimeError(
            "A autorização da Shopee expirou. Inicie a conexão novamente."
        )
    return transacao


def processar_callback_shopee() -> None:
    """Processa o retorno do OAuth da Shopee sem bloquear a tela principal."""
    callback = st.session_state.pop(_CHAVE_CALLBACK, None)
    if not isinstance(callback, dict):
        return

    state = str(callback.get("state", "")).strip()
    if not state:
        st.error(
            "A resposta da Shopee não incluiu o estado de segurança. "
            "Inicie a conexão novamente."
        )
        return

    try:
        transacao = _consumir_transacao_oauth(state)
        erro_provedor = str(callback.get("error", "")).strip()
        if erro_provedor:
            st.error(
                "A Shopee não autorizou a conexão. Inicie a autorização "
                "novamente para tentar outra vez."
            )
            return

        codigo = str(callback.get("code", "")).strip()
        if not codigo:
            raise RuntimeError(
                "A Shopee não retornou um código de autorização."
            )

        verificador = None
        valor_verificador = transacao.get("code_verifier_encrypted")
        if isinstance(valor_verificador, str) and valor_verificador.strip():
            verificador = _descriptografar(valor_verificador)

        tokens = _trocar_codigo_shopee(codigo, verificador)
        _salvar_tokens_shopee(tokens, obter_tenant_id())
        st.session_state.pop(_CHAVE_URL_AUTORIZACAO, None)
        st.success(
            "Autorização da Shopee recebida e armazenada com criptografia. "
            "O fluxo de sincronização de pedidos e estoque continua em "
            "etapas separadas até a validação final do Open Platform."
        )
    except RuntimeError as erro:
        st.error(f"Não foi possível concluir a conexão com a Shopee: {erro}")


def status_integracao_shopee() -> str:
    """Retorna um resumo legível do estado atual da integração."""
    if not is_database_mode():
        return "Disponível somente em ambiente Supabase (DEV ou PROD)."

    try:
        _obter_configuracao_shopee()
    except RuntimeError as erro:
        mensagem = str(erro)
        return (
            "Configuração pendente: " + mensagem
            if "Configure os secrets do ambiente" in mensagem
            else "Configuração inválida: " + mensagem
        )

    try:
        conexao = _obter_conexao_shopee()
    except RuntimeError:
        conexao = None

    if conexao is None:
        return (
            "Pronta para OAuth: os secrets essenciais do app Shopee foram "
            "identificados e o fluxo de conexão foi preparado em base segura "
            "para o Open Platform."
        )

    expiracao = _expira_em_shopee(conexao)
    agora = _agora_utc()
    if expiracao <= agora:
        return (
            "Conectada à loja Shopee "
            f"{conexao.get('external_user_id', 'desconhecida')}, mas o token "
            "já expirou e precisa de renovação."
        )
    if expiracao <= agora + timedelta(minutes=2):
        return (
            "Conectada à loja Shopee "
            f"{conexao.get('external_user_id', 'desconhecida')}; o token expira "
            f"em {expiracao.astimezone().strftime('%d/%m/%Y %H:%M %Z')} e será "
            "renovado antes da próxima chamada."
        )

    return (
        "Conectada à loja Shopee "
        f"{conexao.get('external_user_id', 'desconhecida')} e o token fica "
        f"válido até {expiracao.astimezone().strftime('%d/%m/%Y %H:%M %Z')}."
    )


def mostrar_conexao_shopee() -> None:
    """Exibe o estado da integração Shopee sem bloquear o restante do app."""
    st.markdown("### Shopee")
    status = status_integracao_shopee()
    if not is_database_mode():
        st.info(
            "A integração da Shopee exige um ambiente Supabase para ser "
            "validada."
        )
        st.caption(status)
        return

    try:
        _obter_configuracao_shopee()
    except RuntimeError:
        st.warning(_MENSAGEM_CREDENCIAIS_PENDENTES)
        st.caption(status)
        st.info(
            "Configure as credenciais do Open Platform e o callback aprovado "
            "para este ambiente."
        )
        return

    try:
        conexao = _obter_conexao_shopee()
    except RuntimeError:
        conexao = None

    if conexao is None:
        st.info(
            "Configuração do app Shopee detectada para este ambiente. "
            "A base OAuth e o callback "
            "estão preparados e a sincronização de pedidos/estoque foi "
            "implementada em uma camada dedicada para a API da Shopee."
        )
        st.caption(status)
        st.caption(_diagnostico_configuracao_shopee())
        if st.button("Iniciar conexão com Shopee", key="mi_shopee_start_connection"):
            try:
                st.session_state[_CHAVE_URL_AUTORIZACAO] = iniciar_conexao_shopee()
            except RuntimeError as erro:
                st.error(str(erro))
        url_autorizacao = st.session_state.get(_CHAVE_URL_AUTORIZACAO)
        if isinstance(url_autorizacao, str) and url_autorizacao:
            st.link_button(
                "Autorizar na Shopee",
                url_autorizacao,
                type="primary",
            )
        return

    st.info(
        "Configuração do app Shopee detectada para este ambiente. "
        "A base OAuth e o callback "
        "estão preparados e a sincronização de pedidos/estoque foi "
        "implementada em uma camada dedicada para a API da Shopee."
    )
    st.caption(status)
    st.success(
        "Loja conectada — identificador da loja Shopee: "
        f"{conexao['external_user_id']}."
    )
    st.caption(_diagnostico_configuracao_shopee())

    with st.expander("Validar e gerenciar conexão"):
        if st.button("Validar conexão", key="mi_shopee_validate_connection"):
            try:
                conta_id = _validar_conexao_shopee()
            except RuntimeError as erro:
                st.error(str(erro))
            else:
                st.success(f"Conexão válida para a loja Shopee {conta_id}.")
        if st.button("Remover conexão", key="mi_shopee_remove_connection"):
            try:
                _remover_conexao_shopee()
            except RuntimeError as erro:
                st.error(str(erro))
            else:
                st.success("Conexão da Shopee removida deste tenant.")


def exigir_integracao_shopee() -> None:
    """Valida que o tenant e os secrets da Shopee estejam prontos."""
    if not is_database_mode():
        raise RuntimeError(
            "A integração da Shopee exige um ambiente Supabase para "
            "validar a conexão e a sincronização."
        )
    _obter_configuracao_shopee()
    if _obter_conexao_shopee() is None:
        raise RuntimeError(
            "Nenhuma conta da Shopee está conectada neste tenant. "
            "Inicie a autenticação antes de sincronizar dados."
        )
