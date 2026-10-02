import pandas as pd

# =========================================================
# 1. CARREGAR OS DADOS
# =========================================================

produtos = pd.read_csv("dados/produtos.csv")
pedidos = pd.read_csv("dados/pedidos.csv")
publicidade = pd.read_csv("dados/publicidade.csv")

print("Dados carregados com sucesso!")

# =========================================================
# 2. VALIDAR PEDIDOS
# =========================================================

pedidos_concluidos = pedidos[
    pedidos["status"] == "Concluído"
].copy()

print()
print("=" * 70)
print("VALIDAÇÃO DOS PEDIDOS")
print("=" * 70)

print(f"Total de pedidos: {len(pedidos)}")
print(f"Pedidos concluídos: {len(pedidos_concluidos)}")
print(
    f"Pedidos cancelados/devolvidos: "
    f"{len(pedidos) - len(pedidos_concluidos)}"
)

# =========================================================
# 3. VALIDAR ESTOQUE
# =========================================================

vendas = pedidos_concluidos.groupby(
    "sku"
)["quantidade"].sum()

estoque_validacao = produtos[
    ["sku", "produto", "estoque_inicial"]
].copy()

estoque_validacao["unidades_vendidas"] = (
    estoque_validacao["sku"]
    .map(vendas)
    .fillna(0)
)

estoque_validacao["estoque_atual"] = (
    estoque_validacao["estoque_inicial"]
    -
    estoque_validacao["unidades_vendidas"]
)

print()
print("=" * 70)
print("VALIDAÇÃO DO ESTOQUE")
print("=" * 70)

print(
    estoque_validacao[
        [
            "produto",
            "estoque_inicial",
            "unidades_vendidas",
            "estoque_atual"
        ]
    ].to_string(index=False)
)

# =========================================================
# 4. VERIFICAR ESTOQUE NEGATIVO
# =========================================================

estoque_negativo = estoque_validacao[
    estoque_validacao["estoque_atual"] < 0
]

print()

if estoque_negativo.empty:
    print("OK: nenhum produto ficou com estoque negativo.")
else:
    print("ATENÇÃO: existem produtos com estoque negativo!")
    print(estoque_negativo)

# =========================================================
# 5. PRODUTOS ESGOTADOS
# =========================================================

esgotados = estoque_validacao[
    estoque_validacao["estoque_atual"] == 0
]

print()
print(f"Produtos esgotados: {len(esgotados)}")

if not esgotados.empty:
    print()
    print(esgotados["produto"].to_string(index=False))

# =========================================================
# 6. VALIDAR PUBLICIDADE
# =========================================================

print()
print("=" * 70)
print("VALIDAÇÃO DA PUBLICIDADE")
print("=" * 70)

print(
    f"Investimento: "
    f"R$ {publicidade['investimento'].sum():,.2f}"
)

print(
    f"Receita atribuída: "
    f"R$ {publicidade['receita_atribuida'].sum():,.2f}"
)

# =========================================================
# 7. RESULTADO FINAL DA VALIDAÇÃO
# =========================================================

print()
print("=" * 70)
print("VALIDAÇÃO FINAL")
print("=" * 70)

if estoque_negativo.empty:
    print("✓ Dados de estoque consistentes.")
else:
    print("✗ Existem inconsistências no estoque.")

print("✓ Pedidos analisados.")
print("✓ Publicidade analisada.")
print("✓ Arquivos principais carregados.")

print()
print("Validação concluída.")