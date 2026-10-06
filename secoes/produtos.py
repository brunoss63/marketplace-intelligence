from html import escape

import pandas as pd
import streamlit as st

from componentes import (
    badge_html,
    card,
    formatar_moeda_br,
    icone_svg,
    proxima_animacao_entrada_pagina,
    titulo_secao,
)


_CAMPOS_ESTOQUE = (
    "estoque_atual",
    "media_vendas_dia",
    "dias_estoque",
    "ponto_reposicao",
    "valor_estoque",
    "status_estoque",
    "dias_sem_estoque_estimados",
    "vendas_potenciais_perdidas",
    "receita_potencial_perdida",
)
_ESTADOS_PRODUTO = "_portfolio_produto_detalhe"


def _numero(valor: object, casas: int = 1) -> str:
    numero = pd.to_numeric(valor, errors="coerce")
    if pd.isna(numero):
        return "—"
    return (
        f"{float(numero):,.{casas}f}"
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )


def _percentual(valor: object) -> str:
    texto = _numero(valor, 1)
    return "—" if texto == "—" else f"{texto}%"


def _cobertura(valor: object) -> str:
    numero = pd.to_numeric(valor, errors="coerce")
    if pd.isna(numero):
        return "—"
    if numero == float("inf"):
        return "Sem giro"
    return f"{_numero(numero)} dias"


def _classificar_status_exibicao(linha: pd.Series) -> str:
    if linha["estoque_atual"] <= 0:
        return "Sem estoque"
    if linha["dias_estoque"] < 7:
        return "Crítico"
    if linha["dias_estoque"] <= 15:
        return "Atenção"
    if linha["media_vendas_dia"] == 0 or linha["dias_estoque"] > 45:
        return "Parado"
    return "Normal"


def _preparar_catalogo(
    produtos: pd.DataFrame,
    estoque: pd.DataFrame,
) -> pd.DataFrame:
    catalogo = produtos.copy()
    campos_disponiveis = [
        campo for campo in _CAMPOS_ESTOQUE
        if campo in estoque.columns and campo not in catalogo.columns
    ]
    if campos_disponiveis:
        catalogo = catalogo.merge(
            estoque[["sku", *campos_disponiveis]],
            on="sku",
            how="left",
        )
    for campo in _CAMPOS_ESTOQUE:
        if campo not in catalogo.columns:
            catalogo[campo] = 0
    catalogo["faturamento_liquido"] = (
        catalogo["faturamento"] - catalogo["descontos"]
        - catalogo["taxas"] - catalogo["frete"]
    )
    catalogo["status_portfolio"] = catalogo.apply(
        _classificar_status_exibicao,
        axis=1,
    )
    return catalogo


def _estilo_linha_portfolio(linha: pd.Series) -> list[str]:
    estilos = [""] * len(linha)
    for indice, coluna in enumerate(linha.index):
        texto = str(linha.iloc[indice])
        if coluna == "Margem após anúncios":
            if texto.startswith("-"):
                estilos[indice] = "color: #FF806D; font-weight: 650;"
            elif texto != "—":
                estilos[indice] = "color: #4ADE80; font-weight: 650;"
        elif coluna == "Cobertura":
            if texto != "Sem giro" and texto != "—":
                dias = float(
                    texto.split()[0].replace(".", "").replace(",", ".")
                )
                if dias < 15:
                    estilos[indice] = "color: #FF806D; font-weight: 600;"
                elif dias > 45:
                    estilos[indice] = "color: #F6C85F; font-weight: 600;"
        elif coluna == "Status":
            if texto in {"Sem estoque", "Crítico"}:
                estilos[indice] = "color: #FF806D; font-weight: 650;"
            elif texto == "Atenção":
                estilos[indice] = "color: #F6C85F; font-weight: 650;"
            elif texto == "Parado":
                estilos[indice] = "color: #A8B6C9; font-weight: 600;"
            elif texto == "Normal":
                estilos[indice] = "color: #8292A8;"
        elif coluna in {"Resultado após anúncios", "Venda potencial perdida"}:
            if texto.startswith("-R$"):
                estilos[indice] = "color: #FF806D; font-weight: 600;"
    return estilos


def _persistir_filtro(chave_widget: str, chave_dado: str) -> None:
    st.session_state[chave_dado] = st.session_state[chave_widget]


def _restaurar_filtro(chave_widget: str, chave_dado: str, padrao) -> None:
    if chave_widget not in st.session_state and chave_dado in st.session_state:
        st.session_state[chave_widget] = st.session_state[chave_dado]
    elif chave_widget not in st.session_state:
        st.session_state[chave_widget] = padrao


def _estado_selecionado(chave_grid: str) -> int | None:
    estado = st.session_state.get(chave_grid, {})
    if not isinstance(estado, dict):
        return None
    selecao = estado.get("selection", {})
    if not isinstance(selecao, dict):
        return None
    linhas = selecao.get("rows", [])
    return int(linhas[0]) if linhas else None


def _abrir_detalhe_produto(
    produtos_ordenados: pd.DataFrame,
    sku: str,
) -> None:
    referencias = tuple(produtos_ordenados["sku"].astype(str).tolist())
    if sku not in referencias:
        return
    st.session_state[_ESTADOS_PRODUTO] = {
        "aberto": True,
        "referencias": referencias,
        "indice": referencias.index(sku),
    }


def _fechar_detalhe_produto() -> None:
    st.session_state[_ESTADOS_PRODUTO] = {
        "aberto": False,
        "referencias": (),
        "indice": 0,
    }
    st.session_state["_portfolio_produto_grid_versao"] = (
        st.session_state.get("_portfolio_produto_grid_versao", 0) + 1
    )


def _navegar_detalhe_produto(delta: int) -> None:
    estado = st.session_state.get(_ESTADOS_PRODUTO, {})
    referencias = estado.get("referencias", ())
    indice = estado.get("indice", 0)
    if referencias:
        indice = min(max(indice + delta, 0), len(referencias) - 1)
        estado["indice"] = indice
        st.session_state[_ESTADOS_PRODUTO] = estado


@st.dialog(
    "Detalhes do produto",
    width="large",
    dismissible=True,
    on_dismiss=_fechar_detalhe_produto,
)
def _mostrar_detalhe_produto(catalogo_ordenado: pd.DataFrame) -> None:
    estado = st.session_state.get(_ESTADOS_PRODUTO, {})
    referencias = estado.get("referencias", ())
    indice = estado.get("indice", 0)
    if not referencias or indice >= len(referencias):
        st.info("Este produto não está mais disponível nos filtros atuais.")
        st.button(
            "Fechar",
            key="portfolio_produto_detalhe_vazio_fechar",
            on_click=_fechar_detalhe_produto,
        )
        return

    sku = referencias[indice]
    produto_encontrado = catalogo_ordenado[
        catalogo_ordenado["sku"].astype(str).eq(sku)
    ]
    if produto_encontrado.empty:
        st.info("Este produto não está mais disponível nos filtros atuais.")
        st.button(
            "Fechar",
            key="portfolio_produto_detalhe_indisponivel_fechar",
            on_click=_fechar_detalhe_produto,
        )
        return

    produto = produto_encontrado.iloc[0]
    margem = float(produto["margem"])
    classe_margem = (
        "mi-order-detail-result-negative"
        if margem < 0
        else "mi-order-detail-result-positive"
    )
    status = str(produto["status_portfolio"])
    variante_status = (
        "error" if status in {"Sem estoque", "Crítico"}
        else "warning" if status == "Atenção"
        else "neutral"
    )
    st.html(
        f"""
        <div class="mi-order-detail-header mi-order-detail-enter">
            <div>
                <h3 class="mi-order-detail-id">
                    {escape(str(produto['produto']))}
                </h3>
                <div class="mi-order-detail-meta">
                    SKU {escape(str(produto['sku']))} ·
                    {escape(str(produto['categoria']))} ·
                    {escape(str(produto['canal']))}
                </div>
            </div>
            {badge_html(status, variante_status)}
        </div>
        <section class="mi-order-detail-section mi-order-detail-enter"
                 style="--mi-detail-delay:45ms">
            <h4 class="mi-order-detail-section-title">Cadastro</h4>
            <div class="mi-order-detail-row">
                <span>Preço de venda</span>
                <strong>{formatar_moeda_br(produto['preco_venda'])}</strong>
            </div>
            <div class="mi-order-detail-row">
                <span>Custo unitário</span>
                <strong>{formatar_moeda_br(produto['custo_unitario'])}</strong>
            </div>
        </section>
        <section class="mi-order-detail-section mi-order-detail-enter"
                 style="--mi-detail-delay:90ms">
            <h4 class="mi-order-detail-section-title">
                Desempenho no período
            </h4>
            <div class="mi-order-detail-row">
                <span>Unidades</span><strong>{_numero(produto['unidades'], 0)}</strong>
            </div>
            <div class="mi-order-detail-row">
                <span>Faturamento bruto</span>
                <strong>{formatar_moeda_br(produto['faturamento'])}</strong>
            </div>
            <div class="mi-order-detail-row">
                <span>Faturamento líquido</span>
                <strong>{formatar_moeda_br(produto['faturamento_liquido'])}</strong>
            </div>
            <div class="mi-order-detail-row">
                <span>Resultado após anúncios</span>
                <strong class="{classe_margem}">
                    {formatar_moeda_br(produto['resultado'])}
                </strong>
            </div>
            <div class="mi-order-detail-row">
                <span>Margem após anúncios</span>
                <strong class="{classe_margem}">{_percentual(margem)}</strong>
            </div>
            <div class="mi-order-detail-row">
                <span>ROAS</span><strong>{_numero(produto['roas'], 2)}x</strong>
            </div>
        </section>
        <section class="mi-order-detail-section mi-order-detail-enter"
                 style="--mi-detail-delay:135ms">
            <h4 class="mi-order-detail-section-title">Estoque</h4>
            <div class="mi-order-detail-row">
                <span>Estoque atual</span>
                <strong>{_numero(produto['estoque_atual'], 0)} un.</strong>
            </div>
            <div class="mi-order-detail-row">
                <span>Vendas/dia</span>
                <strong>{_numero(produto['media_vendas_dia'], 2)}</strong>
            </div>
            <div class="mi-order-detail-row">
                <span>Cobertura</span><strong>{_cobertura(produto['dias_estoque'])}</strong>
            </div>
            <div class="mi-order-detail-row">
                <span>Ponto de reposição</span>
                <strong>{_numero(produto['ponto_reposicao'], 0)} un.</strong>
            </div>
            <div class="mi-order-detail-row">
                <span>Valor em estoque</span>
                <strong>{formatar_moeda_br(produto['valor_estoque'])}</strong>
            </div>
        </section>
        """
    )
    anterior, fechar, proximo = st.columns(3)
    with anterior:
        st.button(
            "← Anterior",
            key="portfolio_produto_detalhe_anterior",
            disabled=indice == 0,
            on_click=_navegar_detalhe_produto,
            args=(-1,),
            width="stretch",
        )
    with fechar:
        st.button(
            "Fechar",
            key="portfolio_produto_detalhe_fechar",
            on_click=_fechar_detalhe_produto,
            width="stretch",
        )
    with proximo:
        st.button(
            "Próximo →",
            key="portfolio_produto_detalhe_proximo",
            disabled=indice >= len(referencias) - 1,
            on_click=_navegar_detalhe_produto,
            args=(1,),
            width="stretch",
        )


def _formatar_tabela(catalogo: pd.DataFrame, visao: str) -> pd.DataFrame:
    mapa = {
        "Produto": catalogo["produto"],
        "SKU": catalogo["sku"],
        "Categoria": catalogo["categoria"],
        "Canal": catalogo["canal"],
        "Preço": catalogo["preco_venda"].map(formatar_moeda_br),
        "Custo unitário": catalogo["custo_unitario"].map(formatar_moeda_br),
        "Unidades": catalogo["unidades"].map(lambda valor: _numero(valor, 0)),
        "Faturamento bruto": catalogo["faturamento"].map(formatar_moeda_br),
        "Faturamento líquido": catalogo["faturamento_liquido"].map(formatar_moeda_br),
        "Resultado após anúncios": catalogo["resultado"].map(formatar_moeda_br),
        "Margem após anúncios": catalogo["margem"].map(_percentual),
        "ROAS": catalogo["roas"].map(lambda valor: f"{_numero(valor, 2)}x"),
        "Estoque": catalogo["estoque_atual"].map(lambda valor: _numero(valor, 0)),
        "Vendas/dia": catalogo["media_vendas_dia"].map(lambda valor: _numero(valor, 2)),
        "Cobertura": catalogo["dias_estoque"].map(_cobertura),
        "Ponto de reposição": catalogo["ponto_reposicao"].map(lambda valor: _numero(valor, 0)),
        "Valor em estoque": catalogo["valor_estoque"].map(formatar_moeda_br),
        "Dias sem estoque": catalogo["dias_sem_estoque_estimados"].map(
            lambda valor: _numero(valor, 0)
        ),
        "Venda potencial perdida": catalogo["receita_potencial_perdida"].map(formatar_moeda_br),
        "Status": catalogo["status_portfolio"].replace({"Normal": "—"}),
    }
    colunas = {
        "Geral": (
            "Produto", "SKU", "Categoria", "Canal", "Unidades",
            "Faturamento bruto", "Margem após anúncios", "ROAS",
            "Estoque", "Cobertura", "Status",
        ),
        "Estoque": (
            "Produto", "SKU", "Estoque", "Vendas/dia", "Cobertura",
            "Ponto de reposição", "Valor em estoque", "Dias sem estoque",
            "Venda potencial perdida", "Status",
        ),
        "Rentabilidade": (
            "Produto", "SKU", "Categoria", "Canal", "Preço",
            "Custo unitário", "Unidades", "Faturamento bruto",
            "Faturamento líquido", "Resultado após anúncios",
            "Margem após anúncios", "ROAS",
        ),
    }[visao]
    return pd.DataFrame({coluna: mapa[coluna] for coluna in colunas})


def _mostrar_portfolio(catalogo: pd.DataFrame) -> None:
    titulo_secao(
        "Portfólio",
        "Consulte cadastro, estoque e rentabilidade em uma tabela.",
    )
    filtro_busca, filtro_categoria, filtro_status, filtro_ordem = st.columns(
        [2, 1.35, 1.2, 1.35],
        gap="small",
    )
    chave_busca = "portfolio_produtos_busca"
    chave_categoria = "portfolio_produtos_categoria"
    chave_status = "portfolio_produtos_status"
    chave_ordem = "portfolio_produtos_ordem"
    chave_visao = "portfolio_produtos_visao"
    for widget, dado, padrao in (
        (chave_busca, "_portfolio_busca", ""),
        (chave_categoria, "_portfolio_categoria", "Todas"),
        (chave_status, "_portfolio_status", "Todos"),
        (chave_ordem, "_portfolio_ordem", "Maior faturamento"),
        (chave_visao, "_portfolio_visao", "Geral"),
        (
            "portfolio_produtos_tamanho_pagina",
            "_portfolio_tamanho_pagina",
            15,
        ),
    ):
        _restaurar_filtro(widget, dado, padrao)

    with filtro_busca:
        busca = st.text_input(
            "Buscar produto ou SKU",
            placeholder="Digite um produto ou SKU",
            icon=":material/search:",
            key=chave_busca,
            on_change=_persistir_filtro,
            args=(chave_busca, "_portfolio_busca"),
        ).strip()
    with filtro_categoria:
        categorias = ["Todas"] + sorted(
            catalogo["categoria"].dropna().astype(str).unique().tolist()
        )
        if st.session_state[chave_categoria] not in categorias:
            st.session_state[chave_categoria] = "Todas"
        categoria = st.selectbox(
            "Categoria",
            categorias,
            key=chave_categoria,
            on_change=_persistir_filtro,
            args=(chave_categoria, "_portfolio_categoria"),
        )
    with filtro_status:
        status_opcoes = ["Todos"] + [
            "Sem estoque", "Crítico", "Atenção", "Parado", "Normal"
        ]
        if st.session_state[chave_status] not in status_opcoes:
            st.session_state[chave_status] = "Todos"
        status = st.selectbox(
            "Status",
            status_opcoes,
            key=chave_status,
            on_change=_persistir_filtro,
            args=(chave_status, "_portfolio_status"),
        )
    with filtro_ordem:
        ordens = [
            "Maior faturamento",
            "Maior margem",
            "Maior resultado",
            "Menor cobertura",
            "Maior venda potencial perdida",
        ]
        if st.session_state[chave_ordem] not in ordens:
            st.session_state[chave_ordem] = ordens[0]
        ordem = st.selectbox(
            "Ordenar por",
            ordens,
            key=chave_ordem,
            on_change=_persistir_filtro,
            args=(chave_ordem, "_portfolio_ordem"),
        )
    opcoes_visao = ["Geral", "Estoque", "Rentabilidade"]
    if st.session_state[chave_visao] not in opcoes_visao:
        st.session_state[chave_visao] = "Geral"
    visao = st.radio(
        "Visão da tabela",
        opcoes_visao,
        horizontal=True,
        key=chave_visao,
        on_change=_persistir_filtro,
        args=(chave_visao, "_portfolio_visao"),
    )

    filtrado = catalogo.copy()
    if busca:
        corresponde = (
            filtrado["produto"].astype(str).str.contains(
                busca, case=False, regex=False, na=False
            )
            | filtrado["sku"].astype(str).str.contains(
                busca, case=False, regex=False, na=False
            )
        )
        filtrado = filtrado[corresponde]
    if categoria != "Todas":
        filtrado = filtrado[filtrado["categoria"].astype(str) == categoria]
    if status != "Todos":
        filtrado = filtrado[filtrado["status_portfolio"] == status]

    colunas_ordem = {
        "Maior faturamento": ("faturamento", False),
        "Maior margem": ("margem", False),
        "Maior resultado": ("resultado", False),
        "Menor cobertura": ("dias_estoque", True),
        "Maior venda potencial perdida": ("receita_potencial_perdida", False),
    }
    campo_ordem, crescente = colunas_ordem[ordem]
    filtrado = filtrado.sort_values(
        campo_ordem,
        ascending=crescente,
        na_position="last",
        kind="mergesort",
    ).reset_index(drop=True)

    tamanho_pagina = st.session_state.get(
        "portfolio_produtos_tamanho_pagina",
        15,
    )
    tamanho_pagina = tamanho_pagina if tamanho_pagina in {15, 30, 50} else 15
    total_paginas = max(
        (len(filtrado) + tamanho_pagina - 1) // tamanho_pagina,
        1,
    )
    pagina = min(
        max(st.session_state.get("portfolio_produtos_pagina", 0), 0),
        total_paginas - 1,
    )
    st.session_state["portfolio_produtos_pagina"] = pagina
    inicio = pagina * tamanho_pagina
    linhas_pagina = filtrado.iloc[inicio:inicio + tamanho_pagina].copy()
    apresentacao = _formatar_tabela(linhas_pagina, visao)

    instrucao, botao = st.columns([5, 1], gap="small")
    with instrucao:
        st.html(
            '<div class="mi-order-open-instruction">'
            f'{icone_svg("package", tamanho=17)}'
            "<span>Marque a caixa à esquerda de um produto para ver os detalhes</span>"
            "</div>"
        )
    versao_grid = st.session_state.get("_portfolio_produto_grid_versao", 0)
    chave_grid = f"portfolio_produto_grid_{versao_grid}"
    indice = _estado_selecionado(chave_grid)
    sku_selecionado = (
        str(linhas_pagina.iloc[indice]["sku"])
        if indice is not None and indice < len(linhas_pagina)
        else None
    )
    with botao:
        if st.button(
            "Ver detalhes",
            key="portfolio_produto_ver_detalhes",
            icon=":material/description:",
            type="secondary",
            disabled=sku_selecionado is None,
            width="stretch",
        ) and sku_selecionado is not None:
            _abrir_detalhe_produto(filtrado, sku_selecionado)

    with st.form("portfolio_produto_abrir", border=False):
        campo, enviar = st.columns([3, 1], gap="small")
        with campo:
            busca_produto = st.text_input(
                "Abrir produto pelo SKU ou nome",
                placeholder="Digite SKU ou nome do produto",
                icon=":material/search:",
                key="portfolio_produto_busca_detalhe",
            ).strip()
        with enviar:
            abrir = st.form_submit_button(
                "Abrir produto",
                icon=":material/open_in_new:",
                type="secondary",
                width="stretch",
            )
    if abrir:
        corresponde = filtrado[
            filtrado["sku"].astype(str).str.casefold().eq(
                busca_produto.casefold()
            )
            | filtrado["produto"].astype(str).str.casefold().eq(
                busca_produto.casefold()
            )
        ]
        if busca_produto and not corresponde.empty:
            _abrir_detalhe_produto(filtrado, str(corresponde.iloc[0]["sku"]))
            st.session_state["_portfolio_produto_nao_encontrado"] = ""
        else:
            st.session_state["_portfolio_produto_nao_encontrado"] = busca_produto
    nao_encontrado = st.session_state.get(
        "_portfolio_produto_nao_encontrado",
        "",
    )
    if nao_encontrado:
        st.info(f"Produto {nao_encontrado} não encontrado nos produtos filtrados.")

    config = {
        nome: st.column_config.TextColumn(
            label=nome,
            pinned="left" if nome in {"Produto", "SKU"} else None,
            width=(
                "large" if nome == "Produto"
                else "medium" if nome == "SKU"
                else "small" if nome in {"Unidades", "Estoque", "ROAS"}
                else "medium"
            ),
        )
        for nome in apresentacao.columns
    }
    animar_tabela, atraso_tabela = proxima_animacao_entrada_pagina()
    if animar_tabela:
        st.html(
            '<span class="mi-product-table-entering" '
            f'style="--mi-entry-delay:{atraso_tabela}ms"></span>'
        )
    estado_grid = st.dataframe(
        apresentacao.style.apply(_estilo_linha_portfolio, axis=1),
        column_config=config,
        hide_index=True,
        height=min(690, max(385, tamanho_pagina * 35 + 42)),
        on_select="rerun",
        selection_mode="single-row",
        key=chave_grid,
        width="stretch",
    )
    linhas_selecionadas = estado_grid.selection.rows
    if linhas_selecionadas and not st.session_state.get(
        _ESTADOS_PRODUTO,
        {},
    ).get("aberto", False):
        indice_selecionado = linhas_selecionadas[0]
        if 0 <= indice_selecionado < len(linhas_pagina):
            _abrir_detalhe_produto(
                filtrado,
                str(linhas_pagina.iloc[indice_selecionado]["sku"]),
            )

    controles = st.columns([1, 1, 1.5, 1], gap="small")
    with controles[0]:
        st.button(
            "← Anterior",
            key="portfolio_produtos_pagina_anterior",
            disabled=pagina == 0,
            on_click=_alterar_pagina_portfolio,
            args=(-1, total_paginas),
            width="stretch",
        )
    with controles[1]:
        st.button(
            "Próxima →",
            key="portfolio_produtos_pagina_proxima",
            disabled=pagina >= total_paginas - 1,
            on_click=_alterar_pagina_portfolio,
            args=(1, total_paginas),
            width="stretch",
        )
    with controles[2]:
        st.html(
            f'<div class="mi-pagination-label">'
            f'Página {pagina + 1} de {total_paginas} · '
            f'{len(filtrado)} produtos</div>'
        )
    with controles[3]:
        st.selectbox(
            "Itens por página",
            [15, 30, 50],
            key="portfolio_produtos_tamanho_pagina",
            on_change=_alterar_tamanho_pagina,
        )

    if st.session_state.get(_ESTADOS_PRODUTO, {}).get("aberto", False):
        _mostrar_detalhe_produto(filtrado)


def _alterar_pagina_portfolio(delta: int, total_paginas: int) -> None:
    atual = st.session_state.get("portfolio_produtos_pagina", 0)
    st.session_state["portfolio_produtos_pagina"] = min(
        max(atual + delta, 0),
        max(total_paginas - 1, 0),
    )


def _alterar_tamanho_pagina() -> None:
    st.session_state["_portfolio_tamanho_pagina"] = st.session_state[
        "portfolio_produtos_tamanho_pagina"
    ]
    st.session_state["portfolio_produtos_pagina"] = 0


def _ranking_visual(
    dados: pd.DataFrame,
    *,
    titulo: str,
    subtitulo: str,
    coluna_valor: str,
    formatador,
    divergir: bool = False,
) -> None:
    selecionados = dados.nlargest(10, coluna_valor).reset_index(drop=True)
    escala = (
        float(selecionados[coluna_valor].abs().max())
        if divergir and not selecionados.empty
        else float(selecionados[coluna_valor].max())
        if not selecionados.empty
        else 0
    )
    linhas = []
    for indice, produto in selecionados.iterrows():
        valor = float(produto[coluna_valor])
        classe_entrada, atraso = proxima_animacao_entrada_pagina()
        largura = (
            min(abs(valor) / escala * 50, 50)
            if divergir and escala > 0
            else max(valor / escala * 100, 2)
            if escala > 0
            else 0
        )
        if divergir:
            posicao = (
                f"left:calc(50% - {largura:.1f}%);"
                if valor < 0
                else f"left:50%;"
            )
            classe_barra = (
                "mi-product-ranking-bar-negative"
                + (" mi-entry-negative-bar" if classe_entrada else "")
                if valor < 0
                else (
                    "mi-product-ranking-bar-positive"
                    + (" mi-entry-positive-bar" if classe_entrada else "")
                )
            )
            cor_barra = "#FF806D" if valor < 0 else "#73A9FF"
            barra = (
                '<span class="mi-product-ranking-zero"></span>'
                f'<span class="mi-product-ranking-bar {classe_barra}" '
                f'style="{posicao}width:{largura:.1f}%;'
                f'--mi-entry-delay:{atraso}ms;background:{cor_barra}"></span>'
            )
        else:
            barra = (
                '<span class="mi-product-ranking-bar '
                'mi-product-ranking-bar-positive '
                f'{"mi-entry-progress" if classe_entrada else ""}" '
                f'style="--mi-progress-target:{largura:.1f}%;'
                f'width:{largura:.1f}%;--mi-entry-delay:{atraso}ms;'
                'background:#73A9FF"></span>'
            )
        nome = escape(str(produto["produto"]))
        linhas.append(
            f"""
            <div class="mi-product-ranking-row {'mi-entry-card' if classe_entrada else ''}"
                 style="--mi-entry-delay:{atraso}ms">
                <span class="mi-product-ranking-position">{indice + 1}</span>
                <span class="mi-product-ranking-name">{nome}</span>
                <span class="mi-product-ranking-bar-track {'mi-product-ranking-diverging' if divergir else ''}">
                    {barra}
                </span>
                <span class="mi-product-ranking-value">
                    {escape(formatador(valor))}
                </span>
            </div>
            """
        )
    if not linhas:
        linhas.append(
            '<div class="mi-product-ranking-empty">'
            "Sem produtos com vendas no período selecionado."
            "</div>"
        )
    st.html(
        f"""
        <div class="mi-chart-heading mi-dashboard-panel">
            <div class="mi-chart-title">{escape(titulo)}</div>
            <div class="mi-chart-subtitle">{escape(subtitulo)}</div>
        </div>
        <div class="mi-product-ranking">{''.join(linhas)}</div>
        """
    )


def mostrar_produtos(
    produtos: pd.DataFrame,
    estoque: pd.DataFrame,
) -> None:
    catalogo = _preparar_catalogo(produtos, estoque)
    vendidos = catalogo[catalogo["unidades"] > 0].copy()
    titulo_secao(
        "Desempenho",
        "Rankings e destaques do catálogo no período selecionado.",
    )
    st.html(
        """
        <style>
            .mi-product-ranking {
                display: flex;
                flex-direction: column;
                gap: 3px;
                padding: 4px 2px;
            }
            .mi-product-ranking-row {
                display: grid;
                grid-template-columns: 22px minmax(110px, 1fr)
                    minmax(60px, 120px) minmax(95px, 125px);
                align-items: center;
                gap: 10px;
                min-height: 31px;
                color: #DCE5F0;
                font-size: 12px;
            }
            .mi-product-ranking-position {
                color: #8FA1B8;
                font-variant-numeric: tabular-nums;
            }
            .mi-product-ranking-name {
                color: #DCE5F0;
                font-size: 12px;
                overflow-wrap: anywhere;
            }
            .mi-product-ranking-bar-track {
                position: relative;
                overflow: hidden;
                height: 7px;
                border-radius: 99px;
                background: rgba(143, 161, 184, .13);
            }
            .mi-product-ranking-bar {
                position: absolute;
                top: 0;
                height: 100%;
                border-radius: inherit;
            }
            .mi-product-ranking-bar-positive {
                left: 0;
                background: #73A9FF;
            }
            .mi-product-ranking-bar-negative {
                background: #FF806D;
            }
            .mi-entry-negative-bar {
                animation: mi-product-negative-grow 420ms
                    cubic-bezier(.22,.61,.36,1) both;
                animation-delay: var(--mi-entry-delay, 0ms);
                transform-origin: right center;
            }
            .mi-entry-positive-bar {
                animation: mi-product-positive-grow 420ms
                    cubic-bezier(.22,.61,.36,1) both;
                animation-delay: var(--mi-entry-delay, 0ms);
                transform-origin: left center;
            }
            @keyframes mi-product-negative-grow {
                from { transform: scaleX(0); }
                to { transform: scaleX(1); }
            }
            @keyframes mi-product-positive-grow {
                from { transform: scaleX(0); }
                to { transform: scaleX(1); }
            }
            .mi-product-ranking-zero {
                position: absolute;
                z-index: 1;
                top: -2px;
                left: 50%;
                width: 1px;
                height: 11px;
                background: #CBD5E1;
            }
            .mi-product-ranking-value {
                color: #F1F5F9;
                font-size: 12px;
                font-variant-numeric: tabular-nums;
                font-weight: 650;
                text-align: right;
                white-space: nowrap;
            }
            .mi-product-ranking-empty {
                padding: 18px 2px;
                color: #A8B6C9;
                font-size: 12px;
            }
            @media (prefers-reduced-motion: reduce) {
                .mi-entry-positive-bar,
                .mi-entry-negative-bar {
                    animation: none;
                    transform: none;
                }
            }
        </style>
        """
    )
    col_faturamento, col_margem = st.columns(2, gap="medium")
    limite = min(len(vendidos), 10)
    with col_faturamento:
        with st.container(border=True):
            _ranking_visual(
                vendidos,
                titulo="Ranking por faturamento",
                subtitulo=f"{limite} produtos · faturamento bruto no período",
                coluna_valor="faturamento",
                formatador=formatar_moeda_br,
            )
    with col_margem:
        with st.container(border=True):
            _ranking_visual(
                vendidos,
                titulo="Ranking por margem",
                subtitulo=f"{limite} produtos · margem após custos e anúncios",
                coluna_valor="margem",
                formatador=_percentual,
                divergir=True,
            )

    if not vendidos.empty:
        maior_venda = vendidos.loc[vendidos["faturamento"].idxmax()]
        maior_margem = vendidos.loc[vendidos["margem"].idxmax()]
        maior_roas = vendidos.loc[vendidos["roas"].idxmax()]
        destaques = [
            (
                "Maior faturamento",
                formatar_moeda_br(maior_venda["faturamento"]),
                "chart-coins",
                f"{maior_venda['produto']} · "
                f"{_percentual(maior_venda['participacao_faturamento'])} do faturamento",
            ),
            (
                "Maior margem após anúncios",
                _percentual(maior_margem["margem"]),
                "chart-up",
                f"{maior_margem['produto']} · "
                f"{_numero(maior_margem['unidades'], 0)} unidades · "
                f"{formatar_moeda_br(maior_margem['faturamento'])} bruto",
            ),
            (
                "Melhor ROAS",
                f"{_numero(maior_roas['roas'], 2)}x",
                "target",
                f"{maior_roas['produto']} · "
                f"{formatar_moeda_br(maior_roas['publicidade'])} investidos",
            ),
        ]
        colunas = st.columns(3, gap="small")
        for coluna, (rotulo, valor, icone, contexto) in zip(
            colunas,
            destaques,
        ):
            with coluna:
                card(
                    rotulo,
                    valor,
                    icone,
                    contexto,
                    tipo="positive",
                    peso="operacional",
                    cor_valor="positive",
                )


def mostrar_portfolio(
    produtos: pd.DataFrame,
    estoque: pd.DataFrame,
) -> None:
    _mostrar_portfolio(_preparar_catalogo(produtos, estoque))
