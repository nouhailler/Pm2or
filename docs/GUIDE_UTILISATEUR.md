# Guide utilisateur — PM² Desktop V0.1

## Premier lancement

L'écran d'accueil propose de créer un projet ou d'ouvrir une archive `.pm2`. Pour créer un projet, saisissez au minimum son nom et sa référence. Le Chef de Projet (PM), le Porteur du Projet (PO), le budget et les dates peuvent être renseignés dans le même formulaire. La méthodologie est fixée à PM² v3.1 en français.

L'application enregistre automatiquement les données dans la base locale à la validation de chaque action. La barre inférieure indique le projet actif, sa phase et le nombre d'erreurs/avertissements.

## Navigation et cycle de vie

La barre latérale donne accès au Dashboard, au projet, à la gouvernance, aux quatre assistants de phase, au plan de travail, aux objets métier, au catalogue complet, aux gates, registres, documents et validations. Le panneau de droite rappelle en permanence le contexte actif.

Chaque assistant Lancement, Planification, Exécution ou Clôture regroupe les artefacts de sa phase, affiche leur complétude et la synthèse des validations, et fournit des accès directs aux données sources. Les assistants concernés intègrent également le gate, l'exécution des tests d'acceptation, l'acceptation finale ou la fermeture administrative.

Le passage d'une phase à la suivante se fait dans **Gates** :

1. ouvrez RfP, RfE ou RfC selon la phase courante ;
2. contrôlez chaque élément de la checklist et joignez mentalement/structurellement les preuves correspondantes ;
3. choisissez `APPROVED`, `REJECTED` ou `APPROVED_WITH_RESERVES` et indiquez le décideur ;
4. une approbation fait avancer le projet et écrit un événement d'audit.

Un élément obligatoire non satisfait bloque l'approbation avec un message explicite.

## Gouvernance et RCmSCI

Dans **Gouvernance**, ajoutez les membres de l'équipe et choisissez leur rôle PM². L'application bloque un second PM actif. L'onglet Parties prenantes conserve intérêt, influence et stratégie d'engagement. La matrice RCmSCI initiale est chargée depuis la méthodologie ; le bouton d'affectation permet d'ajouter des responsabilités projet. Un sujet ne peut avoir qu'un `R` et un `Cm`, tandis que `S`, `C` et `I` sont multiples.

## Plan de travail

Dans **Plan de travail**, créez un lot, une tâche ou un jalon. Sélectionner un élément avant la création le désigne comme parent. Les tâches enregistrent dates, effort, coût et progression ; les jalons utilisent une date unique. Les commandes permettent de renommer, monter, descendre, indenter, désindenter et archiver les éléments.

Les dépendances peuvent être ajoutées ou retirées dans la même vue. Elles sont contrôlées par le service de planification, qui interdit l'auto-dépendance, les liens entre projets et les cycles.

## Besoins, livrables et acceptation

La page **Données métier** permet de créer :

- exigences avec source, priorité et méthode de vérification ;
- livrables avec responsable et état d'acceptation ;
- critères et tests d'acceptation ;
- contrôles qualité ;
- activités de transition et mise en œuvre ;
- réunions.

Utilisez **Traçabilité** pour relier exigences, tâches, livrables, tests, décisions et documents. Les relations sont typées et les liens critiques ne peuvent pas être supprimés.

Dans l'assistant d'Exécution ou de Clôture, l'onglet **Acceptation finale** permet d'enregistrer le verdict et la preuve de chaque test. Une acceptation finale est refusée tant que chaque critère applicable ne dispose pas d'un test exécuté avec succès.

## Registres et workflows

Les quatre onglets de **Registres** permettent recherche, filtrage, création et transition :

- Risque : `OPEN → ASSESSED → RESPONSE_PLANNED → MONITORED → CLOSED` ;
- Problème : `OPEN → ANALYSIS → ACTION_PLANNED → IN_PROGRESS → RESOLVED → CLOSED` ;
- Décision : `OPEN → ANALYSIS → DECIDED → COMMUNICATED → CLOSED` ;
- Modification : `DRAFT → SUBMITTED → IMPACT_ANALYSIS → APPROVAL → APPROVED/REJECTED → IMPLEMENTING → VERIFIED → CLOSED`.

Une modification ne peut entrer en implémentation sans approbation formelle. Un problème ne peut être clôturé sans résolution.

Le bouton **Fiche détaillée** ouvre les données, relations, validations et événements d'audit de la ligne. Le **Catalogue** offre la même vue pour les 47 entités contractuelles, avec création, modification, archivage et restauration lorsque l'entité le permet. Les changements de statut restent exclusivement pilotés par les workflows métier.

## Validation

Le Dashboard montre les actions requises. La page **Validation** filtre les règles par `ERROR`, `WARNING` ou `INFO`. Les erreurs bloquent les gates concernés, mais n'empêchent pas un export ordinaire ; le rapport d'export les mentionne.

## Documents et archives

Dans **Documents**, sélectionnez l'un des 21 artefacts spécialisés et un format : Markdown, HTML, DOCX ou PDF. Les contenus sont régénérés depuis les données structurées de leur assistant et les registres courants. L'aperçu HTML, le dossier d'export et l'historique des versions sont accessibles depuis cette page.

**Exporter le projet .pm2** produit une archive ZIP spécialisée contenant :

- `project.db` ;
- `manifest.json` avec version, projet, méthodologie, date et empreinte ;
- `documents/`, `attachments/` et `exports/` ;
- les rapports d'export et de validation lors d'un export complet.

À l'ouverture, l'empreinte est contrôlée avant toute écriture. Une archive corrompue affiche une erreur et la copie locale existante reste intacte.
