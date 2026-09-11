#!/usr/bin/env python3
"""Génère des captures de recette visuelle sur une base PM² éphémère."""

from __future__ import annotations

import argparse
import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import uuid4

from PySide6.QtWidgets import QApplication
from sqlalchemy import select

from pm2.application.artifacts import ARTIFACT_SCHEMAS, ArtifactDataService
from pm2.application.context import ApplicationContext
from pm2.application.documents import DocumentService
from pm2.application.services import (
    AcceptanceService,
    DeliverableService,
    GovernanceService,
    ProjectService,
    RegisterService,
    WorkPlanService,
)
from pm2.config import AppPaths
from pm2.infrastructure.orm import RiskModel
from pm2.ui.crud import EntityCatalogPage
from pm2.ui.main_window import MainWindow
from pm2.ui.pages import DocumentsPage, RegistersPage
from pm2.ui.wizards import PhaseAssistantPage


def seed(context: ApplicationContext, output: Path) -> None:
    with context.database.session_factory() as session:
        project = ProjectService(session, context.methodology).create(
            reference="QA-2026-001",
            name="Modernisation du portail citoyen",
            description=(
                "Projet de démonstration pour la recette visuelle PM² Desktop. "
                "Il consolide gouvernance, planification, exigences et acceptation."
            ),
            project_manager="Alice Martin",
            project_owner="Bernard Dupont",
            approved_budget=Decimal("480000"),
            currency="CHF",
            start_date=date(2026, 1, 15),
            target_end_date=date(2026, 11, 30),
        )
        GovernanceService(session).add_stakeholder(
            project.id,
            "Direction des services numériques",
            organisation="Administration cantonale",
            function="Bénéficiaire principal",
            interest="HIGH",
            influence="HIGH",
            strategy="Revue mensuelle et validation des jalons",
        )
        plan = WorkPlanService(session)
        package = plan.create_node(project.id, "1", "Conception et réalisation")
        tasks = []
        for code, name, start, end, progress, cost in (
            ("1.1", "Ateliers de conception", date(2026, 2, 2), date(2026, 2, 20), 100, "42000"),
            ("1.2", "Développement du portail", date(2026, 2, 23), date(2026, 6, 30), 58, "215000"),
            ("1.3", "Recette métier", date(2026, 7, 1), date(2026, 8, 15), 10, "68000"),
        ):
            node = plan.create_node(project.id, code, name, node_type="task", parent_id=package.id)
            tasks.append(
                plan.create_task(
                    node.id,
                    planned_start=start,
                    planned_end=end,
                    progress_percent=progress,
                    planned_cost=Decimal(cost),
                )
            )
        plan.add_dependency(tasks[0].id, tasks[1].id, "FS")
        plan.add_dependency(tasks[1].id, tasks[2].id, "FS", 2)
        deliverable = DeliverableService(session).create(
            project.id,
            "DEL-01",
            "Portail citoyen opérationnel",
            owner="Alice Martin",
            planned_date=date(2026, 8, 15),
        )
        deliverable.status = "READY_FOR_ACCEPTANCE"
        criterion = AcceptanceService(session).add_criterion(
            deliverable.id,
            "AC-01",
            "Les cinq démarches prioritaires sont réalisables de bout en bout.",
        )
        AcceptanceService(session).add_test(
            criterion.id,
            "AT-01",
            "Exécuter le scénario nominal de chaque démarche",
            "Cinq demandes enregistrées sans erreur bloquante",
        )
        registers = RegisterService(session)
        registers.create(
            "risk",
            project.id,
            code="R-01",
            title="Disponibilité tardive des experts métier",
            owner="Bernard Dupont",
            probability=4,
            impact=4,
            strategy="Escalade au PSC et suppléants nommés",
        )
        registers.create(
            "issue",
            project.id,
            code="I-01",
            title="Retard de fourniture du référentiel",
            owner="Alice Martin",
            priority="HIGH",
            impact="Décalage potentiel de deux semaines",
        )
        registers.create(
            "decision",
            project.id,
            code="D-01",
            title="Architecture modulaire retenue",
            outcome="Architecture à services découplés",
            rationale="Réduction du risque d'intégration",
        )
        registers.create(
            "change",
            project.id,
            code="C-01",
            title="Ajout de la signature électronique",
            priority="MEDIUM",
            reason="Nouvelle exigence réglementaire",
        )
        documents = DocumentService(session, context.methodology)
        documents.ensure_catalog(project.id)
        artifact_data = ArtifactDataService(session)
        for code, schema in ARTIFACT_SCHEMAS.items():
            artifact_data.save(
                project.id,
                code,
                {
                    field.code: (
                        f"Contenu de démonstration validé pour « {field.label} ». "
                        "Les éléments sont issus des données structurées du projet."
                    )
                    for section in schema.sections
                    for field in section.fields
                },
                actor="recette-visuelle",
            )
        documents.generate(
            project.id,
            "PROJECT_CHARTER",
            output / "project-charter.md",
            "md",
        )
        session.commit()


def prepare_page(window: MainWindow, name: str) -> None:
    window.navigate_to(name)
    page = window.stack.currentWidget()
    if isinstance(page, PhaseAssistantPage):
        if name == "Exécution" and page.acceptance is not None:
            page.tabs.setCurrentWidget(page.acceptance)
        elif page.editors:
            page.tabs.setCurrentWidget(page.editors[0])
    elif isinstance(page, EntityCatalogPage):
        page.selector.setCurrentIndex(page.selector.findData("risks"))
        if page.table.rowCount():
            page.table.selectRow(0)
    elif isinstance(page, RegistersPage):
        page.tabs.setCurrentIndex(0)
        if page.register_tabs[0].table.rowCount():
            page.register_tabs[0].table.selectRow(0)
    elif isinstance(page, DocumentsPage) and page.table.rowCount():
        for row in range(page.table.rowCount()):
            if page.table.item(row, 0).text() == "PROJECT_CHARTER":
                page.table.selectRow(row)
                break


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    database = output / f"visual-qa-{uuid4().hex}.db"
    context = ApplicationContext.open(database)
    seed(context, output)
    app = QApplication.instance() or QApplication([])
    paths = AppPaths(output, database, output / "visual-qa.log", output / "recent.json")
    window = MainWindow(context, paths)
    window.resize(1500, 950)
    window.show()
    app.processEvents()
    captures: list[dict[str, Any]] = []
    for order, page_name in enumerate(
        (
            "Dashboard",
            "Lancement",
            "Planification",
            "Plan de travail",
            "Catalogue",
            "Exécution",
            "Registres",
            "Documents",
            "Clôture",
        ),
        start=1,
    ):
        prepare_page(window, page_name)
        app.processEvents()
        filename = f"{order:02d}-{page_name.lower().replace(' ', '-').replace('ô', 'o')}.png"
        target = output / filename
        if not window.grab().save(str(target), "PNG"):
            raise RuntimeError(f"Capture impossible : {target}")
        captures.append({"page": page_name, "file": filename, "bytes": target.stat().st_size})
    with context.database.session_factory() as session:
        risk_count = len(session.scalars(select(RiskModel)).all())
    manifest = {
        "status": "captured",
        "database": database.name,
        "risk_count": risk_count,
        "captures": captures,
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    window.close()
    print(json.dumps(manifest, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
