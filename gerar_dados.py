import pandas as pd


# =========================
# 1. PRODUTOS FICTÍCIOS
# =========================

produtos = [
    ["SKU001", "Kit Relação X", "Transmissão", 105, 180, 95],
    ["SKU002", "Pastilha Freio Y", "Freios", 42, 120, 140],
    ["SKU003", "Manete Esportivo Z", "Controles", 28, 120, 90],
    ["SKU004", "Protetor Motor A", "Proteção", 78, 160, 70],
    ["SKU005", "Retrovisor B", "Acessórios", 62, 120, 85],
    ["SKU006", "Suporte Celular C", "Acessórios", 25, 79, 120],
    ["SKU007", "Capa Banco D", "Conforto", 38, 89, 100],
    ["SKU008", "Luva Motociclista E", "Equipamentos", 55, 119, 80],
    ["SKU009", "Cavalete Central F", "Manutenção", 92, 179, 45],
    ["SKU010", "Filtro de Ar G", "Manutenção", 24, 69, 130],
    ["SKU011", "Vela Ignição H", "Manutenção", 18, 49, 150],
    ["SKU012", "Bauleto 28L I", "Bagagem", 145, 289, 35],
    ["SKU013", "Antena Corta Pipa J", "Segurança", 14, 39, 180],
    ["SKU014", "Protetor Mão K", "Proteção", 48, 99, 75],
    ["SKU015", "Slider Motor L", "Proteção", 67, 139, 60],
    ["SKU016", "Cinta Capacete M", "Equipamentos", 19, 49, 110],
    ["SKU017", "Carregador USB N", "Eletrônicos", 31, 79, 95],
    ["SKU018", "Capa Chuva O", "Equipamentos", 45, 99, 65],
    ["SKU019", "Corrente Segurança P", "Segurança", 52, 119, 55],
    ["SKU020", "Kit Limpeza Q", "Cuidados", 22, 59, 125],
]


# =========================
# 2. NOME DAS COLUNAS
# =========================

colunas = [
    "sku",
    "produto",
    "categoria",
    "custo_unitario",
    "preco_venda",
    "estoque_inicial"
]


# =========================
# 3. CRIAR DATAFRAME
# =========================

df = pd.DataFrame(produtos, columns=colunas)


# =========================
# 4. SALVAR CSV
# =========================

df.to_csv(
    "dados/produtos.csv",
    index=False,
    encoding="utf-8-sig"
)


# =========================
# 5. MOSTRAR RESULTADO
# =========================

print("Produtos criados com sucesso!")
print()
print(df)