
from componentes import animar_pagina, cabecalho_pagina
from integracao_mercadolivre import mostrar_conexao_mercadolivre
from secoes.marketplace import mostrar_marketplace


# =========================================================
# ANIMAÇÃO DA PÁGINA
# =========================================================

animar_pagina("marketplaces")


# =========================================================
# MARKETPLACES
# =========================================================

cabecalho_pagina(
    "Marketplaces",
    "Desempenho e rentabilidade por canal de venda.",
    "▥"
)

mostrar_conexao_mercadolivre()

mostrar_marketplace()