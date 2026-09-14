"""Créer un projet fictif de formation avec les services métier de PM² Desktop."""

from __future__ import annotations

import argparse
from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select

from pm2.application.artifacts import ArtifactDataService
from pm2.application.context import ApplicationContext
from pm2.application.documents import DocumentService
from pm2.application.services import (
    AcceptanceService,
    DeliverableService,
    GovernanceService,
    ProjectService,
    RegisterService,
    RequirementService,
    WorkPlanService,
)
from pm2.infrastructure.archive import ProjectArchiveService
from pm2.infrastructure.orm import ProjectModel

REFERENCE = "FORMATION-2026-001"


def create_project(context: ApplicationContext) -> str:
    with context.database.session_factory() as session:
        existing = session.scalar(select(ProjectModel).where(ProjectModel.reference == REFERENCE))
        if existing:
            return existing.id
        project = ProjectService(session, context.methodology).create(
            reference=REFERENCE,
            name="EXEMPLE — Portail de l’association Les Colibris",
            description=(
                "Cas fictif pour apprendre PM². Une association de 120 membres souhaite remplacer "
                "ses inscriptions par courriel par un portail de réservation d’activités. "
                "Objectif : 80 % des inscriptions en ligne et 50 % de temps administratif économisé. "
                "Toutes les personnes sont fictives. Le planning est une proposition à valider. "
                "Les documents restent en brouillon et les décisions de passage de phase restent à prendre."
            ),
            project_manager="Alice Martin",
            project_owner="Nicolas Bernard",
            approved_budget=Decimal("24000"),
            currency="CHF",
            start_date=date(2026, 9, 14),
            target_end_date=date(2026, 12, 11),
        )
        governance = GovernanceService(session)
        for name, function, interest, influence, strategy in (
            (
                "Comité de l’association",
                "Sponsor et arbitrage",
                "HIGH",
                "HIGH",
                "Revue aux jalons et suivi mensuel",
            ),
            (
                "Sophie Leroy",
                "Secrétariat et référente métier",
                "HIGH",
                "HIGH",
                "Atelier hebdomadaire et validation des écrans",
            ),
            (
                "Marc Dubois",
                "Responsable technique",
                "HIGH",
                "MEDIUM",
                "Suivi technique hebdomadaire",
            ),
            (
                "Groupe pilote de 12 membres",
                "Utilisateurs pilotes",
                "HIGH",
                "MEDIUM",
                "Démonstration et recette avant ouverture",
            ),
        ):
            governance.add_stakeholder(
                project.id,
                name,
                organisation="Association fictive Les Colibris",
                function=function,
                interest=interest,
                influence=influence,
                strategy=strategy,
            )
        plan = WorkPlanService(session)
        packages = {
            code: plan.create_node(project.id, code, title)
            for code, title in (
                ("1", "Cadrage"),
                ("2", "Conception"),
                ("3", "Réalisation et recette"),
                ("4", "Déploiement et clôture"),
            )
        }
        tasks = {}
        for code, title, start, end, cost, effort in (
            (
                "1.1",
                "Recueillir les besoins du secrétariat",
                "2026-09-14",
                "2026-09-18",
                "1200",
                "2",
            ),
            (
                "1.2",
                "Préparer la charte et la gouvernance",
                "2026-09-21",
                "2026-09-25",
                "1800",
                "3",
            ),
            (
                "2.1",
                "Concevoir les écrans et le parcours membre",
                "2026-09-28",
                "2026-10-09",
                "2400",
                "4",
            ),
            (
                "2.2",
                "Définir les exigences et le plan de recette",
                "2026-10-12",
                "2026-10-16",
                "1800",
                "3",
            ),
            (
                "3.1",
                "Configurer le portail et les comptes",
                "2026-10-19",
                "2026-10-30",
                "6000",
                "10",
            ),
            (
                "3.2",
                "Importer les données fictives des membres",
                "2026-11-02",
                "2026-11-06",
                "1800",
                "3",
            ),
            (
                "3.3",
                "Exécuter la recette avec le groupe pilote",
                "2026-11-09",
                "2026-11-20",
                "2400",
                "4",
            ),
            ("3.4", "Corriger les anomalies de recette", "2026-11-23", "2026-11-27", "1800", "3"),
            (
                "4.1",
                "Former le secrétariat et ouvrir le portail",
                "2026-11-30",
                "2026-12-04",
                "1200",
                "2",
            ),
            ("4.2", "Mesurer les résultats et clôturer", "2026-12-07", "2026-12-11", "600", "1"),
        ):
            node = plan.create_node(
                project.id,
                code,
                title,
                node_type="task",
                parent_id=packages[code[0]].id,
            )
            tasks[code] = plan.create_task(
                node.id,
                planned_start=date.fromisoformat(start),
                planned_end=date.fromisoformat(end),
                planned_cost=Decimal(cost),
                planned_effort=Decimal(effort),
                progress_percent=0,
            )
        for predecessor, successor in zip(list(tasks)[:-1], list(tasks)[1:], strict=True):
            plan.add_dependency(tasks[predecessor].id, tasks[successor].id, "FS")
        deliverables = {}
        acceptance = AcceptanceService(session)
        for code, title, deadline, criterion, expected in (
            (
                "L-01",
                "Maquettes du portail",
                "2026-10-09",
                "Le secrétariat peut comprendre le parcours de réservation.",
                "Le groupe pilote réalise le parcours sur maquette sans aide.",
            ),
            (
                "L-02",
                "Portail configuré",
                "2026-11-27",
                "La capacité d’une activité ne peut pas être dépassée.",
                "La onzième inscription à une activité de dix places est refusée.",
            ),
            (
                "L-03",
                "Données membres importées",
                "2026-11-06",
                "Les 120 membres fictifs sont importés sans doublon.",
                "120 comptes uniques sont présents et le contrôle de rapprochement est correct.",
            ),
            (
                "L-04",
                "Guide utilisateur et formation",
                "2026-12-04",
                "Le secrétariat peut créer une activité de façon autonome.",
                "Sophie crée une activité et exporte les inscriptions sans assistance.",
            ),
        ):
            deliverables[code] = DeliverableService(session).create(
                project.id,
                code,
                title,
                owner="Alice Martin",
                planned_date=date.fromisoformat(deadline),
            )
            item = acceptance.add_criterion(deliverables[code].id, f"AC-{code}", criterion)
            acceptance.add_test(item.id, f"TEST-{code}", criterion, expected)
        requirements = RequirementService(session)
        for code, title, task, deliverable in (
            ("EX-01", "Réserver une activité avec confirmation par courriel", "3.1", "L-02"),
            (
                "EX-02",
                "Limiter automatiquement les inscriptions au nombre de places",
                "3.1",
                "L-02",
            ),
            ("EX-03", "Réserver l’accès aux données membres au secrétariat", "3.1", "L-02"),
            ("EX-04", "Importer 120 membres fictifs sans doublon", "3.2", "L-03"),
            ("EX-05", "Créer une activité et exporter les inscriptions sans aide", "4.1", "L-04"),
        ):
            item = requirements.create(
                project.id,
                code,
                title,
                source="Atelier avec le secrétariat",
                priority="HIGH",
                verification_method="Test de recette avec preuve enregistrée",
            )
            requirements.link_task(item.id, tasks[task].id)
            requirements.link_deliverable(item.id, deliverables[deliverable].id)
        registers = RegisterService(session)
        for code, title, probability, impact, strategy in (
            (
                "R-01",
                "Indisponibilité du secrétariat pour valider les écrans",
                3,
                4,
                "Réserver les ateliers et nommer un suppléant.",
            ),
            (
                "R-02",
                "Doublons dans le fichier des membres",
                4,
                3,
                "Nettoyer un échantillon et tester l’import avant migration.",
            ),
            (
                "R-03",
                "Faible adoption du portail par les membres",
                3,
                3,
                "Associer le groupe pilote et préparer un guide simple.",
            ),
        ):
            registers.create(
                "risk",
                project.id,
                code=code,
                title=title,
                owner="Alice Martin",
                probability=probability,
                impact=impact,
                strategy=strategy,
            )
        registers.create(
            "issue",
            project.id,
            code="I-01",
            title="Le fichier membres ne contient pas tous les courriels",
            owner="Sophie Leroy",
            priority="HIGH",
            impact="Certains membres ne pourront pas recevoir leur invitation.",
            description="Exercice : définir une action, un responsable et une échéance puis suivre la résolution.",
        )
        registers.create(
            "decision",
            project.id,
            code="D-01",
            title="Choisir une solution existante ou un développement spécifique",
            decision_owner="Nicolas Bernard",
            rationale="Comparer le coût total, le délai et la facilité de maintenance.",
            description="Exercice : analyser les options et enregistrer la décision du comité.",
        )
        registers.create(
            "change",
            project.id,
            code="C-01",
            title="Ajouter le paiement en ligne des cotisations",
            requester="Comité de l’association",
            priority="MEDIUM",
            reason="Éviter le rapprochement manuel des paiements.",
            impact_scope="Nouvelle fonction hors du périmètre initial",
            impact_schedule="Estimation initiale : deux semaines",
            impact_cost=Decimal("4500"),
            description="Exercice : analyser puis soumettre la demande à approbation.",
        )
        DocumentService(session, context.methodology).ensure_catalog(project.id)
        data = ArtifactDataService(session)
        data.save(
            project.id,
            "PROJECT_INITIATION_REQUEST",
            {
                "context": "Association fictive de 120 membres ; inscriptions aux activités gérées par courriel et tableur.",
                "requester": "Nicolas Bernard, président et propriétaire du projet.",
                "problem": "Erreurs de capacité, données dispersées et cinq heures de gestion administrative par semaine.",
                "desired_outcomes": "80 % des inscriptions en ligne ; réduction de 50 % du temps administratif.",
                "initial_scope": "Comptes membres, catalogue d’activités, réservations, confirmations et export des inscriptions.",
                "constraints": "24 000 CHF, ouverture au plus tard le 4 décembre 2026 ; aucune donnée réelle dans cet exercice.",
            },
        )
        data.save(
            project.id,
            "BUSINESS_CASE",
            {
                "executive_summary": "Mettre en place un portail simple pour fiabiliser les inscriptions et libérer du temps bénévole.",
                "strategic_alignment": "Améliorer les services aux membres et rendre l’association moins dépendante d’une personne.",
                "options": "1. Garder les courriels ; 2. Configurer une solution existante ; 3. Développer sur mesure.",
                "recommended_option": "Configurer une solution existante, sous réserve de comparaison et d’approbation du comité.",
                "benefits": "Gain visé de 2,5 heures par semaine et diminution des erreurs d’inscription.",
                "costs": "21 000 CHF de tâches planifiées et 3 000 CHF de réserve ; préciser les coûts récurrents en exercice.",
                "business_risks": "Adoption limitée ; disponibilité des bénévoles ; qualité du fichier membres.",
                "roadmap": "Septembre : cadrage ; octobre : conception et configuration ; novembre : recette ; décembre : ouverture.",
                "success_measures": "Mesurer le taux d’inscriptions en ligne et le temps de gestion après quatre semaines d’utilisation.",
            },
        )
        data.save(
            project.id,
            "PROJECT_CHARTER",
            {
                "justification": "Centraliser les inscriptions et fiabiliser les capacités des activités.",
                "objectives": "80 % des inscriptions en ligne et 50 % de temps administratif économisé après quatre semaines.",
                "scope_in": "Comptes membres, activités, réservations, notifications, import fictif et formation.",
                "scope_out": "Paiement en ligne, application mobile et comptabilité.",
                "high_level_requirements": "Contrôle de capacité ; confirmation ; accès restreint ; import sans doublon.",
                "key_deliverables": "Maquettes, portail, données importées, guide utilisateur et formation.",
                "constraints": "Budget maximal de 24 000 CHF ; fin du projet le 11 décembre 2026.",
                "assumptions": "Le secrétariat participe aux ateliers et douze membres contribuent à la recette.",
                "milestones": "Charte : 25/09 ; maquettes : 09/10 ; recette : 20/11 ; ouverture : 04/12 ; clôture : 11/12.",
                "governance": "Alice Martin : PM ; Nicolas Bernard : PO ; comité de l’association : arbitrage aux jalons.",
                "approval": "",
            },
        )
        session.commit()
        return project.id


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--archive", type=Path)
    args = parser.parse_args()
    context = ApplicationContext.open(args.database)
    try:
        project_id = create_project(context)
        if args.archive:
            with context.database.session_factory() as session:
                print(
                    ProjectArchiveService(context.database, session).save(project_id, args.archive)
                )
        print(f"{REFERENCE} : {args.database}")
    finally:
        context.database.dispose()


if __name__ == "__main__":
    main()
