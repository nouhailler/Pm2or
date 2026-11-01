"""Contenu pédagogique hors ligne sur la gestion de projet."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GlossaryEntry:
    term: str
    category: str
    definition: str
    aliases: tuple[str, ...] = ()
    related: tuple[str, ...] = ()

    @property
    def searchable_text(self) -> str:
        return " ".join((self.term, self.category, self.definition, *self.aliases)).casefold()


@dataclass(frozen=True, slots=True)
class MethodologyArticle:
    name: str
    family: str
    origin: str
    summary: str
    principles: tuple[str, ...]
    lifecycle: str
    suitable_for: str
    strengths: tuple[str, ...]
    cautions: tuple[str, ...]
    evolution: str
    source_url: str

    @property
    def searchable_text(self) -> str:
        return " ".join(
            (
                self.name,
                self.family,
                self.origin,
                self.summary,
                *self.principles,
                self.lifecycle,
                self.suitable_for,
                *self.strengths,
                *self.cautions,
                self.evolution,
            )
        ).casefold()


@dataclass(frozen=True, slots=True)
class TimelineEvent:
    year: str
    title: str
    description: str
    source_url: str = ""


def _g(
    term: str,
    category: str,
    definition: str,
    aliases: tuple[str, ...] = (),
    related: tuple[str, ...] = (),
) -> GlossaryEntry:
    return GlossaryEntry(term, category, definition, aliases, related)


GLOSSARY = tuple(
    sorted(
        (
            _g("Acceptation", "Qualité", "Décision formelle confirmant qu'un livrable satisfait les critères convenus.", related=("Critère d'acceptation", "Validation")),
            _g("Agile", "Approches", "Famille de valeurs et de principes favorisant la livraison fréquente, la collaboration et l'adaptation au changement."),
            _g("Backlog", "Agile", "Liste ordonnée et évolutive du travail envisagé pour un produit, une équipe ou une itération."),
            _g("Baseline", "Pilotage", "Photographie approuvée et immuable d'un périmètre, d'un planning ou d'un budget servant de référence aux écarts.", aliases=("Référence approuvée",)),
            _g("Bénéfice", "Stratégie", "Amélioration mesurable rendue possible par les résultats du projet et perçue comme positive par les parties prenantes."),
            _g("Budget", "Coûts", "Enveloppe financière autorisée, ventilée et suivie pour réaliser le projet."),
            _g("Burndown chart", "Agile", "Graphique montrant la quantité de travail restante au fil d'une itération ou d'une release.", aliases=("Graphique d'avancement",)),
            _g("Business case", "Cadrage", "Justification documentée du projet : problème, options, coûts, bénéfices, risques et viabilité.", aliases=("Étude d'opportunité",)),
            _g("Capacité", "Ressources", "Quantité de travail qu'une ressource ou une équipe peut fournir pendant une période donnée."),
            _g("Chemin critique", "Planification", "Chaîne de tâches dont la marge totale est nulle ou minimale et qui détermine la durée du projet.", aliases=("Critical path",), related=("Marge totale", "Dépendance")),
            _g("Contrainte", "Cadrage", "Limite imposée au projet, par exemple une date, un budget, une technologie ou une réglementation."),
            _g("Coût réel (AC)", "Valeur acquise", "Dépense effectivement engagée pour le travail réalisé à une date donnée.", aliases=("Actual Cost", "AC")),
            _g("CPI", "Valeur acquise", "Indice de performance des coûts : valeur acquise divisée par coût réel. Sous 1, le projet dépense plus que la valeur produite."),
            _g("Critère d'acceptation", "Qualité", "Condition observable et testable qu'un livrable doit satisfaire pour être accepté."),
            _g("Demande de changement", "Changements", "Proposition formelle de modifier un élément approuvé, analysée selon ses impacts avant décision.", aliases=("Change request",)),
            _g("Dépendance", "Planification", "Relation logique entre deux activités, par exemple fin-début (FS), début-début (SS), fin-fin (FF) ou début-fin (SF)."),
            _g("Definition of Done", "Agile", "Description partagée de l'état de qualité requis pour considérer un incrément comme terminé.", aliases=("DoD", "Définition de terminé")),
            _g("Dérive", "Pilotage", "Écart défavorable qui s'accumule par rapport à la référence approuvée de coût, délai ou périmètre."),
            _g("Effort", "Ressources", "Quantité de travail humain nécessaire, exprimée par exemple en heures ou jours-personnes ; différente de la durée calendaire."),
            _g("Enjeu", "Cadrage", "Conséquence importante ou valeur à protéger qui explique pourquoi le projet mérite une attention particulière."),
            _g("Épopée", "Agile", "Grand besoin utilisateur destiné à être décomposé en fonctionnalités ou histoires plus petites.", aliases=("Epic",)),
            _g("Exigence", "Périmètre", "Besoin ou condition documentée qu'une solution, un livrable ou un processus doit satisfaire.", aliases=("Requirement",)),
            _g("Gate", "Gouvernance", "Point de décision formel entre deux étapes, fondé sur des preuves et critères de readiness.", aliases=("Revue de passage", "Phase gate")),
            _g("Gouvernance", "Gouvernance", "Cadre de décision, de responsabilité, d'escalade et de contrôle qui dirige le projet."),
            _g("Hybride", "Approches", "Combinaison intentionnelle d'éléments prédictifs et adaptatifs adaptée au contexte du projet."),
            _g("Hypothèse", "Cadrage", "Élément tenu pour vrai à des fins de planification, mais qui doit être surveillé car il reste incertain.", aliases=("Assumption",)),
            _g("Incrément", "Agile", "Version intégrée et utilisable du produit qui ajoute de la valeur aux incréments précédents."),
            _g("Issue", "Registres", "Événement ou problème déjà survenu qui exige une action, contrairement au risque encore incertain.", aliases=("Problème",)),
            _g("Itération", "Agile", "Cycle court et répété produisant un résultat examiné avant de planifier la suite."),
            _g("Jalon", "Planification", "Événement significatif de durée nulle marquant une décision, une livraison ou une échéance.", aliases=("Milestone",)),
            _g("Kanban", "Flux", "Système visuel de pilotage du flux qui limite le travail en cours et favorise l'amélioration évolutive."),
            _g("Lag", "Planification", "Délai d'attente ajouté entre deux tâches liées ; un lag positif retarde la tâche successeure.", aliases=("Décalage positif",)),
            _g("Lead", "Planification", "Chevauchement autorisé entre deux tâches liées ; souvent représenté par un décalage négatif.", aliases=("Avance",)),
            _g("Leçon apprise", "Amélioration", "Connaissance tirée d'une expérience, formulée pour être réutilisable dans le projet ou l'organisation."),
            _g("Livrable", "Périmètre", "Résultat identifiable et vérifiable produit par le projet, intermédiaire ou final.", aliases=("Deliverable",)),
            _g("Lot de travaux", "Planification", "Composant de la WBS suffisamment défini pour être estimé, affecté, exécuté et contrôlé.", aliases=("Work package",)),
            _g("Marge totale", "Planification", "Retard maximal d'une tâche sans décaler la date de fin calculée du projet.", aliases=("Total float",)),
            _g("Matrice RACI", "Gouvernance", "Tableau précisant qui réalise, approuve, est consulté et est informé pour chaque activité ou livrable."),
            _g("Matrice RCmSCI", "Gouvernance", "Extension PM² des responsabilités : Responsible, Accountable, Supports, Consulted et Informed."),
            _g("MVP", "Produit", "Version minimale permettant de tester une hypothèse de valeur avec de vrais utilisateurs.", aliases=("Minimum Viable Product", "Produit minimum viable")),
            _g("Objectif", "Cadrage", "Résultat spécifique recherché ; un bon objectif est compréhensible, mesurable et relié à la stratégie."),
            _g("Partie prenante", "Gouvernance", "Personne, groupe ou organisation pouvant affecter le projet, être affecté par lui ou se percevoir comme tel.", aliases=("Stakeholder",)),
            _g("Périmètre", "Périmètre", "Ensemble des résultats et du travail inclus dans le projet, avec ses exclusions explicites.", aliases=("Scope",)),
            _g("Phase", "Cycle de vie", "Partie cohérente du cycle de vie regroupant des activités et décisions orientées vers un objectif."),
            _g("Plan de management", "Gouvernance", "Document expliquant comment une dimension du projet sera planifiée, exécutée, surveillée et maîtrisée."),
            _g("PMO", "Organisation", "Fonction qui soutient, standardise ou gouverne la gestion de projets, programmes et portefeuilles.", aliases=("Project Management Office",)),
            _g("Portefeuille", "Stratégie", "Ensemble piloté de projets, programmes et activités regroupés pour atteindre des objectifs stratégiques."),
            _g("Product Owner", "Scrum", "Responsabilité Scrum chargée de maximiser la valeur du produit et de gérer efficacement le Product Backlog."),
            _g("Programme", "Stratégie", "Groupe coordonné de projets et activités connexes géré pour obtenir des bénéfices impossibles à produire séparément."),
            _g("Projet", "Fondamentaux", "Entreprise temporaire menée pour créer un produit, service, résultat ou changement unique."),
            _g("Qualité", "Qualité", "Degré auquel un ensemble de caractéristiques satisfait les exigences et l'usage attendu."),
            _g("Registre", "Pilotage", "Liste structurée et tenue à jour d'objets de pilotage comme les risques, issues, décisions ou changements."),
            _g("Release", "Produit", "Version cohérente d'un produit rendue disponible à des utilisateurs ou à un environnement cible."),
            _g("Rétrospective", "Agile", "Moment régulier où l'équipe inspecte sa façon de travailler et choisit des améliorations concrètes."),
            _g("Risque", "Registres", "Événement ou condition incertaine qui, s'il survient, produit un effet positif ou négatif sur les objectifs."),
            _g("Roadmap", "Produit", "Représentation orientée résultats de la direction et des étapes envisagées pour un produit ou une transformation."),
            _g("Scrum Master", "Scrum", "Responsabilité Scrum qui aide l'équipe et l'organisation à comprendre et appliquer Scrum efficacement."),
            _g("SPI", "Valeur acquise", "Indice de performance des délais : valeur acquise divisée par valeur planifiée. Sous 1, l'avancement est inférieur au plan."),
            _g("Sponsor", "Gouvernance", "Dirigeant qui porte la justification du projet, sécurise les moyens et répond des décisions majeures."),
            _g("Sprint", "Scrum", "Événement Scrum de durée fixe, d'un mois au maximum, dans lequel des idées sont transformées en valeur."),
            _g("Tailoring", "Approches", "Adaptation raisonnée d'une méthode, de ses rôles et artefacts au contexte sans perdre ses contrôles essentiels.", aliases=("Personnalisation",)),
            _g("Valeur acquise (EV)", "Valeur acquise", "Valeur budgétée du travail effectivement réalisé à une date donnée.", aliases=("Earned Value", "EV")),
            _g("Valeur planifiée (PV)", "Valeur acquise", "Valeur budgétée du travail qui devait être réalisé à une date donnée.", aliases=("Planned Value", "PV")),
            _g("Validation", "Qualité", "Confirmation que le résultat répond au besoin et à l'usage prévu : construit-on le bon produit ?"),
            _g("Vélocité", "Agile", "Mesure empirique de la quantité de travail terminée par une équipe au cours d'une itération ; elle ne compare pas les équipes."),
            _g("Vérification", "Qualité", "Confirmation que le résultat respecte ses spécifications : construit-on correctement le produit ?"),
            _g("WBS", "Planification", "Décomposition hiérarchique orientée livrables de tout le périmètre du projet.", aliases=("Work Breakdown Structure", "Structure de découpage du projet")),
            _g("WIP", "Flux", "Nombre d'éléments commencés mais non terminés ; le limiter réduit les files d'attente et révèle les blocages.", aliases=("Work in Progress", "Travail en cours")),
        ),
        key=lambda entry: entry.term.casefold(),
    )
)


METHODOLOGIES = (
    MethodologyArticle(
        "PM²", "Gouvernance structurée et adaptable", "Commission européenne, développée en 2007 et publiée en interne en 2008.",
        "Méthodologie ouverte reliant gouvernance, cycle de vie, activités, artefacts et mindsets. Elle vise la livraison de solutions et de bénéfices avec des responsabilités explicites.",
        ("gouvernance claire", "quatre phases et monitor & control transversal", "artefacts proportionnés", "mindsets et adaptation au contexte"),
        "Lancement → Planification → Exécution → Clôture, avec suivi et contrôle continus et revues de passage.",
        "Organisations publiques ou privées recherchant un cadre complet, pragmatique et documenté, notamment dans l'écosystème européen.",
        ("ouverte et accessible", "rôles et décisions explicites", "modèles d'artefacts", "compatible avec des pratiques agiles"),
        ("doit être adaptée pour éviter la bureaucratie", "la gouvernance exige des décideurs réellement disponibles"),
        "Ouverte à tous depuis 2018 ; guide 3.1 en 2023 ; extension progressive vers PM²-Agile, programmes et portefeuilles.",
        "https://pm2.europa.eu/pm2-methodologies/pm2-project-management_en",
    ),
    MethodologyArticle(
        "PMBOK® / Standard PMI", "Corpus de connaissances et standard", "Project Management Institute, fondé en 1969 ; travaux de standardisation engagés dans les années 1970-1980.",
        "Référentiel global de principes, domaines et pratiques. Le PMBOK n'est pas une recette de cycle de vie : il aide à sélectionner et adapter les pratiques au contexte.",
        ("création de valeur", "responsabilité et leadership", "adaptation", "pensée systémique", "qualité et parties prenantes"),
        "Compatible avec des cycles prédictifs, itératifs, incrémentaux, adaptatifs ou hybrides.",
        "Organisations souhaitant un langage commun, une base de compétences et un référentiel transversal à plusieurs modes de livraison.",
        ("large couverture", "vocabulaire international", "fort accent sur l'adaptation", "écosystème professionnel étendu"),
        ("ce n'est pas une méthode prête à appliquer", "la sélection des pratiques demande de l'expérience"),
        "Passage d'une organisation centrée processus dans les éditions historiques à des principes et domaines en 2021 ; la 8e édition de 2025 reconnecte principes, domaines et guidance de processus.",
        "https://www.pmi.org/standards/pmbok",
    ),
    MethodologyArticle(
        "PRINCE2®", "Méthode de gouvernance par processus", "Gouvernement britannique ; PRINCE en 1989, puis PRINCE2 en 1996.",
        "Méthode gouvernée par la justification continue, des responsabilités définies, la gestion par séquences et par exception, et l'adaptation au projet.",
        ("justification continue", "rôles définis", "management par exception", "focalisation produit", "adaptation"),
        "Pré-projet → initialisation → séquences de livraison contrôlées → clôture, avec direction et pilotage continus.",
        "Projets nécessitant une gouvernance forte, des tolérances décisionnelles et une relation claire entre commanditaire, utilisateurs et fournisseurs.",
        ("contrôle par exception", "responsabilités nettes", "focalisation sur les produits", "compatible avec plusieurs modes de livraison"),
        ("risque de formalisme si non adaptée", "ne prescrit pas les techniques détaillées de production"),
        "Les éditions 2009 puis 2017 ont simplifié et renforcé l'adaptation ; PRINCE2 7 (2023) accentue personnes, durabilité, données, numérique et compatibilité agile/hybride.",
        "https://www.peoplecert.org/news-and-announcements/PRINCE2%207%20-%20A%20Process%20of%20Evolution",
    ),
    MethodologyArticle(
        "Prédictif / cycle séquentiel", "Approche de livraison", "Issu de l'ingénierie système et des grands programmes du XXe siècle ; souvent appelé « cycle en cascade ».",
        "Le périmètre et la solution sont définis tôt, puis le travail progresse par étapes planifiées. Le changement est contrôlé par analyse d'impact.",
        ("planification initiale", "séquencement", "références approuvées", "contrôle des changements", "traçabilité"),
        "Cadrage → conception → réalisation → vérification → déploiement, avec retours contrôlés entre étapes.",
        "Contexte stable, réglementé ou matériel, coûts de changement tardif élevés, besoin de preuves et de prévisibilité.",
        ("visibilité à long terme", "documentation et conformité", "gestion contractuelle facilitée"),
        ("retour utilisateur parfois tardif", "fragile quand les besoins ou la solution sont très incertains"),
        "Les pratiques modernes remplacent la cascade rigide par des cycles prédictifs avec prototypes, validation progressive et hybridation.",
        "https://www.iso.org/standard/74947.html",
    ),
    MethodologyArticle(
        "Scrum", "Cadre agile de développement produit", "Ken Schwaber et Jeff Sutherland, développé au début des années 1990 et présenté publiquement en 1995.",
        "Cadre léger pour générer de la valeur face à des problèmes complexes grâce à l'empirisme, des équipes auto-managées et des cycles courts.",
        ("transparence", "inspection", "adaptation", "focus sur un objectif produit", "incréments utilisables"),
        "Sprints d'un mois maximum : planification, travail quotidien, revue et rétrospective autour d'un Product Backlog ordonné.",
        "Produits complexes où les besoins et la solution émergent grâce à des retours fréquents.",
        ("feedback rapide", "responsabilités simples", "priorisation par la valeur", "amélioration régulière"),
        ("ne remplace ni stratégie produit ni pratiques d'ingénierie", "Scrum partiel perd sa cohérence", "prévisibilité longue à construire empiriquement"),
        "Premier Scrum Guide en 2010 ; révisions successives jusqu'à la version officielle 2020, plus simple et moins prescriptive, applicable au-delà du logiciel.",
        "https://scrumguides.org/scrum-guide.html",
    ),
    MethodologyArticle(
        "Kanban Method", "Gestion évolutive du flux", "David J. Anderson ; applications aux services informatiques dès 2004-2007, formalisation en 2010.",
        "Méthode d'amélioration appliquée au système de travail existant : visualiser, limiter le WIP, piloter le flux, expliciter les politiques et évoluer par expérimentation.",
        ("commencer avec l'existant", "changement évolutif", "leadership à tous niveaux", "orientation services", "décisions fondées sur les données"),
        "Flux continu tiré par la capacité, avec points d'engagement et de livraison plutôt qu'itérations obligatoires.",
        "Services, maintenance, opérations et équipes subissant des demandes variables ou souhaitant améliorer progressivement un processus existant.",
        ("faible rupture organisationnelle", "visualisation des blocages", "mesures de flux", "compatible avec d'autres méthodes"),
        ("un tableau seul n'est pas Kanban", "les limites WIP et politiques doivent être réellement respectées"),
        "Enracinée dans le Lean industriel mais adaptée au travail de connaissance ; depuis 2010, développement des modèles de maturité et de la gestion de services à l'échelle.",
        "https://kanban.university/kanban-guide/",
    ),
    MethodologyArticle(
        "Lean", "Système d'amélioration orienté valeur", "Toyota Production System développé surtout après la Seconde Guerre mondiale ; terme « lean production » diffusé en 1990.",
        "Pensée de management visant la valeur client, le flux, le système tiré, la qualité à la source, l'élimination des gaspillages et l'amélioration continue.",
        ("définir la valeur", "voir la chaîne de valeur", "créer le flux", "tirer par la demande", "viser la perfection"),
        "Pas de cycle de projet unique : diagnostic du flux, expérimentation PDCA, standardisation et amélioration continue.",
        "Produits, services et opérations où les délais, la qualité et les gaspillages peuvent être améliorés de bout en bout.",
        ("optimisation du système", "qualité intégrée", "apprentissage continu", "réduction des files et délais"),
        ("réduire Lean à la baisse des coûts détruit sa logique", "demande une culture durable de résolution de problèmes"),
        "Né de l'évolution du système Toyota, conceptualisé mondialement en 1990 puis étendu de l'industrie aux services, à la santé, au numérique et au secteur public.",
        "https://www.lean.org/explore-lean/a-brief-history-of-lean/",
    ),
    MethodologyArticle(
        "Extreme Programming (XP)", "Méthode agile d'ingénierie logicielle", "Kent Beck et l'équipe du projet Chrysler C3 au milieu des années 1990.",
        "Approche logicielle combinant cycles très courts et pratiques techniques disciplinées : tests, intégration continue, conception simple, binômage et refactoring.",
        ("communication", "simplicité", "feedback", "courage", "respect", "qualité technique continue"),
        "Plan de release, cycles hebdomadaires, développement piloté par les tests et livraisons fréquentes avec le client.",
        "Équipes logicielles confrontées à des besoins changeants et capables de collaborer étroitement avec des représentants utilisateurs.",
        ("excellente discipline technique", "détection rapide des défauts", "facilite le changement", "propriété collective"),
        ("pratiques exigeantes", "nécessite disponibilité client et automatisation", "moins directement applicable hors logiciel"),
        "XP a fortement influencé l'ingénierie agile moderne, notamment TDD, intégration continue, refactoring et petites releases.",
        "https://agilealliance.org/glossary/xp/",
    ),
    MethodologyArticle(
        "DSDM / AgilePM", "Méthode agile de projet", "DSDM Consortium, Royaume-Uni, 1994 ; AgilePM est une déclinaison de management de projet fondée sur DSDM.",
        "Méthode couvrant gouvernance et livraison adaptative avec implication métier active, délais et coûts fixés, périmètre priorisé et qualité non négociable.",
        ("se concentrer sur le besoin métier", "livrer à temps", "collaborer", "ne jamais compromettre la qualité", "développer itérativement"),
        "Faisabilité et fondations, puis exploration et ingénierie itératives, déploiement et évaluation des bénéfices.",
        "Projets qui veulent l'agilité avec une gouvernance de projet complète, des rôles métier et des échéances fermes.",
        ("gouvernance plus complète que les cadres d'équipe", "priorisation MoSCoW", "timeboxing", "qualité explicite"),
        ("nombreux rôles à adapter", "demande une participation métier soutenue"),
        "DSDM a participé au mouvement agile dès les années 1990 ; AgilePM a rendu ses principes plus accessibles au management de projet généraliste.",
        "https://www.agilebusiness.org/dsdm-project-framework.html",
    ),
    MethodologyArticle(
        "SAFe®", "Cadre d'agilité à l'échelle", "Dean Leffingwell ; première version publique du Scaled Agile Framework en 2011.",
        "Cadre d'organisation de la stratégie, des portefeuilles et de plusieurs équipes agiles autour de flux de valeur et de cadences communes.",
        ("Lean-Agile", "flux de valeur", "alignement stratégie-exécution", "qualité intégrée", "cadence et synchronisation"),
        "Planification et livraison par incréments de programme, équipes agiles coordonnées dans des Agile Release Trains.",
        "Grandes organisations ayant plusieurs équipes et dépendances, et cherchant un langage de coordination commun.",
        ("alignement multi-équipes", "vision portefeuille", "cadence commune", "intègre produit, architecture et DevOps"),
        ("complexité et coût d'adoption", "risque de déploiement mécanique", "doit préserver autonomie et feedback"),
        "Élargi au fil des versions de la coordination programme vers le portefeuille Lean, les flux de valeur, DevOps et l'agilité métier.",
        "https://scaledagileframework.com/about/",
    ),
    MethodologyArticle(
        "ISO 21502", "Norme de guidance", "Organisation internationale de normalisation ; ISO 21502 publiée en décembre 2020.",
        "Guidance de haut niveau applicable à tout type d'organisation et de projet, quel que soit le modèle de cycle de vie ou l'approche de livraison.",
        ("applicabilité universelle", "pratiques de management", "gouvernance", "bénéfices et résultats", "adaptation"),
        "Ne prescrit pas un cycle unique ; reconnaît explicitement les approches prédictives, incrémentales, itératives, adaptatives et hybrides.",
        "Organisations souhaitant aligner leur cadre interne sur une norme internationale indépendante d'une méthode commerciale.",
        ("neutre quant à la méthode", "langage international", "compatible avec de nombreux secteurs"),
        ("guidance de haut niveau", "nécessite des processus et modèles complémentaires pour l'exécution quotidienne"),
        "Succède à la guidance projet d'ISO 21500:2012 et s'inscrit dans une famille couvrant projets, programmes, portefeuilles et gouvernance.",
        "https://www.iso.org/standard/74947.html",
    ),
    MethodologyArticle(
        "Approche hybride", "Combinaison contextualisée", "Pratique contemporaine issue de la coexistence des approches prédictives, Lean et agiles.",
        "Conception volontaire d'un système de management combinant gouvernance et prévisions là où elles sont utiles, avec exploration itérative et flux adaptatif là où l'incertitude domine.",
        ("adapter par type de travail", "conserver une gouvernance commune", "rendre les interfaces explicites", "mesurer résultats et flux"),
        "Exemple : cadrage et budget par phases, développement en sprints, opérations en Kanban, gates fondées sur des preuves.",
        "Projets contenant simultanément obligations contractuelles ou réglementaires et composants innovants ou numériques.",
        ("réalisme contextuel", "compatibilité avec la gouvernance", "feedback plus précoce", "réduction du dogmatisme"),
        ("peut devenir incohérente sans règles d'interface", "ne doit pas signifier empiler toutes les cérémonies"),
        "La normalisation et les référentiels récents reconnaissent explicitement le continuum prédictif-adaptatif et la nécessité du tailoring.",
        "https://www.iso.org/standard/74947.html",
    ),
)


TIMELINE = (
    TimelineEvent("1910–1915", "Gantt et planification visuelle", "Henry L. Gantt popularise des diagrammes à barres pour planifier et suivre le travail industriel."),
    TimelineEvent("1957–1958", "CPM et PERT", "Le chemin critique (CPM) et PERT formalisent la planification en réseau pour l'industrie et les grands programmes complexes."),
    TimelineEvent("1965", "Création d'IPMA", "Un réseau européen de praticiens, futur IPMA, structure l'échange international autour du management de projet."),
    TimelineEvent("1969", "Création du PMI", "Le Project Management Institute est fondé et contribue à professionnaliser la discipline.", "https://www.pmi.org/about/our-legacy"),
    TimelineEvent("Années 1970", "Cycles séquentiels", "L'ingénierie logicielle formalise des cycles par étapes ; leur représentation en cascade sera ensuite simplifiée et largement diffusée."),
    TimelineEvent("Années 1980", "Qualité, contraintes et standards", "La gestion de projet intègre davantage qualité totale, analyse des risques, valeur acquise et référentiels communs."),
    TimelineEvent("1989–1996", "De PRINCE à PRINCE2", "La méthode britannique PRINCE est généralisée au-delà des systèmes d'information avec PRINCE2."),
    TimelineEvent("1990", "Diffusion du Lean", "The Machine That Changed the World popularise le terme lean production et l'analyse du système Toyota.", "https://www.lean.org/explore-lean/a-brief-history-of-lean/"),
    TimelineEvent("1994–1995", "DSDM, XP et Scrum", "Plusieurs approches adaptatives émergent ; Scrum est présenté publiquement à OOPSLA en 1995.", "https://scrumguides.org/scrum-guide.html"),
    TimelineEvent("1996", "Premier PMBOK® Guide", "PMI publie la première édition complète de son guide du corpus de connaissances."),
    TimelineEvent("2001", "Manifeste Agile", "Dix-sept praticiens formulent quatre valeurs et douze principes pour le développement logiciel agile.", "https://agilemanifesto.org/"),
    TimelineEvent("2007–2008", "Naissance de PM²", "La Commission européenne développe PM² en 2007 et publie une première version interne en 2008.", "https://pm2.europa.eu/pm2-methodologies/pm2-project-management_en"),
    TimelineEvent("2010", "Scrum Guide et Kanban Method", "Le premier Scrum Guide codifie Scrum ; la Kanban Method est formalisée pour le travail de connaissance.", "https://kanban.university/kanban-guide/"),
    TimelineEvent("2011", "Agilité à l'échelle", "Les cadres d'alignement multi-équipes, dont SAFe, répondent à l'adoption de l'agile dans les grandes organisations."),
    TimelineEvent("2012", "ISO 21500", "ISO publie une première guidance internationale générale sur le management de projet."),
    TimelineEvent("2018", "Open PM²", "La méthodologie PM² de la Commission européenne devient ouverte à tous.", "https://pm2.europa.eu/about_en"),
    TimelineEvent("2020", "ISO 21502 et Scrum 2020", "ISO 21502 reconnaît tout le continuum de livraison ; Scrum simplifie son guide et renforce l'objectif produit.", "https://www.iso.org/standard/74947.html"),
    TimelineEvent("2021", "PMBOK® 7", "Le référentiel PMI passe d'une structure principalement orientée processus à des principes et domaines de performance."),
    TimelineEvent("2023", "PM² 3.1 et PRINCE2 7", "PM² actualise son guide ; PRINCE2 renforce personnes, durabilité, données et compatibilité avec les modes adaptatifs.", "https://pm2.europa.eu/about_en"),
    TimelineEvent("2025", "Valeur, IA et systèmes hybrides", "Les référentiels récents accentuent valeur, adaptation, durabilité, données, intelligence artificielle responsable et articulation entre gouvernance et flux.", "https://www.pmi.org/standards/pmbok"),
)


SELECTION_GUIDE = (
    ("Besoins stables, forte conformité", "Prédictif, PM², PRINCE2 ou ISO 21502", "Planifier, baseliner et documenter ; conserver des boucles de validation précoces."),
    ("Produit complexe, feedback fréquent", "Scrum ou XP", "Travailler par objectifs courts et incréments utilisables ; investir dans la qualité technique."),
    ("Flux continu et demandes variables", "Kanban", "Visualiser les files, limiter le WIP et mesurer délais et débit."),
    ("Optimisation de bout en bout", "Lean", "Étudier la chaîne de valeur et améliorer le système, pas seulement l'utilisation individuelle."),
    ("Plusieurs équipes interdépendantes", "PM²/PRINCE2 + pratiques agiles ; SAFe selon l'échelle", "Séparer gouvernance, coordination et mode de réalisation ; éviter les cérémonies sans valeur."),
    ("Réglementé et innovant à la fois", "Hybride", "Appliquer des contrôles prédictifs aux engagements et des boucles adaptatives aux zones incertaines."),
)


SOURCES = (
    ("Commission européenne — PM²", "https://pm2.europa.eu/pm2-methodologies/pm2-project-management_en"),
    ("Commission européenne — chronologie PM²", "https://pm2.europa.eu/about_en"),
    ("PMI — PMBOK Guide", "https://www.pmi.org/standards/pmbok"),
    ("Scrum Guides — guide officiel", "https://scrumguides.org/scrum-guide.html"),
    ("Manifeste Agile", "https://agilemanifesto.org/"),
    ("ISO — ISO 21502:2020", "https://www.iso.org/standard/74947.html"),
    ("PeopleCert — évolution de PRINCE2 7", "https://www.peoplecert.org/news-and-announcements/PRINCE2%207%20-%20A%20Process%20of%20Evolution"),
    ("Kanban University — guide officiel", "https://kanban.university/kanban-guide/"),
    ("Lean Enterprise Institute — histoire du Lean", "https://www.lean.org/explore-lean/a-brief-history-of-lean/"),
    ("Agile Alliance — Extreme Programming", "https://agilealliance.org/glossary/xp/"),
)


def search_glossary(query: str = "", category: str = "Toutes") -> tuple[GlossaryEntry, ...]:
    needle = query.strip().casefold()
    return tuple(
        entry
        for entry in GLOSSARY
        if (category == "Toutes" or entry.category == category)
        and (not needle or needle in entry.searchable_text)
    )


def search_methodologies(query: str = "") -> tuple[MethodologyArticle, ...]:
    needle = query.strip().casefold()
    return tuple(
        article for article in METHODOLOGIES if not needle or needle in article.searchable_text
    )
