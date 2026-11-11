"""Telefone, URL, endereço, classificação e pontuação."""

from __future__ import annotations

import math
import re
import unicodedata
from urllib.parse import urlparse

from buscarleads.constantes import DDDS, EMAIL_RE, REDES, ROTULOS

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


def distancia_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    a = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * 6371.0 * math.asin(math.sqrt(a))


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
        if not digitos.startswith("55"):
            return ""
        digitos = digitos[2:]
        ddd_padrao = ""
    elif digitos.startswith("55") and len(digitos) >= 12:
        digitos = digitos[2:]
    digitos = digitos.lstrip("0")

    if ddd_padrao:
        if len(digitos) == 9 and digitos[0] == "9":
            digitos = ddd_padrao + digitos
        elif len(digitos) == 8 and digitos[0] in "2345":
            digitos = ddd_padrao + digitos
        elif len(digitos) == 8 and digitos[0] in "6789":
            digitos = ddd_padrao + "9" + digitos

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
    """Junta telefones de qualquer tag de telefone/WhatsApp do OSM.

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
    """Primeiro telefone fixo válido (DDD + 8 dígitos) de um texto já formatado."""
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
        re.fullmatch(EMAIL_RE, parte.strip())
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


def normalizar_nome(nome: str) -> str:
    ascii_nome = unicodedata.normalize("NFKD", str(nome))
    ascii_nome = ascii_nome.encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", ascii_nome.casefold()).strip()
