# Instalação: pip install -r requirements.txt
# Execução:   streamlit run app.py
#
# Opcional: defina BUSCA_LEADS_CONTATO no ambiente ou em .env.
# Sem isso, o app pede um e-mail e grava em dados_osm/config.json.
#
# Pesquisa avançada: GOOGLE_PLACES_API_KEY e SERPER_API_KEY no .env.

from buscarleads.ui.app import main

if __name__ == "__main__":
    main()
