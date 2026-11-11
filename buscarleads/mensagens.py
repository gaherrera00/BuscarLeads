"""Textos de abordagem, links de WhatsApp/Google e proteção da exportação."""

from __future__ import annotations

from datetime import datetime

from urllib.parse import quote

import pandas as pd

from buscarleads.dados.concorrencia import gancho_concorrencia


def obter_modelo_mensagem():
    hora = datetime.now().hour

    if 5 <= hora < 12:
        saudacao = "Bom dia"
    elif 12 <= hora < 18:
        saudacao = "Boa tarde"
    else:
        saudacao = "Boa noite"

    return (
        f"{saudacao}, tudo bem? Gostaria de saber se poderia "
        "falar com o responsável pelo {nome}, por gentileza."
    )


MODELO_MSG_AVALIACAO = (
    "Oi, tudo bem? Me chamo {seu_nome}, trabalho com criação de sites pra "
    "{nicho} locais aqui em {cidade}.\n\n"
    "Vi o perfil da {nome} no Google — {trecho_nota}, mas notei que vocês "
    "não têm site. Isso faz perder gente que pesquisa antes de decidir onde ir.\n\n"
    "Posso te mostrar rapidinho como isso afeta vocês e uma solução simples? "
    "São só 2 minutos."
)

MODELO_MSG_CONCORRENCIA = (
    "Oi, tudo bem? Me chamo {seu_nome}, trabalho com criação de sites pra "
    "{nicho} locais aqui em {cidade}.\n\n"
    "Vi o perfil da {nome} no Google — {trecho_nota}, mas notei que vocês "
    'não têm site. Pesquisei "{nicho} em {cidade}" agora e o {concorrente} '
    "aparece na primeira página com site — isso puxa cliente que tava decidindo "
    "entre vocês dois.\n\n"
    "Posso te mostrar rapidinho como resolver isso de forma simples? São só 2 minutos."
)


def neutralizar_formulas(df: pd.DataFrame) -> pd.DataFrame:
    """Evita que textos exportados sejam interpretados como fórmulas no Excel."""

    def limpar(valor):
        if isinstance(valor, str) and valor[:1] in ("=", "+", "-", "@", "\t", "\r"):
            return "'" + valor
        return valor

    return df.apply(lambda coluna: coluna.map(limpar))


def _formatar_nota(nota: str) -> str:
    try:
        return f"{float(str(nota).replace(',', '.')):.1f}"
    except (TypeError, ValueError):
        return str(nota).strip()


def _nota_confiavel(linha) -> bool:
    """Só cita a nota se o Google provavelmente achou o mesmo estabelecimento."""
    if not str(linha.get("gmn_nota", "") or "").strip():
        return False
    return str(linha.get("gmn_confianca", "") or "").strip() != "baixa"


def trecho_nota(linha) -> str:
    """Trecho sobre nota e avaliações, com fallback se o lead não foi pesquisado."""
    if not _nota_confiavel(linha):
        return "ótimo perfil"
    nota = _formatar_nota(linha.get("gmn_nota", ""))
    avaliacoes = str(linha.get("gmn_avaliacoes", "") or "").strip()
    if avaliacoes:
        return f"nota {nota}⭐ com {avaliacoes} avaliações"
    return f"ótima nota ({nota}⭐)"


def _cidade(linha) -> str:
    return str(linha.get("localidade", "") or "").split(",")[0].strip()


def _concorrencia(linha) -> dict:
    return gancho_concorrencia(str(linha.get("nicho", "") or ""), _cidade(linha))


def gerar_mensagem_personalizada(
    linha, seu_nome: str, concorrencia: dict | None = None
) -> str:
    """Mensagem com nota do Google e, se houver, o concorrente que aparece na busca."""
    nicho = str(linha.get("nicho", "") or "negócios").lower()
    cidade = _cidade(linha) or "sua região"
    nome = linha.get("nome", "") or "[nome da empresa]"
    seu_nome = seu_nome.strip() or "[seu nome]"
    concorrencia = _concorrencia(linha) if concorrencia is None else concorrencia

    base = dict(
        seu_nome=seu_nome,
        nicho=nicho,
        cidade=cidade,
        nome=nome,
        trecho_nota=trecho_nota(linha),
    )
    if concorrencia:
        return MODELO_MSG_CONCORRENCIA.format(
            concorrente=concorrencia["melhor_concorrente"], **base
        )
    return MODELO_MSG_AVALIACAO.format(**base)


def texto_abordagem(linha, modelo: str, seu_nome: str) -> str:
    """Personaliza quando há dado confiável do Google ou concorrência; senão usa ``modelo``."""
    concorrencia = _concorrencia(linha)
    if _nota_confiavel(linha) or concorrencia:
        return gerar_mensagem_personalizada(linha, seu_nome, concorrencia)
    return modelo.replace("{nome}", str(linha.get("nome", "") or ""))


def link_whatsapp_texto(numero: str, texto: str):
    if not numero:
        return None
    return f"https://wa.me/55{numero}?text={quote(texto)}"


def criar_link_google(nome: str, localidade: str) -> str:
    return "https://www.google.com/search?q=" + quote(
        f"{nome} {localidade} site oficial"
    )


def coluna_whatsapp(tabela: pd.DataFrame, modelo: str, seu_nome: str) -> pd.Series:
    links = [
        link_whatsapp_texto(
            linha["whatsapp_tentativa"], texto_abordagem(linha, modelo, seu_nome)
        )
        for _, linha in tabela.iterrows()
    ]
    return pd.Series(links, index=tabela.index)
