from __future__ import annotations

import uuid
from typing import Any

import pandas as pd
import streamlit as st
from postgrest.exceptions import APIError

from autenticacao import eh_owner_tenant
from armazenamento import obter_cliente_supabase, obter_tenant_id
from componentes import tabela_limpa


def _obter_usuario_id() -> str:
    usuario_id = st.session_state.get("_mi_supabase_user_id")
    if not usuario_id:
        raise RuntimeError(
            "A identidade autenticada não está disponível para registrar "
            "auditoria administrativa. Entre novamente."
        )
    return str(usuario_id)


def listar_tenants_administrados() -> list[dict[str, Any]]:
    """Lista os tenants em que a conta atual é proprietária."""
    if not eh_owner_tenant():
        return []

    cliente = obter_cliente_supabase()
    resposta = (
        cliente.table("tenant_members")
        .select("tenant_id, role")
        .eq("user_id", _obter_usuario_id())
        .eq("role", "owner")
        .execute()
    )
    return resposta.data or []


def eh_administrador_piloto() -> bool:
    """Indica se a conta atual tem a identidade global de admin do piloto."""
    try:
        resposta = obter_cliente_supabase().rpc(
            "user_is_pilot_administrator"
        ).execute()
    except APIError as erro:
        raise RuntimeError(
            "Não foi possível validar a permissão de administrador do piloto: "
            f"{erro.message}"
        ) from erro
    return resposta.data is True


def exigir_administrador_piloto() -> None:
    """Permite provisionar contas somente a administradores autorizados."""
    if not eh_administrador_piloto():
        raise RuntimeError(
            "O provisionamento de contas é restrito ao administrador "
            "explicitamente autorizado do piloto."
        )


def vincular_usuario_convidado_piloto(
    *,
    user_id: str,
    nome_tenant: str,
    papel: str = "member",
) -> dict[str, Any]:
    """Vincula ao tenant uma conta já criada no Supabase Auth."""
    exigir_administrador_piloto()

    if not user_id:
        raise RuntimeError("É obrigatório informar o ID da conta convidada.")
    if papel not in {"owner", "member"}:
        raise RuntimeError("O papel do usuário deve ser 'owner' ou 'member'.")
    try:
        user_id = str(uuid.UUID(user_id.strip()))
    except (AttributeError, ValueError) as erro:
        raise RuntimeError(
            "Informe um ID de usuário válido, copiado do Supabase Auth."
        ) from erro

    nome = (str(nome_tenant or "")).strip()
    if not nome:
        nome = f"Tenant piloto {user_id[:8]}"

    cliente = obter_cliente_supabase()
    try:
        resposta = cliente.rpc(
            "provision_pilot_user",
            {
                "p_user_id": str(user_id),
                "p_tenant_name": nome,
                "p_role": papel,
                "p_actor_tenant_id": obter_tenant_id(),
            },
        ).execute()
    except APIError as erro:
        raise RuntimeError(
            "Não foi possível vincular a conta convidada ao tenant: "
            f"{erro.message}"
        ) from erro

    resultado = resposta.data
    if isinstance(resultado, list) and resultado:
        resultado = resultado[0]
    if not isinstance(resultado, dict):
        raise RuntimeError(
            "O banco não confirmou o vínculo da conta convidada."
        )
    return resultado


def mostrar_acesso_piloto_pendente() -> None:
    """Informa que a conta autenticada ainda aguarda vínculo administrativo."""
    st.subheader("Piloto privado")
    st.info(
        "Sua conta está autenticada, mas o responsável pelo piloto ainda "
        "precisa vinculá-la ao tenant correto."
    )
    st.caption(
        "O convite do Supabase confirma sua identidade; o acesso aos dados só "
        "é liberado depois que o responsável conclui esse vínculo."
    )


def exigir_permissao_admin_tenant() -> None:
    """Garante que o usuário atual tenha papel de owner do tenant."""
    if not eh_owner_tenant():
        raise RuntimeError(
            "Acesso administrativo entre tenants ainda não está habilitado "
            "para esta conta. O tenant atual só permite acesso restrito ao "
            "usuário vinculado e ao papel declarado no tenant."
        )


def registrar_auditoria_acesso(
    *,
    acao: str,
    target_tenant_id: str | None = None,
    motivo: str = "",
) -> dict[str, Any]:
    """Registra uma ação administrativa em JSON de auditoria do tenant."""
    exigir_permissao_admin_tenant()

    cliente = obter_cliente_supabase()
    payload = {
        "actor_user_id": _obter_usuario_id(),
        "actor_tenant_id": obter_tenant_id(),
        "action": str(acao).strip() or "view",
        "target_tenant_id": target_tenant_id,
        "reason": str(motivo or "").strip(),
    }
    resposta = (
        cliente.table("tenant_access_audit")
        .insert(payload)
        .execute()
    )
    linhas = resposta.data or []
    if not linhas:
        return payload
    return linhas[0]


def listar_auditoria_acesso() -> list[dict[str, Any]]:
    """Lista os eventos administrativos registrados no tenant atual."""
    exigir_permissao_admin_tenant()

    cliente = obter_cliente_supabase()
    resposta = (
        cliente.table("tenant_access_audit")
        .select("*")
        .eq("actor_tenant_id", obter_tenant_id())
        .order("created_at", desc=True)
        .execute()
    )
    return resposta.data or []


def listar_membros_tenant() -> list[dict[str, Any]]:
    """Lista os membros do tenant atual, incluindo o papel de cada usuário."""
    exigir_permissao_admin_tenant()

    cliente = obter_cliente_supabase()
    resposta = (
        cliente.table("tenant_members")
        .select("user_id, tenant_id, role, created_at")
        .eq("tenant_id", obter_tenant_id())
        .order("created_at", desc=True)
        .execute()
    )
    return resposta.data or []


def mostrar_painel_administracao() -> None:
    """Exibe o painel administrativo do tenant atual para owners."""
    st.subheader("Administração do tenant")

    if not eh_owner_tenant():
        st.warning(
            "Este painel é restrito a owners do tenant. "
            "Você não possui autorização administrativa neste contexto."
        )
        st.stop()

    vinculacao_concluida = st.session_state.pop(
        "_mi_usuario_piloto_vinculado",
        None,
    )
    if isinstance(vinculacao_concluida, dict):
        st.success("Conta convidada vinculada ao tenant do piloto.")
        st.caption(
            f"Tenant: {vinculacao_concluida.get('tenant_id', '')} · "
            f"Papel: {vinculacao_concluida.get('role', '')}"
        )

    tenant_id = obter_tenant_id()
    membros = listar_membros_tenant()
    auditoria = listar_auditoria_acesso()
    try:
        administrador_piloto = eh_administrador_piloto()
    except RuntimeError as erro:
        st.error(str(erro))
        st.stop()
    st.caption(f"Tenant atual: {tenant_id}")
    st.info(
        "Acesso administrativo foi reforçado para owner do tenant e toda ação "
        "de gestão fica registrada em auditoria para acompanhamento futuro."
    )

    st.markdown("### Preparar acesso por convite")
    if not administrador_piloto:
        st.info(
            "A preparação de contas convidadas é restrita ao administrador "
            "autorizado do piloto."
        )
    else:
        st.caption(
            "No Supabase Auth, convide primeiro o e-mail individual autorizado. "
            "Copie o User ID da conta criada e faça o vínculo aqui antes de o "
            "cliente aceitar o convite."
        )
        st.caption(
            "O vínculo cria um tenant exclusivo. O aceite do convite libera o "
            "login nesse tenant, sem uma segunda solicitação de acesso."
        )
        with st.form("mi_pilot_invited_user_form"):
            user_id = st.text_input("User ID da conta no Supabase Auth")
            nome_tenant = st.text_input("Nome do tenant do cliente")
            papel = st.selectbox(
                "Papel no tenant",
                ["member", "owner"],
                help="Use member por padrão; owner só se o cliente precisar administrar o tenant.",
            )
            vincular = st.form_submit_button(
                "Vincular conta e criar tenant",
                type="primary",
            )
        if vincular:
            try:
                resultado = vincular_usuario_convidado_piloto(
                    user_id=user_id,
                    nome_tenant=nome_tenant,
                    papel=papel,
                )
            except RuntimeError as erro:
                st.error(str(erro))
            else:
                st.session_state["_mi_usuario_piloto_vinculado"] = resultado
                st.rerun()

    st.markdown("### Membros do tenant")
    if membros:
        tabela_membros = pd.DataFrame({
            "Avatar": ["U"] * len(membros),
            "Usuário": [
                f"Usuário {str(membro.get('user_id') or '')[:8]}"
                for membro in membros
            ],
            "Perfil": [
                "Owner" if membro.get("role") == "owner" else "Viewer"
                for membro in membros
            ],
            "Status": ["Ativo"] * len(membros),
            "Último acesso": ["—"] * len(membros),
        })
        tabela_limpa(
            tabela_membros,
            badges={
                "Perfil": {
                    "Owner": "info",
                    "Viewer": "muted",
                },
                "Status": {
                    "Ativo": "positive",
                },
            },
            chave="membros_tenant",
            linhas_por_pagina=10,
        )
        st.caption(
            "Último acesso não é registrado pela fonte de identidade atual."
        )
    else:
        st.write("Nenhum membro encontrado para este tenant.")

    st.markdown("### Auditoria de acesso")
    if auditoria:
        auditoria_df = pd.DataFrame(auditoria)
        colunas = [
            "action",
            "actor_user_id",
            "target_tenant_id",
            "reason",
            "created_at",
        ]
        for coluna in colunas:
            if coluna not in auditoria_df.columns:
                auditoria_df[coluna] = ""
        st.dataframe(auditoria_df[colunas], use_container_width=True)
    else:
        st.write("Ainda não há registros de auditoria para este tenant.")
