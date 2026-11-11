"""Itens 1 e 5 do pedido, pela interface de verdade (Streamlit AppTest)."""

from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from buscarleads.dados import google as G
from buscarleads.servicos import google_places as GP
from buscarleads.servicos.google_places import ResultadoGoogle
from conftest import criar_csv, lead
from test_pesquisa_avancada import LUGAR_COMPLETO

APP = str(Path(__file__).resolve().parent.parent / "app.py")
ARQ = "leads__Cidade Teste, SP__area__2026-11-09_10h00.csv"


@pytest.fixture
def app(pasta, monkeypatch):
    monkeypatch.setenv("GOOGLE_PLACES_API_KEY", "chave-falsa")
    monkeypatch.delenv("SERPER_API_KEY", raising=False)
    criar_csv(
        pasta,
        ARQ,
        [
            lead("node/1", "Padaria Sol"),
            lead("node/2", "Oficina Lua", telefone="(11) 4000-1000"),
        ],
        {"localidade": "Cidade Teste, SP", "grupos": ["Alimentação"]},
    )
    pd.DataFrame(
        [
            {
                "osm_id": "node/1",
                "status": "Respondeu",
                "observacao": "",
                "atualizado_em": "2026-11-10 10:00",
            }
        ]
    ).to_csv(pasta / "status_leads.csv", index=False)
    return AppTest.from_file(APP, default_timeout=60)


def test_primeira_aba_e_o_dashboard_ja_preenchido_ao_abrir(app):
    at = app.run()
    assert not at.exception
    assert [t.label for t in at.tabs][0] == "Dashboard de leads"
    dash = at.tabs[0]
    assert not dash.info  # sem "ainda não há base carregada"
    assert dict((m.label, m.value) for m in dash.metric)["Leads na base"] == "2"
    assert any(ARQ in c.value for c in dash.caption)  # mostra qual CSV está em uso
    assert [s.value for s in dash.subheader][0] == "Melhores oportunidades"


def test_dashboard_vazio_sem_csv_orienta_o_usuario(pasta):
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception and "Ainda não há uma base" in at.tabs[0].info[0].value


def test_abre_o_csv_mais_recente_da_pasta(app, pasta):
    criar_csv(
        pasta,
        "leads__Cidade Teste, SP__area__2026-11-10_09h00.csv",
        [lead("node/9", "Nova")],
        {"localidade": "Cidade Teste, SP", "grupos": ["Alimentação"]},
    )
    at = app.run()
    assert at.session_state["base"]["osm_id"].tolist() == ["node/9"]


def test_filtros_ficam_na_lateral_e_abas_sao_as_primeiras(app):
    at = app.run()
    assert "Filtros dos resultados" in [e.label for e in at.sidebar.expander]
    assert [t.label for t in at.tabs] == [
        "Dashboard de leads",
        "Leads",
        "Pesquisa avançada",
        "Mapa",
        "Configurações",
    ]


def test_todas_as_abas_renderizam_sem_erro(app):
    at = app.run()
    assert not at.exception
    assert any("Salvar alterações" in b.label for b in at.tabs[1].button)


def _espiao(monkeypatch):
    chamadas = []

    def falso(nome, localidade, lat, lon, **_):
        chamadas.append(nome)
        return ResultadoGoogle("ok", GP.normalizar_lugar(LUGAR_COMPLETO, 0.9, 20.0))

    monkeypatch.setattr("buscarleads.ui.pesquisa.buscar_lugar", falso)
    return chamadas


def test_botao_puxar_exibe_os_dados_na_tela_e_grava_no_csv(app, pasta, monkeypatch):
    chamadas = _espiao(monkeypatch)
    at = app.run()
    at.multiselect(key="sel_pesquisa").set_value(["node/1"])
    at = at.run()
    assert "1 consulta(s) paga(s)" in at.tabs[2].info[0].value
    at.button(key="btn_puxar").click()
    at = at.run()

    assert not at.exception and chamadas == ["Padaria Sol"]
    aba = at.tabs[2]
    assert "1 nova(s)" in aba.success[0].value  # resumo da rodada
    metricas = dict((m.label, m.value) for m in aba.metric)
    assert (
        metricas["Nota"] == "4.6" and metricas["Avaliações"] == "312"
    )  # EXIBE, não só grava
    texto = " ".join([m.value for m in aba.markdown] + [c.value for c in aba.caption])
    assert "Padaria Sol Ltda" in texto and "Ótimo pão!" in texto  # reviews na tela
    assert any(
        "Nem o OpenStreetMap nem o Google listam site" in s.value for s in aba.success
    )
    # e também ficou salvo no CSV
    assert G.ler_enriquecido()["node/1"]["gmn_nota"] == "4.6"


def test_segundo_clique_nao_gasta_de_novo(app, monkeypatch):
    chamadas = _espiao(monkeypatch)
    at = app.run()
    at.multiselect(key="sel_pesquisa").set_value(["node/1"])
    at = at.run()
    at.button(key="btn_puxar").click()
    at = at.run()
    assert len(chamadas) == 1

    at.multiselect(key="sel_pesquisa").set_value(["node/1"])
    at = at.run()
    assert (
        "0 consulta(s) paga(s)"
        in [i.value for i in at.tabs[2].info if "paga" in i.value][0]
    )
    at.button(key="btn_puxar").click()
    at = at.run()
    assert len(chamadas) == 1  # reaproveitou do CSV
    assert "1 reaproveitada(s)" in at.tabs[2].success[0].value


def test_atualizar_forca_nova_consulta(app, monkeypatch):
    chamadas = _espiao(monkeypatch)
    at = app.run()
    at.multiselect(key="sel_pesquisa").set_value(["node/1"])
    at = at.run()
    at.button(key="btn_puxar").click()
    at = at.run()
    at.multiselect(key="sel_pesquisa").set_value(["node/1"])
    at.checkbox(key="pesq_atualizar").set_value(True)
    at = at.run()
    at.button(key="btn_puxar").click()
    at = at.run()
    assert len(chamadas) == 2


def test_ficha_salva_abre_sem_nova_consulta(app, monkeypatch):
    chamadas = _espiao(monkeypatch)
    at = app.run()
    at.multiselect(key="sel_pesquisa").set_value(["node/1"])
    at = at.run()
    at.button(key="btn_puxar").click()
    at = at.run()
    at.button(key="fechar_rodada").click()
    at = at.run()
    assert (
        not at.tabs[2].success
        or "Consulta concluída" not in at.tabs[2].success[0].value
    )
    assert (
        dict((m.label, m.value) for m in at.tabs[2].metric)["Nota"] == "4.6"
    )  # ficha dos dados salvos
    assert len(chamadas) == 1


def test_erro_da_api_aparece_na_tela_e_nao_e_cobrado(app, pasta, monkeypatch):
    monkeypatch.setattr(
        "buscarleads.ui.pesquisa.buscar_lugar",
        lambda *a, **k: ResultadoGoogle("erro", erro="HTTP 403 — PERMISSION_DENIED"),
    )
    at = app.run()
    at.multiselect(key="sel_pesquisa").set_value(["node/1"])
    at = at.run()
    at.button(key="btn_puxar").click()
    at = at.run()
    assert any("PERMISSION_DENIED" in e.value for e in at.tabs[2].error)
    assert not (pasta / "enriquecido.csv").exists()  # nada salvo = pode tentar de novo


def test_sem_chaves_a_aba_explica_o_que_fazer(app, monkeypatch):
    monkeypatch.delenv("GOOGLE_PLACES_API_KEY")
    at = app.run()
    assert any("GOOGLE_PLACES_API_KEY" in w.value for w in at.tabs[2].warning)


# ------------------------------------------------- exportação direto em dados_osm
def test_botao_salva_o_csv_direto_na_pasta_de_dados(app, pasta):
    at = app.run()
    antes = set(p.name for p in pasta.glob("*.csv"))
    at.button(key="salvar_exportacao").click()
    at = at.run()
    assert not at.exception

    novos = [p for p in pasta.glob("leads__*__exportado__*.csv") if p.name not in antes]
    assert len(novos) == 1
    assert novos[0].name.startswith("leads__Cidade Teste, SP__exportado__")
    assert any(
        str(novos[0]) in s.value for s in at.tabs[1].success
    )  # mostra onde salvou

    exportado = pd.read_csv(novos[0], dtype=str, keep_default_na=False)
    assert {"mensagem_pronta", "whatsapp_url", "fonte_dados", "nome"} <= set(
        exportado.columns
    )
    assert "Padaria Sol" in exportado["nome"].tolist()
    assert exportado["mensagem_pronta"].str.contains("Padaria Sol").any()
    assert (
        novos[0].read_bytes().startswith(b"\xef\xbb\xbf")
    )  # UTF-8 com BOM: Excel abre com acento


def test_exportacao_nao_vira_cache_nem_e_aberta_ao_iniciar(app, pasta):
    at = app.run()
    at.button(key="salvar_exportacao").click()
    at = at.run()
    from buscarleads.dados import arquivos

    assert (
        arquivos.cache_mais_recente("Cidade Teste, SP", None, ["Alimentação"])[0].name
        == ARQ
    )
    assert arquivos.ultimo_arquivo_geral().name == ARQ
    assert AppTest.from_file(APP, default_timeout=60).run().session_state["base"][
        "osm_id"
    ].tolist() == ["node/1", "node/2"]


def test_duas_exportacoes_no_mesmo_minuto_nao_se_sobrescrevem(app, pasta):
    at = app.run()
    for _ in range(2):
        at.button(key="salvar_exportacao").click()
        at = at.run()
    assert len(list(pasta.glob("leads__*__exportado__*.csv"))) == 2
