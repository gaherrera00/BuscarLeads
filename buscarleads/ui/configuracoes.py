"""Aba 5: e-mail de contato, modelo de mensagem, arquivos salvos e fontes."""

from __future__ import annotations

import os

import pandas as pd
import streamlit as st

from buscarleads import constantes
from buscarleads.constantes import FONTE_DADOS
from buscarleads.contato import carregar_contato, contato_configurado
from buscarleads.dados.arquivos import resumo_arquivos
from buscarleads.mensagens import obter_modelo_mensagem
from buscarleads.ui.sidebar import dialogo_email


def renderizar_configuracoes() -> None:
    st.subheader("Configurações e informações")

    st.markdown("#### E-mail de contato")
    if contato_configurado():
        origem = (
            "variável de ambiente `BUSCA_LEADS_CONTATO`"
            if os.getenv("BUSCA_LEADS_CONTATO", "").strip()
            else "`dados_osm/config.json`"
        )
        st.success(f"E-mail válido configurado: **{carregar_contato()}**")
        st.caption(f"Origem da configuração: {origem}.")
    else:
        st.warning(
            "Não há e-mail válido configurado. Bases em cache podem ser carregadas, "
            "mas novas coletas ficam bloqueadas."
        )
    if st.button("Abrir configuração de e-mail", key="abrir_email_config"):
        dialogo_email()

    st.divider()
    st.markdown("#### Mensagem de WhatsApp")
    st.text_area(
        "Modelo da mensagem — use `{nome}` para inserir o nome do estabelecimento",
        value=obter_modelo_mensagem(),
        height=150,
        key="modelo_whatsapp",
        help="O link gerado abre uma tentativa de conversa; não confirma que o número tenha WhatsApp.",
    )
    st.caption(
        "Leads já pesquisados na Pesquisa avançada usam um modelo personalizado "
        "(nota do Google e, se houver, concorrente) em vez deste."
    )

    st.divider()
    st.markdown("#### APIs da Pesquisa avançada")
    st.write(
        f"Google Places: {'✅ chave encontrada' if constantes.chave_google() else '❌ sem GOOGLE_PLACES_API_KEY'}  \n"
        f"Serper: {'✅ chave encontrada' if constantes.chave_serper() else '❌ sem SERPER_API_KEY'}"
    )

    st.divider()
    st.markdown("#### Arquivos de leads salvos")
    arquivos = resumo_arquivos()
    if arquivos:
        st.dataframe(pd.DataFrame(arquivos), hide_index=True, width="stretch")
        st.caption(
            f"Pasta: `{constantes.DATA_DIR}`. O app sempre abre o arquivo mais recente de cada busca."
        )
    else:
        st.caption("Nenhum CSV salvo ainda.")

    st.divider()
    st.markdown("#### Fonte dos dados e uso responsável")
    st.markdown(
        f"{FONTE_DADOS}. A ausência de dados no OpenStreetMap não comprova que uma "
        "informação ou estabelecimento não exista."
    )
    st.markdown(
        "Ao abordar um estabelecimento, identifique-se, ofereça uma opção para não receber "
        "novos contatos, evite disparos em massa e respeite a LGPD."
    )
