from datetime import date
from html import escape
import re

import pandas as pd
import streamlit as st

from armazenamento import ler_dataset
from componentes import (
    animar_pagina,
    badge_html,
    cabecalho_pagina,
    card,
    icone_svg,
    renderizar_animacoes_entrada_pagina,
    renderizar_skeleton_vendas_pedidos,
    titulo_secao,
)


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

COLUNAS_EXIBICAO = [
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

CHAVES_ORDENACAO = {
    "Data": "Data",
    "Pedido": "Pedido",
    "Marketplace": "Marketplace",
    "Produto": "Produto",
    "Unidades": "Unidades",
    "Preço unitário": "Preço unitário",
    "Total bruto": "Total bruto",
    "Taxa": "Taxa",
    "Frete vendedor": "Frete vendedor",
    "Desconto": "Desconto",
    "Faturamento líquido": "Faturamento líquido",
    "Margem": "Margem",
    "Margem %": "Margem %",
    "Status": "Status",
}


def _moeda(valor: object) -> str:
    numero = pd.to_numeric(valor, errors="coerce")
    if pd.isna(numero):
        return "—"
    sinal = "-" if numero < 0 else ""
    return (
        f"{sinal}R$ {abs(numero):,.2f}"
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )


def _numero_inteiro(valor: object) -> str:
    numero = pd.to_numeric(valor, errors="coerce")
    if pd.isna(numero):
        return "—"
    return f"{numero:,.0f}".replace(",", ".")


def _texto_percentual(valor: object) -> str:
    numero = pd.to_numeric(valor, errors="coerce")
    if pd.isna(numero):
        return "—"
    return f"{numero:.1f}%".replace(".", ",")


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

    return pedidos.rename(
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


def _formatar_tabela(tabela: pd.DataFrame) -> pd.DataFrame:
    apresentacao = pd.DataFrame(index=tabela.index)
    apresentacao["Data"] = pd.to_datetime(
        tabela["Data"],
        errors="coerce",
    ).dt.strftime("%d/%m/%Y").fillna("—")
    apresentacao["Pedido"] = tabela["Pedido"].astype("string").fillna("—")
    apresentacao["Marketplace"] = (
        tabela["Marketplace"].astype("string").fillna("—")
    )
    apresentacao["Produto"] = tabela["Produto"].astype("string").fillna("—")
    apresentacao["Unidades"] = tabela["Unidades"].map(_numero_inteiro)
    for coluna in (
        "Preço unitário",
        "Total bruto",
        "Taxa",
        "Frete vendedor",
        "Desconto",
        "Faturamento líquido",
        "Margem",
    ):
        valores = tabela[coluna].map(_moeda)
        cancelados_sem_valor = (
            tabela["Status"].eq("Cancelado")
            & pd.to_numeric(tabela[coluna], errors="coerce").fillna(0).eq(0)
        )
        valores.loc[cancelados_sem_valor] = "—"
        apresentacao[coluna] = valores
    apresentacao["Margem %"] = tabela["Margem %"].map(_texto_percentual)
    apresentacao["Status"] = tabela["Status"].astype("string").fillna("—")
    return apresentacao[COLUNAS_EXIBICAO]


def _estilos_linha_tabela(linha: pd.Series) -> list[str]:
    estilos = [""] * len(linha)
    if linha["Status"] == "Cancelado":
        estilos = [
            "color: #8292A8; background-color: #131D2B;"
            for _ in linha
        ]
        return estilos

    if str(linha["Margem"]).startswith("-R$"):
        indice_margem = linha.index.get_loc("Margem")
        estilos[indice_margem] = "color: #FF806D; font-weight: 600;"
    return estilos


def _estilos_marketplace(coluna: pd.Series) -> list[str]:
    cores = {
        "Mercado Livre": "#73A9FF",
        "Shopee": "#4FD1B5",
    }
    return [
        f"color: {cores.get(str(valor), '#A8B6C9')}; font-weight: 600;"
        for valor in coluna
    ]


def _estilos_pedido(coluna: pd.Series) -> list[str]:
    return [
        "color: #9BC2FF; font-weight: 650; text-decoration: underline;"
        for _ in coluna
    ]


def _estilos_taxa(coluna: pd.Series) -> list[str]:
    return ["color: #A8B6C9;" for _ in coluna]


def _indice_selecionado(chave_grid: str) -> int | None:
    estado = st.session_state.get(chave_grid, {})
    if not isinstance(estado, dict):
        return None
    selecao = estado.get("selection", {})
    if not isinstance(selecao, dict):
        return None
    linhas = selecao.get("rows", [])
    if not linhas:
        return None
    return int(linhas[0])


def _abrir_pedido(
    tabela_ordenada: pd.DataFrame,
    referencias: tuple[str, ...],
    referencia: str,
) -> None:
    correspondencia = tabela_ordenada["_row_ref"].astype(str).eq(referencia)
    if not correspondencia.any():
        return
    st.session_state["_vendas_pedidos_detalhe_refs"] = referencias
    st.session_state["_vendas_pedidos_detalhe_indice"] = referencias.index(
        referencia
    )
    st.session_state["_vendas_pedidos_detalhe_ref"] = referencia
    st.session_state["_vendas_pedidos_detalhe_aberto"] = True


def _ordenar_tabela(
    tabela: pd.DataFrame,
    coluna: str,
    crescente: bool,
) -> pd.DataFrame:
    colunas = [CHAVES_ORDENACAO[coluna]]
    crescente_por_coluna = [crescente]
    if coluna == "Data":
        colunas.append("Pedido")
        crescente_por_coluna.append(crescente)
    return tabela.sort_values(
        colunas,
        ascending=crescente_por_coluna,
        na_position="last",
        kind="mergesort",
    )


def _limpar_filtros_locais() -> None:
    st.session_state["vendas_pedidos_busca"] = ""
    st.session_state["vendas_pedidos_status"] = "Todos"
    st.session_state["vendas_pedidos_pagina"] = 0
    st.session_state["_vendas_pedidos_detalhe_aberto"] = False


def _alternar_ordem() -> None:
    st.session_state["vendas_pedidos_ordem_crescente"] = not (
        st.session_state.get("vendas_pedidos_ordem_crescente", False)
    )
    st.session_state["vendas_pedidos_pagina"] = 0


def _alterar_pagina(delta: int, total_paginas: int) -> None:
    atual = st.session_state.get("vendas_pedidos_pagina", 0)
    st.session_state["vendas_pedidos_pagina"] = min(
        max(atual + delta, 0),
        max(total_paginas - 1, 0),
    )


def _alterar_tamanho_pagina() -> None:
    st.session_state["vendas_pedidos_pagina"] = 0


@st.fragment
def _renderizar_grade_pedidos(
    ordenada: pd.DataFrame,
    filtrados: pd.DataFrame,
    ordenar_por: str,
    ordem_crescente: bool,
    chave_grid: str,
) -> None:
    tamanho_pagina = st.session_state.get(
        "vendas_pedidos_tamanho_pagina",
        15,
    )
    total_paginas = max(
        (len(ordenada) + tamanho_pagina - 1) // tamanho_pagina,
        1,
    )
    pagina = min(
        max(st.session_state.get("vendas_pedidos_pagina", 0), 0),
        total_paginas - 1,
    )
    st.session_state["vendas_pedidos_pagina"] = pagina
    inicio = pagina * tamanho_pagina
    linhas_pagina = ordenada.iloc[inicio:inicio + tamanho_pagina]
    apresentacao = _formatar_tabela(linhas_pagina).style.apply(
        _estilos_linha_tabela,
        axis=1,
    ).apply(
        _estilos_marketplace,
        subset=["Marketplace"],
        axis=0,
    ).apply(
        _estilos_pedido,
        subset=["Pedido"],
        axis=0,
    ).apply(
        _estilos_taxa,
        subset=["Taxa"],
        axis=0,
    )
    config_colunas = {
        nome: st.column_config.TextColumn(
            label=(
                f"{nome} "
                f"{'↑' if ordem_crescente else '↓'}"
                if nome == ordenar_por
                else nome
            ),
            pinned="left" if nome in {"Data", "Pedido"} else None,
            width=(
                "large"
                if nome == "Pedido"
                else "small"
                if nome in {"Data", "Unidades", "Margem %"}
                else "medium"
            ),
        )
        for nome in COLUNAS_EXIBICAO
    }
    estado_grid = st.dataframe(
        apresentacao,
        column_config=config_colunas,
        column_order=COLUNAS_EXIBICAO,
        hide_index=True,
        height=min(690, max(385, tamanho_pagina * 35 + 42)),
        on_select="rerun",
        selection_mode="single-row",
        key=chave_grid,
        width="stretch",
    )
    linhas_selecionadas = estado_grid.selection.rows
    if (
        linhas_selecionadas
        and not st.session_state.get("_vendas_pedidos_detalhe_aberto", False)
    ):
        indice_linha = linhas_selecionadas[0]
        if 0 <= indice_linha < len(linhas_pagina):
            referencias = tuple(ordenada["_row_ref"].astype(str).tolist())
            referencia = str(linhas_pagina.iloc[indice_linha]["_row_ref"])
            _abrir_pedido(ordenada, referencias, referencia)
            st.rerun(scope="app")

    controles = st.columns([1, 1, 1.5, 1.4, 2], gap="small")
    with controles[0]:
        st.button(
            "← Anterior",
            key="vendas_pedidos_pagina_anterior",
            disabled=pagina == 0,
            on_click=_alterar_pagina,
            args=(-1, total_paginas),
            width="stretch",
        )
    with controles[1]:
        st.button(
            "Próxima →",
            key="vendas_pedidos_pagina_proxima",
            disabled=pagina >= total_paginas - 1,
            on_click=_alterar_pagina,
            args=(1, total_paginas),
            width="stretch",
        )
    with controles[2]:
        st.html(
            f'<div class="mi-pagination-label">'
            f'Página {pagina + 1} de {total_paginas}</div>'
        )
    with controles[3]:
        st.selectbox(
            "Itens por página",
            [15, 30, 50],
            key="vendas_pedidos_tamanho_pagina",
            on_change=_alterar_tamanho_pagina,
        )
    with controles[4]:
        csv_pedidos = (
            filtrados.set_index("_row_ref")
            .loc[ordenada["_row_ref"].astype(str), COLUNAS_PEDIDOS]
        )
        st.download_button(
            "Baixar pedidos filtrados (CSV)",
            data=_proteger_csv_contra_formulas(csv_pedidos).to_csv(
                index=False,
                encoding="utf-8-sig",
            ),
            file_name="vendas_pedidos.csv",
            mime="text/csv",
            type="secondary",
            icon=":material/download:",
            width="stretch",
        )


def _fechar_detalhe() -> None:
    st.session_state["_vendas_pedidos_detalhe_aberto"] = False
    st.session_state["_vendas_pedidos_grid_versao"] = (
        st.session_state.get("_vendas_pedidos_grid_versao", 0) + 1
    )


def _navegar_detalhe(delta: int) -> None:
    refs = st.session_state.get("_vendas_pedidos_detalhe_refs", ())
    indice = st.session_state.get("_vendas_pedidos_detalhe_indice", 0)
    novo_indice = min(max(indice + delta, 0), len(refs) - 1)
    st.session_state["_vendas_pedidos_detalhe_indice"] = novo_indice
    if refs:
        st.session_state["_vendas_pedidos_detalhe_ref"] = refs[novo_indice]
    st.session_state["_vendas_pedidos_grid_versao"] = (
        st.session_state.get("_vendas_pedidos_grid_versao", 0) + 1
    )


@st.dialog(
    "Detalhes do pedido",
    width="large",
    dismissible=True,
    on_dismiss=_fechar_detalhe,
)
def _mostrar_detalhe_pedido(tabela: pd.DataFrame) -> None:
    refs = st.session_state.get("_vendas_pedidos_detalhe_refs", ())
    indice = st.session_state.get("_vendas_pedidos_detalhe_indice", 0)
    if tabela.empty or not refs or indice >= len(refs):
        st.info("Este pedido não está mais disponível nos filtros atuais.")
        st.button("Fechar", on_click=_fechar_detalhe, key="pedido_detalhe_vazio_fechar")
        return

    referencia = refs[indice]
    corresponde = tabela["_row_ref"].astype(str).eq(referencia)
    if not corresponde.any():
        st.info("Este pedido não está mais disponível nos filtros atuais.")
        st.button("Fechar", on_click=_fechar_detalhe, key="pedido_detalhe_indisponivel_fechar")
        return

    pedido = tabela.loc[corresponde].iloc[0]
    cancelado = pedido["Status"] == "Cancelado"
    status_variante = (
        "warning" if cancelado else
        "success" if pedido["Status"] == "Concluído" else
        "info" if pedido["Status"] == "Em andamento" else
        "neutral"
    )
    data = pedido["Data"]
    data_texto = (
        data.strftime("%d/%m/%Y")
        if pd.notna(data)
        else "Data não informada"
    )
    sku = str(pedido["SKU"]) if pd.notna(pedido["SKU"]) else "—"
    margem_variante = (
        "mi-order-detail-result-negative"
        if pd.notna(pedido["Margem"]) and pedido["Margem"] < 0
        else "mi-order-detail-result-positive"
    )
    resultado = (
        "—" if cancelado or pd.isna(pedido["Margem"])
        else _moeda(pedido["Margem"])
    )
    margem_percentual = (
        "—" if cancelado or pd.isna(pedido["Margem %"])
        else _texto_percentual(pedido["Margem %"])
    )
    liquido = (
        "—" if cancelado or pd.isna(pedido["Faturamento líquido"])
        else _moeda(pedido["Faturamento líquido"])
    )
    taxa = (
        "—" if cancelado and not pedido["Taxa"]
        else _moeda(-pedido["Taxa"])
    )
    frete = (
        "—" if cancelado and not pedido["Frete vendedor"]
        else _moeda(-pedido["Frete vendedor"])
    )
    desconto = (
        "—" if cancelado and not pedido["Desconto"]
        else _moeda(-pedido["Desconto"])
    )
    classe_cancelado = " mi-order-detail-cancelled" if cancelado else ""
    detalhes = f"""
        <div class="mi-order-detail-header mi-order-detail-enter{classe_cancelado}">
            <div>
                <h3 class="mi-order-detail-id">Pedido {escape(str(pedido['Pedido']))}</h3>
                <div class="mi-order-detail-meta">
                    {escape(data_texto)} · {escape(str(pedido['Marketplace']))}
                    · {escape(str(pedido['Produto']))}
                </div>
            </div>
            {badge_html(str(pedido['Status']), status_variante)}
        </div>
        <section class="mi-order-detail-section mi-order-detail-enter"
                 style="--mi-detail-delay:45ms">
            <h4 class="mi-order-detail-section-title">Item</h4>
            <div class="mi-order-detail-row">
                <span>Produto · SKU {escape(sku)}</span>
                <strong>{_numero_inteiro(pedido['Unidades'])} un.</strong>
            </div>
            <div class="mi-order-detail-row">
                <span>Preço unitário</span>
                <strong>{_moeda(pedido['Preço unitário'])}</strong>
            </div>
        </section>
        <section class="mi-order-detail-section mi-order-detail-enter"
                 style="--mi-detail-delay:90ms">
            <h4 class="mi-order-detail-section-title">Composição financeira</h4>
            <div class="mi-order-detail-row">
                <span>Total bruto</span><strong>{_moeda(pedido['Total bruto'])}</strong>
            </div>
            <div class="mi-order-detail-row">
                <span>Menos taxa do marketplace</span><strong>{taxa}</strong>
            </div>
            <div class="mi-order-detail-row">
                <span>Menos frete do vendedor</span><strong>{frete}</strong>
            </div>
            <div class="mi-order-detail-row">
                <span>Menos desconto</span><strong>{desconto}</strong>
            </div>
            <div class="mi-order-detail-row mi-order-detail-total">
                <span>Faturamento líquido</span><strong>{liquido}</strong>
            </div>
        </section>
        <section class="mi-order-detail-section mi-order-detail-enter"
                 style="--mi-detail-delay:135ms">
            <h4 class="mi-order-detail-section-title">Resultado</h4>
            <div class="mi-order-detail-row">
                <span>Margem em R$</span>
                <strong class="{margem_variante}">{resultado}</strong>
            </div>
            <div class="mi-order-detail-row">
                <span>Margem percentual</span>
                <strong class="{margem_variante}">{margem_percentual}</strong>
            </div>
        </section>
    """
    st.html(detalhes)

    anterior, fechar, proximo = st.columns([1, 1, 1])
    with anterior:
        st.button(
            "← Anterior",
            key="pedido_detalhe_anterior",
            disabled=indice == 0,
            on_click=_navegar_detalhe,
            args=(-1,),
            width="stretch",
        )
    with fechar:
        st.button(
            "Fechar",
            key="pedido_detalhe_fechar",
            on_click=_fechar_detalhe,
            width="stretch",
        )
    with proximo:
        st.button(
            "Próximo →",
            key="pedido_detalhe_proximo",
            disabled=indice >= len(refs) - 1,
            on_click=_navegar_detalhe,
            args=(1,),
            width="stretch",
        )


animar_pagina("vendas_pedidos")
renderizar_animacoes_entrada_pagina()
cabecalho_pagina(
    "Vendas & Pedidos",
    "Consulte pedidos individuais e acompanhe os detalhes das vendas.",
    "▤",
)

skeleton_slot = st.empty()
if not st.session_state.get("_mi_vendas_pedidos_loaded", False):
    with skeleton_slot.container():
        renderizar_skeleton_vendas_pedidos()

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
pedidos["quantidade"] = pd.to_numeric(
    pedidos["quantidade"],
    errors="coerce",
)
pedidos["desconto"] = pd.to_numeric(
    pedidos["desconto"],
    errors="coerce",
).fillna(0)
for coluna in ("taxa_marketplace", "frete_vendedor"):
    pedidos[coluna] = pd.to_numeric(
        pedidos[coluna],
        errors="coerce",
    ).fillna(0)
skeleton_slot.empty()
st.session_state["_mi_vendas_pedidos_loaded"] = True

data_inicio = st.session_state.get("data_inicio")
data_fim = st.session_state.get("data_fim")
if not isinstance(data_inicio, date) or not isinstance(data_fim, date):
    skeleton_slot.empty()
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
filtrados["_row_ref"] = filtrados.index.astype(str)

titulo_secao(
    "Localizar pedidos",
    "Busque por número, produto ou SKU e refine por status.",
)
st.markdown(
    '<div class="mi-table-filters-anchor"></div>',
    unsafe_allow_html=True,
)
col_busca, col_status = st.columns([2.4, 1], gap="medium")
with col_busca:
    busca = st.text_input(
        "Buscar por pedido, produto ou SKU",
        placeholder="Digite um ID, nome de produto ou SKU...",
        icon=":material/search:",
        key="vendas_pedidos_busca",
    ).strip()
with col_status:
    status_disponiveis = sorted(
        filtrados["status"].dropna().astype(str).unique().tolist(),
        key=str.casefold,
    )
    status_opcoes = ["Todos", *status_disponiveis]
    if st.session_state.get("vendas_pedidos_status", "Todos") not in status_opcoes:
        st.session_state["vendas_pedidos_status"] = "Todos"
    status_selecionado = st.selectbox(
        "Status do pedido",
        status_opcoes,
        key="vendas_pedidos_status",
    )

filtros_ativos = []
if busca:
    filtros_ativos.append(
        badge_html(f"Busca: {busca}", "info")
    )
if status_selecionado != "Todos":
    filtros_ativos.append(
        badge_html(f"Status: {status_selecionado}", "neutral")
    )
if filtros_ativos:
    col_chips, col_limpar = st.columns([5, 1])
    with col_chips:
        st.html(
            '<div class="mi-filter-chip-row">'
            + "".join(filtros_ativos)
            + "</div>"
        )
    with col_limpar:
        st.button(
            "Limpar filtros",
            key="vendas_pedidos_limpar",
            type="tertiary",
            on_click=_limpar_filtros_locais,
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

assinatura_filtros = (
    data_inicio.isoformat(),
    data_fim.isoformat(),
    str(produto_global or ""),
    str(marketplace_global or ""),
    busca,
    status_selecionado,
)
if st.session_state.get("_vendas_pedidos_assinatura_filtros") != assinatura_filtros:
    st.session_state["vendas_pedidos_pagina"] = 0
    if st.session_state.get("_vendas_pedidos_detalhe_aberto"):
        _fechar_detalhe()
    st.session_state["_vendas_pedidos_assinatura_filtros"] = assinatura_filtros

calculos = _preparar_tabela(filtrados[[*COLUNAS_PEDIDOS, "_row_ref"]])
ordenar_por = st.session_state.get("vendas_pedidos_ordenar_por", "Data")
if ordenar_por not in CHAVES_ORDENACAO:
    ordenar_por = "Data"
    st.session_state["vendas_pedidos_ordenar_por"] = ordenar_por
ordem_crescente = st.session_state.get(
    "vendas_pedidos_ordem_crescente",
    False,
)

titulo_secao(
    "Resumo dos pedidos",
    "Indicadores calculados sobre os filtros globais e locais.",
)
bruto = filtrados["faturamento_bruto"].sum(min_count=1)
unidades = filtrados["quantidade"].sum(min_count=1)
liquido = calculos["Faturamento líquido"].sum(min_count=1)
margens_validas = calculos["Margem %"].dropna()
margem_media = margens_validas.mean() if not margens_validas.empty else pd.NA
cancelados = filtrados["status"].eq("Cancelado")
valor_cancelado = filtrados.loc[
    cancelados,
    "faturamento_bruto",
].sum(min_count=1)

resumo = [
    ("Pedidos", _numero_inteiro(len(filtrados)), "shopping-bag", "Pedidos após filtros", "normal"),
    ("Unidades", _numero_inteiro(unidades), "package", "Unidades vendidas", "normal"),
    ("Faturamento bruto", _moeda(bruto), "chart-coins", "Total bruto dos pedidos", "normal"),
    ("Faturamento líquido", _moeda(liquido), "chart-up", "Somente pedidos concluídos", "normal"),
    (
        "Margem média",
        _texto_percentual(margem_media),
        "chart-average",
        "Média das margens calculáveis",
        "positive" if pd.notna(margem_media) and margem_media >= 0 else
        "negative" if pd.notna(margem_media) else "neutral",
    ),
    (
        "Cancelados",
        _numero_inteiro(cancelados.sum()),
        "chart-down",
        f"{_moeda(valor_cancelado)} em valor bruto cancelado",
        "neutral",
    ),
]
colunas_resumo = st.columns(6, gap="small")
for coluna, (titulo, valor, icone, descricao, variante) in zip(
    colunas_resumo,
    resumo,
):
    with coluna:
        card(
            escape(titulo),
            valor,
            icone,
            escape(descricao),
            peso="operacional",
            tooltip=escape(descricao),
            cor_valor=variante,
        )

titulo_secao(
    "Detalhamento das vendas",
    (
        f"Período de {data_inicio.strftime('%d/%m/%Y')} a "
        f"{data_fim.strftime('%d/%m/%Y')} · "
        f"{_numero_inteiro(len(filtrados))} pedidos"
    ),
)

if filtrados.empty:
    st.html(
        f"""
        <div class="mi-empty-state">
            <span class="mi-empty-state-icon">{icone_svg("shopping-bag", tamanho=24)}</span>
            <strong>Nenhum pedido encontrado</strong>
            <span>Revise a busca e o status selecionado.</span>
        </div>
        """
    )
    if busca or status_selecionado != "Todos":
        st.button(
            "Limpar filtros",
            key="vendas_pedidos_limpar_vazio",
            on_click=_limpar_filtros_locais,
        )
else:
    if st.session_state.get("vendas_pedidos_tamanho_pagina", 15) not in {
        15,
        30,
        50,
    }:
        st.session_state["vendas_pedidos_tamanho_pagina"] = 15
    ordenada = _ordenar_tabela(calculos, ordenar_por, ordem_crescente)
    tamanho_pagina = st.session_state.get(
        "vendas_pedidos_tamanho_pagina",
        15,
    )
    total_paginas = max(
        (len(ordenada) + tamanho_pagina - 1) // tamanho_pagina,
        1,
    )
    pagina = min(
        max(st.session_state.get("vendas_pedidos_pagina", 0), 0),
        total_paginas - 1,
    )
    st.session_state["vendas_pedidos_pagina"] = pagina

    ordenar_coluna, direcao_coluna = st.columns([2, 1], gap="small")
    with ordenar_coluna:
        ordenar_por = st.selectbox(
            "Ordenar por",
            list(CHAVES_ORDENACAO),
            key="vendas_pedidos_ordenar_por",
            help="A ordem escolhida é aplicada à lista e ao CSV.",
        )
    with direcao_coluna:
        st.button(
            "↑ Crescente" if ordem_crescente else "↓ Decrescente",
            key="vendas_pedidos_alternar_ordem",
            type="secondary",
            on_click=_alternar_ordem,
            help="Alternar a direção da ordenação.",
        )

    ordem_crescente = st.session_state.get(
        "vendas_pedidos_ordem_crescente",
        False,
    )
    ordenada = _ordenar_tabela(calculos, ordenar_por, ordem_crescente)
    total_paginas = max(
        (len(ordenada) + tamanho_pagina - 1) // tamanho_pagina,
        1,
    )
    pagina = min(
        max(st.session_state.get("vendas_pedidos_pagina", 0), 0),
        total_paginas - 1,
    )
    st.session_state["vendas_pedidos_pagina"] = pagina
    inicio = pagina * tamanho_pagina
    linhas_pagina = ordenada.iloc[inicio:inicio + tamanho_pagina]

    st.markdown(
        '<div class="mi-orders-table-anchor"></div>',
        unsafe_allow_html=True,
    )
    versao_grid = st.session_state.get("_vendas_pedidos_grid_versao", 0)
    chave_grid = f"vendas_pedidos_grid_{versao_grid}"
    referencia_selecionada = None
    indice_selecionado = _indice_selecionado(chave_grid)
    if indice_selecionado is not None and indice_selecionado < len(linhas_pagina):
        referencia_selecionada = str(
            linhas_pagina.iloc[indice_selecionado]["_row_ref"]
        )

    instrucao, botao_detalhes = st.columns([5, 1], gap="small")
    with instrucao:
        st.html(
            '<div class="mi-order-open-instruction">'
            f'{icone_svg("file-text", tamanho=17)}'
            "<span>Marque a caixa à esquerda de um pedido para ver os detalhes</span>"
            "</div>"
        )
    with botao_detalhes:
        if st.button(
            "Ver detalhes",
            key="vendas_pedidos_ver_detalhes",
            icon=":material/description:",
            type="secondary",
            disabled=referencia_selecionada is None,
            width="stretch",
        ) and referencia_selecionada is not None:
            referencias = tuple(ordenada["_row_ref"].astype(str).tolist())
            _abrir_pedido(
                ordenada,
                referencias,
                referencia_selecionada,
            )

    with st.form("vendas_pedidos_abrir_numero", border=False):
        campo_coluna, submit_coluna = st.columns([3, 1], gap="small")
        with campo_coluna:
            numero_pedido = st.text_input(
                "Abrir pedido pelo número",
                placeholder="Digite o número do pedido",
                icon=":material/search:",
                key="vendas_pedidos_numero_detalhe",
            ).strip()
        with submit_coluna:
            abrir_por_numero = st.form_submit_button(
                "Abrir pedido",
                icon=":material/open_in_new:",
                type="secondary",
                width="stretch",
            )

    if abrir_por_numero:
        referencia_pedido = (
            ordenada.loc[
                ordenada["Pedido"].astype("string").str.strip()
                .eq(numero_pedido),
                "_row_ref",
            ]
            .astype(str)
        )
        if numero_pedido and not referencia_pedido.empty:
            referencias = tuple(ordenada["_row_ref"].astype(str).tolist())
            _abrir_pedido(
                ordenada,
                referencias,
                referencia_pedido.iloc[0],
            )
            st.session_state["_vendas_pedidos_busca_numero_nao_encontrado"] = ""
        else:
            st.session_state["_vendas_pedidos_busca_numero_nao_encontrado"] = (
                numero_pedido
            )
    numero_nao_encontrado = st.session_state.get(
        "_vendas_pedidos_busca_numero_nao_encontrado",
        "",
    )
    if numero_nao_encontrado:
        st.info(
            f"Pedido {numero_nao_encontrado} não encontrado nos pedidos filtrados."
        )

    _renderizar_grade_pedidos(
        ordenada,
        filtrados,
        ordenar_por,
        ordem_crescente,
        chave_grid,
    )

    if st.session_state.get("_vendas_pedidos_detalhe_aberto", False):
        _mostrar_detalhe_pedido(ordenada)
