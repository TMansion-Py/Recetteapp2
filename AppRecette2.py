import streamlit as st
import cloudscraper
from bs4 import BeautifulSoup

st.set_page_config(page_title="Marmiton Fix", page_icon="🛒")

def extraire_recette(url, nb_pers_voulu):
    # On simule un vrai navigateur très précisément
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
    }
    
    # On crée le scraper avec ces paramètres
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})
    
    try:
        # On force l'envoi des headers
        response = scraper.get(url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            return None

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # --- TEST 1 : Nombre de personnes ---
        tag_nb_orig = soup.select_one('.recipe-ingredients__qt-counter-value')
        nb_orig = 4
        if tag_nb_orig:
            try:
                nb_orig = int(''.join(filter(str.isdigit, tag_nb_orig.text)))
            except: pass
        
        ratio = nb_pers_voulu / nb_orig

        # --- TEST 2 : Ingrédients (Sélecteurs larges) ---
        ingredients_finaux = []
        # Marmiton change souvent ses classes, on teste les deux principales
        items = soup.select('.recipe-ingredients__list__item') or soup.select('.card-ingredient')
        
        for item in items:
            name_tag = item.select_one('.ingredient-name') or item.select_one('.name')
            qty_tag = item.select_one('.count')
            unit_tag = item.select_one('.unit')
            
            if name_tag:
                name = name_tag.text.strip()
                unit = unit_tag.text.strip() if unit_tag else ""
                
                try:
                    qty_val = qty_tag.text.strip().replace(',', '.') if qty_tag else ""
                    if qty_val:
                        valeur = float(qty_val) * ratio
                        qty_affiche = int(valeur) if valeur.is_integer() else round(valeur, 1)
                    else:
                        qty_affiche = ""
                except:
                    qty_affiche = ""

                ingredients_finaux.append(f"{qty_affiche} {unit} {name}".strip())
        
        return ingredients_finaux
    except Exception as e:
        return None

# --- INTERFACE ---
st.title("🛒 Liste Marmiton")

nb_pers = st.number_input("Nombre de personnes :", min_value=1, value=4)
liens_input = st.text_area("Collez vos liens Marmiton :")

if st.button("Générer"):
    urls = [u.strip() for u in liens_input.split('\n') if u.strip()]
    
    if urls:
        liste_finale = []
        for url in urls:
            res = extraire_recette(url, nb_pers)
            if res:
                liste_finale.extend(res)
            else:
                st.error(f"Le site Marmiton bloque l'accès à cette recette : {url[:40]}...")
        
        if liste_finale:
            st.success("Recettes récupérées !")
            for i, ing in enumerate(sorted(liste_finale)):
                st.checkbox(ing, key=f"check_{i}")
        else:
            st.warning("Aucun ingrédient trouvé. Marmiton a peut-être renforcé sa sécurité.")
