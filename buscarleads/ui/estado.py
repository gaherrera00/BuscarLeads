"""Estado da sessão: base carregada, abertura automática e execução da busca."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from buscarleads.constantes import NICHOS, STATUS_LEAD
from buscarleads.contato import (
    carregar_ultima_busca,
    salvar_ultima_busca,
)
from buscarleads.dados.arquivos import migrar_nomes_legados
from buscarleads.dados.google import mesclar_enriquecimento
from buscarleads.dados.leads import (
    base_vazia,
    carregar_base,
    carregar_ultimo_arquivo,
)
from buscarleads.dados.status import ler_status

MODO_AREA = "Área inteira (limite administrativo)"
MODO_RAIO = "Raio a partir do centro"


def _guardar_base(base, localidades, raio_km, grupos, origens) -> None:
    st.session_state.update(
        base=base,
        rotulo="; ".join(localidades),
        origens=origens,
        busca_ativa={"localidades": list(localidades), "raio_km": raio_km, "grupos": grupos},
        assinatura=(
            None
            if grupos is None
            else (tuple(localidades), raio_km, tuple(sorted(grupos)))
        ),
    )


def _definir_controles(localidades, raio_km, grupos) -> None:
    """Preenche a barra lateral com a busca aberta. Só vale antes de os widgets existirem."""
    st.session_state["busca_localidades"] = "; ".join(localidades)
    st.session_state["busca_modo"] = MODO_AREA if raio_km is None else MODO_RAIO
    if raio_km is not None:
        st.session_state["busca_raio"] = int(raio_km)
    validos = [grupo for grupo in (grupos or []) if grupo in NICHOS]
    if validos:
        st.session_state["busca_nichos"] = validos


def iniciar_sessao() -> None:
    """Na primeira renderização, abre o CSV mais recente sem acessar a internet.

    Assim o dashboard já aparece preenchido ao abrir o site. Primeiro tenta a
    última busca feita pelo usuário; se não houver, o arquivo mais novo da pasta.
    """
    if st.session_state.get("_sessao_iniciada"):
        return
    st.session_state["_sessao_iniciada"] = True
    migrar_nomes_legados()

    ultima = carregar_ultima_busca()
    if ultima:
        origens: dict = {}
        base, _, _ = carregar_base(
            ultima["localidades"],
            ultima.get("raio_km"),
            ultima.get("grupos"),
            atualizar=False,
            ttl_dias=None,
            origens=origens,
            somente_cache=True,
        )
        if not base.empty:
            _guardar_base(base, ultima["localidades"], ultima.get("raio_km"), ultima.get("grupos"), origens)
            _definir_controles(ultima["localidades"], ultima.get("raio_km"), ultima.get("grupos"))
            return

    aberto = carregar_ultimo_arquivo()
    if aberto:
        base, localidade, _ = aberto
        _guardar_base(base, [localidade], None, None, {localidade: "cache"})
        _definir_controles([localidade], None, None)


def executar_busca(localidades, raio_km, grupos, ttl, atualizar) -> None:
    """Botão "Buscar / carregar base": usa o cache mais recente ou coleta de novo."""
    barra = st.progress(0.0, text="Iniciando busca...")
    origens: dict = {}
    try:
        nova, falhas, _ = carregar_base(
            localidades,
            raio_km,
            grupos,
            atualizar,
            ttl,
            lambda fracao, texto: barra.progress(fracao, text=texto),
            origens=origens,
        )
    except Exception as erro:  # a interface precisa sobreviver a qualquer falha de coleta
        nova, falhas = None, [("(busca)", str(erro))]
    finally:
        barra.empty()

    falhou_tudo = nova is None or len(falhas) >= len(localidades)
    st.session_state.update(falhas=falhas, busca_falhou=falhou_tudo)
    if not falhou_tudo:
        _guardar_base(nova, localidades, raio_km, grupos, origens)
        salvar_ultima_busca(localidades, raio_km, grupos)
    else:
        st.session_state["origens"] = origens


def recarregar_base_ativa() -> None:
    """Relê do disco os mesmos CSVs, depois de uma correção gravada."""
    ativa = st.session_state.get("busca_ativa")
    if not ativa:
        return
    if ativa["grupos"] is None:  # base aberta pelo "último arquivo"
        aberto = carregar_ultimo_arquivo()
        if aberto:
            st.session_state["base"] = aberto[0]
        return
    base, _, _ = carregar_base(
        ativa["localidades"], ativa["raio_km"], ativa["grupos"], False, None, somente_cache=True
    )
    if not base.empty:
        st.session_state["base"] = base


def montar_base() -> pd.DataFrame:
    """Base atual com status/observação e dados do Google já mesclados (tudo local)."""
    bruta = st.session_state.get("base")
    if bruta is None:
        base = base_vazia().assign(status="", observacao="")
    else:
        estados = ler_status()
        base = bruta.assign(
            status=bruta["osm_id"].map(lambda i: estados.get(i, {}).get("status", "Novo")),
            observacao=bruta["osm_id"].map(lambda i: estados.get(i, {}).get("observacao", "")),
        )
        base["status"] = base["status"].where(base["status"].isin(STATUS_LEAD), "Novo")
    return mesclar_enriquecimento(base)
