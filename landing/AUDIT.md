# Audit des fonctionnalités (PM² Desktop 0.1.8)

Base de vérification du contenu du site, établie le 2 novembre 2026 sur le commit `1477881` (tag `v0.1.8`). Ne rien publier sur le site qui ne figure pas ici.

## Vérifications réalisées

| Élément | Résultat |
| :--- | :--- |
| Tests de l'application | 158 réussis, couverture 82,59 % (le README annonce 82,70 %) |
| Ruff et mypy | aucune erreur |
| Paquet `.deb` de la release | SHA-256 conforme ; bundle extrait, `--headless-check` et `--diagnostics` réussis, sans interface graphique |
| Installation `apt` du paquet | **non testée** |
| Écrans | application lancée en rendu `offscreen` et capturée sur une base éphémère |

## Fonctionnalités confirmées

| Fonction | Preuve |
| :--- | :--- |
| Tableau de bord, santé, prochaines actions | `ui/pages.py`, `application/dashboard_metrics.py`, capture |
| Parcours graphique des phases | `ui/project_workflow.py`, capture |
| Assistants des 4 phases | `ui/wizards.py`, capture |
| Revues RfP, RfE, RfC et blocage | `application/gates.py`, `ui/gates_page.py`, YAML `gates` |
| Rôles, parties prenantes, RCmSCI | `application/governance.py`, `ui/governance_page.py` |
| WBS, jalons, Gantt simple, dépendances FS/SS/FF/SF | `ui/work_plan_page.py`, `application/planning.py`, capture |
| Chemin critique (CPM) | `application/planning.py`, capture |
| Ressources, capacité, surcharge | `application/resources.py`, `ui/resources_page.py` |
| Exigences, livrables, critères, tests, acceptation | `application/acceptance_services.py`, `ui/acceptance.py` |
| Registres et workflows | `application/registers.py`, `domain/workflows.py`, capture |
| Traçabilité et objets orphelins | `application/traceability.py`, capture de l'onglet orphelins |
| Conformité PM² | `application/validation.py`, `ui/validation_page.py`, capture |
| Baselines | `application/baselines.py`, `docs/BASELINES_IMMUABLES.md` |
| Journal d'audit, export JSON | `application/audit.py`, `ui/audit_trail_page.py`, capture |
| 21 artefacts, exports MD/HTML/DOCX/PDF | YAML `artifacts` (21), `application/documents.py`, capture |
| Pièces jointes 25 Mio, SHA-256 | `application/attachments.py` |
| Archive `.pm2` et contrôle d'intégrité | `infrastructure/archive.py` |
| Glossaire (68 notions à l'écran), 12 fiches | `application/knowledge_base.py`, capture |
| Guide de démarrage, infobulles | `ui/system_experience.py`, `ui/tooltips.py` |
| Projet Les Colibris et exercices | `examples/`, `scripts/create_training_project.py` |

## Local, réseau et confidentialité

| Point | Constat | Preuve |
| :--- | :--- | :--- |
| Stockage | SQLite dans `~/.local/share/pm2-desktop`, ou `PM2_DATA_DIR` | `config.py` |
| Réseau | seul `application/updates.py` ouvre des connexions, vers GitHub | recherche `urllib`, `requests`, `socket`, `QNetwork` dans `src/` |
| Mises à jour | **vérification activée par défaut**, 30 s après le lancement puis toutes les 6 h ; désactivable | `system_settings.py`, `system_experience.py` |
| Installation automatique | désactivée par défaut, SHA-256 exigé | `system_settings.py`, `updates.py` |
| Compte | aucun ; l'audit utilise le nom d'utilisateur système | `application/audit.py` |
| Chiffrement | aucun : pas de `encrypt`, `cipher` ni `sqlcipher` dans `src/` | recherche dans le code |
| Collaboration | non-objectif : pas de cloud, serveur ni temps réel | `01_ARCHITECTURE.md` §8 |
| Archive | copie **toute la base SQLite**, pas seulement le projet exporté | `infrastructure/archive.py`, `CONTEXT.md` |
| Diagnostic | fichier local anonymisé, jamais envoyé | `application/diagnostics.py` |

## Publication

Release `v0.1.8` : `pm2-desktop_0.1.8_amd64.deb` (109 Mo), `SHA256SUMS-0.1.8`, `pm2-desktop-0.1.8-sbom.cdx.json`. Aucun binaire Windows, macOS, Android ou iOS. Licence : EUPL-1.2. Les ressources du dépôt (`portail-association.pm2`, `EXERCICES.md`) ne sont pas jointes à cette release mais restent dans `examples/`.

## Exclu du site

- Personnalisation, thèmes, autres langues : rien dans le code.
- Graphe de traçabilité présenté comme point fort : voir ci-dessous.

## Anomalies de l'application constatées, non corrigées ici

1. **Graphe de traçabilité illisible** : les libellés des nœuds s'empilent en haut à gauche et les rectangles restent vides. Les rectangles sont créés avec `scene.addRect(x, y, …)`, leur position d'élément reste donc (0, 0) et le texte enfant placé en (7, 5) ne les suit pas (`ui/traceability_page.py`, autour de la ligne 347). Constaté en rendu `offscreen`. **Corrigé dans le code source, non publié** : la version 0.1.8 reste affectée, et le site n'illustre pas le graphe tant qu'une version corrigée n'est pas sortie.
2. **Archive et confidentialité** : exporter un projet embarque les autres projets de la même base. Risque de divulgation en cas de partage.
3. **Libellés non traduits** : `LAUNCH`, `Issues`, `Changes`, `DRAFT` restent visibles dans l'interface.
