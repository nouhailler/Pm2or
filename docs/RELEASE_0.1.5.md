# PM² Desktop 0.1.5

## Fiches détaillées pour tous les tableaux

Toutes les lignes de tableaux peuvent maintenant être activées par double-clic ou avec la
touche **Entrée**. Une fenêtre affiche les noms de colonnes et leurs valeurs complètes, y compris
quand elles sont tronquées dans la vue principale.

Le catalogue **Documents & artefacts** bénéficie d’une fiche spécialisée présentant :

- le titre et le code du document ;
- sa phase PM², son statut et son caractère obligatoire ;
- son objectif méthodologique ;
- son contenu complet rendu dans une fenêtre lisible.

Les tableaux créés dynamiquement reçoivent automatiquement le même comportement, tandis que
les vues disposant d’un détail métier spécialisé conservent leur propre présentation.

## Exemple Les Colibris enrichi

L’archive `portail-association.pm2` contient désormais les 21 artefacts PM² avec 178 champs
illustratifs renseignés. Chaque document explique son rôle dans le projet de portail de
réservation et permet de découvrir concrètement la documentation PM².

## Installer et vérifier

Paquet **Debian 13 amd64** (glibc 2.41 ou ultérieure).

```bash
sudo apt install ./pm2-desktop_0.1.5_amd64.deb
pm2-desktop
sha256sum -c SHA256SUMS-0.1.5
```

## Validation

67 tests automatisés, Ruff et mypy. Le paquet Debian est inspecté après extraction et son
exécutable fait l’objet d’un contrôle sans interface.
