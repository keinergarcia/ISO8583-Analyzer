# -*- coding: utf-8 -*-
"""Regresión DE63 (JSON/lista) y escapes de guion bajo '\\_'.

Cubre el caso real Promerica: DE60/DE63 con guiones bajos literales (byte 5F),
DE63 con valor ASCII tipo JSON que NUNCA debe reconvertirse con HEX→string,
DE64 con cabecera GZIP y payload propietario posterior, y que no aparezca
'\\_' en UI, interpretación ni exportación TXT.

Construido para no tocar el parser, la extracción de DE63 ni la lógica GZIP.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QLabel

import core.api as api
from core.exporter import result_to_text
from core.field_interpreter import interpret_data, is_json_like
from tests.fixtures.frames import FRAME_PROMERICA_DE63

PROMERICA_PROFILE = "promerica"

DE60_VALOR = "[9220_9222428677_20250521_095832_148, NEW9220, 9222428677]"
DE63_VALOR = ('[["GENERIC","PROMERICA","COMPRA_PAGO_RAPIDO",'
              '"MERCHANT_COPY","V1"]]')
DE63_LISTA = [["GENERIC", "PROMERICA", "COMPRA_PAGO_RAPIDO",
               "MERCHANT_COPY", "V1"]]


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _result():
    msg = api.decode(FRAME_PROMERICA_DE63, profile_name=PROMERICA_PROFILE)
    return msg.legacy


def _fields(result):
    return {f.number: f for f in result.fields}


# ---------------------------------------------------------------------------
# 1. Guiones bajos literales (byte 5F): DE60 y DE63
# ---------------------------------------------------------------------------

def test_de60_underscores_literales():
    f = _fields(_result())[60]
    assert f.value == DE60_VALOR
    assert "_" in f.value
    assert "\\_" not in f.value


def test_de63_underscores_literales():
    f = _fields(_result())[63]
    assert f.value == DE63_VALOR
    assert "COMPRA_PAGO_RAPIDO" in f.value
    assert "\\_" not in f.value


# ---------------------------------------------------------------------------
# 2. DE63 se conserva como ASCII (nunca HEX→string)
# ---------------------------------------------------------------------------

def test_de63_ascii_preservado_sin_reconvertir():
    """El valor ASCII no debe convertirse con una función HEX→string."""
    f = _fields(_result())[63]
    assert f.value == DE63_VALOR
    # Si alguien intentara convertirlo como HEX fallaría (contiene [ y ",
    # que no son HEX) o produciría basura; aquí el valor queda literal.
    d = interpret_data(f)
    assert d["value"] == DE63_VALOR
    assert d["json_like"] is True


def test_is_json_like_no_trata_hex_como_json():
    """DE64 (dato binario/hex, no JSON) no se interpreta como lista."""
    f = _fields(_result())[64]
    assert is_json_like(f.value) is False
    assert interpret_data(f)["json_like"] is False
    # DE60 no es JSON válido (tokens sin comillas) → no se reinterpreta.
    f60 = _fields(_result())[60]
    assert is_json_like(f60.value) is False


# ---------------------------------------------------------------------------
# 3. DE63 interpretado estructuralmente como JSON/lista
# ---------------------------------------------------------------------------

def test_de63_json_like_estructura():
    f = _fields(_result())[63]
    d = interpret_data(f)
    assert d["parsed"] == DE63_LISTA
    assert d["json_like"] is True
    assert "COMPRA_PAGO_RAPIDO" in d["compact"]
    # El guion bajo permanece literal en TODA salida de la interpretación.
    assert "\\_" not in d["compact"]
    assert "\\_" not in d["pretty"]
    assert "\\_" not in d["value"]


# ---------------------------------------------------------------------------
# 4. DE64 y payload GZIP posterior (sin alterar la lógica existente)
# ---------------------------------------------------------------------------

def test_de64_raw_hex():
    f = _fields(_result())[64]
    assert f.raw_hex == "02501F8B08000000"
    assert f.length_digits == 8


def test_payload_gzip_posterior_confirmed():
    r = _result()
    tp = r.trailing_payload
    assert tp is not None
    assert tp.status == "confirmed"
    assert tp.kind == "gzip"
    assert tp.declared_length == 592
    assert tp.decompressed_length == 1415
    assert tp.payload_hex.startswith("1F8B08")


# ---------------------------------------------------------------------------
# 5. Exportación TXT sin '\\_' y con estructura JSON/lista
# ---------------------------------------------------------------------------

def test_export_txt_sin_escapes_ni_reconversion():
    txt = result_to_text(_result())
    assert "\\_" not in txt
    # Valor literal de DE60 y DE63 en el reporte.
    assert DE60_VALOR in txt
    assert DE63_VALOR in txt
    assert "COMPRA_PAGO_RAPIDO" in txt
    # Sección de interpretación estructural JSON/lista.
    assert "Estructura JSON/lista:" in txt
    assert '["GENERIC","PROMERICA","COMPRA_PAGO_RAPIDO","MERCHANT_COPY","V1"]' in txt
    # GZIP anotado sin tocar la lógica.
    assert "GZIP" in txt
    assert "592" in txt


# ---------------------------------------------------------------------------
# 6. Presentación UI: valor literal y preview JSON sin escapes
# ---------------------------------------------------------------------------

def _labels(window, object_name, field):
    card = window._field_card(field)
    return [c for c in card.findChildren(QLabel) if c.objectName() == object_name], card


def test_ui_field_de60_y_de63_literal(qapp):
    from ui.main_window import MainWindow

    window = MainWindow()
    r = _result()
    for number, expected in ((60, DE60_VALOR), (63, DE63_VALOR)):
        field = next(f for f in r.fields if f.number == number)
        value_labels, _card = _labels(window, "fieldValue", field)
        assert len(value_labels) == 1, f"DE{number}"
        shown = value_labels[0].text()
        assert shown == expected, f"DE{number}"
        assert "\\_" not in shown
        assert "[URL" not in shown


def test_ui_de63_preview_json_literal(qapp):
    from ui.main_window import MainWindow

    window = MainWindow()
    field = next(f for f in _result().fields if f.number == 63)
    preview, _card = _labels(window, "jsonPreview", field)
    assert len(preview) == 1
    text = preview[0].text()
    assert "COMPRA_PAGO_RAPIDO" in text
    assert "\\_" not in text