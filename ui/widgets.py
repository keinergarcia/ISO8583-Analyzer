# -*- coding: utf-8 -*-
"""Widgets reutilizables de la interfaz: tarjetas, badges, filas de valor."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

try:
    import pyperclip

    def copy_to_clipboard(text):
        pyperclip.copy(text or "")
except ImportError:  # pragma: no cover
    from PySide6.QtWidgets import QApplication

    def copy_to_clipboard(text):
        QApplication.clipboard().setText(text or "")


class Card(QFrame):
    """Panel contenedor con bordes suaves para secciones del análisis."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(16, 14, 16, 14)
        self.layout.setSpacing(8)


class SectionTitle(QLabel):
    """Título de una sección del reporte."""

    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setObjectName("sectionTitle")


def make_badge(text, kind="muted"):
    """Crea una etiqueta estilo chip con color según el tipo."""
    label = QLabel(text)
    label.setProperty("badge", kind)
    return label


class CopyButton(QPushButton):
    """Botón compacto para copiar un texto al portapapeles."""

    def __init__(self, data_provider, text="Copiar", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setProperty("ghost", True)
        self.setObjectName("ghostButton")
        self.setFixedHeight(28)
        self._provider = data_provider
        self.clicked.connect(self._on_copy)

    def _on_copy(self):
        copy_to_clipboard(self._provider())
        self.setText("Copiado ✓")
        from PySide6.QtCore import QTimer
        QTimer.singleShot(1200, lambda: self.setText("Copiar"))


class CollapsibleSection(QWidget):
    """Sección con cabecera plegable (flecha + título + contenido)."""

    def __init__(self, title, content_widget=None, parent=None):
        super().__init__(parent)
        self._collapsed = False
        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(0, 0, 0, 0)
        self._outer.setSpacing(4)

        header = QWidget()
        hlay = QHBoxLayout(header)
        hlay.setContentsMargins(0, 0, 0, 0)
        hlay.setSpacing(6)
        self._toggle = QToolButton()
        self._toggle.setObjectName("collapseToggle")
        self._toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self._toggle.setArrowType(Qt.DownArrow)
        self._toggle.setCheckable(True)
        self._toggle.clicked.connect(self._on_toggle)
        self._title = QLabel(title)
        self._title.setObjectName("cardTitle")
        hlay.addWidget(self._toggle)
        hlay.addWidget(self._title)
        hlay.addStretch(1)
        self._outer.addWidget(header)

        self._content = content_widget if content_widget is not None else QWidget()
        self._outer.addWidget(self._content)

    def _on_toggle(self, checked):
        self._content.setVisible(not checked)
        self._toggle.setArrowType(Qt.RightArrow if checked else Qt.DownArrow)

    def set_title(self, title):
        self._title.setText(title)


def add_tlv_rows(container, nodes, depth=0, inherited_indent=0):
    """Agrega filas TLV (EMV) al layout, recursivamente para hijos."""
    for raw in nodes:
        node = _as_node(raw)
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(inherited_indent + depth * 24, 0, 0, 0)
        lay.setSpacing(8)
        lay.addWidget(make_badge(node["tag"], "accent"))
        name = QLabel(node["name"])
        name.setObjectName("emvName")
        name.setWordWrap(True)
        lay.addWidget(name, 1)
        len_label = QLabel(f"Len: {node['length']}")
        len_label.setObjectName("muted")
        lay.addWidget(len_label)
        if node["value_hex"]:
            hex_label = QLabel(node["value_hex"])
            hex_label.setObjectName("emvHex")
            hex_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            lay.addWidget(hex_label, 1)
            lay.addWidget(CopyButton(lambda n=node: n["value_hex"], "Copiar"))
        container.layout.addWidget(row)
        if node["note"]:
            note = QLabel(node["note"])
            note.setObjectName("emvNote")
            note.setWordWrap(True)
            container.layout.addWidget(note)
        if node.get("interpretation"):
            interp = QLabel(f"Interpretación: {node['interpretation']}")
            interp.setObjectName("emvNote")
            interp.setWordWrap(True)
            container.layout.addWidget(interp)
        if node["children"]:
            add_tlv_rows(container, node["children"], depth + 1)


def _as_node(raw):
    """Normaliza un nodo TLV (dict o TlvNode) a dict."""
    if isinstance(raw, dict):
        return raw
    return {
        "tag": raw.tag,
        "name": raw.name,
        "length": raw.length,
        "value_hex": raw.value_hex,
        "note": raw.note,
        "interpretation": getattr(raw, "interpretation", ""),
        "children": raw.children,
    }


def field_badges(field):
    """Chips de tipo y longitud de un campo analizado."""
    type_map = {
        "n": "n (numérico)",
        "a": "a (alfabético)",
        "an": "an (alfanumérico)",
        "ans": "ans (alfanumérico esp.)",
        "b": "b (binario)",
        "z": "z (track 2)",
    }
    badges = [make_badge(type_map.get(field.ftype, field.ftype), "muted")]
    if field.length_type == "fixed":
        badges.append(make_badge(f"Fijo {field.max_length}", "muted"))
    else:
        badges.append(make_badge(f"Variable {field.length_type.upper()} máx {field.max_length}", "muted"))
    return badges
