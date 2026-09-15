from __future__ import annotations

import re
from contextlib import suppress

from PySide6.QtCore import QEvent, QObject, QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractItemView,
    QApplication,
    QComboBox,
    QFormLayout,
    QMenu,
    QMessageBox,
    QTabWidget,
    QWidget,
)


def _key(text: str) -> str:
    """Return a stable lookup key from a visible Qt label."""
    return re.sub(r"\s+", " ", text.replace("&", "").replace("…", "").strip()).casefold()


ACTION_HELP = {
    "nouveau projet": "Créer un projet PM² et renseigner ses informations initiales.",
    "créer un nouveau projet": "Créer un projet PM² et renseigner ses informations initiales.",
    "ouvrir un projet": "Ouvrir une archive de projet PM² existante.",
    "ouvrir un projet .pm2": "Importer et ouvrir une archive de projet au format .pm2.",
    "exporter l’archive .pm2": "Créer une archive .pm2 portable contenant le projet actif.",
    "exporter le projet .pm2": "Créer une archive .pm2 portable contenant le projet actif.",
    "quitter": "Fermer PM² Desktop.",
    "valider la cohérence": "Contrôler les données du projet et afficher les erreurs ou avertissements.",
    "afficher les validations": "Ouvrir la liste des contrôles de cohérence du projet.",
    "fermer administrativement": "Lancer la procédure de fermeture définitive du projet.",
    "fermer définitivement le projet": "Clore le projet après vérification de toutes les conditions requises.",
    "méthodologie du projet": "Consulter la version et le contenu de la méthodologie attachée au projet.",
    "examiner les différences": "Comparer la méthodologie figée du projet avec la version installée.",
    "mettre à niveau": "Remplacer la méthodologie du projet par la version actuellement installée.",
    "actualiser": "Recharger les données et recalculer les indicateurs affichés.",
    "panneau contextuel": "Afficher ou masquer le résumé du projet à droite de l’écran.",
    "à propos": "Afficher la version de l’application et les informations générales.",
    "créer": "Ajouter un nouvel élément dans la vue actuelle.",
    "modifier": "Modifier l’élément actuellement sélectionné.",
    "modifier / renommer": "Modifier ou renommer l’élément sélectionné du plan de travail.",
    "nouvel élément": "Ajouter un lot de travaux, une tâche ou un jalon.",
    "archiver": "Archiver l’élément sélectionné sans perdre son historique.",
    "archiver / supprimer": "Archiver l’élément sélectionné, ou le supprimer si les règles le permettent.",
    "restaurer": "Réactiver l’élément archivé actuellement sélectionné.",
    "monter": "Déplacer l’élément sélectionné avant l’élément précédent.",
    "descendre": "Déplacer l’élément sélectionné après l’élément suivant.",
    "indenter": "Placer l’élément sélectionné sous l’élément précédent.",
    "désindenter": "Remonter l’élément sélectionné d’un niveau dans la hiérarchie.",
    "dépendance +": "Créer une dépendance entre deux tâches du plan de travail.",
    "dépendance −": "Retirer la dépendance actuellement sélectionnée.",
    "changer le statut": "Faire évoluer l’élément sélectionné vers un statut autorisé.",
    "relier l’exigence": "Associer l’exigence sélectionnée à une tâche ou à un livrable.",
    "fiche détaillée": "Afficher toutes les informations de l’élément sélectionné.",
    "ajouter une personne et un rôle": "Ajouter un membre à l’équipe et lui attribuer un rôle PM².",
    "ajouter une partie prenante": "Répertorier une personne ou une organisation concernée par le projet.",
    "affecter r / cm / s / c / i": "Définir les responsabilités RCmSCI pour l’activité sélectionnée.",
    "enregistrer": "Enregistrer les modifications saisies.",
    "faire avancer le document": "Passer le document à la prochaine étape autorisée de son workflow.",
    "enregistrer la checklist": "Conserver l’état et les preuves de la checklist de revue.",
    "enregistrer une décision": "Consigner la décision prise et l’identité du décideur.",
    "créer un lien": "Créer une relation de traçabilité entre deux éléments du projet.",
    "supprimer le lien": "Supprimer le lien de traçabilité actuellement sélectionné.",
    "aller à la cible": "Ouvrir la page correspondant à la cible du lien sélectionné.",
    "générer": "Générer le document dans le format choisi.",
    "aperçu": "Prévisualiser le document sélectionné avant de l’ouvrir ou le diffuser.",
    "ouvrir le dossier": "Ouvrir le dossier contenant les documents générés.",
    "fermer": "Fermer cette fenêtre.",
    "enregistrer le résultat du test": "Consigner le résultat du test d’acceptation sélectionné.",
    "accepter le livrable sélectionné": "Enregistrer l’acceptation formelle du livrable sélectionné.",
    "inclure les archivés": "Afficher aussi les éléments archivés dans la liste.",
    "continuer l’étape actuelle": "Ouvrir l’assistant de la phase actuellement active.",
    "ouvrir les documents": "Consulter les documents du projet fermé.",
    "projet": "Ouvrir les informations générales et le cadrage du projet.",
    "gouvernance": "Ouvrir l’équipe, les parties prenantes et la matrice RCmSCI.",
    "wbs / gantt": "Ouvrir la structure des travaux, les tâches, les dates et les dépendances.",
    "planning": "Ouvrir le plan de travail et son échéancier.",
    "besoins et livrables": "Ouvrir les exigences, livrables et données métier du projet.",
    "tâches": "Ouvrir les tâches dans le plan de travail.",
    "livrables / qualité / réunions": "Ouvrir les livrables, contrôles qualité et réunions.",
    "acceptations": "Ouvrir les données d’acceptation des livrables.",
    "actions résiduelles": "Ouvrir les registres pour traiter les actions encore en cours.",
    "documents": "Ouvrir le catalogue des documents et leurs versions générées.",
    "registres": "Ouvrir les risques, problèmes, décisions et demandes de changement.",
    "contrôles": "Ouvrir les contrôles de cohérence et leurs résultats.",
}

MENU_HELP = {
    "fichier": "Créer, ouvrir ou exporter un projet, puis quitter l’application.",
    "projet": "Contrôler, documenter ou fermer le projet actif.",
    "affichage": "Actualiser l’écran et choisir les panneaux visibles.",
    "outils": "Accéder aux contrôles et outils transversaux du projet.",
    "aide": "Consulter les informations sur PM² Desktop.",
    "projets récents": "Rouvrir rapidement une archive de projet utilisée récemment.",
}

TAB_HELP = {
    "vue d’ensemble": "Afficher la synthèse et les informations principales.",
    "équipe & rôles": "Gérer les membres du projet et leurs rôles PM².",
    "parties prenantes": "Identifier et analyser les parties prenantes du projet.",
    "rcmsci / ram": "Consulter ou modifier la matrice d’affectation des responsabilités.",
    "données": "Afficher les champs et valeurs de l’élément sélectionné.",
    "relations": "Afficher les liens de traçabilité de l’élément sélectionné.",
    "validation": "Afficher les erreurs et avertissements liés à l’élément.",
    "audit": "Afficher l’historique des modifications de l’élément.",
    "acceptation finale": "Préparer et enregistrer l’acceptation finale des livrables.",
    "fermeture administrative": "Vérifier les conditions et fermer administrativement le projet.",
}

FIELD_HELP = {
    "nom": "Saisissez un nom clair et reconnaissable.",
    "référence": "Saisissez l’identifiant court et unique du projet.",
    "code": "Saisissez un code court permettant d’identifier cet élément.",
    "titre": "Saisissez un titre court décrivant cet élément.",
    "description": "Décrivez le contexte, l’objectif et les informations utiles.",
    "chef de projet (pm)": "Indiquez la personne responsable de la gestion quotidienne du projet.",
    "porteur du projet (po)": "Indiquez la personne responsable de la justification métier du projet.",
    "budget approuvé": "Indiquez le montant total approuvé pour le projet.",
    "devise": "Choisissez la devise utilisée pour les montants du projet.",
    "date de début": "Choisissez la date de démarrage prévue du projet.",
    "date de fin cible": "Choisissez la date à laquelle le projet devrait être terminé.",
    "méthodologie": "Version de PM² figée avec le projet afin de préserver sa cohérence.",
    "responsable": "Indiquez la personne chargée du suivi de cet élément.",
    "priorité": "Choisissez le niveau d’urgence ou d’importance.",
    "probabilité (1–5)": "Évaluez la probabilité du risque, de 1 (faible) à 5 (très forte).",
    "impact (1–5)": "Évaluez l’impact du risque, de 1 (faible) à 5 (très fort).",
    "stratégie": "Décrivez la réponse prévue pour traiter ce risque.",
    "résultat": "Décrivez précisément la décision ou le résultat obtenu.",
    "motif": "Expliquez pourquoi cette modification est demandée.",
    "type": "Choisissez la nature de l’élément à créer.",
    "début planifié": "Date à laquelle le travail doit commencer.",
    "fin planifiée": "Date à laquelle le travail doit être terminé.",
    "avancement (%)": "Indiquez la part du travail déjà réalisée, de 0 à 100 %.",
    "coût planifié": "Indiquez le coût prévu pour cet élément.",
    "type source": "Choisissez le type de l’élément à l’origine du lien.",
    "identifiant source": "Saisissez l’identifiant exact de l’élément source.",
    "relation": "Choisissez la nature du lien entre la source et la cible.",
    "type cible": "Choisissez le type de l’élément visé par le lien.",
    "identifiant cible": "Saisissez l’identifiant exact de l’élément cible.",
}


def _action_help(text: str) -> str:
    key = _key(text)
    if key in ACTION_HELP:
        return ACTION_HELP[key]
    if key.startswith("conserver "):
        return "Continuer à utiliser la méthodologie figée avec ce projet."
    if key.startswith("ouvrir "):
        return f"Ouvrir « {text.replace('&', '').strip()} » dans l’application."
    return f"Exécuter l’action « {text.replace('&', '').strip()} »."


def _set_help(widget: QWidget, help_text: str) -> None:
    if not widget.toolTip():
        widget.setToolTip(help_text)
    if not widget.accessibleDescription():
        widget.setAccessibleDescription(widget.toolTip())


def enhance_tooltips(root: QWidget) -> None:
    """Add consistent help to the interactive controls below *root*.

    Existing, deliberately authored tooltips always take precedence.
    """
    widgets = [root, *root.findChildren(QWidget)]

    for form in root.findChildren(QFormLayout):
        for row in range(form.rowCount()):
            label_item = form.itemAt(row, QFormLayout.ItemRole.LabelRole)
            field_item = form.itemAt(row, QFormLayout.ItemRole.FieldRole)
            label = label_item.widget() if label_item else None
            field = field_item.widget() if field_item else None
            if label is None or field is None or not hasattr(label, "text"):
                continue
            label_text = str(label.text()).replace("*", "").strip()
            help_text = FIELD_HELP.get(_key(label_text), f"Renseignez le champ « {label_text} ».")
            _set_help(field, help_text)

    for widget in widgets:
        if isinstance(widget, QAbstractButton):
            text = widget.text().strip()
            if text:
                _set_help(widget, _action_help(text))
        elif isinstance(widget, QAbstractItemView):
            _set_help(
                widget,
                "Sélectionnez un élément pour le consulter ou utiliser les actions disponibles.",
            )
        elif isinstance(widget, QComboBox):
            _set_help(widget, "Ouvrez la liste pour choisir une valeur.")

    for tabs in root.findChildren(QTabWidget):
        for index in range(tabs.count()):
            if tabs.tabToolTip(index):
                continue
            label = tabs.tabText(index).replace("&", "").strip()
            tabs.setTabToolTip(index, TAB_HELP.get(_key(label), f"Afficher l’onglet « {label} »."))
        _set_help(tabs.tabBar(), "Choisissez un onglet pour afficher la section correspondante.")

    for menu in root.findChildren(QMenu):
        menu.setToolTipsVisible(True)
        title = menu.title().replace("&", "").strip()
        tip = MENU_HELP.get(_key(title), f"Afficher les commandes du menu « {title} ».")
        if not menu.menuAction().toolTip():
            menu.menuAction().setToolTip(tip)
        for action in menu.actions():
            _enhance_action(action)

    for action in root.findChildren(QAction):
        _enhance_action(action)


def _enhance_action(action: QAction) -> None:
    if action.isSeparator() or not action.text().strip():
        return
    # QAction initializes its tooltip from its caption; that is a label, not help.
    if not action.toolTip() or _key(action.toolTip()) == _key(action.text()):
        action.setToolTip(_action_help(action.text()))
    if not action.statusTip():
        action.setStatusTip(action.toolTip())


class _TooltipEventFilter(QObject):
    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if event.type() == QEvent.Type.Show and isinstance(watched, QWidget):
            # QMessageBox manages and may recreate native buttons while opening.
            # Custom message boxes are enhanced explicitly before exec().
            if isinstance(watched.window(), QMessageBox):
                return False
            # Some Qt dialogs finalize (and may recreate) their buttons while handling
            # Show. Defer our inspection until that initialization is complete.
            QTimer.singleShot(0, lambda widget=watched: _enhance_if_available(widget))
        return False


def _enhance_if_available(widget: QWidget) -> None:
    # The widget may have been a short-lived popup destroyed before the timer ran.
    with suppress(RuntimeError):
        enhance_tooltips(widget)


def install_tooltip_support(application: QApplication) -> None:
    """Install once; widgets and dialogs created later are handled when shown."""
    if getattr(application, "_pm2_tooltip_filter", None) is not None:
        return
    event_filter = _TooltipEventFilter(application)
    application.installEventFilter(event_filter)
    application._pm2_tooltip_filter = event_filter  # type: ignore[attr-defined]
