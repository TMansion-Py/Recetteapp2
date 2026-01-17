import streamlit as st
import cloudscraper
from bs4 import BeautifulSoup

st.set_page_config(page_title="Marmiton Liste", page_icon="🛒")

def extraire_recette(url, nb_pers_voulu):
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows'})
    try:
        response = scraper.get(url, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 1. Trouver le nombre de personnes original sur la page
        # Marmiton utilise cette classe pour le compteur
        tag_nb_orig = soup.select_one('.recipe-ingredients__qt-counter-value')
        nb_orig = int(tag_nb_orig.text.strip()) if tag_nb_orig else 4
        
        # Calcul du coefficient multiplicateur
        ratio = nb_pers_voulu / nb_orig

        # 2. Extraire les ingrédients un par un
        ingredients_finaux = []
        items = soup.select('.recipe-ingredients__list__item')
        
        for item in items:
            qty_tag = item.select_one('.count')
            unit_tag = item.select_one('.unit')
            name_tag = item.select_one('.ingredient-name')
            
            if name_tag:
                name = name_tag.text.strip()
                unit = unit_tag.text.strip() if unit_tag else ""
                
                # Calcul de la nouvelle quantité
                try:
                    qty_val = qty_tag.text.strip().replace(',', '.') if qty_tag else ""
                    if qty_val:
                        nouvelle_qty = float(qty_val) * ratio
                        # On arrondi à 1 chiffre après la virgule pour plus de lisibilité
                        qty_affiche = int(nouvelle_qty) if nouvelle_qty.is_integer() else round(nouvelle_qty, 1)
                    else:
                        qty_affiche = ""
                except:
                    qty_affiche = qty_tag.text.strip() if qty_tag else ""

                ingredients_finaux.append(f"{qty_affiche} {unit} {name}".strip())
        
        return ingredients_finaux
    except Exception as e:
        return []

# --- INTERFACE SIMPLE ---
st.title("🛒 Liste de Courses Marmiton")

# Choix du nombre de personnes
nb_pers = st.number_input("Pour combien de personnes ?", min_value=1, value=4, step=1)

# Saisie des liens
liens_input = st.text_area("Collez vos liens Marmiton (un par ligne) :", height=150)

if st.button("Générer la liste"):
    urls = [u.strip() for u in liens_input.split('\n') if u.strip()]
    
    if not urls:
        st.warning("Veuillez coller au moins un lien.")
    else:
        liste_complete = []
        for url in urls:
            with st.spinner(f"Analyse de la recette..."):
                ingredients = extraire_recette(url, nb_pers)
                liste_complete.extend(ingredients)
        
        if liste_complete:
            st.write(f"### Ma liste pour {nb_pers} personnes :")
            # Tri par ordre alphabétique pour regrouper les ingrédients
            liste_complete.sort()
            
            # Affichage avec cases à cocher pour le magasin
            for i, ing in enumerate(liste_complete):
                st.checkbox(ing, key=f"ing_{i}")
        else:
            st.error("Aucun ingrédient trouvé. Vérifiez les liens ou la connexion.")
