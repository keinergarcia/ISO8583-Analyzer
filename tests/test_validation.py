# -*- coding: utf-8 -*-
"""Tests de la validación de tramas (clean_hex / validate_hex).

Cubre el caso real: caracteres Unicode invisibles inyectados por el
portapapeles/Word/PDF (ZWSP, BOM, NBSP, soft hyphen, marcas LTR/RTL)
no deben generar el error "Caracteres no permitidos".
"""

import core.api as api
from core.parser import ParseError, parse_message
from core.utils import clean_hex, validate_hex

ZWSP = "\u200b"   # zero-width space (U+200B)
BOM = "\ufeff"    # byte order mark (U+FEFF)
NBSP = "\u00a0"   # non-breaking space (U+00A0)
SOFTHYPHEN = "\u00ad"  # soft hyphen (U+00AD)
LTR = "\u200e"    # left-to-right mark (U+200E)


def test_clean_hex_removes_invisible():
    for ch in (ZWSP, BOM, NBSP, SOFTHYPHEN, LTR):
        assert clean_hex("00" + ch + "64") == "0064"


def test_clean_hex_removes_whitespace():
    assert clean_hex(" 00 64\t80\n60\r\n00 01 ") == "006480600001"
    assert clean_hex("0064-6080:0001") == "006460800001"


def test_clean_hex_none_and_empty():
    assert clean_hex(None) == ""
    assert clean_hex("") == ""


def test_validate_accepts_invisible_chars():
    frame = "00" + ZWSP + "64" + BOM + "6080" + NBSP + "0001"
    clean, err = validate_hex(frame)
    assert err == ""
    assert clean == "006460800001"


def test_validate_accepts_whitespace_and_separators():
    clean, err = validate_hex(" 0037 6080000001\n0810\t2020\n")
    assert err == ""
    assert clean == "0037608000000108102020"


def test_validate_rejects_visible_non_hex():
    clean, err = validate_hex("0064ls00")
    assert err == "Caracteres no permitidos en la trama: ls"
    assert clean == ""


def test_validate_empty_and_odd():
    _, err = validate_hex("   ")
    assert "vacía" in err
    _, err = validate_hex("123")
    assert "par" in err


def test_parse_message_with_invisible_chars():
    raw = "0037" + ZWSP + "6080000001" + BOM + "0810" + NBSP + "2020000000800013"
    raw += ZWSP + "990001" + SOFTHYPHEN + "000853" + LTR + "3136303030303636"
    raw += "06" + BOM + "000000" + "0D" + "41435455414C495A4143494F4E"
    raw += "A1B23C44A1B23C44"
    res = parse_message(raw)
    assert res.mti.hex == "0810"
    assert [f.number for f in res.fields] == [3, 11, 41, 60, 63, 64]
    assert not res.errors


def test_api_decode_with_invisible_chars():
    raw = "0037" + BOM + "6080000001" + NBSP + "0810" + LTR + "2020000000800013"
    raw += ZWSP + "990001" + "000853" + "3136303030303636" + "06" + "000000"
    raw += "0D" + "41435455414C495A4143494F4E" + "A1B23C44A1B23C44"
    msg = api.decode(raw)
    assert msg.legacy.mti.hex == "0810"


def test_validate_still_raises_for_letters():
    try:
        api.decode("0064hola")
        raise AssertionError("debería lanzar ParseError")
    except ParseError:
        pass


def test_report_diagnostics_content(tmp_path, monkeypatch, capsys):
    import core.utils as utils
    from core.utils import report_diagnostics

    monkeypatch.setattr(utils, "diagnostics_log_path", lambda: tmp_path / "diag.log")
    report_diagnostics("0064ls00", "006400", [("l", 4), ("s", 5)])

    out = capsys.readouterr().out
    assert "RAW: '0064ls00'" in out
    assert "CLEAN: '006400'" in out
    assert "Carácter inválido: 'l'" in out
    assert "Unicode: 0x006C" in out
    assert "Posición: 4" in out
    assert "Carácter inválido: 's'" in out
    assert "Unicode: 0x0073" in out
    assert "Posición: 5" in out

    log = tmp_path / "diag.log"
    assert log.exists()
    assert "0064ls00" in log.read_text(encoding="utf-8")
