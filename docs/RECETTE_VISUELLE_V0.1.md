# Recette visuelle V0.1

Date : 9 septembre 2026

Résultat : **PASS**

Configuration : Linux x86_64, Qt hors écran, fenêtre 1500 × 950.

## Périmètre contrôlé

| Écran | Contrôle principal | Résultat |
|---|---|---|
| Dashboard | contexte projet, indicateurs et navigation | PASS |
| Lancement | assistant, complétude, champs et actions | PASS |
| Planification | sources, artefacts spécialisés et navigation | PASS |
| Plan de travail | WBS, commandes de structure, Gantt et dépendances | PASS |
| Catalogue | liste, actions CRUD, détail, relations, validation et audit | PASS |
| Exécution | livrables, critères, tests et décision d’acceptation | PASS |
| Registres | risques, problèmes, décisions et modifications | PASS |
| Documents | 21 artefacts, génération et historique des versions | PASS |
| Clôture | assistant, contrôles de fermeture et actions | PASS |

## Corrections issues de la recette

- réorganisation des commandes WBS pour éviter leur troncature ;
- amélioration de l’ordre des colonnes et de la densité du Catalogue ;
- raccourcissement des onglets du détail avec info-bulles explicites ;
- francisation des colonnes des registres ;
- correction du libellé « Besoins et livrables » ;
- redimensionnement de l’historique documentaire et de son empreinte SHA-256.

## Preuves

Les neuf captures et leur manifeste se trouvent dans `build/visual-qa-v0.1-final/`.
Aucun défaut visuel bloquant n’a été constaté après la passe finale.
