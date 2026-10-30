"""Actions Expert uniquement sur clic et confirmation explicites."""
from datetime import date
import streamlit as st

from src.data_requesters.ademe import Ademe_API_requester
from src.expert_data import prepare_version
from src.version_store import VersionStore


def render_management():
    st.title("⚙️ Gestion des données et modèles")
    st.write("Préparer une version ne l’active pas. Les fichiers d’origine et les modèles de référence sont conservés.")
    store = VersionStore()
    active = store.active()
    st.caption(f"Données actives : {active['data']} · Modèles actifs : {active['model']}")
    with st.expander("Recevoir de nouveaux diagnostics", expanded=True):
        a, b = st.columns(2)
        dep = a.text_input("Département à actualiser", value="69", key="collect_department")
        source = b.selectbox("Source ADEME", ["existant", "neuf"])
        start = a.date_input("Réception à partir du", value=date(2025, 1, 1))
        end = b.date_input("Réception jusqu’au", value=date.today())
        limit = st.number_input("Volume maximal reçu", min_value=1, max_value=5000, value=500, step=100)
        approved = st.checkbox("Je souhaite lancer cette collecte réseau bornée et préparer une copie locale.")
        if st.button("Collecter et préparer une version", disabled=not approved, key="collect_data"):
            try:
                progress = st.progress(0, text="Réception ADEME…")
                raw = Ademe_API_requester(size=500).bounded_lines_by_date(dep.strip(), start, end, int(limit),
                    neuf=source == "neuf", progress=lambda done,total: progress.progress(min(done/total,1.0), text=f"{done} / {total} lignes reçues"))
                info = prepare_version(raw, source, store)
                st.session_state.last_prepared = info["id"]
                st.success("Nouvelle version préparée, non activée.")
                st.json(info)
            except Exception as exc:
                st.error(f"Actualisation interrompue : {exc}. Les versions actives sont conservées.")
    with st.expander("Valider et activer des données", expanded=True):
        entries = store.list_versions("datasets")
        if entries:
            version = st.selectbox("Version de données à examiner", [x["id"] for x in entries])
            info = store.manifest("datasets", version)
            st.json(info)
            confirm = st.checkbox("J’ai vérifié le bilan, les rejets et les limites de cette version.")
            if st.button("Valider cette version de données", disabled=not confirm, key="validate_data"):
                try:
                    store.validate_data(version)
                    st.success("Version validée ; activation encore séparée.")
                except Exception as exc:
                    st.error(str(exc))
        else:
            st.info("Aucune nouvelle version préparée. Les données initiales restent disponibles.")
        choices = ["initial"] + [x["id"] for x in store.list_versions("datasets") if x["status"] == "validated"]
        selected = st.selectbox("Données à rendre actives", choices)
        confirm_active = st.checkbox("Je confirme le changement des données actives.")
        if st.button("Activer les données choisies", disabled=not confirm_active, key="activate_data"):
            try:
                store.activate(data=selected)
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
    if st.button("Revenir à la sélection précédente", disabled=not active.get("previous"), key="rollback_versions"):
        try:
            store.rollback()
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
