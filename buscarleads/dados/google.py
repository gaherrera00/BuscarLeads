"""Cache local dos dados do Google Places (``enriquecido.csv``).

Cada consulta paga é gravada aqui na hora. Quem lê (tela, mensagens, exportação)
usa só este arquivo e nunca chama a API.
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd

from buscarleads import constantes
from buscarleads.constantes import COLUNAS_GOOGLE, COLUNAS_GOOGLE_NA_BASE
from buscarleads.dados.tabelas import gravar_csv, ler_tabela

_FORMATO = "%Y-%m-%d %H:%M"


def ler_enriquecido() -> dict[str, dict]:
    """{osm_id: {coluna: valor}} com todas as colunas do esquema (vazias se faltarem)."""
    caminho = constantes.arquivo_enriquecido()
    if not caminho.exists():
        return {}
    try:
        df = ler_tabela(caminho)
    except (OSError, pd.errors.ParserError, ValueError):
        return {}
    if "osm_id" not in df.columns:
        return {}

    df = df.reindex(columns=COLUNAS_GOOGLE, fill_value="")
    return {linha["osm_id"]: linha for linha in df.to_dict("records")}


def salvar_enriquecido(osm_id: str, dados: dict) -> None:
    """Grava ou atualiza um lead, preservando os demais. Chamada logo após cada consulta paga."""
    estados = ler_enriquecido()
    registro = {coluna: str(dados.get(coluna, "") or "") for coluna in COLUNAS_GOOGLE}
    registro["osm_id"] = osm_id
    registro["atualizado_em"] = datetime.now().strftime(_FORMATO)
    estados[osm_id] = registro
    gravar_csv(
        pd.DataFrame(list(estados.values()), columns=COLUNAS_GOOGLE),
        constantes.arquivo_enriquecido(),
    )


def idade_dados_dias(registro: dict) -> float | None:
    """Há quantos dias o dado foi consultado; None se a data for desconhecida."""
    try:
        quando = datetime.strptime(str(registro.get("atualizado_em", "")), _FORMATO)
    except ValueError:
        return None
    return max((datetime.now() - quando).total_seconds() / 86400, 0.0)


def mesclar_enriquecimento(base: pd.DataFrame) -> pd.DataFrame:
    """Junta à base os campos de leitura rápida do Google, sem chamar API."""
    base = base.copy()
    colunas = COLUNAS_GOOGLE_NA_BASE + ["gmn_atualizado"]
    if base.empty:
        for coluna in colunas:
            base[coluna] = pd.Series(dtype=str)
        return base

    estados = ler_enriquecido()
    if estados:
        tabela = pd.DataFrame.from_dict(estados, orient="index")
        tabela["gmn_atualizado"] = tabela["atualizado_em"]
    else:
        tabela = pd.DataFrame(columns=colunas)

    for coluna in colunas:
        if coluna in tabela.columns:
            base[coluna] = base["osm_id"].map(tabela[coluna]).fillna("")
        else:
            base[coluna] = ""
    return base
