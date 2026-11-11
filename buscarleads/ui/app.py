"""Montagem da página: ordem das abas e fluxo de cada execução."""

from __future__ import annotations

import streamlit as st

from buscarleads.dados import avisos
from buscarleads.mensagens import obter_modelo_mensagem
from buscarleads.ui.configuracoes import renderizar_configuracoes
from buscarleads.ui.dashboard import renderizar_dashboard
from buscarleads.ui.estado import executar_busca, iniciar_sessao, montar_base
from buscarleads.ui.filtros import aplicar_filtros
from buscarleads.ui.leads import renderizar_leads
from buscarleads.ui.mapa import renderizar_mapa
from buscarleads.ui.pesquisa import renderizar_pesquisa
from buscarleads.ui.sidebar import configurar_email_inicio, renderizar_busca_sidebar
from buscarleads.ui.tema import CSS_TEMA

ABAS = ["Dashboard de leads", "Leads", "Pesquisa avançada", "Mapa", "Configurações"]


def main() -> None:
    st.set_page_config(
        page_title="Busca de leads", page_icon="📍", layout="wide", initial_sidebar_state="expanded"
    )
    st.markdown(CSS_TEMA, unsafe_allow_html=True)

    iniciar_sessao()
    configurar_email_inicio()

    st.title("Busca de leads")
    for aviso in avisos.consumir():
        st.warning(aviso)

    localidades, raio_km, grupos, ttl, atualizar, buscar, invalido = renderizar_busca_sidebar()
    assinatura = (tuple(localidades), raio_km, tuple(sorted(grupos)))

    if buscar and not invalido:
        executar_busca(localidades, raio_km, grupos, ttl, atualizar)
        for aviso in avisos.consumir():
            st.warning(aviso)

    for localidade, mensagem in st.session_state.get("falhas", []):
        st.warning(f"Não foi possível coletar **{localidade}**: {mensagem}")

    base = montar_base()
    sem_base = st.session_state.get("base") is None
    rotulo = st.session_state.get("rotulo", "")
    atual = st.session_state.get("assinatura")

    if st.session_state.get("busca_falhou"):
        st.error("A última busca falhou. A base anterior foi mantida e continua disponível.")
    elif not sem_base and atual is not None and assinatura != atual:
        st.info(
            "Os controles da busca foram alterados, mas a base exibida ainda é: "
            f"**{rotulo}**. Selecione **Buscar / carregar base** para atualizá-la."
        )
    if not sem_base and base.empty:
        st.warning("A busca terminou sem resultados. Tente outro nicho, bairro ou raio.")

    filtrado, filtros = aplicar_filtros(base)
    modelo = st.session_state.get("modelo_whatsapp", obter_modelo_mensagem())

    tab_dash, tab_leads, tab_pesquisa, tab_mapa, tab_config = st.tabs(ABAS)
    sem_dados = "Carregue uma base pela área de busca na lateral."

    with tab_dash:
        renderizar_dashboard(base, filtrado, rotulo, st.session_state.get("origens", {}))
    with tab_leads:
        if sem_base:
            st.info(sem_dados)
        else:
            renderizar_leads(filtrado, filtros, modelo)
    with tab_pesquisa:
        if sem_base:
            st.info(sem_dados)
        else:
            renderizar_pesquisa(base, filtrado)
    with tab_mapa:
        if sem_base:
            st.info(sem_dados)
        else:
            renderizar_mapa(filtrado)
    with tab_config:
        renderizar_configuracoes()

    st.divider()
    st.caption(
        "Dados © OpenStreetMap contributors (ODbL) · openstreetmap.org/copyright. "
        "Ao abordar, respeite a LGPD: identifique-se, ofereça opção de não receber contato "
        "e evite disparos em massa."
    )
