import os

import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError
from postgrest.exceptions import APIError
from supabase import Client, create_client
from supabase_auth.errors import AuthApiError


_CHAVES_SESSAO = (
    "_mi_supabase_access_token",
    "_mi_supabase_refresh_token",
    "_mi_supabase_email",
    "_mi_supabase_user_id",
    "_mi_supabase_client",
    "_mi_tenant_id",
)


def _configuracao(nome: str) -> str | None:
    valor_ambiente = os.environ.get(nome)
    if valor_ambiente:
        return valor_ambiente

    try:
        valor_segredo = st.secrets.get(nome)
    except StreamlitSecretNotFoundError:
        return None

    return str(valor_segredo) if valor_segredo else None


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


def _limpar_sessao() -> None:
    for chave in _CHAVES_SESSAO:
        st.session_state.pop(chave, None)


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


def _renderizar_login(cliente: Client) -> None:
    st.title("Acesso privado")
    st.caption("Entre com sua conta autorizada para acessar o painel.")

    with st.form("mi_login_form"):
        email = st.text_input("E-mail", autocomplete="email").strip()
        senha = st.text_input(
            "Senha",
            type="password",
            autocomplete="current-password",
        )
        enviar = st.form_submit_button("Entrar", type="primary")

    if not enviar:
        return
    if not email or not senha:
        st.error("Informe o e-mail e a senha.")
        return

    try:
        resposta = cliente.auth.sign_in_with_password(
            {"email": email, "password": senha}
        )
    except AuthApiError as erro:
        st.error(
            "O Supabase recusou a autenticação: "
            f"{erro.message} "
            f"(HTTP {erro.status}, código {erro.code or 'indisponível'})."
        )
        return

    if resposta.session is None or resposta.user is None:
        st.error("O provedor de autenticação não retornou uma sessão válida.")
        return

    st.session_state["_mi_supabase_access_token"] = (
        resposta.session.access_token
    )
    st.session_state["_mi_supabase_refresh_token"] = (
        resposta.session.refresh_token
    )
    st.session_state["_mi_supabase_email"] = resposta.user.email or email
    st.session_state["_mi_supabase_user_id"] = resposta.user.id
    st.session_state["_mi_supabase_client"] = cliente
    st.rerun()


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
    access_token = st.session_state.get("_mi_supabase_access_token")
    refresh_token = st.session_state.get("_mi_supabase_refresh_token")

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
                st.session_state["_mi_supabase_user_id"] = usuario.id
                st.session_state["_mi_supabase_client"] = cliente
                try:
                    memberships = (
                        cliente.table("tenant_members")
                        .select("tenant_id")
                        .execute()
                        .data
                        or []
                    )
                except APIError as erro:
                    st.error(
                        "Não foi possível validar o vínculo desta conta "
                        f"com o tenant: {erro.message}"
                    )
                    st.stop()
                if len(memberships) != 1:
                    st.error(
                        "Esta conta precisa estar vinculada a exatamente "
                        "um tenant para acessar os dados do piloto."
                    )
                    if st.button("Sair", key="mi_logout_unlinked"):
                        cliente.auth.sign_out()
                        _limpar_sessao()
                        st.rerun()
                    st.stop()
                st.session_state["_mi_tenant_id"] = memberships[0][
                    "tenant_id"
                ]
                if st.sidebar.button("Sair", key="mi_logout"):
                    cliente.auth.sign_out()
                    _limpar_sessao()
                    st.rerun()
                st.sidebar.caption(
                    f"Acesso autenticado: "
                    f"{st.session_state['_mi_supabase_email']}"
                )
                return
            _limpar_sessao()

    _renderizar_login(cliente)
    st.stop()
