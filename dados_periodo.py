from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from armazenamento import is_database_mode, ler_dataset


def obter_periodo_anterior(
    data_inicio: date,
    data_fim: date
) -> tuple[date, date]:
    """Retorna um período anterior com a mesma duração do período atual."""

    duracao = data_fim - data_inicio
    fim_anterior = data_inicio - timedelta(days=1)
    inicio_anterior = fim_anterior - duracao

    return inicio_anterior, fim_anterior


def obter_kpis_financeiros(
    data_inicio: date,
    data_fim: date,
    produto: str | None = None,
    marketplace: str | None = None
) -> dict[str, float]:
    """Calcula os principais indicadores financeiros do período."""

    produtos = ler_dataset("dados/produtos.csv")
    pedidos = ler_dataset("dados/pedidos.csv")
    publicidade = ler_dataset("dados/publicidade.csv")

    if "desconto" not in pedidos.columns:
        pedidos["desconto"] = 0.0
    pedidos["desconto"] = pd.to_numeric(
        pedidos["desconto"],
        errors="coerce",
    ).fillna(0)
    pedidos["data"] = pd.to_datetime(pedidos["data"])
    publicidade["data"] = pd.to_datetime(publicidade["data"])
    skus_produto = (
        produtos.loc[produtos["produto"] == produto, "sku"]
        if produto is not None
        else None
    )

    pedidos = pedidos[
        (pedidos["status"] == "Concluído")
        & (pedidos["data"].dt.date >= data_inicio)
        & (pedidos["data"].dt.date <= data_fim)
    ]
    if skus_produto is not None:
        pedidos = pedidos[pedidos["sku"].isin(skus_produto)]
        publicidade = publicidade[
            publicidade["sku"].isin(skus_produto)
        ]
    if marketplace is not None:
        pedidos = pedidos[pedidos["marketplace"] == marketplace]
        publicidade = publicidade[
            publicidade["marketplace"] == marketplace
        ]

    pedidos = pedidos.merge(
        produtos[["sku", "custo_unitario"]],
        on="sku",
        how="left"
    )

    publicidade = publicidade[
        (publicidade["data"].dt.date >= data_inicio)
        & (publicidade["data"].dt.date <= data_fim)
    ]

    faturamento_bruto = float(pedidos["faturamento_bruto"].sum())
    custo_produtos = float(
        (pedidos["quantidade"] * pedidos["custo_unitario"]).sum()
    )
    taxas = float(pedidos["taxa_marketplace"].sum())
    frete = float(pedidos["frete_vendedor"].sum())
    descontos = float(pedidos["desconto"].sum())
    investimento_publicidade = float(publicidade["investimento"].sum())
    receita_publicidade = float(publicidade["receita_atribuida"].sum())
    pedidos_total = float(len(pedidos))
    unidades = float(pedidos["quantidade"].sum())

    faturamento_liquido = faturamento_bruto - descontos - taxas - frete
    resultado = (
        faturamento_liquido
        - custo_produtos
        - investimento_publicidade
    )

    return {
        "faturamento_bruto": faturamento_bruto,
        "faturamento_liquido": faturamento_liquido,
        "custo_produtos": custo_produtos,
        "taxas": taxas,
        "frete": frete,
        "descontos": descontos,
        "investimento_publicidade": investimento_publicidade,
        "receita_publicidade": receita_publicidade,
        "resultado": resultado,
        "margem": (
            resultado / (faturamento_bruto - descontos) * 100
            if faturamento_bruto - descontos > 0
            else 0
        ),
        "ticket_medio": (
            (faturamento_bruto - descontos) / pedidos_total
            if pedidos_total > 0
            else 0
        ),
        "roas": (
            receita_publicidade / investimento_publicidade
            if investimento_publicidade > 0
            else 0
        ),
        "pedidos": pedidos_total,
        "unidades": unidades,
    }


def obter_desempenho_produtos(
    data_inicio: date,
    data_fim: date,
    produto: str | None = None,
    marketplace: str | None = None
) -> pd.DataFrame:
    """Calcula o desempenho dos produtos dentro do período selecionado."""

    produtos = ler_dataset("dados/produtos.csv")
    pedidos = ler_dataset("dados/pedidos.csv")
    publicidade = ler_dataset("dados/publicidade.csv")
    if "desconto" not in pedidos.columns:
        pedidos["desconto"] = 0.0
    pedidos["desconto"] = pd.to_numeric(
        pedidos["desconto"],
        errors="coerce",
    ).fillna(0)
    if produto is not None:
        produtos = produtos[produtos["produto"] == produto].copy()
        skus_selecionados = produtos["sku"]
        pedidos = pedidos[pedidos["sku"].isin(skus_selecionados)]
        publicidade = publicidade[
            publicidade["sku"].isin(skus_selecionados)
        ]
    if marketplace is not None:
        pedidos = pedidos[pedidos["marketplace"] == marketplace]
        publicidade = publicidade[
            publicidade["marketplace"] == marketplace
        ]

    pedidos["data"] = pd.to_datetime(pedidos["data"])
    publicidade["data"] = pd.to_datetime(publicidade["data"])

    pedidos = pedidos[
        (pedidos["status"] == "Concluído")
        & (pedidos["data"].dt.date >= data_inicio)
        & (pedidos["data"].dt.date <= data_fim)
    ].copy()

    publicidade = publicidade[
        (publicidade["data"].dt.date >= data_inicio)
        & (publicidade["data"].dt.date <= data_fim)
    ].copy()

    pedidos = pedidos.merge(
        produtos[["sku", "custo_unitario"]],
        on="sku",
        how="left"
    )
    pedidos["custo_produtos"] = (
        pedidos["quantidade"] * pedidos["custo_unitario"]
    )
    canais_produto = pedidos.groupby("sku")["marketplace"].agg(
        lambda canais: (
            "Ambos"
            if canais.nunique() > 1
            else str(canais.iloc[0])
        )
    ).rename("canal")

    desempenho = pedidos.groupby(
        ["sku", "produto"],
        as_index=False
    ).agg(
        pedidos=("id_pedido", "count"),
        unidades=("quantidade", "sum"),
        faturamento=("faturamento_bruto", "sum"),
        custo_produtos=("custo_produtos", "sum"),
        taxas=("taxa_marketplace", "sum"),
        frete=("frete_vendedor", "sum"),
        descontos=("desconto", "sum"),
    )

    publicidade_produto = publicidade.groupby(
        "sku",
        as_index=False
    ).agg(
        publicidade=("investimento", "sum"),
        receita_atribuida=("receita_atribuida", "sum")
    )

    desempenho = produtos[["sku", "produto"]].merge(
        desempenho,
        on=["sku", "produto"],
        how="left"
    ).merge(
        publicidade_produto,
        on="sku",
        how="left"
    )

    valores_zero = [
        "pedidos",
        "unidades",
        "faturamento",
        "descontos",
        "custo_produtos",
        "taxas",
        "frete",
        "publicidade",
        "receita_atribuida"
    ]
    desempenho[valores_zero] = desempenho[valores_zero].fillna(0)

    desempenho["resultado"] = (
        desempenho["faturamento"]
        - desempenho["descontos"]
        - desempenho["custo_produtos"]
        - desempenho["taxas"]
        - desempenho["frete"]
        - desempenho["publicidade"]
    )
    desempenho["margem"] = (
        desempenho["resultado"]
        .div(
            (desempenho["faturamento"] - desempenho["descontos"]).where(
                (desempenho["faturamento"] - desempenho["descontos"]).ne(0)
            )
        )
        .mul(100)
        .fillna(0)
        .astype(float)
    )
    desempenho["roas"] = (
        desempenho["receita_atribuida"]
        .div(desempenho["publicidade"].where(desempenho["publicidade"].ne(0)))
        .fillna(0)
        .astype(float)
    )
    desempenho = desempenho.merge(
        produtos[
            ["sku", "categoria", "preco_venda", "custo_unitario"]
        ],
        on="sku",
        how="left"
    ).merge(
        canais_produto,
        on="sku",
        how="left"
    )
    desempenho["canal"] = desempenho["canal"].fillna("Sem vendas")

    desempenho = desempenho.sort_values(
        "faturamento",
        ascending=False
    ).reset_index(drop=True)

    desempenho["participacao_faturamento"] = (
        desempenho["faturamento"]
        .div(desempenho["faturamento"].sum())
        .mul(100)
        .fillna(0)
    )

    return desempenho


def classificar_produtos(
    desempenho: pd.DataFrame,
    estoque: pd.DataFrame
) -> pd.DataFrame:
    """Adiciona contexto de estoque e uma classificação acionável."""

    colunas_estoque = [
        "sku",
        "estoque_atual",
        "media_vendas_dia",
        "dias_estoque"
    ]
    resultado = desempenho.merge(
        estoque[colunas_estoque],
        on="sku",
        how="left"
    )

    def classificar(linha: pd.Series) -> str:
        if linha["estoque_atual"] <= 0 and linha["unidades"] > 0:
            return "Risco operacional"
        if linha["dias_estoque"] <= 7 and linha["unidades"] > 0:
            return "Reposição urgente"
        if (
            linha["faturamento"] >= desempenho["faturamento"].median()
            and linha["margem"] >= 20
        ):
            return "Alta performance"
        if linha["margem"] >= 30:
            return "Alta margem"
        if linha["unidades"] == 0 or linha["dias_estoque"] > 30:
            return "Baixo giro"
        if linha["margem"] < 15:
            return "Atenção"
        return "Normal"

    resultado["classificacao"] = resultado.apply(
        classificar,
        axis=1
    )

    return resultado


def obter_oportunidades(
    data_inicio: date,
    data_fim: date,
    produto: str | None = None,
    marketplace: str | None = None
) -> pd.DataFrame:
    """Gera oportunidades priorizadas a partir de vendas e estoque."""

    desempenho = obter_desempenho_produtos(
        data_inicio,
        data_fim,
        produto,
        marketplace
    )
    estoque = obter_analise_estoque(
        data_inicio,
        data_fim,
        produto,
        marketplace
    )
    resultado = classificar_produtos(desempenho, estoque)
    if resultado.empty:
        resultado["prioridade"] = pd.Series(dtype="int64")
        resultado["acao_sugerida"] = pd.Series(dtype="string")
        return resultado

    def definir_prioridade(linha: pd.Series) -> int:
        prioridades = {
            "Risco operacional": 1,
            "Reposição urgente": 2,
            "Alta performance": 3,
            "Atenção": 4,
            "Baixo giro": 5,
            "Alta margem": 6,
            "Normal": 7
        }
        return prioridades[linha["classificacao"]]

    resultado["prioridade"] = resultado.apply(
        definir_prioridade,
        axis=1
    )
    resultado["acao_sugerida"] = resultado["classificacao"].map(
        {
            "Risco operacional": "Priorizar reposição",
            "Reposição urgente": "Planejar reposição",
            "Alta performance": "Avaliar aumento de estoque",
            "Atenção": "Investigar margem",
            "Baixo giro": "Avaliar promoção",
            "Alta margem": "Avaliar escala de vendas",
            "Normal": "Monitorar"
        }
    )

    return resultado.sort_values(
        ["prioridade", "faturamento"],
        ascending=[True, False]
    ).reset_index(drop=True)


def obter_analise_estoque(
    data_inicio: date,
    data_fim: date,
    produto: str | None = None,
    marketplace: str | None = None
) -> pd.DataFrame:
    """Calcula estoque e cobertura considerando o período selecionado."""

    produtos = ler_dataset("dados/produtos.csv")
    pedidos = ler_dataset("dados/pedidos.csv")
    caminho_estoque = Path("dados/estoque.csv")
    estoque_importado = None
    if is_database_mode() or caminho_estoque.exists():
        estoque_importado = ler_dataset(caminho_estoque)
        colunas_necessarias = {"marketplace", "sku", "estoque_atual"}
        if not colunas_necessarias.issubset(estoque_importado.columns):
            faltantes = sorted(colunas_necessarias - set(estoque_importado.columns))
            raise ValueError(
                "O arquivo dados/estoque.csv não contém as colunas "
                f"necessárias: {', '.join(faltantes)}."
            )
        estoque_importado["estoque_atual"] = pd.to_numeric(
            estoque_importado["estoque_atual"],
            errors="coerce",
        )
        if estoque_importado["estoque_atual"].isna().any():
            raise ValueError(
                "O arquivo dados/estoque.csv contém quantidades inválidas."
            )
        if marketplace is not None:
            estoque_importado = estoque_importado[
                estoque_importado["marketplace"] == marketplace
            ]
        else:
            estoque_importado = estoque_importado.groupby(
                "sku",
                as_index=False,
            ).agg(estoque_atual=("estoque_atual", "sum"))

    if produto is not None:
        produtos = produtos[produtos["produto"] == produto].copy()
        pedidos = pedidos[pedidos["sku"].isin(produtos["sku"])]
        if estoque_importado is not None:
            estoque_importado = estoque_importado[
                estoque_importado["sku"].isin(produtos["sku"])
            ]
    pedidos["data"] = pd.to_datetime(pedidos["data"])

    pedidos_validos = pedidos[
        pedidos["status"] == "Concluído"
    ].copy()
    if marketplace is not None:
        pedidos_validos = pedidos_validos[
            pedidos_validos["marketplace"] == marketplace
        ]

    vendas_ate_fim = pedidos_validos[
        pedidos_validos["data"].dt.date <= data_fim
    ].groupby("sku", as_index=False).agg(
        unidades_vendidas=("quantidade", "sum")
    )

    vendas_periodo = pedidos_validos[
        (pedidos_validos["data"].dt.date >= data_inicio)
        & (pedidos_validos["data"].dt.date <= data_fim)
        & (
            pedidos_validos["marketplace"] == marketplace
            if marketplace is not None
            else True
        )
    ].groupby("sku", as_index=False).agg(
        unidades_periodo=("quantidade", "sum")
    )

    estoque = produtos.merge(
        vendas_ate_fim,
        on="sku",
        how="left"
    ).merge(
        vendas_periodo,
        on="sku",
        how="left"
    )

    estoque[["unidades_vendidas", "unidades_periodo"]] = (
        estoque[["unidades_vendidas", "unidades_periodo"]].fillna(0)
    )
    estoque["estoque_calculado"] = (
        estoque["estoque_inicial"] - estoque["unidades_vendidas"]
    ).clip(lower=0)
    if estoque_importado is not None:
        estoque = estoque.merge(
            estoque_importado[["sku", "estoque_atual"]].rename(
                columns={"estoque_atual": "estoque_importado"}
            ),
            on="sku",
            how="left",
        )
        estoque["estoque_atual"] = estoque["estoque_importado"].combine_first(
            estoque["estoque_calculado"]
        )
        estoque = estoque.drop(columns="estoque_importado")
    else:
        estoque["estoque_atual"] = estoque["estoque_calculado"]
    estoque = estoque.drop(columns="estoque_calculado")

    dias_periodo = max((data_fim - data_inicio).days + 1, 1)
    estoque["media_vendas_dia"] = (
        estoque["unidades_periodo"] / dias_periodo
    )
    estoque["estoque_minimo"] = (
        estoque["media_vendas_dia"] * 7
    )
    estoque["ponto_reposicao"] = (
        estoque["media_vendas_dia"] * 5
    )
    estoque["valor_estoque"] = (
        estoque["estoque_atual"] * estoque["custo_unitario"]
    )
    estoque["dias_estoque"] = (
        estoque["estoque_atual"] / estoque["media_vendas_dia"]
    )
    estoque.loc[
        estoque["media_vendas_dia"] == 0,
        "dias_estoque"
    ] = float("inf")
    estoque["dias_sem_estoque_estimados"] = (
        dias_periodo
        - estoque["estoque_inicial"]
        .div(estoque["media_vendas_dia"].replace(0, pd.NA))
    ).clip(lower=0).fillna(0)
    estoque.loc[
        estoque["dias_sem_estoque_estimados"] < 1e-9,
        "dias_sem_estoque_estimados"
    ] = 0
    estoque["vendas_potenciais_perdidas"] = (
        estoque["media_vendas_dia"]
        * estoque["dias_sem_estoque_estimados"]
    )
    estoque["receita_potencial_perdida"] = (
        estoque["vendas_potenciais_perdidas"]
        * estoque["preco_venda"]
    )

    def classificar_estoque(dias: float) -> str:
        if dias == 0:
            return "Sem estoque"
        if dias == float("inf"):
            return "Sem vendas"
        if dias < 7:
            return "Crítico"
        if dias <= 15:
            return "Atenção"
        return "Normal"

    estoque["status_estoque"] = estoque["dias_estoque"].apply(
        classificar_estoque
    )

    return estoque.sort_values(
        "dias_estoque",
        ascending=True
    ).reset_index(drop=True)
