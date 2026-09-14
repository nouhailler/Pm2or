from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QAbstractItemView, QTreeWidget, QTreeWidgetItem

NAVIGATION_GROUPS = (
    ("Vue d’ensemble", ("Dashboard", "Projet", "Gouvernance")),
    (
        "Étapes du projet",
        ("Lancement", "Planification", "Plan de travail", "Exécution", "Clôture", "Gates"),
    ),
    ("Pilotage", ("Suivi & Contrôle", "Registres", "Traçabilité", "Validation")),
    ("Données et documents", ("Données métier", "Documents")),
    ("Outils avancés", ("Catalogue", "Paramètres")),
)

PAGE_LABELS = {
    "Dashboard": "Tableau de bord",
    "Gates": "Passages de phase",
    "Données métier": "Données du projet",
    "Catalogue": "Catalogue des entités",
}

GROUP_HINTS = {
    "Vue d’ensemble": "Comprendre le projet et son organisation.",
    "Étapes du projet": "Avancer du lancement à la clôture et décider des passages de phase.",
    "Pilotage": "Suivre les écarts, les risques et la cohérence du projet.",
    "Données et documents": "Gérer les exigences, livrables, données métier et documents PM².",
    "Outils avancés": "Accéder au catalogue détaillé des entités et aux paramètres.",
}


class ProjectNavigation(QTreeWidget):
    navigate_requested = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("sidebar")
        self.setHeaderHidden(True)
        self.setColumnCount(1)
        self.setIndentation(14)
        self.setRootIsDecorated(False)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setExpandsOnDoubleClick(False)
        self.setAccessibleName("Navigation du projet par catégories repliables")
        self.page_items: dict[str, QTreeWidgetItem] = {}
        self.groups: dict[str, QTreeWidgetItem] = {}
        self.currentItemChanged.connect(self._current_changed)
        self.itemExpanded.connect(self._update_group_label)
        self.itemCollapsed.connect(self._update_group_label)

    def set_pages(self, names: list[str]) -> None:
        expanded = {name for name, group in self.groups.items() if group.isExpanded()}
        self.clear()
        self.page_items.clear()
        self.groups.clear()
        available = set(names)
        for title, pages in NAVIGATION_GROUPS:
            group = QTreeWidgetItem(self, [title])
            group.setData(0, Qt.ItemDataRole.UserRole + 1, title)
            group.setToolTip(0, GROUP_HINTS[title])
            font = group.font(0)
            font.setBold(True)
            group.setFont(0, font)
            self.groups[title] = group
            for name in pages:
                if name not in available:
                    continue
                item = QTreeWidgetItem(group, [PAGE_LABELS.get(name, name)])
                item.setData(0, Qt.ItemDataRole.UserRole, name)
                item.setToolTip(0, f"Ouvrir : {PAGE_LABELS.get(name, name)}")
                self.page_items[name] = item
            group.setExpanded(title in expanded or title == "Vue d’ensemble")
            self._update_group_label(group)
        if set(self.page_items) != available:
            raise ValueError("Certaines pages ne sont pas classées dans la navigation.")

    def select_page(self, name: str) -> None:
        item = self.page_items.get(name)
        if item is None:
            return
        item.parent().setExpanded(True)
        self.setCurrentItem(item)
        self.scrollToItem(item)

    def _current_changed(
        self, item: QTreeWidgetItem | None, previous: QTreeWidgetItem | None
    ) -> None:
        if item is None:
            return
        name = item.data(0, Qt.ItemDataRole.UserRole)
        if name:
            item.parent().setExpanded(True)
            self.navigate_requested.emit(name)

    def _update_group_label(self, group: QTreeWidgetItem) -> None:
        title = group.data(0, Qt.ItemDataRole.UserRole + 1)
        if title:
            group.setText(0, f"{'▾' if group.isExpanded() else '▸'} {title}")

    def mousePressEvent(self, event: QMouseEvent) -> None:
        item = self.itemAt(event.position().toPoint())
        if (
            item is not None
            and item.parent() is None
            and event.button() == Qt.MouseButton.LeftButton
        ):
            self.setFocus()
            item.setExpanded(not item.isExpanded())
            event.accept()
            return
        super().mousePressEvent(event)
