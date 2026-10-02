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

pedidos_concluidos = pedidos[
    pedidos["status"] == "Concluído"
].copy()


# =========================================================
# 3. ADICIONAR O CUSTO DO PRODUTO
# =========================================================

pedidos_concluidos = pedidos_concluidos.merge(
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

pedidos_concluidos["custo_produto"] = (
    pedidos_concluidos["quantidade"]
    *
    pedidos_concluidos["custo_unitario"]
)


# =========================================================
# 5. INDICADORES GERAIS
# =========================================================

numero_pedidos = len(
    pedidos_concluidos
)

unidades_vendidas = pedidos_concluidos[
    "quantidade"
].sum()

faturamento = pedidos_concluidos[
    "faturamento_bruto"
].sum()

custo_produtos = pedidos_concluidos[
    "custo_produto"
].sum()

taxas = pedidos_concluidos[
    "taxa_marketplace"
].sum()

frete = pedidos_concluidos[
    "frete_vendedor"
].sum()

publicidade_total = publicidade[
    "investimento"
].sum()


# =========================================================
# 6. TICKET MÉDIO
# =========================================================

ticket_medio = (
    faturamento / numero_pedidos
)


# =========================================================
# 7. RESULTADO ESTIMADO
# =========================================================

resultado = (
    faturamento
    - custo_produtos
    - taxas
    - frete
    - publicidade_total
)


# =========================================================
# 8. MARGEM
# =========================================================

margem = (
    resultado / faturamento
) * 100


# =========================================================
# 9. ROAS
# =========================================================

receita_atribuida = publicidade[
    "receita_atribuida"
].sum()

roas = (
    receita_atribuida
    / publicidade_total
)


# =========================================================
# 10. MOSTRAR RESULTADOS
# =========================================================

print()
print("=" * 50)
print("INDICADORES GERAIS")
print("=" * 50)

print(
    f"Pedidos concluídos: {numero_pedidos}"
)

print(
    f"Unidades vendidas: {unidades_vendidas}"
)

print(
    f"Faturamento: R$ {faturamento:,.2f}"
)

print(
    f"Ticket médio: R$ {ticket_medio:,.2f}"
)

print()

print(
    f"Custo dos produtos: R$ {custo_produtos:,.2f}"
)

print(
    f"Taxas marketplace: R$ {taxas:,.2f}"
)

print(
    f"Frete vendedor: R$ {frete:,.2f}"
)

print(
    f"Publicidade: R$ {publicidade_total:,.2f}"
)

print()

print(
    f"Resultado estimado: R$ {resultado:,.2f}"
)

print(
    f"Margem estimada: {margem:.2f}%"
)

print()

print(
    f"Receita atribuída à publicidade: "
    f"R$ {receita_atribuida:,.2f}"
)

print(
    f"ROAS: {roas:.2f}"
)

print("=" * 50)