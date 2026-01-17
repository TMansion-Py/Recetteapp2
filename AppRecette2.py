import streamlit as st
import cloudscraper
from bs4 import BeautifulSoup
import re

st.set_page_config(page_title="Marmiton Multi-Perso", page_icon="🍳")


def extraire_recette(url, nb_pers_voulu):
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows'})
    try:
        response = scraper.get(url, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')

        # 1. Trouver le nombre de personnes original
        # Marmiton utilise souvent un sélecteur pour le nombre de portions
        nb_pers_orig_tag = soup.select_one('.recipe-ingredients__qt-counter-value') or \
                           soup.select_one('.shorthand-counter__value')

        nb_pers_orig = int(nb_pers_orig_tag.text.strip()) if nb_pers_orig_tag else 4
        ratio = nb_pers_voulu / nb_pers_orig

        # 2. Extraire les ingrédients
        items = soup.select('.recipe-ingredients__list__item')
        ingredients_calcules = []

        for item in items:
            qty_tag = item.select_one('.count')
            unit_tag = item.select_one('.unit')
            name_tag = item.select_one('.ingredient-name')

            name = name_tag.text.strip() if name_tag else ""
            unit = unit_tag.text.strip() if unit_tag else ""

            # Calcul de la nouvelle quantité
            try:
                if qty_tag and qty_tag.text.strip():
                    # On convertit en float (gestion des virgules françaises)
                    valeur = float(qty_tag.text.strip().replace(',', '.'))
                    nouvelle_qty = round(valeur * ratio, 2)
                    # On enlève le .0 si c'est un entier
                    nouvelle_qty = int(nouvelle_qty) if nouvelle_qty.is_integer() else nouvelle_qty
                else:
                    nouvelle_qty = ""
            except:
                nouvelle_qty = qty_tag.text.strip() if qty_tag else ""

            full_text = f"{nouvelle_qty} {unit} {name}".strip()
            ingredients_calcules.append(full_text)

        return ingredients_calcules
    except:
        return []


# --- INTERFACE ---
st.title("🍳 Marmiton x Intermarché")

col1, col2 = st.columns(2)
with col1:
    nb_pers = st.number_input("Nombre de personnes :", min_value=1, value=4)
with col2:
    st.write("Ajuste les quantités automatiquement !")

liens_input = st.text_area("Colle tes liens Marmiton :", height=150)

if st.button("Générer la liste"):
    urls = [u.strip() for u in liens_input.split('\n') if u.strip()]
    if urls:
        liste_finale = []
        for url in urls:
            res = extraire_recette(url, nb_pers)
            liste_finale.extend(res)

        st.subheader(f"🛒 Liste pour {nb_pers} personnes")
        for ing in sorted(liste_finale):
            recherche_url = f"https://www.intermarche.com/recherche/{ing.split(' ')[-1]}"  # On cherche le dernier mot
            c1, c2 = st.columns([0.85, 0.15])
            c1.checkbox(ing, key=ing)
            c2.markdown(f"[🛒]({recherche_url})")