from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

import pandas as pd
import requests
from postgrest.exceptions import APIError

from armazenamento import salvar_importacao
from importador import _status_canonico


_URL_API = "https://api.mercadolibre.com"
_NOME_MARKETPLACE = "Mercado Livre"
_TIMEOUT_REQUISICAO = (5, 20)
_LIMITE_PEDIDOS = 50
_LIMITE_PUBLICACOES = 50
_TAMANHO_LOTE_ITENS = 20
_MAXIMO_RESULTADOS = 10_000
_FUSO_BRASILIA = timezone(timedelta(hours=-3))


def _requisitar_json(
    access_token: str,
    caminho: str,
    parametros: dict[str, str | int] | None = None,
) -> Any:
    try:
        resposta = requests.get(
            f"{_URL_API}{caminho}",
            params=parametros,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {access_token}",
            },
            timeout=_TIMEOUT_REQUISICAO,
        )
    except requests.RequestException as erro:
        raise RuntimeError(
            "Não foi possível comunicar com a API do Mercado Livre. "
            "Verifique a conexão e tente novamente."
        ) from erro

    if not resposta.ok:
        if resposta.status_code == 401:
            mensagem = (
                "A API do Mercado Livre recusou a autenticação. Valide ou "
                "reautorize a conexão antes de sincronizar."
            )
        elif resposta.status_code == 403:
            mensagem = (
                "A conta não tem permissão para ler estes dados no Mercado "
                "Livre."
            )
        elif resposta.status_code == 429:
            mensagem = (
                "O Mercado Livre limitou as requisições. Aguarde alguns "
                "minutos e tente novamente."
            )
        else:
            mensagem = (
                "A API do Mercado Livre recusou a leitura "
                f"(HTTP {resposta.status_code})."
            )
        raise RuntimeError(mensagem)

    try:
        return resposta.json()
    except requests.JSONDecodeError as erro:
        raise RuntimeError(
            "A API do Mercado Livre retornou uma resposta inválida."
        ) from erro


def _valor_inteiro(valor: Any, campo: str) -> int:
    if isinstance(valor, bool) or not isinstance(valor, int) or valor < 0:
        raise RuntimeError(
            f"A API do Mercado Livre retornou paginação inválida em {campo}."
        )
    return valor


def _buscar_pedidos(
    access_token: str,
    vendedor_id: str,
    data_inicio: date,
    data_fim: date,
) -> list[dict[str, Any]]:
    inicio = datetime.combine(data_inicio, time.min, _FUSO_BRASILIA)
    fim = datetime.combine(data_fim, time.max, _FUSO_BRASILIA)
    parametros: dict[str, str | int] = {
        "seller": vendedor_id,
        "order.date_created.from": inicio.isoformat(timespec="milliseconds"),
        "order.date_created.to": fim.isoformat(timespec="milliseconds"),
        "sort": "date_asc",
        "limit": _LIMITE_PEDIDOS,
        "offset": 0,
    }
    pedidos: list[dict[str, Any]] = []
    total: int | None = None

    while total is None or len(pedidos) < total:
        resposta = _requisitar_json(
            access_token,
            "/orders/search",
            parametros.copy(),
        )
        if not isinstance(resposta, dict):
            raise RuntimeError(
                "A API do Mercado Livre retornou uma busca de pedidos "
                "inválida."
            )
        resultados = resposta.get("results")
        paginacao = resposta.get("paging")
        if not isinstance(resultados, list) or not isinstance(paginacao, dict):
            raise RuntimeError(
                "A API do Mercado Livre retornou pedidos sem paginação válida."
            )
        total = _valor_inteiro(paginacao.get("total"), "pedidos.total")
        if total > _MAXIMO_RESULTADOS:
            raise RuntimeError(
                "O período contém mais pedidos do que o limite de leitura "
                "suportado nesta sincronização. Reduza o intervalo de datas."
            )
        if any(not isinstance(pedido, dict) for pedido in resultados):
            raise RuntimeError(
                "A API do Mercado Livre retornou um pedido em formato inválido."
            )
        pedidos.extend(resultados)
        if len(pedidos) >= total:
            break
        if not resultados:
            raise RuntimeError(
                "A paginação de pedidos do Mercado Livre terminou antes de "
                "todos os resultados serem recebidos."
            )
        parametros["offset"] = len(pedidos)

    return pedidos


def _decimal_nao_negativo(valor: Any, campo: str) -> Decimal:
    if isinstance(valor, bool):
        raise RuntimeError(
            f"A API do Mercado Livre retornou {campo} inválido."
        )
    try:
        numero = Decimal(str(valor))
    except (InvalidOperation, ValueError):
        raise RuntimeError(
            f"A API do Mercado Livre retornou {campo} inválido."
        ) from None
    if not numero.is_finite() or numero < 0:
        raise RuntimeError(
            f"A API do Mercado Livre retornou {campo} inválido."
        )
    return numero


def _sku_publicacao(
    item_id: str,
    item: dict[str, Any],
    variacao: dict[str, Any] | None = None,
) -> str:
    for origem in (variacao, item):
        if not isinstance(origem, dict):
            continue
        for campo in ("seller_custom_field", "seller_sku"):
            valor = origem.get(campo)
            if isinstance(valor, str) and valor.strip():
                return valor.strip()
        atributos = origem.get("attributes")
        if isinstance(atributos, list):
            for atributo in atributos:
                if (
                    isinstance(atributo, dict)
                    and atributo.get("id") == "SELLER_SKU"
                ):
                    valor = atributo.get("value_name")
                    if isinstance(valor, str) and valor.strip():
                        return valor.strip()

    variacao_id = variacao.get("id") if variacao else None
    if variacao_id is not None:
        return f"{item_id}-{variacao_id}"
    return item_id


def _normalizar_pedidos(
    pedidos: list[dict[str, Any]],
    data_inicio: date,
    data_fim: date,
) -> pd.DataFrame:
    agregados: dict[tuple[str, str, str], dict[str, Any]] = {}
    for pedido in pedidos:
        pedido_id = pedido.get("id")
        data_criacao = pedido.get("date_created")
        status = _status_canonico(pedido.get("status", ""))
        itens = pedido.get("order_items")
        if (
            pedido_id is None
            or not isinstance(data_criacao, str)
            or not isinstance(itens, list)
            or not itens
        ):
            raise RuntimeError(
                "A API do Mercado Livre retornou um pedido sem identificador, "
                "data ou itens válidos."
            )
        try:
            data_pedido = datetime.fromisoformat(
                data_criacao.replace("Z", "+00:00")
            ).date()
        except ValueError as erro:
            raise RuntimeError(
                "A API do Mercado Livre retornou uma data de pedido inválida."
            ) from erro
        if not data_inicio <= data_pedido <= data_fim:
            continue
        if not status:
            raise RuntimeError(
                "A API do Mercado Livre retornou um status de pedido não "
                "reconhecido. Nenhum registro deste lote foi salvo."
            )

        for linha in itens:
            if not isinstance(linha, dict) or not isinstance(
                linha.get("item"), dict
            ):
                raise RuntimeError(
                    "A API do Mercado Livre retornou um item de pedido "
                    "inválido."
                )
            item = linha["item"]
            item_id = str(item.get("id", "")).strip()
            if not item_id:
                raise RuntimeError(
                    "A API do Mercado Livre retornou um item sem identificador."
                )
            variacao_id = linha.get("variation_id")
            item_para_sku = {
                **item,
                "seller_sku": item.get("seller_sku")
                or item.get("seller_custom_field"),
            }
            variacao = (
                {"id": variacao_id}
                if variacao_id is not None
                else None
            )
            sku = _sku_publicacao(item_id, item_para_sku, variacao)
            produto = str(item.get("title") or item_id).strip()
            quantidade = _decimal_nao_negativo(
                linha.get("quantity"),
                "quantidade do item",
            )
            if quantidade <= 0:
                raise RuntimeError(
                    "A API do Mercado Livre retornou uma quantidade de item "
                    "que não é positiva."
                )
            preco = _decimal_nao_negativo(
                linha.get("unit_price"),
                "preço unitário do item",
            )
            preco_cheio_valor = linha.get("full_unit_price")
            preco_cheio = (
                _decimal_nao_negativo(
                    preco_cheio_valor,
                    "preço cheio do item",
                )
                if preco_cheio_valor is not None
                else preco
            )
            if preco_cheio < preco:
                raise RuntimeError(
                    "A API do Mercado Livre retornou um preço cheio menor "
                    "que o preço unitário."
                )
            moeda = linha.get("currency_id") or pedido.get("currency_id")
            if moeda is not None and moeda != "BRL":
                raise RuntimeError(
                    "A sincronização de pedidos atualmente aceita somente "
                    "valores em BRL."
                )

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
                    "faturamento_bruto": Decimal("0"),
                    "desconto": Decimal("0"),
                    "taxa_marketplace": 0,
                    "frete_vendedor": 0,
                    "status": status,
                },
            )
            registro["quantidade"] += quantidade
            registro["faturamento_bruto"] += preco_cheio * quantidade
            registro["desconto"] += (preco_cheio - preco) * quantidade

    registros: list[dict[str, Any]] = []
    for registro in agregados.values():
        quantidade = registro["quantidade"]
        registro["preco_unitario"] = (
            registro["faturamento_bruto"] / quantidade
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
    vendedor_id: str,
    data_inicio: date,
    data_fim: date,
) -> dict[str, int]:
    if data_inicio > data_fim:
        raise ValueError("A data inicial não pode ser posterior à data final.")
    pedidos = _buscar_pedidos(
        access_token,
        vendedor_id,
        data_inicio,
        data_fim,
    )
    registros = _normalizar_pedidos(pedidos, data_inicio, data_fim)
    return salvar_importacao(
        "Pedidos",
        registros,
        preservar_campos={"taxa_marketplace", "frete_vendedor"},
    )


def _buscar_ids_publicacoes(
    access_token: str,
    vendedor_id: str,
) -> list[str]:
    parametros: dict[str, str | int] = {
        "status": "active",
        "limit": _LIMITE_PUBLICACOES,
        "offset": 0,
    }
    ids: list[str] = []
    total: int | None = None

    while total is None or len(ids) < total:
        resposta = _requisitar_json(
            access_token,
            f"/users/{vendedor_id}/items/search",
            parametros.copy(),
        )
        if not isinstance(resposta, dict):
            raise RuntimeError(
                "A API do Mercado Livre retornou uma busca de publicações "
                "inválida."
            )
        resultados = resposta.get("results")
        paginacao = resposta.get("paging")
        if not isinstance(resultados, list) or not isinstance(paginacao, dict):
            raise RuntimeError(
                "A API do Mercado Livre retornou publicações sem paginação "
                "válida."
            )
        total = _valor_inteiro(paginacao.get("total"), "publicações.total")
        if total > _MAXIMO_RESULTADOS:
            raise RuntimeError(
                "A conta possui mais publicações do que o limite de leitura "
                "suportado nesta sincronização."
            )
        if any(not isinstance(item_id, str) or not item_id for item_id in resultados):
            raise RuntimeError(
                "A API do Mercado Livre retornou uma publicação sem "
                "identificador válido."
            )
        ids.extend(resultados)
        if len(ids) >= total:
            break
        if not resultados:
            raise RuntimeError(
                "A paginação de publicações terminou antes de todos os "
                "resultados serem recebidos."
            )
        parametros["offset"] = len(ids)

    return ids


def _buscar_publicacoes(
    access_token: str,
    ids: list[str],
) -> list[dict[str, Any]]:
    publicacoes: list[dict[str, Any]] = []
    for inicio in range(0, len(ids), _TAMANHO_LOTE_ITENS):
        lote = ids[inicio:inicio + _TAMANHO_LOTE_ITENS]
        resposta = _requisitar_json(
            access_token,
            "/items",
            {"ids": ",".join(lote)},
        )
        if not isinstance(resposta, list):
            raise RuntimeError(
                "A API do Mercado Livre retornou detalhes de publicações "
                "inválidos."
            )
        if len(resposta) != len(lote):
            raise RuntimeError(
                "A API do Mercado Livre não retornou todos os detalhes das "
                "publicações solicitadas."
            )
        for resultado in resposta:
            if (
                not isinstance(resultado, dict)
                or resultado.get("code") != 200
                or not isinstance(resultado.get("body"), dict)
            ):
                raise RuntimeError(
                    "Não foi possível ler uma publicação do Mercado Livre. "
                    "Nenhum dado de produto deste lote foi salvo."
                )
            publicacoes.append(resultado["body"])
    return publicacoes


def _normalizar_publicacoes(
    publicacoes: list[dict[str, Any]],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    produtos: list[dict[str, Any]] = []
    estoques: list[dict[str, Any]] = []
    skus_encontrados: set[str] = set()

    for publicacao in publicacoes:
        item_id = str(publicacao.get("id", "")).strip()
        titulo = str(publicacao.get("title") or item_id).strip()
        if not item_id or not titulo:
            raise RuntimeError(
                "A API do Mercado Livre retornou uma publicação sem "
                "identificador ou título."
            )
        variacoes = publicacao.get("variations")
        if variacoes is None:
            variacoes = []
        if not isinstance(variacoes, list):
            raise RuntimeError(
                "A API do Mercado Livre retornou variações em formato inválido."
            )
        variantes: list[dict[str, Any] | None] = (
            variacoes if variacoes else [None]
        )
        for variacao in variantes:
            if variacao is not None and not isinstance(variacao, dict):
                raise RuntimeError(
                    "A API do Mercado Livre retornou uma variação inválida."
                )
            sku = _sku_publicacao(item_id, publicacao, variacao)
            if sku in skus_encontrados:
                raise RuntimeError(
                    "A conta tem mais de uma publicação ativa com o SKU "
                    f"{sku!r}. Corrija os SKUs duplicados antes de sincronizar "
                    "produtos e estoque."
                )
            skus_encontrados.add(sku)
            estoque = (
                variacao.get("available_quantity")
                if variacao is not None
                else publicacao.get("available_quantity")
            )
            estoque_decimal = _decimal_nao_negativo(
                estoque,
                "estoque disponível",
            )
            preco = _decimal_nao_negativo(
                publicacao.get("price"),
                "preço da publicação",
            )
            produtos.append({
                "marketplace": _NOME_MARKETPLACE,
                "sku": sku,
                "produto": titulo,
                "categoria": "",
                "custo_unitario": 0,
                "preco_venda": preco,
                "estoque_inicial": 0,
            })
            estoques.append({
                "marketplace": _NOME_MARKETPLACE,
                "sku": sku,
                "produto": titulo,
                "estoque_atual": estoque_decimal,
            })

    return (
        pd.DataFrame(
            produtos,
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
    vendedor_id: str,
) -> dict[str, dict[str, int]]:
    ids = _buscar_ids_publicacoes(access_token, vendedor_id)
    publicacoes = _buscar_publicacoes(access_token, ids)
    produtos, estoques = _normalizar_publicacoes(publicacoes)
    resultado_produtos = salvar_importacao(
        "Produtos",
        produtos,
        preservar_campos={
            "categoria",
            "custo_unitario",
            "estoque_inicial",
        },
    )
    try:
        resultado_estoque = salvar_importacao("Estoque", estoques)
    except APIError as erro:
        raise RuntimeError(
            "Os produtos foram sincronizados, mas não foi possível salvar "
            f"os saldos de estoque: {erro.message}"
        ) from erro
    return {
        "produtos": resultado_produtos,
        "estoque": resultado_estoque,
    }
