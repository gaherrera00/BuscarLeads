"""E-mail de contato, nome do vendedor e última busca (env ou config.json)."""

from __future__ import annotations

import json
import os
import re

from buscarleads import constantes
from buscarleads.constantes import EMAIL_RE


def ler_config() -> dict:
    try:
        configuracao = json.loads(constantes.arquivo_config().read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    return configuracao if isinstance(configuracao, dict) else {}


def gravar_config(configuracao: dict) -> None:
    constantes.arquivo_config().write_text(
        json.dumps(configuracao, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def atualizar_config(**campos: str) -> None:
    configuracao = ler_config()
    configuracao.update(campos)
    gravar_config(configuracao)


def carregar_contato() -> str:
    """A variável de ambiente tem prioridade sobre a configuração local."""
    contato_env = os.getenv("BUSCA_LEADS_CONTATO", "").strip()
    if contato_env:
        return contato_env
    return str(ler_config().get("contato", "")).strip()


def salvar_contato(contato: str) -> None:
    atualizar_config(contato=contato.strip())


def email_de_contato_valido(contato: str) -> bool:
    return bool(
        re.fullmatch(EMAIL_RE, contato.strip())
        and not contato.strip().endswith("@exemplo.com")
    )


def contato_configurado() -> bool:
    return email_de_contato_valido(carregar_contato())


def carregar_nome_vendedor() -> str:
    return str(ler_config().get("nome_vendedor", "")).strip()


def salvar_nome_vendedor(nome: str) -> None:
    atualizar_config(nome_vendedor=nome.strip())


def cabecalhos() -> dict:
    return {"User-Agent": f"BuscaLeadsStreamlit/2.1 ({carregar_contato()})"}


def exigir_contato() -> None:
    if not contato_configurado():
        raise RuntimeError("Configure um e-mail válido para habilitar novas coletas.")


def salvar_ultima_busca(localidades: list[str], raio_km, grupos: list[str]) -> None:
    """Lembra a última busca para abrir o app já com o dashboard preenchido."""
    atualizar_config(
        ultima_busca={
            "localidades": list(localidades),
            "raio_km": None if raio_km is None else float(raio_km),
            "grupos": list(grupos),
        }
    )


def carregar_ultima_busca() -> dict | None:
    busca = ler_config().get("ultima_busca")
    if not isinstance(busca, dict) or not busca.get("localidades"):
        return None
    return busca
