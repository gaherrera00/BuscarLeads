"""Aba 4: mapa dos estabelecimentos filtrados."""

from __future__ import annotations

import pandas as pd
import streamlit as st

LIMITE_PONTOS = 5000


def renderizar_mapa(filtrado: pd.DataFrame) -> None:
    st.subheader("Mapa de estabelecimentos")
    st.caption("Usa os mesmos filtros da barra lateral.")
    if filtrado.empty:
        st.info("Não há leads para mostrar no mapa.")
        return

    pontos = filtrado[["latitude", "longitude"]].apply(pd.to_numeric, errors="coerce").dropna()
    if pontos.empty:
        st.info("Esta base não contém coordenadas válidas para o mapa.")
        return
    if len(pontos) > LIMITE_PONTOS:
        st.caption(f"Mostrando os {LIMITE_PONTOS} melhores de {len(pontos)} pontos, para o mapa responder rápido.")
        pontos = pontos.head(LIMITE_PONTOS)
    st.map(pontos.rename(columns={"latitude": "lat", "longitude": "lon"}))
