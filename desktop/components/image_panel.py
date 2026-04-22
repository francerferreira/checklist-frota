from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout

from theme import configure_dialog_window, style_card


class PreviewImageLabel(QLabel):
    double_clicked = Signal()

    def mouseDoubleClickEvent(self, event):
        self.double_clicked.emit()
        super().mouseDoubleClickEvent(event)


class ImagePreviewDialog(QDialog):
    def __init__(self, pixmap: QPixmap, title: str, parent=None):
        super().__init__(parent)
        self._pixmap = pixmap
        self._normal_geometry = None
        self._is_full_screen = False

        self.setWindowTitle(title or "Visualizacao da imagem")
        configure_dialog_window(self, width=1080, height=760, min_width=820, min_height=600)
        style_card(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        header = QFrame()
        header.setObjectName("DialogHeader")
        header.setAttribute(Qt.WA_StyledBackground, True)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(18, 18, 18, 18)
        header_layout.setSpacing(14)

        title_wrap = QVBoxLayout()
        title_wrap.setContentsMargins(0, 0, 0, 0)
        title_wrap.setSpacing(4)

        title_label = QLabel(title or "Imagem")
        title_label.setObjectName("DialogHeaderTitle")
        subtitle_label = QLabel("Visualizacao ampliada. Use duplo clique ou F11 para tela cheia; Esc para sair.")
        subtitle_label.setObjectName("DialogHeaderSubtitle")
        subtitle_label.setWordWrap(True)
        title_wrap.addWidget(title_label)
        title_wrap.addWidget(subtitle_label)

        self.fullscreen_button = QPushButton("Tela cheia")
        self.fullscreen_button.setProperty("variant", "primary")
        self.fullscreen_button.clicked.connect(self.toggle_full_screen)

        close_button = QPushButton("Fechar")
        close_button.clicked.connect(self.accept)

        header_layout.addLayout(title_wrap, 1)
        header_layout.addWidget(self.fullscreen_button, 0, Qt.AlignTop)
        header_layout.addWidget(close_button, 0, Qt.AlignTop)

        self.image_label = PreviewImageLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumHeight(520)
        self.image_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.image_label.setCursor(Qt.PointingHandCursor)
        self.image_label.setStyleSheet(
            "background:qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0F172A, stop:1 #1E293B); "
            "border-radius:22px; border:1px solid rgba(37,99,235,0.28);"
        )
        self.image_label.double_clicked.connect(self.toggle_full_screen)

        layout.addWidget(header)
        layout.addWidget(self.image_label, 1)

        self._render()

    def toggle_full_screen(self):
        if self._is_full_screen:
            self.showNormal()
            if self._normal_geometry is not None:
                self.setGeometry(self._normal_geometry)
            self.fullscreen_button.setText("Tela cheia")
            self._is_full_screen = False
        else:
            self._normal_geometry = self.geometry()
            self.showFullScreen()
            self.fullscreen_button.setText("Sair da tela cheia")
            self._is_full_screen = True
        self._render()

    def _render(self):
        if self._pixmap.isNull():
            return
        target_size = self.image_label.contentsRect().size()
        if target_size.width() <= 0 or target_size.height() <= 0:
            target_size = self.image_label.size()
        self.image_label.setPixmap(
            self._pixmap.scaled(
                target_size,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
        )

    def keyPressEvent(self, event):
        if event.key() in {Qt.Key_F11, Qt.Key_F}:
            self.toggle_full_screen()
            return
        if event.key() == Qt.Key_Escape and self._is_full_screen:
            self.toggle_full_screen()
            return
        super().keyPressEvent(event)

    def resizeEvent(self, event):
        self._render()
        super().resizeEvent(event)


class ImagePanel(QFrame):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setObjectName("ImagePanel")
        self.setCursor(Qt.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("ImageTitle")

        self.status_label = QLabel("Sem imagem")
        self.status_label.setObjectName("PhotoStatus")

        self.preview_button = QPushButton("Ampliar")
        self.preview_button.setProperty("variant", "primary")
        self.preview_button.setVisible(False)
        self.preview_button.clicked.connect(self.open_preview)

        header.addWidget(self.title_label)
        header.addWidget(self.status_label)
        header.addStretch()
        header.addWidget(self.preview_button)

        self.frame = QFrame()
        self.frame.setObjectName("PhotoFrame")
        self.frame.setAttribute(Qt.WA_StyledBackground, True)
        frame_layout = QVBoxLayout(self.frame)
        frame_layout.setContentsMargins(10, 10, 10, 10)
        frame_layout.setSpacing(10)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(8)

        self.ribbon_label = QLabel("EVIDENCIA")
        self.ribbon_label.setObjectName("PhotoRibbon")

        top_row.addWidget(self.ribbon_label, 0, Qt.AlignLeft)
        top_row.addStretch()

        self.image_label = QLabel("Sem imagem")
        self.image_label.setMinimumHeight(260)
        self.image_label.setMaximumHeight(320)
        self.image_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.image_label.setAlignment(Qt.AlignCenter)
        frame_layout.addLayout(top_row)
        frame_layout.addWidget(self.image_label)

        self.caption_label = QLabel("")
        self.caption_label.setObjectName("PhotoCaption")
        self.caption_label.setWordWrap(True)

        layout.addLayout(header)
        layout.addWidget(self.frame)
        layout.addWidget(self.caption_label)

        self._raw_pixmap = QPixmap()
        self._preview_title = title
        self._hovered = False
        self._apply_visual_state()

    def set_preview_height(self, height: int, *, minimum: int | None = None):
        resolved_minimum = minimum if minimum is not None else max(180, height - 80)
        self.image_label.setMinimumHeight(resolved_minimum)
        self.image_label.setMaximumHeight(height)
        self._render_pixmap()

    def set_image_data(self, raw_bytes: bytes | None, caption: str = ""):
        if raw_bytes:
            self._raw_pixmap = QPixmap()
            self._raw_pixmap.loadFromData(raw_bytes)
            self._render_pixmap()
            self.image_label.setText("")
            self.status_label.setText("Imagem carregada")
            self.preview_button.setVisible(True)
        else:
            self._raw_pixmap = QPixmap()
            self.image_label.clear()
            self.image_label.setText("Sem imagem")
            self.status_label.setText("Sem imagem")
            self.preview_button.setVisible(False)
        self.caption_label.setText(caption)
        self._apply_visual_state()

    def set_preview_title(self, title: str):
        self._preview_title = title

    def set_photo_role(self, role: str):
        self.ribbon_label.setText(role.upper())

    def open_preview(self):
        if self._raw_pixmap.isNull():
            return
        dialog = ImagePreviewDialog(self._raw_pixmap, self._preview_title, self)
        dialog.exec()

    def _apply_visual_state(self):
        if self._hovered:
            frame_style = (
                "background:qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #EFF6FF, stop:1 #DBEAFE);"
                "border:1px solid rgba(37,99,235,0.34); border-radius:20px;"
            )
            image_style = (
                "background:#FFFFFF; border:1px solid rgba(37,99,235,0.42); border-radius:16px; color:#64748B;"
            )
        else:
            frame_style = (
                "background:qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #F8FBFF, stop:1 #EEF5FF);"
                "border:1px solid rgba(37,99,235,0.18); border-radius:20px;"
            )
            image_style = (
                "background:#FFFFFF; border:1px dashed rgba(37,99,235,0.35); border-radius:16px; color:#64748B;"
            )

        self.frame.setStyleSheet(frame_style)
        self.image_label.setStyleSheet(image_style)

    def _render_pixmap(self):
        if self._raw_pixmap.isNull():
            return
        target_size = self.image_label.contentsRect().size()
        if target_size.width() <= 0 or target_size.height() <= 0:
            return
        self.image_label.setPixmap(
            self._raw_pixmap.scaled(
                target_size.width(),
                target_size.height(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
        )

    def enterEvent(self, event):
        self._hovered = True
        self._apply_visual_state()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self._apply_visual_state()
        super().leaveEvent(event)

    def resizeEvent(self, event):
        self._render_pixmap()
        super().resizeEvent(event)
