"""Caminhos, nichos e constantes compartilhadas.

Nada aqui depende do Streamlit. Os caminhos dos arquivos são funções (e não
constantes) para que possam ser trocados em testes ou pela variável de
ambiente ``BUSCA_LEADS_DADOS`` sem reimportar o pacote.
"""

from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # o app funciona sem .env; só a pesquisa avançada fica desligada
    def load_dotenv(*_args, **_kwargs) -> bool:
        return False


APP_DIR = Path(__file__).resolve().parent.parent
load_dotenv(APP_DIR / ".env")

# Pasta dos CSVs. Pode ser trocada com BUSCA_LEADS_DADOS=/caminho/qualquer.
DATA_DIR = Path(os.getenv("BUSCA_LEADS_DADOS") or APP_DIR / "dados_osm")
DATA_DIR.mkdir(parents=True, exist_ok=True)


def arquivo_status() -> Path:
    return DATA_DIR / "status_leads.csv"


def arquivo_config() -> Path:
    return DATA_DIR / "config.json"


def arquivo_enriquecido() -> Path:
    return DATA_DIR / "enriquecido.csv"


def arquivo_concorrencia() -> Path:
    return DATA_DIR / "concorrencia.csv"


def pasta_backup() -> Path:
    return DATA_DIR / "_backup"


def chave_google() -> str:
    """Lida na hora do uso, para refletir o .env e facilitar testes."""
    return os.getenv("GOOGLE_PLACES_API_KEY", "").strip()


def chave_serper() -> str:
    return os.getenv("SERPER_API_KEY", "").strip()


FONTE_DADOS = (
    "© OpenStreetMap contributors - ODbL 1.0 - "
    "https://www.openstreetmap.org/copyright"
)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]

NICHOS = {
    "Alimentação": [
        ("amenity", "restaurant|cafe|fast_food|bar|pub|ice_cream"),
        ("shop", "bakery|confectionery|butcher|greengrocer|deli|pastry"),
    ],
    "Beleza e estética": [
        ("shop", "hairdresser|barber|beauty|cosmetics|massage|tattoo"),
    ],
    "Saúde": [
        ("amenity", "dentist|clinic|doctors|veterinary"),
        (
            "healthcare",
            "dentist|doctor|clinic|psychotherapist|physiotherapist|optometrist",
        ),
        ("shop", "optician"),
    ],
    "Serviços profissionais": [
        (
            "office",
            "lawyer|accountant|estate_agent|insurance|architect|financial|"
            "notary|consulting",
        ),
    ],
    "Automotivo": [
        ("shop", "car_repair|car|tyres|car_parts"),
        ("amenity", "car_wash"),
    ],
    "Pet": [("shop", "pet|pet_grooming")],
    "Fitness e educação": [
        ("leisure", "fitness_centre|sports_centre|dance"),
        ("amenity", "driving_school|language_school|music_school|prep_school"),
    ],
    "Varejo": [
        (
            "shop",
            "clothes|shoes|jewelry|gift|florist|books|furniture|electronics|"
            "mobile_phone|variety_store|bag|boutique",
        ),
    ],
    "Mercados": [("shop", "supermarket|convenience")],
}
GRUPOS_PADRAO = [grupo for grupo in NICHOS if grupo != "Mercados"]

ROTULOS = {
    "restaurant": "Restaurante",
    "cafe": "Cafeteria",
    "fast_food": "Lanchonete",
    "bar": "Bar",
    "pub": "Pub",
    "ice_cream": "Sorveteria",
    "bakery": "Padaria",
    "confectionery": "Doceria",
    "butcher": "Açougue",
    "greengrocer": "Hortifruti",
    "deli": "Delicatessen",
    "pastry": "Confeitaria",
    "hairdresser": "Salão de beleza",
    "barber": "Barbearia",
    "beauty": "Estética / beleza",
    "cosmetics": "Cosméticos",
    "massage": "Massagem",
    "tattoo": "Tatuagem",
    "dentist": "Dentista",
    "clinic": "Clínica",
    "doctors": "Consultório médico",
    "doctor": "Consultório médico",
    "veterinary": "Veterinário",
    "psychotherapist": "Psicologia",
    "physiotherapist": "Fisioterapia",
    "optometrist": "Ótica",
    "optician": "Ótica",
    "lawyer": "Advocacia",
    "accountant": "Contabilidade",
    "estate_agent": "Imobiliária",
    "insurance": "Seguros",
    "architect": "Arquitetura",
    "financial": "Serviços financeiros",
    "notary": "Cartório",
    "consulting": "Consultoria",
    "car_repair": "Oficina",
    "car": "Veículos",
    "tyres": "Pneus",
    "car_parts": "Autopeças",
    "car_wash": "Lava-rápido",
    "pet": "Pet shop",
    "pet_grooming": "Banho e tosa",
    "fitness_centre": "Academia",
    "sports_centre": "Centro esportivo",
    "dance": "Escola de dança",
    "driving_school": "Autoescola",
    "language_school": "Escola de idiomas",
    "music_school": "Escola de música",
    "prep_school": "Cursinho",
    "clothes": "Roupas",
    "shoes": "Calçados",
    "jewelry": "Joalheria",
    "gift": "Presentes",
    "florist": "Floricultura",
    "books": "Livraria",
    "furniture": "Móveis",
    "electronics": "Eletrônicos",
    "mobile_phone": "Celulares",
    "variety_store": "Variedades",
    "bag": "Bolsas",
    "boutique": "Boutique",
    "supermarket": "Supermercado",
    "convenience": "Mercadinho",
}

REDES = (
    "instagram.com",
    "facebook.com",
    "fb.com",
    "linktr.ee",
    "wa.me",
    "whatsapp.com",
    "bio.link",
    "beacons.ai",
    "tiktok.com",
    "ifood.com.br",
    "youtube.com",
)

DDDS = {
    *range(11, 20),
    21, 22, 24, 27, 28,
    31, 32, 33, 34, 35, 37, 38,
    *range(41, 50),
    51, 53, 54, 55,
    *range(61, 70),
    71, 73, 74, 75, 77, 79,
    *range(81, 90),
    *range(91, 100),
}

STATUS_LEAD = [
    "Novo",
    "Contatado",
    "Respondeu",
    "Reunião marcada",
    "Fechado",
    "Descartado",
]
# Status em que vale gastar cota paga da pesquisa avançada.
STATUS_PESQUISA_AVANCADA = ["Respondeu", "Reunião marcada", "Fechado"]
SITUACOES = ["Sem site", "Só rede social", "Com site"]

# Colunas gravadas nos CSVs de leads. ``editado_em`` e ``editado_campos`` marcam
# linhas corrigidas à mão dentro do app e quais campos mudaram (vazio = como
# veio do OpenStreetMap). Servem para preservar as correções numa nova coleta.
COLUNAS = [
    "nome",
    "nicho",
    "localidade",
    "endereco",
    "distancia_km",
    "site",
    "instagram",
    "facebook",
    "email",
    "telefone",
    "whatsapp_num",
    "status_site",
    "rede",
    "pontuacao",
    "osm_id",
    "osm_url",
    "latitude",
    "longitude",
    "coletado_em",
    "editado_em",
    "editado_campos",
]
# Colunas calculadas ao carregar; nunca são gravadas no CSV de leads.
COLUNAS_CALCULADAS = ["whatsapp_tentativa", "arquivo_origem"]

# Campos que o usuário pode corrigir na tabela sem refazer a coleta.
COLUNAS_EDITAVEIS = [
    "nome",
    "endereco",
    "telefone",
    "email",
    "site",
    "instagram",
    "facebook",
]

EMAIL_RE = r"[^@\s]+@[^@\s]+\.[^@\s]+"

# ---- Pesquisa avançada: cache do Google Places (enriquecido.csv) ----------
# Uma linha por lead. Os campos de leitura rápida ficam em colunas próprias e a
# resposta completa da API fica em ``gmn_json``, para que nada pago se perca.
COLUNAS_GOOGLE = [
    "osm_id",
    "gmn_status",  # ok | nao_encontrado
    "gmn_place_id",  # único dado que os termos do Google permitem guardar sem prazo
    "gmn_nome",
    "gmn_endereco",
    "gmn_lat",
    "gmn_lon",
    "gmn_distancia_m",  # distância entre o ponto do OSM e o resultado do Google
    "gmn_similaridade",  # parecença entre o nome do OSM e o do Google (0 a 1)
    "gmn_confianca",  # alta | media | baixa: chance de ser o mesmo estabelecimento
    "gmn_situacao",  # operacional, fechado temporariamente/permanentemente
    "gmn_tipo_principal",
    "gmn_tipos",
    "gmn_nota",
    "gmn_avaliacoes",  # quantidade de avaliações
    "gmn_site",
    "gmn_telefone",
    "gmn_telefone_intl",
    "gmn_nivel_preco",
    "gmn_faixa_preco",
    "gmn_horario",
    "gmn_resumo",  # resumo editorial do Google
    "gmn_resumo_ia",  # resumo gerado por IA do Google
    "gmn_resumo_avaliacoes",  # resumo das avaliações gerado por IA
    "gmn_servicos",
    "gmn_pagamento",
    "gmn_estacionamento",
    "gmn_acessibilidade",
    "gmn_reviews",  # até 5 avaliações em texto corrido
    "gmn_url_maps",
    "gmn_url_avaliacoes",
    "gmn_fotos",  # quantidade de fotos
    "gmn_area_servico",  # atende só na casa do cliente, sem endereço aberto
    "gmn_abertura",
    "gmn_json",  # resposta completa da API
    "atualizado_em",
]
# Subconjunto levado para a tabela principal (o restante é lido sob demanda).
COLUNAS_GOOGLE_NA_BASE = [
    "gmn_status",
    "gmn_nota",
    "gmn_avaliacoes",
    "gmn_site",
    "gmn_telefone",
    "gmn_confianca",
    "gmn_situacao",
]

COLUNAS_CONCORRENCIA = [
    "chave",
    "concorrentes_com_site",
    "total_concorrentes",
    "melhor_concorrente",
    "melhor_concorrente_link",
    "atualizado_em",
]

# Dados do Google com mais dias que isso são sinalizados como antigos na tela.
# Os termos do Google só permitem guardar sem prazo o place_id; o restante deve
# ser tratado como temporário (veja o README).
DIAS_DADO_GOOGLE_ANTIGO = 30
