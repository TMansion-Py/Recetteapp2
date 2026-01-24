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
        
        # Extraction du titre - plusieurs méthodes
        title = "Recette sans titre"
        title_selectors = [
            ('h1', {'class_': 'SHRD__sc-10plygc-0'}),
            ('h1', {}),
            ('meta', {'property': 'og:title'})
        ]
        
        for tag, attrs in title_selectors:
            elem = soup.find(tag, attrs)
            if elem:
                if tag == 'meta':
                    title = elem.get('content', title)
                else:
                    title = elem.text.strip()
                break
        
        # Extraction du nombre de personnes - plusieurs méthodes
        servings = 4
        servings_patterns = [
            (r'pour\s+(\d+)\s+personnes?', re.IGNORECASE),
            (r'(\d+)\s+personnes?', re.IGNORECASE),
        ]
        
        # Chercher dans les spans
        servings_elem = soup.find('span', class_='SHRD__sc-w4kphj-0')
        if not servings_elem:
            servings_elem = soup.find(string=re.compile(r'personnes?', re.IGNORECASE))
        
        if servings_elem:
            servings_text = str(servings_elem)
            for pattern, flags in servings_patterns:
                match = re.search(pattern, servings_text, flags)
                if match:
                    servings = int(match.group(1))
                    break
        
        # Extraction des ingrédients - PLUSIEURS MÉTHODES
        ingredients = []
        
        # Méthode 1: Classes spécifiques Marmiton
        ingredient_classes = [
            'SHRD__sc-1s5xfvn-0',
            'ingredient',
            'recipe-ingredient',
            'ingredient-item'
        ]
        
        for class_name in ingredient_classes:
            ingredient_elems = soup.find_all('span', class_=class_name)
            if not ingredient_elems:
                ingredient_elems = soup.find_all('li', class_=class_name)
            if not ingredient_elems:
                ingredient_elems = soup.find_all('div', class_=class_name)
            
            if ingredient_elems:
                for elem in ingredient_elems:
                    ingredient_text = elem.get_text(strip=True)
                    if ingredient_text and len(ingredient_text) > 2:
                        ingredients.append(ingredient_text)
                break
        
        # Méthode 2: Recherche dans les listes
        if not ingredients:
            lists = soup.find_all(['ul', 'ol'])
            for lst in lists:
                items = lst.find_all('li')
                if items and len(items) > 2:  # Probablement une liste d'ingrédients
                    temp_ingredients = []
                    for item in items:
                        text = item.get_text(strip=True)
                        if text and len(text) > 2:
                            temp_ingredients.append(text)
                    if temp_ingredients:
                        ingredients = temp_ingredients
                        break
        
        # Méthode 3: Recherche par pattern JSON-LD
        if not ingredients:
            json_ld = soup.find('script', type='application/ld+json')
            if json_ld:
                try:
                    import json
                    data = json.loads(json_ld.string)
                    if isinstance(data, list):
                        data = data[0]
                    if 'recipeIngredient' in data:
                        ingredients = data['recipeIngredient']
                    elif 'ingredients' in data:
                        ingredients = data['ingredients']
                except:
                    pass
        
        # Affichage debug
        st.info(f"🔍 Recette trouvée: {title}")
        st.info(f"👥 Pour {servings} personnes")
        st.info(f"📝 {len(ingredients)} ingrédients extraits")
        
        if not ingredients:
            st.warning("⚠️ Aucun ingrédient extrait automatiquement. Vous pouvez les ajouter manuellement ci-dessous.")
        
        return {
            'title': title,
            'servings': servings,
            'ingredients': ingredients,
            'url': url
        }
    except Exception as e:
        st.error(f"❌ Erreur lors de l'extraction : {str(e)}")
        import traceback
        st.error(traceback.format_exc())
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
                st.success(f"✅ Recette '{recipe_data['title']}' ajoutée avec {len(recipe_data['ingredients'])} ingrédients!")
                
                # Afficher les ingrédients extraits
                if recipe_data['ingredients']:
                    with st.expander("Voir les ingrédients extraits"):
                        for ing in recipe_data['ingredients']:
                            st.write(f"- {ing}")
                
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
