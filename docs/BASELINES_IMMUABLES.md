# Baselines immuables

Une baseline est une photographie canonique et append-only de l’état d’un projet. Elle couvre le projet et son budget, le Work Plan et les jalons, les exigences, les livrables, les risques, les documents et les données des artefacts PM².

Chaque baseline possède une référence monotone (`B-001`, `B-002`, …), un nom, un type, son créateur, ses informations d’approbation, un snapshot JSON et son empreinte SHA-256.

## Garanties

- le snapshot est figé dès la création ;
- toute lecture recalcule et vérifie son empreinte ;
- une baseline ne peut être ni modifiée ni supprimée ;
- l’approbation peut uniquement compléter une baseline non encore approuvée, une seule fois ;
- des triggers SQLite protègent ces règles même en dehors des services applicatifs ;
- chaque création et approbation est inscrite dans l’audit.

L’état opérationnel du projet reste modifiable. La comparaison aplatit le snapshot et l’état courant pour présenter les valeurs ajoutées, retirées et modifiées. Une évolution approuvée se matérialise par une nouvelle baseline ; elle ne remplace jamais une référence historique.
