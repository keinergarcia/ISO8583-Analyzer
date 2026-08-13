# -*- coding: utf-8 -*-
"""Tests de la función "Organizar trama" (organize_hex).

Verifica que la organización visual no modifique los datos: solo inserta
saltos de línea y comprueba la integridad antes de devolver el resultado.
"""

from core.utils import organize_hex

FRAME = "0064608000000108102020000002800010"


def test_organizes_in_16_bytes_lines():
    out, err = organize_hex(FRAME)
    assert err == ""
    assert out == FRAME[:32] + "\n" + FRAME[32:]


def test_organizes_in_custom_bytes_per_line():
    out, err = organize_hex(FRAME, bytes_per_line=8)
    assert err == ""
    assert out == "\n".join([FRAME[i:i + 16] for i in range(0, len(FRAME), 16)])


def test_removes_spaces_tabs_newlines_only():
    raw = " 00 64\t60\n80\r\n00 01 08\t10 "
    out, err = organize_hex(raw)
    assert err == ""
    # Sin separadores originales: solo se conservan los saltos de línea nuevos.
    assert out.replace("\n", "") == "0064608000010810"


def test_integrity_is_exact():
    out, err = organize_hex(FRAME)
    assert err == ""
    assert out.replace("\n", "").replace("\r", "") == FRAME


def test_empty_input():
    out, err = organize_hex("")
    assert out == ""
    assert "vacía" in err


def test_whitespace_only_input():
    out, err = organize_hex("   \t\n  ")
    assert out == ""
    assert "vacía" in err


def test_none_input():
    out, err = organize_hex(None)
    assert out == ""
    assert "vacía" in err


def test_rejects_non_hex_chars():
    out, err = organize_hex("0064ls00")
    assert out == ""
    assert "no son hexadecimales" in err


def test_rejects_odd_length():
    out, err = organize_hex("123")
    assert out == ""
    assert "par" in err


def test_single_short_frame_no_change():
    out, err = organize_hex("00")
    assert err == ""
    assert out == "00"


def test_second_pass_is_stable():
    # Organizar una trama ya organizada debe ser idéntico (idempotente).
    first, err = organize_hex(FRAME)
    assert err == ""
    second, err2 = organize_hex(first)
    assert err2 == ""
    assert second == first
