"""Sem edição do usuário, nada pode ser considerado alteração (evita reescrever CSVs à toa)."""


from buscarleads.dados import leads as L
from buscarleads.dados.google import mesclar_enriquecimento
from buscarleads.ui.leads import diferencas_dados, preparar_tabela
from conftest import criar_csv, lead

ARQ = "leads__Cidade Teste, SP__area__2026-11-09_10h00.csv"


def _base(pasta):
    criar_csv(pasta, ARQ, [
        lead("node/1", "Com tudo", site="https://x.com", instagram="https://instagram.com/x", email="a@b.com"),
        lead("node/2", "Site invalido", site="facebook", status_site="Só rede social"),
        lead("node/3", "Vazio"),
    ], {"localidade": "Cidade Teste, SP", "grupos": ["A"]})
    base, _, _ = L.carregar_base(["Cidade Teste, SP"], None, ["A"], False, None, somente_cache=True)
    base["status"], base["observacao"] = "Novo", ""
    return mesclar_enriquecimento(base)


def test_sem_editar_nada_nao_ha_diferencas(pasta):
    tabela = preparar_tabela(_base(pasta), 100, "Oi {nome}")
    assert diferencas_dados(tabela.copy(), tabela) == {}


def test_editar_um_campo_gera_exatamente_uma_diferenca(pasta):
    tabela = preparar_tabela(_base(pasta), 100, "Oi {nome}")
    editado = tabela.copy()
    editado.loc[editado["osm_id"] == "node/3", "email"] = "  novo@x.com "
    assert diferencas_dados(editado, tabela) == {"node/3": {"email": "novo@x.com"}}


def test_apagar_um_campo_e_uma_edicao_valida(pasta):
    tabela = preparar_tabela(_base(pasta), 100, "Oi {nome}")
    editado = tabela.copy()
    editado.loc[editado["osm_id"] == "node/1", "instagram"] = None
    assert diferencas_dados(editado, tabela) == {"node/1": {"instagram": ""}}
    r = L.aplicar_edicoes({"node/1": {"instagram": ""}}, {"node/1": ARQ})
    assert r.gravadas == 1 and L.ler_csv(pasta / ARQ).set_index("osm_id").at["node/1", "instagram"] == ""


def test_status_e_observacao_nao_viram_edicao_de_dados(pasta):
    tabela = preparar_tabela(_base(pasta), 100, "Oi {nome}")
    editado = tabela.copy(); editado["status"] = "Contatado"; editado["observacao"] = "ligar"
    assert diferencas_dados(editado, tabela) == {}


def test_tabela_traz_colunas_do_google(pasta):
    assert {"gmn_nota", "gmn_avaliacoes"} <= set(preparar_tabela(_base(pasta), 100, "x").columns)
