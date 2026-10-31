from __future__ import annotations

import os
import sys
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QRunnable, Qt, QThreadPool, QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from pm2 import __version__
from pm2.application.system_settings import SystemSettingsStore
from pm2.application.updates import (
    RELEASE_DATE,
    ReleaseInfo,
    UpdateService,
    install_desktop_shortcut,
)

LEGAL_VERSION = "1"


def asset_path(name: str) -> Path:
    return Path(__file__).resolve().parents[1] / "assets" / name


class _WorkerSignals(QObject):
    finished = Signal(object)
    failed = Signal(str)


class _Worker(QRunnable):
    def __init__(self, operation: Callable[[], object]) -> None:
        super().__init__()
        self.operation = operation
        self.signals = _WorkerSignals()

    def run(self) -> None:
        try:
            self.signals.finished.emit(self.operation())
        except Exception as exc:
            self.signals.failed.emit(str(exc))


class UpdateController(QObject):
    checking = Signal()
    checked = Signal(object)
    update_available = Signal(object)
    failed = Signal(str)
    installation_started = Signal(str)

    def __init__(self, store: SystemSettingsStore, data_dir: Path) -> None:
        super().__init__()
        self.store = store
        self.service = UpdateService()
        self.data_dir = data_dir
        self.pool = QThreadPool.globalInstance()
        self.timer = QTimer(self)
        self.timer.timeout.connect(lambda: self.check_now(manual=False))

    def start(self) -> None:
        settings = self.store.value
        if not settings.automatic_update_checks or os.environ.get("PM2_DISABLE_UPDATE_CHECK"):
            return
        interval = max(1, settings.update_interval_hours) * 60 * 60 * 1000
        self.timer.start(interval)
        QTimer.singleShot(30_000, lambda: self.check_now(manual=False))

    def apply_preferences(self) -> None:
        self.timer.stop()
        self.start()

    def check_now(self, *, manual: bool = True) -> None:
        self.checking.emit()
        worker = _Worker(self.service.latest_release)
        worker.signals.finished.connect(
            lambda value: self._checked(value, manual=manual)
        )
        worker.signals.failed.connect(self.failed)
        self.pool.start(worker)

    def _checked(self, value: object, *, manual: bool) -> None:
        if not isinstance(value, ReleaseInfo):
            self.failed.emit("Réponse de mise à jour inattendue.")
            return
        self.store.record_update_check()
        self.checked.emit(value)
        if value.is_newer:
            self.update_available.emit(value)
            if self.store.value.automatic_update_install:
                self._download_and_install(value)

    def _download_and_install(self, release: ReleaseInfo) -> None:
        worker = _Worker(
            lambda: self.service.download(release, self.data_dir / "updates")
        )
        worker.signals.finished.connect(self._install_package)
        worker.signals.failed.connect(self.failed)
        self.pool.start(worker)

    def _install_package(self, value: object) -> None:
        if not isinstance(value, Path):
            self.failed.emit("Paquet de mise à jour invalide.")
            return
        started, _pid = QProcess.startDetached(
            "pkexec", ["apt-get", "install", "-y", str(value)]
        )
        if started:
            self.installation_started.emit(str(value))
        else:
            self.failed.emit(
                "Le programme d'installation système n'a pas pu démarrer."
            )


class SystemSettingsDialog(QDialog):
    def __init__(
        self,
        store: SystemSettingsStore,
        updates: UpdateController,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.store, self.updates = store, updates
        self.setWindowTitle("Paramètres système")
        self.setMinimumWidth(560)
        layout = QVBoxLayout(self)
        title = QLabel("Paramètres système")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        form = QFormLayout()
        form.addRow("Version installée", QLabel(__version__))
        form.addRow("Date de sortie", QLabel(RELEASE_DATE.strftime("%d.%m.%Y")))
        self.last_check = QLabel(store.value.last_update_check_label)
        form.addRow("Dernière vérification", self.last_check)
        layout.addLayout(form)
        self.auto_check = QCheckBox("Vérifier périodiquement les nouvelles versions")
        self.auto_check.setChecked(store.value.automatic_update_checks)
        self.auto_install = QCheckBox(
            "Télécharger et lancer automatiquement l'installation vérifiée"
        )
        self.auto_install.setChecked(store.value.automatic_update_install)
        self.auto_install.setToolTip(
            "L'empreinte SHA-256 est contrôlée. Linux peut demander votre mot de passe système."
        )
        layout.addWidget(self.auto_check)
        layout.addWidget(self.auto_install)
        actions = QHBoxLayout()
        check = QPushButton("Vérifier les mises à jour")
        check.setObjectName("primaryButton")
        check.clicked.connect(lambda: updates.check_now(manual=True))
        install = QPushButton("Installer l'application")
        install.clicked.connect(self._install_shortcut)
        actions.addWidget(check)
        actions.addWidget(install)
        actions.addStretch()
        layout.addLayout(actions)
        self.status = QLabel("Prêt.")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self._save_and_close)
        layout.addWidget(buttons)
        updates.checking.connect(lambda: self.status.setText("Vérification en cours…"))
        updates.checked.connect(self._show_release)
        updates.failed.connect(lambda message: self.status.setText(f"Échec : {message}"))
        updates.installation_started.connect(
            lambda _path: self.status.setText("Installation système démarrée.")
        )

    def _show_release(self, value: object) -> None:
        self.last_check.setText(self.store.value.last_update_check_label)
        if isinstance(value, ReleaseInfo):
            self.status.setText(
                f"Version {value.version} disponible."
                if value.is_newer
                else "Vous utilisez la dernière version disponible."
            )

    def _install_shortcut(self) -> None:
        try:
            executable = (
                Path(sys.executable)
                if getattr(sys, "frozen", False)
                else Path(sys.argv[0]).resolve()
            )
            launcher = install_desktop_shortcut(
                executable,
                asset_path("pm2-desktop-logo.png"),
                Path.home(),
            )
            QMessageBox.information(
                self,
                "Application installée",
                f"Le raccourci a été ajouté au menu des applications :\n{launcher}",
            )
        except OSError as exc:
            QMessageBox.critical(self, "Installation impossible", str(exc))

    def _save_and_close(self) -> None:
        self.store.value.automatic_update_checks = self.auto_check.isChecked()
        self.store.value.automatic_update_install = self.auto_install.isChecked()
        self.store.save()
        self.updates.apply_preferences()
        self.accept()


class OnboardingDialog(QDialog):
    def __init__(self, store: SystemSettingsStore, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.store = store
        self.setWindowTitle("Bienvenue dans PM² Desktop")
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setMinimumSize(650, 430)
        layout = QVBoxLayout(self)
        self.pages = QStackedWidget()
        layout.addWidget(self.pages)
        self.pages.addWidget(
            self._page(
                "Bienvenue 👋",
                "PM² Desktop vous accompagne du lancement à la clôture. "
                "Vos projets restent stockés localement sur cet ordinateur.",
            )
        )
        legal = QWidget()
        legal_layout = QVBoxLayout(legal)
        legal_layout.addWidget(QLabel("Mentions légales et responsabilité"))
        text = QLabel(
            "Vous êtes responsable des données que vous saisissez, importez ou partagez. "
            "L'auteur et les contributeurs de PM² Desktop ne contrôlent pas leur exactitude, "
            "leur légalité, leur confidentialité ni leur sauvegarde, et ne peuvent être tenus "
            "responsables d'une perte, d'une divulgation ou d'un usage inapproprié. Le logiciel "
            "est fourni sans garantie, conformément à la licence EUPL-1.2. Conservez des "
            "sauvegardes et respectez les règles de votre organisation."
        )
        text.setWordWrap(True)
        legal_layout.addWidget(text)
        self.accept_legal = QCheckBox(
            "J'ai lu ces informations et j'accepte la responsabilité de mes données."
        )
        legal_layout.addWidget(self.accept_legal)
        legal_layout.addStretch()
        self.pages.addWidget(legal)
        self.pages.addWidget(
            self._page(
                "Une aide à chaque étape 💡",
                "Le menu ☰ regroupe les fonctions par catégorie. Des infobulles expliquent "
                "chaque champ et un bandeau contextuel présente chaque écran lors de sa "
                "première ouverture. Les paramètres système contrôlent les mises à jour.",
            )
        )
        controls = QHBoxLayout()
        self.previous = QPushButton("Précédent")
        self.next = QPushButton("Suivant")
        self.previous.clicked.connect(self._previous)
        self.next.clicked.connect(self._next)
        controls.addWidget(self.previous)
        controls.addStretch()
        controls.addWidget(self.next)
        layout.addLayout(controls)
        self._sync_buttons()

    @staticmethod
    def _page(title_text: str, body_text: str) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        title = QLabel(title_text)
        title.setObjectName("welcomeTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body = QLabel(body_text)
        body.setWordWrap(True)
        body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addStretch()
        layout.addWidget(title)
        layout.addSpacing(25)
        layout.addWidget(body)
        layout.addStretch()
        return page

    def _previous(self) -> None:
        self.pages.setCurrentIndex(max(0, self.pages.currentIndex() - 1))
        self._sync_buttons()

    def _next(self) -> None:
        if self.pages.currentIndex() == 1 and not self.accept_legal.isChecked():
            QMessageBox.warning(
                self, "Confirmation requise", "Veuillez confirmer la lecture des mentions."
            )
            return
        if self.pages.currentIndex() == self.pages.count() - 1:
            self.store.value.legal_accepted_version = LEGAL_VERSION
            self.store.save()
            self.accept()
            return
        self.pages.setCurrentIndex(self.pages.currentIndex() + 1)
        self._sync_buttons()

    def _sync_buttons(self) -> None:
        self.previous.setEnabled(self.pages.currentIndex() > 0)
        self.next.setText(
            "Commencer" if self.pages.currentIndex() == self.pages.count() - 1 else "Suivant"
        )

    def reject(self) -> None:
        if self.store.value.legal_accepted_version == LEGAL_VERSION:
            super().reject()
