from pathlib import Path

import pandas as pd
import streamlit as st

from src.data_requesters import Ademe_API_requester, api_ademe
from src.processing.data_cleaner import DataCleaner
from src.utils.dataloader import generate_file_selector

ASSETS_PATH = Path(__file__).parent.parent / "assets"
# Image
st.sidebar.image(ASSETS_PATH / "light_bulb.gif")

# General configuration
st.set_page_config(page_title="Datasets", page_icon="📂", layout="wide")

# === Path to CSV Files ===
DATASETS_DIR = Path(__file__).parent.parent / "data" / "datasets"

# === Side bar files selection ===
csv_files = sorted([f.name for f in DATASETS_DIR.glob("*.csv")])


@st.cache_data
def load_csv(files):
    dfs = []
    for f in files:
        df = pd.read_csv(f)
        dfs.append(df)
    return pd.concat(dfs, ignore_index=True)


st.title("📂 Manage your Datasets")

# Main tabs
(
    tab1,
    tab2,
) = st.tabs(["🧮 Your Datasets", "🛜 Fetch new data"])


# === Dataset manager ===
# === File uploader ===
with tab1:
    if not csv_files:
        st.warning("⚠️ Aucun dataset disponible.")

    else:
        generate_file_selector(sidebar=False)

        # Load the data in memory.
        data = st.session_state.get("df", None)

        if data is None:
            st.info("⬆️ Please select a dataset to get started.")

        else:
            st.write("Number of rows in the dataset:", len(data))
            st.write(data.head(5))

            # Action butons
            col1, col2, col3 = st.columns(3)

            with col1:
                # Download button to download the current dataset
                st.download_button(
                    "💾 Download current dataset (CSV)",
                    data=data.to_csv(index=False).encode("utf-8"),
                    file_name=f"{st.session_state.last_file}",
                    mime="text/csv",
                )

            with col2:
                # Button to refresh the current data set.

                if st.button("🔄 Refresh the current dataset with new data"):
                    file_path = DATASETS_DIR / st.session_state.last_file

                    # List to get the new data from the both API endpoints
                    new_data = list()

                    # Get the latest DPE date by converting to datetime
                    latest_dpe_date = pd.to_datetime(
                        data["date_reception_dpe"], errors="coerce"
                    ).max()

                    # Get the string representation of the date.
                    latest_dpe_date = latest_dpe_date.strftime("%Y-%m-%d")

                    # Get the partment code from the dataset
                    departement = str(data["code_departement_ban"].iloc[0]).zfill(2)

                    with st.spinner("Fetching new data from both ADEME API..."):
                        loading_text = st.empty()
                        try:
                            loading_text.text("Fetching data on old buildings...")
                            progress_bar = st.progress(0.0)
                            status_text = st.empty()

                            # === Load Data ===
                            def progress_cb_old(current: int, total: int) -> None:
                                frac = (current / total) if total else 0.0
                                progress_bar.progress(min(1.0, frac))
                                status_text.text(f"Retrieved {current:,} / {total:,}")

                            # Query the API for the new data since the latest DPE date
                            new_data.extend(
                                api_ademe.custom_lines_request(
                                    neuf=False,
                                    progress_callback=progress_cb_old,
                                    qs=f"date_reception_dpe:[{latest_dpe_date} TO *] AND code_departement_ban:{departement}",
                                ),
                            )

                            loading_text.text("Fetching data on new buildings...")

                            # Query the API for new housing data since the latest DPE date
                            new_data.extend(
                                api_ademe.custom_lines_request(
                                    neuf=True,
                                    qs=f"date_reception_dpe:[{latest_dpe_date} TO *] AND code_departement_ban:{departement}",
                                )
                            )

                            loading_text.empty()
                        except Exception as e:
                            loading_text.empty()
                            st.error(f"❌ Error while fetching data: {e}")
                            new_data = []

                        # Generate a Dataframe from the new data and clean it
                        if new_data:
                            new_df = pd.DataFrame(new_data)
                            cleaner = DataCleaner(new_df)
                            new_df = cleaner.clean_all()

                            # Concatenate the new data to the existing one
                            combined_df = pd.concat(
                                [data, new_df], ignore_index=True
                            ).drop_duplicates()

                            # free the memory
                            del cleaner
                            del new_df
                            st.session_state.df = None

                            # Save the updated data to the CSV file
                            combined_df.to_csv(file_path, index=False)

                            # Update the session state
                            st.session_state.df = combined_df
                            data = st.session_state.df

                            # Keep track of the update
                            st.session_state.has_updated = True

                            # Rerun the page
                            st.rerun()

                if st.session_state.get("has_updated", False):
                    st.success("✅ Dataset updated successfully.")
                    st.session_state.has_updated = False

            with col3:
                # Button to delete the current dataset
                if st.button("🗑️ Delete this dataset"):
                    file_path = DATASETS_DIR / st.session_state.last_file
                    file_path.unlink()  # supprime le fichier
                    st.success(
                        f"✅ `{st.session_state.last_file}` supprimé avec succès."
                    )
                    st.session_state.df = None
                    st.session_state.last_file = None
                    st.rerun()  # recharge la page pour actualiser la liste


# === ADEME API Import ===
with tab2:
    st.header("🌐 Import new department Data from ADEME API")
    type_bat = st.radio("Building type:", ["Existing", "New"], horizontal=True)
    neuf = type_bat == "New"

    departement = st.text_input("Department code (e.g.: 75, 13, 59...)", "33")
    limit = st.number_input("Maximum number to retrieve", 100, 10_000, 1000, step=500)
    size = st.slider("API batch size (size)", 100, 2500, 500, step=100)

    fetch_api = st.button("🚀 Fetch from ADEME API")

    # Define progress elements
    if st.session_state.get("data_api", None) is None:
        progress_bar = st.progress(0.0)
        status_text = st.empty()
    else:
        progress_bar = st.progress(1.0)
        status_text = st.text("Data already loaded in session.")

    # === Load Data ===
    def progress_cb(current: int, total: int) -> None:
        frac = (current / total) if total else 0.0
        progress_bar.progress(min(1.0, frac))
        status_text.text(f"Retrieved {current:,} / {total:,}")

    def load_api(neuf: bool, limit: int, departement: str, size: int):
        requester = Ademe_API_requester(size=size)
        data_api = requester.custom_lines_request(
            neuf=neuf,
            limit=limit,
            progress_callback=progress_cb,
            qs=f"code_departement_ban:{departement}",
        )
        return pd.DataFrame(data_api)

    data_api = st.session_state.get("data_api", None)

    if fetch_api:
        data_api = load_api(neuf, limit, departement, size)
        if not data_api.empty:
            cleaner_api = DataCleaner(data_api)
            data_api = cleaner_api.clean_all()
            st.session_state.data_api = data_api
        else:
            st.warning("⚠️ No data returned from ADEME API.")
            st.session_state.data_api = None

        data_api = st.session_state.data_api

    if data_api is not None:
        new = data_api["age_batiment"].sum() == 0

        dep = data_api["code_departement_ban"].iloc[0]

        st.success(
            f"✅ Data for {"new" if new else "existing"} housing for department {dep} loaded and processed successfully: {len(data_api)} rows."
        )

        st.write(data_api.head(5))

        # == Action buttons ==
        col1, col2 = st.columns(2)

        with col1:
            st.download_button(
                "💾 Download result API (CSV)",
                data=data_api.to_csv(index=False).encode("utf-8"),
                file_name=f"dpe_ademe_{dep}_{'new' if neuf else 'existing'}.csv",
                mime="text/csv",
            )
        with col2:
            file_path = DATASETS_DIR / f"data_{dep}.csv"

            action = st.session_state.get("action", "Replace")

            if st.button("➕ Add to your datasets"):
                if file_path.exists():
                    if action == "Replace":
                        data_api.to_csv(file_path, index=False)
                        st.session_state.has_newfile = True
                        st.rerun()

                    elif action == "Concat & Overwrite":
                        existing_df = pd.read_csv(file_path, low_memory=False)

                        combined_df = pd.concat(
                            [existing_df, data_api], ignore_index=True
                        ).drop_duplicates()

                        combined_df.to_csv(file_path, index=False)

                        st.session_state.has_newfile = True
                        st.rerun()

                else:
                    data_api.to_csv(
                        file_path,
                        index=False,
                    )
                    st.session_state.has_newfile = True
                    st.rerun()

            # Update the state to refresh the selection menu.
            if st.session_state.get("has_newfile", False):
                st.success(f"✅ File `{file_path.name}` added to your dataset.")
                st.session_state.has_newfile = False

            if file_path.exists():
                st.warning(f"⚠️ Data for department `{dep}` already exists.")
                # Display a radio button to choose action
                action = st.radio(
                    "File exists: choose action",
                    options=["Replace", "Concat & Overwrite"],
                    index=0,
                )
                st.session_state.action = action
