$ErrorActionPreference = "Stop"
$repo = Split-Path $PSScriptRoot -Parent
$required = @("output/cleaned_data.csv", "output/cleaned_data_metadata.csv", "data/communes-france-2025.csv", "MLmodels/final_models.json", "MLmodels/final_geo_v1/classification.joblib", "MLmodels/final_geo_v1/regression.joblib")
foreach ($relative in $required) {
    if (-not (Test-Path -LiteralPath (Join-Path $repo $relative) -PathType Leaf)) {
        throw "Fichier local manquant : $relative. Recuperer la copie preparee aupres du groupe ; aucun telechargement automatique."
    }
}
docker info --format '{{.ServerVersion}}'
if ($LASTEXITCODE -ne 0) { throw "Demarrer Docker Desktop et attendre le moteur Linux (WSL2), puis relancer ce controle." }
Write-Output "Entrees presentes et moteur Docker accessible."
