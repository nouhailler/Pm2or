from __future__ import annotations

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QGraphicsItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from pm2.application.traceability import (
    TraceabilityGraph,
    TraceabilityService,
    TraceGraphNode,
)
from pm2.infrastructure.orm import ProjectModel, TraceLinkModel
from pm2.ui.dialogs import RELATION_LABELS, TraceLinkDialog
from pm2.ui.page_base import Page

TYPE_LABELS = {
    "requirement": "Exigence",
    "task": "Tâche",
    "deliverable": "Livrable",
    "acceptance_criterion": "Critère",
    "acceptance_test": "Test d'acceptation",
    "risk": "Risque",
    "risk_action": "Mitigation",
    "change": "Modification",
    "change_impact": "Impact",
    "issue": "Problème",
    "decision": "Décision",
    "document": "Document",
    "transition_activity": "Transition",
}

TYPE_COLORS = {
    "requirement": "#dceeff",
    "task": "#e6f4ea",
    "deliverable": "#fff1cc",
    "acceptance_criterion": "#f3e8ff",
    "acceptance_test": "#eadcff",
    "risk": "#ffe4e0",
    "risk_action": "#fff0e0",
    "change": "#e8e8ff",
    "change_impact": "#f0e8ff",
}

IMPACT_LABELS = {
    "Schedule": "Planning",
    "Cost": "Coût",
    "Scope": "Périmètre",
    "Quality": "Qualité",
    "Risk": "Risque",
}

CHAIN_ROOTS = {"requirements": "requirement", "risks": "risk", "changes": "change"}

CHAIN_TYPES = {
    "requirements": {
        "requirement",
        "task",
        "deliverable",
        "acceptance_criterion",
        "acceptance_test",
    },
    "risks": {"risk", "risk_action", "task", "deliverable"},
    "changes": {
        "change",
        "change_impact",
        "task",
        "risk",
        "requirement",
        "deliverable",
    },
}


def _relation_label(relation: str) -> str:
    return RELATION_LABELS.get(relation, relation)


def _node_label(node: TraceGraphNode) -> str:
    if node.entity_type == "change_impact":
        return IMPACT_LABELS.get(node.label, node.label)
    return node.label


def _shorten(text: str, limit: int = 38) -> str:
    if len(text) <= limit:
        return text
    cut = text[: limit - 1]
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return f"{cut.rstrip()}…"


class TraceabilityPage(Page):
    """Visual graph, typed links and project orphan analysis."""

    changed = Signal()
    navigate_requested = Signal(str)

    def __init__(self, session: Session, project: ProjectModel) -> None:
        super().__init__()
        self.session, self.project = session, project
        self._graph = TraceabilityGraph((), ())
        layout = QVBoxLayout(self)
        heading = QHBoxLayout()
        title = QLabel("Graphe de traçabilité")
        title.setObjectName("pageTitle")
        heading.addWidget(title)
        heading.addStretch()
        add = QPushButton("Créer un lien")
        add.setObjectName("primaryButton")
        add.clicked.connect(self._add)
        remove = QPushButton("Supprimer le lien")
        remove.clicked.connect(self._remove)
        heading.addWidget(add)
        heading.addWidget(remove)
        layout.addLayout(heading)
        subtitle = QLabel(
            "Suivez les chaînes Exigence → Tâche → Livrable → Acceptation, "
            "les réponses aux risques et les impacts des changements."
        )
        subtitle.setObjectName("pageSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        self._build_graph_tab()
        self._build_links_tab()
        self._build_orphans_tab()
        self.reload()

    def _build_graph_tab(self) -> None:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        toolbar = QHBoxLayout()
        self.chain_filter = QComboBox()
        self.chain_filter.addItem("Tout le projet", "")
        self.chain_filter.addItem("Exigences → Acceptation", "requirements")
        self.chain_filter.addItem("Risques → Mitigations", "risks")
        self.chain_filter.addItem("Changements → Impacts", "changes")
        self.chain_filter.currentIndexChanged.connect(lambda: self._reload_graph())
        navigate = QPushButton("Ouvrir l'objet sélectionné")
        navigate.clicked.connect(self._navigate_graph)
        toolbar.addWidget(QLabel("Chaîne"))
        toolbar.addWidget(self.chain_filter)
        toolbar.addWidget(navigate)
        toolbar.addStretch()
        layout.addLayout(toolbar)
        self.graph_summary = QLabel()
        layout.addWidget(self.graph_summary)
        self.scene = QGraphicsScene(self)
        self.graph_view = QGraphicsView(self.scene)
        self.graph_view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.graph_view.setMinimumHeight(360)
        layout.addWidget(self.graph_view)
        self.tabs.addTab(widget, "Graphe")

    def _build_links_tab(self) -> None:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        toolbar = QHBoxLayout()
        self.filter = QComboBox()
        self.filter.addItem("Toutes les relations", "")
        for relation_type in sorted(TraceabilityService.RELATION_TYPES, key=_relation_label):
            self.filter.addItem(_relation_label(relation_type), relation_type)
        self.filter.currentIndexChanged.connect(self.reload)
        navigate = QPushButton("Aller à la cible")
        navigate.clicked.connect(self._navigate)
        toolbar.addWidget(self.filter)
        toolbar.addWidget(navigate)
        toolbar.addStretch()
        layout.addLayout(toolbar)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Source", "Relation", "Cible", "Critique", "Créé le"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)
        self.tabs.addTab(widget, "Liens explicites")

    def _build_orphans_tab(self) -> None:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        self.orphan_summary = QLabel()
        self.orphan_summary.setObjectName("sectionTitle")
        layout.addWidget(self.orphan_summary)
        navigate = QPushButton("Corriger les objets sélectionnés")
        navigate.clicked.connect(self._navigate_orphan)
        layout.addWidget(navigate, alignment=Qt.AlignmentFlag.AlignLeft)
        self.orphans = QTableWidget(0, 4)
        self.orphans.setHorizontalHeaderLabels(
            ["Contrôle", "Résultat", "Objets concernés", "Correction"]
        )
        self.orphans.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.orphans.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.orphans.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.orphans)
        self.tabs.addTab(widget, "Objets orphelins")

    def _navigate(self) -> None:
        row = self.table.currentRow()
        target_item = self.table.item(row, 2) if row >= 0 else None
        if target_item is not None:
            self.navigate_requested.emit(
                self._destination(target_item.data(Qt.ItemDataRole.UserRole))
            )

    def _navigate_graph(self) -> None:
        selected = self.scene.selectedItems()
        if selected:
            page = selected[0].data(2)
            if page:
                self.navigate_requested.emit(str(page))

    def _navigate_orphan(self) -> None:
        row = self.orphans.currentRow()
        item = self.orphans.item(row, 0) if row >= 0 else None
        if item is not None:
            page = item.data(Qt.ItemDataRole.UserRole)
            if page:
                self.navigate_requested.emit(str(page))

    def _add(self) -> None:
        dialog = TraceLinkDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            values = dialog.values()
            TraceabilityService(self.session).link(
                self.project.id,
                values["source_type"],
                values["source_id"],
                values["target_type"],
                values["target_id"],
                values["relation_type"],
            )
            self.session.commit()
            self.reload()
            self.changed.emit()
        except Exception as exc:
            self.session.rollback()
            QMessageBox.critical(self, "Lien impossible", str(exc))

    def _remove(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        try:
            source_item = self.table.item(row, 0)
            if source_item is None:
                return
            TraceabilityService(self.session).unlink(source_item.data(Qt.ItemDataRole.UserRole))
            self.session.commit()
            self.reload()
            self.changed.emit()
        except Exception as exc:
            self.session.rollback()
            QMessageBox.critical(self, "Suppression impossible", str(exc))

    def reload(self) -> None:
        service = TraceabilityService(self.session)
        self._graph = service.graph(self.project.id)
        labels = {node.key: node for node in self._graph.nodes}
        statement = select(TraceLinkModel).where(TraceLinkModel.project_id == self.project.id)
        relation = self.filter.currentData()
        if relation:
            statement = statement.where(TraceLinkModel.relation_type == relation)
        links = self.session.scalars(statement.order_by(TraceLinkModel.created_at.desc())).all()
        self.table.setRowCount(len(links))
        for row, link in enumerate(links):
            source = labels.get(f"{link.source_type}:{link.source_id}")
            target = labels.get(f"{link.target_type}:{link.target_id}")
            values = (
                self._node_text(source, link.source_type, link.source_id),
                _relation_label(link.relation_type),
                self._node_text(target, link.target_type, link.target_id),
                "Oui" if link.critical else "Non",
                str(link.created_at),
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, link.id)
                if column == 2:
                    item.setData(Qt.ItemDataRole.UserRole, link.target_type)
                self.table.setItem(row, column, item)
        self._reload_graph()
        self._reload_orphans(service)

    def _reload_graph(self) -> None:
        self.scene.clear()
        chain = self.chain_filter.currentData()
        allowed_types = CHAIN_TYPES.get(str(chain)) if chain else None
        nodes = [
            node
            for node in self._graph.nodes
            if allowed_types is None or node.entity_type in allowed_types
        ]
        if chain:
            nodes = self._chain_nodes(nodes, CHAIN_ROOTS[str(chain)])
        node_keys = {node.key for node in nodes}
        edges = [
            edge
            for edge in self._graph.edges
            if edge.source in node_keys and edge.target in node_keys
        ]
        summary = f"{len(nodes)} objets · {len(edges)} relations"
        if chain and not edges:
            summary += " — aucune relation pour cette chaîne : complétez les registres ou créez un lien"
        self.graph_summary.setText(summary)
        layer_order = {
            "requirement": 0,
            "risk": 0,
            "change": 0,
            "issue": 0,
            "decision": 0,
            "risk_action": 1,
            "change_impact": 1,
            "task": 1,
            "document": 1,
            "transition_activity": 1,
            "deliverable": 2,
            "acceptance_criterion": 3,
            "acceptance_test": 4,
        }
        grouped: dict[int, list[TraceGraphNode]] = {}
        for node in nodes:
            layer = layer_order.get(node.entity_type, 1)
            if node.entity_type == "change_impact" and not node.entity_id.endswith(":impact"):
                layer = 2
            grouped.setdefault(layer, []).append(node)
        positions: dict[str, tuple[float, float]] = {}
        width, height = 190.0, 70.0
        column_step, row_step = 330.0, 105.0
        for layer, layer_nodes in grouped.items():
            for row, node in enumerate(layer_nodes):
                positions[node.key] = (30.0 + layer * column_step, 30.0 + row * row_step)
        edge_pen = QPen(QColor("#718096"), 1.6)
        for edge in edges:
            if edge.source not in positions or edge.target not in positions:
                continue
            source_x, source_y = positions[edge.source]
            target_x, target_y = positions[edge.target]
            start = QPointF(source_x + width, source_y + height / 2)
            end = QPointF(target_x, target_y + height / 2)
            if target_x - source_x == column_step:
                self.scene.addLine(start.x(), start.y(), end.x(), end.y(), edge_pen)
                label_center = QPointF((start.x() + end.x()) / 2, (start.y() + end.y()) / 2)
            else:
                # Les colonnes et les rangées laissent des couloirs libres : le lien les
                # emprunte pour ne passer derrière aucun nœud intermédiaire.
                gutter = source_y + height + (row_step - height) / 2
                path = QPainterPath(start)
                path.lineTo(start.x() + 20, start.y())
                path.lineTo(start.x() + 20, gutter)
                path.lineTo(end.x() - 20, gutter)
                path.lineTo(end.x() - 20, end.y())
                path.lineTo(end)
                self.scene.addPath(path, edge_pen)
                label_center = QPointF((start.x() + end.x()) / 2, gutter)
            arrow = QPolygonF(
                [
                    QPointF(end.x(), end.y()),
                    QPointF(end.x() - 9, end.y() - 5),
                    QPointF(end.x() - 9, end.y() + 5),
                ]
            )
            self.scene.addPolygon(arrow, edge_pen, QBrush(QColor("#718096")))
            relation = self.scene.addText(_relation_label(edge.relation))
            relation.setDefaultTextColor(QColor("#5b677a"))
            relation.setPos(
                label_center.x() - relation.boundingRect().width() / 2,
                label_center.y() - 20,
            )
        for node in nodes:
            x, y = positions[node.key]
            color = QColor(TYPE_COLORS.get(node.entity_type, "#eef2f7"))
            rectangle = self.scene.addRect(
                0, 0, width, height, QPen(QColor("#52677a"), 1.4), QBrush(color)
            )
            rectangle.setPos(x, y)
            rectangle.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
            rectangle.setData(0, node.entity_type)
            rectangle.setData(1, node.entity_id)
            rectangle.setData(2, node.page)
            title = TYPE_LABELS.get(
                node.entity_type, node.entity_type.replace("_", " ").title()
            )
            label = _node_label(node)
            rectangle.setToolTip(f"{title}\n{label} — {node.title}")
            text = self.scene.addText(f"{title}\n{label} — {_shorten(node.title)}")
            text.setDefaultTextColor(QColor("#172033"))
            text.setTextWidth(width - 14)
            text.setParentItem(rectangle)
            text.setPos(7, 5)
            text.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        bounds = self.scene.itemsBoundingRect().adjusted(-20, -20, 20, 20)
        self.scene.setSceneRect(bounds)

    def _chain_nodes(
        self, nodes: list[TraceGraphNode], root_type: str
    ) -> list[TraceGraphNode]:
        """Keep the chain's root objects and what can be reached from them."""
        keys = {node.key for node in nodes}
        reached = {node.key for node in nodes if node.entity_type == root_type}
        pending = list(reached)
        while pending:
            current = pending.pop()
            for edge in self._graph.edges:
                if edge.source == current and edge.target in keys and edge.target not in reached:
                    reached.add(edge.target)
                    pending.append(edge.target)
        return [node for node in nodes if node.key in reached]

    def _reload_orphans(self, service: TraceabilityService) -> None:
        findings = service.orphan_findings(self.project.id)
        total = sum(finding.count for finding in findings)
        self.orphan_summary.setText(
            "✓ Aucun objet orphelin"
            if total == 0
            else f"⚠ {total} objet(s) orphelin(s) détecté(s)"
        )
        self.orphans.setRowCount(len(findings))
        for row, finding in enumerate(findings):
            values = (
                finding.label,
                "✓ 0" if finding.count == 0 else f"⚠ {finding.count}",
                ", ".join(finding.entity_labels) or "—",
                f"Ouvrir {finding.page}",
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, finding.page)
                if finding.count:
                    item.setBackground(QColor("#fff4d6"))
                    item.setForeground(QColor("#7a4b00"))
                self.orphans.setItem(row, column, item)

    @staticmethod
    def _node_text(
        node: TraceGraphNode | None, entity_type: str, entity_id: str
    ) -> str:
        if node is not None:
            label = TYPE_LABELS.get(entity_type, entity_type)
            return f"{label} · {_node_label(node)} — {node.title}"
        return f"{entity_type} · {entity_id}"

    @staticmethod
    def _destination(entity_type: str) -> str:
        destinations = {
            "task": "Plan de travail",
            "wbs_node": "Plan de travail",
            "requirement": "Données métier",
            "deliverable": "Données métier",
            "acceptance_criterion": "Données métier",
            "acceptance_test": "Données métier",
            "transition_activity": "Données métier",
            "risk": "Registres",
            "risk_action": "Registres",
            "issue": "Registres",
            "decision": "Registres",
            "change": "Registres",
            "change_impact": "Registres",
            "document": "Documents",
        }
        return destinations.get(entity_type, "Traçabilité")
