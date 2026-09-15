from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from pm2.ui.tooltips import enhance_tooltips, install_tooltip_support


def test_enhance_tooltips_covers_actions_tabs_and_form_fields(qapp) -> None:
    root = QWidget()
    layout = QVBoxLayout(root)

    create = QPushButton("Créer")
    layout.addWidget(create)

    form_widget = QWidget()
    form = QFormLayout(form_widget)
    reference = QLineEdit()
    choice = QComboBox()
    form.addRow("Référence *", reference)
    form.addRow("Catégorie", choice)
    layout.addWidget(form_widget)

    tabs = QTabWidget()
    tabs.addTab(QLabel("Contenu"), "Validation")
    layout.addWidget(tabs)

    menu = QMenu("&Fichier", root)
    action = menu.addAction("Nouveau projet…")

    enhance_tooltips(root)

    assert "nouvel élément" in create.toolTip().lower()
    assert "unique" in reference.toolTip().lower()
    assert choice.toolTip() == "Renseignez le champ « Catégorie »."
    assert "erreurs" in tabs.tabToolTip(0).lower()
    assert menu.toolTipsVisible()
    assert "créer un projet" in action.toolTip().lower()
    assert action.statusTip() == action.toolTip()
    assert create.accessibleDescription() == create.toolTip()


def test_existing_tooltip_is_preserved(qapp) -> None:
    button = QPushButton("Créer")
    button.setToolTip("Aide spécifique")

    enhance_tooltips(button)

    assert button.toolTip() == "Aide spécifique"


def test_support_enhances_dialogs_created_after_installation(qapp, qtbot) -> None:
    install_tooltip_support(qapp)
    dialog = QWidget()
    button = QPushButton("Modifier", dialog)
    qtbot.addWidget(dialog)

    dialog.show()
    qtbot.waitUntil(lambda: bool(button.toolTip()))

    assert "sélectionné" in button.toolTip().lower()
