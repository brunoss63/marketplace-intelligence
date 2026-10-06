from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from postgrest.exceptions import APIError
import streamlit as st


EstadoConexao = Literal[
    "connected",
    "syncing",
    "attention",
    "error",
    "disconnected",
    "coming_soon",
]


@dataclass(frozen=True)
class StatusConexao:
    marketplace: str
    estado: EstadoConexao
    rotulo: str
    ultima_sincronizacao: datetime | None = None
    mensagem: str = ""


def obter_status_conexoes() -> tuple[StatusConexao, StatusConexao]:
    """Fonte central do estado simples exibido para cada marketplace."""
    from armazenamento import is_database_mode

    ultimo_sync = st.session_state.get("_mi_ml_last_sync")
    if not isinstance(ultimo_sync, datetime):
        ultimo_sync = None

    if st.session_state.get("_mi_ml_connection_error"):
        estado_ml: EstadoConexao = "error"
        rotulo_ml = "Erro"
        mensagem_ml = "Não foi possível consultar o status da conexão."
    elif st.session_state.get("_mi_ml_connection_attention"):
        estado_ml = "attention"
        rotulo_ml = "Atenção"
        mensagem_ml = "A conexão precisa ser validada."
    elif st.session_state.get("_mi_ml_syncing"):
        estado_ml = "syncing"
        rotulo_ml = "Sincronizando"
        mensagem_ml = "Sincronização em andamento."
    else:
        try:
            conectado = is_database_mode()
            if conectado:
                from integracao_mercadolivre import _obter_conexao

                conectado = _obter_conexao() is not None
        except (APIError, RuntimeError):
            estado_ml = "error"
            rotulo_ml = "Erro"
            mensagem_ml = "Não foi possível consultar o status da conexão."
        else:
            estado_ml = "connected" if conectado else "disconnected"
            rotulo_ml = "Conectado" if conectado else "Desconectado"
            mensagem_ml = ""

    return (
        StatusConexao(
            marketplace="Mercado Livre",
            estado=estado_ml,
            rotulo=rotulo_ml,
            ultima_sincronizacao=ultimo_sync,
            mensagem=mensagem_ml,
        ),
        StatusConexao(
            marketplace="Shopee",
            estado="coming_soon",
            rotulo="Em breve",
        ),
    )


def texto_ultima_sincronizacao(
    ultima_sincronizacao: datetime | None,
    *,
    agora: datetime | None = None,
) -> str:
    if ultima_sincronizacao is None:
        return ""
    instante_atual = agora or datetime.now(ultima_sincronizacao.tzinfo)
    segundos = max(
        0,
        int((instante_atual - ultima_sincronizacao).total_seconds()),
    )
    minutos = segundos // 60
    if minutos < 1:
        return "Última sincronização: há menos de 1 min"
    if minutos < 60:
        return f"Última sincronização: há {minutos} min"
    horas = minutos // 60
    if horas < 24:
        return f"Última sincronização: há {horas} h"
    dias = horas // 24
    return f"Última sincronização: há {dias} d"
