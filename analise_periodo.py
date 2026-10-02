import pandas as pd

# =========================================================
# 1. CARREGAR OS DADOS
# =========================================================

pedidos = pd.read_csv("dados/pedidos.csv")

print("Dados carregados com sucesso!")

# =========================================================
# 2. CONSIDERAR APENAS PEDIDOS CONCLUÍDOS
# =========================================================

pedidos = pedidos[
    pedidos["status"] == "Concluído"
].copy()

# =========================================================
# 3. GARANTIR QUE A DATA SEJA RECONHECIDA COMO DATA
# =========================================================

pedidos["data"] = pd.to_datetime(
    pedidos["data"]
)

# =========================================================
# 4. AGRUPAR OS INDICADORES POR DIA
# =========================================================

periodo = pedidos.groupby(
    "data",
    as_index=False
).agg(
    pedidos=("id_pedido", "count"),
    unidades=("quantidade", "sum"),
    faturamento=("faturamento_bruto", "sum"),
    taxas=("taxa_marketplace", "sum"),
    frete=("frete_vendedor", "sum")
)

# =========================================================
# 5. CALCULAR TICKET MÉDIO
# =========================================================

periodo["ticket_medio"] = (
    periodo["faturamento"]
    /
    periodo["pedidos"]
)

# =========================================================
# 6. SALVAR RESULTADO
# =========================================================

periodo.to_csv(
    "dados/analise_periodo.csv",
    index=False,
    encoding="utf-8-sig"
)

# =========================================================
# 7. MOSTRAR RESULTADOS
# =========================================================

print()
print("=" * 100)
print("EVOLUÇÃO DIÁRIA")
print("=" * 100)

print(
    periodo.to_string(index=False)
)

print()
print("Arquivo criado:")
print("dados/analise_periodo.csv")

print("=" * 100)