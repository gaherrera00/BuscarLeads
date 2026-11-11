"""Aba 3: pesquisa avançada (Google Places + concorrência), sob demanda.

Regras de gasto:
- cada lead só é consultado uma vez; o resultado é gravado no CSV na hora;
- leads já salvos são reaproveitados de graça, a menos que o usuário peça atualização;
- antes de clicar, a tela diz quantas consultas pagas serão feitas.
"""

from __future__ import annotations

import json
import time

import pandas as pd
import streamlit as st

from buscarleads.constantes import (
    DIAS_DADO_GOOGLE_ANTIGO,
    STATUS_PESQUISA_AVANCADA,
    chave_google,
    chave_serper,
)
from buscarleads.dados.concorrencia import chave_serp, entrada_valida, ler_serp_cache
from buscarleads.dados.google import idade_dados_dias, ler_enriquecido, salvar_enriquecido
from buscarleads.servicos.google_places import buscar_lugar
from buscarleads.servicos.serper import buscar_concorrencia

CUSTO_POR_CONSULTA = "US$ 0,04"
LIMITE_OPCOES = 2000


def _cidade(localidade: str) -> str:
    return str(localidade).split(",")[0].strip()


# ----------------------------------------------------------------- consulta
def executar_pesquisa(linhas: pd.DataFrame, atualizar: bool) -> dict:
    """Consulta os leads, grava cada resultado na hora e devolve o resumo da rodada."""
    cache = ler_enriquecido()
    resultados, barra = [], st.progress(0.0, "Consultando...")

    for indice, linha in enumerate(linhas.itertuples(), start=1):
        item = {"osm_id": linha.osm_id, "nome": linha.nome, "origem": "", "erro": ""}

        if linha.osm_id in cache and not atualizar:
            item["origem"] = "reaproveitado"
        else:
            r = buscar_lugar(
                linha.nome, linha.localidade, float(linha.latitude), float(linha.longitude)
            )
            if r.cobrado:
                salvar_enriquecido(linha.osm_id, r.dados)  # grava já: nada pago se perde
                item["origem"] = "nova" if r.status == "ok" else "nao_encontrado"
            else:
                item["origem"], item["erro"] = "erro", r.erro
                if r.status == "sem_chave":
                    resultados.append(item)
                    break

        if chave_serper():
            _, erro, consultou = buscar_concorrencia(linha.nicho, _cidade(linha.localidade))
            item["concorrencia_nova"] = consultou
            item["concorrencia_erro"] = erro

        resultados.append(item)
        barra.progress(indice / len(linhas), f"{indice}/{len(linhas)}")
        time.sleep(0.15)

    barra.empty()
    return {"itens": resultados}


# -------------------------------------------------------------------- ficha
def _json_bruto(registro: dict) -> dict:
    try:
        dados = json.loads(registro.get("gmn_json") or "{}")
    except ValueError:
        return {}
    return dados if isinstance(dados, dict) else {}


def _linha_link(rotulo: str, url: str) -> None:
    if url:
        st.markdown(f"[{rotulo}]({url})")


def mostrar_ficha(registro: dict, nome_osm: str, site_osm: str, nicho: str, localidade: str) -> None:
    """Tudo o que o Google devolveu para o lead, lido do CSV (sem custo)."""
    if registro.get("gmn_status") == "nao_encontrado":
        st.warning(
            f"O Google não encontrou **{nome_osm}** perto do ponto do OpenStreetMap. "
            "A consulta ficou salva; marque *Atualizar dados já salvos* para tentar de novo."
        )
        return

    bruto = _json_bruto(registro)
    confianca = registro.get("gmn_confianca", "")
    st.markdown(f"#### {registro.get('gmn_nome') or nome_osm}")
    st.caption(f"{registro.get('gmn_tipo_principal', '')} · {registro.get('gmn_endereco', '')}")

    if confianca == "baixa":
        st.warning(
            f"Casamento pouco confiável (nome parecido: {registro.get('gmn_similaridade')}, "
            f"a {registro.get('gmn_distancia_m')} m do ponto do OSM). Pode ser outro estabelecimento: "
            "confira antes de usar nota ou site. A mensagem personalizada ignora a nota neste caso."
        )
    else:
        st.caption(
            f"Confiança do casamento com o OSM: **{confianca}** "
            f"({registro.get('gmn_distancia_m')} m de distância)."
        )

    idade = idade_dados_dias(registro)
    if idade is not None and idade > DIAS_DADO_GOOGLE_ANTIGO:
        st.warning(
            f"Dados do Google consultados há {int(idade)} dias. Os termos do Google tratam esse "
            "conteúdo como temporário; considere atualizar."
        )
    else:
        st.caption(f"Consultado em {registro.get('atualizado_em', '')}.")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Nota", registro.get("gmn_nota") or "—")
    c2.metric("Avaliações", registro.get("gmn_avaliacoes") or "—")
    c3.metric("Situação", registro.get("gmn_situacao") or "—")
    c4.metric("Preço", registro.get("gmn_nivel_preco") or registro.get("gmn_faixa_preco") or "—")

    # O que importa para quem vende sites: o Google confirma a ausência de site?
    site_google = registro.get("gmn_site", "")
    if site_google:
        st.warning(f"O Google lista um site para este lead ({site_google}). Ele pode já ter site.")
    elif not site_osm:
        st.success("Nem o OpenStreetMap nem o Google listam site: lead forte para oferta de site.")
    else:
        st.info("O Google não lista site, mas o OpenStreetMap tem um registro.")

    with st.expander("Contato e links", expanded=True):
        st.write(f"**Telefone:** {registro.get('gmn_telefone') or '—'}  ·  {registro.get('gmn_telefone_intl') or ''}")
        _linha_link("Abrir no Google Maps", registro.get("gmn_url_maps", ""))
        _linha_link("Ver avaliações no Google", registro.get("gmn_url_avaliacoes", ""))
        if registro.get("gmn_area_servico"):
            st.caption("Negócio que atende na casa do cliente (sem endereço público).")
        if registro.get("gmn_abertura"):
            st.caption(f"Abertura prevista/registrada: {registro['gmn_abertura']}")

    if registro.get("gmn_horario"):
        with st.expander("Horário de funcionamento"):
            for linha in registro["gmn_horario"].split(" | "):
                st.write(linha)

    resumos = [
        ("Resumo do Google", registro.get("gmn_resumo", "")),
        ("Resumo por IA do Google", registro.get("gmn_resumo_ia", "")),
        ("O que dizem as avaliações (IA)", registro.get("gmn_resumo_avaliacoes", "")),
    ]
    if any(texto for _, texto in resumos):
        with st.expander("Sobre o lugar"):
            for titulo, texto in resumos:
                if texto:
                    st.markdown(f"**{titulo}**  \n{texto}")

    extras = [
        ("Serviços", registro.get("gmn_servicos", "")),
        ("Pagamento", registro.get("gmn_pagamento", "")),
        ("Estacionamento", registro.get("gmn_estacionamento", "")),
        ("Acessibilidade", registro.get("gmn_acessibilidade", "")),
        ("Tipos", registro.get("gmn_tipos", "")),
    ]
    if any(texto for _, texto in extras):
        with st.expander("Comodidades e tipos"):
            for titulo, texto in extras:
                if texto:
                    st.write(f"**{titulo}:** {texto}")

    avaliacoes = bruto.get("reviews") or []
    if avaliacoes:
        with st.expander(f"Avaliações recentes ({len(avaliacoes)})"):
            for item in avaliacoes:
                autor = ((item.get("authorAttribution") or {}).get("displayName")) or "Anônimo"
                corpo = ((item.get("text") or {}).get("text")) or ""
                st.markdown(f"**★{item.get('rating', '?')}** — {autor} · {item.get('relativePublishTimeDescription', '')}")
                if corpo:
                    st.caption(corpo)

    concorrencia = ler_serp_cache().get(chave_serp(nicho, _cidade(localidade)))
    if entrada_valida(concorrencia):
        with st.expander("Concorrência no Google"):
            st.write(
                f"Busca “{nicho} em {_cidade(localidade)}”: "
                f"{concorrencia['concorrentes_com_site']} com site entre os "
                f"{concorrencia['total_concorrentes']} primeiros resultados."
            )
            if concorrencia.get("melhor_concorrente"):
                st.write(
                    f"Melhor posicionado: **{concorrencia['melhor_concorrente']}** "
                    f"({concorrencia.get('melhor_concorrente_link', '')})"
                )

    with st.expander("Resposta completa da API (tudo que o Google devolveu)"):
        st.json(bruto if bruto else {"aviso": "sem JSON salvo"})


# ------------------------------------------------------------------- resultado
def _mostrar_resultado_rodada(base: pd.DataFrame) -> None:
    rodada = st.session_state.get("pesquisa_resultado")
    if not rodada:
        return
    itens = rodada["itens"]
    contagem = pd.Series([i["origem"] for i in itens]).value_counts().to_dict()

    st.success(
        f"Consulta concluída: {contagem.get('nova', 0)} nova(s) · "
        f"{contagem.get('reaproveitado', 0)} reaproveitada(s) do CSV · "
        f"{contagem.get('nao_encontrado', 0)} não encontrada(s) · {contagem.get('erro', 0)} com erro."
    )
    for item in itens:
        if item["erro"]:
            st.error(f"**{item['nome']}** — {item['erro']}")
        if item.get("concorrencia_erro"):
            st.warning(f"**{item['nome']}** (concorrência) — {item['concorrencia_erro']}")

    por_id = base.drop_duplicates("osm_id").set_index("osm_id")
    registros = ler_enriquecido()
    for item in itens:
        registro = registros.get(item["osm_id"])
        if item["origem"] == "erro" or not registro or item["osm_id"] not in por_id.index:
            continue
        lead = por_id.loc[item["osm_id"]]
        with st.container(border=True):
            mostrar_ficha(registro, lead["nome"], lead["site"], lead["nicho"], lead["localidade"])

    if st.button("Fechar resultados desta consulta", key="fechar_rodada"):
        st.session_state.pop("pesquisa_resultado")
        st.rerun()


def _selecionar_leads(filtrado: pd.DataFrame, cache: dict):
    """Escolha dos leads. Devolve (linhas_selecionadas, atualizar)."""
    qualquer = st.checkbox(
        "Permitir qualquer status",
        help=f"Por padrão só {', '.join(STATUS_PESQUISA_AVANCADA)}: cada consulta é paga.",
        key="pesq_qualquer_status",
    )
    candidatos = filtrado if qualquer else filtrado[filtrado["status"].isin(STATUS_PESQUISA_AVANCADA)]
    if candidatos.empty:
        st.info(
            f"Nenhum lead com status {', '.join(STATUS_PESQUISA_AVANCADA)} nos filtros atuais. "
            "Mude o status na aba Leads ou marque *Permitir qualquer status*."
        )
        return candidatos.iloc[0:0], False

    candidatos = candidatos.head(LIMITE_OPCOES)
    rotulos = {
        linha.osm_id: f"{linha.nome} — {linha.localidade}"
        + (" ✓ salvo" if linha.osm_id in cache else "")
        for linha in candidatos.itertuples()
    }
    ids = st.multiselect(
        "Leads para pesquisar", list(rotulos), format_func=rotulos.get, key="sel_pesquisa"
    )
    atualizar = st.checkbox(
        "Atualizar dados já salvos (gera nova cobrança)", key="pesq_atualizar",
        help="Sem isto, leads com ✓ salvo são lidos do CSV, sem custo.",
    )
    return candidatos[candidatos["osm_id"].isin(ids)], atualizar


def renderizar_pesquisa(base: pd.DataFrame, filtrado: pd.DataFrame) -> None:
    st.subheader("Pesquisa avançada")
    st.caption(
        "Traz do Google Places tudo o que a API oferece (nota, avaliações, horários, status, "
        "tipos, resumos, comodidades, links) e a concorrência no Google. "
        "Cada lead é consultado uma vez e fica salvo no CSV."
    )

    if not chave_google() and not chave_serper():
        st.warning("Defina GOOGLE_PLACES_API_KEY e/ou SERPER_API_KEY no arquivo .env para habilitar esta função.")
        return

    _mostrar_resultado_rodada(base)

    cache = ler_enriquecido()
    selecionados, atualizar = _selecionar_leads(filtrado, cache)

    novos = int(sum(1 for i in selecionados["osm_id"] if atualizar or i not in cache))
    reaproveitados = len(selecionados) - novos
    if len(selecionados):
        st.info(
            f"{novos} consulta(s) paga(s) ao Google (até {CUSTO_POR_CONSULTA} cada, "
            f"após as 1.000 gratuitas do mês) · {reaproveitados} lido(s) do CSV sem custo."
        )

    if st.button("🔍 Puxar informações", type="primary", disabled=len(selecionados) == 0, key="btn_puxar"):
        st.session_state["pesquisa_resultado"] = executar_pesquisa(selecionados, atualizar)
        st.rerun()

    st.divider()
    st.markdown("##### Dados já salvos")
    salvos = base[base["gmn_status"].isin(["ok", "nao_encontrado"])].drop_duplicates("osm_id")
    if salvos.empty:
        st.caption("Ainda não há leads pesquisados nesta base.")
        return
    rotulos = {linha.osm_id: f"{linha.nome} — {linha.localidade}" for linha in salvos.itertuples()}
    escolhido = st.selectbox("Ver ficha de um lead pesquisado", list(rotulos), format_func=rotulos.get, key="ficha_salva")
    lead = salvos.set_index("osm_id").loc[escolhido]
    mostrar_ficha(ler_enriquecido()[escolhido], lead["nome"], lead["site"], lead["nicho"], lead["localidade"])
