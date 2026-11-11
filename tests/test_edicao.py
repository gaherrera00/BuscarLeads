"""Item 4 do pedido: alterar dados no CSV sem refazer a coleta."""

import pandas as pd

from buscarleads.constantes import COLUNAS
from buscarleads.dados import leads as L, status as S
from conftest import criar_csv, lead

NOME = "leads__Cidade Teste, SP__area__2026-11-09_10h00.csv"


def _dois(pasta):
    return criar_csv(
        pasta, NOME,
        [lead("node/1", "Padaria Sol"), lead("node/2", "Oficina Lua", telefone="", status_site="Sem site")],
        {"localidade": "Cidade Teste, SP", "grupos": ["Alimentação"]},
    )


def test_edicao_grava_no_proprio_csv_e_aparece_ao_reler(pasta):
    caminho = _dois(pasta)
    r = L.aplicar_edicoes(
        {"node/1": {"email": "contato@sol.com", "telefone": "11 98888-7777"}}, {"node/1": NOME}
    )
    assert r.gravadas == 1 and r.erros == []
    df = L.ler_csv(caminho).set_index("osm_id")
    assert df.at["node/1", "email"] == "contato@sol.com"
    assert df.at["node/1", "telefone"] == "(11) 98888-7777"
    assert df.at["node/1", "whatsapp_num"] == "11988887777"  # celular novo vira WhatsApp
    assert df.at["node/1", "editado_campos"] == "email;telefone"
    assert df.at["node/1", "editado_em"] != ""


def test_pontuacao_e_situacao_do_site_acompanham_a_correcao(pasta):
    caminho = _dois(pasta)
    antes = L.ler_csv(caminho).set_index("osm_id").at["node/1", "pontuacao"]
    L.aplicar_edicoes({"node/1": {"site": "padariasol.com.br"}}, {"node/1": NOME})
    d = L.ler_csv(caminho).set_index("osm_id")
    assert d.at["node/1", "site"] == "https://padariasol.com.br"
    assert d.at["node/1", "status_site"] == "Com site"
    assert d.at["node/1", "pontuacao"] < antes  # ter site tira os 3 pontos


def test_telefone_fixo_novo_limpa_whatsapp_antigo(pasta):
    caminho = criar_csv(pasta, NOME, [lead(telefone="(11) 98888-7777", whatsapp_num="11988887777")],
                        {"localidade": "Cidade Teste, SP", "grupos": ["A"]})
    L.aplicar_edicoes({"node/1": {"telefone": "(11) 4221-3344"}}, {"node/1": NOME})
    d = L.ler_csv(caminho).iloc[0]
    assert d["whatsapp_num"] == "" and d["whatsapp_tentativa"] == "1142213344"


def test_outras_linhas_e_colunas_ficam_intactas(pasta):
    caminho = _dois(pasta)
    antes = pd.read_csv(caminho, dtype=str, keep_default_na=False)
    pontuacao_antes = int(L.ler_csv(caminho).at[0, "pontuacao"])  # o app sempre recalcula
    L.aplicar_edicoes({"node/1": {"email": "a@b.com"}}, {"node/1": NOME})
    depois = pd.read_csv(caminho, dtype=str, keep_default_na=False)
    assert list(depois.columns) == COLUNAS and len(depois) == 2
    pd.testing.assert_series_equal(antes.loc[1], depois.loc[1])  # linha 2 idêntica
    mudaveis = ["email", "pontuacao", "editado_campos", "editado_em"]  # pontuação sobe com e-mail válido
    assert antes.loc[0].drop(mudaveis).equals(depois.loc[0].drop(mudaveis))
    assert int(depois.at[0, "pontuacao"]) == pontuacao_antes + 1


def test_guarda_backup_do_original_so_na_primeira_vez(pasta):
    caminho = _dois(pasta)
    original = caminho.read_bytes()
    L.aplicar_edicoes({"node/1": {"email": "a@b.com"}}, {"node/1": NOME})
    L.aplicar_edicoes({"node/1": {"email": "c@d.com"}}, {"node/1": NOME})
    backup = pasta / "_backup" / NOME
    assert backup.read_bytes() == original
    assert caminho.read_bytes() != original


def test_backup_nao_e_confundido_com_cache(pasta):
    from buscarleads.dados import arquivos
    _dois(pasta); L.aplicar_edicoes({"node/1": {"email": "a@b.com"}}, {"node/1": NOME})
    assert [p.name for p in arquivos.arquivos_leads()] == [NOME]


def test_valores_invalidos_sao_recusados_sem_gravar(pasta):
    caminho = _dois(pasta); antes = caminho.read_bytes()
    r = L.aplicar_edicoes(
        {"node/1": {"email": "isso-nao-e-email", "site": "sem ponto nem url", "nome": "  "}}, {"node/1": NOME}
    )
    assert r.gravadas == 0 and len(r.erros) == 3
    assert caminho.read_bytes() == antes  # nada gravado nem backup criado
    assert not (pasta / "_backup").exists()


def test_arquivo_ou_linha_inexistente_vira_erro_e_nao_excecao(pasta):
    _dois(pasta)
    r = L.aplicar_edicoes({"node/99": {"email": "a@b.com"}, "node/1": {"email": "a@b.com"}},
                          {"node/99": NOME, "node/1": "nao_existe.csv"})
    assert r.gravadas == 0 and len(r.erros) == 2


def test_valor_igual_ao_atual_nao_conta_como_edicao(pasta):
    caminho = _dois(pasta); antes = caminho.read_bytes()
    r = L.aplicar_edicoes({"node/1": {"nome": "Padaria Sol"}}, {"node/1": NOME})
    assert r.gravadas == 0 and caminho.read_bytes() == antes


def test_nova_coleta_preserva_apenas_os_campos_corrigidos(pasta):
    caminho = _dois(pasta)
    L.aplicar_edicoes({"node/1": {"email": "meu@email.com"}}, {"node/1": NOME})
    # nova coleta: o OSM agora tem outro telefone para o lead 1
    nova = pd.DataFrame([lead("node/1", "Padaria Sol", telefone="(11) 3000-1111")], columns=COLUNAS)
    herdadas = L.herdar_edicoes(nova, caminho)
    assert herdadas == 1
    linha = nova.iloc[0]
    assert linha["email"] == "meu@email.com"          # correção do usuário mantida
    assert linha["telefone"] == "(11) 3000-1111"      # dado novo do OSM NÃO sobrescrito
    assert linha["editado_campos"] == "email"


def test_nova_coleta_ignora_lugar_que_sumiu_do_osm(pasta):
    caminho = _dois(pasta)
    L.aplicar_edicoes({"node/1": {"email": "a@b.com"}}, {"node/1": NOME})
    nova = pd.DataFrame([lead("node/2", "Oficina Lua")], columns=COLUNAS)
    assert L.herdar_edicoes(nova, caminho) == 0


def test_carregar_base_mostra_a_correcao_sem_rede(pasta):
    _dois(pasta); L.aplicar_edicoes({"node/1": {"email": "a@b.com"}}, {"node/1": NOME})
    base, falhas, _ = L.carregar_base(["Cidade Teste, SP"], None, ["Alimentação"], False, 30, somente_cache=True)
    assert falhas == [] and base.set_index("osm_id").at["node/1", "email"] == "a@b.com"
    assert set(base["arquivo_origem"]) == {NOME}


def test_status_preserva_data_de_quem_nao_mudou(pasta):
    S.salvar_status(pd.DataFrame({"osm_id": ["node/1"], "status": ["Contatado"], "observacao": [""]}))
    f = pasta / "status_leads.csv"
    df = pd.read_csv(f, dtype=str); df["atualizado_em"] = "2020-01-01 00:00"; df.to_csv(f, index=False)
    S.salvar_status(pd.DataFrame({"osm_id": ["node/1", "node/2"], "status": ["Contatado", "Respondeu"],
                                  "observacao": ["", "ligar terça"]}))
    r = S.ler_status()
    assert r["node/1"]["atualizado_em"] == "2020-01-01 00:00"   # intacto (bug do original)
    assert r["node/2"]["atualizado_em"] != "2020-01-01 00:00"


def test_status_novo_sem_observacao_sai_do_arquivo(pasta):
    S.salvar_status(pd.DataFrame({"osm_id": ["node/1"], "status": ["Contatado"], "observacao": [""]}))
    assert S.salvar_status(pd.DataFrame({"osm_id": ["node/1"], "status": ["Novo"], "observacao": [""]})) == 1
    assert S.ler_status() == {}


def test_status_corrompido_vira_aviso_e_backup_sem_streamlit(pasta):
    from buscarleads.dados import avisos
    (pasta / "status_leads.csv").write_text("lixo,sem,colunas\n1,2,3\n")
    assert S.ler_status() == {}
    assert "ilegível" in avisos.consumir()[0]
    assert list(pasta.glob("status_leads_corrompido_*.csv"))
