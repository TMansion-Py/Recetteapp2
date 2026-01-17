import streamlit as st
import cloudscraper
from bs4 import BeautifulSoup
import re

# --- CONFIGURATION DES RAYONS ---
RAYONS = {
    "🍎 Fruits & Légumes": ["pomme", "carotte", "oignon", "ail", "salade", "tomate", "courgette", "pomme de terre", "citron", "poivron", "champignon", "herbes", "échalote"],
    "🧀 Crèmerie & Œufs": ["lait", "beurre", "oeuf", "crème", "fromage", "yaourt", "parmesan", "gruyère", "mozzarella", "emmental", "ricotta"],
    "🥩 Boucherie & Poisson": ["poulet", "boeuf", "lardons", "saumon", "jambon", "crevette", "viande", "steak", "porc", "thon", "dinde"],
    "🍝 Épicerie": ["farine", "sucre", "sel", "huile", "pâte", "riz", "conserve", "épice", "chocolat", "levure", "moutarde", "bouillon", "sauce", "poivre", "miel"],
    "📦 Autre": []
}

def determiner_rayon(ingredient):
    ing_low = ingredient.lower()
    for rayon, mots_cles in RAYONS.items():
        if any(mot in ing_low for mot in mots_cles): return rayon
    return "📦 Autre"

def extraire_recette(url, nb_pers_voulu):
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows'})
    try:
        res = scraper.get(url, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        ingredients = []
        titre = "Recette Inconnue"

        if "marmiton.org" in url:
            titre = soup.find('h1').text.strip()
            tag_nb_orig = soup.select_one('.recipe-ingredients__qt-counter-value')
            nb_orig = int(re.sub(r'\D', '', tag_nb_orig.text)) if tag_nb_orig else 4
            ratio = nb_pers_voulu / nb_orig
            for item in soup.select('.recipe-ingredients__list__item'):
                name = item.select_one('.ingredient-name').text.strip()
                qty_tag, unit_tag = item.select_one('.count'), item.select_one('.unit')
                unit = unit_tag.text.strip() if unit_tag else ""
                qty_val = ""
                if qty_tag and qty_tag.text.strip():
                    try:
                        val = float(qty_tag.text.strip().replace(',', '.')) * ratio
                        qty_val = int(val) if val.is_integer() else round(val, 1)
                    except: qty_val = qty_tag.text.strip()
                ingredients.append(f"{qty_val} {unit} {name}".strip())

        elif "750g.com" in url:
            titre = soup.find('h1').text.strip()
            items = soup.select('.c-recipe-ingredients__list-item') or soup.select('.recipe-ingredients li')
            for item in items:
                ingredients.append(" ".join(item.get_text().split()))
        
        return {"titre": titre, "ingredients": ingredients}
    except: return None

# --- INTERFACE STREAMLIT ---
st.set_page_config(page_title="Mes Courses Web", page_icon="🛒")
st.title("🛒 Planning & Courses")

# Initialisation du stockage de la semaine
if 'planning' not in st.session_state:
    st.session_state.planning = []

# --- BARRE LATÉRALE : AJOUT ---
with st.sidebar:
    st.header("➕ Ajouter une recette")
    url_input = st.text_input("Lien Marmiton ou 750g")
    nb_pers = st.number_input("Nombre de personnes", min_value=1, value=4)
    
    if st.button("Ajouter au planning"):
        if url_input:
            with st.spinner("Analyse..."):
                data = extraire_recette(url_input, nb_pers)
                if data:
                    st.session_state.planning.append(data)
                    st.success(f"Ajouté : {data['titre']}")
                else:
                    st.error("Impossible de lire cette recette.")

# --- AFFICHAGE PRINCIPAL ---
tab1, tab2 = st.tabs(["📅 Mon Planning", "🛍️ Ma Liste de Courses"])

with tab1:
    if not st.session_state.planning:
        st.info("Votre planning est vide. Ajoutez des recettes via la barre latérale.")
    else:
        for i, recette in enumerate(st.session_state.planning):
            col1, col2 = st.columns([0.8, 0.2])
            col1.write(f"**{recette['titre']}**")
            if col2.button("🗑️", key=f"del_{i}"):
                st.session_state.planning.pop(i)
                st.rerun()

with tab2:
    if not st.session_state.planning:
        st.write("Rien à acheter pour l'instant.")
    else:
        # Regroupement et dédoublonnage
        par_rayon = {r: set() for r in RAYONS.keys()}
        for recette in st.session_state.planning:
            for ing in recette["ingredients"]:
                par_rayon[determiner_rayon(ing)].add(ing)
        
        for rayon, items in par_rayon.items():
            if items:
                st.subheader(rayon)
                for it in sorted(items):
                    st.checkbox(it, key=f"check_{it}")

if st.button("Reset tout le planning"):
    st.session_state.planning = []
    st.rerun()
