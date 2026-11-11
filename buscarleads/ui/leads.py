"""Aba 2: tabela de leads com edição direta (status, observação e dados do CSV)."""

from __future__ import annotations

import hashlib

import pandas as pd
import streamlit as st

from buscarleads.constantes import COLUNAS_EDITAVEIS, FONTE_DADOS, STATUS_LEAD
from buscarleads.contato import carregar_nome_vendedor
from buscarleads.dados.arquivos import nome_exportacao
from buscarleads.dados.leads import aplicar_edicoes
from buscarleads.dados.status import salvar_status
from buscarleads.mensagens import (
    coluna_whatsapp,
    criar_link_google,
    neutralizar_formulas,
    texto_abordagem,
)
from buscarleads.normalizacao import url_valida
from buscarleads.ui.estado import recarregar_base_ativa

ORDEM_COLUNAS = [
    "pontuacao", "nome", "nicho", "localidade", "status_site", "telefone",
    "whatsapp_url", "instagram", "facebook", "email", "site", "google_url",
    "osm_url", "endereco", "distancia_km", "gmn_nota", "gmn_avaliacoes",
    "status", "observacao",
]
EDITAVEIS_NA_TABELA = COLUNAS_EDITAVEIS + ["status", "observacao"]


def _vazio_para_none(serie: pd.Series) -> pd.Series:
    return serie.replace("", None)


def preparar_tabela(filtrado: pd.DataFrame, limite: int, modelo: str) -> pd.DataFrame:
    """Recorta as melhores linhas e monta as colunas de exibição (links, notas)."""
    tabela = filtrado.head(limite).copy()
    seu_nome = carregar_nome_vendedor() or "[seu nome]"
    tabela["whatsapp_url"] = coluna_whatsapp(tabela, modelo, seu_nome)
    tabela["google_url"] = [
        criar_link_google(nome, local) for nome, local in zip(tabela["nome"], tabela["localidade"])
    ]
    tabela["site"] = [site if url_valida(site) else None for site in tabela["site"]]
    for coluna in ("instagram", "facebook", "osm_url", "email"):
        tabela[coluna] = _vazio_para_none(tabela[coluna])
    for coluna in ("gmn_nota", "gmn_avaliacoes"):
        tabela[coluna] = pd.to_numeric(tabela[coluna], errors="coerce")
    return tabela[["osm_id"] + ORDEM_COLUNAS]


def _texto(valor) -> str:
    return "" if valor is None or (isinstance(valor, float) and pd.isna(valor)) else str(valor).strip()


def diferencas_dados(editado: pd.DataFrame, original: pd.DataFrame) -> dict[str, dict]:
    """{osm_id: {coluna: novo_valor}} só do que o usuário mudou nos campos do CSV."""
    novo = editado.set_index("osm_id")
    antigo = original.set_index("osm_id")
    mudancas: dict[str, dict] = {}
    for osm_id in novo.index.intersection(antigo.index):
        campos = {
            coluna: _texto(novo.at[osm_id, coluna])
            for coluna in COLUNAS_EDITAVEIS
            if _texto(novo.at[osm_id, coluna]) != _texto(antigo.at[osm_id, coluna])
        }
        if campos:
            mudancas[osm_id] = campos
    return mudancas


def salvar_alteracoes(editado, original, filtrado) -> None:
    """Grava status/observação (status_leads.csv) e correções de dados (CSV do lead)."""
    mudancas = diferencas_dados(editado, original)
    origem_por_id = dict(zip(filtrado["osm_id"], filtrado["arquivo_origem"]))

    alterados_status = salvar_status(editado[["osm_id", "status", "observacao"]])
    resultado = aplicar_edicoes(mudancas, origem_por_id)

    if resultado.gravadas:
        recarregar_base_ativa()
    st.session_state["resumo_salvamento"] = {
        "status": alterados_status,
        "dados": resultado.gravadas,
        "erros": resultado.erros,
    }


def _mostrar_resumo_salvamento() -> None:
    resumo = st.session_state.pop("resumo_salvamento", None)
    if not resumo:
        return
    if resumo["status"] or resumo["dados"]:
        st.success(
            f"Salvo: {resumo['dados']} lead(s) corrigido(s) no CSV e "
            f"{resumo['status']} alteração(ões) de status/observação."
        )
    elif not resumo["erros"]:
        st.info("Nenhuma alteração para salvar.")
    for erro in resumo["erros"]:
        st.warning(f"Não gravado — {erro}")


def _configuracao_colunas() -> dict:
    link = st.column_config.LinkColumn
    texto = st.column_config.TextColumn
    return {
        "pontuacao": st.column_config.NumberColumn(
            "Score", width="small",
            help="Pontuação de oportunidade calculada pelas informações disponíveis; não é probabilidade de conversão.",
        ),
        "nome": texto("Nome", width="medium"),
        "nicho": texto("Nicho", width="medium"),
        "localidade": texto("Localidade", width="medium"),
        "status_site": texto("Situação do site", width="medium", help="Reflete os registros do OSM."),
        "telefone": texto("Telefone", width="medium"),
        "whatsapp_url": link("WhatsApp (tentar)", display_text="Abrir", width="small"),
        "instagram": link("Instagram", width="small"),
        "facebook": link("Facebook", width="small"),
        "email": texto("E-mail", width="medium"),
        "site": link("Site", width="small"),
        "google_url": link("Conferir", display_text="Google", width="small"),
        "osm_url": link("OpenStreetMap", display_text="OSM", width="small"),
        "endereco": texto("Endereço", width="large"),
        "distancia_km": st.column_config.NumberColumn(
            "Dist. ao centro (km)", format="%.2f", width="small",
            help="Distância em linha reta até o ponto central da consulta.",
        ),
        "gmn_nota": st.column_config.NumberColumn(
            "Nota Google", format="%.1f", width="small",
            help="Vem da Pesquisa avançada. Vazio = ainda não pesquisado.",
        ),
        "gmn_avaliacoes": st.column_config.NumberColumn("Aval. Google", format="%d", width="small"),
        "status": st.column_config.SelectboxColumn("Status", options=STATUS_LEAD, required=True, width="medium"),
        "observacao": texto("Observação", width="large"),
    }


def renderizar_tabela(filtrado: pd.DataFrame, limite: int, modelo: str) -> None:
    tabela = preparar_tabela(filtrado, limite, modelo)
    chave = hashlib.sha1("|".join(tabela["osm_id"].astype(str)).encode("utf-8")).hexdigest()[:12]

    editado = st.data_editor(
        tabela,
        column_order=ORDEM_COLUNAS,
        hide_index=True,
        width="stretch",
        key=f"editor_leads_{chave}",
        disabled=[c for c in ORDEM_COLUNAS if c not in EDITAVEIS_NA_TABELA],
        column_config=_configuracao_colunas(),
    )

    if len(filtrado) > len(tabela):
        st.caption(
            f"A tabela mostra os {len(tabela)} melhores de {len(filtrado)} leads filtrados. "
            "A exportação CSV inclui todos os leads filtrados."
        )

    col_botao, col_ajuda = st.columns([1, 3])
    if col_botao.button("Salvar alterações", type="primary", key=f"salvar_{chave}"):
        try:
            salvar_alteracoes(editado, tabela, filtrado)
        except OSError as erro:
            st.error(f"Não consegui gravar os arquivos: {erro}")
        else:
            st.rerun()
    col_ajuda.caption(
        "Edite nome, telefone, e-mail, site, redes, endereço, status e observação direto na tabela. "
        "As correções vão para o próprio CSV da coleta, sem nova coleta nem novo download; "
        "o original fica em `dados_osm/_backup`."
    )


def renderizar_exportacao(filtrado: pd.DataFrame, modelo: str) -> None:
    seu_nome = carregar_nome_vendedor() or "[seu nome]"
    mensagens = [texto_abordagem(linha, modelo, seu_nome) for _, linha in filtrado.iterrows()]
    links = coluna_whatsapp(filtrado, modelo, seu_nome)

    exportar = filtrado.drop(
        columns=["rede", "osm_url", "arquivo_origem", "editado_campos"], errors="ignore"
    ).assign(
        mensagem_pronta=mensagens,
        whatsapp_url=links.fillna("").astype(str).tolist(),
        fonte_dados=FONTE_DADOS,
    )
    csv = neutralizar_formulas(exportar).to_csv(index=False).encode("utf-8-sig")
    lugares = sorted({str(v).strip() for v in filtrado["localidade"] if str(v).strip()})

    st.download_button(
        "Baixar todos os leads filtrados (CSV)",
        data=csv,
        file_name=nome_exportacao(lugares),
        mime="text/csv",
        width="stretch",
    )


def renderizar_leads(filtrado: pd.DataFrame, filtros: dict, modelo: str) -> None:
    _mostrar_resumo_salvamento()

    if filtrado.empty:
        st.info("Nenhum lead corresponde aos filtros selecionados.")
        return

    st.caption(
        f"{len(filtrado)} lead(s) correspondem aos filtros, ordenados por pontuação e distância. "
        "A ausência de site no OpenStreetMap não garante que o negócio não tenha site: "
        "use o link do Google para conferir. O link de WhatsApp é só uma tentativa de contato."
    )
    renderizar_tabela(filtrado, filtros["limite"], modelo)
    st.divider()
    renderizar_exportacao(filtrado, modelo)
