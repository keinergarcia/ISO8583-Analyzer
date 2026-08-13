# -*- coding: utf-8 -*-
"""Regresión de la capa de presentación del reporte ISO8583 Analyzer.

Cadena inviolable: HEX -> parser -> Field.value -> UI/reporte.
El valor de cada Data Element debe llegar y mostrarse LITERAL, sin
transformaciones Markdown ni escapes. Lo demuestran con la trama Promerica
real (DE60 con '_', DE62 con '_' y '|').

Garantías cubiertas:
- DE60 conserva '_'
- DE62 conserva '_' y '|'
- no aparece '[URL](URL)'
- no aparece barra-baja escapada
- no aparece tuberia escapada
- el HEX original no cambia
- parser intacto y sin errores
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QLabel

import core.api as api
from core.exporter import result_to_text
from tests.fixtures.frames import FRAME_PROMERICA

PROMERICA_PROFILE = "promerica"

DE60_EXPECTED = (
    "[9220_9222750206_20250918_130414_945, NEW9220, 9222750206]"
)

DE62_EXPECTED = (
    "https://notificaciones-qa.promerica.fi.cr/voucher-merchant/"
    "GFLfE_td1YAXRltlv689MKHa00POIXKYciYTYE8RrCTCkB9jyy3UVVqRjAgNnqHp9JkD"
    "|"
    "https://notificaciones-qa.promerica.fi.cr/voucher-client/"
    "GFLfE_td1YAXRltlv689MKHa00POIXKYciYTYE8RrCTCkB9jyy3UVVqRjAgNnqHp9JkD"
)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _promerica_fields():
    msg = api.decode(FRAME_PROMERICA, profile_name=PROMERICA_PROFILE)
    return msg, {f.number: f for f in msg.legacy.fields}


def _assert_literal(shown, raw):
    """El texto mostrado debe ser idéntico al valor original decodificado."""
    assert shown == raw
    assert "\\_" not in shown
    assert "\\|" not in shown
    assert "](" not in shown


# ---------------------------------------------------------------- parser


def test_parser_de60_keeps_underscores():
    _, fields = _promerica_fields()
    assert fields[60].value == DE60_EXPECTED
    assert fields[60].value.count("_") == 4
    assert "\\_" not in fields[60].value


def test_parser_de62_keeps_underscore_and_pipe():
    _, fields = _promerica_fields()
    assert fields[62].value == DE62_EXPECTED
    assert fields[62].value.count("_") == 2
    assert fields[62].value.count("|") == 1
    assert "\\_" not in fields[62].value
    assert "\\|" not in fields[62].value
    assert "[URL" not in fields[62].value


def test_hex_original_no_cambia():
    msg, fields = _promerica_fields()
    r = msg.legacy
    assert r.raw_clean.upper() == FRAME_PROMERICA.upper()
    assert r.consumed_hex == 760
    assert r.declared_hex == 760
    assert not r.errors
    assert not r.warnings
    assert bytes.fromhex(fields[60].raw_hex).decode("ascii") == fields[60].value
    assert bytes.fromhex(fields[62].raw_hex).decode("ascii") == fields[62].value


# ------------------------------------------------------------- reporte TXT


def test_reporte_valor_lines_literal():
    """Las líneas 'Valor:' y 'Contenido:' del reporte conservan el valor."""
    body = result_to_text(_promerica_fields()[0].legacy)
    assert f"    Valor:  {DE60_EXPECTED}" in body
    assert f"    Valor:  {DE62_EXPECTED}" in body
    assert DE62_EXPECTED in body


def test_reporte_no_tiene_markdown_ni_escapes():
    body = result_to_text(_promerica_fields()[0].legacy)
    assert "\\_" not in body
    assert "\\|" not in body
    assert f"[{DE62_EXPECTED}]({DE62_EXPECTED})" not in body
    assert f"[{DE60_EXPECTED}]({DE60_EXPECTED})" not in body


# ------------------------------------------------------------------- UI


def _field_card_labels(window, field):
    """Devuelve (card, labels) manteniendo la tarjeta viva durante la aserción."""
    card = window._field_card(field)
    labels = [
        child for child in card.findChildren(QLabel)
        if child.objectName() == "fieldValue"
    ]
    return card, labels


@pytest.mark.parametrize(
    "value",
    [
        "URL1|URL2",
        DE62_EXPECTED,
        DE60_EXPECTED,
        "GFLfE_td1",
    ],
)
def test_field_card_muestra_valor_literal(qapp, value):
    from ui.main_window import MainWindow

    window = MainWindow()
    _, fields = _promerica_fields()
    field = next(f for f in fields.values() if f.number == 62)
    field.value = value
    card, labels = _field_card_labels(window, field)
    assert len(labels) == 1
    _assert_literal(labels[0].text(), value)


def test_campos_de60_y_de62_literal_en_ui(qapp):
    from ui.main_window import MainWindow

    window = MainWindow()
    _, fields = _promerica_fields()
    for number, expected in ((60, DE60_EXPECTED), (62, DE62_EXPECTED)):
        field = fields[number]
        card, labels = _field_card_labels(window, field)
        assert len(labels) == 1
        shown = labels[0].text()
        assert shown == expected
        assert "\\_" not in shown
        assert "\\|" not in shown
        assert "[URL" not in shown


def test_todos_los_data_elements_literal_en_ui(qapp):
    from ui.main_window import MainWindow

    window = MainWindow()
    _, fields = _promerica_fields()
    for field in fields.values():
        card, labels = _field_card_labels(window, field)
        assert len(labels) == 1, f"DE{field.number} debe tener un fieldValue"
        expected = field.value if field.value else "—"
        _assert_literal(labels[0].text(), expected)