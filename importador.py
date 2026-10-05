from io import BytesIO, StringIO
from pathlib import Path
import re
from typing import TypedDict
from zipfile import BadZipFile

import pandas as pd

from armazenamento import is_database_mode, salvar_importacao


class EsquemaImportacao(TypedDict):
    arquivo: str
    chave: list[str]
    campos: dict[str, tuple[str, bool, tuple[str, ...]]]


ESQUEMAS_IMPORTACAO: dict[str, EsquemaImportacao] = {
    "Pedidos": {
        "arquivo": "pedidos.csv",
        "chave": ["marketplace", "id_pedido", "sku", "produto"],
        "campos": {
            "id_pedido": ("ID do pedido", True, ("id_pedido", "id", "pedido", "order_id", "numero do pedido")),
            "data": ("Data do pedido", True, ("data", "date", "data do pedido", "order date")),
            "sku": ("SKU", False, ("sku", "seller_sku", "seller sku", "codigo sku")),
            "produto": ("Produto", False, ("produto", "product", "product name", "nome do produto", "titulo", "item")),
            "quantidade": ("Quantidade", True, ("quantidade", "quantity", "qty", "qtd", "unidades")),
            "preco_unitario": ("Preço unitário", False, ("preco unitario", "unit price", "preco")),
            "faturamento_bruto": ("Valor bruto da venda", True, ("faturamento_bruto", "valor bruto", "receita bruta", "valor total", "total", "amount", "sale amount")),
            "desconto": ("Desconto", False, ("desconto", "discount", "discount amount", "valor do desconto")),
            "taxa_marketplace": ("Taxa do marketplace", False, ("taxa_marketplace", "taxa", "taxas", "fee", "commission")),
            "frete_vendedor": ("Frete pago pelo vendedor", False, ("frete_vendedor", "frete", "shipping", "envio")),
            "status": ("Status do pedido", True, ("status", "situacao", "order status", "estado")),
        },
    },
    "Produtos": {
        "arquivo": "produtos.csv",
        "chave": ["marketplace", "sku"],
        "campos": {
            "sku": ("SKU", True, ("sku", "seller_sku", "seller sku", "codigo sku")),
            "produto": ("Nome do produto", True, ("produto", "product", "product name", "nome do produto", "titulo", "item", "nome")),
            "categoria": ("Categoria", False, ("categoria", "category", "tipo")),
            "custo_unitario": ("Custo unitário", False, ("custo unitario", "custo", "cost", "unit cost")),
            "preco_venda": ("Preço de venda", False, ("preco venda", "preco", "price", "sale price")),
            "estoque_inicial": ("Estoque cadastrado", False, ("estoque inicial", "estoque", "stock", "quantity")),
        },
    },
    "Estoque": {
        "arquivo": "estoque.csv",
        "chave": ["marketplace", "sku"],
        "campos": {
            "sku": ("SKU", True, ("sku", "seller_sku", "seller sku", "codigo sku")),
            "produto": ("Nome do produto", False, ("produto", "product", "product name", "nome do produto", "titulo", "item", "nome")),
            "estoque_atual": ("Quantidade disponível", True, ("estoque atual", "estoque", "stock", "available", "quantity", "qty")),
        },
    },
    "Publicidade": {
        "arquivo": "publicidade.csv",
        "chave": ["marketplace", "data", "sku", "campanha"],
        "campos": {
            "data": ("Data da campanha", True, ("data", "date", "campaign date")),
            "sku": ("SKU", True, ("sku", "seller_sku", "seller sku", "codigo sku")),
            "campanha": ("Nome da campanha", True, ("campanha", "campaign", "campaign name", "nome da campanha")),
            "investimento": ("Investimento", True, ("investimento", "spend", "cost", "ad spend")),
            "receita_atribuida": ("Receita atribuída", True, ("receita atribuida", "revenue", "sales", "attributed sales")),
        },
    },
}

COLUNAS_CANONICAS: dict[str, list[str]] = {
    "Pedidos": [
        "id_pedido", "data", "marketplace", "sku", "produto",
        "quantidade", "preco_unitario", "faturamento_bruto", "desconto",
        "taxa_marketplace", "frete_vendedor", "status",
    ],
    "Produtos": [
        "marketplace", "sku", "produto", "categoria", "custo_unitario",
        "preco_venda", "estoque_inicial",
    ],
    "Estoque": ["marketplace", "sku", "produto", "estoque_atual"],
    "Publicidade": [
        "data", "marketplace", "sku", "campanha",
        "investimento", "receita_atribuida",
    ],
}


def ler_arquivo_importado(
    conteudo: bytes,
    nome_arquivo: str,
    planilha: str | None = None,
) -> pd.DataFrame:
    """Lê arquivo CSV ou XLSX externo como texto, sem impor seus cabeçalhos."""

    if nome_arquivo.lower().endswith(".xlsx"):
        try:
            arquivo_excel = pd.ExcelFile(BytesIO(conteudo), engine="openpyxl")
            nome_planilha = planilha or arquivo_excel.sheet_names[0]
            dados = pd.read_excel(
                arquivo_excel,
                sheet_name=nome_planilha,
                dtype=str,
                keep_default_na=False,
            )
        except (BadZipFile, ImportError, ValueError, OSError) as erro:
            raise ValueError(
                "Não foi possível ler a planilha. Confirme que o arquivo "
                "é um XLSX válido e que a dependência openpyxl está instalada. "
                f"Detalhes: {erro}"
            ) from erro
        dados.columns = [str(coluna).strip() for coluna in dados.columns]
        return dados

    erros: list[str] = []
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            texto = conteudo.decode(encoding)
            dados = pd.read_csv(
                StringIO(texto),
                sep=None,
                engine="python",
                dtype=str,
                keep_default_na=False,
            )
            if dados.empty and len(dados.columns) == 0:
                raise ValueError("O arquivo não contém cabeçalhos ou linhas.")
            dados.columns = [str(coluna).strip() for coluna in dados.columns]
            return dados
        except (UnicodeDecodeError, pd.errors.ParserError, pd.errors.EmptyDataError) as erro:
            erros.append(f"{encoding}: {erro}")

    detalhes = "; ".join(erros)
    raise ValueError(
        "Não foi possível interpretar o CSV. Verifique o delimitador e "
        f"o conteúdo do arquivo. Detalhes: {detalhes}"
    )


def listar_planilhas_xlsx(conteudo: bytes) -> list[str]:
    try:
        planilhas = pd.ExcelFile(BytesIO(conteudo), engine="openpyxl").sheet_names
        if not planilhas:
            raise ValueError("O arquivo XLSX não contém planilhas.")
        return planilhas
    except (BadZipFile, ImportError, ValueError, OSError) as erro:
        raise ValueError(
            "Não foi possível abrir o arquivo XLSX. "
            f"Detalhes: {erro}"
        ) from erro


def sugerir_mapeamento(
    tipo_dado: str,
    colunas: list[str],
) -> dict[str, str | None]:
    """Sugere associações de colunas pelo nome normalizado."""

    campos = _esquema(tipo_dado)["campos"]
    nomes_normalizados = {
        coluna: _normalizar_nome_coluna(coluna)
        for coluna in colunas
    }
    sugestoes: dict[str, str | None] = {}
    for campo, (_, _, sinonimos) in campos.items():
        opcoes = {_normalizar_nome_coluna(nome) for nome in sinonimos}
        sugestoes[campo] = next(
            (
                coluna
                for coluna, normalizado in nomes_normalizados.items()
                if normalizado in opcoes
            ),
            None,
        )
    return sugestoes


def normalizar_importacao(
    dados: pd.DataFrame,
    tipo_dado: str,
    marketplace: str,
    mapeamento: dict[str, str | None],
) -> tuple[pd.DataFrame, pd.Series]:
    """Transforma um arquivo de origem no esquema canônico do tipo escolhido."""

    esquema = _esquema(tipo_dado)
    campos = esquema["campos"]
    obrigatorios = [
        rotulo
        for campo, (rotulo, requerido, _) in campos.items()
        if requerido and not mapeamento.get(campo)
    ]
    if obrigatorios:
        raise ValueError(
            "Mapeie os campos obrigatórios: " + ", ".join(obrigatorios) + "."
        )
    colunas_mapeadas = [
        coluna for coluna in mapeamento.values() if coluna is not None
    ]
    if len(colunas_mapeadas) != len(set(colunas_mapeadas)):
        raise ValueError(
            "Cada coluna de origem pode ser associada a apenas um campo "
            "interno. Revise o mapeamento."
        )
    if tipo_dado == "Pedidos" and not (
        mapeamento.get("sku") or mapeamento.get("produto")
    ):
        raise ValueError("Mapeie pelo menos um campo: SKU ou Produto.")

    normalizado = pd.DataFrame(index=dados.index)
    erros = pd.Series("", index=dados.index, dtype="string")
    campos_data = {"data"}
    campos_texto = {
        "id_pedido", "sku", "produto", "categoria", "status", "campanha",
    }
    for campo in COLUNAS_CANONICAS[tipo_dado]:
        if campo == "marketplace":
            normalizado[campo] = marketplace
            continue
        coluna = mapeamento.get(campo)
        if not coluna:
            normalizado[campo] = "" if campo in campos_texto | campos_data else 0.0
            continue

        origem = dados[coluna]
        if campo in campos_data:
            datas = _converter_datas(origem)
            normalizado[campo] = datas.dt.strftime("%Y-%m-%d").fillna("")
            _adicionar_erro(erros, datas.isna(), f"{campos[campo][0]} inválida")
        elif campo in campos_texto:
            normalizado[campo] = origem.astype("string").fillna("").str.strip()
        else:
            valores = origem.map(_numero)
            normalizado[campo] = valores
            preenchidos = origem.astype("string").str.strip().ne("")
            obrigatorio = bool(campos[campo][1])
            _adicionar_erro(
                erros,
                valores.isna() & (preenchidos | obrigatorio),
                f"{campos[campo][0]} inválido ou ausente",
            )

    for campo, (rotulo, requerido, _) in campos.items():
        if campo not in normalizado:
            continue
        if campo in campos_texto and requerido and campo != "status":
            _adicionar_erro(
                erros,
                normalizado[campo].astype("string").str.strip().eq(""),
                f"{rotulo} ausente",
            )

    if tipo_dado == "Pedidos":
        _adicionar_erro(
            erros,
            normalizado["sku"].eq("") & normalizado["produto"].eq(""),
            "SKU e Produto ausentes",
        )
        _adicionar_erro(
            erros,
            normalizado["quantidade"].notna()
            & (normalizado["quantidade"] <= 0),
            "Quantidade deve ser maior que zero",
        )
        _adicionar_erro(
            erros,
            normalizado["faturamento_bruto"].notna()
            & (normalizado["faturamento_bruto"] < 0),
            "Valor bruto inválido",
        )
        normalizado["status"] = normalizado["status"].map(_status_canonico)
        _adicionar_erro(
            erros,
            normalizado["status"].eq(""),
            "Status não reconhecido",
        )
        normalizado["preco_unitario"] = normalizado["preco_unitario"].fillna(0)
        normalizado["desconto"] = normalizado["desconto"].fillna(0)
        normalizado["taxa_marketplace"] = normalizado["taxa_marketplace"].fillna(0)
        normalizado["frete_vendedor"] = normalizado["frete_vendedor"].fillna(0)
        normalizado["quantidade"] = normalizado["quantidade"].fillna(0)
        _adicionar_erro(
            erros,
            normalizado["desconto"] < 0,
            "Desconto não pode ser negativo",
        )
    elif tipo_dado == "Produtos":
        for campo in ("custo_unitario", "preco_venda", "estoque_inicial"):
            valores = normalizado[campo]
            _adicionar_erro(
                erros,
                valores.notna() & (valores < 0),
                f"{campos[campo][0]} não pode ser negativo",
            )
            normalizado[campo] = valores.fillna(0)
        for campo in ("categoria",):
            normalizado[campo] = normalizado[campo].fillna("")
    elif tipo_dado == "Estoque":
        _adicionar_erro(
            erros,
            normalizado["estoque_atual"].notna()
            & (normalizado["estoque_atual"] < 0),
            "Quantidade disponível inválida",
        )
        normalizado["estoque_atual"] = normalizado["estoque_atual"].fillna(0)
        if "produto" in normalizado:
            normalizado["produto"] = normalizado["produto"].fillna("")
    elif tipo_dado == "Publicidade":
        for campo in ("investimento", "receita_atribuida"):
            valores = normalizado[campo]
            _adicionar_erro(
                erros,
                valores.notna() & (valores < 0),
                f"{campos[campo][0]} não pode ser negativo",
            )
            normalizado[campo] = valores.fillna(0)

    normalizado["marketplace"] = marketplace
    chaves = list(esquema["chave"])
    duplicadas = normalizado.duplicated(subset=chaves, keep=False)
    _adicionar_erro(erros, duplicadas, "Registro duplicado no arquivo")

    return normalizado[COLUNAS_CANONICAS[tipo_dado]], erros


def mesclar_importacao_dashboard(
    tipo_dado: str,
    registros_validos: pd.DataFrame,
) -> dict[str, int]:
    """Insere os registros válidos na tabela principal do dashboard."""

    if is_database_mode():
        return salvar_importacao(tipo_dado, registros_validos)

    esquema = _esquema(tipo_dado)
    colunas = COLUNAS_CANONICAS[tipo_dado]
    destino = Path(__file__).resolve().parent / "dados" / f"{tipo_dado.lower()}.csv"
    destino.parent.mkdir(parents=True, exist_ok=True)

    registros = registros_validos.copy()
    if registros.empty:
        return {"inseridos": 0, "atualizados": 0, "total": 0}

    for coluna in colunas:
        if coluna not in registros.columns:
            registros[coluna] = ""
    registros = registros[colunas].copy().fillna("")

    if destino.exists():
        existente = pd.read_csv(destino, dtype=str, keep_default_na=False)
        for coluna in colunas:
            if coluna not in existente.columns:
                existente[coluna] = ""
        existente = existente[colunas].copy().fillna("")
    else:
        existente = pd.DataFrame(columns=colunas)

    chave = esquema["chave"]
    chave_existente = existente[chave].astype(str).apply(
        lambda linha: tuple(str(valor).strip() for valor in linha),
        axis=1,
    )
    chave_nova = registros[chave].astype(str).apply(
        lambda linha: tuple(str(valor).strip() for valor in linha),
        axis=1,
    )
    chaves_existentes = set(chave_existente)
    chaves_novas = set(chave_nova)
    atualizados = len(chaves_novas & chaves_existentes)
    inseridos = len(chaves_novas - chaves_existentes)

    combinado = pd.concat([existente, registros], ignore_index=True, sort=False)
    combinado = combinado.fillna("")
    combinado = combinado.drop_duplicates(subset=chave, keep="last")
    combinado = combinado[colunas]
    combinado.to_csv(destino, index=False, encoding="utf-8-sig")
    return {
        "inseridos": inseridos,
        "atualizados": atualizados,
        "total": len(registros),
    }


def _esquema(tipo_dado: str) -> EsquemaImportacao:
    if tipo_dado not in ESQUEMAS_IMPORTACAO:
        raise ValueError(f"Tipo de dado não suportado: {tipo_dado}.")
    return ESQUEMAS_IMPORTACAO[tipo_dado]


def _normalizar_nome_coluna(valor: str) -> str:
    texto = str(valor).strip().lower()
    texto = re.sub(r"[áàãâ]", "a", texto)
    texto = re.sub(r"[éèê]", "e", texto)
    texto = re.sub(r"[íìî]", "i", texto)
    texto = re.sub(r"[óòõô]", "o", texto)
    texto = re.sub(r"[úùû]", "u", texto)
    texto = texto.replace("ç", "c")
    return re.sub(r"[^a-z0-9]+", " ", texto).strip()


def _converter_datas(valores: pd.Series) -> pd.Series:
    origem = valores.astype("string").str.strip()
    datas = pd.to_datetime(origem, format="ISO8601", errors="coerce")
    restantes = datas.isna()
    datas.loc[restantes] = pd.to_datetime(
        origem.loc[restantes],
        format="mixed",
        dayfirst=True,
        errors="coerce",
    )
    return datas


def _numero(valor: object) -> float:
    if pd.isna(valor):
        return float("nan")
    texto = str(valor).strip()
    if not texto:
        return float("nan")
    negativo = texto.startswith("(") and texto.endswith(")")
    texto = re.sub(r"[^0-9,.\-+]", "", texto)
    if "," in texto and "." in texto:
        if texto.rfind(",") > texto.rfind("."):
            texto = texto.replace(".", "").replace(",", ".")
        else:
            texto = texto.replace(",", "")
    elif "," in texto:
        partes = texto.split(",")
        texto = "".join(partes) if len(partes[-1]) == 3 else ".".join(partes)
    elif "." in texto:
        partes = texto.split(".")
        if len(partes[-1]) == 3:
            texto = "".join(partes)
        elif len(partes) > 2:
            texto = "".join(partes[:-1]) + "." + partes[-1]
    try:
        numero = float(texto)
    except ValueError:
        return float("nan")
    return -abs(numero) if negativo else numero


def _status_canonico(valor: object) -> str:
    status = _normalizar_nome_coluna(str(valor))
    if status in {
        "concluido", "concluida", "completed", "delivered", "entregue",
        "order completed", "paid", "settled", "fulfilled", "finished", "done",
        "aprovado", "aprovada", "finalizado", "finalizada",
    }:
        return "Concluído"
    if status in {"cancelado", "cancelada", "canceled", "cancelled"}:
        return "Cancelado"
    if status in {"devolvido", "devolvida", "returned", "refunded"}:
        return "Devolvido"
    if status in {
        "pending", "unpaid", "processing", "shipped", "to ship",
        "to receive", "ready to ship", "awaiting shipment",
        "awaiting payment", "in transit", "created", "incomplete",
        "confirmed", "payment required", "payment in process",
        "partially paid", "em andamento", "aberto", "aberta", "nao pago",
    }:
        return "Em andamento"
    return ""


def _adicionar_erro(
    erros: pd.Series,
    mascara: pd.Series,
    mensagem: str,
) -> None:
    erros.loc[mascara] = erros.loc[mascara].map(
        lambda atual: f"{atual}; {mensagem}" if atual else mensagem
    )
