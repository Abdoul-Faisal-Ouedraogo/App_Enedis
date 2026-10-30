"""Application locale : aucune extraction ni aucun entraînement."""
import streamlit as st
from src.streamlit_app import run

st.set_page_config(page_title="Habitat & énergie", page_icon="🏡", layout="wide")
run()
