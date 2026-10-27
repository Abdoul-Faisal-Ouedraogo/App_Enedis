# setup_env.ps1
# Cree l'environnement virtuel (.venv), installe les dependances et lance l'application.
# Usage, depuis la racine du projet : .\setup_env.ps1

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# 1. Creer l'environnement virtuel avec Python 3.13 (sans erreur s'il existe deja)
uv venv --python 3.13 --allow-existing

# 2. Installer les dependances declarees dans pyproject.toml / uv.lock
uv sync

# 3. Activer l'environnement virtuel
. .\.venv\Scripts\Activate.ps1

# 4. Lancer l'application Streamlit
streamlit run home.py
