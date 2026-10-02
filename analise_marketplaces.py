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
# 5. AGRUPAR VENDAS POR MARKETPLACE
# =========================================================

desempenho = pedidos.groupby(
    "marketplace",
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
# 6. AGRUPAR PUBLICIDADE POR MARKETPLACE
# =========================================================

publicidade_marketplace = publicidade.groupby(
    "marketplace",
    as_index=False
).agg(
    publicidade=("investimento", "sum"),
    receita_atribuida=("receita_atribuida", "sum")
)

# =========================================================
# 7. JUNTAR PUBLICIDADE
# =========================================================

desempenho = desempenho.merge(
    publicidade_marketplace,
    on="marketplace",
    how="left"
)

desempenho["publicidade"] = (
    desempenho["publicidade"]
    .fillna(0)
)

desempenho["receita_atribuida"] = (
    desempenho["receita_atribuida"]
    .fillna(0)
)

# =========================================================
# 8. TICKET MÉDIO
# =========================================================

desempenho["ticket_medio"] = (
    desempenho["faturamento"]
    /
    desempenho["pedidos"]
)

# =========================================================
# 9. RESULTADO ESTIMADO
# =========================================================

desempenho["resultado"] = (
    desempenho["faturamento"]
    - desempenho["custo_produtos"]
    - desempenho["taxas"]
    - desempenho["frete"]
    - desempenho["publicidade"]
)

# =========================================================
# 10. MARGEM
# =========================================================

desempenho["margem"] = (
    desempenho["resultado"]
    /
    desempenho["faturamento"]
) * 100

# =========================================================
# 11. ROAS
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
# 12. ORDENAR PELO FATURAMENTO
# =========================================================

desempenho = desempenho.sort_values(
    "faturamento",
    ascending=False
)

# =========================================================
# 13. SALVAR RESULTADO
# =========================================================

desempenho.to_csv(
    "dados/desempenho_marketplaces.csv",
    index=False,
    encoding="utf-8-sig"
)

# =========================================================
# 14. MOSTRAR RESULTADOS
# =========================================================

print()
print("=" * 100)
print("DESEMPENHO POR MARKETPLACE")
print("=" * 100)

print(
    desempenho[
        [
            "marketplace",
            "pedidos",
            "unidades",
            "faturamento",
            "ticket_medio",
            "taxas",
            "frete",
            "publicidade",
            "resultado",
            "margem",
            "roas"
        ]
    ].to_string(index=False)
)

print()
print("Arquivo criado:")
print("dados/desempenho_marketplaces.csv")

print("=" * 100)