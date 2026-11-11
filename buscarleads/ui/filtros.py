"""Filtros dos resultados, na barra lateral. Valem para todas as abas."""

from __future__ import annotations

import hashlib
import re

import pandas as pd
import streamlit as st

from buscarleads.constantes import SITUACOES, STATUS_LEAD


def filtros_vazios() -> dict:
    return {"limite": 300}


def _chave_widgets(localidades: list[str], nichos: list[str]) -> str:
    """Muda só quando as opções mudam (outra base), preservando os filtros ao salvar edições."""
    texto = "|".join(localidades) + "##" + "|".join(nichos)
    return hashlib.sha1(texto.encode("utf-8")).hexdigest()[:10]


def aplicar_filtros(base: pd.DataFrame):
    """Desenha os filtros e devolve (base_filtrada, filtros)."""
    if base.empty:
        return base.copy(), filtros_vazios()

    localidades = sorted(base["localidade"].dropna().unique().tolist())
    nichos = sorted(base["nicho"].dropna().unique().tolist())
    k = _chave_widgets(localidades, nichos)

    with st.sidebar.expander("Filtros dos resultados", expanded=True):
        sel_loc = st.multiselect("Localidade", localidades, default=localidades, key=f"f_localidade_{k}")
        sel_nicho = st.multiselect("Nicho", nichos, default=nichos, key=f"f_nicho_{k}")
        sel_sit = st.multiselect(
            "Situação do site", SITUACOES, default=["Sem site", "Só rede social"], key=f"f_situacao_{k}"
        )
        sel_status = st.multiselect(
            "Status do lead",
            STATUS_LEAD,
            default=[s for s in STATUS_LEAD if s != "Descartado"],
            key=f"f_status_{k}",
        )
        so_contato = st.checkbox(
            "Só com forma de contato",
            value=True,
            key=f"f_contato_{k}",
            help="Telefone, e-mail, Instagram ou Facebook cadastrados.",
        )
        sem_redes = st.checkbox(
            "Excluir redes identificadas",
            value=True,
            key=f"f_redes_{k}",
            help="Considera rede quem tem brand:wikidata no OpenStreetMap.",
        )
        nome_busca = st.text_input("Nome contém", key=f"f_nome_{k}")
        limite = st.number_input(
            "Máx. linhas na tabela", min_value=50, max_value=2000, value=300, step=50, key=f"f_limite_{k}"
        )

        distancias = pd.to_numeric(base["distancia_km"], errors="coerce").dropna()
        max_dist = None
        if st.checkbox("Filtrar por distância máxima", key=f"f_ativar_distancia_{k}"):
            if distancias.empty:
                st.info("Não há distâncias válidas nesta base.")
            else:
                teto = max(1.0, float(distancias.max()))
                max_dist = st.slider(
                    "Distância máxima (km)", 0.0, teto, teto, 0.5, key=f"f_distancia_{k}",
                    help="Distância em linha reta até o ponto central da consulta.",
                )

    filtrado = base[
        base["localidade"].isin(sel_loc)
        & base["nicho"].isin(sel_nicho)
        & base["status_site"].isin(sel_sit)
        & base["status"].isin(sel_status)
    ]
    if so_contato:
        filtrado = filtrado[
            (filtrado["telefone"] != "")
            | (filtrado["email"] != "")
            | (filtrado["instagram"] != "")
            | (filtrado["facebook"] != "")
        ]
    if sem_redes:
        filtrado = filtrado[~filtrado["rede"]]
    if nome_busca.strip():
        filtrado = filtrado[
            filtrado["nome"].str.contains(re.escape(nome_busca.strip()), case=False, na=False)
        ]
    if max_dist is not None:
        filtrado = filtrado[filtrado["distancia_km"] <= max_dist]

    filtrado = filtrado.sort_values(["pontuacao", "distancia_km"], ascending=[False, True])
    return filtrado, {"limite": int(limite)}
