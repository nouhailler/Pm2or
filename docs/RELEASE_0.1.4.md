# PM² Desktop 0.1.4

## Aide contextuelle dans toute l’application

Cette version facilite la découverte de l’interface grâce à des infobulles cohérentes sur les
menus, boutons, onglets, champs de formulaire, listes et tableaux.

- Les principales commandes disposent d’une explication métier précise.
- Les formulaires décrivent la donnée attendue à partir du libellé de chaque champ.
- Les onglets expliquent le contenu qu’ils affichent.
- Les pages et fenêtres créées après le démarrage reçoivent automatiquement la même aide.
- Les infobulles spécifiques déjà présentes sont conservées en priorité.
- Les descriptions sont également exposées aux technologies d’assistance.

## Installer et vérifier

Paquet **Debian 13 amd64** (glibc 2.41 ou ultérieure).

```bash
sudo apt install ./pm2-desktop_0.1.4_amd64.deb
pm2-desktop
```

Placez `SHA256SUMS-0.1.4` à côté du paquet, puis vérifiez son intégrité :

```bash
sha256sum -c SHA256SUMS-0.1.4
```

Le projet fictif `portail-association.pm2` et son guide `EXERCICES.md` restent disponibles
parmi les ressources de la release.

## Validation

62 tests automatisés, Ruff et mypy. Le paquet Debian est inspecté après extraction et son
exécutable fait l’objet d’un contrôle sans interface.
