"""Barra lateral: e-mail de contato e parâmetros da busca."""

from __future__ import annotations

import streamlit as st

from buscarleads.constantes import GRUPOS_PADRAO, NICHOS
from buscarleads.contato import (
    carregar_contato,
    carregar_nome_vendedor,
    contato_configurado,
    email_de_contato_valido,
    salvar_contato,
    salvar_nome_vendedor,
)
from buscarleads.ui.estado import MODO_AREA, MODO_RAIO


@st.dialog("Configurar e-mail de contato")
def dialogo_email() -> None:
    st.write(
        "Informe um e-mail para identificar as consultas ao OpenStreetMap. "
        "Ele será salvo localmente em `dados_osm/config.json`."
    )
    contato = st.text_input(
        "E-mail",
        value=carregar_contato(),
        placeholder="voce@email.com",
        key="email_contato_config",
    )

    col_salvar, col_continuar = st.columns(2)
    if col_salvar.button("Salvar e-mail", type="primary", width="stretch"):
        email = contato.strip()
        if not email_de_contato_valido(email):
            st.error("Informe um e-mail válido.")
        else:
            try:
                salvar_contato(email)
            except OSError as erro:
                st.error(f"Não foi possível salvar a configuração: {erro}")
            else:
                st.rerun()

    if col_continuar.button("Continuar sem configurar", width="stretch"):
        st.rerun()


def configurar_email_inicio() -> None:
    """Mostra o pop-up uma vez por sessão se ainda não houver e-mail válido."""
    if st.session_state.get("email_dialog_exibido"):
        return
    st.session_state["email_dialog_exibido"] = True
    if not contato_configurado():
        dialogo_email()


def _erro_de_validacao(localidades, grupos, raio_km) -> str:
    if not localidades:
        return "Informe ao menos uma cidade ou bairro."
    if not grupos:
        return "Selecione ao menos um nicho."
    if raio_km and len(localidades) > 1:
        return "Busca por raio aceita apenas uma localidade."
    return ""


def renderizar_busca_sidebar():
    """Desenha os controles de busca. Devolve (localidades, raio, grupos, ttl, atualizar, buscar, invalido)."""
    # Valores iniciais por session_state: assim a busca aberta ao iniciar o app
    # pode preencher os campos sem conflito com o parâmetro `value`.
    st.session_state.setdefault("busca_localidades", "São Caetano do Sul, SP")
    st.session_state.setdefault("busca_modo", MODO_AREA)
    st.session_state.setdefault("busca_raio", 3)
    st.session_state.setdefault("busca_nichos", GRUPOS_PADRAO)
    st.session_state.setdefault("busca_ttl", 30)

    with st.sidebar:
        st.markdown("### Busca de leads")
        st.caption("Área, abrangência e nichos da próxima busca.")

        if st.button("Configurar e-mail de contato", width="stretch"):
            dialogo_email()

        nome_atual = carregar_nome_vendedor()
        novo_nome = st.text_input(
            "Seu nome (aparece nas mensagens)",
            value=nome_atual,
            key="config_seu_nome",
            placeholder="Ex.: João Silva",
        )
        if novo_nome.strip() and novo_nome.strip() != nome_atual:
            salvar_nome_vendedor(novo_nome)

        if not contato_configurado():
            st.warning(
                "Sem e-mail válido: bases em cache ainda podem ser carregadas, "
                "mas novas coletas ficam bloqueadas."
            )

        texto = st.text_input(
            "Cidade(s) ou bairro(s)",
            key="busca_localidades",
            help=(
                "Separe localidades por ponto e vírgula. Para a capital, prefira "
                "bairros (ex.: Pinheiros, São Paulo; Tatuapé, São Paulo)."
            ),
        )
        modo = st.radio("Abrangência", [MODO_AREA, MODO_RAIO], key="busca_modo")
        raio_km = st.slider("Raio (km)", 1, 20, key="busca_raio") if modo == MODO_RAIO else None
        grupos = st.multiselect("Nichos", list(NICHOS), key="busca_nichos")
        ttl = st.number_input("Validade do cache (dias)", min_value=1, max_value=365, key="busca_ttl")
        atualizar = st.checkbox(
            "Forçar nova coleta",
            key="busca_atualizar",
            help="Ignora o cache para as localidades desta busca. Correções manuais são mantidas.",
        )

        localidades = [parte.strip() for parte in texto.split(";") if parte.strip()]
        invalido = _erro_de_validacao(localidades, grupos, raio_km)
        if invalido:
            st.error(invalido)

        buscar = st.button(
            "Buscar / carregar base",
            type="primary",
            disabled=bool(invalido),
            width="stretch",
        )

    return localidades, raio_km, grupos, int(ttl), atualizar, buscar, invalido
