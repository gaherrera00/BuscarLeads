"""Aba 1: dashboard de leads. É a primeira tela ao abrir o site."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from buscarleads import constantes
from buscarleads.dados.arquivos import data_coleta, idade_dias
from buscarleads.ui.componentes import (
    formatar_origem,
    metricas_leads,
    mostrar_distribuicao,
    mostrar_funil,
)


def _arquivos_em_uso(base: pd.DataFrame) -> list[str]:
    linhas = []
    for nome in base["arquivo_origem"].dropna().unique():
        caminho = constantes.DATA_DIR / nome
        if not caminho.exists():
            continue
        dias = idade_dias(caminho)
        idade = "hoje" if dias < 1 else f"há {int(dias)} dia(s)"
        linhas.append(f"`{nome}` — coletado em {data_coleta(caminho):%d/%m/%Y %H:%M} ({idade})")
    return linhas


def _serie(filtrado: pd.DataFrame, coluna: str) -> pd.Series:
    return filtrado[coluna] if not filtrado.empty else pd.Series(dtype=str)


def renderizar_dashboard(base: pd.DataFrame, filtrado: pd.DataFrame, rotulo: str, origens: dict) -> None:
    if base.empty:
        st.info(
            "Ainda não há uma base carregada. Configure a busca na lateral e "
            "selecione **Buscar / carregar base**."
        )
        return

    topo, total = st.columns([3, 1])
    with topo:
        st.markdown(f"**Base atual:** {rotulo or 'Localidade não informada'}")
        for linha in _arquivos_em_uso(base):
            st.caption(f"Arquivo em uso: {linha}")
        origem = formatar_origem(origens)
        if origem:
            st.caption(origem)
    total.metric("Leads na base", len(base))

    metricas_leads(filtrado)
    st.caption(
        "A pontuação é heurística e não representa probabilidade de conversão. "
        "A ausência de site no OpenStreetMap não prova que o negócio não tenha site."
    )

    st.subheader("Melhores oportunidades")
    if filtrado.empty:
        st.info("Nenhum lead corresponde aos filtros atuais.")
    else:
        melhores = filtrado.head(10)[
            ["pontuacao", "nome", "nicho", "localidade", "status_site", "telefone", "status"]
        ].rename(
            columns={
                "pontuacao": "Score", "nome": "Nome", "nicho": "Nicho", "localidade": "Localidade",
                "status_site": "Situação do site", "telefone": "Telefone", "status": "Status",
            }
        )
        st.dataframe(melhores, hide_index=True, width="stretch")
        st.caption("Abra a aba **Leads** para ver a lista completa, editar e exportar.")

    mostrar_funil(base, filtrado)

    vazio = "Não há leads para os filtros atuais."
    col_nicho, col_site, col_status = st.columns(3)
    with col_nicho:
        mostrar_distribuicao("Por nicho", _serie(filtrado, "nicho"), vazio)
    with col_site:
        mostrar_distribuicao("Por situação do site", _serie(filtrado, "status_site"), vazio)
    with col_status:
        mostrar_distribuicao("Por status do lead", _serie(filtrado, "status"), vazio)
