# App_Enedis — préparation et modèles DPE

Projet de groupe sur les données DPE ADEME : nettoyage, enrichissement,
modèles finaux et application Streamlit locale (Standard et Intermédiaire).

## Niveau Expert et rendu final local

La page **Gestion des données et modèles** ajoute une collecte ADEME volontaire
et bornée, des versions de données à valider puis activer séparément, et le
réentraînement explicite des deux modèles. Les modèles initiaux `final_geo_v1`
et CSV d'origine ne sont jamais remplacés. Les nouvelles versions et le pointeur
actif sont dans `runtime/` (ignoré par Git), ou dans `ENEDIS_RUNTIME` si défini.
Un retour à la sélection précédente est disponible. Les anciens résultats sont
invalidés lors d'un changement actif. Les tests n'exécutent ni collecte réelle
ni entraînement complet : réponses simulées et 36 lignes/deux arbres.

L'API partage le chargeur et les sept règles d'entrée de Streamlit :

```powershell
.\.venv-app\Scripts\python.exe -m uvicorn src.prediction_api:app --host 127.0.0.1 --port 8000
curl.exe http://127.0.0.1:8000/health
curl.exe -H "Content-Type: application/json" --data-binary "@examples/prediction.json" http://127.0.0.1:8000/predict
```

API documentée via `/openapi.json` et `/docs`. Docker Compose fournit les deux
services, uniquement sur les ports locaux 8501 et 8000 ; trois CSV sont montés en
lecture seule, les versions créées vont dans un volume partagé distinct.
**Image construite et deux conteneurs testés avec succès.** Démarrer Docker Desktop
avec moteur Linux/WSL2 si nécessaire, puis :

```powershell
.\scripts\check_docker_inputs.ps1
docker compose build
docker compose up -d
docker compose run --rm --no-deps application python scripts/smoke_container.py --api-url http://api:8000
docker compose down
```

Si 8501/8000 sont déjà occupés, préserver les services existants et utiliser la
surcouche vérifiée : `docker compose -f compose.yaml -f compose.test.yaml up -d`,
puis `docker compose -f compose.yaml -f compose.test.yaml down`. Elle lie uniquement
127.0.0.1:18501 (application) et 127.0.0.1:18000 (API). C'est cette surcouche qui a
été exécutée lors des tests, sans arrêter les services déjà présents.

Ne pas utiliser `down -v` pour un arrêt normal : conserver le volume des versions.
Le protocole d'apprentissage garde les réceptions depuis 2025 réservées au test :
une collecte récente n'est pas automatiquement utilisée pour apprendre. Le
nettoyage incrémental réutilise l'IQR par lot ; sa comparabilité reste une limite.

Rendu éditable : [guide utilisateur](doc/guide_utilisateur.md),
[documentation technique](doc/documentation_technique.md),
[rapport ML final](doc/rapport_ml_final.md),
[architecture Draw.io](doc/architecture.drawio),
[scénario vidéo 4 min 50](doc/scenario_video.md),
[matrice des exigences ouvertes](doc/exigences_rendu.md).
Les trois Markdown principaux ont été rendus pour contrôler leurs longueurs :
2, 2 et 5 pages. Les PDF de contrôle restent dans `output/submission/`, hors Git.

```powershell
.\.venv-app\Scripts\python.exe scripts/render_submission_docs.py
```

**Restent non confirmés visuellement : petit écran et Exploration après refonte**,
ainsi que les derniers gestes de caméra et les nouveaux parcours Expert dans le
navigateur. Le sujet complet n'est pas présent ; conformité formelle exhaustive,
captation vidéo et déploiement restent ouverts. Aucun déploiement n'est exécuté.

## Application locale — Windows, Python 3.13

L'application dispose de quatre pages en français : Contexte, Exploration,
Carte et Prédiction. Elle utilise uniquement les données et modèles déjà
présents sur la machine, sans extraction ni entraînement au lancement.
Son environnement est séparé de `.venv-ml` et de `uv.lock`.

Installation dans un environnement application (à créer seulement s'il n'existe pas) :

~~~powershell
py -3.13 -m venv .venv-app
.\.venv-app\Scripts\python.exe -m pip install -r requirements-app.txt
~~~

Avec `uv` installé, notamment si l'environnement existant n'a pas `pip` :

~~~powershell
uv pip install --python .venv-app/Scripts/python.exe -r requirements-app.txt
~~~

Depuis `C:\Users\mouni\Documents\App_Enedis`, lancer :

~~~powershell
.\.venv-app\Scripts\python.exe -m streamlit run home.py --server.address 127.0.0.1 --server.port 8501 --browser.gatherUsageStats false
~~~

Ouvrir **http://127.0.0.1:8501** ; arrêter avec `Ctrl+C` dans le terminal.
La configuration `.streamlit/config.toml` impose également l'écoute locale
et désactive les statistiques d'utilisation. Aucun déploiement n'est prévu.

Prérequis locaux : `output/cleaned_data.csv`, `MLmodels/final_models.json`
et les artefacts complets de `MLmodels/final_geo_v1/`. Les données ne sont
pas fournies par un clone Git : demander les fichiers préparés au groupe.
Une absence de données est signalée ; la prédiction reste possible si les
modèles finaux sont disponibles. Aucun modèle historique ne sert de repli.

- Exploration : filtres en cascade (liste vide = tous), plage de surface,
  valeurs absentes incluses au choix, indicateurs, tableau limité à 500 lignes,
  quatre graphiques et export de toutes les lignes filtrées en CSV.
  Cliquer « Préparer l’export CSV filtré », puis télécharger. Le CSV utilise
  UTF-8 avec BOM, `;` et la virgule décimale pour Excel français.
- Chaque graphique a son export PNG natif Matplotlib : aucun Chrome,
  Kaleido, téléchargement de binaire ou service d'export n'est nécessaire.
  Histogramme et boîtes utilisent toutes les valeurs filtrées ; le nuage
  représente au plus 5 000 lignes, avec effectif affiché.
- Carte : marqueurs WebGL avec infobulles ; limite réglable de 1 000 à
  10 000 logements, tirage fixe et effectifs affichés. Contrôle des valeurs
  finies et de l'emprise métropolitaine/Corse ; ce contrôle ne certifie pas
  chaque adresse. Les logements superposés restent distincts dans le compte.
  Le fond CARTO est facultatif, désactivé par défaut et nécessite Internet ;
  le canevas de marqueurs fonctionne sans tuiles. WebGL doit être disponible.
- Prédiction : chargeur existant `load_final_bundle`, cache et empreintes
  des modèles contrôlées. Catégories issues de l'encodeur final, âge fixé
  à la référence 2026, H1/H2/H3, unités explicites. Les résultats réels et
  limites sont présentés, notamment sur l'existant et F/G. La MAE n'est
  jamais un intervalle de confiance individuel.

Tests (installer les dépendances de test uniquement dans l'environnement application) :

~~~powershell
uv pip install --python .venv-app/Scripts/python.exe -r requirements-app-test.txt
.\.venv-app\Scripts\python.exe -m pytest -q
.\.venv-app\Scripts\python.exe scripts/verify_app.py
.\.venv-app\Scripts\python.exe scripts/verify_final_models.py
~~~

Voir [le compte rendu de vérification](doc/application_streamlit_locale.md).

### Refonte de l'interface, comparaison et PDF

La branche `feat/20-refonte-interface` ([Issue #20](https://github.com/Abdoul-Faisal-Ouedraogo/App_Enedis/issues/20))
reprend les quatre pages avec un accueil plus court, des accès directs,
des filtres actifs visibles, une légende DPE et un cadrage automatique de carte.
Les détails techniques et crédits sont dans des sections dépliables.

La page Prédiction propose un logement ou deux profils indépendants. Les
saisies sont réactives : une modification retire immédiatement le résultat
correspondant, son PDF et, si nécessaire, l'écart comparatif jusqu'au recalcul.
L'écart est exprimé en kWh/an (B moins A) ; ce n'est pas une preuve de l'effet
d'une rénovation. La lettre reste produite par le classificateur distinct.

Chaque estimation peut être téléchargée en PDF ; la comparaison exporte les
deux logements. Le résumé contient les sept caractéristiques, les résultats,
les unités, la date du calcul en Europe/Paris, la version des modèles et les
limites essentielles. ReportLab est la seule dépendance application ajoutée ;
pypdf sert uniquement aux tests.

L'aide géographique se choisit dans chaque profil : sélectionner un département
puis une commune, consulter la proposition et cliquer **Utiliser ces valeurs**.
L'altitude et la zone restent modifiables. Le référentiel local requis est
`data/communes-france-2025.csv` ; les règles H1/H2/H3 sont lues comme listes
littérales du notebook 1, sans exécution. Le remplacement départemental utilise
la moyenne des communes du référentiel, jamais celle des logements. Les
corrections de jointure Lyon/Pierre-Bénite sont conservées. Une référence ou
une zone indisponible est signalée et n'empêche pas une saisie manuelle.
Les codes 2A/2B ne sont pas convertis arbitrairement en 20 pour déduire une zone.

Voir [le bilan de la refonte et ses contrôles](doc/refonte_interface_locale.md).
Ce bilan distingue les validations manuelles réalisées des contrôles restant à
faire, notamment **le petit écran et la page Exploration après refonte**.

## Installation des notebooks — Windows, Python 3.13

Depuis la racine du dépôt, sans modifier les environnements existants :

~~~powershell
py -3.13 -m venv .venv-ml
.\.venv-ml\Scripts\python.exe -m pip install -r requirements.txt
.\.venv-ml\Scripts\python.exe -m jupyterlab
~~~

Sélectionner .venv-ml comme environnement Python dans VS Code/Jupyter.
Le script setup_env.ps1 prépare cet environnement et s'arrête : il ne lance
aucune application, extraction ou entraînement.

Avec uv déjà installé :

~~~powershell
$env:UV_PROJECT_ENVIRONMENT = ".venv-ml"
uv sync --locked
uv run --locked python -m jupyterlab
~~~

pyproject.toml décrit les dépendances ML/notebooks, uv.lock fixe les versions
et requirements.txt est son export pour pip. requirements-notebooks.txt
est un alias du même fichier. Pour régénérer l'export après une modification
intentionnelle des dépendances :

~~~powershell
uv export --locked --no-hashes --no-emit-project --format requirements-txt --output-file requirements.txt
~~~

Les dépendances des anciennes expériences XGBoost restent disponibles dans
l'option experiments. Elles ne sont pas nécessaires aux notebooks ML courants.
L'application utilise son environnement séparé ; aucune de ces commandes
ML/notebooks ne la lance.

## Données locales et ordre des notebooks

Les dossiers data/ et output/ sont ignorés par Git. Un clone seul ne contient
pas les données : récupérer les fichiers locaux auprès du groupe.

1. Notebooks_Api_Traitement/1_data_preparation.ipynb lit
   data/ademe_data_old.csv, data/ademe_data_new.csv et
   data/communes-france-2025.csv, puis exporte output/cleaned_data.csv.
   Il conserve conso_5_usages_ef, ajoute l'âge, l'altitude et les zones
   climatiques H1/H2/H3. Année de référence : 2026. Extraction API désactivée.
   Les corrections de jointure de Nouhayla pour Lyon/Pierre-Bénite sont intégrées.
   Avant remplacement, le CSV est sauvegardé dans output/backups/. Les dates et
   identifiants sont exportés séparément dans output/cleaned_data_metadata.csv.
2. 1a_enrichissement_donnees.ipynb conserve le travail de Nouhayla sur le Rhône
   (13 481 logements selon ses sorties historiques). Il nécessite
   output/ademe_data_69_cleaned.csv et data/climate_zones.csv, absents ici.
   Son export output/ademe_data_69_enriched.csv reste distinct du CSV commun.
   Son calcul Rhône complet reste non vérifiable sans ces entrées. Ses règles
   géographiques vérifiées sont reprises dans le notebook 1 ; ses sous-zones
   climatiques ne sont pas déduites sans référence.
3. 2_classification_dpe.ipynb prédit etiquette_dpe. Il présente le modèle final
   corrigé et ses résultats sauvegardés, sans entraînement ou nouvelle
   prédiction sur le lot réservé.
   Les expériences originales du Rhône sont conservées intégralement dans
   Notebooks_Api_Traitement/archives/2_classification_dpe_rhone_historique.ipynb.
4. 3_regression_consommation.ipynb prédit conso_5_usages_ef, consommation
   finale totale des cinq usages en **kWh/an**. Il présente également le modèle
   final corrigé. Les versions précédentes des deux notebooks sont conservées
   intégralement dans archives/.

Ouvrir les notebooks depuis la racine ou leur dossier : ils retrouvent la racine
automatiquement. Les deux notebooks ML rechargent les modèles finaux et
vérifient leurs prédictions de contrôle sur des exemples de développement.
Aucun notebook courant ne lance d'entraînement ou de recherche de paramètres.

Les données corrigées sont versionnées par empreinte dans
output/preparation_manifest.json. Les anciens modèles restent associés aux
anciennes données via MLmodels/data_reference.json. Les modèles finaux corrigés
sont dans MLmodels/final_geo_v1/, désignés par MLmodels/final_models.json.
Ne pas remplacer les zones H1/H2/H3 par H1c/H2d sans leur référence.
Le module historique src/processing/data_cleaner.py est une autre chaîne ;
il ne remplace pas le notebook 1 et n'est pas utilisé par les modèles courants.

## Modèles et vérifications sans entraînement

Source commune contrôlée : **616 057 logements, 94 départements**, 16 colonnes.
Les deux modèles utilisent les mêmes sept caractéristiques du logement :
surface, niveaux, âge, altitude, énergie de chauffage, type et zone climatique.
Les coûts, consommations détaillées et étiquettes ne sont pas des entrées.

Artefacts finaux, entraînés sur 453 680 lignes corrigées (entraînement + validation) :

- MLmodels/final_geo_v1/classification.joblib et classification_variables.json
- MLmodels/final_geo_v1/regression.joblib et regression_variables.json
- MLmodels/final_geo_v1/frozen_protocol.json, comparison_validation.json,
  results.json, partition_distributions.json, reload_check.json et split_plan.json
- MLmodels/final_models.json : manifeste de la version à utiliser

Les anciens artefacts restent conservés pour reproduire le travail précédent :

- MLmodels/pipeline_random_forest_consommation.pkl
- MLmodels/features_target_columns_consommation.pkl

Artefacts de classification commune, distincts des modèles historiques :

- MLmodels/pipeline_classification_common.pkl
- MLmodels/classification_common.json : paramètres, versions, empreintes du
  CSV/modèle et métriques par classe.

Depuis la racine, dans l'environnement installé :

~~~powershell
.\.venv-ml\Scripts\python.exe -m src.ml_workflow
.\.venv-ml\Scripts\python.exe -m src.ml_workflow --historical
.\.venv-ml\Scripts\python.exe scripts/verify_final_models.py
.\.venv-ml\Scripts\python.exe scripts/verify_notebooks.py
.\.venv-ml\Scripts\python.exe scripts/verify_preparation.py
.\.venv-ml\Scripts\python.exe scripts/verify_geography.py
.\.venv-ml\Scripts\python.exe scripts/verify_validation_groups.py
~~~

La commande sans option valide le CSV corrigé et les modèles finaux.
L'option --historical vérifie les anciens modèles sur leur sauvegarde de référence.
verify_final_models.py contrôle les artefacts, les exemples de rechargement
et les résultats depuis les prédictions conservées : aucun nouveau calcul
de prédiction des modèles sur le réservé, aucun entraînement.
Les notebooks ML sont vérifiés en bloquant réseau, entraînement et sauvegardes.
Le contrôle de préparation rejoue les bruts locaux en ne chargeant que les
colonnes utiles et compare le CSV/sa traçabilité sans les écraser. Les deux
derniers scripts vérifient les altitudes/jointures et les groupes de validation.

Pour préparer le découpage et annoncer la comparaison de classification :

~~~powershell
.\.venv-ml\Scripts\python.exe scripts/prepare_classification_comparison.py
.\.venv-ml\Scripts\python.exe scripts/compare_classification.py
~~~

Ces commandes sans option n'entraînent rien. La comparaison autorisée a été
exécutée une fois : trois Random Forest de 100 arbres,
profondeurs 10/20, avec/sans pondération, deux threads, sur le même échantillon
d'entraînement de 60 000 lignes. Le choix utilise seulement le F1 macro sur
55 235 lignes de validation chronologique, après séparation des groupes liés.
Le modèle profondeur 10 pondéré est retenu au F1 macro de validation. Les deux
modèles finaux de 100 arbres sont entraînés sur les 453 680 lignes d'entraînement
et de validation, avec deux threads. La régression conserve ses réglages antérieurs,
sans nouvelle recherche. Le lot réservé de 107 666 lignes est évalué après gel ;
aucun réglage n'a suivi. L'ancienne commande --train-classification
est bloquée sur le nouveau CSV pour éviter de réutiliser l'ancien test aléatoire.
Charger uniquement les fichiers pickle fournis par le groupe.

## Résultats finaux et limites

Sur le lot réservé interne de 107 666 lignes :

- Classification : accuracy **55,41 %**, F1 macro **0,4031** ; référence toujours C :
  accuracy 36,72 %, F1 macro 0,0767.
- Régression : MAE **1 814,68 kWh/an**, RMSE **2 957,21 kWh/an**, R² **0,6531**.
  Référence médiane constante : MAE 3 505,67 kWh/an.
- Classification existant/neuf : accuracy **38,70 % / 74,43 %**. La classification
  reste faible sur F/G et dans l'existant ; les faux positifs sont nombreux.

**Ce lot reste interne à des données déjà exploitées : ce n'est pas un test
externe indépendant.** Les paramètres ont été figés avant cette évaluation.
Le rechargement des nouveaux modèles reproduit les prédictions de contrôle.
Les anciens modèles restent inchangés.

Consulter le [rapport final](doc/modeles_finaux_2026-10-29.md) pour les distributions
des classes et populations, comparaisons, résultats par classe et par source,
artefacts, contrôles et instructions de reproduction dans une copie séparée.

### Références historiques

Les scores suivants concernent uniquement la sauvegarde antérieure aux
corrections géographiques ; ils ne sont pas les scores du nouveau CSV.

Régression : MAE **2 121,45 kWh/an**, RMSE **3 954,70 kWh/an**, R² **0,6932**,
sur 184 818 logements de test. Résultats reproduits sans réentraînement.
Le test ayant aussi servi à comparer les modèles, une évaluation finale sur
un jeu indépendant reste nécessaire.

Classification commune : accuracy **0,5796**, F1 macro **0,4759** ; test
stratifié 70/30, graine 42. Ce premier modèle est encore modeste, surtout
sur F et G. Les scores historiques du Rhône ne sont pas directement comparables
car les données, le périmètre et les variables d'entrée diffèrent.

L'échantillon est filtré sur les coûts/surfaces et contient beaucoup de neuf.
Il ne représente pas à lui seul le parc français. La validation chronologique
par groupes est exécutée. Les filtres de préparation ont encore été calculés
globalement ; une validation externe reste nécessaire. Une prédiction DPE n'est pas un diagnostic
réglementaire ; la MAE n'est pas un intervalle de confiance individuel.

Voir [l'audit détaillé](doc/audit_modeles_2026-10-29.md) pour les contrôles
effectués et les points restant ouverts.
Voir aussi le [rapport de correction et de séparation](doc/preparation_validation_2026-10-29.md)
pour les fichiers sauvegardés, dates/identifiants, effectifs des partitions
et limites du protocole préparé (notamment 91,7 % de neuf en validation).

## Contribution

Suivre [CONTRIBUTING.md](CONTRIBUTING.md) : Issue, branche dédiée, Pull Request
et revue avant intégration à main. Aucun push pendant la correction locale.
