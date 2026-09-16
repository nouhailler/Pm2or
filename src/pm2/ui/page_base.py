from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget


class Page(QWidget):
    """Common contract for navigable project pages."""

    changed = Signal()

    def reload(self) -> None:
        pass
