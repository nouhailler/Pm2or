# PM² Desktop 0.1.3

## Navigation par tiroirs

La barre latérale regroupe les écrans dans cinq catégories repliables :

- **Vue d’ensemble** : Tableau de bord, Projet, Gouvernance.
- **Étapes du projet** : Lancement, Planification, Plan de travail, Exécution, Clôture, Passages de phase.
- **Pilotage** : Suivi & Contrôle, Registres, Traçabilité, Validation.
- **Données et documents** : Données du projet, Documents.
- **Outils avancés** : Catalogue des entités, Paramètres.

Cliquer sur le titre d’une catégorie ouvre ou ferme son tiroir sans changer d’écran. Au premier affichage, la vue d’ensemble est ouverte et les autres catégories sont repliées. Le tiroir d’une destination s’ouvre automatiquement lorsqu’on y accède depuis le parcours graphique ou un autre raccourci. Les catégories ouvertes sont conservées pendant la session lors d’un changement de projet.

Les noms « Dashboard », « Gates », « Données métier » et « Catalogue » deviennent respectivement « Tableau de bord », « Passages de phase », « Données du projet » et « Catalogue des entités ». Les données du projet et les workflows métier conservent leur fonctionnement.

## Installer et tester

Paquet **Debian 13 amd64** (glibc 2.41 ou ultérieure).

```bash
sudo apt install ./pm2-desktop_0.1.3_amd64.deb
pm2-desktop
```

1. Ouvrez un projet et cliquez sur **Étapes du projet** pour voir ses écrans.
2. Sélectionnez **Plan de travail**, puis repliez le tiroir : le contenu reste affiché.
3. Depuis **Vue d’ensemble → Tableau de bord**, cliquez sur une phase du parcours graphique : l’assistant s’ouvre et le tiroir **Étapes du projet** se déplie.
4. Ouvrez **Outils avancés → Catalogue des entités** : une seule entrée du menu est sélectionnée.

Le projet fictif `portail-association.pm2` et son guide `EXERCICES.md` restent disponibles dans la release.

## Vérification

59 tests automatisés, Ruff et mypy. Vérification visuelle de la navigation repliée et ouverte. Contrôle du paquet Debian extrait, démarrage sans interface et démarrage Qt hors écran avec le projet d’entraînement.

```bash
sha256sum -c SHA256SUMS-0.1.3
```
