# -*- coding: utf-8 -*-
"""Ventana principal de ISO8583 Analyzer."""

import time

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QSpinBox,
)

from core import api, converters
from core.exporter import result_to_json, result_to_text
from core.fields import translate
from core.history import HistoryManager
from core.mti import MTI_DESCRIPTIONS
from core.parser import ParseError, ParseOptions
from core.utils import chunk_bytes

from .controller import Controller
from .dialogs import AboutDialog, show_error
from .panels.formatter import FormatterPanel
from .widgets import (
    Card,
    CollapsibleSection,
    CopyButton,
    SectionTitle,
    add_tlv_rows,
    copy_to_clipboard,
    field_badges,
    make_badge,
)


def build_sample_basic():
    """Trama de ejemplo con DE3, DE11, DE41, DE60, DE63 y DE64."""
    data = (
        "990001" + "000853" + "3136303030303636"
        + "06" + "000000"
        + "0D" + "41435455414C495A4143494F4E"
        + "A1B23C44A1B23C44"
    )
    total = 15 + len(data) // 2
    return format(total, "04X") + "6080000001" + "0810" + "2020000000800013" + data


def build_sample_emv():
    """Trama de ejemplo que incluye EMV (Campo 55)."""
    tlv = (
        "9F2608" + "123456789ABCDEF0"
        + "9F2701" + "80"
        + "9F1007" + "9F260411223344"
        + "9A03" + "260820"
        + "5F2A02" + "0604"
        + "9C01" + "00"
        + "9F3602" + "0042"
        + "8202" + "3800"
    )
    data = "000000" + "000853" + "047F" + tlv
    total = 15 + len(data) // 2
    return format(total, "04X") + "6080000001" + "0200" + "2020000000000200" + data


CONVERSIONS = [
    ("HEX → ASCII", converters.hex_to_ascii),
    ("ASCII → HEX", converters.ascii_to_hex),
    ("BCD → Decimal", converters.bcd_to_decimal),
    ("Decimal → BCD (HEX)", converters.decimal_to_bcd),
    ("HEX → Decimal (int)", converters.hex_to_decimal),
    ("Decimal → HEX (int)", converters.decimal_to_hex),
]


class MainWindow(QMainWindow):
    def __init__(self, icon_path=None):
        super().__init__()
        self.setWindowTitle("ISO8583 Analyzer — build 2026-08-05 22:52")
        self.resize(1280, 820)
        self.setMinimumSize(980, 660)
        if icon_path:
            self.setWindowIcon(QIcon(icon_path))

        self.history = HistoryManager()
        self._current = None
        self._mti_override = None
        self._conversion_labels = [c[0] for c in CONVERSIONS]
        self.controller = Controller(self)

        self._build_ui()
        self._connect()
        self.controller.set_profile(self.combo_profile.currentData())
        self._reload_history()
        self._update_status("Listo. Pegue una trama ISO 8583 y presione Analizar.")

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        root = QWidget()
        root.setObjectName("centralRoot")
        self.setCentralWidget(root)
        main = QVBoxLayout(root)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        main.addWidget(self._build_header())

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._build_input_panel())
        splitter.addWidget(self._build_results_panel())
        splitter.setSizes([440, 840])
        splitter.setStretchFactor(1, 1)
        main.addWidget(splitter, 1)

        self.statusBar().showMessage("")

    def _build_header(self):
        header = QFrame()
        header.setObjectName("headerBar")
        lay = QHBoxLayout(header)
        lay.setContentsMargins(18, 10, 18, 10)
        lay.setSpacing(12)

        icon = QLabel()
        icon.setFixedSize(40, 40)
        icon.setPixmap(self.windowIcon().pixmap(40, 40))
        icon.setStyleSheet("background: transparent;")
        lay.addWidget(icon)

        title_col = QVBoxLayout()
        title_col.setSpacing(0)
        title = QLabel("ISO8583 Analyzer")
        title.setObjectName("appTitle")
        subtitle = QLabel("Analizador profesional de mensajes ISO 8583")
        subtitle.setObjectName("appSubtitle")
        title_col.addWidget(title)
        title_col.addWidget(subtitle)
        lay.addLayout(title_col)
        lay.addStretch(1)

        self.btn_about = QPushButton("Acerca de")
        self.btn_about.setObjectName("ghostButton")
        lay.addWidget(self.btn_about)
        return header

    def _build_input_panel(self):
        panel = QWidget()
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)

        title = QLabel("Trama ISO 8583 (hex)")
        title.setObjectName("panelTitle")
        lay.addWidget(title)

        self.input_edit = QTextEdit()
        self.input_edit.setObjectName("inputEdit")
        self.input_edit.setAcceptRichText(False)
        self.input_edit.setPlaceholderText(
            "Pegue aquí la trama ISO 8583 en hexadecimal…\n\nEj.: 0064608000000108102020000002800010…"
        )
        lay.addWidget(self.input_edit, 1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self.btn_analyze = QPushButton("▶  Analizar")
        self.btn_analyze.setObjectName("bigButton")
        self.btn_analyze.setMinimumHeight(46)
        self.btn_paste = QPushButton("Pegar")
        self.btn_paste.setObjectName("ghostButton")
        self.btn_clear = QPushButton("Limpiar")
        self.btn_clear.setObjectName("ghostButton")
        btn_row.addWidget(self.btn_analyze, 2)
        btn_row.addWidget(self.btn_paste)
        btn_row.addWidget(self.btn_clear)
        lay.addLayout(btn_row)

        config = Card()
        config.layout.setContentsMargins(14, 12, 14, 12)
        config.layout.setSpacing(8)

        mti_row = QHBoxLayout()
        mti_row.setSpacing(8)
        mti_label = QLabel("Tipo de mensaje (MTI):")
        mti_label.setObjectName("muted")
        mti_row.addWidget(mti_label)
        self.combo_mti = QComboBox()
        self.combo_mti.addItem("Automático (según trama)", "")
        for mti in sorted(MTI_DESCRIPTIONS):
            self.combo_mti.addItem(f"{mti} · {MTI_DESCRIPTIONS[mti]}", mti)
        mti_row.addWidget(self.combo_mti, 1)
        self.btn_mti_auto = QPushButton("⟲ Auto")
        self.btn_mti_auto.setObjectName("ghostButton")
        self.btn_mti_auto.setToolTip("Volver a la detección automática del MTI")
        mti_row.addWidget(self.btn_mti_auto)
        config.layout.addLayout(mti_row)

        self.chk_tpdu = QCheckBox("TPDU (5 bytes)")
        self.chk_tpdu.setChecked(True)
        self.chk_debug = QCheckBox("Depurar")
        self.combo_mti_mode = QComboBox()
        self.combo_mti_mode.addItem("Automático", "auto")
        self.combo_mti_mode.addItem("Manual", "manual")
        self.combo_mti_mode.setMinimumWidth(90)
        self.spin_mti_offset = QSpinBox()
        self.spin_mti_offset.setRange(0, 64)
        self.spin_mti_offset.setValue(7)
        self.spin_mti_offset.setPrefix("byte ")
        self.spin_mti_offset.setMinimumWidth(80)
        self.spin_mti_offset.setEnabled(False)
        self.combo_enc = QComboBox()
        self.combo_enc.addItem("Automática", "auto")
        self.combo_enc.addItem("BCD (empacado)", "bcd")
        self.combo_enc.addItem("ASCII", "ascii")
        self.combo_enc.addItem("Híbrido", "hybrid")
        self.combo_profile = QComboBox()
        for p in api.list_profiles():
            self.combo_profile.addItem(p["name"], p["name"])
        idx = self.combo_profile.findData(api.get_default_profile().name)
        if idx >= 0:
            self.combo_profile.setCurrentIndex(idx)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)
        grid.setColumnStretch(1, 1)
        start_row = QWidget()
        start_lay = QHBoxLayout(start_row)
        start_lay.setContentsMargins(0, 0, 0, 0)
        start_lay.setSpacing(6)
        start_lay.addWidget(self.combo_mti_mode)
        start_lay.addWidget(self.spin_mti_offset)
        grid.addWidget(self._muted_label("Inicio del mensaje:"), 0, 0)
        grid.addWidget(start_row, 0, 1)
        grid.addWidget(self._muted_label("Codificación:"), 1, 0)
        grid.addWidget(self.combo_enc, 1, 1)
        grid.addWidget(self._muted_label("Perfil:"), 2, 0)
        grid.addWidget(self.combo_profile, 2, 1)
        config.layout.addLayout(grid)

        chk_row = QHBoxLayout()
        chk_row.setSpacing(14)
        chk_row.addWidget(self.chk_tpdu)
        chk_row.addWidget(self.chk_debug)
        chk_row.addStretch(1)
        config.layout.addLayout(chk_row)

        lay.addWidget(config)

        samples = QHBoxLayout()
        samples.setSpacing(8)
        self.btn_sample = QPushButton("Ejemplo básico")
        self.btn_sample.setObjectName("ghostButton")
        self.btn_sample_emv = QPushButton("Ejemplo EMV")
        self.btn_sample_emv.setObjectName("ghostButton")
        samples.addWidget(self.btn_sample)
        samples.addWidget(self.btn_sample_emv)
        samples.addStretch(1)
        lay.addLayout(samples)

        return panel

    def _build_results_panel(self):
        panel = QWidget()
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_analysis_tab(), "Análisis")
        self.tabs.addTab(self._build_history_tab(), "Historial")
        self.tabs.addTab(self._build_converters_tab(), "Conversores")
        self.tabs.addTab(FormatterPanel(), "Formato")
        lay.addWidget(self.tabs)

        return panel

    def _build_analysis_tab(self):
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self.btn_export_txt = QPushButton("Exportar TXT")
        self.btn_export_json = QPushButton("Exportar JSON")
        self.btn_export_pdf = QPushButton("PDF (próximamente)")
        self.btn_export_pdf.setEnabled(False)
        self.btn_copy_raw = QPushButton("Copiar trama")
        self.btn_copy_raw.setObjectName("ghostButton")
        self.btn_translate = QPushButton("Traducir campos")
        self.btn_translate.setObjectName("toggleButton")
        self.btn_translate.setCheckable(True)
        self.btn_translate.setToolTip("Mostrar los nombres de los campos en español")
        self.btn_clear_results = QPushButton("Limpiar")
        self.btn_clear_results.setObjectName("ghostButton")
        for b in (self.btn_export_txt, self.btn_export_json):
            b.setObjectName("ghostButton")
        toolbar.addWidget(self.btn_export_txt)
        toolbar.addWidget(self.btn_export_json)
        toolbar.addWidget(self.btn_export_pdf)
        toolbar.addWidget(self.btn_copy_raw)
        toolbar.addStretch(1)
        toolbar.addWidget(self.btn_translate)
        toolbar.addWidget(self.btn_clear_results)
        lay.addLayout(toolbar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.results_container = QWidget()
        self.results_layout = QVBoxLayout(self.results_container)
        self.results_layout.setContentsMargins(4, 4, 4, 4)
        self.results_layout.setSpacing(12)
        self.results_layout.addStretch(1)
        scroll.setWidget(self.results_container)
        lay.addWidget(scroll, 1)
        return tab

    def _build_history_tab(self):
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)

        hint = QLabel("Los análisis se guardan automáticamente. Doble clic en una fila para recargar la trama.")
        hint.setObjectName("muted")
        lay.addWidget(hint)

        self.history_table = QTableWidget(0, 5)
        self.history_table.setHorizontalHeaderLabels(["Fecha", "Hora", "MTI", "TPDU", "Campos"])
        self.history_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.history_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.history_table.setSelectionMode(QTableWidget.SingleSelection)
        self.history_table.setAlternatingRowColors(True)
        self.history_table.verticalHeader().setVisible(False)
        lay.addWidget(self.history_table, 1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self.btn_history_load = QPushButton("Cargar selección")
        self.btn_history_load.setObjectName("ghostButton")
        self.btn_history_delete = QPushButton("Eliminar")
        self.btn_history_delete.setObjectName("ghostButton")
        self.btn_history_clear = QPushButton("Limpiar historial")
        self.btn_history_clear.setObjectName("ghostButton")
        btn_row.addWidget(self.btn_history_load)
        btn_row.addWidget(self.btn_history_delete)
        btn_row.addWidget(self.btn_history_clear)
        btn_row.addStretch(1)
        lay.addLayout(btn_row)
        return tab

    def _build_converters_tab(self):
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)

        title = QLabel("Conversores de utilidad")
        title.setObjectName("panelTitle")
        lay.addWidget(title)

        sel_row = QHBoxLayout()
        sel_row.setSpacing(8)
        self.combo_conv = QComboBox()
        for label in self._conversion_labels:
            self.combo_conv.addItem(label)
        self.btn_convert = QPushButton("Convertir")
        self.btn_convert.setObjectName("bigButton")
        self.btn_convert.setFixedHeight(36)
        sel_row.addWidget(self.combo_conv, 1)
        sel_row.addWidget(self.btn_convert)
        lay.addLayout(sel_row)

        self.conv_input = QLineEdit()
        self.conv_input.setPlaceholderText("Ingrese el valor de entrada…")
        lay.addWidget(self.conv_input)

        self.conv_output = QPlainTextEdit()
        self.conv_output.setObjectName("outputEdit")
        self.conv_output.setReadOnly(True)
        self.conv_output.setPlaceholderText("Resultado…")
        self.conv_output.setMinimumHeight(120)
        lay.addWidget(self.conv_output)

        tool_row = QHBoxLayout()
        tool_row.setSpacing(8)
        self.btn_remove_spaces = QPushButton("Eliminar espacios")
        self.btn_add_spaces = QPushButton("Agregar espacios (byte)")
        self.btn_copy_result = QPushButton("Copiar resultado")
        self.btn_swap = QPushButton("⇄ Intercambiar")
        self.btn_clear_conv = QPushButton("Limpiar")
        self.btn_clear_conv.setObjectName("ghostButton")
        for b in (self.btn_remove_spaces, self.btn_add_spaces, self.btn_copy_result, self.btn_swap):
            b.setObjectName("ghostButton")
        tool_row.addWidget(self.btn_remove_spaces)
        tool_row.addWidget(self.btn_add_spaces)
        tool_row.addWidget(self.btn_swap)
        tool_row.addStretch(1)
        tool_row.addWidget(self.btn_copy_result)
        tool_row.addWidget(self.btn_clear_conv)
        lay.addLayout(tool_row)

        self.conv_status = QLabel("")
        self.conv_status.setObjectName("muted")
        lay.addWidget(self.conv_status)
        lay.addStretch(1)
        return tab

    # ------------------------------------------------------------ helpers
    @staticmethod
    def _muted_label(text):
        label = QLabel(text)
        label.setObjectName("muted")
        return label

    @staticmethod
    def _clear_layout(layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
            elif item.layout() is not None:
                MainWindow._clear_layout(item.layout())

    def _connect(self):
        self.btn_analyze.clicked.connect(lambda: self._analyze())
        self.btn_paste.clicked.connect(self._paste)
        self.btn_clear.clicked.connect(lambda: self.input_edit.clear())
        self.btn_sample.clicked.connect(lambda: self._load_sample(build_sample_basic()))
        self.btn_sample_emv.clicked.connect(lambda: self._load_sample(build_sample_emv()))
        self.btn_about.clicked.connect(lambda: AboutDialog(self).exec())

        self.btn_export_txt.clicked.connect(self._export_txt)
        self.btn_export_json.clicked.connect(self._export_json)
        self.btn_copy_raw.clicked.connect(self._copy_raw)
        self.btn_translate.clicked.connect(self._on_toggle_translate)
        self.btn_clear_results.clicked.connect(self._clear_results)

        self.history_table.itemDoubleClicked.connect(lambda _i: self._history_load())
        self.btn_history_load.clicked.connect(self._history_load)
        self.btn_history_delete.clicked.connect(self._history_delete)
        self.btn_history_clear.clicked.connect(self._history_clear)

        self.btn_convert.clicked.connect(self._convert)
        self.btn_remove_spaces.clicked.connect(self._convert_utility("remove"))
        self.btn_add_spaces.clicked.connect(self._convert_utility("add"))
        self.btn_copy_result.clicked.connect(self._copy_conv_result)
        self.btn_swap.clicked.connect(self._swap_conversion)
        self.btn_clear_conv.clicked.connect(self._clear_converters)
        self.conv_input.returnPressed.connect(self._convert)

        self.combo_profile.currentIndexChanged.connect(self._on_profile_change)
        self.combo_mti_mode.currentIndexChanged.connect(self._on_mti_mode_change)
        self.combo_mti.currentIndexChanged.connect(self._on_mti_changed)
        self.btn_mti_auto.clicked.connect(self._reset_mti_auto)

    # ------------------------------------------------------------- actions
    def _paste(self):
        text = QApplication.clipboard().text()
        if text:
            self.input_edit.setPlainText(text)

    def _load_sample(self, raw):
        self.input_edit.setPlainText(raw)
        self._analyze(raw)

    def _analyze(self, raw=None):
        text = self.input_edit.toPlainText() if not isinstance(raw, str) else raw
        mti_offset = None
        if self.combo_mti_mode.currentData() == "manual":
            mti_offset = self.spin_mti_offset.value()
        opts = ParseOptions(
            has_tpdu=self.chk_tpdu.isChecked(),
            numeric_encoding=self.combo_enc.currentData(),
            mti_offset=mti_offset,
            mti_auto=(self.combo_mti_mode.currentData() == "auto"),
            debug=self.chk_debug.isChecked(),
        )
        try:
            start = time.perf_counter()
            msg = api.decode(text, profile_name=self.controller.active_profile, options=opts)
            result = msg.legacy
            override = self._mti_override
            if override and result.mti_offset_bytes is not None:
                pos = result.mti_offset_bytes * 2
                clean = result.raw_clean
                if len(clean) >= pos + 4 and (result.mti is None or result.mti.hex != override):
                    text = clean[:pos] + override + clean[pos + 4:]
                    self.input_edit.setPlainText(text)
                    msg = api.decode(text, profile_name=self.controller.active_profile, options=opts)
                    result = msg.legacy
            elapsed = (time.perf_counter() - start) * 1000
        except ParseError as exc:
            self._update_status("Error de análisis.")
            show_error(self, str(exc))
            return

        self._current = result
        self.controller.set_message(msg)
        self._build_results(result)
        offset_info = ""
        if result.mti_offset_bytes is not None:
            offset_info = f" · inicio MTI byte {result.mti_offset_bytes}"
        mti_info = f" · MTI {result.mti.hex}" if result.mti else ""
        self._update_status(
            f"OK · {len(result.fields)} campos · {len(result.active_fields)} bits activos "
            f"· {elapsed:.1f} ms · modo {result.numeric_encoding.upper()} · perfil {msg.profile}"
            f"{offset_info}{mti_info}"
        )
        self.history.add(text, result)
        self._reload_history()

    def _on_mti_changed(self, _index):
        data = self.combo_mti.currentData()
        override = data or None
        if override == self._mti_override:
            return
        self._mti_override = override
        if self.input_edit.toPlainText().strip():
            self._analyze()
        else:
            self._update_status(
                "Detección automática del MTI activada." if not override
                else f"MTI fijado: {override}."
            )

    def _reset_mti_auto(self):
        self._mti_override = None
        self.combo_mti.blockSignals(True)
        self.combo_mti.setCurrentIndex(0)
        self.combo_mti.blockSignals(False)
        if self.input_edit.toPlainText().strip():
            self._analyze()
        else:
            self._update_status("Detección automática del MTI activada.")

    def _on_toggle_translate(self):
        if self._current:
            self._build_results(self._current)
        self._update_status(
            "Traducción de campos al español activada." if self.btn_translate.isChecked()
            else "Traducción de campos desactivada."
        )

    def _clear_results(self):
        self._clear_layout(self.results_layout)
        self.results_layout.addStretch(1)
        self._current = None
        self._update_status("Resultados limpiados.")

    def _on_profile_change(self):
        self.controller.set_profile(self.combo_profile.currentData())
        self._update_status(f"Perfil activo: {self.controller.active_profile or 'por defecto'}")

    def _on_mti_mode_change(self):
        manual = self.combo_mti_mode.currentData() == "manual"
        self.spin_mti_offset.setEnabled(manual)
        self._update_status(
            "Modo manual: indique en qué byte comienza el MTI."
            if manual else "Detección automática del inicio del mensaje activada."
        )

    def _build_results(self, result):
        self._clear_layout(self.results_layout)

        # Longitud
        card = Card()
        card.layout.addWidget(SectionTitle("Longitud"))
        row, _ = self._kv(card, "Hex", result.length_hex)
        row, _ = self._kv(card, "Decimal", f"{result.length_value} bytes")
        ok = result.declared_hex == 0 or result.consumed_hex == result.declared_hex
        status = "✓ Consistente con el contenido" if ok else "⚠ No coincide con el contenido"
        card.layout.addWidget(make_badge(status, "green" if ok else "warn"))
        self.results_layout.addWidget(card)

        # Inicio del mensaje (offset del MTI)
        if result.mti_offset_bytes is not None:
            card = Card()
            card.layout.addWidget(SectionTitle("Inicio del mensaje"))
            self._kv(card, "Offset", f"byte {result.mti_offset_bytes}")
            if result.header_hex:
                self._kv(card, "Header", chunk_bytes(result.header_hex),
                         copy=result.header_hex, small=True)
            self.results_layout.addWidget(card)

        # TPDU
        if result.tpdu:
            card = Card()
            card.layout.addWidget(SectionTitle("TPDU"))
            self._kv(card, "TPDU", result.tpdu.hex, copy=result.tpdu.hex)
            self._kv(card, "Destino", result.tpdu.destination)
            self._kv(card, "Origen", result.tpdu.source)
            self._kv(card, "Control", result.tpdu.control)
            self._kv(card, "Longitud", f"{result.tpdu.length_bytes} bytes")
            self.results_layout.addWidget(card)

        # MTI
        if result.mti:
            card = Card()
            card.layout.addWidget(SectionTitle("Tipo de mensaje (MTI)"))
            top = QHBoxLayout()
            top.setSpacing(10)
            big = QLabel(result.mti.hex)
            big.setObjectName("mtiBig")
            top.addWidget(big)
            top.addWidget(make_badge(result.mti.description, "green"))
            top.addStretch(1)
            top.addWidget(CopyButton(lambda: result.mti.hex, "Copiar"))
            card.layout.addLayout(top)
            self._kv(card, "Versión", result.mti.version, mono=False)
            self._kv(card, "Clase", result.mti.message_class, mono=False)
            self._kv(card, "Función", result.mti.function, mono=False)
            self._kv(card, "Origen", result.mti.origin, mono=False)
            self.results_layout.addWidget(card)

        # Bitmap
        card = Card()
        card.layout.addWidget(SectionTitle("Bitmap"))
        self._kv(card, "Primario", result.bitmap_primary_hex, copy=result.bitmap_primary_hex)
        if result.bitmap_secondary_hex:
            self._kv(card, "Secundario", result.bitmap_secondary_hex, copy=result.bitmap_secondary_hex)
        self._kv(card, "Bits", f"{len(result.active_fields)} campos activos")
        self.results_layout.addWidget(card)

        # Campos activos
        card = Card()
        card.layout.addWidget(SectionTitle("Campos activos"))
        chips = QHBoxLayout()
        chips.setSpacing(6)
        chips.setAlignment(Qt.AlignLeft)
        for n in result.active_fields:
            if n == 1:
                continue
            chips.addWidget(make_badge(f"✓ DE{n}", "green"))
        card.layout.addLayout(chips)
        self.results_layout.addWidget(card)

        # Campos ausentes (plegable)
        present = set(result.active_fields)
        absent = [n for n in range(2, 129) if n not in present]
        if absent:
            absent_card = Card()
            label = QLabel(
                " ".join(f"DE{n}" for n in absent)
            )
            label.setObjectName("hexSmall")
            label.setWordWrap(True)
            section = CollapsibleSection(f"Campos ausentes ({len(absent)})", label)
            absent_card.layout.addWidget(section)
            self.results_layout.addWidget(absent_card)

        # EMV
        if result.emv:
            card = Card()
            card.layout.addWidget(SectionTitle("Campo 55 · EMV"))
            add_tlv_rows(card, result.emv)
            self.results_layout.addWidget(card)

        # Data Elements
        for f in result.fields:
            self.results_layout.addWidget(self._field_card(f))

        # Advertencias
        if result.warnings:
            card = Card()
            card.layout.addWidget(SectionTitle("Advertencias"))
            for w in result.warnings:
                row = QHBoxLayout()
                row.addWidget(make_badge("⚠", "warn"))
                label = QLabel(w)
                label.setWordWrap(True)
                row.addWidget(label, 1)
                card.layout.addLayout(row)
            self.results_layout.addWidget(card)

        # Errores
        if result.errors:
            card = Card()
            card.layout.addWidget(SectionTitle("Errores"))
            for e in result.errors:
                row = QHBoxLayout()
                row.addWidget(make_badge("✗", "error"))
                label = QLabel(e)
                label.setObjectName("errorText")
                label.setWordWrap(True)
                row.addWidget(label, 1)
                card.layout.addLayout(row)
            self.results_layout.addWidget(card)

        self.results_layout.addStretch(1)

    def _field_card(self, f):
        card = Card()

        header = QHBoxLayout()
        header.setSpacing(10)
        header.addWidget(make_badge(f"DE{f.number}", "accent"))
        name_col = QVBoxLayout()
        name_col.setSpacing(0)
        name = QLabel()
        name.setObjectName("fieldName")
        use_es = self.btn_translate.isChecked()
        es = translate(f.number)
        if use_es:
            name.setText(es)
        else:
            name.setText(f.name)
        name_col.addWidget(name)
        secondary = f.name if use_es else (f.description if f.description and f.description != f.name else None)
        if secondary:
            desc = QLabel(secondary)
            desc.setObjectName("fieldDesc")
            desc.setWordWrap(True)
            name_col.addWidget(desc)
        header.addLayout(name_col, 1)
        for badge in field_badges(f):
            header.addWidget(badge)
        card.layout.addLayout(header)

        if f.has_error:
            err = QLabel(f"⚠ {f.error}")
            err.setObjectName("errorText")
            err.setWordWrap(True)
            card.layout.addWidget(err)
            return card

        value_row = QHBoxLayout()
        value_row.setSpacing(8)
        value_label = QLabel(f.value if f.value else "—")
        value_label.setObjectName("fieldValue")
        value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        value_label.setWordWrap(True)
        value_row.addWidget(value_label)
        if f.value:
            value_row.addWidget(CopyButton(lambda f=f: f.value, "Copiar valor"))
        value_row.addStretch(1)
        card.layout.addLayout(value_row)

        self._kv(card, "Hex", chunk_bytes(f.raw_hex), copy=f.raw_hex, small=True)
        if f.number == 55 and f.emv:
            divider = QFrame()
            divider.setFrameShape(QFrame.HLine)
            divider.setStyleSheet("color: #2b3744;")
            card.layout.addWidget(divider)
            tlv_title = QLabel("EMV · Tags decodificados")
            tlv_title.setObjectName("sectionTitle")
            card.layout.addWidget(tlv_title)
            add_tlv_rows(card, f.emv)
        return card

    def _kv(self, card, title, value, copy=None, mono=True, strong=False, small=False):
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        title_label = QLabel(title)
        title_label.setObjectName("muted")
        title_label.setFixedWidth(90)
        lay.addWidget(title_label)
        value_label = QLabel(str(value))
        value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        if strong:
            value_label.setObjectName("monoValue")
        elif small:
            value_label.setObjectName("hexSmall")
        elif mono:
            value_label.setObjectName("monoValue")
        else:
            value_label.setObjectName("fieldName")
        lay.addWidget(value_label, 1)
        if copy is not None:
            lay.addWidget(CopyButton(lambda: copy, "Copiar"))
        card.layout.addWidget(row)
        return row, value_label

    def _update_status(self, text):
        self.statusBar().showMessage(text)

    # ------------------------------------------------------------ export
    def _export_txt(self):
        if not self._current:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Exportar análisis TXT", "analisis.txt", "Texto (*.txt)")
        if path:
            try:
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(result_to_text(self._current))
                self._update_status(f"Exportado a TXT: {path}")
            except OSError as exc:
                show_error(self, f"No se pudo guardar el archivo: {exc}")

    def _export_json(self):
        if not self._current:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Exportar análisis JSON", "analisis.json", "JSON (*.json)")
        if path:
            try:
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(result_to_json(self._current))
                self._update_status(f"Exportado a JSON: {path}")
            except OSError as exc:
                show_error(self, f"No se pudo guardar el archivo: {exc}")

    def _copy_raw(self):
        if self._current:
            copy_to_clipboard(self._current.raw_clean)
            self._update_status("Trama copiada al portapapeles.")

    # ------------------------------------------------------------ history
    def _reload_history(self):
        records = self.history.records
        self.history_table.setRowCount(len(records))
        for r, record in enumerate(records):
            for c, key in enumerate(["date", "time", "mti", "tpdu", "field_count"]):
                item = QTableWidgetItem(str(record.get(key, "")))
                item.setData(Qt.UserRole, r)
                self.history_table.setItem(r, c, item)
        self.history_table.resizeColumnsToContents()

    def _selected_history(self):
        row = self.history_table.currentRow()
        if row < 0:
            return None
        record = self.history.get(row)
        return record

    def _history_load(self):
        record = self._selected_history()
        if record and record.get("raw"):
            self.input_edit.setPlainText(record["raw"])
            self._analyze(record["raw"])

    def _history_delete(self):
        row = self.history_table.currentRow()
        if row >= 0:
            self.history.delete(row)
            self._reload_history()

    def _history_clear(self):
        self.history.clear()
        self._reload_history()

    # --------------------------------------------------------- converters
    def _conversion_fn(self):
        return CONVERSIONS[self.combo_conv.currentIndex()][1]

    def _convert(self):
        text = self.conv_input.text()
        try:
            result = self._conversion_fn()(text)
            self.conv_output.setPlainText(result)
            self.conv_status.setText(f"Resultado: {len(result)} caracteres")
        except ValueError as exc:
            self.conv_output.setPlainText("")
            self.conv_status.setText(str(exc))
            show_error(self, str(exc), "Error de conversión")

    def _convert_utility(self, kind):
        def run():
            text = self.conv_input.text()
            try:
                if kind == "remove":
                    result = converters.remove_spaces(text)
                else:
                    result = converters.add_spaces(text)
                self.conv_output.setPlainText(result)
                self.conv_status.setText(f"Resultado: {len(result)} caracteres")
            except ValueError as exc:
                show_error(self, str(exc), "Error de conversión")
        return run

    def _copy_conv_result(self):
        text = self.conv_output.toPlainText()
        if text:
            copy_to_clipboard(text)
            self.conv_status.setText("Resultado copiado al portapapeles.")

    def _clear_converters(self):
        self.conv_input.clear()
        self.conv_output.clear()
        self.conv_status.setText("")
        self._update_status("Conversores limpiados.")

    def _swap_conversion(self):
        current = self.combo_conv.currentText()
        swaps = {
            "HEX → ASCII": "ASCII → HEX",
            "ASCII → HEX": "HEX → ASCII",
            "BCD → Decimal": "Decimal → BCD (HEX)",
            "Decimal → BCD (HEX)": "BCD → Decimal",
            "HEX → Decimal (int)": "Decimal → HEX (int)",
            "Decimal → HEX (int)": "HEX → Decimal (int)",
        }
        target = swaps.get(current)
        if target:
            self.combo_conv.setCurrentIndex(self._conversion_labels.index(target))
        if self.conv_output.toPlainText():
            self.conv_input.setText(self.conv_output.toPlainText())
