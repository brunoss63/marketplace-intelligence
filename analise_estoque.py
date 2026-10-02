import pandas as pd

# =========================================================
# 1. CARREGAR OS DADOS
# =========================================================

produtos = pd.read_csv("dados/produtos.csv")
pedidos = pd.read_csv("dados/pedidos.csv")

print("Dados carregados com sucesso!")

# =========================================================
# 2. CONSIDERAR APENAS PEDIDOS CONCLUÍDOS
# =========================================================

pedidos = pedidos[
    pedidos["status"] == "Concluído"
].copy()

# =========================================================
# 3. AGRUPAR VENDAS POR PRODUTO
# =========================================================

vendas = pedidos.groupby(
    "sku",
    as_index=False
).agg(
    unidades_vendidas=("quantidade", "sum")
)

# =========================================================
# 4. JUNTAR COM OS PRODUTOS
# =========================================================

estoque = produtos.merge(
    vendas,
    on="sku",
    how="left"
)

# Produtos sem venda recebem zero
estoque["unidades_vendidas"] = (
    estoque["unidades_vendidas"]
    .fillna(0)
)

# =========================================================
# 5. CALCULAR ESTOQUE ATUAL ESTIMADO
# =========================================================

estoque["estoque_atual"] = (
    estoque["estoque_inicial"]
    - estoque["unidades_vendidas"]
)

# Evita estoque negativo
estoque["estoque_atual"] = (
    estoque["estoque_atual"]
    .clip(lower=0)
)

# =========================================================
# 6. CALCULAR MÉDIA DE VENDAS POR DIA
# =========================================================

NUMERO_DE_DIAS = 30

estoque["media_vendas_dia"] = (
    estoque["unidades_vendidas"]
    /
    NUMERO_DE_DIAS
)

# =========================================================
# 7. CALCULAR DIAS DE ESTOQUE
# =========================================================

estoque["dias_estoque"] = (
    estoque["estoque_atual"]
    /
    estoque["media_vendas_dia"]
)

# Produtos sem venda ficam sem previsão
estoque.loc[
    estoque["media_vendas_dia"] == 0,
    "dias_estoque"
] = float("inf")

# =========================================================
# 8. CLASSIFICAR ESTOQUE
# =========================================================

def classificar_estoque(dias):

    if dias == float("inf"):
        return "Sem vendas"

    if dias < 7:
        return "Crítico"

    if dias <= 15:
        return "Atenção"

    return "Normal"


estoque["status_estoque"] = (
    estoque["dias_estoque"]
    .apply(classificar_estoque)
)

# =========================================================
# 9. ORDENAR PELOS PRODUTOS COM MENOS ESTOQUE
# =========================================================

estoque = estoque.sort_values(
    "dias_estoque",
    ascending=True
)

# =========================================================
# 10. SALVAR RESULTADO
# =========================================================

estoque.to_csv(
    "dados/analise_estoque.csv",
    index=False,
    encoding="utf-8-sig"
)

# =========================================================
# 11. MOSTRAR RESULTADOS
# =========================================================

print()
print("=" * 100)
print("ANÁLISE DE ESTOQUE")
print("=" * 100)

print(
    estoque[
        [
            "produto",
            "estoque_inicial",
            "unidades_vendidas",
            "estoque_atual",
            "media_vendas_dia",
            "dias_estoque",
            "status_estoque"
        ]
    ].to_string(index=False)
)

print()
print("Resumo dos alertas:")

print(
    estoque["status_estoque"]
    .value_counts()
)

print()
print("Arquivo criado:")
print("dados/analise_estoque.csv")

print("=" * 100)