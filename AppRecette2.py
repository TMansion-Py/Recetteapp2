import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
from fractions import Fraction
from collections import defaultdict
import json
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

st.set_page_config(page_title="Liste de Courses Marmiton", page_icon="🛒", layout="wide")

def extract_marmiton_recipe(url):
    """Extrait les informations d'une recette Marmiton"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # DEBUG: Sauvegarder le HTML
        with st.expander("🔍 DEBUG - Voir le code HTML (pour diagnostic)"):
            st.code(soup.prettify()[:3000] + "...", language="html")
        
        # Extraction du titre
        title = "Recette sans titre"
        
        # Essayer plusieurs sélecteurs pour le titre
        title_elem = soup.find('h1')
        if title_elem:
            title = title_elem.get_text(strip=True)
        
        # Extraction du nombre de personnes
        servings = 4
        text_content = soup.get_text()
        servings_match = re.search(r'(\d+)\s*(?:pers(?:onnes?)?|conv(?:ives?)?)', text_content, re.IGNORECASE)
        if servings_match:
            servings = int(servings_match.group(1))
        
        # Extraction des ingrédients - MÉTHODE AMÉLIORÉE
        ingredients = []
        
        # Méthode 1: Chercher dans le JSON-LD (données structurées)
        json_scripts = soup.find_all('script', type='application/ld+json')
        for script in json_scripts:
            try:
                data = json.loads(script.string)
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and 'recipeIngredient' in item:
                            ingredients = item['recipeIngredient']
                            break
                elif isinstance(data, dict) and 'recipeIngredient' in data:
                    ingredients = data['recipeIngredient']
                
                if ingredients:
                    break
            except:
                continue
        
        # Méthode 2: Chercher toutes les listes possibles
        if not ingredients:
            # Chercher tous les éléments qui pourraient contenir des ingrédients
            possible_containers = soup.find_all(['ul', 'ol', 'div'], class_=re.compile(r'ingredient', re.IGNORECASE))
            
            for container in possible_containers:
                items = container.find_all(['li', 'p', 'div'])
                temp_ingredients = []
                for item in items:
                    text = item.get_text(strip=True)
                    # Filtrer les textes qui ressemblent à des ingrédients
                    if text and 3 < len(text) < 200 and not text.startswith('http'):
                        temp_ingredients.append(text)
                
                if len(temp_ingredients) >= 3:  # Au moins 3 ingrédients
                    ingredients = temp_ingredients
                    break
        
        # Méthode 3: Chercher tous les spans/divs avec du texte qui ressemble à des ingrédients
        if not ingredients:
            all_elements = soup.find_all(['span', 'div', 'li'])
            for elem in all_elements:
                text = elem.get_text(strip=True)
                # Pattern pour détecter un ingrédient (commence par un chiffre ou contient des mots clés)
                if re.match(r'^\d+', text) or any(word in text.lower() for word in ['huile', 'sel', 'poivre', 'farine', 'sucre', 'beurre', 'oeuf', 'lait']):
                    if 3 < len(text) < 200 and text not in ingredients:
                        ingredients.append(text)
        
        return {
            'title': title,
            'servings': servings,
            'ingredients': ingredients[:50],  # Limiter à 50 ingrédients max
            'url': url
        }
    except Exception as e:
        st.error(f"❌ Erreur lors de l'extraction : {str(e)}")
        import traceback
        st.code(traceback.format_exc())
        return None

def parse_ingredient(ingredient_text, ratio):
    """Parse un ingrédient et ajuste la quantité selon le ratio"""
    patterns = [
        r'^(\d+(?:[.,]\d+)?(?:\s*/\s*\d+)?)\s*(kg|g|l|ml|cl|cuillères?|cuillère|c\.|càs|càc|cs|cc|pincée|gousse|feuille|branche|botte)?\s+(?:de\s+|d\')?(.+)',
        r'^(\d+(?:[.,]\d+)?)\s+(.+)',
    ]
    
    for pattern in patterns:
        match = re.match(pattern, ingredient_text, re.IGNORECASE)
        if match:
            groups = match.groups()
            
            if len(groups) == 3:
                quantity_str, unit, name = groups
                try:
                    quantity = parse_quantity(quantity_str) * ratio
                    unit = unit if unit else ""
                    return quantity, unit.strip(), name.strip()
                except:
                    pass
            elif len(groups) == 2:
                quantity_str, name = groups
                try:
                    quantity = parse_quantity(quantity_str) * ratio
                    return quantity, "", name.strip()
                except:
                    pass
    
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

def generate_pdf(recipes_data, merged, non_quantified):
    """Génère un PDF avec les recettes et la liste de courses"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor='#2E86AB',
        spaceAfter=30,
        alignment=TA_CENTER
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        textColor='#A23B72',
        spaceAfter=12,
        spaceBefore=20
    )
    
    normal_style = styles['Normal']
    normal_style.fontSize = 11
    normal_style.leading = 14
    
    # Construction du document
    story = []
    
    # Titre principal
    story.append(Paragraph("🛒 Ma Liste de Courses", title_style))
    story.append(Spacer(1, 0.5*cm))
    
    # Section recettes
    story.append(Paragraph("📋 Mes Recettes", heading_style))
    
    for idx, recipe in enumerate(recipes_data, 1):
        recipe_title = f"{idx}. <b>{recipe['title']}</b>"
        story.append(Paragraph(recipe_title, normal_style))
        
        persons_info = f"Pour {recipe['target_servings']} personne(s)"
        if recipe['target_servings'] != recipe['original_servings']:
            persons_info += f" (recette originale: {recipe['original_servings']} personne(s))"
        story.append(Paragraph(persons_info, normal_style))
        
        if recipe['url'] != 'Saisie manuelle':
            url_text = f"<link href='{recipe['url']}'>{recipe['url']}</link>"
            story.append(Paragraph(url_text, normal_style))
        
        story.append(Spacer(1, 0.3*cm))
    
    story.append(Spacer(1, 0.5*cm))
    
    # Section liste de courses
    story.append(Paragraph("🛍️ Liste de Courses", heading_style))
    story.append(Spacer(1, 0.3*cm))
    
    # Ingrédients avec quantités
    if merged:
        story.append(Paragraph("<b>Ingrédients avec quantités :</b>", normal_style))
        story.append(Spacer(1, 0.2*cm))
        
        for (name_lower, unit_lower), data in sorted(merged.items()):
            qty_str = format_quantity(data['quantity'])
            unit_display = f" {data['unit']}" if data['unit'] else ""
            ingredient_text = f"• <b>{qty_str}{unit_display}</b> {data['name']}"
            story.append(Paragraph(ingredient_text, normal_style))
        
        story.append(Spacer(1, 0.5*cm))
    
    # Ingrédients sans quantités
    if non_quantified:
        story.append(Paragraph("<b>Autres ingrédients :</b>", normal_style))
        story.append(Spacer(1, 0.2*cm))
        
        for name in sorted(non_quantified.keys()):
            story.append(Paragraph(f"• {name.capitalize()}", normal_style))
    
    # Génération du PDF
    doc.build(story)
    buffer.seek(0)
    return buffer

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

# Initialisation de la session
if 'recipes' not in st.session_state:
    st.session_state.recipes = []
if 'manual_mode' not in st.session_state:
    st.session_state.manual_mode = False

# Interface Streamlit
st.title("🛒 Générateur de Liste de Courses Marmiton")
st.markdown("Ajoutez des recettes Marmiton et générez automatiquement votre liste de courses !")

# Onglets pour mode automatique et manuel
tab1, tab2 = st.tabs(["📡 Extraction automatique", "✍️ Saisie manuelle"])

with tab1:
    st.header("➕ Ajouter une recette automatiquement")
    col1, col2 = st.columns([3, 1])

    with col1:
        recipe_url = st.text_input("URL de la recette Marmiton", placeholder="https://www.marmiton.org/recettes/...")

    with col2:
        nb_persons = st.number_input("Nombre de personnes", min_value=1, max_value=50, value=4, key="auto_persons")

    if st.button("Extraire et ajouter la recette", type="primary", key="extract_btn"):
        if recipe_url:
            with st.spinner("Extraction de la recette en cours..."):
                recipe_data = extract_marmiton_recipe(recipe_url)
                
                if recipe_data and recipe_data['ingredients']:
                    st.session_state.recipes.append({
                        'title': recipe_data['title'],
                        'original_servings': recipe_data['servings'],
                        'target_servings': nb_persons,
                        'ingredients': recipe_data['ingredients'],
                        'url': recipe_data['url']
                    })
                    st.success(f"✅ Recette '{recipe_data['title']}' ajoutée avec {len(recipe_data['ingredients'])} ingrédients !")
                    
                    with st.expander("Voir les ingrédients extraits"):
                        for ing in recipe_data['ingredients']:
                            st.write(f"- {ing}")
                    
                    st.rerun()
                elif recipe_data and not recipe_data['ingredients']:
                    st.warning("⚠️ Aucun ingrédient extrait. Utilisez l'onglet 'Saisie manuelle' pour ajouter la recette.")
        else:
            st.warning("Veuillez entrer une URL de recette")

with tab2:
    st.header("✍️ Ajouter une recette manuellement")
    
    with st.form("manual_recipe_form"):
        manual_title = st.text_input("Nom de la recette")
        
        col1, col2 = st.columns(2)
        with col1:
            manual_servings = st.number_input("Nombre de personnes (original)", min_value=1, value=4)
        with col2:
            manual_target = st.number_input("Nombre de personnes (souhaité)", min_value=1, value=4)
        
        manual_ingredients = st.text_area(
            "Ingrédients (un par ligne)",
            placeholder="200g de farine\n3 oeufs\n1 litre de lait\n...",
            height=200
        )
        
        submitted = st.form_submit_button("➕ Ajouter cette recette", type="primary")
        
        if submitted:
            if manual_title and manual_ingredients:
                ingredients_list = [ing.strip() for ing in manual_ingredients.split('\n') if ing.strip()]
                
                st.session_state.recipes.append({
                    'title': manual_title,
                    'original_servings': manual_servings,
                    'target_servings': manual_target,
                    'ingredients': ingredients_list,
                    'url': 'Saisie manuelle'
                })
                st.success(f"✅ Recette '{manual_title}' ajoutée avec {len(ingredients_list)} ingrédients !")
                st.rerun()
            else:
                st.warning("Veuillez remplir le titre et les ingrédients")

# Affichage des recettes ajoutées
if st.session_state.recipes:
    st.header("📋 Recettes ajoutées")
    
    for idx, recipe in enumerate(st.session_state.recipes):
        with st.expander(f"{recipe['title']} - {recipe['target_servings']} personnes"):
            st.write(f"**Personnes (original) :** {recipe['original_servings']}")
            st.write(f"**Personnes (souhaité) :** {recipe['target_servings']}")
            st.write(f"**Source :** {recipe['url']}")
            st.write("**Ingrédients :**")
            for ing in recipe['ingredients']:
                st.write(f"- {ing}")
            
            if st.button(f"🗑️ Supprimer", key=f"del_{idx}"):
                st.session_state.recipes.pop(idx)
                st.rerun()
    
    # Génération de la liste de courses
    st.header("🛍️ Liste de Courses")
    
    if st.button("🎯 Générer la liste de courses", type="primary"):
        merged, non_quantified = merge_ingredients(st.session_state.recipes)
        
        st.subheader("📝 Ingrédients à acheter :")
        
        # Ingrédients avec quantités
        if merged:
            st.write("**Avec quantités :**")
            for (name_lower, unit_lower), data in sorted(merged.items()):
                qty_str = format_quantity(data['quantity'])
                unit_display = f" {data['unit']}" if data['unit'] else ""
                st.write(f"- **{qty_str}{unit_display}** {data['name']}")
        
        # Ingrédients sans quantités
        if non_quantified:
            st.write("")
            st.write("**Autres ingrédients :**")
            for name in sorted(non_quantified.keys()):
                st.write(f"- {name.capitalize()}")
        
        if not merged and not non_quantified:
            st.warning("⚠️ Aucun ingrédient à afficher. Vérifiez que vos recettes contiennent bien des ingrédients.")
        
        # Options de téléchargement
        if merged or non_quantified:
            col_dl1, col_dl2 = st.columns(2)
            
            with col_dl1:
                # PDF
                pdf_buffer = generate_pdf(st.session_state.recipes, merged, non_quantified)
                st.download_button(
                    label="📥 Télécharger en PDF",
                    data=pdf_buffer,
                    file_name="liste_courses.pdf",
                    mime="application/pdf",
                    type="primary"
                )
            
            with col_dl2:
                # TXT
                shopping_list_text = "LISTE DE COURSES\n" + "="*50 + "\n\n"
                shopping_list_text += "MES RECETTES :\n"
                for idx, recipe in enumerate(st.session_state.recipes, 1):
                    shopping_list_text += f"{idx}. {recipe['title']}\n"
                    shopping_list_text += f"   Pour {recipe['target_servings']} personne(s)\n"
                    if recipe['url'] != 'Saisie manuelle':
                        shopping_list_text += f"   {recipe['url']}\n"
                    shopping_list_text += "\n"
                
                shopping_list_text += "\n" + "="*50 + "\n\n"
                
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
                    label="📥 Télécharger en TXT",
                    data=shopping_list_text,
                    file_name="liste_courses.txt",
                    mime="text/plain"
                )

else:
    st.info("👆 Ajoutez votre première recette pour commencer !")

# Bouton pour tout effacer
if st.session_state.recipes:
    st.divider()
    if st.button("🗑️ Tout effacer", type="secondary"):
        st.session_state.recipes = []
        st.rerun()
