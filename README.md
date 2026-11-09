# 📍 Busca de Leads

Aplicação em **Streamlit** para prospecção de estabelecimentos comerciais usando dados abertos do **OpenStreetMap**. Permite buscar negócios por região e nicho, identificar oportunidades (ex.: sem site/rede social), gerenciar status de contato e exportar os resultados.

## ✨ Funcionalidades

- **Busca geográfica**: por cidade/bairro (limite administrativo) ou raio em km a partir de um ponto central.
- **Filtro por nichos**: Alimentação, Beleza, Saúde, Serviços profissionais, Automotivo, Pet, Fitness/Educação, Varejo, Mercados.
- **Pontuação de oportunidade**: heurística baseada em presença de site, redes sociais, WhatsApp, e-mail e telefone.
- **Deduplicação aproximada**: remove leads duplicados por nome/telefone/endereço.
- **Cache local**: resultados salvos em CSV com TTL configurável, evitando novas consultas repetidas.
- **Edição de status**: acompanhamento de leads (Novo, Contatado, Respondeu, Reunião marcada, Fechado, Descartado) com observações persistidas.
- **Exportação CSV**: com proteção contra injeção de fórmulas no Excel.
- **Mapa e gráficos**: visualização geográfica e distribuição por nicho/situação/status.
- **Links de ação**: WhatsApp (mensagem pré-formatada), busca no Google e link direto para o registro no OSM.

## 📦 Instalação

```bash
pip install "streamlit>=1.50" pandas requests
```

## ▶️ Execução

```bash
streamlit run app.py
```

## ⚙️ Configuração

A aplicação precisa de um e-mail de contato para identificar as requisições ao Nominatim/Overpass (boa prática de uso da API pública do OSM).

**Opção 1 — Variável de ambiente** (tem prioridade):
```bash
export BUSCA_LEADS_CONTATO="voce@email.com"
```

**Opção 2 — Interface**: se a variável não estiver definida, a aplicação exibe um diálogo para informar o e-mail, que é salvo em `dados_osm/config.json`.

> Sem e-mail válido configurado, bases em cache ainda podem ser carregadas, mas novas coletas ficam bloqueadas.

## 🗂️ Estrutura de dados

```
dados_osm/
├── config.json              # e-mail de contato salvo localmente
├── status_leads.csv         # status e observações dos leads
└── leads_<hash>.csv         # cache de resultados por busca
```

## 🧭 Como usar

1. Na barra lateral, informe uma ou mais localidades (separadas por `;`).
2. Escolha a abrangência: área administrativa completa ou raio em km (aceita apenas uma localidade).
3. Selecione os nichos de interesse.
4. Defina a validade do cache (dias) e, se necessário, force uma nova coleta.
5. Clique em **Buscar / carregar base**.
6. Use os **filtros de resultados** (localidade, nicho, situação do site, status, distância etc.) para refinar a lista.
7. Edite **Status** e **Observação** diretamente na tabela e clique em **Salvar status e observações**.
8. Use os links de **WhatsApp**, **Google** e **OpenStreetMap** para conferir e abordar os leads.
9. Exporte os leads filtrados em **CSV**.

## 🧮 Pontuação de oportunidade (heurística)

| Critério | Pontos |
|---|---|
| Sem site ou só rede social | +3 |
| WhatsApp (celular) encontrado | +2 |
| Telefone válido (sem WhatsApp) | +1 |
| Instagram ou Facebook | +1 |
| E-mail válido | +1 |
| Identificado como rede (`brand:wikidata`) | −4 |

> ⚠️ A pontuação **não representa probabilidade de conversão**. A ausência de site no OpenStreetMap **não comprova** que o negócio não tenha site.

## 📜 Fonte dos dados e uso responsável

Dados fornecidos por:

> © OpenStreetMap contributors — ODbL 1.0 — https://www.openstreetmap.org/copyright

Ao abordar estabelecimentos:
- Identifique-se claramente.
- Ofereça opção de não receber novos contatos.
- Evite disparos em massa.
- Respeite a **LGPD**.

## 🛠️ Stack técnica

| Componente | Uso |
|---|---|
| **Streamlit** | Interface web |
| **Pandas** | Manipulação e persistência de dados (CSV) |
| **Requests** | Chamadas às APIs Nominatim e Overpass |
| **Nominatim** | Geocodificação de localidades |
| **Overpass API** | Consulta de estabelecimentos (com múltiplos endpoints de fallback) |

## 📄 Licença

Defina a licença do projeto aqui (ex.: MIT). Os dados coletados seguem a licença **ODbL 1.0** do OpenStreetMap.