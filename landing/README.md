# Site de présentation de PM² Desktop

Site statique, responsive et installable (PWA) qui présente [PM² Desktop](https://github.com/nouhailler/Pm2or). Il est indépendant de l'application de bureau : il n'en modifie ni le code, ni le paquet, et la PWA ne transforme pas PM² Desktop en application Web.

## Technologies

HTML, CSS et JavaScript sans framework. Une seule page avec peu d'interactions ne justifie pas React ni Vite, et le site n'a aucune dépendance à l'exécution.

- `scripts/build.mjs` : build en Node seul (empreintes de fichiers, sprite d'icônes, galerie, précache).
- `playwright`, `axe-core`, `html-validate` : uniquement pour les tests.
- Polices Bricolage Grotesque et Source Sans 3 (licence OFL), icônes Lucide (ISC), tout est servi par le site.

## Prérequis

Node.js 20 ou ultérieur. Pour les tests navigateur, un Chromium (`npx playwright install chromium`, ou `CHROMIUM_PATH=/usr/bin/chromium`).

## Commandes

À lancer dans `landing/` :

```bash
npm install
```

```bash
npm run dev
```

Reconstruit à chaque modification et sert le site sur <http://localhost:4391/> (port réglable avec `PORT`).

```bash
npm run build
```

Produit le site dans `landing/dist/`. Cette commande n'a besoin d'aucune dépendance installée.

```bash
npm run preview
```

```bash
npm test
```

Enchaîne le build, la validation HTML, les contrôles statiques (`tests/static.test.mjs`) et les tests navigateur (`tests/browser.test.mjs`) : largeurs de 320 à 1920 px, axe-core, clavier, sans JavaScript, hors ligne, mise à jour du service worker. Ces tests appliquent la politique CSP de production.

Le service worker ne s'active qu'en HTTPS ou sur `localhost`. En développement, s'il sert une ancienne version, désinscrivez-le dans les outils du navigateur.

## Déploiement sur Cloudflare Pages

Cloudflare Pages convient : le site est entièrement statique, et `_headers` y est pris en charge. Rien n'est déployé automatiquement.

1. Dans Cloudflare : **Workers & Pages → Create → Pages → Connect to Git**, puis choisir `nouhailler/Pm2or`.
2. Renseigner :
   - **Production branch** : `main`
   - **Root directory** : `landing`
   - **Build command** : `npm run build`
   - **Build output directory** : `dist`
3. Variable facultative : `SITE_URL=https://votre-domaine` (sans `/` final). Une fois le domaine connu, elle ajoute la balise canonique, `og:url`, une adresse absolue pour l'image de partage (attendue par de nombreux réseaux sociaux), `sitemap.xml` et sa mention dans `robots.txt`. Sans elle, le site fonctionne mais ces éléments sont absents ou relatifs.
4. Lancer le déploiement, puis vérifier le site sur le domaine obtenu.

Déploiement manuel, après `npm run build`, avec un compte Cloudflare authentifié :

```bash
npx wrangler pages deploy dist --project-name pm2-desktop
```

Fichiers concernés : `public/_headers` (CSP, cache immuable des fichiers à empreinte). Aucune redirection n'est nécessaire : Cloudflare sert `404.html` pour les adresses inconnues et retire lui-même l'extension `.html` (`/offline.html` → `/offline`). C'est pourquoi le service worker précache `/offline`.

### PWA et cache

La PWA sert à reconsulter la présentation, la FAQ et les instructions d'installation sans connexion. Le nom court « PM² Site » et le texte du bouton d'installation évitent de la confondre avec l'application.

- Accueil : réseau d'abord, copie en cache si hors ligne. Autres adresses : page `offline.html`.
- Fichiers de `/assets/` et `/icons/` : cache d'abord (noms à empreinte), 40 fichiers au plus dans le cache d'exécution.
- Les autres origines, dont GitHub et les paquets, ne passent jamais par le service worker.
- Chaque build change la version du cache. Le visiteur voit « Recharger », et les anciens caches sont supprimés à l'activation.

## Mettre à jour le contenu

**Nouvelle release** : modifier `site.config.mjs` (`VERSION`, `RELEASE_DATE`, `DEB_SIZE`), relire la section Téléchargement et la FAQ, puis lancer `npm test`, qui compare `VERSION` à `../pyproject.toml`. Les boutons pointent vers la page des releases : ils n'ont pas à changer.

**Nouvelle fonctionnalité** : l'ajouter à `src/index.html` seulement après vérification dans le code, et compléter [AUDIT.md](AUDIT.md).

**Captures** : elles viennent de la vraie application, sur une base éphémère et le projet fictif Les Colibris. Depuis la racine du dépôt, après `uv sync --frozen --extra dev` :

```bash
QT_QPA_PLATFORM=offscreen PM2_DISABLE_UPDATE_CHECK=1 PYTHONPATH=src .venv/bin/python landing/scripts/capture_screens.py --output build/landing-captures
```

```bash
landing/scripts/optimize-images.sh build/landing-captures
```

Le second script requiert `cwebp`. La galerie se règle dans `site.config.mjs`. `npm run og-image` régénère l'image de partage.

**Icônes** : dérivées de `src/pm2/assets/pm2-desktop-logo.png`, dans `public/icons/`.

## Liens officiels

- Dépôt : <https://github.com/nouhailler/Pm2or>
- Téléchargements : <https://github.com/nouhailler/Pm2or/releases>
- Tickets : <https://github.com/nouhailler/Pm2or/issues>

## Limites connues

- Seul un paquet Debian 13 amd64 est publié : le site ne peut rien proposer d'autre.
- La canonique et le sitemap attendent le domaine définitif (`SITE_URL`).
- Le graphe de traçabilité n'est pas illustré : ses libellés s'affichent empilés en haut à gauche dans la version 0.1.8 publiée. La correction est dans le code source, pas encore dans une release (voir [AUDIT.md](AUDIT.md)). Ajouter une capture une fois la version corrigée publiée.
- Les captures sont produites avec le rendu Qt `offscreen` : les polices peuvent différer légèrement d'un poste réel.
- `Installer ce site` dépend du navigateur (l'événement `beforeinstallprompt` n'existe pas partout, notamment sur Safari et Firefox).
- Le mode sombre n'est pas proposé : la direction artistique demande un fond clair.
