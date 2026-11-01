from __future__ import annotations

from html import escape

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from pm2.application.knowledge_base import (
    GLOSSARY,
    METHODOLOGIES,
    SELECTION_GUIDE,
    SOURCES,
    TIMELINE,
    GlossaryEntry,
    MethodologyArticle,
    TimelineEvent,
    search_glossary,
    search_methodologies,
)
from pm2.ui.page_base import Page

DETAIL_STYLE = """
<style>
body { color: #172033; font-family: sans-serif; line-height: 1.45; }
h1 { color: #18324a; margin-bottom: 4px; }
h2 { color: #255f85; margin-top: 18px; }
.badge { color: #255f85; font-weight: bold; }
.note { background: #eaf4fb; border-left: 4px solid #255f85; padding: 10px; }
li { margin: 4px 0; }
</style>
"""


def _list(items: tuple[str, ...]) -> str:
    return "<ul>" + "".join(f"<li>{escape(item)}</li>" for item in items) + "</ul>"


class KnowledgePage(Page):
    """Glossaire et encyclopédie de gestion de projet disponibles hors ligne."""

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        title = QLabel("Glossaire & encyclopédie")
        title.setObjectName("pageTitle")
        subtitle = QLabel(
            f"{len(GLOSSARY)} notions, {len(METHODOLOGIES)} approches et une chronologie "
            "pour comprendre la gestion de projet."
        )
        subtitle.setObjectName("pageSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        self.tabs = QTabWidget()
        self.tabs.addTab(self._glossary_tab(), "A–Z Glossaire")
        self.tabs.addTab(self._methodologies_tab(), "Méthodologies")
        self.tabs.addTab(self._timeline_tab(), "Histoire & évolution")
        self.tabs.addTab(self._choose_tab(), "Comment choisir ?")
        self.tabs.addTab(self._sources_tab(), "Sources")
        layout.addWidget(self.tabs, 1)

    def _glossary_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        filters = QHBoxLayout()
        self.glossary_search = QLineEdit()
        self.glossary_search.setPlaceholderText("Rechercher un terme, un alias ou une définition…")
        self.glossary_category = QComboBox()
        self.glossary_category.addItem("Toutes")
        self.glossary_category.addItems(sorted({entry.category for entry in GLOSSARY}))
        self.glossary_count = QLabel()
        filters.addWidget(self.glossary_search, 1)
        filters.addWidget(self.glossary_category)
        filters.addWidget(self.glossary_count)
        layout.addLayout(filters)
        content = QHBoxLayout()
        self.glossary_list = QListWidget()
        self.glossary_list.setMinimumWidth(280)
        self.glossary_detail = QTextBrowser()
        self.glossary_detail.setOpenExternalLinks(True)
        content.addWidget(self.glossary_list, 1)
        content.addWidget(self.glossary_detail, 2)
        layout.addLayout(content, 1)
        self.glossary_search.textChanged.connect(self._filter_glossary)
        self.glossary_category.currentTextChanged.connect(self._filter_glossary)
        self.glossary_list.currentItemChanged.connect(self._show_glossary)
        self._filter_glossary()
        return page

    def _filter_glossary(self, _value: str = "") -> None:
        entries = search_glossary(
            self.glossary_search.text(), self.glossary_category.currentText()
        )
        self.glossary_list.clear()
        for entry in entries:
            item = QListWidgetItem(f"{entry.term}  ·  {entry.category}")
            item.setData(Qt.ItemDataRole.UserRole, entry)
            self.glossary_list.addItem(item)
        self.glossary_count.setText(f"{len(entries)} résultat(s)")
        if entries:
            self.glossary_list.setCurrentRow(0)
        else:
            self.glossary_detail.setHtml(
                DETAIL_STYLE
                + "<h2>Aucun résultat</h2><p>Essayez un mot plus court ou choisissez une autre catégorie.</p>"
            )

    def _show_glossary(
        self, current: QListWidgetItem | None, _previous: QListWidgetItem | None
    ) -> None:
        if current is None:
            return
        entry = current.data(Qt.ItemDataRole.UserRole)
        if not isinstance(entry, GlossaryEntry):
            return
        aliases = (
            f"<p><b>Autres noms :</b> {escape(', '.join(entry.aliases))}</p>"
            if entry.aliases
            else ""
        )
        related = (
            f"<p><b>À rapprocher de :</b> {escape(', '.join(entry.related))}</p>"
            if entry.related
            else ""
        )
        self.glossary_detail.setHtml(
            DETAIL_STYLE
            + f"<h1>{escape(entry.term)}</h1>"
            + f'<p class="badge">{escape(entry.category)}</p>'
            + f"<p>{escape(entry.definition)}</p>{aliases}{related}"
        )

    def _methodologies_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.methodology_search = QLineEdit()
        self.methodology_search.setPlaceholderText(
            "Rechercher une méthode, un principe, un contexte ou une limite…"
        )
        layout.addWidget(self.methodology_search)
        content = QHBoxLayout()
        self.methodology_list = QListWidget()
        self.methodology_list.setMinimumWidth(285)
        self.methodology_detail = QTextBrowser()
        self.methodology_detail.setOpenExternalLinks(True)
        content.addWidget(self.methodology_list, 1)
        content.addWidget(self.methodology_detail, 3)
        layout.addLayout(content, 1)
        self.methodology_search.textChanged.connect(self._filter_methodologies)
        self.methodology_list.currentItemChanged.connect(self._show_methodology)
        self._filter_methodologies()
        return page

    def _filter_methodologies(self, _value: str = "") -> None:
        articles = search_methodologies(self.methodology_search.text())
        self.methodology_list.clear()
        for article in articles:
            item = QListWidgetItem(f"{article.name}\n{article.family}")
            item.setData(Qt.ItemDataRole.UserRole, article)
            self.methodology_list.addItem(item)
        if articles:
            self.methodology_list.setCurrentRow(0)
        else:
            self.methodology_detail.setHtml(
                DETAIL_STYLE + "<h2>Aucune méthodologie trouvée</h2>"
            )

    def _show_methodology(
        self, current: QListWidgetItem | None, _previous: QListWidgetItem | None
    ) -> None:
        if current is None:
            return
        article = current.data(Qt.ItemDataRole.UserRole)
        if not isinstance(article, MethodologyArticle):
            return
        self.methodology_detail.setHtml(
            DETAIL_STYLE
            + f"<h1>{escape(article.name)}</h1>"
            + f'<p class="badge">{escape(article.family)}</p>'
            + f'<p class="note"><b>Origine :</b> {escape(article.origin)}</p>'
            + f"<p>{escape(article.summary)}</p>"
            + "<h2>Principes et repères</h2>"
            + _list(article.principles)
            + f"<h2>Cycle ou fonctionnement</h2><p>{escape(article.lifecycle)}</p>"
            + f"<h2>Quand l'utiliser ?</h2><p>{escape(article.suitable_for)}</p>"
            + "<h2>Forces</h2>"
            + _list(article.strengths)
            + "<h2>Points de vigilance</h2>"
            + _list(article.cautions)
            + f"<h2>Évolution</h2><p>{escape(article.evolution)}</p>"
            + f'<p><a href="{escape(article.source_url)}">Consulter la source de référence ↗</a></p>'
        )

    def _timeline_tab(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)
        self.timeline_list = QListWidget()
        self.timeline_list.setMinimumWidth(330)
        self.timeline_detail = QTextBrowser()
        self.timeline_detail.setOpenExternalLinks(True)
        for event in TIMELINE:
            item = QListWidgetItem(f"{event.year}  —  {event.title}")
            item.setData(Qt.ItemDataRole.UserRole, event)
            self.timeline_list.addItem(item)
        self.timeline_list.currentItemChanged.connect(self._show_timeline)
        layout.addWidget(self.timeline_list, 1)
        layout.addWidget(self.timeline_detail, 2)
        self.timeline_list.setCurrentRow(0)
        return page

    def _show_timeline(
        self, current: QListWidgetItem | None, _previous: QListWidgetItem | None
    ) -> None:
        if current is None:
            return
        event = current.data(Qt.ItemDataRole.UserRole)
        if not isinstance(event, TimelineEvent):
            return
        source = (
            f'<p><a href="{escape(event.source_url)}">Source et approfondissement ↗</a></p>'
            if event.source_url
            else ""
        )
        self.timeline_detail.setHtml(
            DETAIL_STYLE
            + f"<h1>{escape(event.year)}</h1><h2>{escape(event.title)}</h2>"
            + f"<p>{escape(event.description)}</p>{source}"
        )

    def _choose_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        explanation = QLabel(
            "Il n'existe pas de meilleure méthode universelle. Choisissez selon l'incertitude, "
            "le risque, la réglementation, la fréquence du feedback, la taille et la culture. "
            "Une approche hybride doit rester cohérente et explicite."
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)
        table = QTableWidget(len(SELECTION_GUIDE), 3)
        table.setHorizontalHeaderLabels(("Situation", "Point de départ", "Conseil"))
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setWordWrap(True)
        table.verticalHeader().setVisible(False)
        for row, values in enumerate(SELECTION_GUIDE):
            for column, value in enumerate(values):
                table.setItem(row, column, QTableWidgetItem(value))
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        table.resizeRowsToContents()
        layout.addWidget(table, 1)
        warning = QLabel(
            "⚠ Une méthode ne remplace ni le jugement professionnel, ni la gouvernance, ni la "
            "compréhension du domaine. Commencez léger, mesurez, puis adaptez explicitement."
        )
        warning.setWordWrap(True)
        layout.addWidget(warning)
        return page

    def _sources_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        intro = QLabel(
            "Cette synthèse pédagogique distingue méthodes, cadres, standards et approches. "
            "Elle ne remplace pas leurs publications officielles ni une formation certifiante."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)
        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setHtml(
            DETAIL_STYLE
            + "<h1>Sources de référence</h1><ul>"
            + "".join(
                f'<li><a href="{escape(url)}">{escape(label)} ↗</a></li>'
                for label, url in SOURCES
            )
            + "</ul><p>Contenu consultable hors ligne ; les liens nécessitent Internet.</p>"
        )
        layout.addWidget(browser, 1)
        return page


class KnowledgeDialog(QDialog):
    """Accès à l'encyclopédie même lorsqu'aucun projet n'est ouvert."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Glossaire & encyclopédie de la gestion de projet")
        self.resize(1100, 760)
        self.setMinimumSize(820, 600)
        layout = QVBoxLayout(self)
        layout.addWidget(KnowledgePage(), 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
