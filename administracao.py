from __future__ import annotations

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


def mostrar_acesso_piloto_pendente() -> None:
    """Informa que a conta autenticada ainda aguarda vínculo administrativo."""
    st.subheader("Piloto privado")
    st.info(
        "Sua conta está autenticada, mas não foi provisionada como convite "
        "para um tenant do piloto."
    )
    st.caption(
        "Entre em contato com o responsável pelo piloto para confirmar se o "
        "convite foi enviado pelo Supabase Auth."
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

    tenant_id = obter_tenant_id()
    membros = listar_membros_tenant()
    auditoria = listar_auditoria_acesso()
    st.caption(f"Tenant atual: {tenant_id}")
    st.info(
        "Acesso administrativo foi reforçado para owner do tenant e toda ação "
        "de gestão fica registrada em auditoria para acompanhamento futuro."
    )

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
