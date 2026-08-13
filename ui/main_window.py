# -*- coding: utf-8 -*-
"""Ventana principal de ISO8583 Analyzer."""

import time

from PySide6.QtCore import QEvent, Qt
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
from core.currency import detector as currency_detector
from core.emv import enrich_result_emv
from core.exporter import result_to_json, result_to_text
from core.field_interpreter import interpret
from core.fields import translate
from core.history import HistoryManager
from core.mti import MTI_DESCRIPTIONS
from core.parser import ParseError, ParseOptions
from core.transaction_summary import TransactionSummary
from core.utils import chunk_bytes, organize_hex
from core.validation import validate_result

from .controller import Controller
from .dialogs import AboutDialog, show_error
from .panels.formatter import FormatterPanel
from .panels.frame_prep import FramePrepPanel
from .panels.reference import ReferenceCenterPanel
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
    ("HEX → Binario", converters.hex_to_binary),
    ("Binario → HEX", converters.binary_to_hex),
    ("Decimal → Binario", converters.decimal_to_binary),
    ("Binario → Decimal", converters.binary_to_decimal),
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
        self._ref_field_map = {}
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
        self.btn_organize = QPushButton("Organizar trama")
        self.btn_organize.setObjectName("ghostButton")
        self.btn_organize.setToolTip(
            "Organiza visualmente la trama HEX en líneas de 16 bytes, "
            "sin analizarla ni modificar los datos."
        )
        self.btn_paste = QPushButton("Pegar")
        self.btn_paste.setObjectName("ghostButton")
        self.btn_clear = QPushButton("Limpiar")
        self.btn_clear.setObjectName("ghostButton")
        btn_row.addWidget(self.btn_analyze, 2)
        btn_row.addWidget(self.btn_organize)
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
        self.combo_profile.addItem("Automático", "auto")
        for p in api.list_profiles():
            self.combo_profile.addItem(p["name"], p["name"])
        self.combo_profile.setCurrentIndex(0)

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
        self.reference_panel = ReferenceCenterPanel()
        self.tabs.addTab(self.reference_panel, "Referencia")

        self.frame_prep_panel = FramePrepPanel()
        self.tabs.addTab(self.frame_prep_panel, "Preparador")

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
        self.btn_organize.clicked.connect(self._organize_frame)
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

        self.frame_prep_panel.send_requested.connect(self._on_frame_prep_send)

    def _on_frame_prep_send(self, clean_hex):
        """Recibe la trama limpia del Preparador y la deja en el área de entrada.

        NO analiza automáticamente: el usuario pulsa Analizar (política del
        Preparador de Tramas).
        """
        if not clean_hex:
            return
        self.input_edit.setPlainText(clean_hex)
        self.tabs.setCurrentIndex(0)  # pestaña "Análisis"
        self._update_status("Trama preparada y lista para analizar. Pulse Analizar.")

    # ------------------------------------------------------------- actions
    def _paste(self):
        text = QApplication.clipboard().text()
        if text:
            self.input_edit.setPlainText(text)

    def _organize_frame(self):
        """Organiza visualmente la trama pegada en líneas de 16 bytes.

        Solo inserta saltos de línea; no analiza la trama ni genera reporte.
        Si la trama no es HEX válida o falla la verificación de integridad,
        no modifica el contenido del usuario y muestra un error.
        """
        organized, error = organize_hex(self.input_edit.toPlainText())
        if error:
            self._update_status("Organizar trama: no se modificó el contenido.")
            show_error(self, error, "Organizar trama")
            return
        self.input_edit.setPlainText(organized)
        hex_len = len(organized.replace("\n", ""))
        self._update_status(
            f"Trama organizada · {hex_len // 2} bytes · 16 bytes por línea · "
            f"{organized.count(chr(10)) + 1} líneas."
        )

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
            profile_name = self.controller.active_profile
            if profile_name == "auto":
                probe = ParseOptions(
                    has_tpdu=opts.has_tpdu,
                    numeric_encoding=opts.numeric_encoding,
                    mti_offset=opts.mti_offset,
                    mti_auto=opts.mti_auto,
                    debug=False,
                )
                profile_name = api.pick_profile(text, probe) or api.get_default_profile().name
            msg = api.decode(text, profile_name=profile_name, options=opts)
            result = msg.legacy
            override = self._mti_override
            if override and result.mti_offset_bytes is not None:
                pos = result.mti_offset_bytes * 2
                clean = result.raw_clean
                if len(clean) >= pos + 4 and (result.mti is None or result.mti.hex != override):
                    text = clean[:pos] + override + clean[pos + 4:]
                    self.input_edit.setPlainText(text)
                    msg = api.decode(text, profile_name=profile_name, options=opts)
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
            mti_ref = QPushButton("Ficha MTI")
            mti_ref.setObjectName("ghostButton")
            mti_ref.setCursor(Qt.PointingHandCursor)
            mti_ref.setFixedHeight(28)
            mti_ref.clicked.connect(lambda _=False, h=result.mti.hex: self._open_reference_mti(h))
            top.addWidget(mti_ref)
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

        # Resumen de transacción
        summary = TransactionSummary(result)
        card = Card()
        card.layout.addWidget(SectionTitle("Resumen de Transacción"))
        amt = summary.amount()
        if amt["available"]:
            self._kv(card, "Monto de la transacción", amt["formatted"], mono=False)
            self._kv(card, "Monto bruto DE4", amt["raw"])
        elif amt["present"]:
            self._kv(card, "Monto bruto", amt["raw"])
            self._kv(card, "Monto interpretado", "No disponible", mono=False)
            self._kv(card, "Motivo", amt["reason"], mono=False)
        else:
            self._kv(card, "Monto", "No disponible", mono=False)
            self._kv(card, "Motivo", amt["reason"], mono=False)
        cur = summary.currency()
        if cur["detected"]:
            self._kv(card, "Moneda", cur["currency"], mono=False)
            self._kv(card, "Código ISO", cur["code"])
            self._kv(card, "Fuente de moneda", cur["source"], mono=False)
            if cur["name"]:
                self._kv(card, "Descripción", cur["name"], mono=False)
            if cur["minor_units"] is not None:
                self._kv(card, "Minor units", str(cur["minor_units"]))
            if cur["mismatch"]:
                card.layout.addWidget(make_badge("⚠ Advertencia de moneda", "warn"))
                self._kv(card, "Estado", "Los códigos de moneda no coinciden", mono=False)
        else:
            self._kv(card, "Moneda", "No detectada", mono=False)
        tm = summary.time()
        if tm["valid"]:
            self._kv(card, "Hora de la transacción", tm["formatted"])
            self._kv(card, "DE12", tm["raw"])
        elif tm["present"]:
            self._kv(card, "Hora", "Valor inválido", mono=False)
        else:
            self._kv(card, "Hora", "No disponible", mono=False)
            self._kv(card, "Motivo", tm["reason"], mono=False)
        dt = summary.date()
        if dt["valid"]:
            self._kv(card, "Fecha de la transacción", dt["formatted"])
            self._kv(card, "DE13", dt["raw"])
        elif dt["present"]:
            self._kv(card, "Fecha", "Valor inválido", mono=False)
        else:
            self._kv(card, "Fecha", "No disponible", mono=False)
            self._kv(card, "Motivo", dt["reason"], mono=False)
        self.results_layout.addWidget(card)

        # Validación de Trama
        validation = validate_result(result)
        card = Card()
        card.layout.addWidget(SectionTitle("Validación de Trama"))
        badge_kind = "green" if validation.status == "valid" else (
            "warn" if validation.status == "warnings" else "error")
        card.layout.addWidget(make_badge(validation.status_label, badge_kind))
        for finding in validation.errors:
            self._validation_row(card, "❌", finding, "errorText")
        for finding in validation.warnings:
            self._validation_row(card, "⚠", finding, "warnText")
        for finding in validation.infos:
            self._validation_row(card, "✓", finding, "infoText")
        if not validation.findings:
            note = QLabel("No se detectaron hallazgos adicionales.")
            note.setObjectName("muted")
            card.layout.addWidget(note)
        self.results_layout.addWidget(card)

        # Moneda de transacción
        currency_report = currency_detector().detect(result)
        if currency_report.detected:
            card = Card()
            card.layout.addWidget(SectionTitle("Moneda de Transacción"))
            primary = currency_report.primary or currency_report.emv
            if primary:
                self._kv(card, "Fuente", primary.source, mono=False)
                self._kv(card, "Código ISO", primary.code)
                self._kv(card, "Moneda", primary.currency)
                if primary.name:
                    self._kv(card, "Descripción", primary.name, mono=False)
            else:
                self._kv(card, "Moneda", "No detectada", mono=False)
            if currency_report.secondary:
                self._kv(card, "Secundaria (DE51)",
                         f"{currency_report.secondary.code} {currency_report.secondary.currency}")
            if currency_report.mismatch:
                card.layout.addWidget(make_badge("⚠ Diferencia de moneda detectada", "warn"))
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
            _src = summary.source
            enrich_result_emv(result,
                              getattr(_src, "currency", None) if _src else None,
                              getattr(_src, "minor_units", None) if _src else None)
            card = Card()
            card.layout.addWidget(SectionTitle("Campo 55 · EMV"))
            add_tlv_rows(card, result.emv)
            self.results_layout.addWidget(card)

        # Payload posterior (p. ej. GZIP propietario tras DE64)
        if result.trailing_payload is not None:
            p = result.trailing_payload
            card = Card()
            card.layout.addWidget(SectionTitle("Payload posterior"))
            if p.status == "confirmed":
                self._kv(card, "Tipo", "GZIP (gzip comprimido)", mono=False)
            else:
                self._kv(card, "Tipo", "Posible payload propietario", mono=False)
                self._kv(card, "Motivo", p.reason, mono=False)
            self._kv(card, "Longitud declarada", f"{p.declared_length} bytes")
            self._kv(card, "Longitud disponible", f"{p.available_length} bytes")
            if p.decompressed_length is not None:
                self._kv(card, "Estado", f"Descomprimido correctamente — {p.decompressed_length} bytes")
            else:
                self._kv(card, "Estado", "No se pudo descomprimir")
            if p.preview:
                preview = QLabel(p.preview)
                preview.setObjectName("hexSmall")
                preview.setWordWrap(True)
                card.layout.addWidget(preview)
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
        interp = interpret(f)
        header.addWidget(make_badge(interp.label, "green" if interp.category == "text" else "accent"))
        for badge in field_badges(f):
            header.addWidget(badge)
        ref_btn = QPushButton("ℹ  Ficha")
        ref_btn.setObjectName("ghostButton")
        ref_btn.setCursor(Qt.PointingHandCursor)
        ref_btn.setFixedHeight(26)
        ref_btn.setToolTip("Abrir la ficha de este campo en el Centro de Referencia")
        ref_btn.clicked.connect(lambda _=False, ff=f: self._open_reference(ff))
        header.addWidget(ref_btn)
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
        value_label.setTextFormat(Qt.PlainText)
        value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        value_label.setWordWrap(True)
        value_row.addWidget(value_label)
        if f.value:
            value_row.addWidget(CopyButton(lambda f=f: f.value, "Copiar valor"))
        value_row.addStretch(1)
        card.layout.addLayout(value_row)

        if f.number in (49, 50, 51) and f.value and f.value.strip().isdigit():
            cur = api.reference_currency(f.value.strip())
            if cur:
                ref = api.reference_service()
                cur_row = QHBoxLayout()
                cur_row.setSpacing(8)
                cur_lbl = QLabel("Moneda / Currency:")
                cur_lbl.setObjectName("muted")
                cur_row.addWidget(cur_lbl)
                cur_val = QLabel(
                    f"{cur['numeric']} · {cur['alpha']} — "
                    f"{ref.loc(cur, 'name', 'es')} / {ref.loc(cur, 'name', 'en')}"
                )
                cur_val.setWordWrap(True)
                cur_row.addWidget(cur_val, 1)
                cur_btn = QPushButton("Ver")
                cur_btn.setObjectName("ghostButton")
                cur_btn.setCursor(Qt.PointingHandCursor)
                cur_btn.setFixedHeight(26)
                cur_btn.clicked.connect(
                    lambda _=False, cc=f.value.strip(): self._open_reference_currency(cc))
                cur_row.addWidget(cur_btn)
                card.layout.addLayout(cur_row)

        self._ref_field_map[id(card)] = f
        card.installEventFilter(self)
        self._ref_field_map[id(value_label)] = f
        value_label.installEventFilter(self)

        self._kv(card, "Hex", chunk_bytes(f.raw_hex), copy=f.raw_hex, small=True)
        if f.note:
            note = QLabel(f"ℹ {f.note}")
            note.setObjectName("muted")
            note.setWordWrap(True)
            card.layout.addWidget(note)
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

    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseButtonDblClick:
            f = self._ref_field_map.get(id(obj))
            if f is not None:
                self._open_reference(f)
                return True
        return super().eventFilter(obj, event)

    def _open_reference(self, f):
        """Con doble clic o 'Ficha' en un campo, abre su ficha en el Centro."""
        self.tabs.setCurrentWidget(self.reference_panel)
        if f.number in (49, 50, 51) and f.value and f.value.strip().isdigit():
            if api.reference_currency(f.value.strip()):
                self.reference_panel.open_currency(f.value.strip())
                return
        if f.number == 39 and f.value:
            if api.reference_response_code(f.value):
                self.reference_panel.open_response_code(f.value)
                return
        self.reference_panel.open_field(f.number)

    def _open_reference_mti(self, mti_hex):
        self.tabs.setCurrentWidget(self.reference_panel)
        self.reference_panel.open_mti(mti_hex)

    def _open_reference_currency(self, code):
        self.tabs.setCurrentWidget(self.reference_panel)
        self.reference_panel.open_currency(code)

    def _kv(self, card, title, value, copy=None, mono=True, strong=False, small=False):
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        title_label = QLabel(title)
        title_label.setObjectName("muted")
        title_label.setMinimumWidth(90)
        title_label.setWordWrap(True)
        lay.addWidget(title_label)
        value_label = QLabel(str(value))
        value_label.setWordWrap(True)
        value_label.setTextFormat(Qt.PlainText)
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

    def _validation_row(self, card, icon, finding, style_name):
        """Fila de un hallazgo de validación dentro de la tarjeta."""
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        lay.addWidget(QLabel(icon))
        col = QVBoxLayout()
        col.setSpacing(2)
        header = QLabel(f"{finding.code}" + (f" · {finding.field}" if finding.field else ""))
        header.setObjectName("hexSmall")
        col.addWidget(header)
        message = QLabel(finding.message)
        message.setObjectName(style_name)
        message.setWordWrap(True)
        col.addWidget(message)
        if finding.value:
            value = QLabel(finding.value)
            value.setObjectName("muted")
            value.setWordWrap(True)
            col.addWidget(value)
        lay.addLayout(col, 1)
        card.layout.addWidget(row)

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
            "HEX → Binario": "Binario → HEX",
            "Binario → HEX": "HEX → Binario",
            "Decimal → Binario": "Binario → Decimal",
            "Binario → Decimal": "Decimal → Binario",
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
