# -*- coding: utf-8 -*-
"""Tests del offset del MTI: detección automática, offset manual y depuración.

Cubre el caso real reportado: el parser no debe asumir siempre "2 bytes de
longitud + 5 bytes de TPDU" antes del MTI. Debe localizar el MTI por sí mismo
o usar el offset manual configurado.
"""

import core.api as api
from core.parser import ParseOptions, parse_message
from tests.fixtures.frames import FRAME_BASIC

# Trama con cabecera propietaria de 3 bytes entre TPDU y MTI:
# [2 longitud][5 TPDU][3 header][2 MTI][8 bitmap][datos]
# longitud = 5+3+2+8+40 = 58 = 0x003A
FIELDS = ("9900010008533136303030303636"
          "06000000"
          "0D41435455414C495A4143494F4E"
          "A1B23C44A1B23C44")
FRAME_HEADER = "003A" + "6000018000" + "AABBCC" + "0200" + "2020000000800013" + FIELDS

# Trama BCD donde DE63 (an) contiene texto literal no-hex (simula JSON/XML/
# Base64 o datos propietarios): no debe rechazarse ni validarse como hex.
FRAME_LITERAL = (
    "0034" + "6080000001" + "0810" + "2020000000800013"
    + "9900010008533136303030303636"
    + "06" + "000000"
    + "0A" + "HOLAMUNDOX"
    + "A1B23C44A1B23C44"
)


def test_basic_matches_reference_layout():
    """FRAME_BASIC: MTI en el byte 7 (2 longitud + 5 TPDU), igual que el
    decoder de referencia con TPDU_byte=7."""
    r = parse_message(FRAME_BASIC)
    assert r.mti.hex == "0810"
    assert r.mti_offset_bytes == 7
    assert [f.number for f in r.fields] == [3, 11, 41, 60, 63, 64]
    assert r.fields[4].value == "ACTUALIZACION"
    assert not r.errors


def test_auto_detects_proprietary_header_before_mti():
    """La detección automática debe encontrar el MTI en el byte 10 pese a la
    cabecera propietaria de 3 bytes entre el TPDU y el MTI."""
    r = parse_message(FRAME_HEADER)
    assert r.mti.hex == "0200"
    assert r.mti_offset_bytes == 10, r.mti_offset_bytes
    assert r.header_hex == "003A6000018000AABBCC"
    assert [f.number for f in r.fields] == [3, 11, 41, 60, 63, 64]
    assert r.fields[4].value == "ACTUALIZACION"
    assert not r.errors


def test_manual_offset_used():
    r = parse_message(FRAME_HEADER, ParseOptions(mti_offset=10))
    assert r.mti_offset_bytes == 10
    assert r.mti.hex == "0200"
    assert [f.number for f in r.fields] == [3, 11, 41, 60, 63, 64]


def test_manual_offset_auto_off_falls_back_to_classic():
    """Si se desactiva la detección automática sin offset manual, se usa el
    layout clásico (2 + TPDU) y la cabecera propietaria se ignora."""
    r = parse_message(FRAME_HEADER, ParseOptions(mti_auto=False))
    assert r.mti_offset_bytes == 7


def test_api_decode_with_offset_option():
    msg = api.decode(FRAME_HEADER, options=ParseOptions(mti_offset=10))
    assert msg.legacy.mti.hex == "0200"
    assert msg.metadata["mti_offset_bytes"] == 10


def test_literal_content_in_field_not_validated_as_hex():
    """Un DE con texto literal (l/s/JSON/XML/Base64) NO dispara el error
    'Caracteres no permitidos en la trama'."""
    r = parse_message(FRAME_LITERAL)
    fields = {f.number: f for f in r.fields}
    assert fields[63].value == "HOLAMUNDOX"
    assert fields[64].raw_hex == "A1B23C44A1B23C44"
    assert not r.errors


def test_debug_mode_reports_offset_and_fields(capsys):
    import core.utils as utils
    parse_message(FRAME_BASIC, ParseOptions(debug=True))
    out = capsys.readouterr().out
    assert "Offset inicial usado (bytes antes del MTI): 7" in out
    assert "MTI encontrado: 0810" in out
    assert "Bitmap encontrado: 2020000000800013" in out
    assert "DE3:" in out and "offset final byte" in out and "bytes consumidos" in out
