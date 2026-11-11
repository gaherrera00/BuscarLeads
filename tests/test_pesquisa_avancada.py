"""Item 5 do pedido: tudo que a API devolve, salvo no CSV e sem gasto repetido."""

import json

import pandas as pd
import requests

from buscarleads.constantes import COLUNAS_GOOGLE
from buscarleads.dados import concorrencia as C, google as G
from buscarleads.mensagens import texto_abordagem, trecho_nota
from buscarleads.servicos import google_places as GP, serper as SP

LUGAR_COMPLETO = {
    "id": "ChIJabc123",
    "displayName": {"text": "Padaria Sol Ltda", "languageCode": "pt-BR"},
    "formattedAddress": "Rua A, 10 - Centro, São Caetano do Sul - SP",
    "location": {"latitude": -23.6001, "longitude": -46.5001},
    "businessStatus": "OPERATIONAL",
    "primaryType": "bakery", "primaryTypeDisplayName": {"text": "Padaria"},
    "types": ["bakery", "food", "store"],
    "rating": 4.6, "userRatingCount": 312,
    "nationalPhoneNumber": "(11) 4221-3344", "internationalPhoneNumber": "+55 11 4221-3344",
    "priceLevel": "PRICE_LEVEL_MODERATE",
    "priceRange": {"startPrice": {"currencyCode": "BRL", "units": "10"}, "endPrice": {"currencyCode": "BRL", "units": "30"}},
    "regularOpeningHours": {"openNow": True, "weekdayDescriptions": ["segunda: 06:00–20:00", "domingo: Fechado"]},
    "editorialSummary": {"text": "Padaria de bairro."},
    "generativeSummary": {"overview": {"text": "Pães frescos e café."}},
    "reviewSummary": {"text": {"text": "Clientes elogiam o pão."}},
    "delivery": True, "dineIn": True, "takeout": True, "reservable": False, "servesCoffee": True,
    "paymentOptions": {"acceptsCreditCards": True, "acceptsCashOnly": False},
    "parkingOptions": {"freeStreetParking": True},
    "accessibilityOptions": {"wheelchairAccessibleEntrance": True},
    "googleMapsUri": "https://maps.google.com/?cid=1",
    "googleMapsLinks": {"reviewsUri": "https://maps.google.com/reviews"},
    "photos": [{}, {}, {}],
    "reviews": [{"rating": 5, "text": {"text": "Ótimo pão!"}, "relativePublishTimeDescription": "há 2 meses",
                 "authorAttribution": {"displayName": "Ana"}}],
}


class Resp:
    def __init__(self, codigo=200, corpo=None, razao="OK"):
        self.status_code, self._corpo, self.reason = codigo, corpo if corpo is not None else {}, razao

    def json(self):
        if self._corpo == "lixo":
            raise ValueError("x")
        return self._corpo

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")


class Sessao:
    """Falsa 'requests': registra chamadas e devolve respostas prontas."""
    def __init__(self, *respostas, erro=None):
        self.respostas, self.chamadas, self.erro = list(respostas), [], erro

    def post(self, url, json=None, headers=None, timeout=None):
        self.chamadas.append({"url": url, "json": json, "headers": headers})
        if self.erro:
            raise self.erro
        return self.respostas.pop(0)


def buscar(sessao, nome="Padaria Sol", chave="K"):
    return GP.buscar_lugar(nome, "São Caetano do Sul, SP", -23.6, -46.5, chave=chave, sessao=sessao)


# ------------------------------------------------------------- pedido à API
def test_pede_todos_os_campos_numa_unica_chamada():
    s = Sessao(Resp(corpo={"places": [LUGAR_COMPLETO]}))
    buscar(s)
    assert len(s.chamadas) == 1
    assert s.chamadas[0]["headers"]["X-Goog-FieldMask"] == "*"
    assert s.chamadas[0]["json"]["locationBias"]["circle"]["radius"] == 500.0
    assert s.chamadas[0]["headers"]["X-Goog-Api-Key"] == "K"


def test_extrai_todos_os_campos_para_as_colunas():
    r = buscar(Sessao(Resp(corpo={"places": [LUGAR_COMPLETO]})))
    d = r.dados
    assert r.status == "ok" and r.cobrado
    assert d["gmn_nota"] == 4.6 and d["gmn_avaliacoes"] == 312
    assert d["gmn_site"] == "" and d["gmn_telefone"] == "(11) 4221-3344"
    assert d["gmn_situacao"] == "Operacional" and d["gmn_nivel_preco"] == "$$"
    assert d["gmn_faixa_preco"] == "BRL 10 – BRL 30"
    assert d["gmn_horario"] == "segunda: 06:00–20:00 | domingo: Fechado"
    assert d["gmn_servicos"] == "Delivery, Consumo no local, Para viagem, Café"  # só os True
    assert d["gmn_pagamento"] == "Cartão de crédito" and d["gmn_estacionamento"] == "Rua gratuita"
    assert d["gmn_resumo"] == "Padaria de bairro." and d["gmn_resumo_ia"] == "Pães frescos e café."
    assert d["gmn_resumo_avaliacoes"] == "Clientes elogiam o pão."
    assert "Ótimo pão!" in d["gmn_reviews"] and d["gmn_fotos"] == 3
    assert d["gmn_place_id"] == "ChIJabc123" and d["gmn_tipo_principal"] == "Padaria"
    assert json.loads(d["gmn_json"])["id"] == "ChIJabc123"  # resposta completa preservada


def test_so_devolve_colunas_conhecidas():
    d = buscar(Sessao(Resp(corpo={"places": [LUGAR_COMPLETO]}))).dados
    assert set(d) <= set(COLUNAS_GOOGLE) - {"osm_id", "atualizado_em"}


def test_resposta_minima_nao_quebra():
    r = buscar(Sessao(Resp(corpo={"places": [{"id": "X", "displayName": {"text": "Padaria Sol"}}]})))
    assert r.status == "ok" and r.dados["gmn_nota"] == "" and r.dados["gmn_horario"] == ""


# --------------------------------------------------------------- escolha
def test_escolhe_o_candidato_certo_e_nao_o_primeiro():
    errado = {**LUGAR_COMPLETO, "id": "ERRADO", "displayName": {"text": "Banco Central"},
              "location": {"latitude": -23.7, "longitude": -46.7}}
    r = buscar(Sessao(Resp(corpo={"places": [errado, LUGAR_COMPLETO]})))
    assert r.dados["gmn_place_id"] == "ChIJabc123" and r.dados["gmn_confianca"] == "alta"


def test_confianca_baixa_quando_e_outro_lugar():
    outro = {**LUGAR_COMPLETO, "displayName": {"text": "Farmácia Lua"}, "location": {"latitude": -23.65, "longitude": -46.5}}
    r = buscar(Sessao(Resp(corpo={"places": [outro]})))
    assert r.dados["gmn_confianca"] == "baixa"


def test_similaridade_reconhece_nome_contido():
    assert GP.similaridade("Padaria Sol", "Padaria Sol Ltda") >= 0.9
    assert GP.similaridade("Padaria Sol", "Oficina Lua") < 0.5


# --------------------------------------------------------- falhas explícitas
def test_sem_chave_nao_chama_a_api():
    s = Sessao()
    r = buscar(s, chave="")
    assert r.status == "sem_chave" and not r.cobrado and s.chamadas == []


def test_nao_encontrado_e_cobrado_e_guardavel():
    r = buscar(Sessao(Resp(corpo={})))
    assert r.status == "nao_encontrado" and r.cobrado and r.dados["gmn_status"] == "nao_encontrado"


def test_erro_403_explica_o_motivo_e_nao_cobra():
    corpo = {"error": {"code": 403, "status": "PERMISSION_DENIED", "message": "API has not been used"}}
    r = buscar(Sessao(Resp(403, corpo, "Forbidden")))
    assert r.status == "erro" and not r.cobrado
    assert "PERMISSION_DENIED" in r.erro and "Places API (New)" in r.erro


def test_erro_de_rede_e_json_invalido_viram_erro_legivel():
    assert "rede" in buscar(Sessao(erro=requests.ConnectionError("sem internet"))).erro
    assert "JSON" in buscar(Sessao(Resp(corpo="lixo"))).erro


# ------------------------------------------------------------ cache em CSV
def test_cache_guarda_tudo_e_sobrevive_a_novas_gravacoes(pasta):
    d1 = buscar(Sessao(Resp(corpo={"places": [LUGAR_COMPLETO]}))).dados
    G.salvar_enriquecido("node/1", d1)
    G.salvar_enriquecido("node/2", {"gmn_status": "nao_encontrado"})
    lido = G.ler_enriquecido()
    assert set(lido) == {"node/1", "node/2"}
    assert lido["node/1"]["gmn_nota"] == "4.6" and lido["node/1"]["gmn_servicos"].startswith("Delivery")
    assert json.loads(lido["node/1"]["gmn_json"])["rating"] == 4.6
    assert lido["node/1"]["atualizado_em"] != ""
    assert list(pd.read_csv(pasta / "enriquecido.csv").columns) == COLUNAS_GOOGLE


def test_formato_antigo_de_4_colunas_ainda_le(pasta):
    (pasta / "enriquecido.csv").write_text(
        "osm_id,gmn_nota,gmn_avaliacoes,gmn_site,gmn_telefone,atualizado_em\nnode/1,4.5,10,,(11) 1,2026-11-01 10:00\n")
    r = G.ler_enriquecido()["node/1"]
    assert r["gmn_nota"] == "4.5" and r["gmn_json"] == ""


def test_mescla_na_base_sem_chamar_api(pasta):
    G.salvar_enriquecido("node/1", {"gmn_status": "ok", "gmn_nota": "4.6", "gmn_avaliacoes": "312", "gmn_confianca": "alta"})
    base = pd.DataFrame({"osm_id": ["node/1", "node/2"]})
    m = G.mesclar_enriquecimento(base).set_index("osm_id")
    assert m.at["node/1", "gmn_nota"] == "4.6" and m.at["node/2", "gmn_nota"] == ""
    assert G.mesclar_enriquecimento(base.iloc[0:0]).empty


# ------------------------------------------------------------- mensagens
def test_mensagem_ignora_nota_quando_confianca_baixa():
    ok = {"nome": "X", "nicho": "Padaria", "localidade": "SCS, SP", "gmn_nota": "4.6", "gmn_avaliacoes": "312", "gmn_confianca": "alta"}
    assert "4.6" in trecho_nota(ok) and "312" in trecho_nota(ok)
    assert trecho_nota({**ok, "gmn_confianca": "baixa"}) == "ótimo perfil"
    msg = texto_abordagem({**ok, "gmn_confianca": "baixa"}, "Oi {nome}", "Eu")
    assert msg == "Oi X"  # sem nota confiável cai no modelo genérico


# ----------------------------------------------------------------- Serper
def serper(*titulos_links):
    return {"organic": [{"title": t, "link": l} for t, l in titulos_links]}


def test_serper_ignora_artigos_e_diretorios_e_acha_concorrente_real(pasta):
    s = Sessao(Resp(corpo=serper(
        ("As 5 Melhores Oficinas Mecânicas em São Caetano do Sul", "https://blog.com/a"),
        ("Oficinas em SCS - Guia Mais", "https://guiamais.com.br/x"),
        ("Auto Center Beta - Rua X, 100", "https://www.autobeta.com.br/"),
    )))
    dados, erro, consultou = SP.buscar_concorrencia("Oficina", "São Caetano do Sul", chave="K", sessao=s)
    assert erro == "" and consultou
    assert dados["melhor_concorrente"] == "Auto Center Beta"
    assert dados["melhor_concorrente_link"] == "autobeta.com.br"


def test_serper_cache_evita_segunda_cobranca(pasta):
    s = Sessao(Resp(corpo=serper(("Auto Beta", "https://autobeta.com.br"))))
    SP.buscar_concorrencia("Oficina", "SCS", chave="K", sessao=s)
    _, _, consultou = SP.buscar_concorrencia("Oficina", "SCS", chave="K", sessao=s)
    assert not consultou and len(s.chamadas) == 1


def test_serper_sem_resultados_tambem_fica_em_cache(pasta):
    s = Sessao(Resp(corpo={"organic": []}))
    SP.buscar_concorrencia("Oficina", "SCS", chave="K", sessao=s)
    SP.buscar_concorrencia("Oficina", "SCS", chave="K", sessao=s)
    assert len(s.chamadas) == 1


def test_serper_entrada_antiga_com_titulo_de_artigo_e_refeita(pasta):
    C.salvar_serp_cache(C.chave_serp("Oficina", "SCS"),
                        {"concorrentes_com_site": "1", "total_concorrentes": "3",
                         "melhor_concorrente": "As 5 Melhores Oficinas Mecânicas em São Caetano do Sul ..."})
    assert C.gancho_concorrencia("Oficina", "SCS") == {}  # não vai para a mensagem
    s = Sessao(Resp(corpo=serper(("Auto Beta", "https://autobeta.com.br"))))
    _, _, consultou = SP.buscar_concorrencia("Oficina", "SCS", chave="K", sessao=s)
    assert consultou


def test_serper_erro_e_sem_chave_sao_explicitos(pasta):
    assert "SERPER_API_KEY" in SP.buscar_concorrencia("a", "b", chave="")[1]
    _, erro, _ = SP.buscar_concorrencia("a", "b", chave="K", sessao=Sessao(erro=requests.Timeout("t")))
    assert "Serper" in erro
