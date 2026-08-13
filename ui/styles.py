# -*- coding: utf-8 -*-
"""Hoja de estilos QSS con tema oscuro profesional.

Se aplica sobre el tema base de qdarktheme para unificar el aspecto.
"""

STYLE_SHEET = """
* {
    font-family: "Segoe UI", "Segoe UI Variable", "Noto Sans", sans-serif;
}

QMainWindow, QWidget#centralRoot {
    background-color: #151b23;
}

QWidget {
    color: #d7dee7;
    font-size: 13px;
}

QToolTip {
    background-color: #232d3a;
    color: #d7dee7;
    border: 1px solid #3a4657;
    padding: 4px 8px;
    border-radius: 6px;
}

QStatusBar {
    background-color: #10151c;
    color: #8a97a8;
    border-top: 1px solid #222c39;
}
QStatusBar::item { border: none; }

QScrollBar:vertical { background: transparent; width: 10px; }
QScrollBar::handle:vertical { background: #33405a; border-radius: 5px; min-height: 30px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { background: transparent; height: 10px; }
QScrollBar::handle:horizontal { background: #33405a; border-radius: 5px; min-width: 30px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

QFrame#headerBar {
    background-color: #10151c;
    border-bottom: 1px solid #26303d;
}
QLabel#appTitle {
    font-size: 20px;
    font-weight: 700;
    color: #e8edf3;
    letter-spacing: 0.5px;
}
QLabel#appSubtitle {
    font-size: 12px;
    color: #8a97a8;
}
QLabel#panelTitle {
    font-size: 14px;
    font-weight: 600;
    color: #c6d2de;
}

QFrame#card {
    background-color: #1e2733;
    border: 1px solid #2b3744;
    border-radius: 10px;
}
QFrame#card > QLabel {
    color: #d7dee7;
}

QLabel#sectionTitle {
    font-size: 15px;
    font-weight: 700;
    color: #4c9aff;
}
QLabel#cardTitle {
    font-size: 14px;
    font-weight: 700;
    color: #e4eaef;
}
QLabel#muted {
    color: #9aa7ba;
}
QLabel#fieldName {
    font-size: 14px;
    font-weight: 600;
    color: #e7edf4;
}
QLabel#fieldDesc {
    color: #9aa7ba;
}
QLabel#mono {
    font-family: "Cascadia Code", "Consolas", "Courier New", monospace;
    color: #9ecbff;
    background-color: #151b23;
    border: 1px solid #2b3744;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 13px;
    selection-background-color: #2f5da8;
}
QLabel#monoValue {
    font-family: "Cascadia Code", "Consolas", "Courier New", monospace;
    color: #d8e6ff;
    font-size: 14px;
    font-weight: 600;
}
QLabel#mtiBig {
    font-family: "Cascadia Code", "Consolas", "Courier New", monospace;
    color: #7db4ff;
    font-size: 26px;
    font-weight: 800;
    letter-spacing: 2px;
    background-color: #12263f;
    border: 1px solid #2f5da8;
    border-radius: 8px;
    padding: 6px 14px;
}
QLabel#mtiAutoHint {
    color: #57d687;
    font-size: 12px;
    font-weight: 600;
}
QLabel#fieldValue {
    font-family: "Cascadia Code", "Consolas", "Courier New", monospace;
    color: #9ecbff;
    font-size: 15px;
    font-weight: 700;
    background-color: #12263f;
    border: 1px solid #2f5da8;
    border-radius: 6px;
    padding: 5px 12px;
    selection-background-color: #2f5da8;
}
QLabel#hexSmall {
    font-family: "Cascadia Code", "Consolas", "Courier New", monospace;
    color: #7b8794;
    font-size: 12px;
}
QLabel#emvName {
    color: #c9d6e4;
    font-size: 12px;
}
QLabel#emvHex {
    font-family: "Cascadia Code", "Consolas", "Courier New", monospace;
    color: #9ecbff;
    font-size: 12px;
}
QLabel#emvNote {
    color: #57d687;
    font-size: 12px;
}
QLabel#errorText {
    color: #f08078;
    font-weight: 600;
}
QLabel#warnText {
    color: #e3b341;
    font-weight: 600;
}
QLabel#infoText {
    color: #57d687;
    font-weight: 600;
}

QLabel[badge="accent"] {
    background-color: #1e3a63;
    color: #7db4ff;
    border: 1px solid #2f5da8;
    border-radius: 5px;
    padding: 2px 8px;
    font-weight: 600;
    font-family: "Cascadia Code", "Consolas", monospace;
}
QLabel[badge="muted"] {
    background-color: #263041;
    color: #9aa7ba;
    border: 1px solid #33405a;
    border-radius: 5px;
    padding: 2px 8px;
    font-family: "Cascadia Code", "Consolas", monospace;
}
QLabel[badge="green"] {
    background-color: #173a24;
    color: #57d687;
    border: 1px solid #1f5a37;
    border-radius: 5px;
    padding: 2px 8px;
    font-family: "Cascadia Code", "Consolas", monospace;
}
QLabel[badge="warn"] {
    background-color: #3a2c16;
    color: #e3b341;
    border: 1px solid #5c451a;
    border-radius: 5px;
    padding: 2px 8px;
    font-family: "Cascadia Code", "Consolas", monospace;
}
QLabel[badge="error"] {
    background-color: #3d1d1c;
    color: #f08078;
    border: 1px solid #662a27;
    border-radius: 5px;
    padding: 2px 8px;
    font-family: "Cascadia Code", "Consolas", monospace;
}

QPushButton {
    background-color: #263041;
    color: #d7dee7;
    border: 1px solid #33405a;
    border-radius: 8px;
    padding: 7px 14px;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #2e3b4f;
    border-color: #3f4f6a;
}
QPushButton:pressed {
    background-color: #1e2733;
}
QPushButton:disabled {
    background-color: #1c242f;
    color: #5a6675;
    border-color: #232c38;
}
QPushButton#bigButton {
    background-color: #2f7df0;
    color: #ffffff;
    border: none;
    border-radius: 10px;
    font-size: 15px;
    font-weight: 700;
    padding: 12px 24px;
    letter-spacing: 0.5px;
}
QPushButton#bigButton:hover {
    background-color: #3f89f7;
}
QPushButton#bigButton:pressed {
    background-color: #2567c9;
}
QPushButton#ghostButton {
    background-color: transparent;
    border: 1px solid #33405a;
}
QPushButton#ghostButton:hover {
    background-color: #263041;
}
QPushButton#toggleButton {
    background-color: transparent;
    border: 1px solid #33405a;
    color: #9aa7ba;
}
QPushButton#toggleButton:hover {
    background-color: #263041;
    color: #d7dee7;
}
QPushButton#toggleButton:checked {
    background-color: #1e3a63;
    border: 1px solid #2f5da8;
    color: #7db4ff;
}

QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QSpinBox {
    background-color: #161c25;
    border: 1px solid #2b3744;
    border-radius: 8px;
    padding: 7px 10px;
    color: #d7dee7;
    selection-background-color: #2f5da8;
}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QComboBox:focus, QSpinBox:focus {
    border-color: #2f7df0;
}
QSpinBox::up-button, QSpinBox::down-button {
    background-color: #263041;
    border: 1px solid #33405a;
    border-radius: 4px;
    width: 18px;
    subcontrol-origin: border;
}
QSpinBox::up-button:hover, QSpinBox::down-button:hover {
    background-color: #2e3b4f;
}
QSpinBox::up-arrow {
    image: none;
    width: 0;
    height: 0;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-bottom: 5px solid #9aa7ba;
}
QSpinBox::down-arrow {
    image: none;
    width: 0;
    height: 0;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #9aa7ba;
}
QTextEdit#inputEdit {
    font-family: "Cascadia Code", "Consolas", "Courier New", monospace;
    font-size: 13px;
    background-color: #0f141b;
}
QPlainTextEdit#outputEdit {
    font-family: "Cascadia Code", "Consolas", "Courier New", monospace;
    font-size: 13px;
    background-color: #0f141b;
}
QComboBox::drop-down {
    border: none;
    width: 24px;
}
QComboBox QAbstractItemView {
    background-color: #1e2733;
    border: 1px solid #2b3744;
    selection-background-color: #2f5da8;
    color: #d7dee7;
}

QCheckBox {
    color: #aeb9c6;
    spacing: 6px;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1px solid #33405a;
    background-color: #161c25;
}
QCheckBox::indicator:checked {
    background-color: #2f7df0;
    border-color: #2f7df0;
}

QTableWidget {
    background-color: #161c25;
    alternate-background-color: #1a212c;
    border: 1px solid #2b3744;
    border-radius: 8px;
    gridline-color: #222c39;
    color: #d7dee7;
    selection-background-color: #1e3a63;
}
QTableWidget::item { padding: 4px 6px; }
QHeaderView::section {
    background-color: #1e2733;
    color: #9aa7ba;
    border: none;
    border-bottom: 1px solid #2b3744;
    padding: 6px 8px;
    font-weight: 600;
}

QTabWidget::pane {
    border: 1px solid #2b3744;
    border-radius: 8px;
    top: -1px;
    background-color: #151b23;
}
QTabBar::tab {
    background-color: #1e2733;
    color: #9aa7ba;
    border: 1px solid #2b3744;
    border-bottom: none;
    padding: 8px 18px;
    margin-right: 3px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    font-weight: 600;
}
QTabBar::tab:selected {
    background-color: #263041;
    color: #d7dee7;
    border-top: 2px solid #2f7df0;
}
QTabBar::tab:hover:!selected {
    background-color: #232d3a;
}

QToolButton#collapseToggle {
    background-color: transparent;
    border: none;
    color: #8a97a8;
    font-weight: 600;
    padding: 4px;
    text-align: left;
}
QToolButton#collapseToggle:hover { color: #d7dee7; }

QSplitter::handle {
    background-color: #222c39;
    width: 1px;
}
QSplitter::handle:hover { background-color: #2f7df0; }

/* ---------- Centro de Referencia ---------- */
QWidget#referencePanel {
    background-color: #151b23;
}
QWidget#referencePanel QLabel {
    color: #d7dee7;
}
QScrollArea, QSplitter, QStackedWidget {
    background-color: #151b23;
    border: none;
}
QScrollArea > QWidget > QWidget {
    background-color: #151b23;
}
QWidget#refContainer {
    background-color: #151b23;
}
QListWidget {
    background-color: #161c25;
    border: 1px solid #2b3744;
    border-radius: 8px;
    color: #c6d2de;
    outline: none;
}
QListWidget::item {
    padding: 7px 10px;
    color: #c6d2de;
    border-radius: 5px;
}
QListWidget::item:hover {
    background-color: #232d3a;
    color: #e6ecf2;
}
QListWidget::item:selected {
    background-color: #1e3a63;
    border: 1px solid #2f5da8;
    color: #a8d0ff;
}
QPushButton#refEntry {
    background-color: #1d2733;
    border: 1px solid #2b3744;
    border-radius: 6px;
    color: #dde4ec;
    text-align: left;
    padding: 6px 10px;
    font-weight: 500;
}
QPushButton#refEntry:hover {
    background-color: #25344a;
    border-color: #3f5b85;
    color: #ffffff;
}
QPushButton#refEntry:pressed {
    background-color: #182230;
}
QPushButton#primaryButton {
    background-color: #2f7df0;
    color: #ffffff;
    border: none;
    border-radius: 8px;
    font-weight: 600;
    font-size: 13px;
    padding: 0 22px;
}
QPushButton#primaryButton:hover {
    background-color: #3f89f7;
}
QPushButton#primaryButton:pressed {
    background-color: #2567c9;
}
QLabel#refValue {
    color: #cfd8e3;
    font-size: 13px;
    border: 1px solid transparent;
    border-radius: 5px;
}
QLabel#refValue:hover {
    background-color: #212c3a;
    border-color: #2b3744;
}
QLabel#refValueStrong {
    color: #e6ecf2;
    font-weight: 600;
}

/* ---------- Alertas / notificaciones ---------- */
QMessageBox {
    background-color: #1c2530;
}
QMessageBox QLabel {
    color: #dde4ec;
    font-size: 13px;
}
QMessageBox QPushButton {
    min-width: 90px;
}
QDialog {
    background-color: #1c2530;
}
QDialog QLabel {
    color: #dde4ec;
}
"""
