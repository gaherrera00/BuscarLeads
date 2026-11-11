"""Concorrência via Serper: quem aparece no Google para "{nicho} em {cidade}"."""

from __future__ import annotations

import re
from urllib.parse import urlparse

import requests

from buscarleads.constantes import chave_serper
from buscarleads.dados.concorrencia import (
    chave_serp,
    entrada_valida,
    ler_serp_cache,
    parece_artigo,
    salvar_serp_cache,
)

URL_SERPER = "https://google.serper.dev/search"

# Diretórios, redes e portais: aparecem na busca mas não são concorrentes diretos.
DOMINIOS_GENERICOS = (
    "instagram.com", "facebook.com", "ifood.com.br", "google.com", "linktr.ee",
    "tripadvisor.com", "yelp.com", "guiamais.com.br", "youtube.com", "wikipedia.org",
    "reclameaqui.com.br", "olx.com.br", "mercadolivre.com.br", "apontador.com.br",
    "solutudo.com.br", "telelistas.net", "g1.globo.com", "tiktok.com", "linkedin.com",
)


def _limpar_titulo(titulo: str) -> str:
    """'Oficina X - Rua Y | Google' -> 'Oficina X'."""
    return re.split(r"\s[-|–—]\s", titulo or "")[0].strip()[:70]


def _eh_concorrente(item: dict) -> bool:
    link = item.get("link", "")
    return not any(d in link for d in DOMINIOS_GENERICOS) and not parece_artigo(item.get("title", ""))


def buscar_concorrencia(nicho: str, cidade: str, chave: str | None = None, sessao=requests):
    """Devolve (dados, erro, consultou_api).

    Reaproveita o cache por nicho+cidade: uma chamada serve a todos os leads do
    par. Uma resposta sem resultados também é guardada, para não pagar de novo.
    """
    chave_api = chave if chave is not None else chave_serper()
    if not chave_api:
        return {}, "Defina SERPER_API_KEY no arquivo .env.", False

    chave_cache = chave_serp(nicho, cidade)
    existente = ler_serp_cache().get(chave_cache)
    if entrada_valida(existente):
        return existente, "", False

    try:
        resposta = sessao.post(
            URL_SERPER,
            json={"q": f"{nicho} em {cidade}", "gl": "br", "hl": "pt-br", "num": 10},
            headers={"X-API-KEY": chave_api, "Content-Type": "application/json"},
            timeout=20,
        )
        resposta.raise_for_status()
        organicos = resposta.json().get("organic", [])
    except requests.RequestException as erro:
        return {}, f"Falha ao consultar o Serper: {erro}", False
    except ValueError:
        return {}, "Resposta do Serper não é JSON válido.", False

    concorrentes = [item for item in organicos if _eh_concorrente(item)]
    melhor = concorrentes[0] if concorrentes else {}
    dados = {
        "concorrentes_com_site": str(len(concorrentes)),
        "total_concorrentes": str(len(organicos)),
        "melhor_concorrente": _limpar_titulo(melhor.get("title", "")),
        "melhor_concorrente_link": urlparse(melhor.get("link", "")).netloc.removeprefix("www."),
    }
    salvar_serp_cache(chave_cache, dados)
    return ler_serp_cache()[chave_cache], "", True
