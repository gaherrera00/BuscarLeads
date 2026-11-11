"""Blocos visuais reutilizados em mais de uma aba."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from buscarleads.normalizacao import tem_telefone_valido


def metricas_leads(df: pd.DataFrame) -> None:
    colunas = st.columns(5)
    colunas[0].metric("Leads filtrados", len(df))
    colunas[1].metric(
        "Sem site / só rede social",
        int(df["status_site"].isin(["Sem site", "Só rede social"]).sum()),
        help="Ausência de registro de site no OpenStreetMap não comprova que o estabelecimento não tenha site.",
    )
    colunas[2].metric(
        "WhatsApp para tentar",
        int((df["whatsapp_tentativa"] != "").sum()),
        help=(
            f"{int((df['whatsapp_num'] != '').sum())} são celulares; o restante é telefone fixo "
            "(WhatsApp Business também roda em linha fixa). Um número encontrado não confirma conta ativa."
        ),
    )
    colunas[3].metric(
        "Já contatados", int((df["status"] != "Novo").sum()), help="Leads com status diferente de Novo."
    )
    colunas[4].metric(
        "Com dados do Google",
        int((df["gmn_status"] == "ok").sum()),
        help="Leads já consultados na Pesquisa avançada (dados salvos, sem nova cobrança).",
    )


def tipo_contato(df: pd.DataFrame) -> pd.Series:
    """Classifica cada lead pelo melhor canal de contato disponível."""
    tem_email = df["email"] != ""
    tem_rede = (df["instagram"] != "") | (df["facebook"] != "")
    tem_fixo = df["telefone"].map(tem_telefone_valido)
    tem_zap = df["whatsapp_num"] != ""
    return pd.Series(
        [
            "Celular (WhatsApp)" if z
            else "Só telefone fixo" if t
            else "Só e-mail" if e and not r
            else "Só rede social" if r
            else "Sem contato"
            for z, t, e, r in zip(tem_zap, tem_fixo, tem_email, tem_rede)
        ],
        index=df.index,
    )


def mostrar_funil(base: pd.DataFrame, filtrado: pd.DataFrame) -> None:
    """Mostra onde os leads da base se perdem até chegar à tabela."""
    if base.empty:
        return
    com_contato = (
        (base["telefone"] != "") | (base["email"] != "")
        | (base["instagram"] != "") | (base["facebook"] != "")
    )
    zap_filtrado = int((filtrado["whatsapp_tentativa"] != "").sum()) if not filtrado.empty else 0
    etapas = pd.DataFrame(
        {
            "Etapa": [
                "1. Base coletada",
                "2. Com algum contato no OSM",
                "3. Com telefone",
                "4. Com celular",
                "4b. Com celular ou fixo (WhatsApp p/ tentar)",
                "5. Após os filtros atuais",
                "6. Filtrados com WhatsApp p/ tentar",
            ],
            "Leads": [
                len(base),
                int(com_contato.sum()),
                int((base["telefone"] != "").sum()),
                int((base["whatsapp_num"] != "").sum()),
                int((base["whatsapp_tentativa"] != "").sum()),
                len(filtrado),
                zap_filtrado,
            ],
        }
    )
    etapas["% da base"] = (etapas["Leads"] / max(len(base), 1) * 100).round(1)

    st.subheader("Funil de contatos")
    st.caption(
        "Poucos estabelecimentos têm telefone cadastrado no OpenStreetMap; "
        "por isso a base inteira é muito maior que o total contatável."
    )
    st.dataframe(etapas, hide_index=True, width="stretch")
    st.bar_chart(tipo_contato(base).value_counts().rename_axis("Tipo de contato").rename("Leads"))


def mostrar_distribuicao(titulo: str, serie: pd.Series, mensagem_vazia: str) -> None:
    st.subheader(titulo)
    if serie.empty:
        st.info(mensagem_vazia)
        return
    st.bar_chart(serie.value_counts().rename_axis("Categoria").rename("Quantidade"))


def formatar_origem(origens: dict) -> str:
    valores = set(origens.values())
    if not valores or valores == {"falha"}:
        return ""
    if valores <= {"cache"}:
        return "Base carregada do cache mais recente."
    if valores <= {"cache antigo"}:
        return (
            "Base carregada de um arquivo anterior à organização dos CSVs: nichos e raio "
            "daquela coleta não ficaram registrados. Use Forçar nova coleta se a busca mudou."
        )
    if valores <= {"nova coleta"}:
        return "Base atualizada por nova coleta."
    if "cache antigo" in valores:
        return (
            "Parte da base veio de um arquivo antigo, sem registro de nicho e raio. "
            "Use Forçar nova coleta se a busca mudou."
        )
    return "Base combinada: parte do cache mais recente e parte de nova coleta."
