import streamlit as st
import json
import time
from datetime import datetime
from fpdf import FPDF
import numpy as np
from scipy.stats import hypergeom

# --------- Config langue ---------
LANGS = {'Français': 'fr', 'English': 'en'}
lang_choice = st.sidebar.selectbox("Langue / Language", list(LANGS.keys()), index=0)
lang = LANGS[lang_choice]

# --------- Config Deck & UI ---------
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
st.session_state["deck_name"] = st.sidebar.text_input("Nom du deck", st.session_state["deck_name"])
st.session_state["deck_size"] = st.sidebar.number_input("Taille du deck", 30, 60, st.session_state["deck_size"])
st.session_state["hand_size"] = st.sidebar.number_input("Main de départ", 4, 7, st.session_state["hand_size"])
who = st.sidebar.radio("Qui commence ?", ["Moi (First)", "L'adversaire (Second)"],
    index=0 if st.session_state["first_player"] else 1, horizontal=True)
st.session_state["first_player"] = (who == "Moi (First)")
st.session_state["n_sim"] = st.sidebar.number_input("Nb simulations Monte Carlo", 1000, 50000, st.session_state["n_sim"], step=1000)

# --------- Reset bouton ---------
if st.sidebar.button("Réinitialiser la configuration"):
    for key in ["deck_name", "deck_size", "hand_size", "first_player", "n_sim", "cat_names", "cats"]:
        if key in st.session_state:
            del st.session_state[key]
    st.experimental_rerun()

# --------- Catégories de cartes ---------
DEFAULT_CATS = [
    {"name": "Starter", "desc": "Lance le plan de jeu.", "q": 12, "min": 1, "max": 3},
    {"name": "Extender", "desc": "Continue/combo après interruption.", "q": 9, "min": 0, "max": 3},
    {"name": "Board Breaker", "desc": "Gère le terrain adverse.", "q": 8, "min": 0, "max": 3},
    {"name": "Handtrap", "desc": "Interrompt l’adversaire depuis la main.", "q": 8, "min": 0, "max": 3},
    {"name": "Tech Card", "desc": "Réponse précise au méta.", "q": 3, "min": 0, "max": 2},
    {"name": "Brick", "desc": "Carte à éviter en main.", "q": 2, "min": 0, "max": 1},
]
DEFAULT_CATNAMES = "\n".join([cat["name"] for cat in DEFAULT_CATS])

if "cat_names" not in st.session_state:
    st.session_state['cat_names'] = DEFAULT_CATNAMES
if "cats" not in st.session_state:
    st.session_state['cats'] = DEFAULT_CATS

st.title("Simulateur Yu-Gi-Oh! | Statistiques d'ouverture")
st.markdown(f"""
**Deck** : `{st.session_state['deck_name']}` | **Taille** : {st.session_state['deck_size']} | **Main** : {st.session_state['hand_size']} | **{'First' if st.session_state['first_player'] else 'Second'}** | **Monte Carlo** : {st.session_state['n_sim']} essais
""")

st.markdown("### 📦 Configuration des types de cartes")
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

# --------- Calculs probabilités ----------
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

# --------- Générer explications dynamiques ----------
def role_explanation(role, p, mn, mx):
    p = round(p, 2)
    # Règles positives/négatives selon le min/max
    if role.lower() == "starter":
        if mn == 0:
            if p > 70:
                return f"{p}% : {p}% de chance de ne pas ouvrir de Starter (min={mn}). C’est **négatif** : il faut ouvrir avec un Starter."
            else:
                return f"{p}% : {p}% de chance d’ouvrir sans Starter. **Positif** : la plupart du temps, tu en as un."
        else:
            if p > 70:
                return f"{p}% : {p}% de chance d’avoir au moins 1 Starter. **Positif** : ouvrir avec un Starter permet d’exécuter ton plan."
            else:
                return f"{p}% : Seulement {p}% d’ouvrir avec Starter. **Négatif** : tu risques de manquer de jeu."
    elif role.lower() == "extender":
        if mn == 0 and mx == 1:
            if p > 70:
                return f"{p}% : Beaucoup de mains sans Extender. **Négatif** : tu risques de t’arrêter si interrompu."
            else:
                return f"{p}% : Rare de ne pas voir d’Extender. **Positif** : tu pourras continuer après interruption."
        else:
            if p > 70:
                return f"{p}% : Tu as {p}% d’avoir {mn} à {mx} Extenders en main. **Positif** : idéal pour maintenir la pression."
            else:
                return f"{p}% : Peu de chance d’avoir les Extenders nécessaires. **Négatif**."
    elif role.lower() == "board breaker":
        if mn == 0 and mx == 0:
            return f"{p}% : Aucune Board Breaker (min={mn}). (Going first ? Attendu.)"
        else:
            return f"{p}% : {p}% de chance d’avoir {mn} à {mx} Board Breakers. (Important en second pour casser le board adverse.)"
    elif role.lower() == "handtrap":
        if p > 70:
            return f"{p}% : {p}% de chance d’avoir {mn} à {mx} Handtraps. **Positif** : tu peux contrer l’adversaire."
        else:
            return f"{p}% : Faible chance d’avoir une Handtrap. **Négatif** : attention au plan adverse."
    elif role.lower() == "tech card":
        if mn == 0 and mx == 0:
            return f"{p}% : Tu ne verras pas de Tech Card au départ. (Logique, peu de place)."
        else:
            return f"{p}% : {p}% d’ouvrir avec une Tech Card. Pratique contre certains decks."
    elif role.lower() == "brick":
        if mx == 0 or (mn == 0 and mx == 1):
            if p > 70:
                return f"{p}% : Très peu de Bricks en main (min={mn}, max={mx}). **Positif**."
            else:
                return f"{p}% : Risque de voir un Brick. **Négatif**."
        else:
            if p > 70:
                return f"{p}% : Tu risques souvent de piocher des Bricks. **Négatif**."
            else:
                return f"{p}% : Rare de voir plusieurs Bricks. **Positif**."
    else:
        return f"{p}% : {p}% de chance d’avoir {mn} à {mx} {role}(s)."

def display_role_results(details, categories):
    for cat in categories:
        role = cat['name']
        p = details.get(role, 0)
        mn, mx = cat['min'], cat['max']
        exp = role_explanation(role, p, mn, mx)
        st.markdown(f"""
        <div style="margin-bottom:12px;">
            <span style="font-weight:700; color:#0fa; font-size:1.12em;">{role} : {p:.2f}%</span><br>
            <span style="color:#e5e5e5; font-size:1em;">{exp}</span>
            <hr style="border:0.5px solid #ccc; opacity:0.45; margin:9px 0;">
        </div>
        """, unsafe_allow_html=True)

# --------- Bouton calcul & animation ----------
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
    st.success("Calcul terminé !")
    st.session_state["run_calc_done"] = True
else:
    st.session_state["run_calc_done"] = False

# --------- Affichage résultats & PDF ----------
if st.session_state.get("run_calc_done", False):
    st.header("Résultats")
    details = hypergeom_prob(st.session_state["deck_size"], st.session_state["hand_size"], categories)
    display_role_results(details, categories)

    # ----- Export PDF -----
    def export_results_pdf(deck_name, deck_size, hand_size, results, categories):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", "B", 15)
        pdf.cell(0, 12, f"Résultats Master Duel - {deck_name}", ln=True, align="C")
        pdf.set_font("Arial", "", 11)
        pdf.cell(0, 8, f"Date : {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True)
        pdf.cell(0, 8, f"Taille du deck : {deck_size} | Main de départ : {hand_size}", ln=True)
        pdf.ln(2)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 8, "Probabilités par type :", ln=True)
        pdf.set_font("Arial", "", 11)
        for cat in categories:
            name = cat["name"]
            value = results[name]
            mn, mx = cat['min'], cat['max']
            pdf.cell(0, 8, f"{name} : {value:.2f}% (entre {mn} et {mx})", ln=True)
        pdf.ln(4)
        pdf.set_font("Arial", "I", 10)
        pdf.cell(0, 8, "Fait avec le Simulateur Master Duel - Abdellah SABIR", ln=True, align="C")
        return pdf.output(dest="S").encode("latin1")
    pdf_bytes = export_results_pdf(
        st.session_state["deck_name"],
        st.session_state["deck_size"],
        st.session_state["hand_size"],
        details,
        categories
    )
    st.download_button("Exporter en PDF", pdf_bytes, file_name="resultats_simulateur.pdf")

# ---- FOOTER ----
st.markdown("<br><hr><center style='color:gray;font-size:12px;'>Simulateur Yu-Gi-Oh! - par SABIR Abdellah - 2024</center>", unsafe_allow_html=True)
