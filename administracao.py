from __future__ import annotations

import re
from typing import Any

import pandas as pd
import streamlit as st
from postgrest.exceptions import APIError

from autenticacao import eh_owner_tenant
from armazenamento import obter_cliente_supabase, obter_tenant_id


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
    """Bloqueia a gestão global de onboarding a contas explicitamente autorizadas."""
    if not eh_administrador_piloto():
        raise RuntimeError(
            "A aprovação global de onboarding é restrita ao administrador "
            "explicitamente autorizado do piloto."
        )


def solicitar_onboarding_piloto(*, motivo: str = "") -> dict[str, Any]:
    """Registra a solicitação de acesso ao piloto privado para a conta."""
    usuario_id = st.session_state.get("_mi_supabase_user_id")
    if not usuario_id:
        raise RuntimeError(
            "A identidade autenticada não está disponível para registrar o "
            "onboarding do piloto privado. Entre novamente."
        )

    if st.session_state.get("_mi_tenant_id"):
        return {
            "status": "already_linked",
            "tenant_id": str(st.session_state["_mi_tenant_id"]),
        }

    cliente = obter_cliente_supabase()
    try:
        resposta = (
            cliente.table("tenant_access_audit")
            .select("*")
            .eq("actor_user_id", str(usuario_id))
            .eq("action", "pilot_onboarding_request")
            .is_("actor_tenant_id", "null")
            .is_("target_tenant_id", "null")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
    except APIError as erro:
        raise RuntimeError(
            "Não foi possível verificar se já existe uma solicitação pendente "
            f"de onboarding: {erro.message}"
        ) from erro
    linhas = resposta.data or []
    if linhas:
        return linhas[0]

    payload = {
        "actor_user_id": str(usuario_id),
        "actor_tenant_id": None,
        "action": "pilot_onboarding_request",
        "target_tenant_id": None,
        "reason": (str(motivo) or "Solicitação de acesso ao piloto privado").strip(),
    }
    try:
        resposta = cliente.table("tenant_access_audit").insert(payload).execute()
    except APIError as erro:
        raise RuntimeError(
            "Não foi possível registrar a solicitação de onboarding: "
            f"{erro.message}"
        ) from erro
    linhas = resposta.data or []
    if not linhas:
        raise RuntimeError(
            "O banco não confirmou o registro da solicitação de onboarding."
        )
    return linhas[0]


def listar_solicitacoes_piloto_pendentes() -> list[dict[str, Any]]:
    """Lista pedidos de onboarding ainda sem tenant vinculado."""
    exigir_administrador_piloto()
    cliente = obter_cliente_supabase()
    try:
        resposta = (
            cliente.table("tenant_access_audit")
            .select("*")
            .eq("action", "pilot_onboarding_request")
            .is_("actor_tenant_id", "null")
            .is_("target_tenant_id", "null")
            .order("created_at", desc=True)
            .execute()
        )
    except APIError as erro:
        raise RuntimeError(
            "Não foi possível carregar as solicitações pendentes de "
            f"onboarding: {erro.message}"
        ) from erro
    return resposta.data or []


def aprovar_onboarding_piloto(
    *,
    user_id: str,
    nome_tenant: str,
    papel: str = "member",
    tenant_id: str | None = None,
) -> dict[str, Any]:
    """Aprova a solicitação por meio da operação transacional do banco."""
    exigir_administrador_piloto()

    if not user_id:
        raise RuntimeError("É obrigatório informar o identificador do usuário.")
    if papel not in {"owner", "member"}:
        raise RuntimeError("O papel do usuário deve ser 'owner' ou 'member'.")

    nome = (str(nome_tenant or "")).strip()
    if not nome:
        nome = f"Tenant piloto {user_id[:8]}"

    cliente = obter_cliente_supabase()
    try:
        resposta = cliente.rpc(
            "approve_pilot_onboarding",
            {
                "p_user_id": str(user_id),
                "p_tenant_name": nome,
                "p_role": papel,
                "p_actor_tenant_id": obter_tenant_id(),
                "p_target_tenant_id": tenant_id,
            },
        ).execute()
    except APIError as erro:
        raise RuntimeError(
            "Não foi possível aprovar o onboarding do piloto: "
            f"{erro.message}"
        ) from erro

    resultado = resposta.data
    if isinstance(resultado, list) and resultado:
        resultado = resultado[0]
    if not isinstance(resultado, dict):
        raise RuntimeError(
            "O banco não confirmou a aprovação do onboarding do piloto."
        )
    return resultado


def mostrar_fluxo_onboarding_piloto() -> None:
    """Exibe o fluxo de onboarding para usuários autenticados sem tenant."""
    st.subheader("Piloto privado")
    st.info(
        "Sua conta está autenticada, mas ainda não foi vinculada a um tenant "
        "do piloto. Solicite o acesso para receber o vínculo e as permissões "
        "do ambiente de testes."
    )
    st.caption(
        "Próximo passo: registrar sua solicitação e aguardar aprovação do "
        "responsável pelo produto."
    )

    with st.form("mi_pilot_onboarding_form"):
        motivo = st.text_area(
            "Descreva o objetivo do acesso ao piloto",
            value="Solicito acesso ao piloto privado para validar o ambiente e as integrações.",
            height=120,
        )
        enviado = st.form_submit_button("Solicitar acesso ao piloto", type="primary")

    if enviado:
        try:
            resultado = solicitar_onboarding_piloto(motivo=motivo)
        except RuntimeError as erro:
            st.error(str(erro))
            return
        st.success(
            "Solicitação registrada com sucesso. O responsável pelo produto "
            "poderá aprovar o vínculo do seu tenant e liberar o acesso."
        )
        st.caption(f"Registro de acesso: {resultado.get('action', 'pilot_onboarding_request')}")


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

    aprovacao_concluida = st.session_state.pop(
        "_mi_onboarding_aprovado",
        None,
    )
    if isinstance(aprovacao_concluida, dict):
        st.success("Usuário aprovado e vinculado ao tenant do piloto.")
        st.caption(
            f"Tenant: {aprovacao_concluida.get('tenant_id', '')} · "
            f"Papel: {aprovacao_concluida.get('role', '')}"
        )

    tenant_id = obter_tenant_id()
    membros = listar_membros_tenant()
    auditoria = listar_auditoria_acesso()
    try:
        administrador_piloto = eh_administrador_piloto()
    except RuntimeError as erro:
        st.error(str(erro))
        st.stop()
    solicitacoes_pendentes = (
        listar_solicitacoes_piloto_pendentes()
        if administrador_piloto
        else []
    )

    st.caption(f"Tenant atual: {tenant_id}")
    st.info(
        "Acesso administrativo foi reforçado para owner do tenant e toda ação "
        "de gestão fica registrada em auditoria para acompanhamento futuro."
    )

    st.markdown("### Solicitações de onboarding do piloto")
    if not administrador_piloto:
        st.info(
            "A visualização e aprovação global de pedidos de onboarding estão "
            "restritas ao administrador autorizado do piloto."
        )
    elif solicitacoes_pendentes:
        for solicitacao in solicitacoes_pendentes:
            user_id = str(solicitacao.get("actor_user_id") or "")
            nome_tenant = f"Tenant do piloto {user_id[:8]}"
            with st.expander(f"Solicitação de {user_id[:8]}"):
                st.write(solicitacao.get("reason") or "Sem motivo informado.")
                nome_tenant = st.text_input(
                    "Nome do tenant para aprovar",
                    value=nome_tenant,
                    key=f"tenant_name_{user_id}",
                )
                papel = st.selectbox(
                    "Papel do usuário no tenant",
                    ["member", "owner"],
                    key=f"tenant_role_{user_id}",
                )
                if st.button("Aprovar onboarding", key=f"approve_{user_id}"):
                    try:
                        resultado = aprovar_onboarding_piloto(
                            user_id=user_id,
                            nome_tenant=nome_tenant,
                            papel=papel,
                        )
                    except RuntimeError as erro:
                        st.error(str(erro))
                    else:
                        st.session_state["_mi_onboarding_aprovado"] = resultado
                        st.rerun()
    else:
        st.write("Nenhuma solicitação pendente de onboarding do piloto.")

    st.markdown("### Membros do tenant")
    if membros:
        tabela = pd.DataFrame(membros)
        colunas_esperadas = ["user_id", "role", "created_at"]
        colunas_disponiveis = [coluna for coluna in colunas_esperadas if coluna in tabela.columns]
        if colunas_disponiveis:
            tabela = tabela[colunas_disponiveis]
        st.dataframe(tabela, use_container_width=True)
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
