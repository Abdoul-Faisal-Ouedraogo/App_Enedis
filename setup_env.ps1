# setup_env.ps1
# Prepare uniquement l'environnement des donnees et notebooks ML.
# Usage, depuis la racine du projet : .\setup_env.ps1

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# Ne pas modifier les environnements deja utilises dans le projet.
if (-not (Test-Path -LiteralPath ".venv-ml\Scripts\python.exe")) {
    py -3.13 -m venv .venv-ml
    if ($LASTEXITCODE -ne 0) { throw "Creation de l'environnement impossible." }
}
# Un environnement cree par uv peut ne pas contenir pip.
& .\.venv-ml\Scripts\python.exe -m ensurepip --upgrade
if ($LASTEXITCODE -ne 0) { throw "Initialisation de pip impossible." }
& .\.venv-ml\Scripts\python.exe -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "Installation des dependances impossible." }
Write-Host "Environnement ML pret. Selectionnez .venv-ml dans Jupyter/VS Code."
Write-Host "Verification sans entrainement : .\.venv-ml\Scripts\python.exe -m src.ml_workflow"
