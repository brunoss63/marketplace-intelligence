import pandas as pd


# =========================================================
# CARREGAR DADOS
# =========================================================

pedidos = pd.read_csv(
    "dados/pedidos.csv"
)

produtos = pd.read_csv(
    "dados/produtos.csv"
)

publicidade = pd.read_csv(
    "dados/publicidade.csv"
)


# =========================================================
# FILTRAR PEDIDOS CONCLUÍDOS
# =========================================================

pedidos = pedidos[
    pedidos["status"] == "Concluído"
].copy()


# =========================================================
# TRAZER CUSTO DO PRODUTO PARA CADA PEDIDO
# =========================================================

pedidos = pedidos.merge(
    produtos[
        [
            "sku",
            "custo_unitario"
        ]
    ],
    on="sku",
    how="left"
)


# =========================================================
# CALCULAR CUSTO TOTAL DOS PRODUTOS
# =========================================================

pedidos["custo_total"] = (
    pedidos["quantidade"]
    *
    pedidos["custo_unitario"]
)


# =========================================================
# INDICADORES
# =========================================================

total_pedidos = len(pedidos)

unidades = (
    pedidos["quantidade"]
    .sum()
)

faturamento = (
    pedidos["faturamento_bruto"]
    .sum()
)

ticket_medio = (
    faturamento / total_pedidos
)

custos = (
    pedidos["custo_total"]
    .sum()
)

taxas = (
    pedidos["taxa_marketplace"]
    .sum()
)

frete = (
    pedidos["frete_vendedor"]
    .sum()
)

investimento_publicidade = (
    publicidade["investimento"]
    .sum()
)


resultado = (
    faturamento
    -
    custos
    -
    taxas
    -
    frete
    -
    investimento_publicidade
)


margem = (
    resultado / faturamento
) * 100


receita_publicidade = (
    publicidade["receita_atribuida"]
    .sum()
)


roas = (
    receita_publicidade
    /
    investimento_publicidade
)


# =========================================================
# CRIAR ARQUIVO FINAL
# =========================================================

indicadores = pd.DataFrame(
    {
        "pedidos": [total_pedidos],
        "unidades": [unidades],
        "faturamento": [faturamento],
        "ticket_medio": [ticket_medio],
        "resultado": [resultado],
        "margem": [margem],
        "roas": [roas]
    }
)


indicadores.to_csv(
    "dados/indicadores.csv",
    index=False,
    encoding="utf-8-sig"
)


print("Arquivo criado:")
print("dados/indicadores.csv")

print()

print(indicadores)