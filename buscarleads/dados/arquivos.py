"""Nomes, localização e escolha dos CSVs de leads.

Formato do nome (legível por pessoas, com lugar, abrangência e data):

    leads__São Caetano do Sul, SP__area__2026-11-10_21h05.csv
    leads__São Caetano do Sul, SP__raio 3 km__2026-11-10_21h05.csv

Duas coletas no mesmo minuto recebem o sufixo ``-2``, ``-3``... e nunca
sobrescrevem uma à outra.
"""

from __future__ import annotations

import json
import os
import re
import unicodedata
from datetime import datetime
from pathlib import Path

import pandas as pd

from buscarleads import constantes

_PADRAO_NOME = re.compile(
    r"^leads__(?P<loc>.+?)__(?P<escopo>area|raio \d+(?:\.\d+)? km|legado|exportado)"
    r"__(?P<data>\d{4}-\d{2}-\d{2}_\d{2}h\d{2})(?:-(?P<seq>\d+))?\.csv$"
)
_PADRAO_HASH = re.compile(r"^leads_[0-9a-f]{12}\.csv$")
_PADRAO_EXPORT_ANTIGO = re.compile(r"^leads_\d{8}_\d{4}\.csv$")
_FORMATO_DATA = "%Y-%m-%d_%Hh%M"


# --------------------------------------------------------------------- nomes
def nome_legivel(localidade: str) -> str:
    """Nome de arquivo seguro e ainda reconhecível (mantém acentos e vírgulas)."""
    texto = unicodedata.normalize("NFKC", str(localidade or "")).strip()
    texto = texto.replace("__", " ")
    texto = re.sub(r'[<>:"/\\|?*]', " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip(" .")
    return texto[:80] or "Localidade"


def chave_localidade(localidade: str) -> str:
    """Iguala 'São Paulo', 'Sao Paulo' e 'São Paulo, SP' para achar o mesmo cache."""
    texto = nome_legivel(localidade)
    sem_uf = re.sub(r"\s*[-,]\s*[A-Za-z]{2}\s*$", "", texto)
    if sem_uf.strip():
        texto = sem_uf
    ascii_nome = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "", ascii_nome.casefold())


def escopo_legivel(raio_km) -> str:
    if raio_km is None:
        return "area"
    numero = float(raio_km)
    texto = str(int(numero)) if numero.is_integer() else str(numero)
    return f"raio {texto} km"


def _stamp(momento: datetime | None = None) -> str:
    return (momento or datetime.now()).strftime(_FORMATO_DATA)


def _caminho_livre(caminho: Path) -> Path:
    if not caminho.exists():
        return caminho
    for extra in range(2, 100):
        candidato = caminho.with_name(f"{caminho.stem}-{extra}{caminho.suffix}")
        if not candidato.exists():
            return candidato
    return caminho.with_name(f"{caminho.stem}-{datetime.now():%H%M%S}{caminho.suffix}")


def novo_caminho_cache(localidade: str, raio_km, quando: datetime | None = None) -> Path:
    nome = (
        f"leads__{nome_legivel(localidade)}__{escopo_legivel(raio_km)}"
        f"__{_stamp(quando)}.csv"
    )
    return _caminho_livre(constantes.DATA_DIR / nome)


def nome_exportacao(localidades) -> str:
    """Nome do CSV baixado pelo botão: lugar(es) + data da exportação."""
    lugares = [nome_legivel(lugar) for lugar in localidades if str(lugar).strip()]
    if not lugares:
        rotulo = "leads"
    elif len(lugares) == 1:
        rotulo = lugares[0]
    else:
        rotulo = " + ".join(lugares[:3])
        if len(lugares) > 3:
            rotulo += f" +{len(lugares) - 3}"
    return f"leads__{rotulo[:120]}__{_stamp()}.csv"


# ---------------------------------------------------------------------- meta
def _meta_path(caminho: Path) -> Path:
    return caminho.with_suffix(".meta.json")


def gravar_meta(caminho: Path, localidade: str, raio_km, grupos, tipo: str) -> None:
    meta = {
        "localidade": localidade.strip(),
        "raio_km": None if raio_km is None else float(raio_km),
        "grupos": None if grupos is None else list(grupos),
        "tipo": tipo,
        "criado_em": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    _meta_path(caminho).write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def ler_meta(caminho: Path) -> dict | None:
    arquivo = _meta_path(caminho)
    if not arquivo.exists():
        return None
    try:
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    return dados if isinstance(dados, dict) else None


# ----------------------------------------------------------------- descoberta
def partes_nome(caminho: Path) -> dict | None:
    achado = _PADRAO_NOME.match(caminho.name)
    return achado.groupdict() if achado else None


def arquivos_leads() -> list[Path]:
    return [
        caminho
        for caminho in constantes.DATA_DIR.glob("leads_*.csv")
        if caminho.is_file()
    ]


def data_coleta(caminho: Path) -> datetime:
    """Quando os dados foram coletados, lido do NOME do arquivo.

    O ``mtime`` do disco não serve: muda ao copiar a pasta, extrair um zip ou
    salvar uma correção, e faria um dado antigo parecer recém-coletado.
    """
    partes = partes_nome(caminho)
    if partes:
        try:
            return datetime.strptime(partes["data"], _FORMATO_DATA)
        except ValueError:
            pass
    try:
        return datetime.fromtimestamp(caminho.stat().st_mtime)
    except OSError:
        return datetime.fromtimestamp(0)


def idade_dias(caminho: Path) -> float:
    return max((datetime.now() - data_coleta(caminho)).total_seconds() / 86400, 0.0)


def cache_valido(caminho: Path, ttl_dias: float) -> bool:
    return caminho.exists() and idade_dias(caminho) < ttl_dias


def _ordem_recencia(caminho: Path) -> tuple:
    """Mais recente = maior data no nome; empate no mesmo minuto vale o sufixo -N."""
    partes = partes_nome(caminho)
    data = partes["data"] if partes else ""
    sequencia = int(partes["seq"]) if partes and partes["seq"] else 1
    try:
        mtime = caminho.stat().st_mtime
    except OSError:
        mtime = 0.0
    return data, sequencia, mtime


def _raios_iguais(salvo, pedido) -> bool:
    if salvo is None or pedido is None:
        return salvo is None and pedido is None
    try:
        return float(salvo) == float(pedido)
    except (TypeError, ValueError):
        return False


def _grupos_iguais(salvos, pedidos) -> bool:
    if not isinstance(salvos, list) or not pedidos:
        return False
    return sorted(salvos) == sorted(pedidos)


def cache_mais_recente(localidade: str, raio_km, grupos) -> tuple[Path | None, str]:
    """O CSV mais novo desta busca e a origem (``cache`` ou ``cache antigo``).

    - Só entra quem tem o mesmo lugar, a mesma abrangência e os mesmos nichos.
    - Entre os candidatos vale sempre o mais recente; um arquivo velho da mesma
      busca nunca é usado no lugar de um novo.
    - Arquivos antigos (anteriores à organização, sem nicho/raio registrados)
      só servem para busca por área inteira; nunca para busca por raio.
    - Exportações baixadas pelo botão nunca entram.
    """
    exatos: list[Path] = []
    legados: list[Path] = []
    chave = chave_localidade(localidade)

    for caminho in arquivos_leads():
        partes = partes_nome(caminho)
        if not partes or partes["escopo"] == "exportado":
            continue
        meta = ler_meta(caminho)
        local_arquivo = (meta or {}).get("localidade") or partes["loc"]
        if chave_localidade(str(local_arquivo)) != chave and chave_localidade(partes["loc"]) != chave:
            continue

        if (
            meta
            and partes["escopo"] == escopo_legivel(raio_km)
            and _raios_iguais(meta.get("raio_km"), raio_km)
            and _grupos_iguais(meta.get("grupos"), grupos)
        ):
            exatos.append(caminho)
        elif partes["escopo"] == "legado" and raio_km is None:
            legados.append(caminho)

    if exatos:
        return max(exatos, key=_ordem_recencia), "cache"
    if legados:
        return max(legados, key=_ordem_recencia), "cache antigo"
    return None, ""


def ultimo_arquivo_geral() -> Path | None:
    """O CSV de coleta mais recente da pasta, de qualquer lugar. Usado ao abrir o app."""
    candidatos = [
        caminho
        for caminho in arquivos_leads()
        if (partes := partes_nome(caminho)) and partes["escopo"] != "exportado"
    ]
    return max(candidatos, key=_ordem_recencia) if candidatos else None


def resumo_arquivos() -> list[dict]:
    """Uma linha por CSV de leads, para a tela de configurações."""
    linhas = []
    for caminho in sorted(arquivos_leads(), key=_ordem_recencia, reverse=True):
        partes = partes_nome(caminho)
        linhas.append(
            {
                "arquivo": caminho.name,
                "lugar": partes["loc"] if partes else "",
                "abrangência": partes["escopo"] if partes else "",
                "coletado em": data_coleta(caminho).strftime("%d/%m/%Y %H:%M"),
                "tamanho (KB)": round(caminho.stat().st_size / 1024),
            }
        )
    return linhas


# ----------------------------------------------------------------- migração
def _localidade_do_csv(caminho: Path) -> tuple[str, str]:
    """Devolve (localidade para o nome, data YYYY-MM-DD_HHhMM) de um arquivo antigo."""
    try:
        df = pd.read_csv(
            caminho,
            dtype=str,
            keep_default_na=False,
            usecols=lambda coluna: coluna in {"localidade", "coletado_em"},
        )
    except (OSError, ValueError, pd.errors.ParserError):
        df = pd.DataFrame()

    localidade = "Localidade"
    if "localidade" in df.columns:
        unicos = list(
            dict.fromkeys(str(v).strip() for v in df["localidade"] if str(v).strip())
        )
        if len(unicos) == 1:
            localidade = unicos[0]
        elif unicos:
            localidade = "Várias localidades"

    data = ""
    if _PADRAO_EXPORT_ANTIGO.match(caminho.name):
        # Exportação: o que importa é quando foi baixada, e isso está no nome.
        bruto = caminho.stem.removeprefix("leads_")
        return localidade, f"{bruto[:4]}-{bruto[4:6]}-{bruto[6:8]}_{bruto[9:11]}h{bruto[11:13]}"
    if "coletado_em" in df.columns:
        for valor in df["coletado_em"]:
            achado = re.match(r"(\d{4}-\d{2}-\d{2})[ T](\d{2}):(\d{2})", str(valor))
            if achado:
                data = max(data, f"{achado.group(1)}_{achado.group(2)}h{achado.group(3)}")
    if not data:
        data = datetime.fromtimestamp(caminho.stat().st_mtime).strftime(_FORMATO_DATA)
    return localidade, data


def migrar_nomes_legados() -> list[Path]:
    """Renomeia caches em hash e exports antigos para nomes com lugar e data."""
    renomeados = []
    for caminho in list(arquivos_leads()):
        if partes_nome(caminho):
            continue
        exportado = bool(_PADRAO_EXPORT_ANTIGO.match(caminho.name))
        legado = bool(_PADRAO_HASH.match(caminho.name))
        if not exportado and not legado:
            continue

        localidade, data = _localidade_do_csv(caminho)
        escopo = "exportado" if exportado else "legado"
        destino = _caminho_livre(
            constantes.DATA_DIR / f"leads__{nome_legivel(localidade)}__{escopo}__{data}.csv"
        )
        os.replace(caminho, destino)
        if not _meta_path(destino).exists():
            gravar_meta(destino, localidade, None, None, escopo)
        renomeados.append(destino)
    return renomeados
