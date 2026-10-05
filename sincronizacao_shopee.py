from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

import pandas as pd
import requests

from armazenamento import salvar_importacao
from importador import _status_canonico

_URL_API = "https://partner.shopeemobile.com/api/v2"
_NOME_MARKETPLACE = "Shopee"
_TIMEOUT_REQUISICAO = (5, 20)
_LIMITE_PEDIDOS = 100
_LIMITE_ITENS = 100
_MAXIMO_RESULTADOS = 10_000
_FUSO_BRASILIA = timezone(timedelta(hours=-3))


def _valor_inteiro(valor: Any, campo: str) -> int:
    if isinstance(valor, bool) or not isinstance(valor, int) or valor < 0:
        raise RuntimeError(
            f"A API da Shopee retornou paginação inválida em {campo}."
        )
    return valor


def _valor_decimal(valor: Any, campo: str) -> Decimal:
    if isinstance(valor, bool):
        raise RuntimeError(f"A API da Shopee retornou {campo} inválido.")
    try:
        numero = Decimal(str(valor))
    except (InvalidOperation, ValueError):
        raise RuntimeError(f"A API da Shopee retornou {campo} inválido.") from None
    if not numero.is_finite() or numero < 0:
        raise RuntimeError(f"A API da Shopee retornou {campo} inválido.")
    return numero


def _obter_valor_texto(dados: dict[str, Any], campos: tuple[str, ...]) -> str:
    for nome in campos:
        valor = dados.get(nome)
        if isinstance(valor, str) and valor.strip():
            return valor.strip()
        if valor is not None and not isinstance(valor, (dict, list)):
            texto = str(valor).strip()
            if texto:
                return texto
    return ""


def _extrair_lista(valor: Any) -> list[Any]:
    if isinstance(valor, list):
        return valor
    if not isinstance(valor, dict):
        return []
    for nome in ("data", "response", "result", "results", "order_list", "item_list", "items", "list", "details"):
        item = valor.get(nome)
        if isinstance(item, list):
            return item
        if isinstance(item, dict):
            lista = _extrair_lista(item)
            if lista:
                return lista
    return []


def _extrair_dados_api(resposta: Any) -> list[Any]:
    if isinstance(resposta, list):
        return resposta
    if not isinstance(resposta, dict):
        return []
    if "data" in resposta:
        dados = resposta["data"]
        lista = _extrair_lista(dados)
        if lista:
            return lista
    for nome in ("response", "result", "results", "order_list", "item_list", "items", "list"):
        valor = resposta.get(nome)
        lista = _extrair_lista(valor)
        if lista:
            return lista
    return [resposta]


def _extrair_total(resposta: Any) -> int:
    if not isinstance(resposta, dict):
        return 0
    for nome in ("total_count", "total", "count"):
        valor = resposta.get(nome)
        if isinstance(valor, int) and valor >= 0:
            return valor
    for chave in ("data", "response"):
        dados = resposta.get(chave)
        if isinstance(dados, dict):
            total = _extrair_total(dados)
            if total:
                return total
    return 0


def _requisitar_json(
    access_token: str,
    caminho: str,
    parametros: dict[str, str | int] | None = None,
) -> Any:
    try:
        resposta = requests.get(
            f"{_URL_API}{caminho}",
            params={**(parametros or {}), "access_token": access_token},
            headers={"Accept": "application/json"},
            timeout=_TIMEOUT_REQUISICAO,
        )
    except requests.RequestException as erro:
        raise RuntimeError(
            "Não foi possível comunicar com a API da Shopee. "
            "Verifique a conexão e tente novamente."
        ) from erro

    if not resposta.ok:
        if resposta.status_code == 401:
            mensagem = (
                "A API da Shopee recusou a autenticação. Valide ou "
                "reautorize a conexão antes de sincronizar."
            )
        elif resposta.status_code == 403:
            mensagem = (
                "A conta não tem permissão para ler estes dados na Shopee."
            )
        elif resposta.status_code == 429:
            mensagem = (
                "A Shopee limitou as requisições. Aguarde alguns minutos e "
                "tente novamente."
            )
        else:
            mensagem = (
                "A API da Shopee recusou a leitura "
                f"(HTTP {resposta.status_code})."
            )
        raise RuntimeError(mensagem)

    try:
        return resposta.json()
    except requests.JSONDecodeError as erro:
        raise RuntimeError(
            "A API da Shopee retornou uma resposta inválida."
        ) from erro


def _data_pedido(valor: Any) -> date:
    if isinstance(valor, (int, float)):
        try:
            return datetime.fromtimestamp(int(valor), tz=_FUSO_BRASILIA).date()
        except (OverflowError, OSError, ValueError):
            raise RuntimeError(
                "A API da Shopee retornou uma data de pedido inválida."
            ) from None
    if isinstance(valor, str):
        texto = valor.strip()
        if not texto:
            raise RuntimeError(
                "A API da Shopee retornou uma data de pedido inválida."
            )
        try:
            if texto.endswith("Z"):
                texto = texto[:-1] + "+00:00"
            return datetime.fromisoformat(texto).astimezone(_FUSO_BRASILIA).date()
        except ValueError:
            try:
                return datetime.fromtimestamp(int(texto), tz=_FUSO_BRASILIA).date()
            except (TypeError, ValueError):
                raise RuntimeError(
                    "A API da Shopee retornou uma data de pedido inválida."
                ) from None
    raise RuntimeError(
        "A API da Shopee retornou uma data de pedido inválida."
    )


def _buscar_pedidos(
    access_token: str,
    data_inicio: date,
    data_fim: date,
) -> list[dict[str, Any]]:
    inicio = datetime.combine(data_inicio, time.min, tzinfo=_FUSO_BRASILIA)
    fim = datetime.combine(data_fim, time.max, tzinfo=_FUSO_BRASILIA)
    parametros: dict[str, str | int] = {
        "page_size": _LIMITE_PEDIDOS,
        "page_no": 1,
        "time_from": int(inicio.timestamp()),
        "time_to": int(fim.timestamp()),
    }

    pedidos: list[dict[str, Any]] = []
    total: int | None = None

    while total is None or len(pedidos) < total:
        resposta = _requisitar_json(
            access_token,
            "/order/get_order_list",
            parametros.copy(),
        )
        if not isinstance(resposta, dict):
            raise RuntimeError(
                "A API da Shopee retornou uma busca de pedidos inválida."
            )
        lista = _extrair_dados_api(resposta)
        if not isinstance(lista, list):
            raise RuntimeError(
                "A API da Shopee retornou uma busca de pedidos inválida."
            )
        total = _extrair_total(resposta)
        if total <= 0:
            total = len(lista)
        if total > _MAXIMO_RESULTADOS:
            raise RuntimeError(
                "O período contém mais pedidos do que o limite de leitura "
                "suportado nesta sincronização. Reduza o intervalo de datas."
            )
        if any(not isinstance(pedido, dict) for pedido in lista):
            raise RuntimeError(
                "A API da Shopee retornou um pedido em formato inválido."
            )
        pedidos.extend(lista)
        if len(pedidos) >= total or not lista:
            break
        parametros["page_no"] = int(parametros.get("page_no", 1)) + 1

    return pedidos


def _normalizar_pedidos(
    pedidos: list[dict[str, Any]],
    data_inicio: date,
    data_fim: date,
) -> pd.DataFrame:
    agregados: dict[tuple[str, str, str], dict[str, Any]] = {}

    for pedido in pedidos:
        if not isinstance(pedido, dict):
            raise RuntimeError(
                "A API da Shopee retornou um pedido em formato inválido."
            )

        pedido_id = _obter_valor_texto(
            pedido,
            ("order_sn", "order_id", "order_number", "id"),
        )
        data_raw = pedido.get("create_time") or pedido.get("created_time")
        if not pedido_id or data_raw is None:
            raise RuntimeError(
                "A API da Shopee retornou um pedido sem identificador ou data."
            )
        data_pedido = _data_pedido(data_raw)
        if not data_inicio <= data_pedido <= data_fim:
            continue

        status = _status_canonico(
            _obter_valor_texto(
                pedido,
                ("order_status", "status", "status_name"),
            )
        )
        if not status:
            raise RuntimeError(
                "A API da Shopee retornou um status de pedido não reconhecido."
            )

        itens = _extrair_lista(
            pedido.get("order_detail")
            or pedido.get("order_items")
            or pedido.get("details")
            or pedido.get("items")
            or pedido.get("line_items")
        )
        if not itens:
            raise RuntimeError(
                "A API da Shopee retornou um pedido sem itens válidos."
            )

        for item in itens:
            if not isinstance(item, dict):
                raise RuntimeError(
                    "A API da Shopee retornou um item de pedido inválido."
                )
            sku = _obter_valor_texto(
                item,
                ("item_sku", "shop_sku", "product_sn", "seller_sku", "sku", "item_id"),
            )
            produto = _obter_valor_texto(
                item,
                ("item_name", "product_name", "name", "title"),
            )
            if not sku:
                sku = str(item.get("item_id") or item.get("product_id") or "sem-sku").strip()
            if not produto:
                produto = sku

            quantidade = _valor_decimal(
                item.get("quantity")
                or item.get("item_quantity")
                or item.get("qty")
                or item.get("amount")
                or 0,
                "quantidade do item",
            )
            if quantidade <= 0:
                raise RuntimeError(
                    "A API da Shopee retornou uma quantidade de item que não é positiva."
                )

            preco = _valor_decimal(
                item.get("unit_price")
                or item.get("original_price")
                or item.get("price")
                or item.get("item_price")
                or 0,
                "preço unitário do item",
            )
            valor_total = item.get("total_amount")
            faturamento = (
                _valor_decimal(valor_total, "valor total do item")
                if valor_total is not None
                else preco * quantidade
            )
            if faturamento < preco * quantidade:
                faturamento = preco * quantidade

            chave = (str(pedido_id), sku, produto)
            registro = agregados.setdefault(
                chave,
                {
                    "id_pedido": str(pedido_id),
                    "data": data_pedido.isoformat(),
                    "marketplace": _NOME_MARKETPLACE,
                    "sku": sku,
                    "produto": produto,
                    "quantidade": Decimal("0"),
                    "preco_unitario": Decimal("0"),
                    "faturamento_bruto": Decimal("0"),
                    "desconto": Decimal("0"),
                    "taxa_marketplace": 0,
                    "frete_vendedor": 0,
                    "status": status,
                },
            )
            registro["quantidade"] += quantidade
            registro["faturamento_bruto"] += faturamento

    registros: list[dict[str, Any]] = []
    for registro in agregados.values():
        quantidade = registro["quantidade"]
        registro["preco_unitario"] = (
            registro["faturamento_bruto"] / quantidade
            if quantidade > 0
            else Decimal("0")
        )
        registros.append(registro)

    return pd.DataFrame(
        registros,
        columns=[
            "id_pedido",
            "data",
            "marketplace",
            "sku",
            "produto",
            "quantidade",
            "preco_unitario",
            "faturamento_bruto",
            "desconto",
            "taxa_marketplace",
            "frete_vendedor",
            "status",
        ],
    )


def sincronizar_pedidos(
    access_token: str,
    data_inicio: date,
    data_fim: date,
) -> dict[str, int]:
    if data_inicio > data_fim:
        raise ValueError("A data inicial não pode ser posterior à data final.")
    pedidos = _buscar_pedidos(access_token, data_inicio, data_fim)
    registros = _normalizar_pedidos(pedidos, data_inicio, data_fim)
    return salvar_importacao(
        "Pedidos",
        registros,
        preservar_campos={"taxa_marketplace", "frete_vendedor"},
    )


def _buscar_produtos(access_token: str) -> list[dict[str, Any]]:
    parametros: dict[str, str | int] = {"page_size": _LIMITE_ITENS, "page_no": 1}
    itens: list[dict[str, Any]] = []
    total: int | None = None

    while total is None or len(itens) < total:
        resposta = _requisitar_json(
            access_token,
            "/product/get_item_list",
            parametros.copy(),
        )
        if not isinstance(resposta, dict):
            raise RuntimeError(
                "A API da Shopee retornou uma busca de produtos inválida."
            )
        lista = _extrair_dados_api(resposta)
        if not isinstance(lista, list):
            raise RuntimeError(
                "A API da Shopee retornou uma busca de produtos inválida."
            )
        total = _extrair_total(resposta)
        if total <= 0:
            total = len(lista)
        if total > _MAXIMO_RESULTADOS:
            raise RuntimeError(
                "A conta possui mais produtos do que o limite de leitura "
                "suportado nesta sincronização."
            )
        if any(not isinstance(item, dict) for item in lista):
            raise RuntimeError(
                "A API da Shopee retornou um produto em formato inválido."
            )
        itens.extend(lista)
        if len(itens) >= total or not lista:
            break
        parametros["page_no"] = int(parametros.get("page_no", 1)) + 1

    return itens


def _normalizar_publicacoes(
    produtos: list[dict[str, Any]],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    dados_produtos: list[dict[str, Any]] = []
    estoques: list[dict[str, Any]] = []
    skus_encontrados: set[str] = set()

    for item in produtos:
        if not isinstance(item, dict):
            raise RuntimeError(
                "A API da Shopee retornou um produto em formato inválido."
            )

        sku = _obter_valor_texto(
            item,
            ("shop_sku", "item_sku", "product_sn", "seller_sku", "sku"),
        )
        if not sku:
            sku = str(item.get("item_id") or item.get("product_id") or "sem-sku").strip()
        if sku in skus_encontrados:
            raise RuntimeError(
                "A conta tem mais de um produto ativo com o SKU "
                f"{sku!r}. Corrija os SKUs duplicados antes de sincronizar "
                "produtos e estoque."
            )
        skus_encontrados.add(sku)

        produto = _obter_valor_texto(
            item,
            ("item_name", "product_name", "name", "title"),
        ) or sku
        estoque = item.get("stock")
        if estoque is None:
            estoque = item.get("stock_num") or item.get("stock_qty") or 0
        preco = item.get("price")
        if preco is None:
            preco = item.get("normal_price") or item.get("current_price") or 0

        dados_produtos.append({
            "marketplace": _NOME_MARKETPLACE,
            "sku": sku,
            "produto": produto,
            "categoria": "",
            "custo_unitario": Decimal("0"),
            "preco_venda": _valor_decimal(preco, "preço da publicação"),
            "estoque_inicial": Decimal("0"),
        })
        estoques.append({
            "marketplace": _NOME_MARKETPLACE,
            "sku": sku,
            "produto": produto,
            "estoque_atual": _valor_decimal(estoque, "estoque disponível"),
        })

    return (
        pd.DataFrame(
            dados_produtos,
            columns=[
                "marketplace",
                "sku",
                "produto",
                "categoria",
                "custo_unitario",
                "preco_venda",
                "estoque_inicial",
            ],
        ),
        pd.DataFrame(
            estoques,
            columns=["marketplace", "sku", "produto", "estoque_atual"],
        ),
    )


def sincronizar_produtos_e_estoque(
    access_token: str,
) -> dict[str, dict[str, int]]:
    produtos_api = _buscar_produtos(access_token)
    produtos, estoques = _normalizar_publicacoes(produtos_api)
    resultado_produtos = salvar_importacao(
        "Produtos",
        produtos,
        preservar_campos={"categoria", "custo_unitario", "estoque_inicial"},
    )
    resultado_estoque = salvar_importacao("Estoque", estoques)
    return {"produtos": resultado_produtos, "estoque": resultado_estoque}
