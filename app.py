# -*- coding: utf-8 -*-
"""Punto de entrada de la aplicación ISO8583 Analyzer."""

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QColor, QIcon, QPixmap

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"


def _ensure_icon():
    """Genera (o recupera) el icono de la aplicación con Pillow."""
    target = ASSETS / "app_icon.png"
    if target.exists():
        return target
    ASSETS.mkdir(parents=True, exist_ok=True)
    try:
        from PIL import Image, ImageDraw, ImageFont

        size = 256
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Fondo con degradado redondeado
        for y in range(size):
            t = y / size
            color = (21 + int(30 * t), 33 + int(38 * t), 58 + int(50 * t), 255)
            draw.line([(0, y), (size, y)], fill=color)
        draw.rounded_rectangle([8, 8, size - 8, size - 8], radius=48, outline=(79, 154, 255, 255), width=6)

        # Barra de "señal" decorativa
        draw.rounded_rectangle([40, 180, 216, 200], radius=8, fill=(63, 185, 80, 255))
        draw.rounded_rectangle([60, 156, 196, 176], radius=8, fill=(47, 125, 240, 255))

        font = None
        for candidate in ("arialbd.ttf", "segoeuib.ttf", "DejaVuSans-Bold.ttf"):
            try:
                font = ImageFont.truetype(candidate, 84)
                break
            except OSError:
                continue
        if font is None:
            font = ImageFont.load_default()

        text = "8583"
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text(((size - tw) / 2 - bbox[0], 60 - bbox[1]), text, fill=(232, 237, 243, 255), font=font)

        img.save(target)
    except Exception:
        # Sin Pillow: icono simple
        fallback = QPixmap(64, 64)
        fallback.fill(QColor("#2f7df0"))
        fallback.save(str(target))
    return target


def create_app_icon():
    path = _ensure_icon()
    return QIcon(str(path)), path


def apply_theme(app):
    """Aplica el tema oscuro (qdarktheme) y la hoja de estilos personalizada."""
    try:
        import qdarktheme
        qdarktheme.setup_theme("dark")
    except Exception:
        pass

    try:
        import darkdetect
        darkdetect.isDark()  # detecta el tema del SO (información)
    except Exception:
        pass

    from ui.styles import STYLE_SHEET
    app.setStyleSheet(app.styleSheet() + STYLE_SHEET)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("ISO8583 Analyzer")
    app.setOrganizationName("ISO8583 Analyzer")
    app.setStyle("Fusion")

    icon, icon_path = create_app_icon()
    app.setWindowIcon(icon)

    apply_theme(app)

    from ui.main_window import MainWindow
    window = MainWindow(icon_path=str(icon_path))
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
