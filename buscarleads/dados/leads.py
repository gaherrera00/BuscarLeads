"""Leitura, carga e correção dos CSVs de leads."""

from __future__ import annotations

import re
import shutil
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

from buscarleads import constantes
from buscarleads.constantes import COLUNAS, COLUNAS_CALCULADAS, COLUNAS_EDITAVEIS
from buscarleads.contato import exigir_contato
from buscarleads.dados import arquivos, avisos
from buscarleads.dados.tabelas import gravar_csv
from buscarleads.normalizacao import (
    RE_LINK_ZAP,
    ddd_predominante,
    email_valido,
    normalizar_nome,
    normalizar_url,
    pontuar,
    primeiro_fixo,
    processar_telefones,
    situacao_site,
    url_social,
    url_valida,
)
from buscarleads.osm import coletar

_VERDADEIRO = ("true", "1", "sim")


# ------------------------------------------------------------------- leitura
def _links_whatsapp(site: str, instagram: str, facebook: str) -> str:
    return ";".join(RE_LINK_ZAP.findall(" ".join((site, instagram, facebook))))


def ler_csv(caminho: Path) -> pd.DataFrame:
    """Lê um CSV de leads e recalcula telefone, WhatsApp e pontuação.

    Recalcular aqui (e não confiar no que está gravado) mantém arquivos antigos
    consistentes com as regras atuais e faz uma correção manual de telefone ou
    site refletir na pontuação sem passos extras.
    """
    caminho = Path(caminho)
    df = pd.read_csv(caminho, dtype=str, keep_default_na=False)
    if not {"nome", "osm_id"} <= set(df.columns):
        raise ValueError(f"{caminho.name} não tem as colunas esperadas")

    df = df.reindex(columns=COLUNAS, fill_value="")
    for coluna in ("distancia_km", "latitude", "longitude"):
        df[coluna] = pd.to_numeric(df[coluna], errors="coerce")

    df["rede"] = df["rede"].astype(str).str.strip().str.lower().isin(_VERDADEIRO)

    ddd = ddd_predominante(df["telefone"])
    extra_zap = [
        _links_whatsapp(site, insta, face)
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
        zap or primeiro_fixo(tel) for zap, tel in zip(df["whatsapp_num"], df["telefone"])
    ]
    df["arquivo_origem"] = caminho.name
    return df


def deduplicar_aproximado(df: pd.DataFrame) -> pd.DataFrame:
    """Remove o mesmo estabelecimento repetido (nome + telefone ou nome + endereço)."""
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
        nome = normalizar_nome(df.at[indice, "nome"])
        telefone = str(df.at[indice, "telefone"]).strip()
        endereco = str(df.at[indice, "endereco"]).strip().casefold()

        if not nome:
            continue

        repetido = False
        if telefone:
            repetido = any(
                not endereco or not existente or existente == endereco
                for existente in por_telefone.get((nome, telefone), [])
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


def base_vazia() -> pd.DataFrame:
    return pd.DataFrame(columns=COLUNAS + COLUNAS_CALCULADAS)


def _consolidar(quadros: list[pd.DataFrame]) -> tuple[pd.DataFrame, int]:
    base = pd.concat(quadros, ignore_index=True).drop_duplicates(subset="osm_id")
    antes = len(base)
    base = deduplicar_aproximado(base)
    return base.reset_index(drop=True), antes - len(base)


# ---------------------------------------------------------------------- carga
def carregar_base(
    localidades,
    raio_km,
    grupos,
    atualizar,
    ttl_dias,
    progresso=None,
    origens=None,
    somente_cache=False,
):
    """Carrega o CSV mais recente de cada localidade ou faz uma coleta nova.

    ``somente_cache=True`` nunca acessa a internet e ignora a validade: é o
    modo usado ao abrir o app para mostrar o que já existe no disco.
    ``origens`` é opcional e recebe, por localidade, de onde veio a base.
    Devolve (base, falhas, quantidade_removida_na_deduplicacao).
    """
    quadros, falhas = [], []
    consultou = False

    for indice, localidade in enumerate(localidades):
        if progresso:
            progresso(
                indice / len(localidades),
                f"Processando {localidade} ({indice + 1}/{len(localidades)})",
            )

        caminho, origem_cache = arquivos.cache_mais_recente(localidade, raio_km, grupos)

        try:
            if somente_cache:
                if caminho is None:
                    raise ValueError("não há arquivo salvo para esta busca")
                quadros.append(ler_csv(caminho))
                if origens is not None:
                    origens[localidade] = origem_cache
                continue

            if (
                caminho
                and not atualizar
                and arquivos.cache_valido(caminho, ttl_dias)
            ):
                try:
                    quadros.append(ler_csv(caminho))
                    if origens is not None:
                        origens[localidade] = origem_cache
                    continue
                except (ValueError, OSError, pd.errors.ParserError):
                    pass  # arquivo ilegível: cai para uma coleta nova

            exigir_contato()
            if consultou:
                time.sleep(1.1)  # respeita o limite do Nominatim
            consultou = True

            dados = coletar(localidade, raio_km, grupos)
            if caminho is not None:
                herdadas = herdar_edicoes(dados, caminho)
                if herdadas:
                    avisos.registrar(
                        f"{herdadas} correção(ões) manual(is) de {localidade} foram "
                        "mantidas na nova coleta."
                    )
            destino = arquivos.novo_caminho_cache(localidade, raio_km)
            gravar_csv(dados, destino)
            arquivos.gravar_meta(destino, localidade, raio_km, grupos, "coleta")
            quadros.append(ler_csv(destino))
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
        return base_vazia(), falhas, 0

    base, removidos = _consolidar(quadros)
    return base, falhas, removidos


def carregar_ultimo_arquivo() -> tuple[pd.DataFrame, str, Path] | None:
    """Abre o CSV de coleta mais recente da pasta. Devolve (base, localidade, caminho)."""
    caminho = arquivos.ultimo_arquivo_geral()
    if caminho is None:
        return None
    try:
        df = ler_csv(caminho)
    except (ValueError, OSError, pd.errors.ParserError):
        return None
    meta = arquivos.ler_meta(caminho) or {}
    partes = arquivos.partes_nome(caminho) or {}
    localidade = meta.get("localidade") or partes.get("loc") or ""
    base, _ = _consolidar([df])
    return base, localidade, caminho


# ------------------------------------------------------------------- correção
@dataclass
class ResultadoEdicao:
    gravadas: int = 0  # linhas realmente alteradas
    erros: list[str] = field(default_factory=list)


def normalizar_edicao(coluna: str, valor, ddd: str = "") -> tuple[str, str | None]:
    """Valida e padroniza um valor digitado. Devolve (valor, mensagem_de_erro)."""
    texto = "" if valor is None or (isinstance(valor, float) and pd.isna(valor)) else str(valor).strip()

    if coluna == "nome":
        return (texto, None) if texto else ("", "o nome não pode ficar vazio")
    if coluna == "email":
        if texto and not email_valido(texto):
            return "", f"e-mail inválido: {texto}"
        return texto, None
    if coluna == "site":
        if not texto:
            return "", None
        url = normalizar_url(texto)
        return (url, None) if url_valida(url) else ("", f"site inválido: {texto}")
    if coluna == "instagram":
        return (url_social(texto, "instagram.com"), None) if texto else ("", None)
    if coluna == "facebook":
        return (url_social(texto, "facebook.com"), None) if texto else ("", None)
    if coluna == "telefone":
        if not texto:
            return "", None
        formatado, _ = processar_telefones(texto, ddd)
        return formatado, None
    return texto, None  # endereco e demais campos livres


def _backup_uma_vez(caminho: Path) -> None:
    """Guarda a versão original (como saiu do OpenStreetMap) antes da 1ª correção."""
    pasta = constantes.pasta_backup()
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / caminho.name
    if not destino.exists():
        shutil.copy2(caminho, destino)


def _atualizar_linha(bruto: pd.DataFrame, indice, campos: dict, ddd: str):
    """Aplica campos validados a uma linha do CSV cru e recalcula o que deriva deles.

    Devolve (houve_mudanca, lista_de_erros).
    """
    erros, mudados = [], []
    nome_lead = str(bruto.at[indice, "nome"])

    for coluna, valor in campos.items():
        if coluna not in COLUNAS_EDITAVEIS:
            continue
        novo, erro = normalizar_edicao(coluna, valor, ddd)
        if erro:
            erros.append(f"{nome_lead}: {erro}")
            continue

        if coluna == "telefone":
            extra = _links_whatsapp(
                bruto.at[indice, "site"],
                bruto.at[indice, "instagram"],
                bruto.at[indice, "facebook"],
            )
            telefone, zap = processar_telefones(novo, ddd, extra)
            if telefone != bruto.at[indice, "telefone"] or zap != bruto.at[indice, "whatsapp_num"]:
                bruto.at[indice, "telefone"] = telefone
                bruto.at[indice, "whatsapp_num"] = zap
                mudados.append(coluna)
        elif novo != str(bruto.at[indice, coluna]):
            bruto.at[indice, coluna] = novo
            mudados.append(coluna)

    if mudados:
        site, insta, face = (str(bruto.at[indice, c]) for c in ("site", "instagram", "facebook"))
        bruto.at[indice, "status_site"] = situacao_site(site, insta, face)
        bruto.at[indice, "pontuacao"] = str(
            pontuar(
                bruto.at[indice, "status_site"],
                bruto.at[indice, "whatsapp_num"],
                bruto.at[indice, "telefone"],
                bruto.at[indice, "email"],
                insta,
                face,
                str(bruto.at[indice, "rede"]).strip().lower() in _VERDADEIRO,
            )
        )
        anteriores = {c for c in str(bruto.at[indice, "editado_campos"]).split(";") if c}
        bruto.at[indice, "editado_campos"] = ";".join(sorted(anteriores | set(mudados)))
        bruto.at[indice, "editado_em"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    return bool(mudados), erros


def _ler_cru(caminho: Path) -> pd.DataFrame:
    bruto = pd.read_csv(caminho, dtype=str, keep_default_na=False)
    for coluna in COLUNAS:
        if coluna not in bruto.columns:
            bruto[coluna] = ""
    return bruto


def aplicar_edicoes(
    mudancas: dict[str, dict], origem_por_id: dict[str, str]
) -> ResultadoEdicao:
    """Grava correções direto nos CSVs de origem, sem nova coleta.

    ``mudancas``: {osm_id: {coluna: novo_valor}}.
    ``origem_por_id``: {osm_id: nome do CSV de onde a linha veio}.
    Cada arquivo é reescrito de forma atômica; a primeira correção de um
    arquivo guarda uma cópia do original em ``dados_osm/_backup``.
    """
    resultado = ResultadoEdicao()
    por_arquivo: dict[str, dict[str, dict]] = {}
    for osm_id, campos in mudancas.items():
        origem = origem_por_id.get(osm_id)
        if not origem:
            resultado.erros.append(f"{osm_id}: arquivo de origem desconhecido")
            continue
        por_arquivo.setdefault(origem, {})[osm_id] = campos

    for nome_arquivo, linhas in por_arquivo.items():
        caminho = constantes.DATA_DIR / nome_arquivo
        if not caminho.exists():
            resultado.erros.append(f"{nome_arquivo}: arquivo não encontrado")
            continue

        bruto = _ler_cru(caminho)
        ddd = ddd_predominante(bruto["telefone"])
        posicoes = {osm: idx for idx, osm in zip(bruto.index, bruto["osm_id"])}
        alterou_arquivo = 0

        for osm_id, campos in linhas.items():
            indice = posicoes.get(osm_id)
            if indice is None:
                resultado.erros.append(f"{osm_id}: não está em {nome_arquivo}")
                continue
            mudou, erros = _atualizar_linha(bruto, indice, campos, ddd)
            resultado.erros.extend(erros)
            alterou_arquivo += int(mudou)

        if alterou_arquivo:
            _backup_uma_vez(caminho)
            gravar_csv(bruto, caminho)
            resultado.gravadas += alterou_arquivo

    return resultado


def herdar_edicoes(novo: pd.DataFrame, anterior: Path) -> int:
    """Leva as correções manuais do CSV anterior para uma coleta nova (em memória).

    Sem isso, "Forçar nova coleta" apagaria em silêncio o trabalho de correção.
    Devolve quantas linhas herdaram correções.
    """
    try:
        velho = _ler_cru(anterior)
    except (OSError, ValueError, pd.errors.ParserError):
        return 0

    editados = velho[velho["editado_em"].astype(str).str.strip() != ""]
    if editados.empty:
        return 0

    for coluna in COLUNAS:
        if coluna not in novo.columns:
            novo[coluna] = ""
    derivadas = ["telefone", "whatsapp_num", "status_site", "pontuacao", "editado_em", "editado_campos"]
    novo[derivadas] = novo[derivadas].astype(object)

    posicoes = {osm: idx for idx, osm in zip(novo.index, novo["osm_id"].astype(str))}
    ddd = ddd_predominante(novo["telefone"].astype(str))
    herdadas = 0
    for _, linha in editados.iterrows():
        indice = posicoes.get(linha["osm_id"])
        if indice is None:
            continue  # o lugar sumiu do OpenStreetMap: não há onde aplicar
        # Só os campos que o usuário de fato corrigiu: o resto segue o OSM atualizado.
        editados_na_linha = [c for c in str(linha["editado_campos"]).split(";") if c in COLUNAS_EDITAVEIS]
        campos = {coluna: linha[coluna] for coluna in editados_na_linha}
        mudou, _ = _atualizar_linha(novo, indice, campos, ddd)
        if mudou:
            novo.at[indice, "editado_em"] = linha["editado_em"]
            herdadas += 1
    return herdadas
