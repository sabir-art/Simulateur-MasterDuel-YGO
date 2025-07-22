import streamlit as st
import json
import time
import numpy as np
from fpdf import FPDF
import matplotlib.pyplot as plt
from scipy.stats import hypergeom

# --------- GESTION DE LA LANGUE ---------
LANGS = {
    'Français': 'fr',
    'English': 'en',
}
lang_choice = st.sidebar.selectbox("Langue / Language", list(LANGS.keys()), index=0)
lang = LANGS[lang_choice]

# --------- SESSION STATE INIT ---------
def reset_all():
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    st.experimental_rerun()

if st.sidebar.button("🔄 Réinitialiser l'application"):
    reset_all()

if "deck_name" not in st.session_state:
    st.session_state["deck_name"] = "Mon deck"
if "deck_size" not in st.session_state:
    st.session_state["deck_size"] = 40
if "first_player" not in st.session_state:
    st.session_state["first_player"] = True  # Moi (First)
if "hand_size" not in st.session_state:
    st.session_state["hand_size"] = 5
if "hand_size_user_set" not in st.session_state:
    st.session_state["hand_size_user_set"] = False
if "n_sim" not in st.session_state:
    st.session_state["n_sim"] = 10000

# --------- UI SIDEBAR ---------
st.sidebar.markdown("### Paramètres du deck")

# Nom deck
st.session_state["deck_name"] = st.sidebar.text_input(
    "Nom du deck", st.session_state["deck_name"]
)
# Taille deck
st.session_state["deck_size"] = st.sidebar.number_input(
    "Taille du deck", 30, 60, st.session_state["deck_size"]
)

# Qui commence ? First/Second
who = st.sidebar.radio(
    "Qui commence ?",
    ["Moi (First)", "L'adversaire (Second)"],
    index=0 if st.session_state["first_player"] else 1,
    horizontal=True
)
st.session_state["first_player"] = (who == "Moi (First)")

# Main par défaut selon First/Second
default_hand_size = 5 if st.session_state["first_player"] else 6
main_value = st.session_state["hand_size"] if st.session_state["hand_size_user_set"] else default_hand_size

hand_size = st.sidebar.number_input(
    "Taille de la main de départ", 4, 7, main_value, key="hand_size"
)
# Garde mémoire si utilisateur modifie la main
if st.session_state["hand_size"] != default_hand_size:
    st.session_state["hand_size_user_set"] = True
else:
    st.session_state["hand_size_user_set"] = False

# Nombre de simulations Monte Carlo
st.session_state["n_sim"] = st.sidebar.number_input(
    "Nombre de simulations Monte Carlo", 1000, 100000, st.session_state["n_sim"], step=1000
)

# --------- EXPORT PDF ---------
# ----------- EXPORT PDF UTILITAIRE -----------
from fpdf import FPDF

def export_results_pdf(deck_name, deck_size, hand_size, first_player, n_sim, theor_global, monte_global, theor_details, monte_details, result_text, img_bytes):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 12, f"Simulation Probabilités Yu-Gi-Oh!", ln=1, align="C")
    pdf.set_font("Arial", "", 12)
    pdf.cell(0, 9, f"Deck : {deck_name}", ln=1)
    pdf.cell(0, 8, f"Taille du deck : {deck_size}", ln=1)
    pdf.cell(0, 8, f"Main de départ : {hand_size}", ln=1)
    pdf.cell(0, 8, f"{'First' if first_player else 'Second'}", ln=1)
    pdf.cell(0, 8, f"Simulations Monte Carlo : {n_sim}", ln=1)
    pdf.ln(4)
    pdf.set_font("Arial", "B", 13)
    pdf.cell(0, 8, f"Probabilité théorique générale : {theor_global:.2f}%", ln=1)
    pdf.cell(0, 8, f"Probabilité Monte Carlo générale : {monte_global:.2f}%", ln=1)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 8, "Détails par rôle (théorique):", ln=1)
    pdf.set_font("Arial", "", 11)
    for t in theor_details:
        pdf.multi_cell(0, 6, t)
    pdf.ln(3)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 8, "Détails par rôle (Monte Carlo):", ln=1)
    pdf.set_font("Arial", "", 11)
    for t in monte_details:
        pdf.multi_cell(0, 6, t)
    pdf.ln(3)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 8, "Résumé complet :", ln=1)
    pdf.set_font("Arial", "", 10)
    pdf.multi_cell(0, 6, result_text)
    pdf.ln(4)
    # Image
    if img_bytes is not None:
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
            tmp.write(img_bytes.getbuffer())
            tmp.flush()
            pdf.image(tmp.name, x=20, w=170)
    return pdf.output(dest="S").encode("latin1")

# --------- TITRE PRINCIPAL ---------
st.title("Simulateur de probabilités Yu-Gi-Oh! Master Duel")
st.caption("Créez votre deck, simulez vos probabilités d'ouverture et exportez vos résultats en PDF.")

# ------ SUITE : (PARTIE 2) ------
# ----------- DÉFINITION DES RÔLES PAR DÉFAUT -----------
DEFAULT_CATS = [
    {"name": "Starter", "desc": "Carte qui lance le combo/stratégie principale.", "q": 12, "min": 1, "max": 3},
    {"name": "Extender", "desc": "Permet de continuer ou d’étendre ton jeu après le début du combo.", "q": 9, "min": 0, "max": 3},
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
        mx = st.number_input(f"Max '{cat}' en main", mn, min(st.session_state['hand_size'], 5), default_max, key=f"{cat}_mx")  # max en main à 5
    categories.append({'name': cat, 'q': q, 'min': mn, 'max': mx, "desc": desc})
    if desc:
        st.markdown(f'<span style="font-size:0.97em;color:#b3b3b3;opacity:0.68; margin-left:2px">{desc}</span>', unsafe_allow_html=True)

st.session_state['cats'] = categories

# ----------- FONCTIONS DE CALCUL -----------
def hypergeom_prob(deck_size, hand_size, categories):
    """
    Calcule la probabilité hypergéométrique pour chaque type
    Retourne : dict(role: probabilité %)
    """
    from scipy.stats import hypergeom
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
    """
    Simule n_sim mains de départ pour donner des statistiques réelles par type
    """
    import numpy as np
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

# ----------- PHRASES INTELLIGENTES PAR RÔLE & RANGE -----------
def role_explanation(role, p, mn, mx):
    """
    Génère une explication intelligente pour chaque type/role, selon min/max choisi.
    """
    p = round(p, 2)
    role_low = role.lower()
    if role_low == "starter":
        if mn == 0 and mx <= 1:
            if p > 70:
                return f"{p}% : Vous avez {p}% de chance de ne PAS ouvrir Starter. Négatif : vous risquez souvent de ne pas jouer !"
            else:
                return f"{p}% : {p}% de chance de ne pas ouvrir Starter. Positif : la majorité du temps, vous en aurez un."
        else:
            if p > 70:
                return f"{p}% : {p}% de chance d’ouvrir au moins 1 Starter (entre {mn} et {mx}). Positif : votre deck est stable."
            else:
                return f"{p}% : Seulement {p}% de chance d’ouvrir Starter. Négatif, vous risquez de manquer de plan de jeu."
    elif role_low == "extender":
        if mn == 0 and mx == 1:
            if p > 70:
                return f"{p}% : {p}% de chance d’ouvrir 0 ou 1 Extender. Négatif : peu de rebond si le plan est stoppé."
            else:
                return f"{p}% : {p}% de chance d’avoir au moins un Extender. Positif, vous pouvez continuer le combo."
        else:
            if p > 70:
                return f"{p}% : {p}% de chance d’avoir entre {mn} et {mx} Extender(s). Positif, rebond possible."
            else:
                return f"{p}% : Faible probabilité de voir des Extender. Attention au manque de ressources."
    elif role_low == "board breaker":
        if mn == 0 and mx == 0:
            return f"{p}% : {p}% de chance d’ouvrir SANS Board Breaker (souvent normal si vous jouez First)."
        else:
            return f"{p}% : {p}% de chance d’ouvrir avec {mn} à {mx} Board Breaker(s). Utile pour casser le terrain adverse."
    elif role_low == "handtrap":
        if p > 70:
            return f"{p}% : {p}% de chance d’avoir entre {mn} et {mx} Handtrap(s). Positif, vous pourrez ralentir l’adversaire."
        else:
            return f"{p}% : Seulement {p}% de chance d’avoir une Handtrap. Risqué si le meta en demande beaucoup."
    elif role_low == "tech card":
        if mn == 0 and mx == 0:
            return f"{p}% : {p}% de chance d’ouvrir SANS Tech Card. Pas grave si votre deck n’en dépend pas."
        else:
            return f"{p}% : {p}% de chance d’ouvrir avec {mn} à {mx} Tech Card(s)."
    elif role_low == "brick":
        if mx == 0 or (mn == 0 and mx == 1):
            if p > 70:
                return f"{p}% : {p}% de chance de ne PAS voir de Brick. Positif, votre deck est fiable."
            else:
                return f"{p}% : {p}% de chance de voir une Brick. Négatif, vous risquez de bricker."
        else:
            if p > 70:
                return f"{p}% : {p}% de chance de voir plusieurs Bricks. Négatif : risque de main injouable."
            else:
                return f"{p}% : {p}% de chance de ne pas trop voir de Brick. Plutôt positif."
    else:
        return f"{p}% : {p}% de chance d’avoir entre {mn} et {mx} {role}(s)."

def display_role_results(details, categories):
    color_map = {
        "starter": "#08e078",
        "extender": "#f44",
        "board breaker": "#11e1e1",
        "handtrap": "#ffc300",
        "tech card": "#fc51fa",
        "brick": "#ff5757"
    }
    for cat in categories:
        role = cat['name']
        color = color_map.get(role.lower(), "#fff")
        p = details.get(role, 0)
        mn, mx = cat['min'], cat['max']
        exp = role_explanation(role, p, mn, mx)
        st.markdown(
            f"""
            <div style="margin-bottom:9px;">
                <span style="font-weight:700; color:{color}; font-size:1.11em;">{role} : {p:.2f}%</span><br>
                <span style="font-size:1em;">{exp}</span>
                <hr style="border:0.5px solid {color}; opacity:0.36; margin:8px 0;">
            </div>
            """,
            unsafe_allow_html=True,
        )

# ----------- ANIMATION, CALCUL & AFFICHAGE -----------
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

# ----------- Résultats après calcul -----------
if st.session_state.get("run_calc_done", False):
        # --------- EXPORT PDF ---------
    st.markdown("### Export PDF des résultats")
    import io
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    buf.seek(0)
    # Préparation des données pour le tableau PDF
    roles = [cat["name"] for cat in categories]
    theor_vals = [details[cat["name"]] for cat in categories]
    monte_vals = [sim_results[cat["name"]] for cat in categories]
    explanations = {}
    for i, cat in enumerate(categories):
        role = cat["name"]
        theor = theor_vals[i]
        monte = monte_vals[i]
        exp = role_explanation(role, theor, cat['min'], cat['max'])
        explanations[role] = exp

    st.download_button(
        "Exporter en PDF",
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
            buf
        ),
        file_name="simulation_ygo.pdf"
    )
    st.header("Résultats - Probabilités")

    # ----------- Probabilités hypergéométriques -----------
    details = hypergeom_prob(
        st.session_state["deck_size"],
        st.session_state["hand_size"],
        categories,
    )
    # Proba globale théorique (toutes les conditions réunies)
    theor_global = 1.0
    for v in details.values():
        theor_global *= v/100 if v > 0 else 1
    theor_global = theor_global * 100

    st.subheader(f"Probabilité théorique globale : {theor_global:.2f}%")
    theor_explains = []
    for cat in categories:
        role = cat['name']
        p = details.get(role, 0)
        mn, mx = cat['min'], cat['max']
        exp = role_explanation(role, p, mn, mx)
        theor_explains.append(f"{role} : {p:.2f}%\n{exp}\n")
        st.markdown(
            f"""
            <div style="margin-bottom:8px;">
                <span style="font-weight:700; color:#1ed760; font-size:1.13em;">{role} : {p:.2f}%</span><br>
                <span style="font-size:1em;">{exp}</span>
                <hr style="border:0.5px solid #1ed760; opacity:0.28; margin:8px 0;">
            </div>
            """,
            unsafe_allow_html=True,
        )

    # ----------- Monte Carlo -----------
    st.header("Résultats - Simulation Monte Carlo")
    sim_results = simulate(
        st.session_state["deck_size"],
        st.session_state["hand_size"],
        categories,
        st.session_state["n_sim"]
    )
    # Proba globale Monte Carlo (toutes conditions réunies)
    monte_global = 1.0
    for v in sim_results.values():
        monte_global *= v/100 if v > 0 else 1
    monte_global = monte_global * 100
    st.subheader(f"Probabilité Monte Carlo globale : {monte_global:.2f}%")
    monte_explains = []
    for cat in categories:
        role = cat['name']
        p = sim_results.get(role, 0)
        mn, mx = cat['min'], cat['max']
        exp = role_explanation(role, p, mn, mx)
        monte_explains.append(f"{role} : {p:.2f}%\n{exp}\n")
        st.markdown(
            f"""
            <div style="margin-bottom:8px;">
                <span style="font-weight:700; color:#11e1e1; font-size:1.13em;">{role} (MC) : {p:.2f}%</span><br>
                <span style="font-size:1em;">{exp}</span>
                <hr style="border:0.5px solid #11e1e1; opacity:0.28; margin:8px 0;">
            </div>
            """,
            unsafe_allow_html=True,
        )

    # --------- GRAPHIQUE matplotlib ---------
    fig, ax = plt.subplots()
    roles = [cat["name"] for cat in categories]
    values = [details[cat["name"]] for cat in categories]
    colors = ["#08e078", "#f44", "#11e1e1", "#ffc300", "#fc51fa", "#ff5757"][:len(roles)]
    ax.barh(roles, values, color=colors)
    ax.set_xlabel('Probabilité (%)')
    ax.set_title("Probabilité d'obtenir chaque type de carte (Hypergéométrique)")
    st.pyplot(fig)

    # --------- EXPORT PDF ---------
from unidecode import unidecode  # Pour retirer accents des textes français (évite bugs PDF)

def remove_accents(txt):
    try:
        return unidecode(str(txt))
    except Exception:
        return str(txt)

def export_results_pdf(deck_name, deck_size, hand_size, first_player, n_sim, theor_global, monte_global, theor_details, monte_details, explanations, img_bytes):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "", 12)
    pdf.cell(0, 8, remove_accents(f"Simulation probabilites Yu-Gi-Oh!"), ln=1)
    pdf.cell(0, 8, remove_accents(f"Deck: {deck_name}"), ln=1)
    pdf.cell(0, 8, remove_accents(f"Taille du deck: {deck_size}"), ln=1)
    pdf.cell(0, 8, remove_accents(f"Main de depart: {hand_size}"), ln=1)
    pdf.cell(0, 8, remove_accents(f"{'First' if first_player else 'Second'}"), ln=1)
    pdf.cell(0, 8, remove_accents(f"Simulations Monte Carlo: {n_sim}"), ln=1)
    pdf.cell(0, 8, remove_accents(f"Probabilite theorique globale: {theor_global:.2f}%"), ln=1)
    pdf.cell(0, 8, remove_accents(f"Probabilite Monte Carlo globale: {monte_global:.2f}%"), ln=1)
    pdf.ln(5)
    # --------- Tableau résultats par rôle ---------
    pdf.set_font("Arial", "B", 11)
    pdf.cell(55, 8, remove_accents("Role"), 1)
    pdf.cell(35, 8, remove_accents("Theorique (%)"), 1)
    pdf.cell(35, 8, remove_accents("Monte Carlo (%)"), 1)
    pdf.cell(0, 8, remove_accents("Explication"), 1)
    pdf.ln()
    pdf.set_font("Arial", "", 10)
    for i, role in enumerate(explanations):
        # theor_details[i], monte_details[i] = % pour chaque rôle
        expl = remove_accents(explanations[role])
        pdf.cell(55, 8, remove_accents(role), 1)
        pdf.cell(35, 8, f"{theor_details[i]:.2f}", 1)
        pdf.cell(35, 8, f"{monte_details[i]:.2f}", 1)
        pdf.multi_cell(0, 8, expl, border=1)
    pdf.ln(2)
    # --------- Graphique (optionnel) ---------
    if img_bytes is not None:
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
            tmp.write(img_bytes.getbuffer())
            tmp.flush()
            pdf.image(tmp.name, x=10, w=170)
    return pdf.output(dest="S").encode("latin1")
