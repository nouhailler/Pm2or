# Historique des changements

## À venir

### Prévu à partir du 15 septembre 2026

- Enrichir le projet fictif Les Colibris pour en faire une démonstration clé en main :
  scénario, gouvernance, planning, exigences, livrables, registres, documents,
  preuves de recette, acceptation, clôture et guide de démonstration.
- Le cas actuel reste un support d’entraînement partiel. Ce chantier n’est pas encore réalisé.

### Documentation — 14 septembre 2026

- Création de `CONTEXT.md` pour conserver l’état livré et le point de reprise de la prochaine session.
- Création de `CHANGELOG.md` et mise à jour du README sur l’état du cas d’exemple
  et la préparation de la future démonstration.

## 0.1.4 — 15 septembre 2026

- Ajout d’infobulles explicatives sur les menus, boutons, onglets, champs de formulaire,
  listes et tableaux de l’application.
- Aides métier détaillées pour les principales actions PM², avec texte générique pour les
  nouveaux contrôles qui ne disposent pas encore d’une description spécialisée.
- Application automatique aux pages et dialogues créés dynamiquement, sans remplacer les
  infobulles spécifiques existantes.
- Ajout de descriptions accessibles cohérentes avec les infobulles.
- Validation : 62 tests automatisés et analyse Ruff.

## 0.1.3 — 14 septembre 2026

- Regroupement des menus dans cinq tiroirs repliables : Vue d’ensemble, Étapes du projet,
  Pilotage, Données et documents, Outils avancés.
- Ouverture automatique du tiroir de la destination lors d’une navigation par raccourci.
- Libellés clarifiés : Tableau de bord, Passages de phase, Données du projet,
  Catalogue des entités.
- Conservation de l’écran lors du repli d’une catégorie et vérification de la navigation au clavier.
- Mise à jour des guides et captures d’écran ; publication du paquet Debian et des assets de formation.
- Validation : 59 tests, Ruff, mypy, contrôle visuel, démarrage du paquet extrait sans interface et avec Qt.

## 0.1.2 — 14 septembre 2026

- Parcours graphique des phases PM² dans le tableau de bord, avec position réelle,
  accès aux assistants et raccourcis de pilotage.
- Repères issus de la méthodologie figée du projet ; disposition adaptée aux écrans plus étroits.
- Déplacement de la revue RfC vers l’assistant d’exécution, conformément à la configuration méthodologique.
- Correction du démarrage PyInstaller : nom du fichier YAML embarqué aligné sur le chargeur.
- Ajout du cas fictif Les Colibris, de son générateur, de l’archive initiale et des exercices.
- Validation : 57 tests, Ruff, mypy et démarrage du paquet Debian extrait.

## 0.1.1 — 14 septembre 2026

- Gel de la méthodologie par projet : snapshot YAML, version et empreinte SHA-256.
- Comparaison et mise à niveau explicite et auditée de la méthodologie.
- Archives `.pm2` au format 1.1 avec snapshot et contrôles de cohérence ; migration des anciennes bases.
- Publication du paquet Debian 13 amd64.

## 0.1.0

- Première version : assistants des quatre phases, gouvernance, WBS et dépendances,
  exigences, livrables, registres et workflows métier.
- Catalogue des 47 entités, acceptation, 21 modèles documentaires, exports et archives locales.
- Application desktop hors ligne avec stockage SQLite.
