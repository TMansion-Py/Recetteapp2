import streamlit as st
import cloudscraper
from bs4 import BeautifulSoup
import re

# --- CONFIGURATION DES RAYONS ---
RAYONS = {
    "🍎 Fruits & Légumes": ["pomme", "carotte", "oignon", "ail", "salade", "tomate", "courgette", "pomme de terre", "citron", "poivron", "champignon", "herbes", "échalote", "bouquet garni"],
    "🧀 Crèmerie & Œufs": ["lait", "beurre", "oeuf", "crème", "fromage", "yaourt", "parmesan", "gruyère", "mozzarella", "emmental"],
    "🥩 Boucherie & Poisson": ["poulet", "boeuf", "lardons", "saumon", "jambon", "crevette", "viande", "steak", "porc", "thon", "poitrine", "paleron"],
    "🍝 Épicerie": ["farine", "sucre", "sel", "huile", "pâte", "riz", "conserve", "épice", "chocolat", "levure", "moutarde", "bouillon", "sauce", "poivre", "miel", "vin"],
    "📦 Autre": []
}

def determiner_rayon(ingredient):
    ing_low = ingredient.lower()
    for rayon, mots_cles in RAYONS.items():
        if any(mot in ing_low for mot in mots_cles): return rayon
    return "📦 Autre"

def extraire_recette(url, nb_pers_voulu):
    # Création d'un scraper qui imite parfaitement un humain
    scraper = cloudscraper.create_scraper(
        browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False}
    )
    
    try:
        # On ajoute des headers manuels très précis
        headers = {
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'accept-language': 'fr-FR,fr;q=0.9',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        response = scraper.get(url, headers=headers, timeout=20)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 1. Extraction du Titre
        titre = "Recette"
        if soup.h1: titre = soup.h1.get_text().strip()

        # 2. Extraction du nombre de personnes original
        nb_orig = 4
        # On cherche le texte qui contient "pers" ou le compteur Marmiton
        pers_text = soup.find(text=re.compile(r'pers', re.I))
        if pers_text:
            digits = re.findall(r'\d+', pers_text)
            if digits: nb_orig = int(digits[0])
        
        ratio = nb_pers_voulu / nb_orig

        # 3. Extraction des ingrédients (Méthode de secours large)
        ingredients = []
        
        # On cherche toutes les lignes qui ont une classe contenant "ingredient"
        items = soup.find_all(class_=re.compile(r'ingredient', re.I))
        
        for item in items:
            # On cherche le nom, la quantité et l'unité à l'intérieur de l'item
            name_tag = item.find(class_=re.compile(r'name', re.I))
            qty_tag = item.find(class_=re.compile(r'count', re.I))
            unit_tag = item.find(class_=re.compile(r'unit', re.I))
            
            if name_tag:
                name = name_tag.get_text().strip()
                unit = unit_tag.get_text().strip() if unit_tag else ""
                
                qty_val = ""
                if qty_tag:
                    raw_qty = qty_tag.get_text().strip().replace(',', '.')
                    try:
                        val = float(raw_qty) * ratio
                        qty_val = int(val) if val.is_integer() else round(val, 1)
                    except:
                        qty_val = raw_qty
                
                full_ing = f"{qty_val} {unit} {name}".strip()
                if full_ing not in ingredients and len(full_ing) > 2:
                    ingredients.append(full_ing)

        return {"titre": titre, "ingredients": ingredients}
    except Exception as e:
        return None

# --- INTERFACE ---
st.title("👨‍🍳 Mon Assistant Courses")

if 'planning' not in st.session_state:
    st.session_state.planning = []

url_input = st.text_input("Lien de la recette (Marmiton ou 750g)")
nb_pers = st.number_input("Nombre de personnes", min_value=1, value=4)

if st.button("Ajouter à la liste"):
    if url_input:
        with st.spinner("Recherche des ingrédients..."):
            res = extraire_recette(url_input, nb_pers)
            if res and res["ingredients"]:
                st.session_state.planning.append(res)
                st.success(f"Ajouté : {res['titre']}")
            else:
                st.error("Marmiton bloque la lecture automatique. Essayez de rafraîchir ou vérifiez le lien.")

# Affichage des résultats
if st.session_state.planning:
    par_rayon = {r: set() for r in RAYONS.keys()}
    for rec in st.session_state.planning:
        for ing in rec["ingredients"]:
            par_rayon[determiner_rayon(ing)].add(ing)
            
    for rayon, items in par_rayon.items():
        if items:
            st.subheader(rayon)
            for it in sorted(items):
                st.checkbox(it, key=it)
