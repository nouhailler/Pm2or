# PM² Desktop 0.1.2

## Nouveautés et corrections

- **Parcours graphique dans Dashboard** : les quatre phases, les revues RfP/RfE/RfC et la position réelle du projet. Les phases sont cliquables et le bouton « Continuer l’étape actuelle » ouvre l’assistant courant. La position suit les décisions de passage et la clôture finale.
- Repères de l’étape issus de la méthodologie figée du projet, et raccourcis vers les registres, le planning et les contrôles. Le parcours se réorganise sur petit écran ; le tableau de bord peut défiler verticalement.
- La revue **RfC** est affichée dans l’assistant d’exécution, avant la clôture, conformément à la configuration méthodologique.
- Correction du démarrage du binaire : le YAML embarqué porte désormais le nom attendu par le chargeur, comme dans le paquet Python.
- Projet fictif **Les Colibris** : dix tâches, quatre livrables et leurs tests d’acceptation, cinq exigences, trois risques et des exemples de problème, décision et changement. Une archive initiale et un parcours d’exercices sont fournis.

## Installation et test en live

Paquet **Debian 13 amd64** (glibc 2.41 ou ultérieure).

```bash
sudo apt install ./pm2-desktop_0.1.2_amd64.deb
pm2-desktop
```

Ouvrez un projet et sélectionnez **Dashboard → Votre parcours PM²**. Cliquez sur une phase : son assistant s’ouvre, sans changer la phase réelle. Utilisez « Continuer l’étape actuelle » pour reprendre le travail. Après une décision de passage, revenez au tableau de bord : le marqueur suit la phase du projet. **Affichage → Actualiser** permet aussi de rafraîchir les données.

Pour le cas d’entraînement, téléchargez `portail-association.pm2` et `EXERCICES.md` depuis cette release. Dans l’application, utilisez **Fichier → Ouvrir un projet…** et sélectionnez l’archive. Toutes les personnes et données de ce cas sont fictives.

## Vérification

57 tests automatisés, Ruff et mypy ; vérification visuelle du tableau de bord à 1440 et 1050 pixels de largeur. Le paquet Debian est extrait puis testé hors du dépôt, avec le contrôle sans interface et le démarrage Qt hors écran.

```bash
sha256sum -c SHA256SUMS-0.1.2
```

## Construction

```bash
./scripts/build.sh
PYTHONPATH=src .venv/bin/python scripts/package_deb.py
```
