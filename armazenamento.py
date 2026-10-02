import json
import os
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError
from supabase import Client

from autenticacao import obter_cliente_supabase as _restaurar_cliente_supabase


_DADOS = {
    "pedidos.csv": {
        "table": "orders",
        "columns": {
            "id_pedido": "order_id",
            "data": "order_date",
            "marketplace": "marketplace",
            "sku": "sku",
            "produto": "product_name",
            "quantidade": "quantity",
            "preco_unitario": "unit_price",
            "faturamento_bruto": "gross_revenue",
            "desconto": "discount",
            "taxa_marketplace": "marketplace_fee",
            "frete_vendedor": "seller_shipping",
            "status": "status",
        },
        "keys": [
            "marketplace",
            "id_pedido",
            "sku",
            "produto",
        ],
    },
    "produtos.csv": {
        "table": "products",
        "columns": {
            "marketplace": "marketplace",
            "sku": "sku",
            "produto": "product_name",
            "categoria": "category",
            "custo_unitario": "unit_cost",
            "preco_venda": "sale_price",
            "estoque_inicial": "initial_stock",
        },
        "keys": ["marketplace", "sku"],
    },
    "estoque.csv": {
        "table": "inventory",
        "columns": {
            "marketplace": "marketplace",
            "sku": "sku",
            "produto": "product_name",
            "estoque_atual": "current_stock",
        },
        "keys": ["marketplace", "sku"],
    },
    "publicidade.csv": {
        "table": "ad_performance",
        "columns": {
            "data": "ad_date",
            "marketplace": "marketplace",
            "sku": "sku",
            "campanha": "campaign",
            "investimento": "spend",
            "receita_atribuida": "attributed_revenue",
        },
        "keys": [
            "marketplace",
            "data",
            "sku",
            "campanha",
        ],
    },
}
_TAMANHO_PAGINA = 1000
_TAMANHO_LOTE = 500


def is_database_mode() -> bool:
    ambiente = os.environ.get("MI_ENV")
    if not ambiente:
        try:
            ambiente = st.secrets.get("MI_ENV")
        except StreamlitSecretNotFoundError:
            ambiente = None
    if ambiente not in {"local", "development", "production"}:
        raise RuntimeError(
            "Configure MI_ENV como 'local', 'development' ou 'production' "
            "antes de acessar os dados."
        )
    return ambiente in {"development", "production"}


def obter_cliente_supabase() -> Client:
    return _restaurar_cliente_supabase()


def obter_tenant_id() -> str:
    tenant_id = st.session_state.get("_mi_tenant_id")
    if not tenant_id:
        raise RuntimeError(
            "Esta conta ainda não está vinculada a um tenant autorizado."
        )
    return str(tenant_id)


def _obter_usuario_cache_id() -> str:
    usuario_id = st.session_state.get("_mi_supabase_user_id")
    if not usuario_id:
        raise RuntimeError(
            "A identidade autenticada não está disponível para consultar "
            "os dados. Entre novamente."
        )
    return str(usuario_id)


def _validar_escopo_cache(tenant_id: str, usuario_id: str) -> None:
    if (
        tenant_id != obter_tenant_id()
        or usuario_id != _obter_usuario_cache_id()
    ):
        raise RuntimeError(
            "A sessão mudou durante a leitura dos dados. Atualize a página "
            "para autenticar novamente."
        )


def _ler_tabela(
    nome_tabela: str,
    colunas: str = "*",
) -> list[dict[str, Any]]:
    cliente = obter_cliente_supabase()
    tenant_id = obter_tenant_id()
    linhas: list[dict[str, Any]] = []
    inicio = 0

    while True:
        resposta = (
            cliente.table(nome_tabela)
            .select(colunas)
            .eq("tenant_id", tenant_id)
            .range(inicio, inicio + _TAMANHO_PAGINA - 1)
            .execute()
        )
        pagina = resposta.data or []
        linhas.extend(pagina)
        if len(pagina) < _TAMANHO_PAGINA:
            return linhas
        inicio += _TAMANHO_PAGINA


@st.cache_data(ttl=30, show_spinner=False)
def _ler_dataset_banco(
    tenant_id: str,
    usuario_id: str,
    nome_arquivo: str,
) -> pd.DataFrame:
    _validar_escopo_cache(tenant_id, usuario_id)
    definicao = _DADOS.get(nome_arquivo)
    if definicao is None:
        raise ValueError(
            f"Não há mapeamento do banco para o dataset {nome_arquivo!r}."
        )

    campos = definicao["columns"]
    colunas_banco = list(dict.fromkeys(fields for fields in campos.values()))
    linhas = _ler_tabela(
        str(definicao["table"]),
        ",".join(["tenant_id", *colunas_banco]),
    )
    dados = pd.DataFrame(linhas).rename(
        columns={
            coluna_banco: coluna_csv
            for coluna_csv, coluna_banco in campos.items()
        }
    )
    return dados.reindex(columns=list(campos))


@st.cache_data(ttl=30, show_spinner=False)
def _ler_historico_banco(
    tenant_id: str,
    usuario_id: str,
) -> list[dict[str, Any]]:
    _validar_escopo_cache(tenant_id, usuario_id)
    return sorted(
        _ler_tabela("import_batches"),
        key=lambda linha: str(linha.get("imported_at", "")),
    )


def ler_dataset(
    caminho: str | Path,
    **opcoes_csv: Any,
) -> pd.DataFrame:
    """Lê os CSVs locais na demonstração ou dados isolados por tenant no banco."""

    if not is_database_mode():
        return pd.read_csv(caminho, **opcoes_csv)

    dados = _ler_dataset_banco(
        obter_tenant_id(),
        _obter_usuario_cache_id(),
        Path(caminho).name,
    )

    dtype = opcoes_csv.get("dtype")
    if isinstance(dtype, dict):
        for coluna, tipo in dtype.items():
            if coluna in dados:
                dados[coluna] = dados[coluna].astype(tipo)

    return dados


def salvar_importacao(
    tipo_dado: str,
    registros: pd.DataFrame,
) -> dict[str, int]:
    tipos_arquivo = {
        "Pedidos": "pedidos.csv",
        "Produtos": "produtos.csv",
        "Estoque": "estoque.csv",
        "Publicidade": "publicidade.csv",
    }
    nome_arquivo = tipos_arquivo.get(tipo_dado)
    definicao = _DADOS.get(nome_arquivo or "")
    if definicao is None:
        raise ValueError(f"Tipo de importação não suportado: {tipo_dado}.")
    if registros.empty:
        return {"inseridos": 0, "atualizados": 0, "total": 0}

    campos = definicao["columns"]
    chaves = definicao["keys"]
    colunas_chave_banco = [campos[chave] for chave in chaves]
    linhas_existentes = _ler_tabela(
        str(definicao["table"]),
        ",".join(["tenant_id", *colunas_chave_banco]),
    )
    nomes_chave_existentes = {
        tuple(str(linha.get(coluna) or "").strip() for coluna in chaves)
        for linha in (
            pd.DataFrame(linhas_existentes)
            .rename(
                columns={
                    coluna_banco: coluna_csv
                    for coluna_csv, coluna_banco in campos.items()
                }
            )
            .to_dict(orient="records")
        )
    }
    nomes_chave_novos = [
        tuple(str(linha.get(coluna) or "").strip() for coluna in chaves)
        for linha in registros.to_dict(orient="records")
    ]
    chaves_novas_unicas = set(nomes_chave_novos)
    atualizados = len(chaves_novas_unicas & nomes_chave_existentes)
    inseridos = len(chaves_novas_unicas - nomes_chave_existentes)

    registros_json = json.loads(
        registros[list(campos)].to_json(
            orient="records",
            date_format="iso",
        )
    )
    payload = [
        {
            "tenant_id": obter_tenant_id(),
            **{
                coluna_banco: linha.get(coluna_csv)
                for coluna_csv, coluna_banco in campos.items()
            },
        }
        for linha in registros_json
    ]
    colunas_conflicto = [
        "tenant_id",
        *colunas_chave_banco,
    ]
    cliente = obter_cliente_supabase()
    for inicio in range(0, len(payload), _TAMANHO_LOTE):
        (
            cliente.table(str(definicao["table"]))
            .upsert(
                payload[inicio:inicio + _TAMANHO_LOTE],
                on_conflict=",".join(colunas_conflicto),
            )
            .execute()
        )

    _limpar_cache_dados()
    return {
        "inseridos": inseridos,
        "atualizados": atualizados,
        "total": len(registros),
    }


def listar_historico_importacoes() -> list[dict[str, Any]]:
    return _ler_historico_banco(
        obter_tenant_id(),
        _obter_usuario_cache_id(),
    )


def salvar_lote_importacao(registro: dict[str, Any]) -> None:
    payload = {
        "tenant_id": obter_tenant_id(),
        "marketplace": registro["marketplace"],
        "data_type": registro["tipo_dado"],
        "source_filename": registro["arquivo_origem"],
        "fingerprint": registro["fingerprint"],
        "source_records": registro["registros_origem"],
        "imported_records": registro["importados"],
        "inserted_records": registro["inseridos"],
        "updated_records": registro["atualizados"],
        "ignored_records": registro["ignorados"],
        "error_records": registro["erros"],
        "status": registro["status"],
        "imported_at": registro["data_hora"],
    }
    obter_cliente_supabase().table("import_batches").insert(payload).execute()
    _limpar_cache_dados()


def _limpar_cache_dados() -> None:
    _ler_dataset_banco.clear()
    _ler_historico_banco.clear()
