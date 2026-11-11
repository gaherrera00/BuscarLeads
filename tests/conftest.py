"""Fixtures: cada teste roda numa pasta de dados temporária e isolada."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from buscarleads import constantes  # noqa: E402
from buscarleads.constantes import COLUNAS  # noqa: E402
from buscarleads.dados import arquivos, avisos, tabelas  # noqa: E402


@pytest.fixture
def pasta(tmp_path, monkeypatch):
    monkeypatch.setattr(constantes, "DATA_DIR", tmp_path)
    tabelas.limpar_cache()
    avisos.consumir()
    return tmp_path


def lead(osm_id="node/1", nome="Padaria Sol", **extra) -> dict:
    base = {c: "" for c in COLUNAS}
    base.update(
        nome=nome, nicho="Padaria", localidade="Cidade Teste, SP", endereco="Rua A, 10",
        distancia_km="1.0", site="", instagram="", facebook="", email="",
        telefone="(11) 4221-3344", whatsapp_num="", status_site="Sem site", rede="False",
        pontuacao="1", osm_id=osm_id, osm_url=f"https://www.openstreetmap.org/{osm_id}",
        latitude="-23.6", longitude="-46.5", coletado_em="2026-11-09 10:00:00",
    )
    base.update(extra)
    return base


def criar_csv(pasta: Path, nome_arquivo: str, linhas: list[dict], meta: dict | None = None) -> Path:
    caminho = pasta / nome_arquivo
    pd.DataFrame(linhas, columns=COLUNAS).to_csv(caminho, index=False, encoding="utf-8-sig")
    if meta is not None:
        arquivos.gravar_meta(caminho, meta["localidade"], meta.get("raio_km"), meta.get("grupos"), "coleta")
    return caminho
