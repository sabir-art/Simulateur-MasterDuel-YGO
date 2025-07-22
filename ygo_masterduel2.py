import streamlit as st
import json
import time
import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import hypergeom
from fpdf import FPDF
from unidecode import unidecode
import io
import pandas as pd

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
        "subtitle": "Build your deck, simulate your opening odds, and export your results as a PDF.",
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

# Titre principal
st.title(T["main_title"])
st.caption(T["subtitle"])
