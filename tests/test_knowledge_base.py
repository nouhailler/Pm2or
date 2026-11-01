from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QTableWidget

from pm2.application.knowledge_base import (
    GLOSSARY,
    METHODOLOGIES,
    SELECTION_GUIDE,
    TIMELINE,
    search_glossary,
    search_methodologies,
)
from pm2.ui.knowledge_page import KnowledgeDialog, KnowledgePage


def test_knowledge_searches_terms_aliases_categories_and_articles() -> None:
    assert len(GLOSSARY) >= 60
    assert len(METHODOLOGIES) >= 10
    assert len(TIMELINE) >= 15
    assert search_glossary("critical path")[0].term == "Chemin critique"
    assert {entry.term for entry in search_glossary(category="Valeur acquise")} >= {
        "CPI",
        "SPI",
    }
    assert search_methodologies("empirisme")[0].name == "Scrum"
    assert any(article.name == "PM²" for article in search_methodologies("Commission"))


def test_knowledge_page_filters_and_explains_content(qtbot: Any) -> None:
    page = KnowledgePage()
    qtbot.addWidget(page)

    assert page.tabs.count() == 5
    assert page.glossary_list.count() == len(GLOSSARY)
    page.glossary_search.setText("chemin critique")
    assert page.glossary_list.count() == 1
    assert "marge totale" in page.glossary_detail.toPlainText().casefold()

    page.methodology_search.setText("Toyota")
    assert page.methodology_list.count() == 1
    assert "Lean" in page.methodology_detail.toPlainText()
    assert page.timeline_list.count() == len(TIMELINE)
    tables = page.findChildren(QTableWidget)
    assert any(table.rowCount() == len(SELECTION_GUIDE) for table in tables)


def test_knowledge_dialog_is_available_without_a_project(qtbot: Any) -> None:
    dialog = KnowledgeDialog()
    qtbot.addWidget(dialog)

    assert dialog.windowTitle().startswith("Glossaire")
    assert dialog.findChild(KnowledgePage) is not None
