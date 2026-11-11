"""Geocodificação (Nominatim) e coleta de estabelecimentos (Overpass)."""

from __future__ import annotations

import time
from datetime import datetime

import pandas as pd
import requests

from buscarleads.constantes import COLUNAS, NICHOS, NOMINATIM_URL, OVERPASS_URLS
from buscarleads.contato import cabecalhos
from buscarleads.normalizacao import (
    classificar,
    distancia_km,
    montar_endereco,
    normalizar_url,
    pontuar,
    processar_telefones,
    situacao_site,
    telefones_das_tags,
    url_social,
)

def geocodificar(localidade: str) -> dict:
    resposta = requests.get(
        NOMINATIM_URL,
        params={
            "q": localidade,
            "format": "jsonv2",
            "limit": 5,
            "countrycodes": "br",
        },
        headers=cabecalhos(),
        timeout=30,
    )
    resposta.raise_for_status()
    resultados = resposta.json()

    if not resultados:
        raise ValueError(f'Não encontrei "{localidade}". Tente "Cidade, SP".')

    lugar = next(
        (
            resultado
            for resultado in resultados
            if resultado.get("osm_type") == "relation"
            and resultado.get("category") in ("boundary", "place")
        ),
        None,
    ) or next(
        (
            resultado
            for resultado in resultados
            if resultado.get("osm_type") in ("relation", "way")
        ),
        resultados[0],
    )

    osm_id = int(lugar["osm_id"])
    area_id = {
        "relation": 3_600_000_000,
        "way": 2_400_000_000,
    }.get(lugar.get("osm_type"))

    return {
        "latitude": float(lugar["lat"]),
        "longitude": float(lugar["lon"]),
        "area_id": area_id + osm_id if area_id else None,
    }


def montar_consulta(grupos, area_id, lat, lon, raio_km) -> str:
    if raio_km is not None:
        cabecalho = "[out:json][timeout:120];"
        filtro = f"(around:{int(raio_km * 1000)},{lat},{lon})"
    elif area_id is None:
        raise ValueError(
            "Esse local não tem limite administrativo. Use o nome de uma "
            "cidade/bairro com estado ou a busca por raio."
        )
    else:
        cabecalho = f"[out:json][timeout:120];area({area_id})->.a;"
        filtro = "(area.a)"

    partes = [
        f'nwr["{chave}"~"^({valores})$"]["name"]{filtro};'
        for grupo in grupos
        for chave, valores in NICHOS[grupo]
    ]
    return f"{cabecalho}({''.join(partes)});out center tags;"


def _espera_retry(resposta, padrao: float) -> float:
    try:
        return min(float(resposta.headers.get("Retry-After", "")), 30.0)
    except (TypeError, ValueError):
        return padrao


def consultar_overpass(consulta: str) -> dict:
    ultimo_erro = "sem resposta"

    for rodada in range(3):
        for url in OVERPASS_URLS:
            try:
                resposta = requests.post(
                    url,
                    data={"data": consulta},
                    headers=cabecalhos(),
                    timeout=150,
                )

                if resposta.status_code == 429 or resposta.status_code >= 500:
                    ultimo_erro = f"{url} respondeu HTTP {resposta.status_code}"
                    time.sleep(_espera_retry(resposta, 2 * (rodada + 1)))
                    continue

                resposta.raise_for_status()
                dados = resposta.json()

                if "runtime error" in str(dados.get("remark", "")).lower():
                    raise RuntimeError(
                        "Overpass não concluiu a consulta. Tente um bairro, "
                        "menos nichos ou um raio menor."
                    )
                return dados

            except (requests.RequestException, ValueError) as erro:
                ultimo_erro = f"{url}: {erro}"

        if rodada < 2:
            time.sleep(5 * (rodada + 1))

    raise RuntimeError(
        f"Overpass indisponível após várias tentativas. Último erro: {ultimo_erro}"
    )


def coletar(localidade: str, raio_km, grupos) -> pd.DataFrame:
    try:
        lugar = geocodificar(localidade)
    except requests.RequestException as erro:
        raise RuntimeError(
            f"Nominatim indisponível ou recusou a consulta: {erro}"
        ) from erro

    consulta = montar_consulta(
        grupos,
        lugar["area_id"],
        lugar["latitude"],
        lugar["longitude"],
        raio_km,
    )
    dados = consultar_overpass(consulta)
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    linhas = []

    for elemento in dados.get("elements", []):
        tags = elemento.get("tags", {})
        centro = elemento.get("center", {})
        lat = elemento.get("lat", centro.get("lat"))
        lon = elemento.get("lon", centro.get("lon"))
        nome = (tags.get("name") or "").strip()

        if lat is None or lon is None or not nome:
            continue

        site = normalizar_url(tags.get("website") or tags.get("contact:website"))
        instagram = url_social(
            tags.get("contact:instagram") or tags.get("instagram"),
            "instagram.com",
        )
        facebook = url_social(
            tags.get("contact:facebook") or tags.get("facebook"),
            "facebook.com",
        )
        email = (tags.get("email") or tags.get("contact:email") or "").strip()

        bruto_tel, bruto_zap = telefones_das_tags(tags)
        telefone, whatsapp = processar_telefones(bruto_tel, explicito=bruto_zap)

        rede = bool(tags.get("brand:wikidata"))
        situacao = situacao_site(site, instagram, facebook)
        tipo = elemento.get("type", "")
        id_osm = elemento.get("id", "")

        linhas.append(
            {
                "nome": nome,
                "nicho": classificar(tags),
                "localidade": localidade.strip(),
                "endereco": montar_endereco(tags),
                "distancia_km": round(
                    distancia_km(
                        lugar["latitude"], lugar["longitude"], float(lat), float(lon)
                    ),
                    2,
                ),
                "site": site,
                "instagram": instagram,
                "facebook": facebook,
                "email": email,
                "telefone": telefone,
                "whatsapp_num": whatsapp,
                "status_site": situacao,
                "rede": rede,
                "pontuacao": pontuar(
                    situacao,
                    whatsapp,
                    telefone,
                    email,
                    instagram,
                    facebook,
                    rede,
                ),
                "osm_id": f"{tipo}/{id_osm}",
                "osm_url": f"https://www.openstreetmap.org/{tipo}/{id_osm}",
                "latitude": float(lat),
                "longitude": float(lon),
                "coletado_em": agora,
                "editado_em": "",
                "editado_campos": "",
            }
        )

    return pd.DataFrame(linhas, columns=COLUNAS)
