"""Leitura e gravação básica de CSV, compartilhada por todos os módulos de dados."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import pandas as pd


def gravar_csv(df: pd.DataFrame, caminho: Path) -> None:
    """Grava de forma atômica: nunca deixa um arquivo pela metade.

    O CSV é escrito num temporário e só então substitui o definitivo. Se algo
    falhar no meio (disco cheio, processo encerrado), o arquivo anterior
    continua intacto e o temporário é removido.
    """
    caminho = Path(caminho)
    temporario = caminho.with_name(caminho.name + ".tmp")
    try:
        df.to_csv(temporario, index=False, encoding="utf-8-sig")
        os.replace(temporario, caminho)
    finally:
        if temporario.exists():
            try:
                temporario.unlink()
            except OSError:
                pass


@lru_cache(maxsize=32)
def _ler_por_assinatura(caminho: str, mtime_ns: int, tamanho: int) -> pd.DataFrame:
    # mtime_ns e tamanho só entram na chave: quando o arquivo muda, a chave muda.
    return pd.read_csv(caminho, dtype=str, keep_default_na=False)


def ler_tabela(caminho: Path) -> pd.DataFrame:
    """Lê um CSV pequeno (status, enriquecimento, concorrência) com cache.

    A interface relê esses arquivos a cada interação do usuário. O cache é
    invalidado sozinho quando o arquivo muda, então nunca devolve dado velho.
    Devolve sempre uma cópia, segura para alterar.
    """
    estado = Path(caminho).stat()
    return _ler_por_assinatura(str(caminho), estado.st_mtime_ns, estado.st_size).copy()


def limpar_cache() -> None:
    _ler_por_assinatura.cache_clear()
