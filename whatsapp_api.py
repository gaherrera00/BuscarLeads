"""Cliente HTTP da WAHA Core.

Endpoints usados, conforme a documentação atual (waha.devlike.pro):
- GET /ping e GET /health
- GET /api/sessions/{session}
- POST /api/{session}/auth/qr
- POST /api/sendText

O chatId é o telefone internacional, sem "+", com sufixo @c.us.
A autenticação, quando configurada, vai no cabeçalho X-Api-Key.
O motor GOWS existe na imagem Core (gratuita) e na Plus; o compose
deste projeto define WHATSAPP_DEFAULT_ENGINE=GOWS.

POST /api/sendText envia texto de conversa. A WAHA Core não usa os
modelos aprovados da API oficial da Meta. O envio fica bloqueado quando
a sessão não está WORKING ou quando a própria sessão informa restrição
de abordagem (reachoutTimelock).
"""

from __future__ import annotations

import base64
import binascii
import os
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, urlparse

import requests


class WahaErro(Exception):
    def __init__(self, tipo: str, mensagem: str):
        super().__init__(mensagem)
        self.tipo = tipo


@dataclass(frozen=True, repr=False)
class ConfigWaha:
    base_url: str
    api_key: str
    session: str

    def __repr__(self) -> str:
        return (
            "ConfigWaha("
            f"base_url={self.base_url!r}, "
            f"session={self.session!r}, "
            f"api_key_definida={bool(self.api_key)})"
        )


_ENV_CARREGADO = False
_PLACEHOLDER = re.compile(r"\{([A-Za-z0-9_]+)\}")
_STATUS_TEXTO = {
    "STOPPED": (
        "A sessão está parada. No painel da WAHA, inicie a sessão e conecte "
        "o WhatsApp."
    ),
    "STARTING": "A sessão está iniciando. Aguarde o status WORKING antes de enviar.",
    "SCAN_QR_CODE": (
        "A sessão aguarda o QR Code. No WhatsApp do celular, abra Aparelhos "
        "conectados e escaneie o código exibido abaixo ou no painel da WAHA."
    ),
    "SCAN_QR": (
        "A sessão aguarda o QR Code. No WhatsApp do celular, abra Aparelhos "
        "conectados e escaneie o código exibido abaixo ou no painel da WAHA."
    ),
    "FAILED": (
        "A sessão falhou. No painel da WAHA, reinicie a sessão. Se continuar "
        "falhando, saia da sessão e conecte o WhatsApp de novo."
    ),
    "PASSKEY_REQUIRED": (
        "O WhatsApp pediu uma passkey para concluir a conexão. Termine o "
        "pareamento no celular antes de enviar."
    ),
    "PASSKEY_CONFIRMATION_REQUIRED": (
        "O WhatsApp pediu a confirmação de um código no celular. Termine o "
        "pareamento antes de enviar."
    ),
}


def _carregar_env() -> None:
    global _ENV_CARREGADO
    if _ENV_CARREGADO:
        return
    _ENV_CARREGADO = True
    caminho = Path(__file__).resolve().parent / ".env"
    if not caminho.is_file():
        return
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        texto = linha.strip()
        if not texto or texto.startswith("#") or "=" not in texto:
            continue
        chave, valor = texto.split("=", 1)
        chave = chave.strip()
        valor = valor.strip().strip('"').strip("'")
        if chave and chave not in os.environ:
            os.environ[chave] = valor


def _de_secrets(nome: str) -> str:
    try:
        import streamlit as st

        segredos = st.secrets
    except Exception:
        return ""
    try:
        valor = segredos[nome]
    except Exception:
        return ""
    return str(valor or "").strip()


def _limpar_campo(valor) -> str:
    if valor is None:
        return ""
    texto = " ".join(str(valor).split())
    if texto.lower() == "none":
        return ""
    return texto


def _url_valida(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc) and not (
        parsed.username or parsed.password
    )


def ler_config() -> ConfigWaha:
    _carregar_env()
    base = os.getenv("WAHA_BASE_URL", "").strip() or _de_secrets("WAHA_BASE_URL")
    chave = os.getenv("WAHA_API_KEY", "").strip() or _de_secrets("WAHA_API_KEY")
    sessao = os.getenv("WAHA_SESSION", "").strip() or _de_secrets("WAHA_SESSION")
    return ConfigWaha(
        base_url=(base or "http://127.0.0.1:3000").rstrip("/"),
        api_key=chave,
        session=sessao or "default",
    )


def resumo_config(config: ConfigWaha | None = None) -> dict:
    config = config or ler_config()
    return {
        "base_url": config.base_url,
        "session": config.session,
        "api_key_definida": bool(config.api_key),
        "url_valida": _url_valida(config.base_url),
        "sessao_valida": bool(re.fullmatch(r"[A-Za-z0-9_-]{1,64}", config.session)),
    }


def personalizar_mensagem(
    modelo: str,
    nome: str,
    nicho: str = "",
    cidade: str = "",
) -> tuple[str, str]:
    """Devolve (texto, erro). Erro vazio significa que o texto pode ser enviado."""
    texto_modelo = "" if modelo is None else str(modelo).replace("\r\n", "\n")
    if not texto_modelo.strip():
        return "", "O modelo da mensagem está vazio."
    if "{nome}" not in texto_modelo:
        return "", "O modelo precisa conter a variável {nome}."

    valores = {
        "nome": _limpar_campo(nome),
        "nicho": _limpar_campo(nicho),
        "cidade": _limpar_campo(cidade),
    }
    if not valores["nome"]:
        return "", "O lead não tem nome de empresa utilizável."

    faltando: list[str] = []

    def substituir(ocorrencia: re.Match) -> str:
        chave = ocorrencia.group(1)
        if chave not in valores:
            faltando.append(chave)
            return ocorrencia.group(0)
        return valores[chave]

    texto = _PLACEHOLDER.sub(substituir, texto_modelo)
    if faltando:
        unicas = ", ".join(sorted(set(faltando)))
        return "", f"O modelo contém variável não suportada: {unicas}."

    linhas = []
    for linha in texto.split("\n"):
        linha = re.sub(r"[ \t]{2,}", " ", linha)
        linha = re.sub(r"\s+([,.;:!?])", r"\1", linha).strip()
        linhas.append(linha)
    texto = "\n".join(linhas).strip()
    if not texto:
        return "", "A mensagem ficou vazia depois da personalização."
    if len(texto) > 4000:
        return "", "A mensagem passou de 4000 caracteres."
    return texto, ""


def chat_id_waha(digitos_nacionais: str) -> str:
    digitos = re.sub(r"\D", "", digitos_nacionais or "")
    if digitos.startswith("55") and len(digitos) in {12, 13}:
        digitos = digitos[2:]
    if len(digitos) not in {10, 11}:
        raise WahaErro(
            "numero",
            "O número não está no formato internacional exigido pela WAHA.",
        )
    return f"55{digitos}@c.us"


def extrair_message_id(corpo) -> str:
    if not isinstance(corpo, dict):
        return ""
    identificador = corpo.get("id")
    if isinstance(identificador, str) and identificador.strip():
        return identificador.strip()
    if isinstance(identificador, dict):
        serializado = identificador.get("_serialized")
        if isinstance(serializado, str) and serializado.strip():
            return serializado.strip()
        interno = identificador.get("id")
        if isinstance(interno, str) and interno.strip():
            return interno.strip()
    chave = corpo.get("key")
    if isinstance(chave, dict):
        interno = chave.get("id")
        if isinstance(interno, str) and interno.strip():
            return interno.strip()
    return ""


def _sanitizar(texto: str, config: ConfigWaha) -> str:
    limpo = texto or ""
    if config.api_key:
        limpo = limpo.replace(config.api_key, "[redigido]")
    return limpo[:300]


def _detalhe_http(resposta: requests.Response, config: ConfigWaha) -> str:
    try:
        corpo = resposta.json()
    except ValueError:
        return _sanitizar((resposta.text or "").strip(), config) or f"HTTP {resposta.status_code}"
    if isinstance(corpo, dict):
        for chave in ("message", "error", "details"):
            valor = corpo.get(chave)
            if isinstance(valor, str) and valor.strip():
                return _sanitizar(valor.strip(), config)
            if isinstance(valor, list) and valor:
                return _sanitizar("; ".join(str(item) for item in valor), config)
    return f"HTTP {resposta.status_code}"


def _validar_config(config: ConfigWaha) -> None:
    if not _url_valida(config.base_url):
        raise WahaErro(
            "configuracao",
            "WAHA_BASE_URL precisa ser um endereço http ou https, sem usuário nem senha na URL.",
        )
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", config.session):
        raise WahaErro(
            "configuracao",
            "WAHA_SESSION contém caracteres não aceitos. Use letras, números, _ ou -.",
        )


def _pedido(
    config: ConfigWaha,
    metodo: str,
    caminho: str,
    payload: dict | None = None,
    accept: str = "application/json",
) -> requests.Response:
    _validar_config(config)
    headers = {"Accept": accept}
    if config.api_key:
        headers["X-Api-Key"] = config.api_key
    try:
        resposta = requests.request(
            metodo,
            config.base_url + caminho,
            headers=headers,
            json=payload,
            timeout=20,
            allow_redirects=False,
        )
    except requests.Timeout as erro:
        raise WahaErro(
            "timeout",
            "A WAHA não respondeu dentro do tempo limite.",
        ) from erro
    except requests.RequestException as erro:
        raise WahaErro(
            "conexao",
            "Não foi possível conectar à WAHA. Verifique se o serviço está em execução.",
        ) from erro
    if resposta.status_code in {301, 302, 303, 307, 308}:
        raise WahaErro("resposta", "A WAHA respondeu com redirecionamento inesperado.")
    return resposta


def verificar_servico(config: ConfigWaha) -> None:
    ultimo: WahaErro | None = None
    for caminho in ("/ping", "/health"):
        try:
            resposta = _pedido(config, "GET", caminho)
        except WahaErro as erro:
            if erro.tipo == "autenticacao":
                raise
            ultimo = erro
            continue
        if resposta.status_code in {401, 403}:
            raise WahaErro(
                "autenticacao",
                "A WAHA recusou a autenticação. Confira WAHA_API_KEY no ambiente ou em st.secrets.",
            )
        if resposta.status_code == 404:
            ultimo = WahaErro("resposta", f"A WAHA não encontrou {caminho}.")
            continue
        if resposta.status_code >= 400:
            raise WahaErro(
                "resposta",
                f"A WAHA respondeu HTTP {resposta.status_code} em {caminho}.",
            )
        return
    raise ultimo or WahaErro("conexao", "A WAHA não respondeu em /ping nem em /health.")


def _nome_engine(dados: dict) -> str:
    engine = dados.get("engine")
    if isinstance(engine, str):
        return engine.strip()
    if isinstance(engine, dict):
        valor = engine.get("engine") or engine.get("name") or ""
        return str(valor).strip()
    return ""


def _timelock_ativo(dados: dict) -> bool:
    me = dados.get("me")
    if not isinstance(me, dict):
        return False
    trava = me.get("reachoutTimelock")
    return isinstance(trava, dict) and bool(trava.get("isActive"))


def _situacao(
    acessivel: bool,
    status: str,
    pode_enviar: bool,
    mensagem: str,
    engine: str = "",
) -> dict:
    return {
        "acessivel": acessivel,
        "status": status,
        "pode_enviar": pode_enviar,
        "mensagem": mensagem,
        "engine": engine,
    }


def _situacao_erro(erro: WahaErro) -> dict:
    acessivel = erro.tipo in {"autenticacao", "resposta", "sessao"}
    return _situacao(acessivel, "", False, str(erro))


def consultar_situacao(config: ConfigWaha | None = None) -> dict:
    config = config or ler_config()
    try:
        verificar_servico(config)
    except WahaErro as erro:
        return _situacao_erro(erro)

    caminho = f"/api/sessions/{quote(config.session, safe='')}"
    try:
        resposta = _pedido(config, "GET", caminho)
    except WahaErro as erro:
        return _situacao_erro(erro)

    if resposta.status_code in {401, 403}:
        return _situacao(
            True,
            "",
            False,
            "A WAHA recusou a chave de API ao consultar a sessão.",
        )
    if resposta.status_code == 404:
        return _situacao(
            True,
            "STOPPED",
            False,
            f'A sessão "{config.session}" não existe. Crie e inicie essa sessão no painel da WAHA.',
        )
    if resposta.status_code >= 400:
        return _situacao(
            True,
            "",
            False,
            "Não foi possível consultar a sessão. " + _detalhe_http(resposta, config),
        )
    try:
        dados = resposta.json()
    except ValueError:
        return _situacao(True, "", False, "A consulta da sessão não retornou JSON.")
    if not isinstance(dados, dict):
        return _situacao(True, "", False, "A consulta da sessão trouxe uma resposta inesperada.")

    status = str(dados.get("status") or "").strip().upper()
    engine = _nome_engine(dados)
    motor = f" Motor {engine}." if engine else ""
    if status == "WORKING" and _timelock_ativo(dados):
        return _situacao(
            True,
            status,
            False,
            "A sessão está WORKING, mas o WhatsApp aplicou uma restrição temporária "
            "para abordar novos contatos. O envio fica bloqueado até essa restrição "
            "terminar. Não reinicie a sessão por causa disso." + motor,
            engine,
        )
    if status == "WORKING":
        return _situacao(
            True,
            status,
            True,
            "Sessão conectada (WORKING)."
            + motor
            + " Uma resposta de aceite da API não confirma entrega nem leitura.",
            engine,
        )
    return _situacao(
        True,
        status,
        False,
        _STATUS_TEXTO.get(
            status,
            f"A sessão está em {status or 'estado desconhecido'}. "
            "O envio só ocorre com status WORKING.",
        ),
        engine,
    )


def obter_qr(config: ConfigWaha | None = None) -> tuple[bytes, str]:
    config = config or ler_config()
    caminho = f"/api/{quote(config.session, safe='')}/auth/qr"
    resposta = _pedido(config, "POST", caminho, payload={}, accept="application/json")
    if resposta.status_code in {401, 403}:
        raise WahaErro("autenticacao", "A WAHA recusou a chave de API ao pedir o QR Code.")
    if resposta.status_code >= 400:
        raise WahaErro(
            "sessao",
            "Não foi possível obter o QR Code. Conecte o WhatsApp pelo painel da WAHA. "
            + _detalhe_http(resposta, config),
        )
    tipo = resposta.headers.get("Content-Type", "")
    if "image/" in tipo and resposta.content:
        return resposta.content, tipo.split(";")[0].strip() or "image/png"
    try:
        dados = resposta.json()
    except ValueError as erro:
        raise WahaErro("resposta", "A resposta do QR Code não é uma imagem nem JSON.") from erro
    if not isinstance(dados, dict):
        raise WahaErro("resposta", "A resposta do QR Code veio em formato inesperado.")
    mime = str(dados.get("mimetype") or "image/png")
    data = dados.get("data") or ""
    if not isinstance(data, str) or not data.strip():
        raise WahaErro("resposta", "A WAHA não devolveu a imagem do QR Code.")
    try:
        return base64.b64decode(data), mime
    except (ValueError, binascii.Error) as erro:
        raise WahaErro("resposta", "A imagem do QR Code veio corrompida.") from erro


def enviar_texto(config: ConfigWaha, chat_id: str, texto: str) -> str:
    if not isinstance(chat_id, str) or not re.fullmatch(r"55\d{10,11}@c\.us", chat_id):
        raise WahaErro("numero", "O número não está no formato chatId da WAHA.")
    if not texto or not texto.strip():
        raise WahaErro("mensagem", "A mensagem está vazia.")
    resposta = _pedido(
        config,
        "POST",
        "/api/sendText",
        payload={"session": config.session, "chatId": chat_id, "text": texto},
    )
    if resposta.status_code in {401, 403}:
        raise WahaErro("autenticacao", "A WAHA recusou a chave de API no envio.")
    if resposta.status_code == 404:
        raise WahaErro("sessao", "A WAHA não encontrou a sessão no momento do envio.")
    if resposta.status_code >= 400:
        detalhe = _detalhe_http(resposta, config)
        tipo = "numero" if resposta.status_code in {400, 422} else "resposta"
        if re.search(r"session|WORKING|disconnected", detalhe, re.I):
            tipo = "sessao"
        raise WahaErro(tipo, f"A WAHA não aceitou o envio. {detalhe}")
    try:
        corpo = resposta.json()
    except ValueError as erro:
        raise WahaErro(
            "resposta",
            "A WAHA não confirmou o envio em JSON. A tentativa não foi marcada como enviada.",
        ) from erro
    message_id = extrair_message_id(corpo)
    if not message_id:
        raise WahaErro(
            "resposta",
            "A WAHA não devolveu o identificador da mensagem. A tentativa não foi marcada como enviada.",
        )
    return message_id
