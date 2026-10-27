from pathlib import Path

import pandas as pd
import streamlit as st

# ============================================================ #
# Loader for csv files in stream lit application with caching  #
# ============================================================ #


@st.cache_data
def load_csv(path: Path) -> pd.DataFrame:
    """Function to cache loaded dataset.

    Args:
        path (Path): Path to the CSV file.

    Returns:
        pd.DataFrame: Loaded DataFrame.
    """
    return pd.read_csv(path)


def generate_file_selector(sidebar: bool = True):
    """
    Generate a file selector in the sidebar and load the selected file into session state.
    Cache the loaded file into st.session_sate.df
    """

    # === Path to CSV Files ===
    DATASETS_DIR = Path(__file__).parent.parent.parent / "data" / "datasets"

    # === Side bar files selection ===
    csv_files = sorted([f.name for f in DATASETS_DIR.glob("*.csv")])

    # Get the default index of the menu.
    default_index = (
        csv_files.index(st.session_state.last_file) + 1
        if st.session_state.get("last_file", None) in csv_files
        else 0
    )

    # Call back function.
    def load_selected_file():
        if st.session_state.selected_file == "Select a dataset":
            st.session_state.df = None
            st.session_state.last_file = None
            return

        file_path = DATASETS_DIR / st.session_state.selected_file
        st.session_state.df = load_csv(file_path)
        st.session_state.last_file = st.session_state.selected_file
        st.sidebar.success(
            f"✅ Dataset `{st.session_state.selected_file}` successfully loaded"
        )

    # Selectbox avec on_change
    if sidebar:
        st.sidebar.selectbox(
            "**Select your dataset:**",
            ["Select a dataset"] + csv_files,
            index=default_index,
            key="selected_file",
            on_change=load_selected_file,
        )

    else:
        st.selectbox(
            "**Select your dataset:**",
            ["Select a dataset"] + csv_files,
            index=default_index,
            key="selected_file",
            on_change=load_selected_file,
        )
