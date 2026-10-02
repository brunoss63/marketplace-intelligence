from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path

import pandas as pd
import streamlit as st
from postgrest.exceptions import APIError

from componentes import animar_pagina, cabecalho_pagina, tabela_limpa
from armazenamento import (
    is_database_mode,
    listar_historico_importacoes,
    salvar_lote_importacao,
)
from importador import (
    COLUNAS_CANONICAS,
    ESQUEMAS_IMPORTACAO,
    listar_planilhas_xlsx,
    ler_arquivo_importado,
    mesclar_importacao_dashboard,
    normalizar_importacao,
    sugerir_mapeamento,
)


ETAPAS = [
    "Selecionar",
    "Upload",
    "Mapear",
    "Validar",
    "Revisar",
    "Importar",
    "Resultado",
]
TIPOS_DADO = list(ESQUEMAS_IMPORTACAO)
MARKETPLACES = ["Mercado Livre", "Shopee"]
RAIZ_DADOS = Path(__file__).resolve().parents[1] / "dados"
RAIZ_IMPORTACOES = RAIZ_DADOS / "importacoes"
ARQUIVO_HISTORICO = RAIZ_IMPORTACOES / "historico.json"
MENSAGEM_SEM_MAPEAMENTO = "— Não mapear —"


def _estado() -> dict[str, object]:
    estado = st.session_state.get("importacao_etapas")
    if not isinstance(estado, dict):
        estado = {"etapa": 1}
        st.session_state["importacao_etapas"] = estado
    return estado


def _avancar(estado: dict[str, object], etapa: int) -> None:
    estado["etapa"] = etapa
    st.rerun()


def _slug(valor: str) -> str:
    return (
        valor.lower()
        .replace(" ", "_")
        .replace("&", "e")
        .replace("ç", "c")
        .replace("ã", "a")
    )


def _arquivos_importacao(estado: dict[str, object]) -> list[dict[str, object]]:
    arquivos = estado.get("arquivos")
    if isinstance(arquivos, list) and arquivos:
        return [item for item in arquivos if isinstance(item, dict)]

    conteudo = estado.get("conteudo")
    nome_arquivo = estado.get("nome_arquivo")
    if isinstance(conteudo, bytes) and isinstance(nome_arquivo, str):
        return [{
            "conteudo": conteudo,
            "nome_arquivo": nome_arquivo,
            "planilha": estado.get("planilha"),
            "mapeamento": estado.get("mapeamento"),
        }]
    return []


def _arquivo_origem_label(estado: dict[str, object]) -> str:
    nomes = [
        str(arquivo.get("nome_arquivo", "arquivo"))
        for arquivo in _arquivos_importacao(estado)
    ]
    if not nomes:
        return str(estado.get("nome_arquivo", "Arquivo não informado"))
    return ", ".join(nomes)


def _carregar_origem_arquivo(
    arquivo: dict[str, object],
    planilha: str | None = None,
) -> pd.DataFrame:
    conteudo = arquivo.get("conteudo")
    nome_arquivo = arquivo.get("nome_arquivo")
    if not isinstance(conteudo, bytes) or not isinstance(nome_arquivo, str):
        raise ValueError("Envie novamente o arquivo para continuar.")
    return ler_arquivo_importado(
        conteudo,
        nome_arquivo,
        planilha or arquivo.get("planilha"),
    )


def _carregar_origem(
    estado: dict[str, object],
    planilha: str | None = None,
) -> pd.DataFrame:
    arquivos = _arquivos_importacao(estado)
    if not arquivos:
        raise ValueError("Envie novamente o arquivo para continuar.")
    if len(arquivos) > 1:
        raise ValueError(
            "Há vários arquivos na importação. Valide e revisem o conjunto "
            "completo antes de continuar."
        )
    return _carregar_origem_arquivo(arquivos[0], planilha)


def _normalizar_estado(
    estado: dict[str, object],
) -> tuple[pd.DataFrame, pd.Series]:
    tipo_dado = str(estado["tipo_dado"])
    marketplace = str(estado["marketplace"])
    arquivos = _arquivos_importacao(estado)
    if not arquivos:
        raise ValueError("Envie novamente o arquivo para continuar.")

    quadros: list[pd.DataFrame] = []
    erros: list[pd.Series] = []
    for arquivo in arquivos:
        mapeamento = arquivo.get("mapeamento")
        if not isinstance(mapeamento, dict):
            raise ValueError("Mapeie as colunas antes de validar.")
        dados = _carregar_origem_arquivo(arquivo)
        normalizado, erros_arquivo = normalizar_importacao(
            dados,
            tipo_dado,
            marketplace,
            mapeamento,
        )
        quadros.append(normalizado.reset_index(drop=True))
        erros.append(erros_arquivo.reset_index(drop=True))

    if not quadros:
        raise ValueError("Nenhum arquivo foi carregado para normalização.")

    return (
        pd.concat(quadros, ignore_index=True),
        pd.concat(erros, ignore_index=True),
    )


def _fingerprint(estado: dict[str, object]) -> str:
    arquivos = _arquivos_importacao(estado)
    if not arquivos:
        raise ValueError("A importação ainda não foi mapeada.")

    assinatura = []
    for indice, arquivo in enumerate(arquivos):
        mapeamento = arquivo.get("mapeamento")
        if not isinstance(mapeamento, dict):
            raise ValueError("A importação ainda não foi mapeada.")
        assinatura.append({
            "indice": indice,
            "nome_arquivo": str(arquivo.get("nome_arquivo", "")),
            "conteudo": sha256(arquivo.get("conteudo", b"")).hexdigest(),
            "marketplace": str(estado["marketplace"]),
            "tipo_dado": str(estado["tipo_dado"]),
            "mapeamento": mapeamento,
            "planilha": str(arquivo.get("planilha", "")),
        })

    payload = json.dumps(assinatura, sort_keys=True).encode("utf-8")
    return sha256(payload).hexdigest()[:20]


def _opcionais_nao_mapeados(
    estado: dict[str, object],
) -> list[str]:
    tipo_dado = str(estado["tipo_dado"])
    campos = ESQUEMAS_IMPORTACAO[tipo_dado]["campos"]
    opcionais: set[str] = set()
    for arquivo in _arquivos_importacao(estado):
        mapeamento = arquivo.get("mapeamento")
        if not isinstance(mapeamento, dict):
            continue
        for campo, (rotulo, obrigatorio, _) in campos.items():
            if not obrigatorio and not mapeamento.get(campo):
                opcionais.add(rotulo)
    return sorted(opcionais)


def _ler_historico() -> list[dict[str, object]]:
    if is_database_mode():
        return [
            {
                "data_hora": item["imported_at"],
                "marketplace": item["marketplace"],
                "tipo_dado": item["data_type"],
                "arquivo_origem": item["source_filename"],
                "registros_origem": item["source_records"],
                "importados": item["imported_records"],
                "inseridos": item["inserted_records"],
                "atualizados": item["updated_records"],
                "ignorados": item["ignored_records"],
                "erros": item["error_records"],
                "status": item["status"],
                "fingerprint": item["fingerprint"],
            }
            for item in listar_historico_importacoes()
        ]

    if not ARQUIVO_HISTORICO.exists():
        return []
    try:
        dados = json.loads(ARQUIVO_HISTORICO.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as erro:
        raise ValueError(
            f"Não foi possível ler o histórico de importações: {erro}"
        ) from erro
    if not isinstance(dados, list) or any(
        not isinstance(item, dict) for item in dados
    ):
        raise ValueError("O arquivo do histórico de importações está inválido.")
    return dados


def _importacao_existente(fingerprint: str) -> dict[str, object] | None:
    return next(
        (
            item
            for item in _ler_historico()
            if item.get("fingerprint") == fingerprint
        ),
        None,
    )


def _salvar_importacao(
    estado: dict[str, object],
    registros_validos: pd.DataFrame,
    registros_ignorados: int,
    quantidade_erros: int,
) -> dict[str, object]:
    fingerprint = _fingerprint(estado)
    historico = _ler_historico()
    existente = next(
        (
            item
            for item in historico
            if item.get("fingerprint") == fingerprint
        ),
        None,
    )
    if existente is not None:
        raise ValueError(
            "Este mesmo arquivo, marketplace, tipo e mapeamento já foram "
            "importados. O registro existente não foi duplicado."
        )

    tipo_dado = str(estado["tipo_dado"])
    marketplace = str(estado["marketplace"])
    nome_arquivo = _arquivo_origem_label(estado)
    merge = mesclar_importacao_dashboard(tipo_dado, registros_validos)
    data_hora = datetime.now().astimezone().isoformat(timespec="seconds")
    resultado: dict[str, object] = {
        "data_hora": data_hora,
        "marketplace": marketplace,
        "tipo_dado": tipo_dado,
        "arquivo_origem": nome_arquivo,
        "registros_origem": len(registros_validos) + registros_ignorados,
        "importados": len(registros_validos),
        "inseridos": merge["inseridos"],
        "atualizados": merge["atualizados"],
        "ignorados": registros_ignorados,
        "erros": quantidade_erros,
        "status": "Concluída" if quantidade_erros == 0 else "Concluída com avisos",
        "fingerprint": fingerprint,
    }
    if is_database_mode():
        salvar_lote_importacao(resultado)
        return resultado

    pasta_tipo = RAIZ_IMPORTACOES / _slug(tipo_dado)
    pasta_tipo.mkdir(parents=True, exist_ok=True)
    nome_saida = (
        f"{_slug(marketplace)}_{fingerprint}.csv"
    )
    caminho_saida = pasta_tipo / nome_saida
    if caminho_saida.exists():
        raise ValueError(
            "O arquivo normalizado desta importação já existe, mas não "
            "consta no histórico. Ele não será sobrescrito."
        )
    caminho_temporario = caminho_saida.with_suffix(".tmp")
    resultado["arquivo_normalizado"] = str(
        caminho_saida.relative_to(RAIZ_DADOS)
    )
    caminho_historico_temporario = ARQUIVO_HISTORICO.with_suffix(".tmp")
    arquivo_normalizado_publicado = False

    try:
        registros_validos[COLUNAS_CANONICAS[tipo_dado]].to_csv(
            caminho_temporario,
            index=False,
            encoding="utf-8-sig",
        )
        historico.append(resultado)
        caminho_historico_temporario.write_text(
            json.dumps(historico, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        caminho_temporario.replace(caminho_saida)
        arquivo_normalizado_publicado = True
        caminho_historico_temporario.replace(ARQUIVO_HISTORICO)
    except OSError as erro:
        if caminho_temporario.exists():
            caminho_temporario.unlink()
        if caminho_historico_temporario.exists():
            caminho_historico_temporario.unlink()
        if arquivo_normalizado_publicado:
            caminho_saida.unlink(missing_ok=True)
        raise OSError(f"Falha ao salvar a importação: {erro}") from erro
    return resultado


def _mostrar_historico() -> None:
    st.subheader("Histórico de importações")
    try:
        historico = _ler_historico()
    except (ValueError, APIError) as erro:
        st.error(str(erro))
        return
    if not historico:
        st.caption("Nenhuma importação registrada até agora.")
        return

    tabela = pd.DataFrame(historico[-20:][::-1]).rename(
        columns={
            "data_hora": "Data/hora",
            "marketplace": "Marketplace",
            "tipo_dado": "Tipo de dado",
            "arquivo_origem": "Arquivo",
            "registros_origem": "Registros",
            "importados": "Importados",
            "inseridos": "Inseridos",
            "atualizados": "Atualizados",
            "ignorados": "Ignorados",
            "erros": "Erros",
            "status": "Status",
        }
    )
    colunas = [
        "Data/hora", "Marketplace", "Tipo de dado", "Arquivo",
        "Registros", "Importados", "Inseridos", "Atualizados", "Ignorados",
        "Erros", "Status",
    ]
    tabela = tabela[[coluna for coluna in colunas if coluna in tabela]]
    if "Data/hora" in tabela:
        def formatar_data_hora(valor: object) -> str:
            try:
                return datetime.fromisoformat(str(valor)).astimezone().strftime(
                    "%d/%m/%Y %H:%M"
                )
            except ValueError:
                return str(valor)

        tabela["Data/hora"] = tabela["Data/hora"].map(formatar_data_hora)

    tabela_limpa(
        tabela,
        badges={
            "Marketplace": {
                "Mercado Livre": "ml",
                "Shopee": "shopee",
            },
            "Status": {
                "Concluída": "positive",
                "Concluída com avisos": "warning",
            },
        },
        chave="historico_importacoes",
        linhas_por_pagina=10,
    )
    _mostrar_resumo_acumulado(historico)


def _mostrar_resumo_acumulado(historico: list[dict[str, object]]) -> None:
    registros = pd.DataFrame(historico)
    if registros.empty:
        return

    for coluna in (
        "importados",
        "inseridos",
        "atualizados",
        "ignorados",
        "erros",
    ):
        if coluna not in registros:
            registros[coluna] = 0
        registros[coluna] = pd.to_numeric(
            registros[coluna],
            errors="coerce",
        ).fillna(0)

    if "inseridos" not in pd.DataFrame(historico).columns:
        registros["inseridos"] = (
            registros["importados"] - registros["atualizados"]
        ).clip(lower=0)
    else:
        inseridos_antigos = registros["inseridos"].eq(0) & registros["importados"].gt(0)
        registros.loc[inseridos_antigos, "inseridos"] = (
            registros.loc[inseridos_antigos, "importados"]
            - registros.loc[inseridos_antigos, "atualizados"]
        ).clip(lower=0)

    if "marketplace" not in registros:
        registros["marketplace"] = "Não informado"
    if "tipo_dado" not in registros:
        registros["tipo_dado"] = "Não informado"
    registros["registros_analisados"] = pd.to_numeric(
        registros.get("registros_origem", registros["importados"] + registros["ignorados"]),
        errors="coerce",
    ).fillna(registros["importados"] + registros["ignorados"])

    resumo = (
        registros.groupby(["marketplace", "tipo_dado"], dropna=False)
        .agg(
            importacoes=("tipo_dado", "size"),
            registros_analisados=("registros_analisados", "sum"),
            inseridos=("inseridos", "sum"),
            atualizados=("atualizados", "sum"),
            ignorados=("ignorados", "sum"),
            erros=("erros", "sum"),
        )
        .reset_index()
        .rename(
            columns={
                "marketplace": "Marketplace",
                "tipo_dado": "Tipo de dado",
                "importacoes": "Importações",
                "registros_analisados": "Registros analisados",
                "inseridos": "Inseridos",
                "atualizados": "Atualizados",
                "ignorados": "Ignorados",
                "erros": "Erros",
            }
        )
        .sort_values(["Marketplace", "Tipo de dado"])
    )
    st.subheader("Impacto acumulado por marketplace e tipo de dado")
    st.dataframe(resumo, use_container_width=True, hide_index=True)


def _mostrar_etapas(etapa_atual: int) -> None:
    itens = []
    for indice, nome in enumerate(ETAPAS, start=1):
        if indice < etapa_atual:
            estado = "completed"
            icone = "✓"
        elif indice == etapa_atual:
            estado = "active"
            icone = str(indice)
        else:
            estado = "upcoming"
            icone = str(indice)
        itens.append(
            f'<div class="mi-import-step {estado}">'
            f'<span>{icone}</span><b>{nome}</b></div>'
        )
    st.markdown(
        """
        <style>
        .mi-import-steps {
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            gap: 8px;
            margin: 4px 0 14px;
            padding: 12px;
            border: 1px solid #263449;
            border-radius: 8px;
            background: #121C2B;
        }
        .mi-import-step {
            display: flex;
            align-items: center;
            min-height: 30px;
            padding: 4px 8px;
            border: 1px solid transparent;
            border-radius: 6px;
            gap: 6px;
            color: #8292A8;
            font-size: 11px;
            transition:
                transform 160ms ease,
                border-color 160ms ease,
                background-color 160ms ease,
                color 160ms ease;
        }
        .mi-import-step:hover {
            transform: translateY(-2px);
            border-color: rgba(96, 165, 250, .3);
            background: rgba(59, 130, 246, .08);
            color: #E2E8F0;
        }
        .mi-import-step span {
            display: grid;
            width: 20px;
            height: 20px;
            place-items: center;
            border: 1px solid #334155;
            border-radius: 50%;
            font-size: 10px;
        }
        .mi-import-step.active { color: #E2E8F0; }
        .mi-import-step.active span {
            border-color: #3B82F6;
            background: #3B82F6;
            color: white;
        }
        .mi-import-step.completed { color: #60A5FA; }
        .mi-import-step.completed span {
            border-color: rgba(59, 130, 246, .45);
            color: #60A5FA;
        }
        .stVerticalBlock:has(
            > [data-testid="stElementContainer"] .mi-import-controls-anchor
        ) [data-testid="stSelectbox"] {
            padding: 5px 7px;
            border: 1px solid #263449;
            border-radius: 6px;
            background: linear-gradient(145deg, #151F2E, #121C2B);
            transition:
                border-color 160ms ease,
                background-color 160ms ease,
                box-shadow 160ms ease;
        }
        .stVerticalBlock:has(
            > [data-testid="stElementContainer"] .mi-import-controls-anchor
        ) [data-testid="stSelectbox"]:hover {
            border-color: #3B82F6;
            box-shadow: 0 0 0 1px rgba(59, 130, 246, .12);
        }
        .stVerticalBlock:has(
            > [data-testid="stElementContainer"] .mi-import-controls-anchor
        ) [data-testid="stSelectbox"] label {
            color: #8292A8;
            font-size: 10px;
            font-weight: 650;
        }
        .stVerticalBlock:has(
            > [data-testid="stElementContainer"] .mi-import-controls-anchor
        ) [data-testid="stSelectbox"] [role="group"] {
            min-height: 34px;
            border: 1px solid #2B3B52;
            border-radius: 5px;
            background: #0F172A;
        }
        .stVerticalBlock:has(
            > [data-testid="stElementContainer"] .mi-import-controls-anchor
        ) [data-testid="stSelectbox"] [role="combobox"] {
            min-height: 32px;
            padding: 0 8px;
            color: #E2E8F0;
            font-size: 11px;
            cursor: pointer;
        }
        .stVerticalBlock:has(
            > [data-testid="stElementContainer"] .mi-import-controls-anchor
        ) [data-testid="stSelectbox"] button {
            cursor: pointer;
        }
        .stVerticalBlock:has(
            > [data-testid="stElementContainer"] .mi-import-controls-anchor
        ) [data-testid="stBaseButton-primary"] {
            border: 1px solid #3B82F6;
            border-radius: 6px;
            background: #3B82F6;
            color: #F8FAFC;
            transition:
                background-color 150ms ease,
                border-color 150ms ease,
                box-shadow 150ms ease,
                transform 150ms ease;
        }
        .stVerticalBlock:has(
            > [data-testid="stElementContainer"] .mi-import-controls-anchor
        ) [data-testid="stBaseButton-primary"]:hover:not(:disabled) {
            border-color: #60A5FA;
            background: #2563EB;
            box-shadow: 0 4px 12px rgba(37, 99, 235, .2);
            transform: translateY(-1px);
        }
        .stVerticalBlock:has(
            > [data-testid="stElementContainer"] .mi-import-controls-anchor
        ) [data-testid="stBaseButton-primary"]:disabled {
            border-color: #334155;
            background: #1E293B;
            color: #8292A8;
        }
        .stVerticalBlock:has(
            > [data-testid="stElementContainer"] .mi-import-controls-anchor
        ) [data-testid="stCheckbox"] > label {
            padding: 9px 11px;
            border: 1px solid #263449;
            border-radius: 6px;
            background: #121C2B;
            color: #CBD5E1;
            cursor: pointer;
            transition:
                border-color 160ms ease,
                background-color 160ms ease;
        }
        .stVerticalBlock:has(
            > [data-testid="stElementContainer"] .mi-import-controls-anchor
        ) [data-testid="stCheckbox"] > label:hover {
            border-color: #3B82F6;
            background: #151F2E;
        }
        .stVerticalBlock:has(
            > [data-testid="stElementContainer"] .mi-import-controls-anchor
        ) [data-testid="stCheckbox"] [role="checkbox"] {
            border-radius: 4px;
            cursor: pointer;
        }
        @media (max-width: 800px) {
            .mi-import-step { flex: 1 0 28%; }
        }
        @media (prefers-reduced-motion: reduce) {
            .mi-import-step,
            .stVerticalBlock:has(
                > [data-testid="stElementContainer"] .mi-import-controls-anchor
            ) [data-testid="stSelectbox"],
            .stVerticalBlock:has(
                > [data-testid="stElementContainer"] .mi-import-controls-anchor
            ) [data-testid="stCheckbox"] > label,
            .stVerticalBlock:has(
                > [data-testid="stElementContainer"] .mi-import-controls-anchor
            ) [data-testid="stBaseButton-primary"] {
                transition: none;
            }
            .mi-import-step:hover {
                transform: none;
            }
        }
        </style>
        <div class="mi-import-steps">
        """
        + "".join(itens)
        + "</div>",
        unsafe_allow_html=True,
    )


def _botao_voltar(estado: dict[str, object], etapa: int) -> None:
    if etapa > 1 and st.button("Voltar", key=f"import_voltar_{etapa}"):
        _avancar(estado, etapa - 1)


animar_pagina("importar_dados")
cabecalho_pagina(
    "Importação de Dados",
    "Transforme arquivos CSV ou XLSX do marketplace em tabelas internas "
    "padronizadas.",
    "⇧",
)

estado = _estado()
etapa_atual = int(estado.get("etapa", 1))
_mostrar_etapas(etapa_atual)

with st.container(border=True):
    st.markdown(
        '<div class="mi-import-controls-anchor"></div>',
        unsafe_allow_html=True,
    )
    if etapa_atual < 7:
        st.subheader(f"Etapa {etapa_atual} — {ETAPAS[etapa_atual - 1]}")

    if etapa_atual == 1:
        st.caption("Informe de onde vêm os dados e qual tabela será importada.")
        marketplace = st.selectbox(
            "Marketplace",
            MARKETPLACES,
            index=MARKETPLACES.index(
                estado.get("marketplace", MARKETPLACES[0])
            ),
            key="importacao_marketplace_selecao",
        )
        tipo_dado = st.selectbox(
            "Tipo de dado",
            TIPOS_DADO,
            index=TIPOS_DADO.index(
                estado.get("tipo_dado", TIPOS_DADO[0])
            ),
            key="importacao_tipo_selecao",
        )
        st.caption(
            "Cada tipo tem seu próprio esquema canônico. As colunas e a "
            "ordem do CSV/XLSX de origem não precisam coincidir com esse modelo."
        )
        if st.button("Continuar para upload", type="primary"):
            tipo_anterior = estado.get("tipo_dado")
            if tipo_anterior != tipo_dado:
                for chave in (
                    "arquivos",
                    "conteudo",
                    "nome_arquivo",
                    "planilha",
                    "source_hash",
                    "mapeamento",
                    "resultado",
                ):
                    estado.pop(chave, None)
                st.session_state.pop("importacao_upload", None)
                for chave in list(st.session_state):
                    if chave.startswith("import_map_"):
                        st.session_state.pop(chave, None)
            estado["marketplace"] = marketplace
            estado["tipo_dado"] = tipo_dado
            _avancar(estado, 2)

    elif etapa_atual == 2:
        st.caption(
            f"Envie um ou mais arquivos de {estado.get('tipo_dado', 'dados')} "
            f"do marketplace {estado.get('marketplace', '')}. Nesta operação, "
            "todos os arquivos devem ser desse tipo; cada arquivo precisa "
            "conter os campos obrigatórios."
        )
        arquivos = st.file_uploader(
            "Arquivos de origem",
            type=["csv", "xlsx"],
            max_upload_size=20,
            key="importacao_upload",
            help="Arquivos CSV ou Excel .xlsx de até 20 MB. Você pode enviar vários arquivos em uma mesma importação.",
            accept_multiple_files=True,
        )
        if arquivos:
            lista_arquivos: list[dict[str, object]] = []
            for arquivo in arquivos:
                conteudo = arquivo.getvalue()
                if len(conteudo) > 20 * 1024 * 1024:
                    st.error(f"O arquivo {arquivo.name} excede o limite de 20 MB.")
                    continue
                planilha_selecionada: str | None = None
                if arquivo.name.lower().endswith(".xlsx"):
                    try:
                        planilhas = listar_planilhas_xlsx(conteudo)
                    except ValueError as erro:
                        st.error(str(erro))
                        planilhas = []
                    if planilhas:
                        planilha_selecionada = st.selectbox(
                            "Planilha",
                            planilhas,
                            index=0,
                            key=f"importacao_planilha_{sha256(conteudo).hexdigest()[:12]}_{arquivo.name}",
                        )
                if arquivo.name.lower().endswith(".csv") or planilha_selecionada:
                    try:
                        dados_origem = ler_arquivo_importado(
                            conteudo,
                            arquivo.name,
                            planilha_selecionada,
                        )
                    except ValueError as erro:
                        st.error(str(erro))
                        continue
                    if dados_origem.empty:
                        st.error(f"O arquivo {arquivo.name} não contém linhas de dados.")
                        continue
                    st.caption(
                        f"{arquivo.name} · {len(dados_origem):,} "
                        f"registros · {len(dados_origem.columns)} colunas"
                    )
                    st.dataframe(
                        dados_origem.head(10),
                        use_container_width=True,
                        hide_index=True,
                    )
                    lista_arquivos.append({
                        "conteudo": conteudo,
                        "nome_arquivo": arquivo.name,
                        "planilha": planilha_selecionada,
                    })
            if lista_arquivos:
                estado["arquivos"] = lista_arquivos
                estado["conteudo"] = lista_arquivos[0]["conteudo"]
                estado["nome_arquivo"] = lista_arquivos[0]["nome_arquivo"]
                estado["planilha"] = lista_arquivos[0].get("planilha")
                if st.button(
                    "Continuar para mapeamento",
                    type="primary",
                ):
                    _avancar(estado, 3)
        _botao_voltar(estado, 2)

    elif etapa_atual == 3:
        arquivos = _arquivos_importacao(estado)
        if not arquivos:
            st.error("Envie novamente o arquivo para continuar.")
        else:
            tipo_dado = str(estado["tipo_dado"])
            esquema = ESQUEMAS_IMPORTACAO[tipo_dado]
            campos = esquema["campos"]
            st.caption(
                "Associe cada arquivo às colunas do modelo interno. Para arquivos "
                "parciais, deixe campos opcionais sem mapeamento. Campos "
                "obrigatórios continuam marcados com *."
            )
            with st.form("importacao_mapeamento_total"):
                for indice_arquivo, arquivo in enumerate(arquivos):
                    nome_arquivo = str(arquivo.get("nome_arquivo", f"Arquivo {indice_arquivo + 1}"))
                    st.subheader(f"Arquivo {indice_arquivo + 1}: {nome_arquivo}")
                    dados_origem = _carregar_origem_arquivo(arquivo)
                    sugestoes = sugerir_mapeamento(
                        tipo_dado,
                        dados_origem.columns.tolist(),
                    )
                    mapeamento_existente = arquivo.get("mapeamento", {})
                    if not isinstance(mapeamento_existente, dict):
                        mapeamento_existente = {}
                    opcoes = [MENSAGEM_SEM_MAPEAMENTO, *dados_origem.columns.tolist()]
                    mapeamento: dict[str, str | None] = {}
                    campos_lista = list(campos.items())
                    for inicio in range(0, len(campos_lista), 2):
                        colunas = st.columns(2, gap="medium")
                        for coluna_ui, (campo, (rotulo, requerido, _)) in zip(
                            colunas,
                            campos_lista[inicio : inicio + 2],
                        ):
                            valor_atual = mapeamento_existente.get(
                                campo,
                                sugestoes.get(campo),
                            )
                            indice = (
                                opcoes.index(valor_atual)
                                if valor_atual in opcoes
                                else 0
                            )
                            escolhido = coluna_ui.selectbox(
                                f"{rotulo}{' *' if requerido else ''}",
                                opcoes,
                                index=indice,
                                key=f"import_map_{indice_arquivo}_{campo}",
                            )
                            mapeamento[campo] = (
                                None
                                if escolhido == MENSAGEM_SEM_MAPEAMENTO
                                else escolhido
                            )
                    arquivo["mapeamento"] = mapeamento
                    st.caption(
                        f"Preview: {len(dados_origem):,} registros e "
                        f"{len(dados_origem.columns)} colunas."
                    )
                    st.dataframe(
                        dados_origem.head(5),
                        use_container_width=True,
                        hide_index=True,
                    )
                    st.divider()
                enviado = st.form_submit_button(
                    "Salvar mapeamento e validar",
                    type="primary",
                )
            if enviado:
                estado["arquivos"] = arquivos
                estado.pop("mapeamento", None)
                estado.pop("resultado", None)
                _avancar(estado, 4)
        _botao_voltar(estado, 3)

    elif etapa_atual == 4:
        try:
            normalizado, erros = _normalizar_estado(estado)
        except (ValueError, KeyError, APIError) as erro:
            st.error(str(erro))
        else:
            validos = erros.eq("")
            invalidos = ~validos
            metricas = st.columns(3)
            metricas[0].metric("Registros analisados", f"{len(normalizado):,}")
            metricas[1].metric("Válidos", f"{int(validos.sum()):,}")
            metricas[2].metric("Com problemas", f"{int(invalidos.sum()):,}")
            if invalidos.any():
                st.warning(
                    "Registros com problemas serão ignorados se você "
                    "confirmar a importação parcial na etapa de revisão."
                )
                amostra_erros = normalizado.loc[invalidos].head(30).copy()
                amostra_erros["problemas"] = erros.loc[invalidos].head(30)
                st.dataframe(
                    amostra_erros,
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.success(
                    "Validação concluída: todos os registros podem ser importados."
                )
            if validos.any() and st.button(
                "Continuar para revisão",
                type="primary",
            ):
                _avancar(estado, 5)
        _botao_voltar(estado, 4)

    elif etapa_atual == 5:
        try:
            normalizado, erros = _normalizar_estado(estado)
        except (ValueError, KeyError) as erro:
            st.error(str(erro))
        else:
            validos = erros.eq("")
            ignorados = int((~validos).sum())
            opcionais_sem_mapeamento = _opcionais_nao_mapeados(estado)
            metricas = st.columns(4)
            metricas[0].metric("Origem", _arquivo_origem_label(estado))
            metricas[1].metric("Marketplace", str(estado["marketplace"]))
            metricas[2].metric("Serão importados", f"{int(validos.sum()):,}")
            metricas[3].metric("Serão ignorados", f"{ignorados:,}")
            st.caption(
                "Confira os registros já convertidos ao esquema interno "
                f"de {estado['tipo_dado']}."
            )
            if opcionais_sem_mapeamento:
                st.warning(
                    "Estes campos opcionais não foram mapeados e receberão "
                    "zero ou texto vazio: "
                    + ", ".join(opcionais_sem_mapeamento)
                    + "."
                )
            st.dataframe(
                normalizado.loc[validos].head(20),
                use_container_width=True,
                hide_index=True,
            )
            revisado = True
            if ignorados:
                revisado = st.checkbox(
                    f"Revisei os problemas e aceito importar apenas as "
                    f"{int(validos.sum()):,} linhas válidas.",
                    key=f"importacao_aceitar_parcial_{_fingerprint(estado)}",
                )
            if revisado and st.button(
                "Confirmar revisão",
                type="primary",
            ):
                _avancar(estado, 6)
        _botao_voltar(estado, 5)

    elif etapa_atual == 6:
        try:
            normalizado, erros = _normalizar_estado(estado)
            fingerprint = _fingerprint(estado)
            existente = _importacao_existente(fingerprint)
        except (ValueError, KeyError) as erro:
            st.error(str(erro))
        else:
            validos = erros.eq("")
            st.markdown(
                f"**Marketplace:** {estado['marketplace']}  \n"
                f"**Tipo de dado:** {estado['tipo_dado']}  \n"
                f"**Arquivo(s):** {_arquivo_origem_label(estado)}  \n"
                f"**Linhas que serão registradas:** {int(validos.sum()):,}  \n"
                f"**Linhas que serão ignoradas:** {int((~validos).sum()):,}"
            )
            if is_database_mode():
                st.info(
                    "Após a confirmação, os registros válidos serão gravados "
                    "no banco persistente deste tenant. Registros com a mesma "
                    "chave serão atualizados; novos registros serão inseridos."
                )
            else:
                st.info(
                    "Após a confirmação, os registros válidos serão arquivados "
                    "em `dados/importacoes/` e consolidados nas tabelas "
                    "principais em `dados/`, que alimentam o dashboard. "
                    "Registros com a mesma chave serão atualizados; novos "
                    "registros serão inseridos."
                )
            opcionais_sem_mapeamento = _opcionais_nao_mapeados(estado)
            if opcionais_sem_mapeamento:
                st.warning(
                    "Confirme que estes campos opcionais podem ficar sem "
                    "valor: " + ", ".join(opcionais_sem_mapeamento) + "."
                )
            if existente is not None:
                st.warning(
                    "Este arquivo com este mapeamento já consta no histórico "
                    "e não poderá ser duplicado."
                )
            elif st.button(
                "Importar registros válidos",
                type="primary",
                disabled=not validos.any(),
            ):
                try:
                    resultado = _salvar_importacao(
                        estado,
                        normalizado.loc[validos].copy(),
                        int((~validos).sum()),
                        int((~validos).sum()),
                    )
                except (OSError, ValueError, APIError) as erro:
                    st.error(str(erro))
                else:
                    estado["resultado"] = resultado
                    _avancar(estado, 7)
        _botao_voltar(estado, 6)

    elif etapa_atual == 7:
        resultado = estado.get("resultado")
        if not isinstance(resultado, dict):
            st.info(
                "Nenhum resultado de importação está aberto. Você pode "
                "consultar o histórico ou iniciar uma nova importação."
            )
        else:
            st.success(str(resultado["status"]))
            st.subheader("Resumo desta importação")
            resumo_importacao = pd.DataFrame(
                [
                    {
                        "Marketplace": resultado["marketplace"],
                        "Tipo de dado": resultado["tipo_dado"],
                        "Arquivo(s)": resultado["arquivo_origem"],
                        "Registros importados": resultado["importados"],
                        "Inseridos": resultado.get("inseridos", 0),
                        "Atualizados": resultado["atualizados"],
                        "Ignorados": resultado["ignorados"],
                        "Erros": resultado["erros"],
                    }
                ]
            )
            st.dataframe(
                resumo_importacao,
                use_container_width=True,
                hide_index=True,
            )
            if is_database_mode():
                st.markdown(
                    "**Armazenamento:** Banco persistente do tenant  \n"
                    f"**Origem:** {resultado['arquivo_origem']} · "
                    f"{resultado['marketplace']} · {resultado['tipo_dado']}"
                )
            else:
                st.markdown(
                    f"**Tabela interna:** `{resultado['arquivo_normalizado']}`  \n"
                    f"**Origem:** {resultado['arquivo_origem']} · "
                    f"{resultado['marketplace']} · {resultado['tipo_dado']}"
                )
            st.caption("Resumo da atualização no dashboard")
            st.info(
                f"Registro de {resultado['tipo_dado']}: "
                f"{int(resultado.get('inseridos', 0))} novos e "
                f"{int(resultado.get('atualizados', 0))} registros atualizados "
                f"na base principal."
            )
        if st.button("Iniciar nova importação", type="primary"):
            st.session_state.pop("importacao_etapas", None)
            st.session_state.pop("importacao_upload", None)
            st.session_state.pop("importacao_marketplace_selecao", None)
            st.session_state.pop("importacao_tipo_selecao", None)
            for chave in list(st.session_state):
                if chave.startswith("import_map_"):
                    st.session_state.pop(chave, None)
            st.rerun()

_mostrar_historico()
