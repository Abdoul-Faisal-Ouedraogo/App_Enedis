# Préparation du futur déploiement - aucune exécution

Les fichiers racine Dockerfile/Compose et les endpoints de santé sont les bases
réutilisables. Ils sont volontairement liés à 127.0.0.1 ; ce dossier n'active aucun
hébergement, tunnel, publication ou déploiement.

Avant une décision de mise en ligne :

- Répéter les tests de l'image locale sur la future machine cible avec moteur Docker Linux.
- Définir l'hébergement, TLS, authentification et autorisations séparées pour les
  actions de collecte/entraînement/activation. L'API actuelle est locale et sans auth.
- Fournir les CSV par volumes ou stockage privé, jamais par construction d'image.
- Prévoir sauvegarde/restauration du registre et de chaque version, quotas CPU/mémoire,
  surveillance des erreurs et contrôle du contrat ADEME.
- Évaluer les limites ML, la protection des adresses et les conditions des sources
  avant d'exposer un service à d'autres utilisateurs.
- Faire les contrôles visuels petit écran et Exploration après refonte et relire
  la grille officielle du sujet lorsqu'elle sera disponible.

Aucun identifiant cloud, secret, action CI de déploiement ou configuration publique
n'est ajouté. Un changement d'adresse d'écoute distante ne doit pas être effectué
implicitement en reprenant le Compose local.
