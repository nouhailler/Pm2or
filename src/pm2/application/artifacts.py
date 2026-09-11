from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from pm2.application.services import AuditService
from pm2.infrastructure.orm import DocumentModel, SettingModel, utcnow


@dataclass(frozen=True, slots=True)
class ArtifactField:
    code: str
    label: str
    required: bool = True
    multiline: bool = True
    help_text: str = ""


@dataclass(frozen=True, slots=True)
class ArtifactSection:
    title: str
    fields: tuple[ArtifactField, ...]


@dataclass(frozen=True, slots=True)
class ArtifactSchema:
    code: str
    title: str
    phase: str
    purpose: str
    sections: tuple[ArtifactSection, ...]


def field(code: str, label: str, required: bool = True, help_text: str = "") -> ArtifactField:
    return ArtifactField(code, label, required, True, help_text)


def section(title: str, *fields: ArtifactField) -> ArtifactSection:
    return ArtifactSection(title, fields)


ARTIFACT_SCHEMAS: dict[str, ArtifactSchema] = {
    "PROJECT_INITIATION_REQUEST": ArtifactSchema(
        "PROJECT_INITIATION_REQUEST",
        "Demande d’Initiation de Projet",
        "LAUNCH",
        "Formaliser le besoin, le contexte et les résultats souhaités.",
        (
            section(
                "Contexte",
                field("context", "Contexte organisationnel"),
                field("requester", "Demandeur"),
            ),
            section(
                "Besoin",
                field("problem", "Problème ou opportunité"),
                field("desired_outcomes", "Résultats souhaités"),
            ),
            section(
                "Cadre initial",
                field("initial_scope", "Périmètre initial"),
                field("constraints", "Contraintes connues", False),
            ),
        ),
    ),
    "BUSINESS_CASE": ArtifactSchema(
        "BUSINESS_CASE",
        "Étude d’Opportunité",
        "LAUNCH",
        "Établir la justification, les options et la valeur attendue.",
        (
            section(
                "Synthèse",
                field("executive_summary", "Résumé exécutif"),
                field("strategic_alignment", "Alignement stratégique"),
            ),
            section(
                "Analyse",
                field("options", "Options étudiées"),
                field("recommended_option", "Option recommandée"),
            ),
            section(
                "Viabilité",
                field("benefits", "Bénéfices attendus"),
                field("costs", "Coûts estimés"),
                field("business_risks", "Risques métier"),
            ),
            section(
                "Feuille de route",
                field("roadmap", "Échéancier de haut niveau"),
                field("success_measures", "Mesures de succès"),
            ),
        ),
    ),
    "PROJECT_CHARTER": ArtifactSchema(
        "PROJECT_CHARTER",
        "Charte du Projet",
        "LAUNCH",
        "Définir et autoriser le projet sur ses dimensions essentielles.",
        (
            section(
                "Justification et objectifs",
                field("justification", "Justification"),
                field("objectives", "Objectifs mesurables"),
            ),
            section(
                "Périmètre",
                field("scope_in", "Dans le périmètre"),
                field("scope_out", "Hors périmètre"),
            ),
            section(
                "Résultats",
                field("high_level_requirements", "Exigences de haut niveau"),
                field("key_deliverables", "Livrables principaux"),
            ),
            section(
                "Cadre",
                field("constraints", "Contraintes"),
                field("assumptions", "Hypothèses"),
                field("milestones", "Jalons"),
            ),
            section(
                "Gouvernance",
                field("governance", "Organisation et responsabilités"),
                field("approval", "Autorisation du projet"),
            ),
        ),
    ),
    "PROJECT_HANDBOOK": ArtifactSchema(
        "PROJECT_HANDBOOK",
        "Manuel du Projet",
        "PLANNING",
        "Décrire l’approche de gestion, la gouvernance et les processus du projet.",
        (
            section(
                "Approche",
                field("management_approach", "Approche de gestion"),
                field("tailoring", "Adaptation de PM²"),
            ),
            section(
                "Gouvernance",
                field("roles", "Rôles et responsabilités"),
                field("decision_process", "Décision et escalade"),
            ),
            section(
                "Pilotage",
                field("reporting", "Rapports et réunions"),
                field("change_control", "Gestion des changements"),
                field("configuration", "Gestion de configuration"),
            ),
            section(
                "Assurance",
                field("quality_assurance", "Assurance qualité"),
                field("information_management", "Gestion de l’information"),
            ),
        ),
    ),
    "STAKEHOLDER_MATRIX": ArtifactSchema(
        "STAKEHOLDER_MATRIX",
        "Matrice des Parties Prenantes",
        "PLANNING",
        "Analyser les parties prenantes et définir leur engagement.",
        (
            section(
                "Méthode",
                field("identification_method", "Méthode d’identification"),
                field("classification_method", "Méthode de classification"),
            ),
            section(
                "Engagement",
                field("engagement_principles", "Principes d’engagement"),
                field("sensitive_information", "Traitement des informations sensibles", False),
            ),
        ),
    ),
    "WORK_PLAN": ArtifactSchema(
        "WORK_PLAN",
        "Plan de Travail du Projet",
        "PLANNING",
        "Décomposer et planifier le travail, les ressources, les coûts et l’échéancier.",
        (
            section(
                "Référence",
                field("planning_basis", "Base de planification"),
                field("baseline_policy", "Politique de référence"),
            ),
            section(
                "Organisation",
                field("wbs_approach", "Approche WBS"),
                field("resource_plan", "Plan de ressources"),
            ),
            section(
                "Contrôle",
                field("schedule_control", "Contrôle de l’échéancier"),
                field("cost_control", "Contrôle des coûts"),
                field("progress_measurement", "Mesure de l’avancement"),
            ),
        ),
    ),
    "OUTSOURCING_PLAN": ArtifactSchema(
        "OUTSOURCING_PLAN",
        "Plan d’Externalisation",
        "PLANNING",
        "Organiser les acquisitions et le pilotage des prestations externes.",
        (
            section(
                "Périmètre",
                field("outsourced_scope", "Travaux externalisés"),
                field("sourcing_strategy", "Stratégie d’externalisation"),
            ),
            section(
                "Sélection",
                field("procurement_process", "Processus d’acquisition"),
                field("selection_criteria", "Critères de sélection"),
            ),
            section(
                "Pilotage",
                field("supplier_governance", "Gouvernance fournisseur"),
                field("contract_monitoring", "Suivi des obligations"),
                field("exit_strategy", "Stratégie de sortie"),
            ),
        ),
    ),
    "DELIVERABLE_ACCEPTANCE_PLAN": ArtifactSchema(
        "DELIVERABLE_ACCEPTANCE_PLAN",
        "Plan d’Acceptation des Livrables",
        "PLANNING",
        "Définir les critères, tests, responsabilités et décisions d’acceptation.",
        (
            section(
                "Approche",
                field("acceptance_approach", "Approche d’acceptation"),
                field("roles", "Rôles d’acceptation"),
            ),
            section(
                "Évaluation",
                field("criteria_method", "Définition des critères"),
                field("test_method", "Méthode de test"),
                field("evidence", "Preuves attendues"),
            ),
            section(
                "Décision",
                field("schedule", "Calendrier d’acceptation"),
                field("decision_process", "Décision et réserves"),
            ),
        ),
    ),
    "TRANSITION_PLAN": ArtifactSchema(
        "TRANSITION_PLAN",
        "Plan de Transition",
        "PLANNING",
        "Préparer le transfert contrôlé des résultats vers l’exploitation.",
        (
            section(
                "Objectifs",
                field("transition_objectives", "Objectifs de transition"),
                field("prerequisites", "Prérequis"),
            ),
            section(
                "Transfert",
                field("handover", "Transfert des livrables"),
                field("data_migration", "Migration des données", False),
                field("training", "Formation"),
            ),
            section(
                "Exploitation",
                field("operational_readiness", "Préparation opérationnelle"),
                field("support_model", "Support post-transition"),
                field("rollback", "Repli et continuité"),
            ),
        ),
    ),
    "ORGANISATIONAL_IMPLEMENTATION_PLAN": ArtifactSchema(
        "ORGANISATIONAL_IMPLEMENTATION_PLAN",
        "Plan de Mise en Œuvre Organisationnelle",
        "PLANNING",
        "Planifier les changements de processus, de compétences et d’adoption.",
        (
            section(
                "Impacts",
                field("impact_analysis", "Analyse des impacts"),
                field("readiness", "État de préparation"),
            ),
            section(
                "Changement",
                field("change_actions", "Actions de changement"),
                field("communication", "Communication du changement"),
                field("training", "Développement des compétences"),
            ),
            section(
                "Adoption",
                field("adoption_measures", "Mesures d’adoption"),
                field("resistance", "Gestion des résistances"),
                field("sustainability", "Pérennisation"),
            ),
        ),
    ),
    "REQUIREMENTS_MANAGEMENT_PLAN": ArtifactSchema(
        "REQUIREMENTS_MANAGEMENT_PLAN",
        "Plan de Gestion des Besoins",
        "PLANNING",
        "Définir comment les exigences sont recueillies, suivies et vérifiées.",
        (
            section(
                "Cycle des besoins",
                field("elicitation", "Recueil"),
                field("analysis", "Analyse et documentation"),
                field("prioritisation", "Priorisation"),
            ),
            section(
                "Contrôle",
                field("approval", "Revue et approbation"),
                field("change_process", "Gestion des changements"),
                field("traceability", "Traçabilité"),
            ),
            section(
                "Vérification",
                field("verification", "Méthodes de vérification"),
                field("acceptance_link", "Lien avec l’acceptation"),
            ),
        ),
    ),
    "CHANGE_MANAGEMENT_PLAN": ArtifactSchema(
        "CHANGE_MANAGEMENT_PLAN",
        "Plan de Gestion des Modifications",
        "PLANNING",
        "Définir le contrôle intégré des demandes de modification.",
        (
            section(
                "Soumission",
                field("submission", "Soumission et enregistrement"),
                field("classification", "Classification et priorité"),
            ),
            section(
                "Analyse",
                field("impact_analysis", "Analyse d’impact"),
                field("recommendation", "Recommandation"),
            ),
            section(
                "Décision",
                field("approval_authority", "Autorités d’approbation"),
                field("decision_rules", "Règles de décision"),
            ),
            section(
                "Mise en œuvre",
                field("implementation_control", "Contrôle de mise en œuvre"),
                field("verification", "Vérification"),
                field("communication", "Communication"),
            ),
        ),
    ),
    "RISK_MANAGEMENT_PLAN": ArtifactSchema(
        "RISK_MANAGEMENT_PLAN",
        "Plan de Gestion des Risques",
        "PLANNING",
        "Organiser l’identification, l’évaluation, le traitement et l’escalade des risques.",
        (
            section(
                "Cadre",
                field("categories", "Catégories de risques"),
                field("identification", "Identification"),
            ),
            section(
                "Évaluation",
                field("probability_scale", "Échelle de probabilité"),
                field("impact_scale", "Échelle d’impact"),
                field("tolerance", "Tolérance"),
            ),
            section(
                "Réponse",
                field("strategies", "Stratégies de réponse"),
                field("ownership", "Attribution"),
                field("contingency", "Contingences"),
            ),
            section(
                "Suivi",
                field("review_cadence", "Cadence de revue"),
                field("escalation", "Escalade et rapports"),
            ),
        ),
    ),
    "ISSUE_MANAGEMENT_PLAN": ArtifactSchema(
        "ISSUE_MANAGEMENT_PLAN",
        "Plan de Gestion des Problèmes",
        "PLANNING",
        "Organiser l’identification, la résolution et l’escalade des problèmes.",
        (
            section(
                "Enregistrement",
                field("identification", "Identification et journalisation"),
                field("classification", "Classification et priorité"),
            ),
            section(
                "Résolution",
                field("assignment", "Attribution"),
                field("analysis", "Analyse"),
                field("resolution_process", "Planification et résolution"),
            ),
            section(
                "Contrôle",
                field("monitoring", "Suivi"),
                field("escalation", "Escalade"),
                field("closure", "Vérification et clôture"),
            ),
        ),
    ),
    "QUALITY_MANAGEMENT_PLAN": ArtifactSchema(
        "QUALITY_MANAGEMENT_PLAN",
        "Plan de Gestion de la Qualité",
        "PLANNING",
        "Définir les objectifs, normes et activités d’assurance et de contrôle qualité.",
        (
            section(
                "Objectifs",
                field("quality_objectives", "Objectifs qualité"),
                field("standards", "Normes et référentiels"),
            ),
            section(
                "Assurance",
                field("assurance_activities", "Activités d’assurance"),
                field("reviews", "Revues et audits"),
            ),
            section(
                "Contrôle",
                field("control_activities", "Contrôles"),
                field("acceptance_alignment", "Alignement avec l’acceptation"),
            ),
            section(
                "Amélioration",
                field("nonconformity", "Traitement des non-conformités"),
                field("configuration", "Gestion de configuration"),
                field("improvement", "Amélioration continue"),
            ),
        ),
    ),
    "COMMUNICATIONS_MANAGEMENT_PLAN": ArtifactSchema(
        "COMMUNICATIONS_MANAGEMENT_PLAN",
        "Plan de Communication",
        "PLANNING",
        "Planifier les communications selon les besoins des parties prenantes.",
        (
            section(
                "Objectifs",
                field("communication_objectives", "Objectifs de communication"),
                field("principles", "Principes"),
            ),
            section(
                "Publics",
                field("audiences", "Publics et besoins"),
                field("confidentiality", "Confidentialité"),
            ),
            section(
                "Dispositif",
                field("channels", "Canaux et formats"),
                field("calendar", "Calendrier et fréquence"),
                field("ownership", "Responsabilités"),
            ),
            section(
                "Évaluation",
                field("feedback", "Retour et efficacité"),
                field("records", "Conservation des communications"),
            ),
        ),
    ),
    "MEETING_MINUTES": ArtifactSchema(
        "MEETING_MINUTES",
        "Procès-Verbal de Réunion",
        "EXECUTION",
        "Documenter les échanges, décisions et actions d’une réunion.",
        (
            section(
                "Réunion",
                field("meeting_reference", "Référence et date"),
                field("purpose", "Objet"),
                field("chair", "Présidence"),
            ),
            section(
                "Participants",
                field("participants", "Présents et excusés"),
                field("agenda", "Ordre du jour"),
            ),
            section(
                "Compte rendu",
                field("discussion", "Points discutés"),
                field("decisions", "Décisions prises"),
                field("actions", "Actions convenues"),
            ),
            section(
                "Approbation",
                field("next_meeting", "Prochaine réunion", False),
                field("minutes_approval", "Approbation du procès-verbal"),
            ),
        ),
    ),
    "PROJECT_REPORT": ArtifactSchema(
        "PROJECT_REPORT",
        "Rapport sur le Projet",
        "EXECUTION",
        "Communiquer une vue consolidée de la performance et des prévisions.",
        (
            section(
                "Période",
                field("reporting_period", "Période couverte"),
                field("executive_summary", "Synthèse exécutive"),
            ),
            section(
                "Performance",
                field("scope_status", "Périmètre et livrables"),
                field("schedule_status", "Échéancier"),
                field("cost_status", "Coûts"),
                field("quality_status", "Qualité"),
            ),
            section(
                "Pilotage",
                field("risk_issue_summary", "Risques et problèmes"),
                field("change_summary", "Modifications"),
                field("decisions_needed", "Décisions attendues"),
            ),
            section(
                "Prévisions",
                field("forecast", "Prévisions"),
                field("next_period", "Travaux de la prochaine période"),
            ),
        ),
    ),
    "QUALITY_REPORT": ArtifactSchema(
        "QUALITY_REPORT",
        "Rapport Qualité",
        "EXECUTION",
        "Présenter les contrôles, constats, actions et tendances qualité.",
        (
            section(
                "Période",
                field("reporting_period", "Période couverte"),
                field("quality_summary", "Synthèse qualité"),
            ),
            section(
                "Assurance",
                field("assurance_completed", "Activités d’assurance réalisées"),
                field("audit_results", "Résultats de revue/audit"),
            ),
            section(
                "Contrôles",
                field("control_results", "Résultats des contrôles"),
                field("findings", "Constats et non-conformités"),
            ),
            section(
                "Actions",
                field("corrective_actions", "Actions correctives"),
                field("trends", "Tendances"),
                field("recommendations", "Recommandations"),
            ),
        ),
    ),
    "PROJECT_END_REPORT": ArtifactSchema(
        "PROJECT_END_REPORT",
        "Rapport de Fin de Projet",
        "CLOSING",
        "Évaluer la performance globale et documenter la clôture.",
        (
            section(
                "Synthèse",
                field("executive_summary", "Synthèse exécutive"),
                field("objectives_achievement", "Atteinte des objectifs"),
            ),
            section(
                "Performance",
                field("scope_performance", "Périmètre et livrables"),
                field("schedule_performance", "Échéancier"),
                field("cost_performance", "Coûts"),
                field("quality_performance", "Qualité"),
            ),
            section(
                "Résultats",
                field("acceptance", "Acceptation finale"),
                field("benefits_outlook", "Perspective des bénéfices"),
                field("transition_outcome", "Transition et exploitation"),
            ),
            section(
                "Clôture",
                field("open_items", "Éléments transférés"),
                field("lessons_summary", "Synthèse des leçons"),
                field("administrative_closure", "Fermeture administrative"),
            ),
        ),
    ),
    "LESSONS_LEARNED": ArtifactSchema(
        "LESSONS_LEARNED",
        "Leçons Apprises",
        "CLOSING",
        "Capitaliser l’expérience du projet et formuler des recommandations réutilisables.",
        (
            section(
                "Contexte",
                field("collection_method", "Méthode de collecte"),
                field("participants", "Contributeurs"),
            ),
            section(
                "Expérience",
                field("successes", "Réussites et bonnes pratiques"),
                field("challenges", "Difficultés et écueils"),
                field("root_causes", "Causes profondes"),
            ),
            section(
                "Capitalisation",
                field("lessons", "Leçons formulées"),
                field("recommendations", "Recommandations"),
                field("follow_up", "Responsables et suivi"),
            ),
        ),
    ),
}


class ArtifactDataService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def load(self, project_id: str, artifact_code: str) -> dict[str, str]:
        self.schema(artifact_code)
        setting = self.session.scalar(
            select(SettingModel).where(
                SettingModel.project_id == project_id,
                SettingModel.key == self.key(artifact_code),
            )
        )
        if setting is None:
            return {}
        try:
            raw = json.loads(setting.value_json)
        except json.JSONDecodeError:
            return {}
        return {str(key): str(value) for key, value in raw.items() if value is not None}

    def save(
        self,
        project_id: str,
        artifact_code: str,
        values: dict[str, str],
        *,
        actor: str = "local",
    ) -> None:
        schema = self.schema(artifact_code)
        allowed = {field.code for section in schema.sections for field in section.fields}
        clean = {key: value.strip() for key, value in values.items() if key in allowed}
        setting = self.session.scalar(
            select(SettingModel).where(
                SettingModel.project_id == project_id,
                SettingModel.key == self.key(artifact_code),
            )
        )
        old = setting.value_json if setting else None
        payload = json.dumps(clean, ensure_ascii=False, sort_keys=True)
        if setting is None:
            setting = SettingModel(
                project_id=project_id, key=self.key(artifact_code), value_json=payload
            )
            self.session.add(setting)
            self.session.flush()
        else:
            setting.value_json = payload
        document = self.session.scalar(
            select(DocumentModel).where(
                DocumentModel.project_id == project_id,
                DocumentModel.artifact_code == artifact_code,
            )
        )
        if document:
            document.updated_at = utcnow()
        AuditService(self.session).record(
            project_id,
            "artifact_data",
            setting.id,
            f"SAVE:{artifact_code}",
            old=old,
            new=clean,
            actor=actor,
        )
        self.session.flush()

    def completion(self, project_id: str, artifact_code: str) -> int:
        schema = self.schema(artifact_code)
        values = self.load(project_id, artifact_code)
        required = [
            field for section in schema.sections for field in section.fields if field.required
        ]
        if not required:
            return 100
        completed = sum(bool(values.get(field.code, "").strip()) for field in required)
        return round(completed * 100 / len(required))

    @staticmethod
    def schema(artifact_code: str) -> ArtifactSchema:
        try:
            return ARTIFACT_SCHEMAS[artifact_code]
        except KeyError as exc:
            raise ValueError(f"Schéma d'artefact inconnu : {artifact_code}") from exc

    @staticmethod
    def key(artifact_code: str) -> str:
        return f"artifact_data:{artifact_code}"
