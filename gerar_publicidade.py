import pandas as pd
import random
from datetime import date, timedelta


# =========================
# 1. CONFIGURAÇÕES
# =========================

random.seed(42)

NUMERO_DE_DIAS = 30

data_inicial = date(2026, 9, 1)


# =========================
# 2. PRODUTOS ANUNCIADOS
# =========================

campanhas = [
    {
        "sku": "SKU001",
        "campanha": "Kit Relação",
        "investimento_medio": 28,
        "roas_medio": 7.6
    },
    {
        "sku": "SKU002",
        "campanha": "Pastilhas",
        "investimento_medio": 22,
        "roas_medio": 6.5
    },
    {
        "sku": "SKU003",
        "campanha": "Acessórios",
        "investimento_medio": 38,
        "roas_medio": 5.0
    },
    {
        "sku": "SKU004",
        "campanha": "Acessórios",
        "investimento_medio": 35,
        "roas_medio": 4.7
    },
    {
        "sku": "SKU005",
        "campanha": "Acessórios",
        "investimento_medio": 20,
        "roas_medio": 4.2
    },
    {
        "sku": "SKU006",
        "campanha": "Acessórios",
        "investimento_medio": 30,
        "roas_medio": 4.8
    },
    {
        "sku": "SKU012",
        "campanha": "Outros",
        "investimento_medio": 22,
        "roas_medio": 4.4
    },
    {
        "sku": "SKU017",
        "campanha": "Outros",
        "investimento_medio": 18,
        "roas_medio": 4.6
    }
]


# =========================
# 3. GERAR PUBLICIDADE
# =========================

publicidade = []


for dia in range(NUMERO_DE_DIAS):

    data_atual = data_inicial + timedelta(days=dia)

    for campanha in campanhas:

        # Nem todas as campanhas rodam todos os dias
        if random.random() > 0.72:
            continue

        investimento = random.gauss(
            campanha["investimento_medio"],
            campanha["investimento_medio"] * 0.18
        )

        investimento = max(
            5,
            investimento
        )

        # Simulamos uma queda de eficiência
        # nas campanhas de Acessórios no final do período

        roas = campanha["roas_medio"]

        if (
            campanha["campanha"] == "Acessórios"
            and dia >= 20
        ):
            roas *= 0.78

        roas_real = max(
            1.8,
            random.gauss(roas, 0.45)
        )

        receita_atribuida = (
            investimento * roas_real
        )

        marketplace = random.choices(
            ["Mercado Livre", "Shopee"],
            weights=[74, 26]
        )[0]

        publicidade.append([
            data_atual,
            marketplace,
            campanha["sku"],
            campanha["campanha"],
            round(investimento, 2),
            round(receita_atribuida, 2)
        ])


# =========================
# 4. CRIAR DATAFRAME
# =========================

colunas = [
    "data",
    "marketplace",
    "sku",
    "campanha",
    "investimento",
    "receita_atribuida"
]

publicidade_df = pd.DataFrame(
    publicidade,
    columns=colunas
)


# =========================
# 5. SALVAR CSV
# =========================

publicidade_df.to_csv(
    "dados/publicidade.csv",
    index=False,
    encoding="utf-8-sig"
)


# =========================
# 6. RESUMO
# =========================

investimento_total = publicidade_df[
    "investimento"
].sum()

receita_total = publicidade_df[
    "receita_atribuida"
].sum()

roas_total = receita_total / investimento_total


print()
print("Publicidade criada com sucesso!")
print()

print(
    f"Investimento total: "
    f"R$ {investimento_total:,.2f}"
)

print(
    f"Receita atribuída: "
    f"R$ {receita_total:,.2f}"
)

print(
    f"ROAS: "
    f"{roas_total:.2f}"
)