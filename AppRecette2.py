import streamlit as st
import cloudscraper
from bs4 import BeautifulSoup

st.set_page_config(page_title="Marmiton Fix", page_icon="🍳")

def extraire_donnees(url, nb_pers_voulu):
    # Utilisation d'un scraper plus robuste
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})
    
    try:
        response = scraper.get(url, timeout=15)
        if response.status_code != 200:
            return [f"Erreur de connexion (Code {response.status_code})"]
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # --- 1. RECUPERER LE NOMBRE DE PERSONNES ORIGINAL ---
        # On cherche partout où il pourrait y avoir le chiffre des personnes
        nb_orig_tag = soup.find(class_=lambda x: x and 'recipe-ingredients__qt-counter-value' in x)
        nb_orig = 4 # Valeur par défaut
        if nb_orig_tag:
            try:
                nb_orig = int(''.join(filter(str.isdigit, nb_orig_tag.text)))
            except: pass
        
        ratio = nb_pers_voulu / nb_orig

        # --- 2. RECUPERER LES INGRÉDIENTS ---
        # On essaie plusieurs cibles différentes pour être sûr de ne rien rater
        ingredients = []
        # Cible les lignes d'ingrédients
        items = soup.find_all(class_=lambda x: x and 'ingredient' in x.lower())
        
        for item in items:
            # On extrait le texte propre
            texte = item.get_text(separator=' ').strip()
            # On nettoie les espaces multiples
            texte = " ".join(texte.split())
            
            # On ignore les textes trop courts ou les titres de sections
            if len(texte) > 2 and texte not in ingredients:
                ingredients.append(texte)

        return ingredients
    except Exception as e:
        return [f"Erreur technique : {str(e)}"]

# --- INTERFACE ---
st.title("🛒 Shopping Intermarché")

nb_pers = st.number_input("Nombre de personnes :", min_value=1, value=4)
liens_input = st.text_area("Colle tes liens ici (un par ligne) :")

if st.button("🔥 Générer ma liste"):
    urls = [u.strip() for u in liens_input.split('\n') if u.strip()]
    
    if not urls:
        st.warning("Veuillez coller un lien.")
    else:
        all_results = []
        for url in urls:
            with st.spinner(f"Analyse de {url[:30]}..."):
                res = extraire_donnees(url, nb_pers)
                all_results.extend(res)
        
        if all_results:
            st.markdown("### 📝 Ma Liste")
            for i, ing in enumerate(all_results):
                col1, col2 = st.columns([0.8, 0.2])
                col1.checkbox(ing, key=f"ing_{i}")
                # Lien vers Intermarché
                nom_seul = ing.split(' ')[-1] # On prend le dernier mot pour la recherche
                url_inter = f"https://www.intermarche.com/recherche/{nom_seul}"
                col2.markdown(f"[🛒]({url_inter})")
        else:
            st.error("Rien n'a été trouvé. Marmiton bloque peut-être l'accès.")
