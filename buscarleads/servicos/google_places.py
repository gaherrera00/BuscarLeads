"""Google Places API (New): busca do estabelecimento com TODOS os campos.

Por que ``X-Goog-FieldMask: *``: a cobrança é pelo maior nível entre os campos
pedidos. Como o app já paga o nível Enterprise (nota, site, telefone), pedir
tudo só sobe para "Enterprise + Atmosphere" (US$ 40 contra US$ 35 por 1.000
consultas) e traz horários, status, tipos, resumos, comodidades e avaliações.
Uma única chamada por lead; nada de segunda chamada de detalhes.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from difflib import SequenceMatcher

import requests

from buscarleads.constantes import COLUNAS_GOOGLE, chave_google
from buscarleads.normalizacao import normalizar_nome

URL_BUSCA = "https://places.googleapis.com/v1/places:searchText"
FIELD_MASK = "*"
RAIO_VIES_M = 500.0

SITUACOES = {
    "OPERATIONAL": "Operacional",
    "CLOSED_TEMPORARILY": "Fechado temporariamente",
    "CLOSED_PERMANENTLY": "Fechado permanentemente",
}
NIVEIS_PRECO = {
    "PRICE_LEVEL_FREE": "Grátis",
    "PRICE_LEVEL_INEXPENSIVE": "$",
    "PRICE_LEVEL_MODERATE": "$$",
    "PRICE_LEVEL_EXPENSIVE": "$$$",
    "PRICE_LEVEL_VERY_EXPENSIVE": "$$$$",
}
SERVICOS = {
    "delivery": "Delivery",
    "dineIn": "Consumo no local",
    "takeout": "Para viagem",
    "curbsidePickup": "Retirada na calçada",
    "reservable": "Aceita reserva",
    "outdoorSeating": "Área externa",
    "liveMusic": "Música ao vivo",
    "allowsDogs": "Aceita cães",
    "goodForChildren": "Bom para crianças",
    "goodForGroups": "Bom para grupos",
    "goodForWatchingSports": "Bom para ver esportes",
    "menuForChildren": "Cardápio infantil",
    "restroom": "Banheiro",
    "servesBreakfast": "Café da manhã",
    "servesBrunch": "Brunch",
    "servesLunch": "Almoço",
    "servesDinner": "Jantar",
    "servesCoffee": "Café",
    "servesDessert": "Sobremesa",
    "servesBeer": "Cerveja",
    "servesWine": "Vinho",
    "servesCocktails": "Drinques",
    "servesVegetarianFood": "Opção vegetariana",
}
PAGAMENTOS = {
    "acceptsCreditCards": "Cartão de crédito",
    "acceptsDebitCards": "Cartão de débito",
    "acceptsCashOnly": "Só dinheiro",
    "acceptsNfc": "NFC / aproximação",
}
ESTACIONAMENTOS = {
    "freeParkingLot": "Estacionamento gratuito",
    "paidParkingLot": "Estacionamento pago",
    "freeStreetParking": "Rua gratuita",
    "paidStreetParking": "Rua paga",
    "valetParking": "Manobrista",
    "freeGarageParking": "Garagem gratuita",
    "paidGarageParking": "Garagem paga",
}
ACESSIBILIDADES = {
    "wheelchairAccessibleParking": "Vaga acessível",
    "wheelchairAccessibleEntrance": "Entrada acessível",
    "wheelchairAccessibleRestroom": "Banheiro acessível",
    "wheelchairAccessibleSeating": "Assentos acessíveis",
}


@dataclass
class ResultadoGoogle:
    """status: ok | nao_encontrado | sem_chave | erro."""

    status: str
    dados: dict = field(default_factory=dict)
    erro: str = ""

    @property
    def cobrado(self) -> bool:
        """A API respondeu com sucesso, então a consulta conta na cota paga."""
        return self.status in ("ok", "nao_encontrado")


# ------------------------------------------------------------------ utilitários
def _texto(valor) -> str:
    """Campos de texto da API vêm como {"text": "...", "languageCode": "..."}."""
    if isinstance(valor, dict):
        return str(valor.get("text", "") or "")
    return "" if valor is None else str(valor)


def _marcados(origem, rotulos: dict) -> str:
    if not isinstance(origem, dict):
        return ""
    return ", ".join(nome for chave, nome in rotulos.items() if origem.get(chave) is True)


def distancia_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (lat1, lon1, lat2, lon2))
    a = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * 6371000.0 * math.asin(math.sqrt(a))


def similaridade(nome_a: str, nome_b: str) -> float:
    """0 a 1. Reconhece nomes contidos um no outro ("Padaria X" / "Padaria X Ltda")."""
    a, b = normalizar_nome(nome_a), normalizar_nome(nome_b)
    if not a or not b:
        return 0.0
    razao = SequenceMatcher(None, a, b).ratio()
    contido = 0.9 if (a in b or b in a) else 0.0
    ta, tb = set(a.split()), set(b.split())
    jaccard = len(ta & tb) / len(ta | tb)
    return round(max(razao, contido, jaccard), 3)


def _avaliar(lugar: dict, nome: str, lat: float, lon: float) -> tuple[float, float, float | None]:
    """(pontuação para ordenar, similaridade, distância em metros)."""
    sim = similaridade(nome, _texto(lugar.get("displayName")))
    local = lugar.get("location") or {}
    if "latitude" in local and "longitude" in local:
        dist = distancia_m(lat, lon, float(local["latitude"]), float(local["longitude"]))
        return sim - min(dist, 2000.0) / 2000.0 * 0.5, sim, dist
    return sim * 0.5, sim, None


def confianca(sim: float, dist: float | None) -> str:
    """Chance de o resultado do Google ser o mesmo estabelecimento do OpenStreetMap."""
    if sim >= 0.75 and dist is not None and dist <= 200:
        return "alta"
    if sim >= 0.9 or (sim >= 0.55 and dist is not None and dist <= 500):
        return "media"
    return "baixa"


def escolher_melhor(lugares: list[dict], nome: str, lat: float, lon: float):
    """O candidato mais provável (nome parecido e perto), não simplesmente o primeiro."""
    ranqueados = [(_avaliar(lugar, nome, lat, lon), lugar) for lugar in lugares]
    (_, sim, dist), lugar = max(ranqueados, key=lambda item: item[0][0])
    return lugar, sim, dist


# -------------------------------------------------------------- normalização
def _faixa_preco(faixa) -> str:
    if not isinstance(faixa, dict):
        return ""

    def valor(item):
        if not isinstance(item, dict) or "units" not in item:
            return ""
        return f"{item.get('currencyCode', '')} {item['units']}".strip()

    inicio, fim = valor(faixa.get("startPrice")), valor(faixa.get("endPrice"))
    return f"{inicio} – {fim}" if inicio and fim else inicio or fim


def _avaliacoes_texto(avaliacoes) -> str:
    linhas = []
    for item in avaliacoes if isinstance(avaliacoes, list) else []:
        if not isinstance(item, dict):
            continue
        autor = _texto((item.get("authorAttribution") or {}).get("displayName"))
        quando = item.get("relativePublishTimeDescription", "")
        corpo = _texto(item.get("text")) or _texto(item.get("originalText"))
        linhas.append(f"★{item.get('rating', '?')} {autor} ({quando}): {corpo}".strip())
    return " | ".join(linhas)


def _abertura(data) -> str:
    if not isinstance(data, dict) or not data.get("year"):
        return ""
    return f"{data.get('year')}-{int(data.get('month', 1)):02d}-{int(data.get('day', 1)):02d}"


def normalizar_lugar(lugar: dict, sim: float, dist: float | None) -> dict:
    """Achata a resposta da API nas colunas de ``COLUNAS_GOOGLE``."""
    horarios = lugar.get("regularOpeningHours") or {}
    links = lugar.get("googleMapsLinks") or {}
    local = lugar.get("location") or {}
    resumo_ia = lugar.get("generativeSummary") or {}
    resumo_aval = lugar.get("reviewSummary") or {}

    dados = {
        "gmn_status": "ok",
        "gmn_place_id": str(lugar.get("id", "")),
        "gmn_nome": _texto(lugar.get("displayName")),
        "gmn_endereco": str(lugar.get("formattedAddress", "")),
        "gmn_lat": local.get("latitude", ""),
        "gmn_lon": local.get("longitude", ""),
        "gmn_distancia_m": "" if dist is None else round(dist),
        "gmn_similaridade": sim,
        "gmn_confianca": confianca(sim, dist),
        "gmn_situacao": SITUACOES.get(str(lugar.get("businessStatus", "")), str(lugar.get("businessStatus", ""))),
        "gmn_tipo_principal": _texto(lugar.get("primaryTypeDisplayName")) or str(lugar.get("primaryType", "")),
        "gmn_tipos": ", ".join(lugar.get("types") or []),
        "gmn_nota": lugar.get("rating", ""),
        "gmn_avaliacoes": lugar.get("userRatingCount", ""),
        "gmn_site": str(lugar.get("websiteUri", "")),
        "gmn_telefone": str(lugar.get("nationalPhoneNumber", "")),
        "gmn_telefone_intl": str(lugar.get("internationalPhoneNumber", "")),
        "gmn_nivel_preco": NIVEIS_PRECO.get(str(lugar.get("priceLevel", "")), ""),
        "gmn_faixa_preco": _faixa_preco(lugar.get("priceRange")),
        "gmn_horario": " | ".join(horarios.get("weekdayDescriptions") or []),
        "gmn_resumo": _texto(lugar.get("editorialSummary")),
        "gmn_resumo_ia": _texto(resumo_ia.get("overview")) or _texto(resumo_ia.get("description")),
        "gmn_resumo_avaliacoes": _texto(resumo_aval.get("text")),
        "gmn_servicos": _marcados(lugar, SERVICOS),
        "gmn_pagamento": _marcados(lugar.get("paymentOptions"), PAGAMENTOS),
        "gmn_estacionamento": _marcados(lugar.get("parkingOptions"), ESTACIONAMENTOS),
        "gmn_acessibilidade": _marcados(lugar.get("accessibilityOptions"), ACESSIBILIDADES),
        "gmn_reviews": _avaliacoes_texto(lugar.get("reviews")),
        "gmn_url_maps": str(lugar.get("googleMapsUri") or links.get("placeUri") or ""),
        "gmn_url_avaliacoes": str(links.get("reviewsUri", "")),
        "gmn_fotos": len(lugar.get("photos") or []),
        "gmn_area_servico": "sim" if lugar.get("pureServiceAreaBusiness") else "",
        "gmn_abertura": _abertura(lugar.get("openingDate")),
        "gmn_json": json.dumps(lugar, ensure_ascii=False, separators=(",", ":")),
    }
    return {coluna: ("" if dados.get(coluna) is None else dados.get(coluna, "")) for coluna in COLUNAS_GOOGLE if coluna not in ("osm_id", "atualizado_em")}


def _mensagem_erro(resposta: requests.Response) -> str:
    try:
        erro = resposta.json().get("error", {})
    except ValueError:
        erro = {}
    detalhe = f"{erro.get('status', resposta.status_code)}: {erro.get('message', resposta.reason)}"
    dicas = {
        400: "A requisição foi recusada pelo Google.",
        401: "Chave de API inválida.",
        403: "Confira se a 'Places API (New)' está ativada no projeto, se o faturamento está ligado e se a chave não tem restrição que bloqueie este uso.",
        429: "Cota ou limite de taxa excedido.",
    }
    dica = dicas.get(resposta.status_code, "")
    return f"HTTP {resposta.status_code} — {detalhe}. {dica}".strip()


# ---------------------------------------------------------------------- busca
def buscar_lugar(
    nome: str,
    localidade: str,
    lat: float,
    lon: float,
    chave: str | None = None,
    sessao=requests,
) -> ResultadoGoogle:
    """Procura o estabelecimento no Google e devolve todos os dados disponíveis.

    Só deve ser chamada por ação explícita do usuário, nunca em massa.
    Devolve sempre um ``ResultadoGoogle``; nunca engole o motivo de uma falha.
    """
    chave = chave if chave is not None else chave_google()
    if not chave:
        return ResultadoGoogle("sem_chave", erro="Defina GOOGLE_PLACES_API_KEY no arquivo .env.")

    corpo = {"textQuery": f"{nome}, {localidade}", "languageCode": "pt-BR"}
    if lat == lat and lon == lon:  # descarta NaN
        corpo["locationBias"] = {
            "circle": {"center": {"latitude": lat, "longitude": lon}, "radius": RAIO_VIES_M}
        }

    try:
        resposta = sessao.post(
            URL_BUSCA,
            json=corpo,
            headers={
                "Content-Type": "application/json",
                "X-Goog-Api-Key": chave,
                "X-Goog-FieldMask": FIELD_MASK,
            },
            timeout=20,
        )
    except requests.RequestException as erro:
        return ResultadoGoogle("erro", erro=f"Falha de rede ao falar com o Google: {erro}")

    if resposta.status_code != 200:
        return ResultadoGoogle("erro", erro=_mensagem_erro(resposta))

    try:
        lugares = resposta.json().get("places") or []
    except ValueError:
        return ResultadoGoogle("erro", erro="Resposta do Google não é JSON válido.")

    if not lugares:
        return ResultadoGoogle("nao_encontrado", dados={"gmn_status": "nao_encontrado"})

    lugar, sim, dist = escolher_melhor(lugares, nome, lat, lon)
    return ResultadoGoogle("ok", dados=normalizar_lugar(lugar, sim, dist))
