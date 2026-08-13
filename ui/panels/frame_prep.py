# -*- coding: utf-8 -*-
"""Panel Preparador de Tramas: limpia y prepara tramas desde varios formatos.

Depende solo de core.frame_prep. No toca el parser, la validación, los
conversores ni las funciones EMV.
"""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.frame_prep import prepare_frame

from ..widgets import copy_to_clipboard


class FramePrepPanel(QWidget):
    """Preparador universal de tramas HEX."""

    #: Se emite con la trama limpia cuando el usuario pulsa "Enviar a Analizador".
    send_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._last_clean = ""
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)

        title = QLabel("Preparador de Tramas")
        title.setObjectName("panelTitle")
        lay.addWidget(title)

        hint = QLabel(
            "Pegue una trama copiada de cualquier herramienta (HEX continuo, "
            "HEX separado, hexdump Wireshark con offset o con columna ASCII). "
            "El formato se detecta automáticamente y se extrae solo el HEX real."
        )
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        lay.addWidget(hint)

        lay.addWidget(QLabel("Trama de entrada:"))
        self.input_edit = QPlainTextEdit()
        self.input_edit.setObjectName("inputEdit")
        self.input_edit.setPlaceholderText(
            "Pegue aquí la trama original (con espacios, offsets, ASCII...).\n"
            "Ejemplo:\n"
            "0000   aa 00 04 10 b2 38 00 01 02 c1 80 04 00 00 00 40   .....8........\n"
            "0010   00 00 00 02 00 70 00 00 00 00 00 02 22 09 09 19   .....p........"
        )
        self.input_edit.setMinimumHeight(160)
        lay.addWidget(self.input_edit)

        self.lbl_format = QLabel("Formato detectado: —")
        self.lbl_format.setObjectName("muted")
        self.lbl_format.setWordWrap(True)
        lay.addWidget(self.lbl_format)

        lay.addWidget(QLabel("Trama HEX limpia:"))
        self.output_edit = QPlainTextEdit()
        self.output_edit.setObjectName("convOutput")
        self.output_edit.setReadOnly(True)
        self.output_edit.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.output_edit.setPlaceholderText("La trama HEX limpia aparecerá aquí…")
        self.output_edit.setMinimumHeight(140)
        lay.addWidget(self.output_edit)

        self.lbl_info = QLabel("")
        self.lbl_info.setObjectName("muted")
        self.lbl_info.setWordWrap(True)
        lay.addWidget(self.lbl_info)

        row = QHBoxLayout()
        row.setSpacing(8)
        self.btn_prepare = QPushButton("Preparar trama")
        self.btn_prepare.setObjectName("bigButton")
        self.btn_prepare.setFixedHeight(36)
        self.btn_copy = QPushButton("Copiar trama")
        self.btn_copy.setObjectName("ghostButton")
        self.btn_send = QPushButton("Enviar a Analizador")
        self.btn_send.setObjectName("ghostButton")
        self.btn_clear = QPushButton("Limpiar")
        self.btn_clear.setObjectName("ghostButton")
        row.addWidget(self.btn_prepare)
        row.addWidget(self.btn_copy)
        row.addWidget(self.btn_send)
        row.addStretch(1)
        row.addWidget(self.btn_clear)
        lay.addLayout(row)

        self.btn_prepare.clicked.connect(self._prepare)
        self.btn_copy.clicked.connect(self._copy)
        self.btn_send.clicked.connect(self._send)
        self.btn_clear.clicked.connect(self._clear)

    # ------------------------------------------------------------- acciones

    def _prepare(self):
        text = self.input_edit.toPlainText()
        if not text.strip():
            self.lbl_format.setText("Formato detectado: —")
            self.output_edit.clear()
            self.lbl_info.setText("")
            self._last_clean = ""
            return

        result = prepare_frame(text)
        if result.format is None:
            self.lbl_format.setText("Formato detectado: ✗ " + result.error)
            self.output_edit.clear()
            self.lbl_info.setText("La entrada no se modificó.")
            self._last_clean = ""
            return

        self.lbl_format.setText("Formato detectado: ✓ " + result.format_label)
        if not result.ok:
            self.output_edit.clear()
            self.lbl_info.setText(result.error + " La entrada no se modificó.")
            self._last_clean = ""
            return

        self.output_edit.setPlainText(result.hex_clean)
        integridad = " ✓ integridad verificada (mismos bytes)" if result.integritas_ok \
            else " ⚠ verificación de integridad"
        self.lbl_info.setText(
            f"{result.bytes_count} bytes · {result.lines_processed} línea(s) procesada(s)"
            f"{integridad}"
        )
        self._last_clean = result.hex_clean

    def _copy(self):
        if self._last_clean:
            copy_to_clipboard(self._last_clean)
            self.lbl_info.setText(
                f"Copiado al portapapeles ({len(self._last_clean) // 2} bytes)."
            )
        else:
            self.lbl_info.setText("No hay trama preparada para copiar.")

    def _send(self):
        if self._last_clean:
            self.send_requested.emit(self._last_clean)
        else:
            self.lbl_info.setText("Prepare la trama antes de enviarla al Analizador.")

    def _clear(self):
        self.input_edit.clear()
        self.output_edit.clear()
        self.lbl_format.setText("Formato detectado: —")
        self.lbl_info.setText("")
        self._last_clean = ""
