import streamlit as st
import cloudscraper
from bs4 import BeautifulSoup
import re
from typing import Dict, List, Optional
from fractions import Fraction

# --- CONFIGURATION DES RAYONS ---
RAYONS = {
    "🍎 Fruits & Légumes": [
        "pomme", "carotte", "oignon", "ail", "salade", "tomate", 
        "courgette", "pomme de terre", "citron", "poivron", "champignon", 
        "herbes", "échalote", "concombre", "aubergine", "banane", "bouquet garni"
    ],
    "🧀 Crèmerie & Œufs": [
        "lait", "beurre", "oeuf", "œuf", "crème", "fromage", "yaourt", 
        "parmesan", "gruyère", "mozzarella", "emmental", "ricotta", "feta"
    ],
    "🥩 Boucherie & Poisson": [
        "poulet", "boeuf", "bœuf", "lardons", "saumon", "jambon", 
        "crevette", "viande", "steak", "porc", "thon", "dinde", "agneau", "bourguignon"
    ],
    "🍝 Épicerie": [
        "farine", "sucre", "sel", "huile", "pâte", "riz", "conserve", 
        "épice", "chocolat", "levure", "moutarde", "bouillon", "sauce", 
        "poivre", "miel", "vinaigre", "pâtes", "spaghetti", "vin", "bouteille"
    ],
    "📦 Autre": []
}

def fraction_to_float(fraction_str: str) -> float:
    """Convertit une fraction en nombre décimal"""
    try:
        return float(Fraction(fraction_str))
    except:
        return float(fraction_str)

@st.cache_data(ttl=3600, show_spinner=False)
def extraire_recette(url: str, nb_pers_voulu: int) -> Optional[Dict]:
    """
    Extrait une recette depuis Marmiton ou 750g avec mise en cache.
    """
    scraper = cloudscraper.create_scraper(
        browser={'browser': 'chrome', 'platform': 'windows'}
    )
    
    try:
        res = scraper.get(url, timeout=15)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, 'html.parser')
        
        if "marmiton.org" in url:
            return _extraire_marmiton(soup, nb_pers_voulu, url)
        elif "750g.com" in url:
            return _extraire_750g(soup, url)
        else:
            return None
            
    except Exception as e:
        st.error(f"Erreur lors de l'extraction : {str(e)}")
        return None

def _extraire_marmiton(soup: BeautifulSoup, nb_pers_voulu: int, url: str) -> Dict:
    """Extrait les données d'une recette Marmiton avec calcul de quantités précis"""
    titre_tag = soup.find('h1')
    if not titre_tag:
        raise ValueError("Titre introuvable")
    
    titre = titre_tag.text.strip()
    
    # Récupération du nombre de personnes original
    tag_nb_orig = soup.select_one('.recipe-ingredients__qt-counter-value')
    nb_orig = 4  # Valeur par défaut
    
    if tag_nb_orig:
        match = re.search(r'\d+', tag_nb_orig.text)
        if match:
            nb_orig = int(match.group())
    
    ratio = nb_pers_voulu / nb_orig
    ingredients = []
    
    for item in soup.select('.recipe-ingredients__list__item'):
        name_tag = item.select_one('.ingredient-name')
        if not name_tag:
            continue
            
        name = name_tag.text.strip()
        qty_tag = item.select_one('.count')
        unit_tag = item.select_one('.unit')
        
        unit = unit_tag.text.strip() if unit_tag else ""
        qty_val = ""
        
        if qty_tag and qty_tag.text.strip():
            qty_text = qty_tag.text.strip().replace(',', '.').replace(' ', '')
            try:
                # Gestion des fractions et nombres
                val = fraction_to_float(qty_text) * ratio
                
                # Arrondi intelligent
                if val < 0.1:
                    qty_val = str(round(val, 2))
                elif val < 1:
                    qty_val = str(round(val, 1))
                elif val.is_integer():
                    qty_val = str(int(val))
                else:
                    qty_val = str(round(val, 1))
            except ValueError:
                qty_val = qty_tag.text.strip()
        
        ingredient = f"{qty_val} {unit} {name}".strip()
        ingredients.append(ingredient)
    
    return {
        "titre": titre, 
        "ingredients": ingredients, 
        "url": url,
        "nb_personnes": nb_pers_voulu
    }

def _extraire_750g(soup: BeautifulSoup, url: str) -> Dict:
    """Extrait les données d'une recette 750g"""
    titre_tag = soup.find('h1')
    if not titre_tag:
        raise ValueError("Titre introuvable")
    
    titre = titre_tag.text.strip()
    ingredients = []
    
    items = (
        soup.select('.c-recipe-ingredients__list-item') or 
        soup.select('.recipe-ingredients li')
    )
    
    for item in items:
        ingredient = " ".join(item.get_text().split())
        if ingredient:
            ingredients.append(ingredient)
    
    return {
        "titre": titre, 
        "ingredients": ingredients, 
        "url": url,
        "nb_personnes": 4
    }

def determiner_rayon(ingredient: str) -> str:
    """Détermine le rayon d'un ingrédient"""
    ing_low = ingredient.lower()
    
    for rayon, mots_cles in RAYONS.items():
        if rayon == "📦 Autre":
            continue
        if any(mot in ing_low for mot in mots_cles):
            return rayon
    
    return "📦 Autre"

# --- CONFIGURATION STREAMLIT ---
st.set_page_config(
    page_title="Mon Assistant Courses", 
    page_icon="👨‍🍳",
    layout="centered"
)

# Style CSS pour thème sombre
st.markdown("""
<style>
    .stApp {
        background-color: #1a1a1a;
        color: #ffffff;
    }
    .success-box {
        background-color: #2d5016;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 1rem 0;
        color: #90ee90;
    }
    h1 {
        color: #ffffff;
    }
    h2, h3 {
        color: #e0e0e0;
    }
</style>
""", unsafe_allow_html=True)

# Initialisation du stockage
if 'planning' not in st.session_state:
    st.session_state.planning = []

# --- EN-TÊTE ---
st.title("👨‍🍳 Mon Assistant Courses")

# --- FORMULAIRE D'AJOUT ---
st.markdown("### Lien de la recette (Marmiton ou 750g)")
url_input = st.text_input(
    "Lien de la recette (Marmiton ou 750g)",
    placeholder="https://www.marmiton.org/recettes/...",
    label_visibility="collapsed"
)

st.markdown("### Nombre de personnes")
nb_pers = st.number_input(
    "Nombre de personnes", 
    min_value=1, 
    max_value=20,
    value=2,
    label_visibility="collapsed"
)

if st.button("Ajouter à la liste", use_container_width=True):
    if not url_input:
        st.warning("⚠️ Veuillez saisir une URL")
    elif not ("marmiton.org" in url_input or "750g.com" in url_input):
        st.error("❌ Seuls Marmiton et 750g sont supportés")
    else:
        with st.spinner("🔍 Analyse de la recette en cours..."):
            data = extraire_recette(url_input, nb_pers)
            
            if data and data.get("ingredients"):
                st.session_state.planning.append(data)
                st.markdown(
                    f'<div class="success-box">Ajouté : {data["titre"]}</div>',
                    unsafe_allow_html=True
                )
                st.rerun()
            else:
                st.error("❌ Impossible de lire cette recette. Vérifiez l'URL.")

st.divider()

# --- ONGLETS ---
if st.session_state.planning:
    tab1, tab2 = st.tabs(["📋 Mes Recettes", "🛒 Liste de Courses"])
    
    with tab1:
        st.markdown(f"### {len(st.session_state.planning)} recette(s) au menu")
        
        for i, recette in enumerate(st.session_state.planning):
            with st.expander(f"**{recette['titre']}** ({recette['nb_personnes']} pers.)", expanded=False):
                st.markdown("**Ingrédients :**")
                for ing in recette["ingredients"]:
                    st.markdown(f"- {ing}")
                
                if st.button("🗑️ Supprimer", key=f"del_{i}"):
                    st.session_state.planning.pop(i)
                    st.rerun()
    
    with tab2:
        st.markdown("### 🛒 Votre liste de courses")
        
        # Regroupement par rayon
        par_rayon = {r: [] for r in RAYONS.keys()}
        
        for recette in st.session_state.planning:
            for ing in recette["ingredients"]:
                rayon = determiner_rayon(ing)
                if ing not in par_rayon[rayon]:
                    par_rayon[rayon].append(ing)
        
        # Affichage par rayon
        for rayon, items in par_rayon.items():
            if items:
                st.markdown(f"## {rayon}")
                for item in sorted(items):
                    st.checkbox(item, key=f"check_{rayon}_{item}")
                st.divider()
        
        # Bouton de reset
        if st.button("🔄 Réinitialiser tout", type="secondary", use_container_width=True):
            st.session_state.planning = []
            st.rerun()
else:
    st.info("👋 Votre planning est vide. Ajoutez une recette ci-dessus pour commencer !")
