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
    # Ajout de headers pour simuler un vrai navigateur
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    scraper = cloudscraper.create_scraper()
    try:
        res = scraper.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        ingredients = []
        
        # --- LOGIQUE MARMITON ---
        if "marmiton.org" in url:
            titre = soup.find('h1').get_text().strip()
            tag_nb_orig = soup.select_one('.recipe-ingredients__qt-counter-value')
            nb_orig = int(re.sub(r'\D', '', tag_nb_orig.text)) if tag_nb_orig else 4
            ratio = nb_pers_voulu / nb_orig
            
            items = soup.select('.recipe-ingredients__list__item')
            for item in items:
                name = item.select_one('.ingredient-name').text.strip()
                qty_tag = item.select_one('.count')
                unit_tag = item.select_one('.unit')
                unit = unit_tag.text.strip() if unit_tag else ""
                
                qty_val = ""
                if qty_tag and qty_tag.text.strip():
                    try:
                        val = float(qty_tag.text.strip().replace(',', '.')) * ratio
                        qty_val = int(val) if val.is_integer() else round(val, 1)
                    except: qty_val = qty_tag.text.strip()
                
                ingredients.append(f"{qty_val} {unit} {name}".strip())
            return {"titre": titre, "ingredients": ingredients}

        # --- LOGIQUE 750G ---
        elif "750g.com" in url:
            titre = soup.find('h1').get_text().strip()
            items = soup.select('.c-recipe-ingredients__list-item') or soup.select('.recipe-ingredients li')
            for item in items:
                ingredients.append(" ".join(item.get_text().split()))
            return {"titre": titre, "ingredients": ingredients}
            
    except Exception as e:
        st.error(f"Erreur lors de l'extraction : {e}")
        return None

# --- INITIALISATION DE LA MÉMOIRE (Session State) ---
if 'planning' not in st.session_state:
    st.session_state.planning = []

# --- INTERFACE ---
st.title("🛒 Mon Assistant Courses Web")

# Zone d'ajout
with st.expander("➕ Ajouter une recette au planning", expanded=True):
    col_link, col_p = st.columns([0.8, 0.2])
    url_input = col_link.text_input("Lien de la recette")
    nb_pers = col_p.number_input("Pers.", min_value=1, value=4)
    if st.button("Ajouter à la semaine"):
        if url_input:
            data = extraire_recette(url_input, nb_pers)
            if data and data["ingredients"]:
                st.session_state.planning.append(data)
                st.success(f"Recette '{data['titre']}' ajoutée !")
            else:
                st.warning("Aucun ingrédient trouvé. Vérifie le lien.")

# --- AFFICHAGE ---
if st.session_state.planning:
    tab1, tab2 = st.tabs(["📅 Planning", "🛍️ Liste de Courses"])
    
    with tab1:
        for i, rec in enumerate(st.session_state.planning):
            c1, c2 = st.columns([0.9, 0.1])
            c1.write(f"🍴 {rec['titre']}")
            if c2.button("❌", key=f"del_{i}"):
                st.session_state.planning.pop(i)
                st.rerun()
                
    with tab2:
        # Tri par rayons
        par_rayon = {r: set() for r in RAYONS.keys()}
        for rec in st.session_state.planning:
            for ing in rec["ingredients"]:
                par_rayon[determiner_rayon(ing)].add(ing)
        
        for rayon, items in par_rayon.items():
            if items:
                st.markdown(f"#### {rayon}")
                for it in sorted(items):
                    st.checkbox(it, key=f"shop_{it}")
        
        if st.button("Tout effacer"):
            st.session_state.planning = []
            st.rerun()
else:
    st.info("Colle un lien ci-dessus pour commencer ta liste !")
