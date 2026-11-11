"""Cache de concorrência por nicho + cidade (``concorrencia.csv``)."""

from __future__ import annotations

import re
from datetime import datetime

import pandas as pd

from buscarleads import constantes
from buscarleads.constantes import COLUNAS_CONCORRENCIA
from buscarleads.dados.tabelas import gravar_csv, ler_tabela

# Títulos de artigo/ranking não são concorrentes ("As 5 Melhores Oficinas...").
_RE_LISTA = re.compile(
    r"\b(melhores|melhor|top\s*\d+|\d+\s+(melhores|dicas|op[cç][oõ]es)|ranking|"
    r"guia|lista|onde\s+encontrar|como\s+escolher)\b",
    re.IGNORECASE,
)


def parece_artigo(titulo: str) -> bool:
    return bool(_RE_LISTA.search(titulo or ""))


def chave_serp(nicho: str, cidade: str) -> str:
    return f"{nicho.strip().casefold()}|{cidade.strip().casefold()}"


def ler_serp_cache() -> dict[str, dict]:
    caminho = constantes.arquivo_concorrencia()
    if not caminho.exists():
        return {}
    try:
        df = ler_tabela(caminho)
    except (OSError, pd.errors.ParserError, ValueError):
        return {}
    if "chave" not in df.columns:
        return {}
    df = df.reindex(columns=COLUNAS_CONCORRENCIA, fill_value="")
    return {linha["chave"]: linha for linha in df.to_dict("records")}


def entrada_valida(entrada: dict | None) -> bool:
    """Entrada existe e não é um título de artigo salvo por versões antigas."""
    return bool(entrada) and not parece_artigo(str(entrada.get("melhor_concorrente", "")))


def salvar_serp_cache(chave: str, dados: dict) -> None:
    estados = ler_serp_cache()
    registro = {coluna: str(dados.get(coluna, "") or "") for coluna in COLUNAS_CONCORRENCIA}
    registro["chave"] = chave
    registro["atualizado_em"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    estados[chave] = registro
    gravar_csv(
        pd.DataFrame(list(estados.values()), columns=COLUNAS_CONCORRENCIA),
        constantes.arquivo_concorrencia(),
    )


def gancho_concorrencia(nicho: str, cidade: str) -> dict:
    """Concorrente do cache para usar na mensagem; {} se não houver um utilizável."""
    if not nicho.strip() or not cidade.strip():
        return {}
    entrada = ler_serp_cache().get(chave_serp(nicho, cidade))
    if not entrada_valida(entrada) or not entrada.get("melhor_concorrente"):
        return {}
    return entrada
