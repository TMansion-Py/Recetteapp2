import streamlit as st
import cloudscraper
from bs4 import BeautifulSoup
import urllib.parse

st.set_page_config(page_title="Marmiton Propre", page_icon="🛒")

def extraire_propre(url, nb_pers_voulu):
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows'})
    try:
        response = scraper.get(url, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 1. Nombre de personnes
        nb_orig = 4
        tag_pers = soup.select_one('.recipe-ingredients__qt-counter-value')
        if tag_pers:
            nb_orig = int(''.join(filter(str.isdigit, tag_pers.text)))
        ratio = nb_pers_voulu / nb_orig

        # 2. Ciblage précis des ingrédients
        # On ne cherche QUE dans la liste des ingrédients officielle
        liste_ing = []
        items = soup.select('.recipe-ingredients__list__item')
        
        for item in items:
            # On récupère les morceaux séparément
            qty_tag = item.select_one('.count')
            unit_tag = item.select_one('.unit')
            name_tag = item.select_one('.ingredient-name')
            
            if name_tag:
                name = name_tag.text.strip()
                unit = unit_tag.text.strip() if unit_tag else ""
                
                # Calcul quantité
                try:
                    qty_text = qty_tag.text.strip().replace(',', '.') if qty_tag else ""
                    if qty_text:
                        valeur = float(qty_text) * ratio
                        qty = int(valeur) if valeur.is_integer() else round(valeur, 2)
                    else:
                        qty = ""
                except:
                    qty = ""

                # On ne garde que si on a un nom d'ingrédient
                liste_ing.append({
                    "nom": name,
                    "complet": f"{qty} {unit} {name}".strip()
                })
        
        return liste_ing
    except:
        return []

# --- INTERFACE ---
st.title("🛒 Ma Liste Intermarché")

nb_pers = st.number_input("Pour combien de personnes ?", min_value=1, value=4)
liens = st.text_area("Liens Marmiton (un par ligne) :")

if st.button("🪄 Nettoyer et Générer"):
    urls = [u.strip() for u in liens.split('\n') if u.strip()]
    if not urls:
        st.warning("Ajoute un lien !")
    else:
        resultats = []
        for url in urls:
            resultats.extend(extraire_propre(url, nb_pers))
        
        if resultats:
            st.write(f"### Liste pour {nb_pers} personnes")
            for i, ing in enumerate(resultats):
                col1, col2 = st.columns([0.8, 0.2])
                
                # Affichage propre
                col1.checkbox(ing['complet'], key=f"check_{i}")
                
                # Recherche Intermarché optimisée (on cherche le nom de l'ingrédient, pas la quantité)
                search_term = urllib.parse.quote(ing['nom'])
                url_inter = f"https://www.intermarche.com/recherche/{search_term}"
                col2.markdown(f"[🛒]({url_inter})")
        else:
            st.error("Aucun ingrédient trouvé. Vérifie que le lien est bien une recette Marmiton.")
