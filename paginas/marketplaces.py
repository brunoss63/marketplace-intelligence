
from componentes import animar_pagina, cabecalho_pagina
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


mostrar_marketplace()