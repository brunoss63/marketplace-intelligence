import pandas as pd

# =========================================================
# 1. CARREGAR OS DADOS
# =========================================================

produtos = pd.read_csv("dados/produtos.csv")
pedidos = pd.read_csv("dados/pedidos.csv")
publicidade = pd.read_csv("dados/publicidade.csv")

print("Dados carregados com sucesso!")

# =========================================================
# 2. CONSIDERAR APENAS PEDIDOS CONCLUÍDOS
# =========================================================

pedidos = pedidos[
    pedidos["status"] == "Concluído"
].copy()

# =========================================================
# 3. ADICIONAR CUSTO DO PRODUTO
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
# 4. CALCULAR CUSTO DOS PRODUTOS
# =========================================================

pedidos["custo_produto"] = (
    pedidos["quantidade"]
    *
    pedidos["custo_unitario"]
)

# =========================================================
# 5. AGRUPAR VENDAS POR PRODUTO
# =========================================================

desempenho = pedidos.groupby(
    ["sku", "produto"],
    as_index=False
).agg(
    pedidos=("id_pedido", "count"),
    unidades=("quantidade", "sum"),
    faturamento=("faturamento_bruto", "sum"),
    custo_produtos=("custo_produto", "sum"),
    taxas=("taxa_marketplace", "sum"),
    frete=("frete_vendedor", "sum")
)

# =========================================================
# 6. AGRUPAR PUBLICIDADE POR PRODUTO
# =========================================================

publicidade_produto = publicidade.groupby(
    "sku",
    as_index=False
).agg(
    publicidade=("investimento", "sum"),
    receita_atribuida=("receita_atribuida", "sum")
)

# =========================================================
# 7. JUNTAR PUBLICIDADE COM VENDAS
# =========================================================

desempenho = desempenho.merge(
    publicidade_produto,
    on="sku",
    how="left"
)

# Produtos sem publicidade recebem zero
desempenho["publicidade"] = (
    desempenho["publicidade"]
    .fillna(0)
)

desempenho["receita_atribuida"] = (
    desempenho["receita_atribuida"]
    .fillna(0)
)

# =========================================================
# 8. CALCULAR RESULTADO ESTIMADO
# =========================================================

desempenho["resultado"] = (
    desempenho["faturamento"]
    - desempenho["custo_produtos"]
    - desempenho["taxas"]
    - desempenho["frete"]
    - desempenho["publicidade"]
)

# =========================================================
# 9. CALCULAR MARGEM
# =========================================================

desempenho["margem"] = (
    desempenho["resultado"]
    /
    desempenho["faturamento"]
) * 100

# =========================================================
# 10. CALCULAR ROAS
# =========================================================

desempenho["roas"] = (
    desempenho["receita_atribuida"]
    /
    desempenho["publicidade"]
)

desempenho["roas"] = (
    desempenho["roas"]
    .replace([float("inf"), -float("inf")], 0)
    .fillna(0)
)

# =========================================================
# 11. ORDENAR PELO FATURAMENTO
# =========================================================

desempenho = desempenho.sort_values(
    "faturamento",
    ascending=False
)

# =========================================================
# 12. SALVAR RESULTADO
# =========================================================

desempenho.to_csv(
    "dados/desempenho_produtos.csv",
    index=False,
    encoding="utf-8-sig"
)

# =========================================================
# 13. MOSTRAR RESULTADOS
# =========================================================

print()
print("=" * 80)
print("DESEMPENHO DOS PRODUTOS")
print("=" * 80)

print(
    desempenho[
        [
            "produto",
            "pedidos",
            "unidades",
            "faturamento",
            "resultado",
            "margem",
            "roas"
        ]
    ].to_string(index=False)
)

print()
print("Arquivo criado:")
print("dados/desempenho_produtos.csv")

print("=" * 80)