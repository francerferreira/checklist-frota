from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap


def make_icon(name: str, bg: str = "#E8F0FE", fg: str = "#1D4ED8", size: int = 22) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(bg))
    painter.drawRoundedRect(QRectF(0, 0, size, size), 7, 7)

    pen = QPen(QColor(fg))
    pen.setWidthF(max(1.6, size / 13))
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)

    if name == "dashboard":
        bar_w = size * 0.14
        gap = size * 0.07
        start_x = size * 0.22
        heights = [0.26, 0.42, 0.6]
        for index, height in enumerate(heights):
            x = start_x + index * (bar_w + gap)
            rect = QRectF(x, size * (0.72 - height), bar_w, size * height)
            painter.drawRoundedRect(rect, 1.8, 1.8)
    elif name == "warning":
        path = QPainterPath()
        path.moveTo(size * 0.50, size * 0.18)
        path.lineTo(size * 0.82, size * 0.78)
        path.lineTo(size * 0.18, size * 0.78)
        path.closeSubpath()
        painter.drawPath(path)
        painter.drawLine(QPointF(size * 0.50, size * 0.36), QPointF(size * 0.50, size * 0.56))
        painter.drawPoint(QPointF(size * 0.50, size * 0.66))
    elif name == "equipment":
        painter.drawRoundedRect(QRectF(size * 0.18, size * 0.34, size * 0.64, size * 0.28), 2.5, 2.5)
        painter.drawEllipse(QRectF(size * 0.24, size * 0.60, size * 0.14, size * 0.14))
        painter.drawEllipse(QRectF(size * 0.62, size * 0.60, size * 0.14, size * 0.14))
    elif name == "reports":
        painter.drawRoundedRect(QRectF(size * 0.24, size * 0.18, size * 0.52, size * 0.64), 2.5, 2.5)
        painter.drawLine(QPointF(size * 0.34, size * 0.38), QPointF(size * 0.66, size * 0.38))
        painter.drawLine(QPointF(size * 0.34, size * 0.50), QPointF(size * 0.66, size * 0.50))
        painter.drawLine(QPointF(size * 0.34, size * 0.62), QPointF(size * 0.58, size * 0.62))
    elif name == "activities":
        painter.drawRoundedRect(QRectF(size * 0.20, size * 0.24, size * 0.24, size * 0.24), 2.8, 2.8)
        painter.drawRoundedRect(QRectF(size * 0.56, size * 0.24, size * 0.24, size * 0.24), 2.8, 2.8)
        painter.drawRoundedRect(QRectF(size * 0.38, size * 0.56, size * 0.24, size * 0.24), 2.8, 2.8)
        painter.drawLine(QPointF(size * 0.44, size * 0.36), QPointF(size * 0.56, size * 0.36))
        painter.drawLine(QPointF(size * 0.50, size * 0.48), QPointF(size * 0.50, size * 0.56))
        painter.drawLine(QPointF(size * 0.68, size * 0.48), QPointF(size * 0.56, size * 0.60))
    elif name == "materials":
        painter.drawRoundedRect(QRectF(size * 0.22, size * 0.30, size * 0.56, size * 0.44), 3.2, 3.2)
        painter.drawLine(QPointF(size * 0.34, size * 0.30), QPointF(size * 0.34, size * 0.18))
        painter.drawLine(QPointF(size * 0.66, size * 0.30), QPointF(size * 0.66, size * 0.18))
        painter.drawLine(QPointF(size * 0.38, size * 0.52), QPointF(size * 0.62, size * 0.52))
    elif name == "users":
        painter.drawEllipse(QRectF(size * 0.33, size * 0.20, size * 0.18, size * 0.18))
        painter.drawRoundedRect(QRectF(size * 0.24, size * 0.48, size * 0.36, size * 0.18), 3, 3)
        painter.drawEllipse(QRectF(size * 0.56, size * 0.28, size * 0.14, size * 0.14))
        painter.drawRoundedRect(QRectF(size * 0.54, size * 0.50, size * 0.18, size * 0.12), 2.5, 2.5)
    elif name == "logout":
        painter.drawRoundedRect(QRectF(size * 0.18, size * 0.22, size * 0.34, size * 0.56), 2.8, 2.8)
        painter.drawLine(QPointF(size * 0.48, size * 0.50), QPointF(size * 0.78, size * 0.50))
        painter.drawLine(QPointF(size * 0.66, size * 0.38), QPointF(size * 0.78, size * 0.50))
        painter.drawLine(QPointF(size * 0.66, size * 0.62), QPointF(size * 0.78, size * 0.50))
    elif name == "ok":
        painter.drawLine(QPointF(size * 0.24, size * 0.54), QPointF(size * 0.42, size * 0.72))
        painter.drawLine(QPointF(size * 0.42, size * 0.72), QPointF(size * 0.76, size * 0.30))
    elif name == "cancel":
        painter.drawLine(QPointF(size * 0.28, size * 0.28), QPointF(size * 0.72, size * 0.72))
        painter.drawLine(QPointF(size * 0.72, size * 0.28), QPointF(size * 0.28, size * 0.72))
    else:
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(fg))
        font = QFont("Segoe UI", max(8, int(size * 0.38)))
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(QRectF(0, 0, size, size), Qt.AlignCenter, name[:1].upper())

    painter.end()
    return QIcon(pixmap)
