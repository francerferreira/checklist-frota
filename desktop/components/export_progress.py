from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, QThread, QTimer, Qt, Signal, Slot, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QProgressBar, QVBoxLayout

from components.confirmation_dialog import show_notice
from theme import configure_dialog_window, style_card


ProgressCallback = Callable[[int, str], None]
ExportTask = Callable[[ProgressCallback], object]


def open_exported_pdf(result: object) -> bool:
    if not isinstance(result, (str, Path)):
        return False
    path = Path(result)
    if path.suffix.lower() != ".pdf":
        return False
    if not path.exists():
        return False
    return QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.resolve())))


class ExportWorker(QObject):
    progress = Signal(int, str)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, task: ExportTask):
        super().__init__()
        self._task = task

    @Slot()
    def run(self):
        try:
            result = self._task(lambda value, message="": self.progress.emit(value, message))
            self.progress.emit(100, "Relatório finalizado")
            self.finished.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))


class ExportTaskController(QObject):
    completed = Signal(object)
    errored = Signal(str)

    def __init__(
        self,
        parent,
        title: str,
        task: ExportTask,
        *,
        success_title: str = "PDF gerado",
        success_template: str = "Arquivo salvo em:\n{result}",
        failure_title: str = "Falha ao exportar PDF",
        icon_name: str = "reports",
    ):
        super().__init__(parent)
        self.parent_widget = parent
        self.task = task
        self.success_title = success_title
        self.success_template = success_template
        self.failure_title = failure_title
        self.icon_name = icon_name
        self.dialog = ExportProgressDialog(title, parent)
        self.thread = QThread(parent)
        self.worker = ExportWorker(task)
        self.worker.moveToThread(self.thread)

        self.completed.connect(self._handle_completed)
        self.errored.connect(self._handle_failed)

    def start(self):
        store = getattr(self.parent_widget, "_export_task_controllers", None)
        if store is None:
            store = []
            setattr(self.parent_widget, "_export_task_controllers", store)
        store.append(self)

        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.dialog.set_progress)
        self.worker.finished.connect(lambda result: self.completed.emit(result))
        self.worker.failed.connect(lambda message: self.errored.emit(message))
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.failed.connect(self.worker.deleteLater)
        self.thread.finished.connect(self._cleanup)
        self.thread.finished.connect(self.thread.deleteLater)

        self.dialog.show()
        self.thread.start()
        return self

    def _handle_completed(self, result):
        self.dialog.mark_finished()
        if self.thread.isRunning():
            self.thread.quit()
        show_notice(
            self.parent_widget,
            self.success_title,
            self.success_template.format(result=result),
            icon_name=self.icon_name,
        )
        open_exported_pdf(result)
        self.dialog.accept()

    def _handle_failed(self, message: str):
        self.dialog.mark_failed(message)
        if self.thread.isRunning():
            self.thread.quit()
        show_notice(self.parent_widget, self.failure_title, message, icon_name="warning")
        self.dialog.accept()

    def _cleanup(self):
        store = getattr(self.parent_widget, "_export_task_controllers", None)
        if store and self in store:
            store.remove(self)


def start_export_task(
    parent,
    title: str,
    task: ExportTask,
    *,
    success_title: str = "PDF gerado",
    success_template: str = "Arquivo salvo em:\n{result}",
    failure_title: str = "Falha ao exportar PDF",
    icon_name: str = "reports",
) -> ExportTaskController:
    return ExportTaskController(
        parent,
        title,
        task,
        success_title=success_title,
        success_template=success_template,
        failure_title=failure_title,
        icon_name=icon_name,
    ).start()


class ExportProgressDialog(QDialog):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self._target_value = 0
        self._display_value = 0
        self._finished = False

        self.setWindowTitle(title)
        configure_dialog_window(self, width=560, height=260, min_width=460, min_height=220)
        style_card(self)
        self.setModal(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(14)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("DialogInfoValue")
        self.title_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self.status_label = QLabel("Preparando exportação")
        self.status_label.setObjectName("SectionCaption")
        self.status_label.setWordWrap(True)

        progress_row = QHBoxLayout()
        progress_row.setSpacing(12)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(16)
        self.progress.setStyleSheet(
            """
            QProgressBar {
                background: #E2E8F0;
                border: 1px solid rgba(37, 99, 235, 0.18);
                border-radius: 8px;
            }
            QProgressBar::chunk {
                background: #2563EB;
                border-radius: 8px;
            }
            """
        )

        self.percent_label = QLabel("0%")
        self.percent_label.setObjectName("DialogInfoValue")
        self.percent_label.setMinimumWidth(54)
        self.percent_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        progress_row.addWidget(self.progress, 1)
        progress_row.addWidget(self.percent_label)

        hint = QLabel("Você pode continuar usando o sistema enquanto o PDF é gerado.")
        hint.setObjectName("MutedText")
        hint.setWordWrap(True)

        layout.addWidget(self.title_label)
        layout.addWidget(self.status_label)
        layout.addLayout(progress_row)
        layout.addWidget(hint)

        self._timer = QTimer(self)
        self._timer.setInterval(25)
        self._timer.timeout.connect(self._animate_step)
        self._timer.start()

    def set_progress(self, value: int, message: str = ""):
        self._target_value = max(self._target_value, max(0, min(100, int(value))))
        if message:
            self.status_label.setText(message)

    def mark_finished(self):
        self._finished = True
        self._target_value = 100
        self._display_value = 100
        self.progress.setValue(100)
        self.percent_label.setText("100%")
        self.status_label.setText("PDF gerado com sucesso")

    def mark_failed(self, message: str):
        self._finished = True
        self.status_label.setText(message)

    def closeEvent(self, event):
        if self._finished:
            event.accept()
            return
        event.ignore()

    def _animate_step(self):
        if self._display_value >= self._target_value:
            return
        delta = max(1, int((self._target_value - self._display_value) * 0.18))
        self._display_value = min(self._target_value, self._display_value + delta)
        self.progress.setValue(self._display_value)
        self.percent_label.setText(f"{self._display_value}%")
