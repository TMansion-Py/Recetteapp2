import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
from fractions import Fraction
from collections import defaultdict

st.set_page_config(page_title="Liste de Courses Marmiton", page_icon="🛒", layout="wide")

def extract_marmiton_recipe(url):
    """Extrait les informations d'une recette Marmiton"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extraction du titre
        title_elem = soup.find('h1', class_='SHRD__sc-10plygc-0')
        title = title_elem.text.strip() if title_elem else "Recette sans titre"
        
        # Extraction du nombre de personnes
        servings_elem = soup.find('span', class_='SHRD__sc-w4kphj-0')
        servings = 4  # valeur par défaut
        if servings_elem:
            servings_text = servings_elem.text
            match = re.search(r'\d+', servings_text)
            if match:
                servings = int(match.group())
        
        # Extraction des ingrédients
        ingredients = []
        ingredient_elems = soup.find_all('span', class_='SHRD__sc-1s5xfvn-0')
        
        for elem in ingredient_elems:
            ingredient_text = elem.text.strip()
            if ingredient_text:
                ingredients.append(ingredient_text)
        
        return {
            'title': title,
            'servings': servings,
            'ingredients': ingredients,
            'url': url
        }
    except Exception as e:
        st.error(f"Erreur lors de l'extraction : {str(e)}")
        return None

def parse_ingredient(ingredient_text, ratio):
    """Parse un ingrédient et ajuste la quantité selon le ratio"""
    # Recherche de quantité au début
    patterns = [
        r'^(\d+(?:[.,]\d+)?(?:\s*/\s*\d+)?)\s*(kg|g|l|ml|cl|cuillères?|c\.|càs|càc|pincée|gousse|feuille|branche|botte)?\s+(?:de\s+|d\')?(.+)',
        r'^(\d+(?:[.,]\d+)?)\s+(.+)',
        r'^(.+)'
    ]
    
    for pattern in patterns:
        match = re.match(pattern, ingredient_text, re.IGNORECASE)
        if match:
            groups = match.groups()
            
            if len(groups) == 3:
                quantity_str, unit, name = groups
                quantity = parse_quantity(quantity_str) * ratio
                unit = unit if unit else ""
                return quantity, unit.strip(), name.strip()
            elif len(groups) == 2:
                quantity_str, name = groups
                try:
                    quantity = parse_quantity(quantity_str) * ratio
                    return quantity, "", name.strip()
                except:
                    return None, "", ingredient_text.strip()
            else:
                return None, "", groups[0].strip()
    
    return None, "", ingredient_text.strip()

def parse_quantity(qty_str):
    """Convertit une chaîne de quantité en nombre"""
    qty_str = qty_str.replace(',', '.').strip()
    
    if '/' in qty_str:
        try:
            return float(Fraction(qty_str))
        except:
            parts = qty_str.split('/')
            if len(parts) == 2:
                try:
                    return float(parts[0]) / float(parts[1])
                except:
                    return float(qty_str.split()[0])
    
    return float(qty_str)

def format_quantity(qty):
    """Formate une quantité pour l'affichage"""
    if qty is None:
        return ""
    if qty == int(qty):
        return str(int(qty))
    return f"{qty:.1f}".rstrip('0').rstrip('.')

def merge_ingredients(recipes_data):
    """Fusionne les ingrédients de plusieurs recettes"""
    merged = defaultdict(lambda: defaultdict(float))
    non_quantified = defaultdict(set)
    
    for recipe in recipes_data:
        ratio = recipe['target_servings'] / recipe['original_servings']
        
        for ingredient in recipe['ingredients']:
            qty, unit, name = parse_ingredient(ingredient, ratio)
            name_lower = name.lower()
            
            if qty is not None:
                key = (name_lower, unit.lower())
                merged[key]['quantity'] += qty
                merged[key]['name'] = name
                merged[key]['unit'] = unit
            else:
                non_quantified[name_lower].add(recipe['title'])
    
    return merged, non_quantified

# Interface Streamlit
st.title("🛒 Générateur de Liste de Courses Marmiton")
st.markdown("Ajoutez des recettes Marmiton et générez automatiquement votre liste de courses !")

# Initialisation de la session
if 'recipes' not in st.session_state:
    st.session_state.recipes = []

# Section d'ajout de recette
st.header("➕ Ajouter une recette")
col1, col2 = st.columns([3, 1])

with col1:
    recipe_url = st.text_input("URL de la recette Marmiton", placeholder="https://www.marmiton.org/recettes/...")

with col2:
    nb_persons = st.number_input("Nombre de personnes", min_value=1, max_value=50, value=4)

if st.button("Ajouter la recette", type="primary"):
    if recipe_url:
        with st.spinner("Extraction de la recette en cours..."):
            recipe_data = extract_marmiton_recipe(recipe_url)
            
            if recipe_data:
                st.session_state.recipes.append({
                    'title': recipe_data['title'],
                    'original_servings': recipe_data['servings'],
                    'target_servings': nb_persons,
                    'ingredients': recipe_data['ingredients'],
                    'url': recipe_data['url']
                })
                st.success(f"✅ Recette '{recipe_data['title']}' ajoutée !")
                st.rerun()
    else:
        st.warning("Veuillez entrer une URL de recette")

# Affichage des recettes ajoutées
if st.session_state.recipes:
    st.header("📋 Recettes ajoutées")
    
    for idx, recipe in enumerate(st.session_state.recipes):
        with st.expander(f"{recipe['title']} - {recipe['target_servings']} personnes"):
            st.write(f"**Nombre de personnes original :** {recipe['original_servings']}")
            st.write(f"**Nombre de personnes souhaité :** {recipe['target_servings']}")
            st.write("**Ingrédients :**")
            for ing in recipe['ingredients']:
                st.write(f"- {ing}")
            
            if st.button(f"🗑️ Supprimer", key=f"del_{idx}"):
                st.session_state.recipes.pop(idx)
                st.rerun()
    
    # Génération de la liste de courses
    st.header("🛍️ Liste de Courses")
    
    if st.button("Générer la liste de courses", type="primary"):
        merged, non_quantified = merge_ingredients(st.session_state.recipes)
        
        st.subheader("Ingrédients à acheter :")
        
        # Ingrédients avec quantités
        if merged:
            for (name_lower, unit_lower), data in sorted(merged.items()):
                qty_str = format_quantity(data['quantity'])
                unit_display = f" {data['unit']}" if data['unit'] else ""
                st.write(f"- **{qty_str}{unit_display}** {data['name']}")
        
        # Ingrédients sans quantités
        if non_quantified:
            st.subheader("Autres ingrédients (sans quantité précise) :")
            for name, recipes in sorted(non_quantified.items()):
                recipe_list = ", ".join(recipes)
                st.write(f"- {name.capitalize()} _(de : {recipe_list})_")
        
        # Option de téléchargement
        shopping_list_text = "LISTE DE COURSES\n" + "="*50 + "\n\n"
        
        if merged:
            shopping_list_text += "INGRÉDIENTS AVEC QUANTITÉS :\n"
            for (name_lower, unit_lower), data in sorted(merged.items()):
                qty_str = format_quantity(data['quantity'])
                unit_display = f" {data['unit']}" if data['unit'] else ""
                shopping_list_text += f"- {qty_str}{unit_display} {data['name']}\n"
        
        if non_quantified:
            shopping_list_text += "\nAUTRES INGRÉDIENTS :\n"
            for name in sorted(non_quantified.keys()):
                shopping_list_text += f"- {name.capitalize()}\n"
        
        st.download_button(
            label="📥 Télécharger la liste",
            data=shopping_list_text,
            file_name="liste_courses.txt",
            mime="text/plain"
        )

else:
    st.info("👆 Ajoutez votre première recette pour commencer !")

# Bouton pour tout effacer
if st.session_state.recipes:
    if st.button("🗑️ Tout effacer"):
        st.session_state.recipes = []
        st.rerun()
