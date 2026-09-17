from __future__ import annotations

from PySide6.QtWidgets import (
    QLabel,
    QVBoxLayout,
    QWidget,
)

from pm2.ui.page_base import Page as Page
from pm2.ui.traceability_page import TraceabilityPage as TraceabilityPage


class InfoPanel(QWidget):
    def __init__(self, title: str, description: str) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        heading = QLabel(title)
        heading.setObjectName("sectionTitle")
        text = QLabel(description)
        text.setWordWrap(True)
        layout.addWidget(heading)
        layout.addWidget(text)
        layout.addStretch()


