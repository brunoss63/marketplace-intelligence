import json
import os
from datetime import datetime, timedelta, timezone
from urllib.parse import unquote

import streamlit as st
import extra_streamlit_components as stx
from streamlit.errors import StreamlitSecretNotFoundError
from postgrest.exceptions import APIError
from supabase import Client, create_client
from supabase_auth.errors import AuthApiError

from componentes import renderizar_painel_login


_CHAVE_COOKIE_PROD_LIMPO = "_mi_prod_auth_cookie_cleared"
_CHAVES_SESSAO = (
    "_mi_supabase_access_token",
    "_mi_supabase_refresh_token",
    "_mi_supabase_email",
    "_mi_user_name",
    "_mi_supabase_user_id",
    "_mi_supabase_client",
    "_mi_tenant_id",
    "_mi_tenant_role",
    _CHAVE_COOKIE_PROD_LIMPO,
)
_COOKIE_SESSAO = "mi_auth_session"
_COOKIE_MANAGER_SESSAO = "_mi_auth_cookie_manager"
_DURACAO_COOKIE_SESSAO_DIAS = 30


def _nome_exibicao(usuario: object, email: str) -> str:
    metadados = getattr(usuario, "user_metadata", None) or {}
    if isinstance(metadados, dict):
        for chave in ("full_name", "name", "display_name"):
            nome = metadados.get(chave)
            if isinstance(nome, str) and nome.strip():
                return nome.strip()

    identificador = email.split("@", 1)[0]
    nome_local = " ".join(
        identificador.replace(".", " ")
        .replace("_", " ")
        .replace("-", " ")
        .split()
    )
    return nome_local.title() or "Conta"


def _valor_segredo_streamlit(nome: str) -> str | None:
    try:
        valor_segredo = st.secrets.get(nome)
    except StreamlitSecretNotFoundError:
        return None
    return str(valor_segredo) if valor_segredo else None


def _normalizar_valor_configuracao(valor: object) -> str | None:
    if valor is None:
        return None
    valor_normalizado = str(valor).strip()
    return valor_normalizado or None


def _configuracao_com_origem(
    nome: str,
    *,
    preferir_secrets: bool = False,
) -> tuple[str | None, str]:
    valor_ambiente = _normalizar_valor_configuracao(os.environ.get(nome))
    if valor_ambiente and not preferir_secrets:
        return valor_ambiente, "variável de ambiente"

    valor_segredo = _normalizar_valor_configuracao(_valor_segredo_streamlit(nome))
    if valor_segredo:
        return valor_segredo, "Streamlit Secrets"
    if valor_ambiente:
        return valor_ambiente, "variável de ambiente"
    return None, "ausente"


def _configuracao(nome: str) -> str | None:
    return _configuracao_com_origem(nome)[0]


def obter_configuracao(
    nome: str,
    *,
    preferir_secrets: bool = False,
) -> str | None:
    """Lê uma configuração do ambiente e dos Streamlit Secrets."""

    return _configuracao_com_origem(
        nome,
        preferir_secrets=preferir_secrets,
    )[0]


def obter_origem_configuracao(
    nome: str,
    *,
    preferir_secrets: bool = False,
) -> str:
    """Informa a origem selecionada para uma configuração, sem seu valor."""

    return _configuracao_com_origem(
        nome,
        preferir_secrets=preferir_secrets,
    )[1]


def _credenciais_supabase(ambiente: str) -> tuple[str | None, str | None]:
    if ambiente == "development":
        prefixo = "SUPABASE_DEV"
    elif ambiente == "production":
        prefixo = "SUPABASE_PROD"
    else:
        raise ValueError(f"Ambiente Supabase não suportado: {ambiente!r}.")

    url = _configuracao(f"{prefixo}_URL")
    chave_anonima = _configuracao(f"{prefixo}_ANON_KEY")

    if ambiente == "production":
        url = url or _configuracao("SUPABASE_URL")
        chave_anonima = chave_anonima or _configuracao("SUPABASE_ANON_KEY")

    return url, chave_anonima


def _usar_cookie_sessao(ambiente: str) -> bool:
    return ambiente == "development"


def _persistir_sessao_cookie(
    cookie_manager: stx.CookieManager,
    access_token: str,
    refresh_token: str,
    *,
    ambiente: str,
) -> None:
    if not _usar_cookie_sessao(ambiente):
        return

    valor = json.dumps(
        {
            "access_token": access_token,
            "refresh_token": refresh_token,
        },
        separators=(",", ":"),
    )
    if cookie_manager.get(_COOKIE_SESSAO) != valor:
        cookie_manager.set(
            _COOKIE_SESSAO,
            valor,
            key="mi_auth_session_set",
            path="/",
            expires_at=datetime.now(timezone.utc)
            + timedelta(days=_DURACAO_COOKIE_SESSAO_DIAS),
            max_age=_DURACAO_COOKIE_SESSAO_DIAS * 24 * 60 * 60,
            secure=_cookie_seguro(),
            same_site="lax",
        )


def _cookie_seguro() -> bool:
    return str(st.context.url or "").startswith("https://")


def _ler_sessao_cookie(
    valor: object,
) -> tuple[str, str] | None:
    if not isinstance(valor, str):
        return None
    try:
        dados = json.loads(valor)
    except json.JSONDecodeError:
        try:
            dados = json.loads(unquote(valor))
        except json.JSONDecodeError:
            return None
    if not isinstance(dados, dict):
        return None
    access_token = dados.get("access_token")
    refresh_token = dados.get("refresh_token")
    if not isinstance(access_token, str) or not access_token:
        return None
    if not isinstance(refresh_token, str) or not refresh_token:
        return None
    return access_token, refresh_token


def _remover_cookie_sessao(
    cookie_manager: stx.CookieManager,
    *,
    existe: bool = False,
) -> None:
    cookie = cookie_manager.get(_COOKIE_SESSAO)
    if cookie is not None:
        cookie_manager.delete(_COOKIE_SESSAO, key="mi_auth_session_delete")
    elif existe:
        cookie_manager.set(
            _COOKIE_SESSAO,
            "",
            path="/",
            max_age=0,
            secure=_cookie_seguro(),
            same_site="lax",
        )


def _preparar_cookie_sessao(
    cookie_manager: stx.CookieManager,
    ambiente: str,
    *,
    cookie_contexto: object | None,
) -> None:
    if _usar_cookie_sessao(ambiente):
        return
    if st.session_state.get(_CHAVE_COOKIE_PROD_LIMPO):
        return

    cookie_componente = cookie_manager.get(_COOKIE_SESSAO)
    if cookie_contexto is not None or cookie_componente is not None:
        _remover_cookie_sessao(cookie_manager, existe=True)
    st.session_state[_CHAVE_COOKIE_PROD_LIMPO] = True


def _limpar_sessao() -> None:
    cookie_manager = st.session_state.get(_COOKIE_MANAGER_SESSAO)
    if cookie_manager is not None:
        _remover_cookie_sessao(cookie_manager)
    for chave in _CHAVES_SESSAO:
        st.session_state.pop(chave, None)
    st.session_state.pop(_COOKIE_MANAGER_SESSAO, None)


def obter_cliente_supabase(*, recriar: bool = False) -> Client:
    cliente = st.session_state.get("_mi_supabase_client")
    if cliente is not None and not recriar:
        return cliente

    access_token = st.session_state.get("_mi_supabase_access_token")
    refresh_token = st.session_state.get("_mi_supabase_refresh_token")
    ambiente = _configuracao("MI_ENV")
    if ambiente not in {"development", "production"}:
        raise RuntimeError(
            "A sessão Supabase requer MI_ENV='development' ou 'production'."
        )
    url, chave_anonima = _credenciais_supabase(ambiente)
    if not access_token or not refresh_token or not url or not chave_anonima:
        raise RuntimeError(
            "A sessão Supabase não está autenticada. Entre novamente."
        )

    cliente = create_client(url, chave_anonima)
    try:
        resposta = cliente.auth.set_session(access_token, refresh_token)
    except AuthApiError as erro:
        _limpar_sessao()
        raise RuntimeError(
            "Sua sessão Supabase expirou. Entre novamente."
        ) from erro

    sessao = resposta.session
    if sessao is None:
        _limpar_sessao()
        raise RuntimeError(
            "Não foi possível restaurar sua sessão Supabase. Entre novamente."
        )

    st.session_state["_mi_supabase_access_token"] = sessao.access_token
    st.session_state["_mi_supabase_refresh_token"] = sessao.refresh_token
    if sessao.user is not None:
        st.session_state["_mi_supabase_user_id"] = sessao.user.id
    st.session_state["_mi_supabase_client"] = cliente
    return cliente


def _renderizar_login(
    cliente: Client,
    cookie_manager: stx.CookieManager,
    ambiente: str,
) -> None:
    st.markdown('<div class="mi-login-layout"></div>', unsafe_allow_html=True)
    painel, formulario = st.columns([1.05, .95], gap="large")

    with painel:
        renderizar_painel_login()

    with formulario:
        with st.container(key="mi-login-card"):
            st.markdown(
                """
                <div class="mi-login-card-heading">
                    <div class="mi-login-card-kicker">SUA OPERAÇÃO, EM FOCO</div>
                    <h2 class="mi-login-card-title">Bem-vindo de volta</h2>
                    <p class="mi-login-card-subtitle">
                        Entre com sua conta autorizada para acessar o painel.
                    </p>
                </div>
                """,
                unsafe_allow_html=True
            )

            with st.form("mi_login_form"):
                email = st.text_input(
                    "E-mail",
                    autocomplete="email",
                    placeholder="voce@empresa.com",
                ).strip()
                senha = st.text_input(
                    "Senha",
                    type="password",
                    autocomplete="current-password",
                    placeholder="Sua senha",
                )
                enviar = st.form_submit_button(
                    "Entrar no painel",
                    type="primary",
                    icon=":material/arrow_forward:",
                )

            if not enviar:
                return
            if not email or not senha:
                st.error("Informe o e-mail e a senha.")
                return

            try:
                with st.spinner("Autenticando sua conta..."):
                    resposta = cliente.auth.sign_in_with_password(
                        {"email": email, "password": senha}
                    )
            except AuthApiError as erro:
                st.error(
                    "O Supabase recusou a autenticação: "
                    f"{erro.message} "
                    f"(HTTP {erro.status}, código "
                    f"{erro.code or 'indisponível'})."
                )
                return

            if resposta.session is None or resposta.user is None:
                st.error(
                    "O provedor de autenticação não retornou uma sessão válida."
                )
                return

            st.session_state["_mi_supabase_access_token"] = (
                resposta.session.access_token
            )
            st.session_state["_mi_supabase_refresh_token"] = (
                resposta.session.refresh_token
            )
            st.session_state["_mi_supabase_email"] = (
                resposta.user.email or email
            )
            st.session_state["_mi_user_name"] = _nome_exibicao(
                resposta.user,
                resposta.user.email or email,
            )
            st.session_state["_mi_supabase_user_id"] = resposta.user.id
            st.session_state["_mi_supabase_client"] = cliente
            _persistir_sessao_cookie(
                cookie_manager,
                resposta.session.access_token,
                resposta.session.refresh_token,
                ambiente=ambiente,
            )


def obter_role_tenant_atual() -> str:
    """Retorna o papel do usuário no tenant atual (owner/member)."""
    papel = st.session_state.get("_mi_tenant_role")
    if not papel:
        raise RuntimeError(
            "O papel do usuário no tenant não foi carregado. "
            "Entre novamente para revalidar o acesso."
        )
    return str(papel)


def eh_owner_tenant() -> bool:
    """Indica se o usuário atual tem papel administrativo do tenant."""
    return obter_role_tenant_atual() == "owner"


def exigir_permissao_administrativa() -> None:
    """Bloqueia acesso administrativo até existir um papel explícito de owner."""
    if not eh_owner_tenant():
        raise RuntimeError(
            "Acesso administrativo entre tenants ainda não está habilitado "
            "para esta conta. Hoje, o tenant atual só permite acesso "
            "restrito ao próprio usuário e ao papel vinculado."
        )


def _carregar_vinculo_tenant(cliente: Client) -> tuple[str, str]:
    """Lê o tenant e o papel do usuário autenticado, sem usar service_role."""
    try:
        memberships = (
            cliente.table("tenant_members")
            .select("tenant_id, role")
            .execute()
            .data
            or []
        )
    except APIError as erro:
        raise RuntimeError(
            "Não foi possível validar o vínculo desta conta com o tenant: "
            f"{erro.message}"
        ) from erro

    if not memberships:
        raise RuntimeError(
            "Esta conta ainda não está vinculada a um tenant do piloto. "
            "Use o fluxo de onboarding para solicitar acesso."
        )
    if len(memberships) != 1:
        raise RuntimeError(
            "Esta conta precisa estar vinculada a exatamente um tenant "
            "para acessar os dados do piloto."
        )

    membro = memberships[0]
    tenant_id = str(membro.get("tenant_id") or "")
    papel = str(membro.get("role") or "member")
    if papel not in {"owner", "member"}:
        raise RuntimeError(
            "O vínculo do usuário com o tenant está em um papel inválido. "
            "A conta precisa ser revalidada no cadastro do piloto."
        )
    if not tenant_id:
        raise RuntimeError(
            "O vínculo do usuário com o tenant não retornou um identificador "
            "válido."
        )
    return tenant_id, papel


def exigir_autenticacao() -> None:
    """Bloqueia o painel até existir uma sessão Supabase autorizada."""

    ambiente = _configuracao("MI_ENV")
    if ambiente not in {"local", "development", "production"}:
        st.error(
            "Configure MI_ENV explicitamente como 'local', 'development' "
            "ou 'production'."
        )
        st.stop()

    if ambiente == "local":
        st.sidebar.caption(
            "Modo de demonstração local: autenticação desativada."
        )
        return

    url, chave_anonima = _credenciais_supabase(ambiente)
    if not url or not chave_anonima:
        prefixo = (
            "SUPABASE_DEV"
            if ambiente == "development"
            else "SUPABASE_PROD"
        )
        st.error(
            f"A autenticação de {ambiente} não está configurada. Defina "
            f"{prefixo}_URL e {prefixo}_ANON_KEY nos segredos do aplicativo."
        )
        st.stop()

    cliente = create_client(url, chave_anonima)
    cookie_manager = stx.CookieManager(key="mi-auth-cookie-manager")
    st.session_state[_COOKIE_MANAGER_SESSAO] = cookie_manager
    cookie_contexto = (
        None
        if _usar_cookie_sessao(ambiente)
        else st.context.cookies.get(_COOKIE_SESSAO)
    )
    _preparar_cookie_sessao(
        cookie_manager,
        ambiente,
        cookie_contexto=cookie_contexto,
    )
    access_token = st.session_state.get("_mi_supabase_access_token")
    refresh_token = st.session_state.get("_mi_supabase_refresh_token")
    if _usar_cookie_sessao(ambiente) and (
        not access_token or not refresh_token
    ):
        valor_cookie = st.context.cookies.get(_COOKIE_SESSAO)
        if valor_cookie is None:
            valor_cookie = cookie_manager.get(_COOKIE_SESSAO)
        sessao_cookie = _ler_sessao_cookie(valor_cookie)
        if sessao_cookie is not None:
            access_token, refresh_token = sessao_cookie
        elif valor_cookie is not None:
            _remover_cookie_sessao(cookie_manager, existe=True)

    if access_token and refresh_token:
        try:
            resposta_sessao = cliente.auth.set_session(
                access_token,
                refresh_token,
            )
            sessao = resposta_sessao.session
            resposta_usuario = (
                cliente.auth.get_user(sessao.access_token)
                if sessao is not None
                else None
            )
            usuario = (
                resposta_usuario.user
                if resposta_usuario is not None
                else None
            )
        except AuthApiError:
            _limpar_sessao()
            st.warning("Sua sessão expirou. Entre novamente.")
        else:
            if sessao is not None and usuario is not None:
                st.session_state["_mi_supabase_access_token"] = (
                    sessao.access_token
                )
                st.session_state["_mi_supabase_refresh_token"] = (
                    sessao.refresh_token
                )
                st.session_state["_mi_supabase_email"] = usuario.email or ""
                st.session_state["_mi_user_name"] = _nome_exibicao(
                    usuario,
                    usuario.email or "",
                )
                st.session_state["_mi_supabase_user_id"] = usuario.id
                st.session_state["_mi_supabase_client"] = cliente
                _persistir_sessao_cookie(
                    cookie_manager,
                    sessao.access_token,
                    sessao.refresh_token,
                    ambiente=ambiente,
                )
                try:
                    tenant_id, tenant_role = _carregar_vinculo_tenant(cliente)
                except RuntimeError as erro:
                    st.error(str(erro))
                    from administracao import mostrar_fluxo_onboarding_piloto
                    mostrar_fluxo_onboarding_piloto()
                    if st.button("Sair", key="mi_logout_unlinked"):
                        cliente.auth.sign_out()
                        _limpar_sessao()
                        st.rerun()
                    st.stop()
                st.session_state["_mi_tenant_id"] = tenant_id
                st.session_state["_mi_tenant_role"] = tenant_role
                return
            _limpar_sessao()

    _renderizar_login(cliente, cookie_manager, ambiente)
    st.stop()
