# -*- coding: utf-8 -*-
"""Diálogos de la aplicación: errores, avisos e información."""

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QMessageBox,
    QVBoxLayout,
)


def show_error(parent, message, title="Error de análisis"):
    """Muestra un cuadro de error estilizado."""
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Warning)
    box.setWindowTitle(title)
    box.setText(message)
    box.setStandardButtons(QMessageBox.Ok)
    box.exec()


def show_info(parent, message, title="Información"):
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Information)
    box.setWindowTitle(title)
    box.setText(message)
    box.setStandardButtons(QMessageBox.Ok)
    box.exec()


class AboutDialog(QDialog):
    """Diálogo 'Acerca de'."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Acerca de ISO8583 Analyzer")
        self.setMinimumWidth(380)
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        title = QLabel("ISO8583 Analyzer")
        title.setStyleSheet("font-size: 20px; font-weight: 700; color: #4c9aff;")
        layout.addWidget(title, alignment=0x0001 | 0x0004)

        version = QLabel("Versión 1.0.0")
        version.setObjectName("muted")
        layout.addWidget(version, alignment=0x0001 | 0x0004)

        desc = QLabel(
            "Herramienta profesional para analizar, interpretar y decodificar "
            "mensajes ISO 8583 de sistemas financieros.\n\n"
            "Características:\n"
            "• Análisis automático de longitud, TPDU, MTI y bitmaps\n"
            "• Diccionario de Data Elements y decodificador EMV (Campo 55)\n"
            "• Conversores HEX / ASCII / BCD / Decimal\n"
            "• Exportación TXT y JSON\n"
            "• Historial automático de análisis"
        )
        desc.setWordWrap(True)
        desc.setObjectName("muted")
        layout.addWidget(desc)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        ok = buttons.button(QDialogButtonBox.Ok)
        ok.setText("Cerrar")
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

        self.setStyleSheet("QLabel#muted { color: #8a97a8; }")
