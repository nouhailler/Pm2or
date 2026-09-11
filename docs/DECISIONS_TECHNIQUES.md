# Décisions techniques V0.1

## ADR-001 — Base SQLite par projet ouvert

SQLite garantit un fonctionnement hors ligne, des transactions ACID et un format copiable. Les clés sont des UUID texte stables. Les archives `.pm2` copient une base cohérente après commit/checkpoint et la protègent avec SHA-256.

## ADR-002 — Configuration méthodologique validée

Le YAML contractuel reste la source de vérité. Pydantic valide strictement l'identité PM², l'ordre des phases et les structures consommées. Les extensions techniques tolèrent des champs supplémentaires afin de garder le contrat évolutif.

## ADR-003 — Workflow explicite dans la couche métier

Les graphes de transitions sont indépendants de Qt. Les gardes qui nécessitent les données persistées se trouvent dans les services applicatifs. L'UI se contente de présenter les cibles permises et les erreurs reçues.

## ADR-004 — Rendu documentaire déterministe et local

Les modèles Jinja2, python-docx et ReportLab ne chargent aucun actif distant. Le contenu métier est trié par code et accompagné de métadonnées/version/validation.

## ADR-005 — Suppression logique

Les entités métier possèdent `archived` et `deleted_at`; seule la relation enfant strictement dépendante peut être supprimée en cascade. Les liens critiques de traçabilité sont protégés par le service.
