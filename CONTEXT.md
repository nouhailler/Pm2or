# Contexte du projet PM² Desktop

Dernière mise à jour : **1er novembre 2026**.

## Point de reprise

La release publiée reste la **0.1.7**. La branche `main` contient désormais les
fonctions prévues pour la prochaine version : moteur CPM, gestion des ressources,
graphe de traçabilité, nouvelle expérience d'accueil et système de mises à jour.
Un centre de connaissances hors ligne complète désormais l'accompagnement des novices :
glossaire, méthodologies, historique, guide de choix et sources officielles.
Avant publication, reconstruire et tester le bundle PyInstaller et le paquet Debian,
puis préparer les notes et le numéro de la prochaine release.

Le nouveau parcours utilisateur comprend un menu hamburger, cinq catégories métier,
un onboarding légal obligatoire, une aide contextuelle à la première visite et des
infobulles sur les champs et les actions. Les paramètres système exposent la date de
sortie et la dernière vérification, déclenchent un contrôle manuel et configurent la
recherche périodique de releases. L'installation automatique reste volontaire : elle
exige le SHA-256 fourni par GitHub et passe par l'autorisation système Linux.

## État livré

- Version publiée : **0.1.7**, sur `main`, tag `v0.1.7`.
- État de développement : changements non encore publiés destinés à la prochaine release.
- Dépôt : <https://github.com/nouhailler/Pm2or>.
- Release : <https://github.com/nouhailler/Pm2or/releases/tag/v0.1.7>.
- Correctif de démarrage : PyInstaller embarque désormais
  `pm2/resources/PM2_METHODOLOGY.yaml`, comme le paquet Python et le chargeur.
- Tableau de bord : parcours graphique des quatre phases, position réelle du projet,
  revues de passage et raccourcis vers les assistants, registres, planning et validations.
- La revue RfC se trouve dans l’assistant d’exécution, avant la clôture.
- Navigation : cinq catégories repliables — Vue d’ensemble, Étapes du projet, Pilotage,
  Données et documents, Outils avancés. Une destination ouverte par un raccourci
  déplie automatiquement son tiroir ; le bouton `☰` masque ou affiche l'ensemble.
- Paramètres système : version et date de sortie, dernière vérification, recherche
  manuelle ou périodique, installation optionnelle et création d'un raccourci desktop.
- Onboarding : mentions légales sur la responsabilité des données, visite guidée,
  aides contextuelles par écran et nouveau logo intégré à l'application et au paquet.
- Aide contextuelle : infobulles sur les menus, boutons, onglets, formulaires, listes et
  tableaux, y compris les composants créés dynamiquement ; descriptions accessibles associées.
- Détail des tableaux : double-clic ou touche Entrée sur une ligne pour afficher toutes ses
  valeurs ; fenêtre enrichie pour les documents avec objectif et rendu complet.
- Exemple documentaire : les 21 artefacts PM² de l’archive Les Colibris contiennent désormais
  178 champs illustratifs renseignés.
- Validation publiée de la 0.1.7 : **127 tests**, couverture lignes/branches de **81,93 %**,
  Ruff, mypy sur toute l'interface, audit des dépendances et SBOM CycloneDX.
- Validation de la branche courante : **158 tests**, couverture de **82,59 %**,
  Ruff et mypy sans erreur.

Les releases 0.1.2 à 0.1.7 incluent le `.deb` et un fichier d'empreintes SHA-256.
Les versions de formation incluent aussi `portail-association.pm2` et `EXERCICES.md`.
Le paquet vise Debian 13 amd64, glibc 2.41 ou ultérieure.

## Exemple actuel

- Référence : `FORMATION-2026-001`.
- Nom : **EXEMPLE — Portail de l’association Les Colibris**.
- Cas entièrement fictif : association de 120 membres, portail de réservation d’activités.
- Budget : **24 000 CHF**, dont 21 000 CHF de tâches proposées et 3 000 CHF de réserve.
- Dates proposées : 14 septembre au 11 décembre 2026.
- Phase initiale : lancement ; dix tâches à 0 %, quatre livrables avec critères et tests,
  cinq exigences liées aux tâches et livrables, quatre parties prenantes, trois risques,
  un problème, une décision à prendre et une demande de changement.
- Demande d’initiation et étude d’opportunité préremplies ; charte partiellement renseignée
  avec autorisation laissée vide. Catalogue documentaire créé, mais les autres documents
  ne sont pas encore renseignés. Les tests d’acceptation sont à exécuter.
- L’exemple laisse donc volontairement du travail et des validations à traiter.
  Ce n’est pas encore une démonstration complète prête à dérouler.

Fichiers de référence :

- [Générateur](scripts/create_training_project.py).
- [Archive initiale](examples/portail-association.pm2).
- [Exercices actuels](examples/EXERCICES.md).
- [Guide utilisateur](docs/GUIDE_UTILISATEUR.md).

Un exemplaire a également été ajouté dans la base locale habituelle
`~/.local/share/pm2-desktop/project.db`. L’utilisateur peut avoir modifié cette copie
pendant son entraînement : utiliser une base dédiée pour préparer le nouveau cas.

## Backlog du projet de démonstration

1. Définir le fil de la démonstration : quels écrans montrer, dans quel ordre,
   quelles décisions faire prendre, et quelle histoire raconter autour du portail.
2. Compléter la gouvernance : personnes fictives, rôles, parties prenantes,
   responsabilités et décideurs des revues de passage.
3. Enrichir et vérifier WBS, dépendances, responsables, effort, coûts, avancement,
   exigences et livrables ; garder les dates et le budget cohérents avec le scénario.
4. Préparer des risques, problèmes, décisions et changements avec analyses,
   actions, échéances, impacts et traces permettant de montrer leurs workflows.
5. Renseigner les documents utiles avec un contenu spécifique au projet,
   sans textes génériques de remplissage ; prévoir revues, versions et exports.
6. Construire la recette : critères mesurables, tests, résultats réels fictifs,
   preuves, anomalies, corrections, acceptation et transfert au secrétariat.
7. Préparer bilan, leçons apprises et mesure des bénéfices ; distinguer les objectifs
   des résultats effectivement simulés à chaque moment du projet.
8. Réviser le guide de démonstration et vérifier le parcours dans l’application installée,
   de l’ouverture de l’archive à l’export et à la réouverture.

À décider au début de ce chantier : conserver un cas unique progressif ou fournir
plusieurs archives correspondant aux étapes du même projet. Distinguer clairement
le support d’entraînement, qui laisse des actions à réaliser, du cas de démonstration
préparé pour montrer des situations et des résultats.

Les transitions doivent passer par les services métier, les décisions de gate et les
preuves attendues. Vérifier que les éventuelles alertes restantes correspondent à l’étape
présentée et sont expliquées dans le guide.

## Repères techniques

Application Python/PySide6, SQLAlchemy et SQLite ; code dans `src/pm2`.
La méthodologie de chaque projet est figée dans son snapshot YAML avec empreinte SHA-256.
Utiliser les services applicatifs pour construire le cas et conserver cette cohérence.

Le générateur actuel ne met pas à jour un projet existant portant la même référence :
il retourne son identifiant. Pour tester une nouvelle version des données, générer dans
une nouvelle base dédiée. Le service d’archive copie la base entière : construire les
archives de démonstration depuis une base contenant seulement le cas fictif.

```bash
PYTHONPATH=src .venv/bin/python scripts/create_training_project.py \
  --database build/demo-colibris.db \
  --archive build/demo-colibris.pm2

QT_QPA_PLATFORM=offscreen PYTHONPATH=src .venv/bin/pytest
.venv/bin/ruff check src tests scripts
PYTHONPATH=src .venv/bin/mypy src/pm2/domain src/pm2/application src/pm2/methodology

.venv/bin/pyinstaller --noconfirm pm2-desktop.spec
PYTHONPATH=src .venv/bin/python scripts/package_deb.py
```

Dans cet espace de travail, les métadonnées Git se trouvent dans `.gitdata` plutôt
que `.git`. Utiliser par exemple `git --git-dir=.gitdata --work-tree=. status`.
Les fichiers `build/`, `dist/`, `*.db` et `*.pm2` sont ignorés ; l’archive fictive
`examples/portail-association.pm2` est néanmoins suivie explicitement dans le dépôt.

Les corrections et publications précédentes ont été autorisées par l’utilisateur.
