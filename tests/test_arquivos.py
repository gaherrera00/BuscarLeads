"""Item 3 do pedido: nomes legíveis e leitura sempre do arquivo mais recente."""

from datetime import datetime


from buscarleads.dados import arquivos as a
from conftest import criar_csv, lead

GRUPOS = ["Alimentação", "Saúde"]
META = {"localidade": "São Caetano do Sul, SP", "raio_km": None, "grupos": GRUPOS}


def test_nome_contem_lugar_escopo_e_data():
    quando = datetime(2026, 11, 10, 21, 5)
    area = a.novo_caminho_cache("São Caetano do Sul, SP", None, quando).name
    raio = a.novo_caminho_cache("São Caetano do Sul, SP", 3, quando).name
    assert area == "leads__São Caetano do Sul, SP__area__2026-11-10_21h05.csv"
    assert raio == "leads__São Caetano do Sul, SP__raio 3 km__2026-11-10_21h05.csv"


def test_nome_de_exportacao_tem_lugar_e_data():
    assert a.nome_exportacao(["Santo André, SP"]).startswith(
        "leads__Santo André, SP__exportado__"
    )
    assert (
        a.partes_nome(
            __import__("pathlib").Path(a.nome_exportacao(["Santo André, SP"]))
        )["escopo"]
        == "exportado"
    )
    assert a.nome_exportacao(["A", "B", "C", "D"]).split("__")[1] == "A + B + C +1"


def test_nome_remove_caracteres_proibidos_no_windows():
    assert a.nome_legivel('A/B:C*D?"E') == "A B C D E"


def test_duas_coletas_no_mesmo_minuto_nao_se_sobrescrevem(pasta):
    q = datetime(2026, 11, 10, 21, 5)
    p1 = a.novo_caminho_cache("X", None, q)
    p1.write_text("a")
    p2 = a.novo_caminho_cache("X", None, q)
    assert p1 != p2 and p2.name.endswith("-2.csv")


def test_le_sempre_o_mais_recente(pasta):
    antigo = criar_csv(
        pasta,
        "leads__São Caetano do Sul, SP__area__2026-11-01_10h00.csv",
        [lead()],
        META,
    )
    novo = criar_csv(
        pasta,
        "leads__São Caetano do Sul, SP__area__2026-11-09_08h30.csv",
        [lead()],
        META,
    )
    meio = criar_csv(
        pasta,
        "leads__São Caetano do Sul, SP__area__2026-11-05_23h59.csv",
        [lead()],
        META,
    )
    achado, origem = a.cache_mais_recente("São Caetano do Sul, SP", None, GRUPOS)
    assert achado == novo and origem == "cache"
    assert achado not in (antigo, meio)


def test_mais_recente_nao_depende_do_mtime_do_disco(pasta):
    """Copiar/extrair a pasta muda o mtime; o app não pode se confundir."""
    import os, time

    velho = criar_csv(
        pasta,
        "leads__SCS__area__2026-11-01_10h00.csv",
        [lead()],
        {**META, "localidade": "SCS"},
    )
    novo = criar_csv(
        pasta,
        "leads__SCS__area__2026-11-09_10h00.csv",
        [lead()],
        {**META, "localidade": "SCS"},
    )
    os.utime(
        novo, (time.time() - 99999, time.time() - 99999)
    )  # "novo" com mtime antigo
    os.utime(velho, (time.time(), time.time()))
    assert a.cache_mais_recente("SCS", None, GRUPOS)[0] == novo


def test_empate_no_mesmo_minuto_vale_o_sufixo(pasta):
    criar_csv(
        pasta,
        "leads__SCS__area__2026-11-09_10h00.csv",
        [lead()],
        {**META, "localidade": "SCS"},
    )
    segundo = criar_csv(
        pasta,
        "leads__SCS__area__2026-11-09_10h00-2.csv",
        [lead()],
        {**META, "localidade": "SCS"},
    )
    assert a.cache_mais_recente("SCS", None, GRUPOS)[0] == segundo


def test_variacoes_do_nome_da_cidade_acham_o_mesmo_cache(pasta):
    arq = criar_csv(
        pasta,
        "leads__São Paulo__area__2026-11-09_10h00.csv",
        [lead()],
        {**META, "localidade": "São Paulo"},
    )
    for digitado in ("São Paulo", "Sao Paulo", "são paulo, SP", "SAO PAULO - SP"):
        assert a.cache_mais_recente(digitado, None, GRUPOS)[0] == arq


def test_nichos_ou_raio_diferentes_nao_reaproveitam_cache(pasta):
    criar_csv(
        pasta,
        "leads__SCS__area__2026-11-09_10h00.csv",
        [lead()],
        {**META, "localidade": "SCS"},
    )
    assert a.cache_mais_recente("SCS", None, ["Pet"])[0] is None
    assert a.cache_mais_recente("SCS", 3, GRUPOS)[0] is None


def test_exportacao_baixada_nunca_vira_cache(pasta):
    criar_csv(
        pasta,
        "leads__SCS__exportado__2026-11-09_10h00.csv",
        [lead()],
        {"localidade": "SCS", "grupos": None},
    )
    assert a.cache_mais_recente("SCS", None, GRUPOS)[0] is None
    assert a.ultimo_arquivo_geral() is None


def test_arquivo_legado_serve_area_mas_nunca_raio(pasta):
    leg = criar_csv(
        pasta,
        "leads__SCS__legado__2026-11-09_10h00.csv",
        [lead()],
        {"localidade": "SCS", "grupos": None},
    )
    assert a.cache_mais_recente("SCS", None, GRUPOS) == (leg, "cache antigo")
    assert a.cache_mais_recente("SCS", 3, GRUPOS)[0] is None  # bug do original


def test_validade_usa_a_data_do_nome_e_nao_o_mtime(pasta):
    velho = criar_csv(
        pasta, "leads__SCS__area__2020-01-01_10h00.csv", [lead()]
    )  # mtime = agora
    assert not a.cache_valido(velho, 30)
    hoje = a.novo_caminho_cache("SCS", None)
    criar_csv(pasta, hoje.name, [lead()])
    assert a.cache_valido(hoje, 30)


def test_migra_hash_e_export_antigo_para_nomes_legiveis(pasta):
    criar_csv(pasta, "leads_0123456789ab.csv", [lead()])
    criar_csv(pasta, "leads_20261109_2050.csv", [lead()])
    novos = {p.name for p in a.migrar_nomes_legados()}
    assert novos == {
        "leads__Cidade Teste, SP__legado__2026-11-09_10h00.csv",
        "leads__Cidade Teste, SP__exportado__2026-11-09_20h50.csv",
    }
    assert a.migrar_nomes_legados() == []  # idempotente


def test_ultimo_arquivo_geral_e_o_mais_novo(pasta):
    criar_csv(pasta, "leads__A__area__2026-11-01_10h00.csv", [lead()])
    b = criar_csv(pasta, "leads__B__area__2026-11-08_10h00.csv", [lead()])
    assert a.ultimo_arquivo_geral() == b
