import streamlit as st
import cloudscraper
from bs4 import BeautifulSoup
import re

# --- CONFIGURATION DES RAYONS ---
RAYONS = {
    "🍎 Fruits & Légumes": ["pomme", "carotte", "oignon", "ail", "salade", "tomate", "courgette", "pomme de terre", "citron", "poivron", "champignon", "herbes", "échalote", "bouquet garni"],
    "🧀 Crèmerie & Œufs": ["lait", "beurre", "oeuf", "crème", "fromage", "yaourt", "parmesan", "gruyère", "mozzarella", "emmental"],
    "🥩 Boucherie & Poisson": ["poulet", "boeuf", "lardons", "saumon", "jambon", "crevette", "viande", "steak", "porc", "thon", "poitrine"],
    "🍝 Épicerie": ["farine", "sucre", "sel", "huile", "pâte", "riz", "conserve", "épice", "chocolat", "levure", "moutarde", "bouillon", "sauce", "poivre", "miel", "vin"],
    "📦 Autre": []
}

def determiner_rayon(ingredient):
    ing_low = ingredient.lower()
    for rayon, mots_cles in RAYONS.items():
        if any(mot in ing_low for mot in mots_cles):
            return rayon
    return "📦 Autre"

def extraire_recette(url, nb_pers_voulu):
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})
    try:
        response = scraper.get(url, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 1. Titre
        titre = soup.find('h1').text.strip() if soup.find('h1') else "Recette sans titre"

        # 2. Nombre de personnes original
        tag_pers = soup.select_one('.recipe-ingredients__qt-counter-value')
        nb_orig = 4
        if tag_pers:
            try:
                nb_orig = int(re.sub(r'\D', '', tag_pers.text))
            except: pass
        
        ratio = nb_pers_voulu / nb_orig

        # 3. Ingrédients
        ingredients = []
        # On cible les éléments Marmiton standards
        items = soup.select('.recipe-ingredients__list__item')
        
        for item in items:
            name_tag = item.select_one('.ingredient-name')
            qty_tag = item.select_one('.count')
            unit_tag = item.select_one('.unit')
            
            if name_tag:
                name = name_tag.text.strip()
                unit = unit_tag.text.strip() if unit_tag else ""
                
                # Calcul quantité
                qty_affiche = ""
                if qty_tag and qty_tag.text.strip():
                    try:
                        val = float(qty_tag.text.strip().replace(',', '.')) * ratio
                        qty_affiche = int(val) if val.is_integer() else round(val, 1)
                    except:
                        qty_affiche = qty_tag.text.strip()
                
                ingredients.append(f"{qty_affiche} {unit} {name}".strip())
        
        return {"titre": titre, "ingredients": ingredients}
    except Exception as e:
        return None

# --- INTERFACE STREAMLIT ---
st.set_page_config(page_title="Cook & Shop Web", layout="centered")

if 'planning' not in st.session_state:
    st.session_state.planning = []

st.title("🍳 Mon Assistant Courses")

# Zone d'ajout
with st.container():
    st.subheader("➕ Ajouter une recette")
    c1, c2 = st.columns([0.8, 0.2])
    url_input = c1.text_input("Lien Marmiton ou 750g", placeholder="Collez le lien ici...")
    nb_pers = c2.number_input("Pers.", min_value=1, value=4)
    
    if st.button("Ajouter à ma semaine", use_container_width=True):
        if url_input:
            with st.spinner("Analyse de la recette..."):
                data = extraire_recette(url_input, nb_pers)
                if data and data["ingredients"]:
                    st.session_state.planning.append(data)
                    st.success(f"Ajouté : {data['titre']}")
                else:
                    st.error("Impossible de récupérer les ingrédients. Vérifiez le lien.")

# Affichage
if st.session_state.planning:
    tab1, tab2 = st.tabs(["📅 Mon Planning", "🛍️ Ma Liste de Courses"])
    
    with tab1:
        for i, rec in enumerate(st.session_state.planning):
            col_t, col_b = st.columns([0.9, 0.1])
            col_t.markdown(f"**{rec['titre']}**")
            if col_b.button("🗑️", key=f"del_{i}"):
                st.session_state.planning.pop(i)
                st.rerun()

    with tab2:
        # Tri et dédoublonnage
        par_rayon = {r: set() for r in RAYONS.keys()}
        for rec in st.session_state.planning:
            for ing in rec["ingredients"]:
                par_rayon[determiner_rayon(ing)].add(ing)
        
        for rayon, items in par_rayon.items():
            if items:
                st.subheader(rayon)
                for it in sorted(items):
                    st.checkbox(it, key=f"check_{it}")
        
        if st.button("Vider tout le planning"):
            st.session_state.planning = []
            st.rerun()
else:
    st.info("Votre planning est vide. Ajoutez une recette pour générer la liste !")
