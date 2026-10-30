# Docker local

Depuis PowerShell à la racine du dépôt :

```powershell
.\scripts\check_docker_inputs.ps1
docker compose config --quiet
docker compose build
docker compose up -d
docker compose ps
docker compose logs --tail 50
docker compose run --rm --no-deps application python scripts/smoke_container.py
docker compose down
```

Application : http://127.0.0.1:8501. Les fichiers de données sont des montages
en lecture seule ; les nouveaux travaux Expert seront conservés dans un volume
distinct, jamais dans les originaux. `down` conserve ce volume ; ne pas utiliser
`down -v` pour un arrêt normal. `create_host_path: false` empêche Compose de créer
un dossier vide à la place d'un CSV absent. Le script Windows vérifie les entrées.

Sur un autre ordinateur : installer Docker Desktop avec moteur Linux/WSL2,
copier le dépôt avec les modèles finaux et les trois fichiers locaux suivants,
en conservant leurs chemins : `output/cleaned_data.csv`,
`output/cleaned_data_metadata.csv`, `data/communes-france-2025.csv`.
Les autres CSV bruts et sauvegardes ne sont pas nécessaires au démarrage.
Le contexte utilise une liste d'autorisation et n'incorpore ni CSV, ni secrets,
ni environnements, ni PDF générés. L'installation des paquets et de l'image de
base nécessite Internet à la construction ; aucune collecte ni entraînement au
démarrage. Les modèles sont chargés depuis les artefacts finaux contrôlés.

État constaté le 30/10/2026 : client Docker 29.8.1 présent, mais moteur Linux
inaccessible (`dockerDesktopLinuxEngine` absent). **Construction et exécution
Docker non réalisées** dans cet état. Action : ouvrir Docker Desktop, activer
le moteur Linux/WSL2 si nécessaire et attendre « Engine running », puis exécuter
les commandes ci-dessus. Le contrôle de configuration ne nécessite pas le moteur.
Le script de smoke-test n'est pas une validation déjà exécutée dans Docker.

Les contrôles visuels **petit écran** et **Exploration après refonte** restent
non confirmés ; voir `refonte_interface_locale.md`.
