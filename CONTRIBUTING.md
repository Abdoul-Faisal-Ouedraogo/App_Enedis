# Contribuer au projet App_Enedis

## Organisation de l'équipe

Le chef de projet coordonne les Issues, les priorités et les mises en
production. Chaque membre peut développer une fonctionnalité, mais personne ne
modifie directement `main`.

## 1. Commencer par une Issue

Avant de coder :

1. recherchez une Issue existante ;
2. créez-en une si nécessaire ;
3. décrivez le besoin, le résultat attendu et les critères d'acceptation ;
4. assignez l'Issue à la personne qui la réalise.

Le tableau GitHub Projects sert à suivre les colonnes `À faire`, `En cours`,
`En revue` et `Terminé`.

## 2. Créer une branche dédiée

Partez de `main` à jour :

```powershell
git switch main
git pull origin main
git switch -c feat/12-import-donnees
```

Utilisez les préfixes suivants :

- `feat/` pour une fonctionnalité ;
- `fix/` pour une correction ;
- `docs/` pour la documentation ;
- `test/` pour les tests ;
- `chore/` pour la maintenance.

Remplacez `12` par le numéro de l'Issue.

## 3. Faire des commits clairs

Utilisez la convention Conventional Commits :

```text
feat: ajouter l'import des données Enedis
fix: corriger le traitement des valeurs manquantes
docs: expliquer l'installation locale
test: couvrir le calcul de consommation
```

Un commit doit rester petit et cohérent. Évitez les messages comme `update` ou
`fix`.

## 4. Tester avant de pousser

Depuis l'environnement virtuel activé :

```powershell
python -m compileall .
python -m pytest
```

Si aucun test n'existe encore, indiquez-le dans la Pull Request et ajoutez des
tests lorsque cela est pertinent.

## 5. Ouvrir une Pull Request

Poussez votre branche :

```powershell
git push -u origin feat/12-import-donnees
```

La Pull Request doit :

- expliquer le problème résolu ;
- référencer l'Issue, par exemple `Closes #12` ;
- décrire les tests exécutés ;
- signaler les points à relire et les éventuelles captures d'écran.

Demandez au moins une revue à un autre membre. Répondez aux remarques avant
l'intégration. Seul le chef de projet, ou une personne désignée par lui,
fusionne une Pull Request validée dans `main`.

## Règles de sécurité

Ne mettez jamais de mot de passe, token ou clé API dans le dépôt. Utilisez un
fichier `.env` local ignoré par Git et documentez les variables nécessaires
dans `.env.example`.
