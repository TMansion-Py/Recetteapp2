import streamlit as st
import cloudscraper
from bs4 import BeautifulSoup
import re
from typing import Dict, List, Optional

# --- CONFIGURATION DES RAYONS ---
RAYONS = {
    "🍎 Fruits & Légumes": [
        "pomme", "carotte", "oignon", "ail", "salade", "tomate", 
        "courgette", "pomme de terre", "citron", "poivron", "champignon", 
        "herbes", "échalote", "concombre", "aubergine", "banane"
    ],
    "🧀 Crèmerie & Œufs": [
        "lait", "beurre", "oeuf", "œuf", "crème", "fromage", "yaourt", 
        "parmesan", "gruyère", "mozzarella", "emmental", "ricotta", "feta"
    ],
    "🥩 Boucherie & Poisson": [
        "poulet", "boeuf", "bœuf", "lardons", "saumon", "jambon", 
        "crevette", "viande", "steak", "porc", "thon", "dinde", "agneau"
    ],
    "🍝 Épicerie": [
        "farine", "sucre", "sel", "huile", "pâte", "riz", "conserve", 
        "épice", "chocolat", "levure", "moutarde", "bouillon", "sauce", 
        "poivre", "miel", "vinaigre", "pâtes", "spaghetti"
    ],
    "📦 Autre": []
}

@st.cache_data(ttl=3600)
def extraire_recette(url: str, nb_pers_voulu: int) -> Optional[Dict]:
    """
    Extrait une recette depuis Marmiton ou 750g avec mise en cache.
    
    Args:
        url: URL de la recette
        nb_pers_voulu: Nombre de personnes souhaité
        
    Returns:
        Dict avec titre et ingrédients ou None si échec
    """
    scraper = cloudscraper.create_scraper(
        browser={'browser': 'chrome', 'platform': 'windows'}
    )
    
    try:
        res = scraper.get(url, timeout=15)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, 'html.parser')
        
        if "marmiton.org" in url:
            return _extraire_marmiton(soup, nb_pers_voulu)
        elif "750g.com" in url:
            return _extraire_750g(soup)
        else:
            return None
            
    except Exception as e:
        st.error(f"Erreur lors de l'extraction : {str(e)}")
        return None

def _extraire_marmiton(soup: BeautifulSoup, nb_pers_voulu: int) -> Dict:
    """Extrait les données d'une recette Marmiton"""
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
            qty_text = qty_tag.text.strip().replace(',', '.')
            try:
                val = float(qty_text) * ratio
                qty_val = str(int(val)) if val.is_integer() else str(round(val, 1))
            except ValueError:
                qty_val = qty_tag.text.strip()
        
        ingredient = f"{qty_val} {unit} {name}".strip()
        ingredients.append(ingredient)
    
    return {"titre": titre, "ingredients": ingredients, "url": ""}

def _extraire_750g(soup: BeautifulSoup) -> Dict:
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
    
    return {"titre": titre, "ingredients": ingredients, "url": ""}

def determiner_rayon(ingredient: str) -> str:
    """Détermine le rayon d'un ingrédient"""
    ing_low = ingredient.lower()
    
    for rayon, mots_cles in RAYONS.items():
        if rayon == "📦 Autre":
            continue
        if any(mot in ing_low for mot in mots_cles):
            return rayon
    
    return "📦 Autre"

def normaliser_ingredient(ingredient: str) -> str:
    """Normalise un ingrédient pour éviter les doublons"""
    # Supprime les quantités au début
    ing = re.sub(r'^\d+[\.,]?\d*\s*(g|kg|ml|cl|l|c\.à\.s|c\.à\.c)?\s*', '', ingredient.lower())
    return ing.strip()

# --- INTERFACE STREAMLIT ---
st.set_page_config(
    page_title="Mes Courses Web", 
    page_icon="🛒",
    layout="wide"
)

st.title("🛒 Planning & Courses")
st.markdown("Organisez vos repas et générez votre liste de courses automatiquement !")

# Initialisation du stockage
if 'planning' not in st.session_state:
    st.session_state.planning = []

# --- BARRE LATÉRALE : AJOUT ---
with st.sidebar:
    st.header("➕ Ajouter une recette")
    
    url_input = st.text_input(
        "Lien Marmiton ou 750g",
        placeholder="https://www.marmiton.org/...",
        help="Collez l'URL complète de la recette"
    )
    
    nb_pers = st.number_input(
        "Nombre de personnes", 
        min_value=1, 
        max_value=20,
        value=4,
        help="Les quantités seront ajustées automatiquement"
    )
    
    if st.button("➕ Ajouter au planning", type="primary", use_container_width=True):
        if not url_input:
            st.warning("Veuillez saisir une URL")
        elif not ("marmiton.org" in url_input or "750g.com" in url_input):
            st.error("Seuls Marmiton et 750g sont supportés")
        else:
            with st.spinner("🔍 Analyse de la recette..."):
                data = extraire_recette(url_input, nb_pers)
                
                if data and data.get("ingredients"):
                    data["url"] = url_input
                    st.session_state.planning.append(data)
                    st.success(f"✅ Ajouté : {data['titre']}")
                    st.balloons()
                else:
                    st.error("❌ Impossible de lire cette recette. Vérifiez l'URL.")
    
    st.divider()
    
    # Statistiques
    if st.session_state.planning:
        st.metric("Recettes", len(st.session_state.planning))
        total_ing = sum(len(r["ingredients"]) for r in st.session_state.planning)
        st.metric("Ingrédients total", total_ing)

# --- AFFICHAGE PRINCIPAL ---
tab1, tab2 = st.tabs(["📅 Mon Planning", "🛍️ Ma Liste de Courses"])

with tab1:
    if not st.session_state.planning:
        st.info("👋 Votre planning est vide. Ajoutez des recettes via la barre latérale.")
    else:
        st.markdown(f"### {len(st.session_state.planning)} recette(s) au menu")
        
        for i, recette in enumerate(st.session_state.planning):
            with st.container():
                col1, col2, col3 = st.columns([0.7, 0.2, 0.1])
                
                with col1:
                    st.markdown(f"**{i+1}. {recette['titre']}**")
                
                with col2:
                    with st.expander("📝 Voir ingrédients"):
                        for ing in recette["ingredients"]:
                            st.text(f"• {ing}")
                
                with col3:
                    if st.button("🗑️", key=f"del_{i}", help="Supprimer"):
                        st.session_state.planning.pop(i)
                        st.rerun()
                
                st.divider()

with tab2:
    if not st.session_state.planning:
        st.info("📭 Rien à acheter pour l'instant. Ajoutez des recettes à votre planning !")
    else:
        st.markdown("### 🛒 Votre liste de courses")
        
        # Regroupement par rayon avec normalisation
        par_rayon = {r: {} for r in RAYONS.keys()}
        
        for recette in st.session_state.planning:
            for ing in recette["ingredients"]:
                rayon = determiner_rayon(ing)
                ing_normalise = normaliser_ingredient(ing)
                
                # Garde la version la plus complète de l'ingrédient
                if ing_normalise not in par_rayon[rayon]:
                    par_rayon[rayon][ing_normalise] = ing
        
        # Affichage par rayon
        for rayon, items_dict in par_rayon.items():
            if items_dict:
                st.subheader(rayon)
                items_sorted = sorted(items_dict.values())
                
                cols = st.columns(2)
                for idx, item in enumerate(items_sorted):
                    with cols[idx % 2]:
                        st.checkbox(item, key=f"check_{rayon}_{idx}")
                
                st.divider()
        
        # Bouton d'export
        if st.button("📋 Copier la liste", use_container_width=True):
            liste_texte = ""
            for rayon, items_dict in par_rayon.items():
                if items_dict:
                    liste_texte += f"\n{rayon}\n"
                    for item in sorted(items_dict.values()):
                        liste_texte += f"☐ {item}\n"
            
            st.code(liste_texte, language=None)
            st.success("✅ Liste prête à copier !")

# --- BOUTON DE RESET ---
st.divider()
col1, col2, col3 = st.columns([1, 1, 1])
with col2:
    if st.button("🔄 Tout réinitialiser", type="secondary", use_container_width=True):
        if st.session_state.planning:
            st.session_state.planning = []
            st.rerun()
        else:
            st.info("Le planning est déjà vide")
