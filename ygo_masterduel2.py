import streamlit as st
import numpy as np
from scipy.stats import hypergeom
import matplotlib.pyplot as plt
from fpdf import FPDF
import json

# --------- Paramètres Langue ---------
LANGS = {'Français': 'fr', 'English': 'en'}
lang_choice = st.sidebar.selectbox("Langue / Language", list(LANGS.keys()), index=0)
lang = LANGS[lang_choice]

# --------- Variables de Session ---------
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

# --------- UI Sidebar ---------
st.sidebar.markdown("### Paramètres du deck")
st.session_state["deck_name"] = st.sidebar.text_input("Nom du deck", st.session_state["deck_name"])
st.session_state["deck_size"] = st.sidebar.number_input("Taille du deck", 30, 60, st.session_state["deck_size"])

# Qui commence ?
who = st.sidebar.radio(
    "Qui commence ?",
    ["Moi (First)", "L'adversaire (Second)"],
    index=0 if st.session_state["first_player"] else 1,
    horizontal=True
)
st.session_state["first_player"] = (who == "Moi (First)")

# Ajuste main de départ à 6 si Second, 5 si First
if st.session_state["first_player"]:
    default_hand_size = 5
else:
    default_hand_size = 6

# Sauf si l'utilisateur a modifié la main
if "hand_size_user_set" not in st.session_state:
    st.session_state["hand_size"] = default_hand_size

hand_size = st.sidebar.number_input(
    "Taille de la main de départ",
    4, 7,
    st.session_state["hand_size"],
    key="hand_size"
)

if hand_size != default_hand_size:
    st.session_state["hand_size_user_set"] = True
else:
    st.session_state["hand_size_user_set"] = False

st.session_state["hand_size"] = hand_size

st.session_state["n_sim"] = st.sidebar.number_input(
    "Nombre de simulations Monte Carlo", 1000, 50000, st.session_state["n_sim"], step=1000
)

# --------- Types de cartes ---------
DEFAULT_CATS = [
    {"name": "Starter", "desc": "Carte qui lance le combo/stratégie principale.", "q": 12, "min": 1, "max": 3},
    {"name": "Extender", "desc": "Permet de continuer ou d’étendre le plan de jeu si interrompu.", "q": 9, "min": 0, "max": 3},
    {"name": "Board Breaker", "desc": "Permet de gérer les cartes adverses déjà sur le terrain.", "q": 8, "min": 0, "max": 3},
    {"name": "Handtrap", "desc": "Carte qui s’active depuis la main pendant le tour adverse.", "q": 8, "min": 0, "max": 3},
    {"name": "Tech Card", "desc": "Répond à un problème précis du méta ou d’un archétype.", "q": 3, "min": 0, "max": 2},
    {"name": "Brick", "desc": "Carte que tu ne veux surtout PAS piocher dans ta main de départ.", "q": 2, "min": 0, "max": 1},
]

if "cat_names" not in st.session_state:
    st.session_state['cat_names'] = "\n".join([cat["name"] for cat in DEFAULT_CATS])
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
        mx = st.number_input(f"Max '{cat}' en main", mn, min(st.session_state['hand_size'], 5), default_max, key=f"{cat}_mx")
    categories.append({'name': cat, 'q': q, 'min': mn, 'max': mx, "desc": desc})
    if desc:
        st.markdown(f'<span style="font-size:0.97em;color:#b3b3b3;opacity:0.68; margin-left:2px">{desc}</span>', unsafe_allow_html=True)

st.session_state['cats'] = categories

# --------- Fonctions de calcul ---------
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

def simulate(deck_size, hand_size, categories, n_sim=10000):
    deck = []
    for cat in categories:
        deck += [cat['name']]*cat['q']
    roles = [cat['name'] for cat in categories]
    mins = {cat['name']: cat['min'] for cat in categories}
    maxs = {cat['name']: cat['max'] for cat in categories}
    success = {r: 0 for r in roles}
    for _ in range(n_sim):
        if len(deck) < hand_size: break
        main = np.random.choice(deck, hand_size, replace=False)
        role_counts = {r: 0 for r in roles}
        for card in main:
            role_counts[card] += 1
        for r in roles:
            if mins[r] <= role_counts[r] <= maxs[r]:
                success[r] += 1
    results = {r: (success[r]/n_sim)*100 for r in roles}
    return results

def display_role_results(details, categories, title):
    color_map = {
        "starter": "#08e078",
        "extender": "#f44",
        "board breaker": "#11e1e1",
        "handtrap": "#08e078",
        "tech card": "#fc51fa",
        "brick": "#08e078"
    }
    st.markdown(f"**{title}**")
    for cat in categories:
        role = cat['name']
        color = color_map.get(role.lower(), "#fff")
        p = details.get(role, 0)
        mn, mx = cat['min'], cat['max']
        st.markdown(
            f"""
            <div style="margin-bottom:8px;">
                <span style="font-weight:700; color:{color}; font-size:1.13em;">{role} : {p:.2f}%</span><br>
                <span style="color:#e5e5e5; font-size:1em;">
                {p:.2f}% : Probabilité d’avoir entre {mn} et {mx} {role}(s) en main.
                </span>
                <hr style="border:0.5px solid {color}; opacity:0.45; margin:9px 0;">
            </div>
            """,
            unsafe_allow_html=True,
        )

# --------- BOUTON CALCUL & Animation ---------
import time
calc = st.button("Calculer les probabilités !", use_container_width=True)
if calc:
    progress = st.empty()
    progress_text = st.empty()
    for percent in range(0, 101, 2):
        time.sleep(0.1)
        progress.progress(percent / 100)
        progress_text.write(f"Calcul en cours... ({percent}%)")
    progress.empty()
    progress_text.empty()
    st.session_state["run_calc_done"] = True
else:
    st.session_state["run_calc_done"] = False

# --------- AFFICHAGE RESULTATS ---------
if st.session_state.get("run_calc_done", False):
    st.header("Résultats")

    # -- Résultat Monte Carlo
    mc_details = simulate(
        st.session_state["deck_size"],
        st.session_state["hand_size"],
        categories,
        int(st.session_state["n_sim"])
    )
    display_role_results(mc_details, categories, "Résultat Monte Carlo (simulé)")
    st.markdown("<br>", unsafe_allow_html=True)

    # -- Probabilité théorique
    theor_details = hypergeom_prob(
        st.session_state["deck_size"],
        st.session_state["hand_size"],
        categories
    )
    display_role_results(theor_details, categories, "Probabilité théorique (hypergéométrique)")
    st.markdown("<br>", unsafe_allow_html=True)

    # -- Statistiques visuelles
    st.subheader("Visualisation")
    fig, ax = plt.subplots()
    roles = [cat["name"] for cat in categories]
    values = [mc_details[cat["name"]] for cat in categories]
    colors = ["#08e078", "#f44", "#11e1e1", "#08e078", "#fc51fa", "#08e078"][:len(roles)]
    ax.barh(roles, values, color=colors)
    ax.set_xlabel('Probabilité Monte Carlo (%)')
    ax.set_title("Probabilité d'obtenir chaque type de carte")
    st.pyplot(fig)

# --------- EXPORT PDF (optionnel) ---------
def export_pdf(deck_name, deck_size, hand_size, n_sim, cats, mc_details, theor_details):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=13)
    pdf.cell(200, 10, f"Simulateur Yu-Gi-Oh! - Résultats", ln=True, align="C")
    pdf.set_font("Arial", size=11)
    pdf.cell(200, 10, f"Deck: {deck_name} - Taille: {deck_size} - Main: {hand_size} - Simu: {n_sim}", ln=True, align="L")
    pdf.ln(4)
    pdf.cell(200, 10, "---- Résultat Monte Carlo ----", ln=True, align="L")
    for cat in cats:
        pdf.cell(200, 10, f"{cat['name']}: {mc_details[cat['name']]:.2f}%", ln=True)
    pdf.ln(4)
    pdf.cell(200, 10, "---- Probabilité théorique ----", ln=True, align="L")
    for cat in cats:
        pdf.cell(200, 10, f"{cat['name']}: {theor_details[cat['name']]:.2f}%", ln=True)
    pdf.output("resultats_ygo.pdf")
    return "resultats_ygo.pdf"

if st.session_state.get("run_calc_done", False):
    if st.button("Exporter en PDF", type="secondary"):
        file_path = export_pdf(
            st.session_state["deck_name"],
            st.session_state["deck_size"],
            st.session_state["hand_size"],
            st.session_state["n_sim"],
            categories,
            mc_details,
            theor_details
        )
        with open(file_path, "rb") as f:
            st.download_button(
                label="Télécharger le PDF des résultats",
                data=f,
                file_name=file_path,
                mime="application/pdf"
            )
