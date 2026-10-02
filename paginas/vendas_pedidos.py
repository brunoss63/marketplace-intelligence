from datetime import date
import re

import pandas as pd
import streamlit as st

from armazenamento import ler_dataset
from componentes import animar_pagina, cabecalho_pagina, tabela_limpa


COLUNAS_PEDIDOS = [
    "id_pedido",
    "data",
    "marketplace",
    "sku",
    "produto",
    "quantidade",
    "preco_unitario",
    "faturamento_bruto",
    "desconto",
    "taxa_marketplace",
    "frete_vendedor",
    "status",
]


def _moeda(valor: object) -> str:
    numero = pd.to_numeric(valor, errors="coerce")
    if pd.isna(numero):
        return "—"
    return (
        f"R$ {numero:,.2f}"
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )


def _proteger_csv_contra_formulas(dados: pd.DataFrame) -> pd.DataFrame:
    """Neutraliza fórmulas em campos textuais antes de exportar para planilhas."""

    seguro = dados.copy()
    prefixo_formula = re.compile(r"^[\t\r\n ]*[=+\-@]")
    for coluna in seguro.columns:
        if not (
            pd.api.types.is_object_dtype(seguro[coluna].dtype)
            or pd.api.types.is_string_dtype(seguro[coluna].dtype)
        ):
            continue
        seguro[coluna] = seguro[coluna].map(
            lambda valor: (
                f"'{valor}"
                if isinstance(valor, str)
                and prefixo_formula.match(valor)
                else valor
            )
        )
    return seguro


def _preparar_tabela(pedidos: pd.DataFrame) -> pd.DataFrame:
    produtos = ler_dataset(
        "dados/produtos.csv",
        dtype={"sku": "string"},
    )
    produtos["custo_unitario"] = pd.to_numeric(
        produtos["custo_unitario"],
        errors="coerce",
    )
    pedidos = pedidos.merge(
        produtos[["sku", "custo_unitario"]],
        on="sku",
        how="left",
        validate="many_to_one",
    )
    pedidos["faturamento_liquido"] = (
        pedidos["faturamento_bruto"]
        - pedidos["desconto"]
        - pedidos["taxa_marketplace"]
        - pedidos["frete_vendedor"]
    )
    pedidos.loc[
        pedidos["status"] != "Concluído",
        "faturamento_liquido"
    ] = pd.NA
    pedidos["custo_venda"] = (
        pedidos["quantidade"] * pedidos["custo_unitario"]
    )
    pedidos["margem_valor"] = (
        pedidos["faturamento_bruto"]
        - pedidos["desconto"]
        - pedidos["taxa_marketplace"]
        - pedidos["frete_vendedor"]
        - pedidos["custo_venda"]
    )
    margem_calculavel = (
        pedidos["status"].eq("Concluído")
        & pedidos["custo_unitario"].notna()
    )
    pedidos.loc[~margem_calculavel, "margem_valor"] = pd.NA
    base_margem = pedidos["faturamento_bruto"] - pedidos["desconto"]
    pedidos["margem_percentual"] = (
        pedidos["margem_valor"]
        .div(base_margem.where(base_margem.gt(0)))
        .mul(100)
    )

    tabela = pedidos.rename(
        columns={
            "id_pedido": "Pedido",
            "data": "Data",
            "marketplace": "Marketplace",
            "sku": "SKU",
            "produto": "Produto",
            "quantidade": "Unidades",
            "preco_unitario": "Preço unitário",
            "faturamento_bruto": "Total bruto",
            "desconto": "Desconto",
            "taxa_marketplace": "Taxa",
            "frete_vendedor": "Frete vendedor",
            "status": "Status",
            "faturamento_liquido": "Faturamento líquido",
            "margem_valor": "Margem",
            "margem_percentual": "Margem %",
        }
    ).copy()
    if "Data" in tabela:
        tabela["Data"] = pd.to_datetime(
            tabela["Data"],
            errors="coerce",
        ).dt.strftime("%d/%m/%Y").fillna("—")
    for coluna in (
        "Preço unitário",
        "Total bruto",
        "Desconto",
        "Taxa",
        "Frete vendedor",
        "Faturamento líquido",
        "Margem",
    ):
        if coluna in tabela:
            tabela[coluna] = tabela[coluna].map(_moeda)
    if "Margem %" in tabela:
        tabela["Margem %"] = tabela["Margem %"].map(
            lambda valor: (
                f"{valor:.1f}%"
                if pd.notna(valor)
                else "—"
            )
        )
    if "Unidades" in tabela:
        tabela["Unidades"] = pd.to_numeric(
            tabela["Unidades"],
            errors="coerce",
        ).fillna(0).map(lambda valor: f"{valor:,.0f}".replace(",", "."))
    return tabela


animar_pagina("vendas_pedidos")
cabecalho_pagina(
    "Vendas & Pedidos",
    "Consulte pedidos individuais e acompanhe os detalhes das vendas.",
    "▤",
)

pedidos = ler_dataset(
    "dados/pedidos.csv",
    dtype={"id_pedido": "string", "sku": "string"},
)
for coluna in COLUNAS_PEDIDOS:
    if coluna not in pedidos.columns:
        pedidos[coluna] = pd.NA

pedidos["data"] = pd.to_datetime(pedidos["data"], errors="coerce")
pedidos["faturamento_bruto"] = pd.to_numeric(
    pedidos["faturamento_bruto"],
    errors="coerce",
)
pedidos["quantidade"] = pd.to_numeric(pedidos["quantidade"], errors="coerce")
pedidos["desconto"] = pd.to_numeric(
    pedidos["desconto"],
    errors="coerce",
).fillna(0)
for coluna in ("taxa_marketplace", "frete_vendedor"):
    pedidos[coluna] = pd.to_numeric(
        pedidos[coluna],
        errors="coerce",
    ).fillna(0)

data_inicio = st.session_state.get("data_inicio")
data_fim = st.session_state.get("data_fim")
if not isinstance(data_inicio, date) or not isinstance(data_fim, date):
    st.info("Selecione um período nos filtros globais para consultar pedidos.")
    st.stop()

filtrados = pedidos[
    pedidos["data"].notna()
    & (pedidos["data"].dt.date >= data_inicio)
    & (pedidos["data"].dt.date <= data_fim)
].copy()
produto_global = st.session_state.get("produto_global")
if produto_global and produto_global != "Todos os produtos":
    filtrados = filtrados[filtrados["produto"] == produto_global]
marketplace_global = st.session_state.get("marketplace_global")
if marketplace_global and marketplace_global != "Todos":
    filtrados = filtrados[filtrados["marketplace"] == marketplace_global]

st.markdown("### 🔎 Localizar pedidos")
st.markdown(
    '<div class="mi-table-filters-anchor"></div>',
    unsafe_allow_html=True,
)
col_busca, col_status = st.columns([2.4, 1], gap="medium")
with col_busca:
    busca = st.text_input(
        "Buscar por pedido, produto ou SKU",
        placeholder="Digite um ID, nome de produto ou SKU...",
        key="vendas_pedidos_busca",
    ).strip()
with col_status:
    status_disponiveis = sorted(
        filtrados["status"].dropna().astype(str).unique().tolist(),
        key=str.casefold,
    )
    status_selecionado = st.selectbox(
        "Status do pedido",
        ["Todos", *status_disponiveis],
        key="vendas_pedidos_status",
    )

if busca:
    corresponde = pd.Series(False, index=filtrados.index)
    for coluna in ("id_pedido", "produto", "sku"):
        corresponde |= filtrados[coluna].astype("string").str.contains(
            busca,
            case=False,
            regex=False,
            na=False,
        )
    filtrados = filtrados[corresponde]
if status_selecionado != "Todos":
    filtrados = filtrados[filtrados["status"] == status_selecionado]

filtrados = filtrados.sort_values(
    ["data", "id_pedido"],
    ascending=[False, False],
    na_position="last",
)

total_bruto = float(filtrados["faturamento_bruto"].fillna(0).sum())
total_unidades = float(filtrados["quantidade"].fillna(0).sum())
metricas = st.columns(3, gap="medium")
metricas[0].metric("Pedidos encontrados", f"{len(filtrados):,}".replace(",", "."))
metricas[1].metric("Unidades vendidas", f"{total_unidades:,.0f}".replace(",", "."))
metricas[2].metric("Faturamento bruto", _moeda(total_bruto))

st.markdown("### 📋 Detalhamento das vendas")
st.caption(
    f"Período: {data_inicio.strftime('%d/%m/%Y')} a "
    f"{data_fim.strftime('%d/%m/%Y')} · {len(filtrados):,} pedidos"
    .replace(",", ".")
)
if filtrados.empty:
    st.info("Nenhum pedido corresponde aos filtros selecionados.")
else:
    tabela = _preparar_tabela(filtrados[COLUNAS_PEDIDOS])
    colunas_tabela = [
        "Data",
        "Pedido",
        "Marketplace",
        "Produto",
        "Unidades",
        "Preço unitário",
        "Total bruto",
        "Taxa",
        "Frete vendedor",
        "Desconto",
        "Faturamento líquido",
        "Margem",
        "Margem %",
        "Status",
    ]
    tabela_limpa(
        tabela[colunas_tabela],
        badges={
            "Marketplace": {
                "Mercado Livre": "ml",
                "Shopee": "shopee",
            },
            "Status": {
                "Concluído": "positive",
                "Cancelado": "warning",
                "Devolvido": "muted",
                "Em andamento": "info",
            },
        },
        chave="vendas_pedidos",
        linhas_por_pagina=15,
    )
    csv = _proteger_csv_contra_formulas(
        filtrados[COLUNAS_PEDIDOS]
    ).to_csv(
        index=False,
        encoding="utf-8-sig",
    )
    st.download_button(
        "Baixar pedidos filtrados (CSV)",
        data=csv,
        file_name="vendas_pedidos.csv",
        mime="text/csv",
        type="secondary",
    )
