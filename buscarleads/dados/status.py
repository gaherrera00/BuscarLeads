"""Status e observações dos leads (``status_leads.csv``), por ``osm_id``."""

from __future__ import annotations

import os
from datetime import datetime

import pandas as pd

from buscarleads import constantes
from buscarleads.dados import avisos
from buscarleads.dados.tabelas import gravar_csv, ler_tabela

COLUNAS_STATUS = ["osm_id", "status", "observacao", "atualizado_em"]


def ler_status() -> dict:
    caminho = constantes.arquivo_status()
    if not caminho.exists():
        return {}

    try:
        df = ler_tabela(caminho)
        if not {"osm_id", "status", "observacao"} <= set(df.columns):
            raise ValueError("colunas inesperadas")
    except (ValueError, OSError, pd.errors.ParserError) as erro:
        backup = caminho.with_name(f"status_leads_corrompido_{datetime.now():%Y%m%d_%H%M%S}.csv")
        try:
            os.replace(caminho, backup)
        except OSError:
            pass
        avisos.registrar(
            f"Arquivo de status ilegível ({erro}). Uma cópia foi guardada como {backup.name}."
        )
        return {}

    if "atualizado_em" not in df.columns:
        df["atualizado_em"] = ""
    return {
        linha.osm_id: {
            "status": linha.status,
            "observacao": linha.observacao,
            "atualizado_em": linha.atualizado_em,
        }
        for linha in df.itertuples()
    }


def salvar_status(editado: pd.DataFrame) -> int:
    """Grava status e observação das linhas editadas. ``Novo`` sem nota some do arquivo.

    Só quem realmente mudou ganha uma nova data em ``atualizado_em``.
    Devolve quantos leads tiveram alteração.
    """
    estados = ler_status()
    agora = datetime.now().strftime("%Y-%m-%d %H:%M")
    alterados = 0

    for linha in editado.itertuples():
        observacao = "" if pd.isna(linha.observacao) else str(linha.observacao)
        anterior = estados.get(linha.osm_id)

        if linha.status == "Novo" and not observacao.strip():
            if anterior is not None:
                estados.pop(linha.osm_id)
                alterados += 1
            continue

        if (
            anterior is not None
            and anterior["status"] == linha.status
            and anterior["observacao"] == observacao
        ):
            continue  # nada mudou: preserva a data original

        estados[linha.osm_id] = {
            "status": linha.status,
            "observacao": observacao,
            "atualizado_em": agora,
        }
        alterados += 1

    if alterados:
        gravar_csv(
            pd.DataFrame(
                [{"osm_id": chave, **valor} for chave, valor in estados.items()],
                columns=COLUNAS_STATUS,
            ),
            constantes.arquivo_status(),
        )
    return alterados
