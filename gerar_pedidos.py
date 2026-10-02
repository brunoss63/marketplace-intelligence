import pandas as pd
import random
from datetime import date, timedelta


# =========================
# 1. CONFIGURAÇÕES
# =========================

NUMERO_DE_DIAS = 30
PEDIDOS_POR_DIA = 40

# Para conseguirmos reproduzir exatamente
# os mesmos dados futuramente
random.seed(42)


# =========================
# 2. LER PRODUTOS
# =========================

produtos = pd.read_csv("dados/produtos.csv")

print("Produtos carregados:")
print(produtos)
print()


# =========================
# 3. PREPARAR ESTOQUE
# =========================

estoque = {}

for _, produto in produtos.iterrows():
    estoque[produto["sku"]] = produto["estoque_inicial"]


# =========================
# 4. GERAR PEDIDOS
# =========================

pedidos = []

numero_pedido = 1

data_inicial = date(2026, 9, 1)


for dia in range(NUMERO_DE_DIAS):

    data_atual = data_inicial + timedelta(days=dia)

    for _ in range(PEDIDOS_POR_DIA):

        # Produtos que ainda possuem estoque
        produtos_disponiveis = produtos[
            produtos["sku"].map(estoque) > 0
        ]

        if produtos_disponiveis.empty:
            break

        # Escolher produto aleatoriamente
        produto = produtos_disponiveis.sample(
            n=1,
            random_state=random.randint(1, 100000)
        ).iloc[0]

        sku = produto["sku"]

        # Quantidade comprada
        quantidade = random.choices(
            [1, 2],
            weights=[90, 10]
        )[0]

        # Não vender mais do que existe no estoque
        quantidade = min(
            quantidade,
            estoque[sku]
        )

        # Pequena variação no preço
        preco = round(
            produto["preco_venda"] *
            random.choice([0.97, 1.00, 1.00, 1.03]),
            2
        )

        faturamento = round(
            quantidade * preco,
            2
        )

        # Escolher marketplace
        marketplace = random.choices(
            ["Mercado Livre", "Shopee"],
            weights=[73, 27]
        )[0]

        # Taxas diferentes por marketplace
        if marketplace == "Mercado Livre":
            percentual_taxa = random.uniform(0.13, 0.17)
        else:
            percentual_taxa = random.uniform(0.10, 0.14)

        taxa_marketplace = round(
            faturamento * percentual_taxa,
            2
        )

        # Frete pago pelo vendedor em parte dos pedidos
        if random.random() < 0.70:
            frete_vendedor = round(
                random.uniform(8, 18),
                2
            )
        else:
            frete_vendedor = 0

        # Pequena quantidade de cancelamentos/devoluções
        sorteio_status = random.random()

        if sorteio_status < 0.025:
            status = random.choice([
                "Cancelado",
                "Devolvido"
            ])
        else:
            status = "Concluído"

        # Só baixamos o estoque quando o pedido foi concluído
        if status == "Concluído":
            estoque[sku] -= quantidade

        # Criar registro
        pedidos.append([
            f"PED{numero_pedido:05d}",
            data_atual,
            marketplace,
            sku,
            produto["produto"],
            quantidade,
            preco,
            faturamento,
            taxa_marketplace,
            frete_vendedor,
            status
        ])

        numero_pedido += 1


# =========================
# 5. CRIAR DATAFRAME
# =========================

colunas = [
    "id_pedido",
    "data",
    "marketplace",
    "sku",
    "produto",
    "quantidade",
    "preco_unitario",
    "faturamento_bruto",
    "taxa_marketplace",
    "frete_vendedor",
    "status"
]

pedidos_df = pd.DataFrame(
    pedidos,
    columns=colunas
)


# =========================
# 6. SALVAR CSV
# =========================

pedidos_df.to_csv(
    "dados/pedidos.csv",
    index=False,
    encoding="utf-8-sig"
)


# =========================
# 7. RESUMO
# =========================

print()
print("Pedidos criados com sucesso!")
print()

print(f"Total de pedidos: {len(pedidos_df)}")

print(
    f"Pedidos concluídos: "
    f"{len(pedidos_df[pedidos_df['status'] == 'Concluído'])}"
)

print(
    f"Pedidos cancelados/devolvidos: "
    f"{len(pedidos_df[pedidos_df['status'] != 'Concluído'])}"
)

print()

print("Pedidos por marketplace:")
print(
    pedidos_df["marketplace"]
    .value_counts()
)

print()

print("Faturamento bruto:")
print(
    pedidos_df[
        pedidos_df["status"] == "Concluído"
    ]["faturamento_bruto"].sum()
)