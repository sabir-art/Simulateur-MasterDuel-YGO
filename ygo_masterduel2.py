import sys
import streamlit as st
import json
import time
import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import hypergeom

# ------------------ LANGUE ------------------
LANGS = {
    'Français': 'fr',
    'English': 'en'
}
lang_choice = st.sidebar.selectbox("Langue / Language", list(LANGS.keys()), index=0)
lang = LANGS[lang_choice]

# ------------------ CONFIG DECK ------------------
if "deck_name" not in st.session_state:
    st.session_state["deck_name"] = "Mon deck"
if "deck_size" not in st.session_state:
    st.session_state["deck_size"] = 40
if "hand_size" not in st.session_state:
    st.session_state["hand_size"] = 5
if "first_player" not in st.session_state:
    st.session_state["first_player"] = True
if "n_sim" not in st.session_state:
    st.session_state["n_sim"] = 10000

st.sidebar.markdown("### Paramètres du deck")
st.session_state["deck_name"] = st.sidebar.text_input(
    "Nom du deck", st.session_state["deck_name"])
st.session_state["deck_size"] = st.sidebar.number_input(
    "Taille du deck", 30, 60, st.session_state["deck_size"])
st.session_state["hand_size"] = st.sidebar.number_input(
    "Taille de la main de départ", 4, 7, st.session_state["hand_size"])
who = st.sidebar.radio("Qui commence ?",
    ["Moi (First)", "L'adversaire (Second)"],
    index=0 if st.session_state["first_player"] else 1,
    horizontal=True)
st.session_state["first_player"] = (who == "Moi (First)")

st.session_state["n_sim"] = st.sidebar.number_input(
    "Nombre de simulations Monte Carlo", 1000, 50000, st.session_state["n_sim"], step=1000
)

# -- Export/Import JSON --
def export_deck_config():
    data = {
        "deck_name": st.session_state["deck_name"],
        "deck_size": st.session_state["deck_size"],
        "hand_size": st.session_state["hand_size"],
        "first_player": st.session_state["first_player"],
        "n_sim": st.session_state["n_sim"]
    }
    st.download_button("Exporter le deck", data=json.dumps(data), file_name="deck_config.json")

def import_deck_config():
    file = st.sidebar.file_uploader("Importer un deck (JSON)", type=["json"])
    if file is not None:
        config = json.load(file)
        st.session_state["deck_name"] = config.get("deck_name", st.session_state["deck_name"])
        st.session_state["deck_size"] = config.get("deck_size", st.session_state["deck_size"])
        st.session_state["hand_size"] = config.get("hand_size", st.session_state["hand_size"])
        st.session_state["first_player"] = config.get("first_player", st.session_state["first_player"])
        st.session_state["n_sim"] = config.get("n_sim", st.session_state["n_sim"])
        st.sidebar.success("Deck importé !")

export_deck_config()
import_deck_config()

# -- UI Main minimal --
st.title("Simulateur Yu-Gi-Oh! (minimal)")
st.markdown(f"**Deck** : {st.session_state['deck_name']} &nbsp;&nbsp;|&nbsp;&nbsp; Taille : {st.session_state['deck_size']} &nbsp;&nbsp;|&nbsp;&nbsp; Main départ : {st.session_state['hand_size']} &nbsp;&nbsp;|&nbsp;&nbsp; {'First' if st.session_state['first_player'] else 'Second'} &nbsp;&nbsp;|&nbsp;&nbsp; Monte Carlo : {st.session_state['n_sim']} essais")

# ------------- Définition des rôles/types de cartes par défaut --------------
DEFAULT_CATS = [
    {"name": "Starter", "desc": "Carte qui lance le combo/stratégie principale.", "q": 12, "min": 1, "max": 3},
    {"name": "Extender", "desc": "Permet de continuer ou d’étendre le plan de jeu si interrompu.", "q": 9, "min": 0, "max": 3},
    {"name": "Board Breaker", "desc": "Permet de gérer les cartes adverses déjà sur le terrain.", "q": 8, "min": 0, "max": 3},
    {"name": "Handtrap", "desc": "Carte qui s’active depuis la main pendant le tour adverse.", "q": 8, "min": 0, "max": 3},
    {"name": "Tech Card", "desc": "Répond à un problème précis du méta ou d’un archétype.", "q": 3, "min": 0, "max": 2},
    {"name": "Brick", "desc": "Carte que tu ne veux surtout PAS piocher dans ta main de départ.", "q": 2, "min": 0, "max": 1},
]
DEFAULT_CATNAMES = "\n".join([cat["name"] for cat in DEFAULT_CATS])

if "cat_names" not in st.session_state:
    st.session_state['cat_names'] = DEFAULT_CATNAMES
if "cats" not in st.session_state:
    st.session_state['cats'] = DEFAULT_CATS

st.markdown("### Configuration des types de cartes")
cat_names = st.text_area(
    "Noms des catégories (une par ligne, ex : Starter, Extender, Board Breaker, Handtrap, Tech Card, Brick)",
    value=st.session_state['cat_names'],
    key="cat_names"
)
cat_names_list = [n.strip() for n in cat_names.split('\n') if n.strip()]

categories = []
for i, cat in enumerate(cat_names_list):
    col1, col2, col3 = st.columns([2, 2, 2])
    default_q = st.session_state['cats'][i]['q'] if i < len(st.session_state['cats']) else 0
    default_min = st.session_state['cats'][i]['min'] if i < len(st.session_state['cats']) else 0
    default_max = st.session_state['cats'][i]['max'] if i < len(st.session_state['cats']) else default_min
    desc = st.session_state['cats'][i]['desc'] if i < len(st.session_state['cats']) and 'desc' in st.session_state['cats'][i] else ""
    with col1:
        q = st.number_input(f"Nb de '{cat}'", 0, st.session_state['deck_size'], default_q, key=f"{cat}_q")
    with col2:
        mn = st.number_input(f"Min '{cat}' en main", 0, st.session_state['hand_size'], default_min, key=f"{cat}_mn")
    with col3:
        mx = st.number_input(f"Max '{cat}' en main", mn, min(st.session_state['hand_size'], 5), default_max, key=f"{cat}_mx") # max main = 5
    categories.append({'name': cat, 'q': q, 'min': mn, 'max': mx, "desc": desc})
    if desc:
        st.markdown(f'<span style="font-size:0.97em;color:#b3b3b3;opacity:0.68; margin-left:2px">{desc}</span>', unsafe_allow_html=True)

st.session_state['cats'] = categories

# ------------- FONCTIONS CALCUL & EXPLICATION -----------

def hypergeom_prob(deck_size, hand_size, categories):
    roles = [cat['name'] for cat in categories]
    counts = {r: 0 for r in roles}
    mins = {r: 0 for r in roles}
    maxs = {r: 0 for r in roles}
    for cat in categories:
        counts[cat['name']] += cat['q']
        mins[cat['name']] = cat['min']
        maxs[cat['name']] = cat['max']
    details = {}
    for r in roles:
        rv = hypergeom(deck_size, counts[r], hand_size)
        p = 0.0
        for k in range(mins[r], maxs[r]+1):
            p += rv.pmf(k)
        details[r] = p*100
    return details

def role_explanation(role, p, mn, mx):
    p = round(p, 2)
    if role.lower() == "starter":
        if mn == 0:
            if p > 70:
                return f"{p}% : Vous avez {p}% de chance de n’avoir aucun Starter (ou max 1). C’est **négatif** : il est important d’ouvrir avec un Starter pour lancer le jeu."
            else:
                return f"{p}% : Vous avez {p}% de chance de ne pas avoir de Starter, donc **positif** : dans la majorité des cas vous en aurez un."
        else:
            if p > 70:
                return f"{p}% : Vous avez {p}% de chance d’avoir au moins 1 Starter (entre {mn} et {mx}). C’est **positif** : ouvrir avec un Starter permet d’exécuter votre plan de jeu."
            else:
                return f"{p}% : Vous avez {p}% de chance d’avoir au moins 1 Starter (entre {mn} et {mx}). C’est **négatif** : vous manquerez souvent de Starter."
    elif role.lower() == "extender":
        if mn == 0 and mx == 1:
            if p > 70:
                return f"{p}% : {p}% de chance de n’avoir aucun ou 1 Extender. **Négatif** : tu risques de t’arrêter sur une interruption."
            else:
                return f"{p}% : {p}% de chance de ne pas voir d’Extender en main, donc **positif** : tu verras souvent un Extender."
        else:
            if p > 70:
                return f"{p}% : {p}% de chance d’avoir entre {mn} et {mx} Extender(s). **Positif** : les Extender aident à continuer le combo même si le plan principal s’arrête."
            else:
                return f"{p}% : {p}% de chance d’avoir entre {mn} et {mx} Extender(s). **Négatif** : tu risques de manquer de ressources pour continuer."
    elif role.lower() == "board breaker":
        if mn == 0 and mx == 0:
            return f"{p}% : {p}% de chance de n’avoir aucun Board Breaker en main. (Going first : impact limité, sauf exceptions.)"
        else:
            return f"{p}% : {p}% d’avoir entre {mn} et {mx} Board Breaker(s). (Surtout utile en second : pour casser le board adverse.)"
    elif role.lower() == "handtrap":
        if p > 70:
            return f"{p}% : {p}% de chance d’avoir entre {mn} et {mx} Handtrap(s). **Positif** : tu as des moyens de t’opposer au plan adverse."
        else:
            return f"{p}% : {p}% de chance d’avoir entre {mn} et {mx} Handtrap(s). **Négatif** : risque de subir le plan adverse."
    elif role.lower() == "tech card":
        if mn == 0 and mx == 0:
            return f"{p}% : {p}% de chance de ne pas voir de Tech Card (ou max 0). **Positif** : tu as peu de solutions méta en main de départ."
        else:
            return f"{p}% : {p}% de chance d’avoir entre {mn} et {mx} Tech Card(s)."
    elif role.lower() == "brick":
        if mx == 0 or (mn == 0 and mx == 1):
            if p > 70:
                return f"{p}% : {p}% de chance de n’avoir aucun Brick (ou max 1). **Positif** : tu limites le risque de main injouable."
            else:
                return f"{p}% : {p}% de chance de voir au moins un Brick. **Négatif** : risque d’avoir des cartes mortes en main."
        else:
            if p > 70:
                return f"{p}% : {p}% de chance de voir plusieurs Bricks. **Négatif** : risque élevé de main injouable."
            else:
                return f"{p}% : {p}% de chance de ne pas trop voir de Brick, donc **positif**."
    else:
        return f"{p}% : {p}% de chance d’avoir entre {mn} et {mx} {role}(s)."

def display_role_results(details, categories):
    color_map = {
        "starter": "#08e078",
        "extender": "#f44",
        "board breaker": "#11e1e1",
        "handtrap": "#08e078",
        "tech card": "#fc51fa",
        "brick": "#08e078"
    }
    for cat in categories:
        role = cat['name']
        color = color_map.get(role.lower(), "#fff")
        p = details.get(role, 0)
        mn, mx = cat['min'], cat['max']
        exp = role_explanation(role, p, mn, mx)
        st.markdown(
            f"""
            <div style="margin-bottom:8px;">
                <span style="font-weight:700; color:{color}; font-size:1.13em;">{role} : {p:.2f}%</span><br>
                <span style="color:#e5e5e5; font-size:1em;">{exp}</span>
                <hr style="border:0.5px solid {color}; opacity:0.45; margin:9px 0;">
            </div>
            """,
            unsafe_allow_html=True,
        )

# ------------- Animation, Calcul & Affichage Résultats -----------

calc = st.button("Calculer les probabilités !", use_container_width=True)

if calc:
    # Animation de 10s
    progress = st.empty()
    progress_text = st.empty()
    for percent in range(0, 101, 2):
        time.sleep(0.1)
        progress.progress(percent / 100)
        progress_text.write(f"Calcul en cours... ({percent}%)")
    progress.empty()
    progress_text.empty()
    st.success("Calcul terminé !")
    st.session_state["run_calc_done"] = True
else:
    st.session_state["run_calc_done"] = False

# Affichage résultats après calcul
if st.session_state.get("run_calc_done", False):
    st.header("Résultats")
    details = hypergeom_prob(
        st.session_state["deck_size"],
        st.session_state["hand_size"],
        categories,
    )
    display_role_results(details, categories)

    # Graphique matplotlib
    fig, ax = plt.subplots()
    roles = [cat["name"] for cat in categories]
    values = [details[cat["name"]] for cat in categories]
    colors = ["#08e078", "#f44", "#11e1e1", "#08e078", "#fc51fa", "#08e078"][:len(roles)]
    ax.barh(roles, values, color=colors)
    ax.set_xlabel('Probabilité (%)')
    ax.set_title("Probabilité d'obtenir chaque type de carte (Hypergéométrique)")
    st.pyplot(fig)
