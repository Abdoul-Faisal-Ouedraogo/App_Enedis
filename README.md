# App_Enedis — préparation et modèles DPE

Projet de groupe sur les données DPE ADEME. Le périmètre courant comprend
le nettoyage, l'enrichissement et les deux modèles. Le développement de
l'application attend une autorisation séparée.

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
L'application Streamlit reste hors du périmètre de cette livraison des modèles ;
aucune de ces commandes ne la lance.

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
