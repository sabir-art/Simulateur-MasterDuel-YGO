# --------- IMPORTS & CONFIG ---------
import streamlit as st
import os
import json
import time
import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import hypergeom
from fpdf import FPDF
from unidecode import unidecode
import io
import pandas as pd
import requests

# Récupérer la clé API OpenAI depuis les variables d'environnement (Streamlit Cloud: "secrets")
api_key_env = os.getenv("OPENAI_API_KEY")

# Champ pour l'utilisateur dans la sidebar (champ masqué, pré-rempli si une clé existe déjà)
user_api_key = st.sidebar.text_input(
    "OpenAI API Key (optionnel, pour l'analyse IA)",
    type="password",
    value=api_key_env if api_key_env else ""
)

# La clé utilisée sera celle saisie par l'utilisateur, sinon celle des secrets/environnement
api_key = user_api_key if user_api_key else api_key_env

# --------- TRADUCTIONS ---------
TRS = {
    "fr": {
        "deck_name": "Nom du deck",
        "deck_size": "Taille du deck",
        "who_starts": "Qui commence ?",
        "first": "Moi (First)",
        "second": "L'adversaire (Second)",
        "hand_size": "Taille de la main de départ",
        "n_sim": "Nombre de simulations Monte Carlo",
        "main_title": "Simulateur de probabilités Yu-Gi-Oh! Master Duel",
        "subtitle": "Créez votre deck, simulez vos probabilités d'ouverture et exportez vos résultats en PDF.",
        "category_config": "Configuration des types de cartes",
        "cat_names": "Noms des catégories (une par ligne, ex : Starter, Extender, Board Breaker, Handtrap, Tech Card, Brick)",
        "calc": "Calculer les probabilités !",
        "res_table": "Tableau complet des résultats",
        "theor_global": "Probabilité théorique globale",
        "mc_global": "Probabilité Monte Carlo globale",
        "export_pdf": "Exporter en PDF",
        "export_title": "Export PDF des résultats",
        "role": "Rôle",
        "theorique": "Théorique (%)",
        "montecarlo": "Monte Carlo (%)",
        "explanation": "Explication",
        "params": "Paramètres du deck",
        "hand": "Main",
        "graph_theor": "Probabilité par rôle (Hypergéométrique)",
        "graph_mc": "Probabilité par rôle (Monte Carlo)",
        "donut_title": "Répartition des rôles dans le deck",
        "hist_title": "Histogramme de la taille de main pour chaque rôle",
    },
    "en": {
        "deck_name": "Deck name",
        "deck_size": "Deck size",
        "who_starts": "Who goes first?",
        "first": "Me (First)",
        "second": "Opponent (Second)",
        "hand_size": "Starting hand size",
        "n_sim": "Number of Monte Carlo simulations",
        "main_title": "Yu-Gi-Oh! Master Duel Probability Simulator",
        "subtitle": "Build your deck,  your opening odds, and export your results as a PDF.",
        "category_config": "Card types configuration",
        "cat_names": "Category names (one per line, e.g.: Starter, Extender, Board Breaker, Handtrap, Tech Card, Brick)",
        "calc": "Calculate probabilities!",
        "res_table": "Full result table",
        "theor_global": "Theoretical overall probability",
        "mc_global": "Monte Carlo overall probability",
        "export_pdf": "Export as PDF",
        "export_title": "Export PDF results",
        "role": "Role",
        "theorique": "Theoretical (%)",
        "montecarlo": "Monte Carlo (%)",
        "explanation": "Explanation",
        "params": "Deck settings",
        "hand": "Hand",
        "graph_theor": "Role probability (Hypergeometric)",
        "graph_mc": "Role probability (Monte Carlo)",
        "donut_title": "Role distribution in the deck",
        "hist_title": "Hand size histogram per role",
    }
}

# --------- GESTION LANGUE ---------
LANGS = {"Français": "fr", "English": "en"}
lang_choice = st.sidebar.selectbox("Langue / Language", list(LANGS.keys()), index=0)
lang = LANGS[lang_choice]
T = TRS[lang]

# --------- SESSION STATE INIT ---------
if "deck_name" not in st.session_state:
    st.session_state["deck_name"] = "Mon deck" if lang == "fr" else "My deck"
if "deck_size" not in st.session_state:
    st.session_state["deck_size"] = 40
if "first_player" not in st.session_state:
    st.session_state["first_player"] = True
if "hand_size" not in st.session_state:
    st.session_state["hand_size"] = 5
if "hand_size_user_set" not in st.session_state:
    st.session_state["hand_size_user_set"] = False
if "n_sim" not in st.session_state:
    st.session_state["n_sim"] = 10000

# --------- UI SIDEBAR ---------
st.sidebar.markdown(f"### {T['params']}")
st.session_state["deck_name"] = st.sidebar.text_input(
    T["deck_name"], st.session_state["deck_name"]
)
st.session_state["deck_size"] = st.sidebar.number_input(
    T["deck_size"], 30, 60, st.session_state["deck_size"]
)
who = st.sidebar.radio(
    T["who_starts"],
    [T["first"], T["second"]],
    index=0 if st.session_state["first_player"] else 1,
    horizontal=True
)
st.session_state["first_player"] = (who == T["first"])
default_hand_size = 5 if st.session_state["first_player"] else 6
main_value = st.session_state["hand_size"] if st.session_state["hand_size_user_set"] else default_hand_size
hand_size = st.sidebar.number_input(
    T["hand_size"], 4, 7, main_value, key="hand_size"
)
if st.session_state["hand_size"] != default_hand_size:
    st.session_state["hand_size_user_set"] = True
else:
    st.session_state["hand_size_user_set"] = False
st.session_state["n_sim"] = st.sidebar.number_input(
    T["n_sim"], 1000, 100000, st.session_state["n_sim"], step=1000
)
# --------- TITRE PRINCIPAL & CONFIGURATION DES CATEGORIES ---------
st.title(T["main_title"])
st.caption(T["subtitle"])

# --- Résumé paramètres deck (barre d'info) ---
def deck_summary(deck_name, deck_size, hand_size, first_player, n_sim, lang):
    if lang == "fr":
        who = "First" if first_player else "Second"
        return (
            f"<b>Deck:</b> <code style='color:#22d47a'>{deck_name}</code>"
            f" <b>| Taille:</b> {deck_size}"
            f" <b>| Main:</b> {hand_size}"
            f" <b>| First:</b> {who}"
            f" <b>| <span style='color:#fff18d'>Monte Carlo</span> :</b> {n_sim} essais"
        )
    else:
        who = "First" if first_player else "Second"
        return (
            f"<b>Deck:</b> <code style='color:#22d47a'>{deck_name}</code>"
            f" <b>| Size:</b> {deck_size}"
            f" <b>| Hand:</b> {hand_size}"
            f" <b>| First:</b> {who}"
            f" <b>| <span style='color:#fff18d'>Monte Carlo</span> :</b> {n_sim} runs"
        )

st.markdown(deck_summary(
    st.session_state["deck_name"],
    st.session_state["deck_size"],
    st.session_state["hand_size"],
    st.session_state["first_player"],
    st.session_state["n_sim"],
    lang
), unsafe_allow_html=True)

# ----------- DÉFINITION DES RÔLES PAR DÉFAUT (MULTILINGUE) -----------
DEFAULT_CATS = [
    {
        "name": "Starter",
        "desc": {
            "fr": "Carte qui lance le combo/stratégie principale.",
            "en": "Card that starts your main combo/strategy."
        },
        "q": 12, "min": 1, "max": 3
    },
    {
        "name": "Extender",
        "desc": {
            "fr": "Permet de continuer ou d’étendre ton jeu après le début du combo.",
            "en": "Lets you continue or extend your play after your main combo."
        },
        "q": 9, "min": 0, "max": 3
    },
    {
        "name": "Board Breaker",
        "desc": {
            "fr": "Permet de gérer les cartes adverses déjà sur le terrain.",
            "en": "Helps deal with opponent's established board."
        },
        "q": 8, "min": 0, "max": 3
    },
    {
        "name": "Handtrap",
        "desc": {
            "fr": "Carte qui s’active depuis la main pendant le tour adverse.",
            "en": "Card you can activate from hand during opponent's turn."
        },
        "q": 8, "min": 0, "max": 3
    },
    {
        "name": "Tech Card",
        "desc": {
            "fr": "Répond à un problème précis du méta ou d’un archétype.",
            "en": "Answers a specific metagame or archetype threat."
        },
        "q": 3, "min": 0, "max": 2
    },
    {
        "name": "Brick",
        "desc": {
            "fr": "Carte que tu ne veux surtout PAS piocher dans ta main de départ.",
            "en": "Card you definitely do NOT want to draw in your starting hand."
        },
        "q": 2, "min": 0, "max": 1
    },
]
DEFAULT_CATNAMES = "\n".join([cat["name"] for cat in DEFAULT_CATS])

if "cat_names" not in st.session_state:
    st.session_state['cat_names'] = DEFAULT_CATNAMES
if "cats" not in st.session_state:
    st.session_state['cats'] = DEFAULT_CATS

st.markdown("### Configuration des types de cartes" if lang == "fr" else "### Card Type Configuration")

cat_names = st.text_area(
    "Noms des catégories (une par ligne, ex : Starter, Extender, Board Breaker, Handtrap, Tech Card, Brick)" if lang == "fr" else
    "Category names (one per line, ex: Starter, Extender, Board Breaker, Handtrap, Tech Card, Brick)",
    value=st.session_state['cat_names'],
    key="cat_names"
)
cat_names_list = [n.strip() for n in cat_names.split('\n') if n.strip()]

categories = []
for i, cat in enumerate(cat_names_list):
    col1, col2, col3 = st.columns([2, 2, 2])
    # Toujours récupérer le dico desc original si dispo
    default_q = st.session_state['cats'][i]['q'] if i < len(st.session_state['cats']) else 0
    default_min = st.session_state['cats'][i]['min'] if i < len(st.session_state['cats']) else 0
    default_max = st.session_state['cats'][i]['max'] if i < len(st.session_state['cats']) else default_min
    default_desc_dict = None
    if i < len(st.session_state['cats']) and isinstance(st.session_state['cats'][i].get('desc', None), dict):
        default_desc_dict = st.session_state['cats'][i]['desc']
    else:
        # fallback
        default_desc_dict = {"fr": "", "en": ""}
    desc = default_desc_dict.get(lang, "")

    with col1:
        q = st.number_input(
            f"Nb de '{cat}'" if lang == "fr" else f"Number of '{cat}'",
            0, st.session_state['deck_size'], default_q, key=f"{cat}_q")
    with col2:
        mn = st.number_input(
            f"Min '{cat}' en main" if lang == "fr" else f"Min '{cat}' in hand",
            0, st.session_state['hand_size'], default_min, key=f"{cat}_mn")
    with col3:
        mx = st.number_input(
            f"Max '{cat}' en main" if lang == "fr" else f"Max '{cat}' in hand",
            mn, min(st.session_state['hand_size'], 5), default_max, key=f"{cat}_mx")
    categories.append({'name': cat, 'q': q, 'min': mn, 'max': mx, "desc": default_desc_dict})
    if desc:
        st.markdown(
            f'<span style="font-size:0.97em;color:#b3b3b3;opacity:0.68; margin-left:2px">{desc}</span>',
            unsafe_allow_html=True
        )

st.session_state['cats'] = categories

# --- Calcule la probabilité exacte (hypergéométrique) pour chaque type ---

def hypergeom_prob(deck_size, hand_size, categories):
    """
    Pour chaque type (catégorie), calcule la probabilité d'en avoir entre min et max dans la main de départ.
    Utilise la loi hypergéométrique (tirage sans remise).
    Retourne un dict : {role: proba_en_%}
    """
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

# --- Simule n_sim mains aléatoires, compte les succès pour chaque type ---
def simulate(deck_size, hand_size, categories, n_sim=10000):
    """
    Pour chaque simulation, pioche une main, compte pour chaque type si min <= nb <= max.
    Retourne un dict : {role: pourcentage de réussite}
    """
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

# ----------- DICTIONNAIRE EXPLICATIONS PAR TYPE/ROLE ET CAS (multilingue) -----------
ROLE_EXPLAIN = {
    "starter": {
        (0, 0): {
            "fr": "Votre main n'aura aucun Starter : attention au risque de ne pas jouer !",
            "en": "Your hand will never open a Starter: you risk not being able to play!"
        },
        (1, 1): {
            "fr": "Au moins 1 Starter garanti : deck stable et fiable.",
            "en": "At least 1 Starter guaranteed: stable, reliable deck."
        },
        (1, 3): {
            "fr": "Vous ouvrez quasi toujours un Starter, plusieurs options en main.",
            "en": "You almost always open a Starter, with multiple options."
        },
        "default_pos": {
            "fr": "Bonne probabilité d'ouvrir un Starter. Main jouable dans la majorité des cas.",
            "en": "Good odds to open a Starter. Playable hand in most cases."
        },
        "default_neg": {
            "fr": "Faible chance de voir un Starter : deck instable, attention aux mauvaises mains.",
            "en": "Low chance to open a Starter: unstable deck, beware of bad hands."
        }
    },
    "extender": {
        (0, 0): {
            "fr": "Aucun Extender dans la main : peu de rebond en cas d'interruption.",
            "en": "No Extender in hand: low resilience if your play is stopped."
        },
        (1, 1): {
            "fr": "Vous avez toujours 1 Extender en main : bon potentiel de rebond.",
            "en": "Always 1 Extender in hand: good follow-up potential."
        },
        (1, 3): {
            "fr": "Vos mains permettent de continuer le combo souvent.",
            "en": "You can extend your combo in most hands."
        },
        "default_pos": {
            "fr": "Bonne chance d'ouvrir un Extender, sécurité en cas de stop.",
            "en": "Good odds for an Extender, safe if interrupted."
        },
        "default_neg": {
            "fr": "Peu de chance d’avoir un Extender. Attention à la gestion du grind.",
            "en": "Low odds for an Extender. Watch out for grind games."
        }
    },
    "board breaker": {
        (0, 0): {
            "fr": "Aucun Board Breaker dans la main : difficile de gérer un board adverse solide.",
            "en": "No Board Breaker: hard to deal with strong opposing boards."
        },
        (1, 1): {
            "fr": "Toujours un Board Breaker en main : bon contre les boards adverses.",
            "en": "Always a Board Breaker: good against strong boards."
        },
        "default_pos": {
            "fr": "Vous ouvrez souvent Board Breaker, utile vs gros boards.",
            "en": "You often open a Board Breaker, useful against big boards."
        },
        "default_neg": {
            "fr": "Rare d’avoir un Board Breaker. Méfiance contre les decks puissants.",
            "en": "Rarely have a Board Breaker. Watch out for strong decks."
        }
    },
    "handtrap": {
        (0, 0): {
            "fr": "Aucune Handtrap : risque de laisser l’adversaire dérouler.",
            "en": "No Handtrap: risk letting the opponent play freely."
        },
        (1, 3): {
            "fr": "Souvent au moins 1 Handtrap : pression sur l’adversaire.",
            "en": "Often at least 1 Handtrap: puts pressure on your opponent."
        },
        "default_pos": {
            "fr": "Bonne fréquence de Handtrap. Défense solide contre les combos.",
            "en": "Good Handtrap frequency. Strong defense against combos."
        },
        "default_neg": {
            "fr": "Pas assez de Handtrap. Fragile contre les decks rapides.",
            "en": "Not enough Handtraps. Weak against fast decks."
        }
    },
    "tech card": {
        (0, 0): {
            "fr": "Aucune Tech Card en main. Deck très 'pur', peu d’adaptation.",
            "en": "No Tech Cards in hand. Pure deck, little adaptation."
        },
        (1, 2): {
            "fr": "Parfois des Tech Cards pour surprendre l’adversaire.",
            "en": "Sometimes Tech Cards to surprise the opponent."
        },
        "default_pos": {
            "fr": "Bonne flexibilité avec vos Tech Cards.",
            "en": "Good flexibility with your Tech Cards."
        },
        "default_neg": {
            "fr": "Peu/pas de Tech Cards. Peu de solutions aux problèmes de méta.",
            "en": "Few/no Tech Cards. Fewer meta answers."
        }
    },
    "brick": {
        (0, 0): {
            "fr": "Aucune Brick en main, deck très stable !",
            "en": "No Brick in hand, very stable deck!"
        },
        (1, 1): {
            "fr": "Toujours une Brick : attention, risque de main morte fréquent.",
            "en": "Always a Brick: risky, dead hands likely."
        },
        "default_pos": {
            "fr": "Très peu de Bricks en main, stabilité maximale.",
            "en": "Very few Bricks drawn, highly stable."
        },
        "default_neg": {
            "fr": "Vous piochez des Bricks trop souvent, main injouable fréquente.",
            "en": "You draw Bricks too often, many unplayable hands."
        }
    }
}

# --- Génère une explication adaptée à la proba, min/max pour chaque type ---
def role_explanation(role, p, mn, mx, lang):
    """
    Retourne une phrase adaptée au résultat selon les seuils typiques (positif/négatif/min/max)
    """
    key = role.lower()
    table = ROLE_EXPLAIN.get(key, {})
    if (mn, mx) in table:
        return f"{p:.2f}% : {table[(mn, mx)][lang]}"
    # Générique positif/négatif si aucun cas spécifique
    if p > 70:
        return f"{p:.2f}% : {table.get('default_pos', {}).get(lang, '')}"
    else:
        return f"{p:.2f}% : {table.get('default_neg', {}).get(lang, '')}"
    
# --- IA advice ---

def get_ia_advice(api_key, resume_stats, lang="fr"):
    if not api_key:
        return "Aucune clé API fournie. L'analyse IA n'est pas disponible."
    prompt_fr = f"""Tu es un expert Yu-Gi-Oh! et deckbuilder. Voici les probabilités d'ouverture d'un deck :
{resume_stats}
Donne une analyse concise (max 5 lignes) sur la stabilité du deck, les points forts/faibles, et donne un conseil d'amélioration."""
    prompt_en = f"""You are a Yu-Gi-Oh! expert and deckbuilder. Here are opening hand odds for a deck:
{resume_stats}
Give a concise analysis (max 5 lines) about deck stability, strengths/weaknesses, and give a tip for improvement."""
    prompt = prompt_fr if lang == "fr" else prompt_en
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    body = {
        "model": "gpt-3.5-turbo",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 350,
        "temperature": 0.7
    }
    try:
        res = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=body, timeout=18)
        res.raise_for_status()
        data = res.json()
        return data['choices'][0]['message']['content'].strip()
    except Exception as e:
        return f"Erreur IA: {e}" if lang == "fr" else f"AI Error: {e}"
def remove_accents(txt):
    try:
        return unidecode(str(txt))
    except Exception:
        return str(txt)
    
# ------------- Export results PDF --------------

def export_results_pdf(deck_name, deck_size, hand_size, first_player, n_sim, theor_global, monte_global, theor_vals, monte_vals, explanations, img_bytes, img2_bytes):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 12, remove_accents(f"{T['main_title']}"), ln=1, align="C")
    pdf.set_font("Arial", "", 11)
    pdf.ln(2)
    pdf.cell(0, 8, remove_accents(f"{T['deck_name']}: {deck_name}"), ln=1)
    pdf.cell(0, 8, remove_accents(f"{T['deck_size']}: {deck_size}"), ln=1)
    pdf.cell(0, 8, remove_accents(f"{T['hand_size']}: {hand_size}"), ln=1)
    pdf.cell(0, 8, remove_accents(f"{T['who_starts']}: {T['first'] if first_player else T['second']}"), ln=1)
    pdf.cell(0, 8, remove_accents(f"{T['n_sim']}: {n_sim}"), ln=1)
    pdf.cell(0, 8, remove_accents(f"{T['theor_global']}: {theor_global:.2f}%"), ln=1)
    pdf.cell(0, 8, remove_accents(f"{T['mc_global']}: {monte_global:.2f}%"), ln=1)
    pdf.ln(5)
    # --- Tableau résultats ---
    pdf.set_font("Arial", "B", 12)
    pdf.set_fill_color(230, 230, 230)
    width_role = 38
    width_theorique = 22
    width_montecarlo = 25
    width_explanation = 100
    pdf.cell(width_role, 8, remove_accents(T["role"]), 1, 0, "C", 1)
    pdf.cell(width_theorique, 8, remove_accents(T["theorique"]), 1, 0, "C", 1)
    pdf.cell(width_montecarlo, 8, remove_accents(T["montecarlo"]), 1, 0, "C", 1)
    pdf.cell(width_explanation, 8, remove_accents(T["explanation"]), 1, 1, "C", 1)
    pdf.set_font("Arial", "", 10)
    for i, role in enumerate([cat["name"] for cat in categories]):
        expl = remove_accents(str(explanations[i]))
        x = pdf.get_x()
        y = pdf.get_y()
        pdf.multi_cell(width_role, 8, remove_accents(role), border=1, align="C")
        pdf.set_xy(x + width_role, y)
        pdf.multi_cell(width_theorique, 8, f"{theor_vals[i]:.2f}", border=1, align="C")
        pdf.set_xy(x + width_role + width_theorique, y)
        pdf.multi_cell(width_montecarlo, 8, f"{monte_vals[i]:.2f}", border=1, align="C")
        pdf.set_xy(x + width_role + width_theorique + width_montecarlo, y)
        pdf.multi_cell(width_explanation, 8, expl, border=1)
        pdf.set_xy(x, y + max(pdf.get_string_width(role) / width_role, 1) * 8)
    pdf.ln(4)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 8, remove_accents(T["graph_theor"]), ln=1)
    if img_bytes is not None:
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
            tmp.write(img_bytes.getbuffer())
            tmp.flush()
            pdf.image(tmp.name, x=20, w=170)
    pdf.ln(4)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 8, remove_accents(T["donut_title"]), ln=1)
    if img2_bytes is not None:
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
            tmp.write(img2_bytes.getbuffer())
            tmp.flush()
            pdf.image(tmp.name, x=45, w=110)
    pdf.ln(3)
    pdf.set_font("Arial", "I", 9)
    pdf.cell(0, 10, "Simulateur Yu-Gi-Oh! - par SABIR Abdellah - 2025", 0, 1, "C")
    return pdf.output(dest="S").encode("latin1")

# ------------- CALCUL & GÉNÉRATION DES RÉSULTATS --------------

calc = st.button(T["calc"], use_container_width=True)
if calc:
    progress = st.empty()
    progress_text = st.empty()
    for percent in range(0, 101, 2):
        time.sleep(0.1)
        progress.progress(percent / 100)
        progress_text.write(f"Calcul en cours... ({percent}%)" if lang == "fr" else f"Calculation in progress... ({percent}%)")
    progress.empty()
    progress_text.empty()
    st.success("Calcul terminé !" if lang == "fr" else "Calculation done!")
    st.session_state["run_calc_done"] = True
else:
    st.session_state["run_calc_done"] = False

if st.session_state.get("run_calc_done", False):
    # 1. Calculs probabilistes
    details = hypergeom_prob(
        st.session_state["deck_size"],
        st.session_state["hand_size"],
        categories,
    )
    theor_global = 1.0
    for v in details.values():
        theor_global *= v / 100 if v > 0 else 1
    theor_global = theor_global * 100

    sim_results = simulate(
        st.session_state["deck_size"],
        st.session_state["hand_size"],
        categories,
        st.session_state["n_sim"]
    )
    monte_global = 1.0
    for v in sim_results.values():
        monte_global *= v / 100 if v > 0 else 1
    monte_global = monte_global * 100

    # 2. Explications
    explanations = []
    for cat in categories:
        role = cat['name']
        p = details.get(role, 0)
        mn, mx = cat['min'], cat['max']
        exp = role_explanation(role, p, mn, mx, lang)
        explanations.append(exp)

    # 3. Table pour Streamlit
    table = []
    for i, cat in enumerate(categories):
        r = cat["name"]
        table.append({
            T["role"]: r,
            T["theorique"]: round(details[r], 2),
            T["montecarlo"]: round(sim_results[r], 2),
            T["explanation"]: explanations[i]
        })
    df = pd.DataFrame(table)
    st.markdown(f"### {T['res_table']}")
    st.dataframe(df, hide_index=True, use_container_width=True)

    st.markdown(f"**{T['theor_global']}** : {theor_global:.2f}%")
    st.markdown(f"**{T['mc_global']}** : {monte_global:.2f}%")

    # 4. Graphiques matplotlib
    fig, ax = plt.subplots(figsize=(6, 4.5))
    roles = [cat["name"] for cat in categories]
    values = [details[cat["name"]] for cat in categories]
    colors = ["#08e078", "#f44", "#11e1e1", "#ffc300", "#fc51fa", "#ff5757"][:len(roles)]
    ax.barh(roles, values, color=colors)
    ax.set_xlabel('Probabilité (%)' if lang == "fr" else "Probability (%)")
    ax.set_title(T["graph_theor"])
    st.pyplot(fig, use_container_width=True)

    fig2, ax2 = plt.subplots(figsize=(4, 4))
    sizes = [cat["q"] for cat in categories]
    ax2.pie(sizes, labels=roles, autopct="%1.0f%%", startangle=90)
    ax2.set_title(T["donut_title"])
    st.pyplot(fig2, use_container_width=True)

    # 5. Buffers images pour PDF
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    buf.seek(0)
    buf2 = io.BytesIO()
    fig2.savefig(buf2, format="png")
    buf2.seek(0)

    # 6. Analyse IA (optionnelle)
    stats_txt = ""
    for cat in categories:
        role = cat["name"]
        theor = details[role]
        monte = sim_results[role]
        if lang == "fr":
            stats_txt += f"{role}: Théorique {theor:.2f}% / Monte Carlo {monte:.2f}%\n"
        else:
            stats_txt += f"{role}: Theoretical {theor:.2f}% / Monte Carlo {monte:.2f}%\n"
    stats_txt += f"{T['theor_global']}: {theor_global:.2f}%\n"
    stats_txt += f"{T['mc_global']}: {monte_global:.2f}%\n"

    if api_key:
        st.markdown("### 🤖 Analyse IA du deck")
        with st.spinner("Analyse en cours…"):
            conseil = get_ia_advice(api_key, stats_txt, lang)
            st.info(conseil)
    else:
        st.markdown("*(Entrer une clé OpenAI dans la sidebar pour générer une analyse IA personnalisée)*")

    # 7. Export PDF (bouton)
    theor_vals = [details[cat["name"]] for cat in categories]
    monte_vals = [sim_results[cat["name"]] for cat in categories]
    st.download_button(
        T["export_pdf"],
        data=export_results_pdf(
            st.session_state["deck_name"],
            st.session_state["deck_size"],
            st.session_state["hand_size"],
            st.session_state["first_player"],
            st.session_state["n_sim"],
            theor_global,
            monte_global,
            theor_vals,
            monte_vals,
            explanations,
            buf,
            buf2,
        ),
        file_name="simulation_ygo.pdf"
    )
