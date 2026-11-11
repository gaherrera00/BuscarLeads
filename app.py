# Instalação: pip install "streamlit>=1.50" pandas requests
# Execução:   streamlit run app.py
#
# Opcional: defina BUSCA_LEADS_CONTATO no ambiente. Se não definir,
# o app pedirá um e-mail e o salvará localmente em dados_osm/config.json.

from __future__ import annotations

from datetime import datetime
import hashlib
import json
import math
import os
import re
import time
import unicodedata
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, urlparse

import pandas as pd
import requests
import streamlit as st


# ───────────────────────── configuração e constantes ─────────────────────────


APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "dados_osm"
DATA_DIR.mkdir(exist_ok=True)

STATUS_FILE = DATA_DIR / "status_leads.csv"
CONFIG_FILE = DATA_DIR / "config.json"

FONTE_DADOS = (
    "© OpenStreetMap contributors - ODbL 1.0 - "
    "https://www.openstreetmap.org/copyright"
)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]

NICHOS = {
    "Alimentação": [
        ("amenity", "restaurant|cafe|fast_food|bar|pub|ice_cream"),
        ("shop", "bakery|confectionery|butcher|greengrocer|deli|pastry"),
    ],
    "Beleza e estética": [
        ("shop", "hairdresser|barber|beauty|cosmetics|massage|tattoo"),
    ],
    "Saúde": [
        ("amenity", "dentist|clinic|doctors|veterinary"),
        (
            "healthcare",
            "dentist|doctor|clinic|psychotherapist|physiotherapist|optometrist",
        ),
        ("shop", "optician"),
    ],
    "Serviços profissionais": [
        (
            "office",
            "lawyer|accountant|estate_agent|insurance|architect|financial|"
            "notary|consulting",
        ),
    ],
    "Automotivo": [
        ("shop", "car_repair|car|tyres|car_parts"),
        ("amenity", "car_wash"),
    ],
    "Pet": [("shop", "pet|pet_grooming")],
    "Fitness e educação": [
        ("leisure", "fitness_centre|sports_centre|dance"),
        ("amenity", "driving_school|language_school|music_school|prep_school"),
    ],
    "Varejo": [
        (
            "shop",
            "clothes|shoes|jewelry|gift|florist|books|furniture|electronics|"
            "mobile_phone|variety_store|bag|boutique",
        ),
    ],
    "Mercados": [("shop", "supermarket|convenience")],
}
GRUPOS_PADRAO = [grupo for grupo in NICHOS if grupo != "Mercados"]

ROTULOS = {
    "restaurant": "Restaurante",
    "cafe": "Cafeteria",
    "fast_food": "Lanchonete",
    "bar": "Bar",
    "pub": "Pub",
    "ice_cream": "Sorveteria",
    "bakery": "Padaria",
    "confectionery": "Doceria",
    "butcher": "Açougue",
    "greengrocer": "Hortifruti",
    "deli": "Delicatessen",
    "pastry": "Confeitaria",
    "hairdresser": "Salão de beleza",
    "barber": "Barbearia",
    "beauty": "Estética / beleza",
    "cosmetics": "Cosméticos",
    "massage": "Massagem",
    "tattoo": "Tatuagem",
    "dentist": "Dentista",
    "clinic": "Clínica",
    "doctors": "Consultório médico",
    "doctor": "Consultório médico",
    "veterinary": "Veterinário",
    "psychotherapist": "Psicologia",
    "physiotherapist": "Fisioterapia",
    "optometrist": "Ótica",
    "optician": "Ótica",
    "lawyer": "Advocacia",
    "accountant": "Contabilidade",
    "estate_agent": "Imobiliária",
    "insurance": "Seguros",
    "architect": "Arquitetura",
    "financial": "Serviços financeiros",
    "notary": "Cartório",
    "consulting": "Consultoria",
    "car_repair": "Oficina",
    "car": "Veículos",
    "tyres": "Pneus",
    "car_parts": "Autopeças",
    "car_wash": "Lava-rápido",
    "pet": "Pet shop",
    "pet_grooming": "Banho e tosa",
    "fitness_centre": "Academia",
    "sports_centre": "Centro esportivo",
    "dance": "Escola de dança",
    "driving_school": "Autoescola",
    "language_school": "Escola de idiomas",
    "music_school": "Escola de música",
    "prep_school": "Cursinho",
    "clothes": "Roupas",
    "shoes": "Calçados",
    "jewelry": "Joalheria",
    "gift": "Presentes",
    "florist": "Floricultura",
    "books": "Livraria",
    "furniture": "Móveis",
    "electronics": "Eletrônicos",
    "mobile_phone": "Celulares",
    "variety_store": "Variedades",
    "bag": "Bolsas",
    "boutique": "Boutique",
    "supermarket": "Supermercado",
    "convenience": "Mercadinho",
}

REDES = (
    "instagram.com",
    "facebook.com",
    "fb.com",
    "linktr.ee",
    "wa.me",
    "whatsapp.com",
    "bio.link",
    "beacons.ai",
    "tiktok.com",
    "ifood.com.br",
    "youtube.com",
)

DDDS = {
    *range(11, 20),
    21,
    22,
    24,
    27,
    28,
    31,
    32,
    33,
    34,
    35,
    37,
    38,
    *range(41, 50),
    51,
    53,
    54,
    55,
    *range(61, 70),
    71,
    73,
    74,
    75,
    77,
    79,
    *range(81, 90),
    *range(91, 100),
}

CHAVES_TEL = (
    "phone",
    "contact:phone",
    "mobile",
    "contact:mobile",
    "whatsapp",
    "contact:whatsapp",
)

STATUS_LEAD = [
    "Novo",
    "Contatado",
    "Respondeu",
    "Reunião marcada",
    "Fechado",
    "Descartado",
]
SITUACOES = ["Sem site", "Só rede social", "Com site"]

COLUNAS = [
    "nome",
    "nicho",
    "localidade",
    "endereco",
    "distancia_km",
    "site",
    "instagram",
    "facebook",
    "email",
    "telefone",
    "whatsapp_num",
    "status_site",
    "rede",
    "pontuacao",
    "osm_id",
    "osm_url",
    "latitude",
    "longitude",
    "coletado_em",
]

#CONFIGURACAO DE MENSAGENS
#HORARIOS
tempo = datetime.now().hour
hora = datetime.now().hour

if 5 <= hora < 12:
    MODELO_MSG = (
    "Bom Dia, tudo bem? Gostaria de saber se poderia falar com o responsável pelo {nome}, por gentileza."
)
elif 12 <= hora < 18:
        MODELO_MSG = (
    "Boa Tarde, tudo bem? Gostaria de saber se poderia falar com o responsável pelo {nome}, por gentileza."
)
else:
        MODELO_MSG = (
    "Boa Noite, tudo bem? Gostaria de saber se poderia falar com o responsável pelo {nome}, por gentileza."
)

CSS_TEMA = """
<style>
:root {
    color-scheme: dark;
}
.stApp {
    background: #111827;
    color: #F3F4F6;
}
[data-testid="stHeader"] {
    background: rgba(17, 24, 39, 0.92);
}
[data-testid="stSidebar"] {
    background: #17212f;
    border-right: 1px solid #374151;
}
[data-testid="stSidebar"] > div:first-child {
    padding-top: 1.2rem;
}
h1, h2, h3 {
    color: #F3F4F6;
    letter-spacing: -0.025em;
}
h1 {
    font-size: 2rem !important;
}
h2 {
    font-size: 1.35rem !important;
}
h3 {
    font-size: 1.05rem !important;
}
p, label, [data-testid="stCaptionContainer"] {
    color: #D1D5DB;
}
[data-testid="stMetric"] {
    background: #1F2937;
    border: 1px solid #374151;
    border-radius: 12px;
    padding: 0.85rem 1rem;
}
[data-testid="stMetricValue"] {
    color: #F3F4F6;
}
[data-testid="stMetricLabel"] {
    color: #9CA3AF;
}
[data-testid="stExpander"] {
    border: 1px solid #374151;
    border-radius: 10px;
    background: #17212f;
}
div[data-baseweb="select"] > div,
div[data-baseweb="input"] > div,
div[data-baseweb="textarea"] > div {
    background: #1F2937;
    border-color: #4B5563;
}
input, textarea {
    color: #F3F4F6 !important;
}
button[kind="primary"] {
    background: #059669;
    border-color: #059669;
}
button[kind="primary"]:hover {
    background: #047857;
    border-color: #047857;
}
button:focus-visible, a:focus-visible, input:focus-visible {
    outline: 2px solid #34D399 !important;
    outline-offset: 2px;
}
[data-testid="stDataFrame"], [data-testid="stDataEditor"] {
    border: 1px solid #374151;
    border-radius: 10px;
}
hr {
    border-color: #374151;
}
</style>
"""


# ───────────────────────── contato e configuração ─────────────────────────


def carregar_contato() -> str:
    """A variável de ambiente tem prioridade sobre a configuração local."""
    contato_env = os.getenv("BUSCA_LEADS_CONTATO", "").strip()
    if contato_env:
        return contato_env

    try:
        configuracao = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        return str(configuracao.get("contato", "")).strip()
    except (OSError, ValueError, TypeError):
        return ""


def salvar_contato(contato: str) -> None:
    CONFIG_FILE.write_text(
        json.dumps(
            {"contato": contato.strip()},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def contato_configurado() -> bool:
    contato = carregar_contato()
    return bool(
        re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", contato)
        and not contato.endswith("@exemplo.com")
    )


def cabecalhos() -> dict:
    return {"User-Agent": f"BuscaLeadsStreamlit/2.1 ({carregar_contato()})"}


def exigir_contato() -> None:
    if not contato_configurado():
        raise RuntimeError("Configure um e-mail válido para habilitar novas coletas.")


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

    if col_salvar.button(
        "Salvar e-mail",
        type="primary",
        use_container_width=True,
    ):
        email = contato.strip()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            st.error("Informe um e-mail válido.")
        else:
            try:
                salvar_contato(email)
            except OSError as erro:
                st.error(f"Não foi possível salvar a configuração: {erro}")
            else:
                st.rerun()

    if col_continuar.button(
        "Continuar sem configurar",
        use_container_width=True,
    ):
        st.rerun()


def configurar_email_inicio() -> None:
    """Mostra o pop-up uma vez por sessão se ainda não houver e-mail válido."""
    if st.session_state.get("email_dialog_exibido"):
        return

    st.session_state["email_dialog_exibido"] = True
    if not contato_configurado():
        dialogo_email()


# ───────────────────────── utilidades e normalizações ─────────────────────────


def distancia_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    a = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * 6371.0 * math.asin(math.sqrt(a))


RE_CHAVE_TEL = re.compile(
    r"(^|[:_])(phone|mobile|whatsapp|telephone|telefone|celular|fone|tel|zap)"
    r"([:_]|\d|$)",
    re.IGNORECASE,
)
RE_CHAVE_ZAP = re.compile(r"(whatsapp|zap)", re.IGNORECASE)
RE_LINK_ZAP = re.compile(
    r"(?:wa\.me/|whatsapp\.com/send\?[^\s]*?phone=|whatsapp\.com/[^\s]*?phone=)\+?(\d{10,15})",
    re.IGNORECASE,
)
RE_FONE_TEXTO = re.compile(
    r"(?<!\d)(?:\+?55[\s.-]*)?\(?0?\d{2}\)?[\s.-]*9?\d{4}[\s.-]?\d{4}(?!\d)"
)


def _normalizar_telefone_br(parte: str, ddd_padrao: str = "") -> str:
    """Devolve DDD + número (só dígitos) se for telefone brasileiro válido.

    Aceita +55, zero de operadora (011), números sem DDD (se ``ddd_padrao``
    for informado) e celulares antigos sem o nono dígito. Rejeita 0800/0300.
    """
    digitos = re.sub(r"\D", "", parte)
    if digitos.startswith(("0800", "0300", "0500", "0900")):
        return ""

    internacional = parte.strip().startswith("+")
    if internacional:
        # Código de país explícito: só o +55 é aceito e o DDD é obrigatório.
        if not digitos.startswith("55"):
            return ""
        digitos = digitos[2:]
        ddd_padrao = ""
    elif digitos.startswith("55") and len(digitos) >= 12:
        digitos = digitos[2:]
    digitos = digitos.lstrip("0")

    # Sem DDD
    if ddd_padrao:
        if len(digitos) == 9 and digitos[0] == "9":
            digitos = ddd_padrao + digitos
        elif len(digitos) == 8 and digitos[0] in "2345":
            digitos = ddd_padrao + digitos
        elif len(digitos) == 8 and digitos[0] in "6789":
            digitos = ddd_padrao + "9" + digitos  # celular antigo sem o 9

    # Celular antigo com DDD mas sem o nono dígito: (11) 9876-5432
    if len(digitos) == 10 and digitos[2] in "6789":
        digitos = digitos[:2] + "9" + digitos[2:]

    if len(digitos) not in (10, 11) or int(digitos[:2]) not in DDDS:
        return ""

    movel = len(digitos) == 11 and digitos[2] == "9"
    fixo = len(digitos) == 10 and digitos[2] in "2345"
    return digitos if movel or fixo else ""


def _formatar(digitos: str) -> str:
    if len(digitos) == 11:
        return f"({digitos[:2]}) {digitos[2:7]}-{digitos[7:]}"
    return f"({digitos[:2]}) {digitos[2:6]}-{digitos[6:]}"


def processar_telefones(
    bruto: str, ddd_padrao: str = "", explicito: str = ""
) -> tuple[str, str]:
    """Retorna telefones formatados e o número de WhatsApp.

    ``explicito`` traz números cadastrados em tags de WhatsApp: valem como
    WhatsApp mesmo se forem fixos (WhatsApp Business roda em linha fixa).
    Fora isso, o WhatsApp é o primeiro celular válido.
    """
    itens, whatsapp, ddd_atual = [], "", ddd_padrao

    for texto_bruto, eh_zap in ((explicito, True), (bruto, False)):
        for parte in re.split(r"[;,/|]", texto_bruto or ""):
            original = parte.strip()
            if not original:
                continue

            digitos = _normalizar_telefone_br(original, ddd_atual)
            if not digitos:
                texto = original
            else:
                ddd_atual = digitos[:2]
                texto = _formatar(digitos)
                if eh_zap or len(digitos) == 11:
                    whatsapp = whatsapp or digitos

            if texto not in itens:
                itens.append(texto)

    return " / ".join(itens), whatsapp


def telefones_das_tags(tags: dict) -> tuple[str, str]:
    """Junta telefones de QUALQUER tag de telefone/WhatsApp do OSM.

    Retorna (telefones_gerais, telefones_declarados_como_whatsapp).
    Também extrai números de links wa.me / api.whatsapp.com e de textos livres.
    """
    gerais, zap = [], []

    for chave, valor in tags.items():
        if not valor or not RE_CHAVE_TEL.search(chave) or "fax" in chave.lower():
            continue
        (zap if RE_CHAVE_ZAP.search(chave) else gerais).append(str(valor))

    for chave in (
        "website", "contact:website", "url", "contact:url",
        "facebook", "contact:facebook", "instagram", "contact:instagram",
    ):
        for achado in RE_LINK_ZAP.findall(str(tags.get(chave, ""))):
            zap.append(achado)

    for chave in ("description", "note", "contact:description"):
        gerais.extend(RE_FONE_TEXTO.findall(str(tags.get(chave, ""))))

    return ";".join(gerais), ";".join(zap)


def primeiro_fixo(telefones: str) -> str:
    """Primeiro telefone fixo válido (DDD + 8 dígitos) de um texto já formatado.

    O WhatsApp Business também funciona em linha fixa, então vale a tentativa.
    """
    achado = re.search(r"\((\d{2})\) ([2-5]\d{3})-(\d{4})", str(telefones))
    return "".join(achado.groups()) if achado else ""


def ddd_predominante(telefones) -> str:
    """DDD mais comum entre os telefones já reconhecidos (usa como padrão)."""
    contagem: dict[str, int] = {}
    for valor in telefones:
        for parte in re.split(r"[;,/|]", str(valor)):
            digitos = _normalizar_telefone_br(parte)
            if digitos:
                contagem[digitos[:2]] = contagem.get(digitos[:2], 0) + 1
    return max(contagem, key=contagem.get) if contagem else ""


def url_valida(url: str) -> bool:
    parsed = urlparse(url or "")
    return (
        parsed.scheme in ("http", "https") and "." in parsed.netloc and " " not in url
    )


def normalizar_url(valor: str) -> str:
    valor = (valor or "").strip()
    if not valor:
        return ""

    candidato = (
        valor
        if re.match(r"^https?://", valor, re.I)
        else "https://" + valor.lstrip("/")
    )
    return candidato if url_valida(candidato) else valor


def url_social(valor: str, dominio: str) -> str:
    valor = (valor or "").strip()
    if not valor:
        return ""
    if valor.lower().startswith("http") or dominio in valor.lower():
        return normalizar_url(valor)
    return f"https://{dominio}/{valor.lstrip('@').strip('/')}"


def eh_rede_social(url: str) -> bool:
    host = urlparse(url).netloc.lower().removeprefix("www.")
    return any(host == rede or host.endswith("." + rede) for rede in REDES)


def situacao_site(site: str, instagram: str, facebook: str) -> str:
    if site and url_valida(site):
        return "Só rede social" if eh_rede_social(site) else "Com site"
    return "Só rede social" if instagram or facebook else "Sem site"


def tem_telefone_valido(telefone: str) -> bool:
    return bool(re.search(r"\(\d{2}\) \d{4,5}-\d{4}", telefone or ""))


def email_valido(email: str) -> bool:
    return any(
        re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", parte.strip())
        for parte in re.split(r"[;,]", email or "")
    )


def pontuar(
    situacao: str,
    whatsapp: str,
    telefone: str,
    email: str,
    instagram: str,
    facebook: str,
    rede: bool,
) -> int:
    pontos = {"Sem site": 3, "Só rede social": 3, "Com site": 0}.get(situacao, 0)
    if whatsapp:
        pontos += 2
    elif tem_telefone_valido(telefone):
        pontos += 1
    if instagram or facebook:
        pontos += 1
    if email_valido(email):
        pontos += 1
    if rede:
        pontos -= 4
    return pontos


def classificar(tags: dict) -> str:
    for chave in ("shop", "amenity", "office", "healthcare", "leisure"):
        valor = (tags.get(chave) or "").lower()
        if valor:
            return ROTULOS.get(valor, valor.replace("_", " ").capitalize())
    return "Outros"


def montar_endereco(tags: dict) -> str:
    rua = " ".join(
        parte
        for parte in (
            tags.get("addr:street", ""),
            tags.get("addr:housenumber", ""),
        )
        if parte
    )
    return ", ".join(
        parte
        for parte in (
            rua,
            tags.get("addr:suburb", ""),
            tags.get("addr:city", ""),
        )
        if parte
    )


# ───────────────────────── coleta OpenStreetMap ─────────────────────────


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
            }
        )

    return pd.DataFrame(linhas, columns=COLUNAS)


# ───────────────────────── cache e persistência ─────────────────────────


def caminho_cache(localidade: str, raio_km, grupos) -> Path:
    chave = (
        f"{localidade.strip().casefold()}|{raio_km}|"
        f"{','.join(sorted(grupos))}|v2"
    )
    nome = hashlib.sha256(chave.encode()).hexdigest()[:12]
    return DATA_DIR / f"leads_{nome}.csv"


def cache_valido(caminho: Path, ttl_dias: int) -> bool:
    return caminho.exists() and time.time() - caminho.stat().st_mtime < ttl_dias * 86400


def ler_csv(caminho: Path) -> pd.DataFrame:
    df = pd.read_csv(caminho, dtype=str, keep_default_na=False)
    if not {"nome", "osm_id"} <= set(df.columns):
        raise ValueError(f"{caminho.name} não tem as colunas esperadas")

    df = df.reindex(columns=COLUNAS, fill_value="")
    for coluna in ("distancia_km", "latitude", "longitude"):
        df[coluna] = pd.to_numeric(df[coluna], errors="coerce")

    df["rede"] = df["rede"].eq("True")

    # Reprocessa o telefone salvo: recupera números que versões anteriores
    # do parser rejeitaram (+55 011..., sem DDD etc.) sem nova coleta.
    ddd = ddd_predominante(df["telefone"])
    extra_zap = [
        ";".join(
            RE_LINK_ZAP.findall(" ".join((site, insta, face)))
        )
        for site, insta, face in zip(df["site"], df["instagram"], df["facebook"])
    ]
    reprocessado = [
        processar_telefones(valor, ddd, extra)
        for valor, extra in zip(df["telefone"], extra_zap)
    ]
    df["telefone"] = [tel for tel, _ in reprocessado]
    df["whatsapp_num"] = [
        zap or antigo for (_, zap), antigo in zip(reprocessado, df["whatsapp_num"])
    ]
    df["pontuacao"] = [
        pontuar(*campos)
        for campos in zip(
            df["status_site"],
            df["whatsapp_num"],
            df["telefone"],
            df["email"],
            df["instagram"],
            df["facebook"],
            df["rede"],
        )
    ]
    df["whatsapp_tentativa"] = [
        zap or primeiro_fixo(tel)
        for zap, tel in zip(df["whatsapp_num"], df["telefone"])
    ]
    return df


def gravar_csv(df: pd.DataFrame, caminho: Path) -> None:
    temporario = caminho.with_name(caminho.name + ".tmp")
    df.to_csv(temporario, index=False, encoding="utf-8-sig")
    os.replace(temporario, caminho)


def _normalizar_nome(nome: str) -> str:
    ascii_nome = unicodedata.normalize("NFKD", str(nome))
    ascii_nome = ascii_nome.encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", ascii_nome.casefold()).strip()


def deduplicar_aproximado(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    campos = ["site", "instagram", "facebook", "email", "telefone", "endereco"]
    completude = sum(
        (df[coluna].astype(str).str.strip() != "").astype(int) for coluna in campos
    )
    ordem = completude.sort_values(ascending=False, kind="stable").index

    por_telefone: dict[tuple[str, str], list[str]] = {}
    por_endereco: set[tuple[str, str]] = set()
    descartar = []

    for indice in ordem:
        nome = _normalizar_nome(df.at[indice, "nome"])
        telefone = str(df.at[indice, "telefone"]).strip()
        endereco = str(df.at[indice, "endereco"]).strip().casefold()

        if not nome:
            continue

        repetido = False
        if telefone:
            repetido = any(
                not endereco or not endereco_existente or endereco_existente == endereco
                for endereco_existente in por_telefone.get((nome, telefone), [])
            )

        if (
            not repetido
            and endereco
            and re.search(r"\d", endereco)
            and (nome, endereco) in por_endereco
        ):
            repetido = True

        if repetido:
            descartar.append(indice)
            continue

        if telefone:
            por_telefone.setdefault((nome, telefone), []).append(endereco)
        if endereco:
            por_endereco.add((nome, endereco))

    return df.drop(index=descartar)


def carregar_base(
    localidades,
    raio_km,
    grupos,
    atualizar,
    ttl_dias,
    progresso=None,
    origens=None,
):
    """Carrega cache ou coleta dados; origens é opcional e serve para feedback visual."""
    quadros, falhas = [], []
    consultou = False

    for indice, localidade in enumerate(localidades):
        if progresso:
            progresso(
                indice / len(localidades),
                f"Processando {localidade} ({indice + 1}/{len(localidades)})",
            )

        caminho = caminho_cache(localidade, raio_km, grupos)

        try:
            if cache_valido(caminho, ttl_dias) and not atualizar:
                try:
                    quadros.append(ler_csv(caminho))
                    if origens is not None:
                        origens[localidade] = "cache"
                    continue
                except (ValueError, OSError, pd.errors.ParserError):
                    pass

            exigir_contato()
            if consultou:
                time.sleep(1.1)
            consultou = True

            dados = coletar(localidade, raio_km, grupos)
            gravar_csv(dados, caminho)
            quadros.append(ler_csv(caminho))
            if origens is not None:
                origens[localidade] = "nova coleta"

        except (
            requests.RequestException,
            ValueError,
            RuntimeError,
            KeyError,
            OSError,
            pd.errors.ParserError,
        ) as erro:
            falhas.append((localidade, str(erro)))
            if origens is not None:
                origens[localidade] = "falha"

    if progresso:
        progresso(1.0, "Concluído")

    if not quadros:
        return pd.DataFrame(columns=COLUNAS + ["whatsapp_tentativa"]), falhas, 0

    base = pd.concat(quadros, ignore_index=True)
    base = base.drop_duplicates(subset="osm_id")
    quantidade_antes = len(base)
    base = deduplicar_aproximado(base)

    return base.reset_index(drop=True), falhas, quantidade_antes - len(base)


def ler_status() -> dict:
    if not STATUS_FILE.exists():
        return {}

    try:
        df = pd.read_csv(STATUS_FILE, dtype=str, keep_default_na=False)
        if not {"osm_id", "status", "observacao"} <= set(df.columns):
            raise ValueError("colunas inesperadas")
    except (ValueError, OSError, pd.errors.ParserError) as erro:
        backup = STATUS_FILE.with_name(
            f"status_leads_corrompido_{datetime.now():%Y%m%d_%H%M%S}.csv"
        )
        try:
            os.replace(STATUS_FILE, backup)
        except OSError:
            pass
        st.warning(
            f"Arquivo de status ilegível ({erro}). "
            f"Uma cópia foi guardada como {backup.name}."
        )
        return {}

    return {
        linha.osm_id: {
            "status": linha.status,
            "observacao": linha.observacao,
        }
        for linha in df.itertuples()
    }


def salvar_status(editado: pd.DataFrame) -> None:
    estados = ler_status()

    for linha in editado.itertuples():
        if linha.status == "Novo" and not str(linha.observacao).strip():
            estados.pop(linha.osm_id, None)
        else:
            estados[linha.osm_id] = {
                "status": linha.status,
                "observacao": str(linha.observacao or ""),
            }

    gravar_csv(
        pd.DataFrame(
            [
                {
                    "osm_id": chave,
                    **valor,
                    "atualizado_em": datetime.now().strftime("%Y-%m-%d %H:%M"),
                }
                for chave, valor in estados.items()
            ],
            columns=["osm_id", "status", "observacao", "atualizado_em"],
        ),
        STATUS_FILE,
    )


# ───────────────────────── exportação e links ─────────────────────────


def neutralizar_formulas(df: pd.DataFrame) -> pd.DataFrame:
    """Evita que textos exportados sejam interpretados como fórmulas no Excel."""

    def limpar(valor):
        if isinstance(valor, str) and valor[:1] in ("=", "+", "-", "@", "\t", "\r"):
            return "'" + valor
        return valor

    return df.apply(lambda coluna: coluna.map(limpar))


def link_whatsapp(numero: str, nome: str, modelo: str):
    if not numero:
        return None
    texto = modelo.replace("{nome}", nome)
    return f"https://wa.me/55{numero}?text={quote(texto)}"


def criar_link_google(nome: str, localidade: str) -> str:
    consulta = f"{nome} {localidade} site oficial"
    return "https://www.google.com/search?q=" + quote(consulta)


# ───────────────────────── componentes de interface ─────────────────────────


def formatar_origem(origens: dict) -> str:
    valores = set(origens.values())
    if valores == {"cache"}:
        return "Base carregada do cache."
    if valores == {"nova coleta"}:
        return "Base atualizada por nova coleta."
    if "cache" in valores and "nova coleta" in valores:
        return "Base combinada: parte do cache e parte de nova coleta."
    if "cache" in valores:
        return "Há localidades carregadas do cache."
    if "nova coleta" in valores:
        return "Há localidades atualizadas por nova coleta."
    return ""


def metricas_leads(df: pd.DataFrame) -> None:
    colunas = st.columns(4)
    colunas[0].metric("Leads filtrados", len(df))
    colunas[1].metric(
        "Sem site / só rede social",
        int(df["status_site"].isin(["Sem site", "Só rede social"]).sum()),
        help=(
            "Ausência de registro de site no OpenStreetMap não comprova que "
            "o estabelecimento não tenha site."
        ),
    )
    colunas[2].metric(
        "WhatsApp para tentar (celular + fixo)",
        int((df["whatsapp_tentativa"] != "").sum()),
        help=(
            f"{int((df['whatsapp_num'] != '').sum())} são celulares; o restante "
            "é telefone fixo (WhatsApp Business também roda em linha fixa). "
            "Um número encontrado não confirma que exista conta ativa."
        ),
    )
    colunas[3].metric(
        "Já contatados",
        int((df["status"] != "Novo").sum()),
        help="Conta leads com status diferente de Novo.",
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


def mostrar_funil(base: pd.DataFrame, f: pd.DataFrame) -> None:
    """Mostra onde os leads da base são perdidos até chegar à tabela."""
    if base.empty:
        return

    com_contato = (
        (base["telefone"] != "")
        | (base["email"] != "")
        | (base["instagram"] != "")
        | (base["facebook"] != "")
    )
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
                len(f),
                int((f["whatsapp_tentativa"] != "").sum()) if not f.empty else 0,
            ],
        }
    )
    etapas["% da base"] = (etapas["Leads"] / max(len(base), 1) * 100).round(1)

    st.subheader("Funil de contatos")
    st.caption(
        "Poucos estabelecimentos têm telefone cadastrado no OpenStreetMap; "
        "por isso a base inteira é muito maior que o total contatável."
    )
    st.dataframe(etapas, hide_index=True, use_container_width=True)

    por_tipo = tipo_contato(base).value_counts()
    st.bar_chart(por_tipo.rename_axis("Tipo de contato").rename("Leads"))


def mostrar_distribuicao(
    titulo: str,
    serie: pd.Series,
    mensagem_vazia: str,
) -> None:
    st.subheader(titulo)
    if serie.empty:
        st.info(mensagem_vazia)
        return

    dados = serie.value_counts().rename_axis("Categoria").rename("Quantidade")
    st.bar_chart(dados)


def renderizar_busca_sidebar():
    with st.sidebar:
        st.markdown("### Busca de leads")
        st.caption("Área, abrangência e nichos da próxima busca.")

        if st.button("Configurar e-mail de contato", use_container_width=True):
            dialogo_email()

        if not contato_configurado():
            st.warning(
                "Sem e-mail válido: bases em cache ainda podem ser carregadas, "
                "mas novas coletas ficam bloqueadas."
            )

        texto = st.text_input(
            "Cidade(s) ou bairro(s)",
            value="São Caetano do Sul, SP",
            key="busca_localidades",
            help=(
                "Separe localidades por ponto e vírgula. Para a capital, prefira "
                "bairros (ex.: Pinheiros, São Paulo; Tatuapé, São Paulo)."
            ),
        )
        modo = st.radio(
            "Abrangência",
            ["Área inteira (limite administrativo)", "Raio a partir do centro"],
            key="busca_modo",
        )
        raio_km = (
            st.slider("Raio (km)", 1, 20, 3, key="busca_raio")
            if modo.startswith("Raio")
            else None
        )
        grupos = st.multiselect(
            "Nichos",
            list(NICHOS),
            default=GRUPOS_PADRAO,
            key="busca_nichos",
        )
        ttl = st.number_input(
            "Validade do cache (dias)",
            min_value=1,
            max_value=365,
            value=30,
            key="busca_ttl",
        )
        atualizar = st.checkbox(
            "Forçar nova coleta",
            key="busca_atualizar",
            help="Ignora o cache para as localidades desta busca.",
        )

        localidades = [parte.strip() for parte in texto.split(";") if parte.strip()]
        invalido = (
            "Informe ao menos uma cidade ou bairro."
            if not localidades
            else (
                "Selecione ao menos um nicho."
                if not grupos
                else (
                    "Busca por raio aceita apenas uma localidade."
                    if raio_km and len(localidades) > 1
                    else ""
                )
            )
        )

        if invalido:
            st.error(invalido)

        buscar = st.button(
            "Buscar / carregar base",
            type="primary",
            disabled=bool(invalido),
            use_container_width=True,
        )

    return localidades, raio_km, grupos, int(ttl), atualizar, buscar, invalido


def preparar_base_com_status(base: pd.DataFrame) -> pd.DataFrame:
    if base.empty:
        return base.assign(status=pd.Series(dtype=str), observacao=pd.Series(dtype=str))

    estados = ler_status()
    resultado = base.assign(
        status=base["osm_id"].map(
            lambda item: estados.get(item, {}).get("status", "Novo")
        ),
        observacao=base["osm_id"].map(
            lambda item: estados.get(item, {}).get("observacao", "")
        ),
    )
    resultado["status"] = resultado["status"].where(
        resultado["status"].isin(STATUS_LEAD),
        "Novo",
    )
    return resultado


def aplicar_filtros(base: pd.DataFrame, chave_base: str):
    if base.empty:
        return base.copy(), {
            "localidades": [],
            "nichos": [],
            "situacoes": [],
            "status": [],
            "so_contato": True,
            "sem_redes": True,
            "nome": "",
            "limite": 300,
            "max_dist": None,
        }

    localidade_opcoes = sorted(base["localidade"].dropna().unique().tolist())
    nicho_opcoes = sorted(base["nicho"].dropna().unique().tolist())
    chave = hashlib.sha1(chave_base.encode("utf-8")).hexdigest()[:10]

    with st.expander("Filtros dos resultados", expanded=True):
        st.caption(
            f"{len(localidade_opcoes)} localidade(s) · "
            f"{len(nicho_opcoes)} nicho(s) disponíveis"
        )
        f1, f2, f3, f4 = st.columns(4)

        sel_loc = f1.multiselect(
            "Localidade",
            localidade_opcoes,
            default=localidade_opcoes,
            key=f"f_localidade_{chave}",
        )
        sel_nicho = f2.multiselect(
            "Nicho",
            nicho_opcoes,
            default=nicho_opcoes,
            key=f"f_nicho_{chave}",
        )
        sel_sit = f3.multiselect(
            "Situação do site",
            SITUACOES,
            default=["Sem site", "Só rede social"],
            key=f"f_situacao_{chave}",
        )
        sel_status = f4.multiselect(
            "Status do lead",
            STATUS_LEAD,
            default=[status for status in STATUS_LEAD if status != "Descartado"],
            key=f"f_status_{chave}",
        )

        g1, g2, g3, g4 = st.columns([1.2, 1.2, 1.4, 1])
        so_contato = g1.checkbox(
            "Só com forma de contato",
            value=True,
            key=f"f_contato_{chave}",
            help="Telefone, e-mail, Instagram ou Facebook cadastrados.",
        )
        sem_redes = g2.checkbox(
            "Excluir redes identificadas",
            value=True,
            key=f"f_redes_{chave}",
            help="Considera rede quem tem brand:wikidata no OpenStreetMap.",
        )
        nome_busca = g3.text_input("Nome contém", key=f"f_nome_{chave}")
        limite_linhas = g4.number_input(
            "Máx. linhas na tabela",
            min_value=50,
            max_value=2000,
            value=300,
            step=50,
            key=f"f_limite_{chave}",
        )

        distancia_disponivel = pd.to_numeric(
            base["distancia_km"], errors="coerce"
        ).dropna()
        max_dist = None
        filtrar_distancia = st.checkbox(
            "Filtrar por distância máxima",
            key=f"f_ativar_distancia_{chave}",
        )
        if filtrar_distancia and not distancia_disponivel.empty:
            teto = max(1.0, float(distancia_disponivel.max()))
            max_dist = st.slider(
                "Distância máxima (km)",
                0.0,
                teto,
                teto,
                0.5,
                key=f"f_distancia_{chave}",
                help="Distância em linha reta até o ponto central da consulta.",
            )
        elif filtrar_distancia:
            st.info("Não há distâncias válidas nesta base.")

    filtrado = base[
        base["localidade"].isin(sel_loc)
        & base["nicho"].isin(sel_nicho)
        & base["status_site"].isin(sel_sit)
        & base["status"].isin(sel_status)
    ]

    if so_contato:
        filtrado = filtrado[
            (filtrado["telefone"] != "")
            | (filtrado["email"] != "")
            | (filtrado["instagram"] != "")
            | (filtrado["facebook"] != "")
        ]

    if sem_redes:
        filtrado = filtrado[~filtrado["rede"]]

    if nome_busca.strip():
        filtrado = filtrado[
            filtrado["nome"].str.contains(
                re.escape(nome_busca.strip()),
                case=False,
                na=False,
            )
        ]

    if max_dist is not None:
        filtrado = filtrado[filtrado["distancia_km"] <= max_dist]

    filtrado = filtrado.sort_values(
        ["pontuacao", "distancia_km"],
        ascending=[False, True],
    )

    return filtrado, {
        "localidades": sel_loc,
        "nichos": sel_nicho,
        "situacoes": sel_sit,
        "status": sel_status,
        "so_contato": so_contato,
        "sem_redes": sem_redes,
        "nome": nome_busca,
        "limite": int(limite_linhas),
        "max_dist": max_dist,
    }


def renderizar_tabela(f: pd.DataFrame, limite_linhas: int, modelo: str) -> None:
    tabela = f.head(limite_linhas).copy()
    tabela["whatsapp_url"] = [
        link_whatsapp(numero, nome, modelo)
        for numero, nome in zip(tabela["whatsapp_tentativa"], tabela["nome"])
    ]
    tabela["google_url"] = [
        criar_link_google(nome, localidade)
        for nome, localidade in zip(tabela["nome"], tabela["localidade"])
    ]

    tabela["site"] = [site if url_valida(site) else None for site in tabela["site"]]
    for coluna in ("instagram", "facebook"):
        tabela[coluna] = tabela[coluna].replace("", None)
    tabela["osm_url"] = tabela["osm_url"].replace("", None)
    tabela["email"] = tabela["email"].replace("", None)

    ordem = [
        "pontuacao",
        "nome",
        "nicho",
        "localidade",
        "status_site",
        "telefone",
        "whatsapp_url",
        "instagram",
        "facebook",
        "email",
        "site",
        "google_url",
        "osm_url",
        "endereco",
        "distancia_km",
        "status",
        "observacao",
    ]

    chave_editor = hashlib.sha1(
        "|".join(tabela["osm_id"].astype(str).tolist()).encode("utf-8")
    ).hexdigest()[:12]

    editado = st.data_editor(
        tabela[["osm_id"] + ordem],
        column_order=ordem,
        hide_index=True,
        width="stretch",
        key=f"editor_leads_{chave_editor}",
        disabled=[
            coluna for coluna in ordem if coluna not in ("status", "observacao")
        ],
        column_config={
            "pontuacao": st.column_config.NumberColumn(
                "Score",
                help=(
                    "Pontuação de oportunidade calculada pelas informações "
                    "disponíveis; não representa probabilidade de conversão."
                ),
                width="small",
            ),
            "nome": st.column_config.TextColumn("Nome", width="medium"),
            "nicho": st.column_config.TextColumn("Nicho", width="medium"),
            "localidade": st.column_config.TextColumn("Localidade", width="medium"),
            "status_site": st.column_config.TextColumn(
                "Situação do site",
                help="A classificação reflete os registros disponíveis no OSM.",
                width="medium",
            ),
            "telefone": st.column_config.TextColumn("Telefone", width="medium"),
            "whatsapp_url": st.column_config.LinkColumn(
                "WhatsApp (tentar)",
                display_text="Abrir",
                width="small",
            ),
            "instagram": st.column_config.LinkColumn(
                "Instagram",
                display_text="Abrir",
                width="small",
            ),
            "facebook": st.column_config.LinkColumn(
                "Facebook",
                display_text="Abrir",
                width="small",
            ),
            "email": st.column_config.TextColumn("E-mail", width="medium"),
            "site": st.column_config.LinkColumn(
                "Site",
                display_text="Abrir",
                width="small",
            ),
            "google_url": st.column_config.LinkColumn(
                "Conferir",
                display_text="Google",
                width="small",
            ),
            "osm_url": st.column_config.LinkColumn(
                "OpenStreetMap",
                display_text="OSM",
                width="small",
            ),
            "endereco": st.column_config.TextColumn("Endereço", width="large"),
            "distancia_km": st.column_config.NumberColumn(
                "Dist. ao centro (km)",
                format="%.2f",
                help="Distância em linha reta até o ponto central da consulta.",
                width="small",
            ),
            "status": st.column_config.SelectboxColumn(
                "Status",
                options=STATUS_LEAD,
                required=True,
                width="medium",
            ),
            "observacao": st.column_config.TextColumn(
                "Observação",
                width="large",
            ),
        },
    )

    if len(f) > len(tabela):
        st.caption(
            f"A tabela mostra os {len(tabela)} melhores de {len(f)} leads filtrados. "
            "A exportação CSV inclui todos os leads filtrados."
        )

    col_salvar, col_ajuda = st.columns([1, 2])
    if col_salvar.button(
        "Salvar status e observações",
        type="primary",
        key=f"salvar_status_{chave_editor}",
    ):
        try:
            salvar_status(editado)
        except OSError as erro:
            st.error(f"Não consegui gravar {STATUS_FILE.name}: {erro}")
        else:
            st.toast("Status e observações salvos.")
            st.rerun()

    col_ajuda.caption(
        "Edite Status e Observação na tabela e salve para persistir as alterações."
    )


def renderizar_exportacao(f: pd.DataFrame, modelo: str) -> None:
    exportar = f.drop(columns=["rede", "osm_url"], errors="ignore").assign(
        whatsapp_url=[
            link_whatsapp(numero, nome, modelo) or ""
            for numero, nome in zip(f["whatsapp_tentativa"], f["nome"])
        ]
    )
    exportar = exportar.assign(fonte_dados=FONTE_DADOS)
    csv = neutralizar_formulas(exportar).to_csv(index=False).encode("utf-8-sig")

    st.download_button(
        "Baixar todos os leads filtrados (CSV)",
        data=csv,
        file_name=f"leads_{datetime.now():%Y%m%d_%H%M}.csv",
        mime="text/csv",
        use_container_width=True,
    )


# ───────────────────────── páginas da aplicação ─────────────────────────


def renderizar_visao_geral(
    base: pd.DataFrame,
    f: pd.DataFrame,
    rotulo: str,
    origens: dict,
) -> None:
    st.subheader("Visão geral")
    if base.empty:
        st.info(
            "Ainda não há uma base carregada. Configure a busca na lateral e "
            "selecione **Buscar / carregar base**."
        )
        return

    ultima_coleta = (
        base["coletado_em"].dropna().max()
        if "coletado_em" in base and not base["coletado_em"].dropna().empty
        else "Data indisponível"
    )
    col_a, col_b = st.columns([2, 1])
    with col_a:
        st.markdown(f"**Base atual:** {rotulo or 'Localidade não informada'}")
        st.caption(f"Última coleta registrada: {ultima_coleta}")
        origem = formatar_origem(origens)
        if origem:
            st.caption(origem)
    with col_b:
        st.metric("Leads disponíveis na base", len(base))

    metricas_leads(f)
    mostrar_funil(base, f)
    st.caption(
        "A pontuação é heurística e não representa probabilidade de conversão. "
        "A ausência de site no OpenStreetMap não prova que o negócio não tenha site."
    )

    col_nicho, col_site = st.columns(2)
    with col_nicho:
        mostrar_distribuicao(
            "Distribuição por nicho",
            f["nicho"] if not f.empty else pd.Series(dtype=str),
            "Não há leads para os filtros atuais.",
        )
    with col_site:
        mostrar_distribuicao(
            "Distribuição por situação do site",
            f["status_site"] if not f.empty else pd.Series(dtype=str),
            "Não há leads para os filtros atuais.",
        )

    st.subheader("Acompanhamento")
    mostrar_distribuicao(
        "Leads por status",
        f["status"] if not f.empty else pd.Series(dtype=str),
        "Não há leads para os filtros atuais.",
    )


def renderizar_leads(f: pd.DataFrame, filtros: dict, modelo: str) -> None:
    st.subheader("Leads e resultados")

    if f.empty:
        st.info("Nenhum lead corresponde aos filtros selecionados.")
        return

    st.caption(
        f"{len(f)} lead(s) correspondem aos filtros. "
        "A tabela é ordenada pela pontuação e distância."
    )
    metricas_leads(f)

    st.caption(
        "A ausência de site no OpenStreetMap não garante que o negócio não tenha site. "
        "Use o link do Google para conferir antes de abordar."
    )
    st.caption(
        "O link de WhatsApp é apenas uma tentativa de contato; encontrar um celular "
        "não confirma que o número tenha conta ativa."
    )

    renderizar_tabela(f, filtros["limite"], modelo)

    st.divider()
    renderizar_exportacao(f, modelo)


def renderizar_analises(f: pd.DataFrame) -> None:
    st.subheader("Mapa e análises")
    st.caption("As visualizações usam os mesmos filtros aplicados aos resultados.")

    col_grafico, col_mapa = st.columns([1, 2])
    with col_grafico:
        mostrar_distribuicao(
            "Leads por nicho",
            f["nicho"] if not f.empty else pd.Series(dtype=str),
            "Não há dados para exibir com os filtros atuais.",
        )
        mostrar_distribuicao(
            "Situação do site",
            f["status_site"] if not f.empty else pd.Series(dtype=str),
            "Não há dados para exibir com os filtros atuais.",
        )
        mostrar_distribuicao(
            "Status do lead",
            f["status"] if not f.empty else pd.Series(dtype=str),
            "Não há dados para exibir com os filtros atuais.",
        )

    with col_mapa:
        st.subheader("Mapa de estabelecimentos")
        if f.empty:
            st.info("Não há leads para mostrar no mapa.")
        else:
            coordenadas = f[["latitude", "longitude"]].copy()
            coordenadas["latitude"] = pd.to_numeric(
                coordenadas["latitude"], errors="coerce"
            )
            coordenadas["longitude"] = pd.to_numeric(
                coordenadas["longitude"], errors="coerce"
            )
            coordenadas = coordenadas.dropna().rename(
                columns={"latitude": "lat", "longitude": "lon"}
            )
            if coordenadas.empty:
                st.info("Esta base não contém coordenadas válidas para o mapa.")
            else:
                st.map(coordenadas)


def renderizar_configuracoes() -> None:
    st.subheader("Configurações e informações")

    st.markdown("#### E-mail de contato")
    contato = carregar_contato()
    if contato_configurado():
        origem = (
            "variável de ambiente `BUSCA_LEADS_CONTATO`"
            if os.getenv("BUSCA_LEADS_CONTATO", "").strip()
            else "`dados_osm/config.json`"
        )
        st.success(f"E-mail válido configurado: **{contato}**")
        st.caption(f"Origem da configuração: {origem}.")
    else:
        st.warning(
            "Não há e-mail válido configurado. Bases existentes em cache podem "
            "ser carregadas, mas novas coletas ficam bloqueadas."
        )

    if st.button("Abrir configuração de e-mail", key="abrir_email_config"):
        dialogo_email()

    st.divider()
    st.markdown("#### Mensagem de WhatsApp")
    st.text_area(
        "Modelo da mensagem — use `{nome}` para inserir o nome do estabelecimento",
        value=MODELO_MSG,
        height=150,
        key="modelo_whatsapp",
        help=(
            "O link gerado abre uma tentativa de conversa. Não é possível confirmar "
            "se o número possui uma conta ativa no WhatsApp."
        ),
    )

    st.divider()
    st.markdown("#### Fonte dos dados e uso responsável")
    st.markdown(
        f"{FONTE_DADOS}. A ausência de dados no OpenStreetMap não comprova que "
        "uma informação ou estabelecimento não exista."
    )
    st.markdown(
        "Ao abordar um estabelecimento, identifique-se, ofereça uma opção para "
        "não receber novos contatos, evite disparos em massa e respeite a LGPD."
    )
    st.caption(
        "A pontuação de oportunidade é uma heurística baseada nas informações "
        "disponíveis, não uma previsão de conversão."
    )


# ───────────────────────── função principal ─────────────────────────


def main() -> None:
    st.set_page_config(
        page_title="Busca de leads",
        page_icon="📍",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(CSS_TEMA, unsafe_allow_html=True)

    st.title("Busca de leads")
    st.caption(
        "Prospecção de estabelecimentos com dados do OpenStreetMap, "
        "priorização de oportunidades e acompanhamento de contatos."
    )

    configurar_email_inicio()

    (
        localidades,
        raio_km,
        grupos,
        ttl,
        atualizar,
        buscar,
        invalido,
    ) = renderizar_busca_sidebar()

    assinatura = (tuple(localidades), raio_km, tuple(sorted(grupos)))

    if buscar and not invalido:
        barra = st.progress(0.0, text="Iniciando busca...")
        origens = {}
        try:
            nova, falhas, aproximadas = carregar_base(
                localidades,
                raio_km,
                grupos,
                atualizar,
                ttl,
                lambda fracao, texto_progresso: barra.progress(
                    fracao,
                    text=texto_progresso,
                ),
                origens=origens,
            )
        except Exception as erro:
            nova, falhas, aproximadas = None, [("(busca)", str(erro))], 0
        finally:
            barra.empty()

        falhou_tudo = nova is None or len(falhas) >= len(localidades)
        st.session_state["falhas"] = falhas
        st.session_state["busca_falhou"] = falhou_tudo
        st.session_state["origens"] = origens

        if not falhou_tudo:
            st.session_state.update(
                base=nova,
                rotulo="; ".join(localidades),
                assinatura=assinatura,
                aprox=aproximadas,
            )

    for localidade, mensagem in st.session_state.get("falhas", []):
        st.warning(f"Não foi possível coletar **{localidade}**: {mensagem}")

    base_bruta = st.session_state.get("base")
    if base_bruta is None:
        base = pd.DataFrame(
            columns=COLUNAS + ["whatsapp_tentativa", "status", "observacao"]
        )
        rotulo = ""
        assinatura_atual = None
        origens = {}
    else:
        base = preparar_base_com_status(base_bruta)
        rotulo = st.session_state.get("rotulo", "")
        assinatura_atual = st.session_state.get("assinatura")
        origens = st.session_state.get("origens", {})

    if st.session_state.get("busca_falhou"):
        st.error(
            "A última busca falhou. A base anterior foi mantida e continua disponível."
        )
    elif base_bruta is not None and assinatura != assinatura_atual:
        st.info(
            f"Os controles da busca foram alterados, mas a base exibida ainda é: "
            f"**{rotulo}**. Selecione **Buscar / carregar base** para atualizá-la."
        )

    if base_bruta is not None and base_bruta.empty:
        st.warning(
            "A busca terminou sem resultados. Tente outro nicho, bairro ou raio."
        )

    chave_base = (
        "|".join(base_bruta["osm_id"].astype(str).tolist())
        if base_bruta is not None and not base_bruta.empty
        else "sem-base"
    )
    f, filtros = aplicar_filtros(base, chave_base)
    modelo = st.session_state.get("modelo_whatsapp", MODELO_MSG)

    tab_visao, tab_leads, tab_analises, tab_config = st.tabs(
        ["Visão geral", "Leads", "Mapa e análises", "Configurações"]
    )

    with tab_visao:
        renderizar_visao_geral(base, f, rotulo, origens)

    with tab_leads:
        if base_bruta is None:
            st.info(
                "Carregue uma base pela área de busca na lateral para visualizar "
                "e acompanhar leads."
            )
        else:
            renderizar_leads(f, filtros, modelo)

    with tab_analises:
        if base_bruta is None:
            st.info("Carregue uma base para consultar o mapa e as análises.")
        else:
            renderizar_analises(f)

    with tab_config:
        renderizar_configuracoes()

    st.divider()
    st.caption(
        "Dados © OpenStreetMap contributors (ODbL) · "
        "openstreetmap.org/copyright. Ao abordar, respeite a LGPD: "
        "identifique-se, ofereça opção de não receber contato e evite disparos em massa."
    )


if __name__ == "__main__":
    main()