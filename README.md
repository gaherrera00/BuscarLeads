# 📍 Busca de Leads

Aplicação em **Streamlit** para prospectar estabelecimentos com dados abertos do **OpenStreetMap**: busca por região e nicho, identifica oportunidades (sem site, só rede social), acompanha o status de contato e exporta os resultados. A **Pesquisa avançada** complementa leads promissores com os dados do Google Places.

## ▶️ Como rodar

```bash
pip install -r requirements.txt
streamlit run app.py
```

Ao abrir, o app carrega sozinho o CSV mais recente (sem acessar a internet), então o **Dashboard de leads** já aparece preenchido.

## 🗂️ Estrutura do código

```
app.py                         # ponto de entrada (3 linhas)
buscarleads/
├── constantes.py              # caminhos, nichos, colunas, esquemas de CSV
├── contato.py                 # e-mail de contato, nome do vendedor, última busca
├── normalizacao.py            # telefone, URL, e-mail, pontuação
├── osm.py                     # coleta Nominatim/Overpass
├── mensagens.py               # modelos de mensagem e links de WhatsApp
├── dados/                     # leitura/gravação dos CSVs (sem Streamlit)
│   ├── arquivos.py            # nomes legíveis, "mais recente", validade, migração
│   ├── leads.py               # ler/carregar base, edição direta no CSV
│   ├── status.py              # status e observações
│   ├── google.py              # cache do Google Places (enriquecido.csv)
│   ├── concorrencia.py        # cache de concorrência
│   ├── tabelas.py             # leitura com cache e gravação atômica
│   └── avisos.py              # avisos da camada de dados para a tela
├── servicos/                  # APIs pagas
│   ├── google_places.py       # busca com todos os campos
│   └── serper.py              # concorrência
└── ui/                        # uma tela por arquivo
    ├── app.py                 # ordem das abas e fluxo da página
    ├── dashboard.py  leads.py  pesquisa.py  mapa.py  configuracoes.py
    └── estado.py  sidebar.py  filtros.py  componentes.py  tema.py
tests/                         # pytest: dados, edição, APIs (simuladas) e interface
```

Para adicionar uma aba: crie `ui/minha_aba.py` com `renderizar_minha_aba(...)` e inclua em `ABAS` e no `with` correspondente em `ui/app.py`.

## 💾 Arquivos CSV

```
dados_osm/
├── leads__São Caetano do Sul, SP__area__2026-11-10_21h05.csv   # uma coleta
├── leads__São Caetano do Sul, SP__raio 3 km__2026-11-10_21h05.csv
├── status_leads.csv        # status/observação por lead
├── enriquecido.csv         # dados do Google por lead
├── concorrencia.csv        # concorrência por nicho+cidade
├── config.json             # e-mail, nome, última busca
└── _backup/                # original de cada CSV, guardado antes da 1ª correção
```

- **Nome**: lugar + abrangência (`area` / `raio N km`) + data e hora da coleta. Duas coletas no mesmo minuto ganham `-2`, `-3`…
- **Leitura**: para cada busca, o app usa **sempre o arquivo mais recente com o mesmo lugar, abrangência e nichos**. A data vem do nome do arquivo, não do disco.
- **Validade do cache**: contada pela data da coleta (padrão 30 dias). Arquivos antigos sem registro de nicho/raio só servem para busca por área inteira.
- **Correções sem nova coleta**: na aba **Leads**, edite nome, telefone, e-mail, site, Instagram, Facebook, endereço, status e observação direto na tabela e clique em **Salvar alterações**. As correções vão para o próprio CSV; a pontuação é recalculada; o original fica em `_backup/`. Se você forçar uma nova coleta depois, os campos que corrigiu são mantidos.

## 🔍 Pesquisa avançada

Requer `GOOGLE_PLACES_API_KEY` (e opcionalmente `SERPER_API_KEY`) no `.env`.

1. Escolha leads (por padrão só *Respondeu*, *Reunião marcada* e *Fechado*; há opção para qualquer status).
2. A tela mostra **quantas consultas pagas** serão feitas. Leads já salvos (✓) são lidos do CSV sem custo.
3. **Puxar informações** faz uma chamada por lead, **grava na hora** e **exibe** a ficha completa.

A ficha traz: nota e avaliações, situação do negócio, telefones, horários, preço, tipos, resumos (editorial e por IA), comodidades, pagamento, estacionamento, acessibilidade, avaliações recentes, links do Maps, comparação do site no Google × OpenStreetMap, concorrência, e a **resposta completa da API** (`gmn_json`). Cada consulta guarda também a **confiança do casamento** (nome e distância) para evitar usar dados de outro estabelecimento.

**Custo** (tabela de preços do Google, confira a atual): o app pede todos os campos (`X-Goog-FieldMask: *`) → nível *Text Search Enterprise + Atmosphere*, US$ 40 por 1.000 consultas, com 1.000 gratuitas por mês. Os campos que o app já pedia antes estavam no nível *Enterprise* (US$ 35), então pedir tudo custa só US$ 5 a mais por mil.

⚠️ **Termos do Google sobre guardar dados.** Os termos do Google permitem guardar o `place_id` sem prazo e coordenadas por até 30 dias; não encontrei, na fonte oficial, permissão explícita para manter nota, avaliações e horários indefinidamente. O app guarda tudo (como pedido) e **sinaliza dados com mais de 30 dias** na ficha. Avalie o seu caso de uso; se precisar de conformidade estrita, guarde só `gmn_place_id` e consulte de novo quando precisar.

## 🧪 Testes

```bash
pip install -r requirements-dev.txt
python -m pytest tests -q
```

As chamadas ao Google/Serper são simuladas nos testes (formato documentado da API); nenhum teste gasta cota.

## ⚖️ Fonte e uso responsável

Dados © OpenStreetMap contributors (ODbL 1.0). A ausência de dado no OSM não prova que o site não exista. Ao abordar, identifique-se, ofereça opção de não receber contato, evite disparos em massa e respeite a LGPD.
