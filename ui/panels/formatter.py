# -*- coding: utf-8 -*-
"""Panel Formatter: vista de bytes estilo Notepad++ (hex/ascii/bin/bcd).

Panel inicial que demuestra el patrón de vistas: depende solo de core.api.
"""

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core import api

from ..dialogs import show_error
from ..widgets import copy_to_clipboard


class FormatterPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)

        title = QLabel("Formatter de trama (estilo Notepad++)")
        title.setObjectName("panelTitle")
        lay.addWidget(title)

        controls = QHBoxLayout()
        controls.setSpacing(8)
        controls.addWidget(QLabel("Estilo:"))
        self.combo_style = QComboBox()
        for label, data in (
            ("HEX (con ASCII)", "hex"),
            ("ASCII", "ascii"),
            ("Binario", "binary"),
            ("BCD (decimal)", "bcd"),
        ):
            self.combo_style.addItem(label, data)
        controls.addWidget(self.combo_style)

        controls.addWidget(QLabel("Columnas:"))
        self.combo_cols = QComboBox()
        for cols in (8, 16, 32):
            self.combo_cols.addItem(str(cols), cols)
        self.combo_cols.setCurrentIndex(1)
        controls.addWidget(self.combo_cols)

        self.btn_format = QPushButton("Formatear")
        self.btn_format.setObjectName("bigButton")
        self.btn_format.setFixedHeight(34)
        controls.addWidget(self.btn_format)
        lay.addLayout(controls)

        self.input_edit = QPlainTextEdit()
        self.input_edit.setPlaceholderText(
            "Pegue la trama hexadecimal aquí…\n\nEj.: 0064608000000108102020000002800010"
        )
        self.input_edit.setMinimumHeight(120)
        lay.addWidget(self.input_edit)

        tool_row = QHBoxLayout()
        tool_row.setSpacing(8)
        self.btn_copy = QPushButton("Copiar resultado")
        self.btn_copy.setObjectName("ghostButton")
        self.btn_clear = QPushButton("Limpiar")
        self.btn_clear.setObjectName("ghostButton")
        tool_row.addWidget(self.btn_copy)
        tool_row.addWidget(self.btn_clear)
        tool_row.addStretch(1)
        lay.addLayout(tool_row)

        self.output_edit = QPlainTextEdit()
        self.output_edit.setObjectName("outputEdit")
        self.output_edit.setReadOnly(True)
        self.output_edit.setPlaceholderText("Resultado formateado…")
        lay.addWidget(self.output_edit, 1)

        self.status_label = QLabel("")
        self.status_label.setObjectName("muted")
        lay.addWidget(self.status_label)

        self.btn_format.clicked.connect(self._format)
        self.btn_copy.clicked.connect(self._copy)
        self.btn_clear.clicked.connect(self._clear)

    def _format(self):
        text = self.input_edit.toPlainText()
        if not text.strip():
            self.status_label.setText("Pegue una trama para formatear.")
            return
        try:
            style = self.combo_style.currentData()
            cols = self.combo_cols.currentData()
            output = api.format_frame(text, style, cols)
            self.output_edit.setPlainText(output)
            lines = output.count("\n") + 1 if output else 0
            self.status_label.setText(
                f"OK · {lines} líneas · estilo {style} · {cols} bytes por línea"
            )
        except ValueError as exc:
            self.output_edit.setPlainText("")
            self.status_label.setText(str(exc))
            show_error(self, str(exc), "Error de formato")

    def _copy(self):
        text = self.output_edit.toPlainText()
        if text:
            copy_to_clipboard(text)
            self.status_label.setText("Resultado copiado al portapapeles.")

    def _clear(self):
        self.input_edit.clear()
        self.output_edit.clear()
        self.status_label.setText("")
