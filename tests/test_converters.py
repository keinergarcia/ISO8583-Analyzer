# -*- coding: utf-8 -*-
"""Tests de los conversores (HEX/ASCII/BIN/DECIMAL/BCD)."""

import pytest

from core import converters


# ---------------------------------------------------------------------------
# HEX → ASCII / ASCII → HEX
# ---------------------------------------------------------------------------

def test_hex_to_ascii_basic():
    assert converters.hex_to_ascii("414243") == "ABC"


def test_hex_to_ascii_spaces_ok():
    assert converters.hex_to_ascii("41 42 43") == "ABC"


def test_hex_to_ascii_non_printable_uses_dot():
    assert converters.hex_to_ascii("00") == "."


def test_hex_to_ascii_frame():
    frame = "006460800000010810202000000280001093001000008530313630303030363635"
    out = converters.hex_to_ascii(frame)
    assert out[0] == "."
    assert out[1] == "d"
    assert out[2] == "`"


def test_hex_to_ascii_rejects_non_hex():
    for bad in ("GG", "0XGG", "12ZZ"):
        with pytest.raises(ValueError):
            converters.hex_to_ascii(bad)


def test_hex_to_ascii_rejects_odd_length():
    with pytest.raises(ValueError, match="par"):
        converters.hex_to_ascii("ABC")


def test_ascii_to_hex_basic():
    assert converters.ascii_to_hex("ABC") == "414243"


def test_ascii_to_hex_spaces_preserved():
    assert converters.ascii_to_hex("Hola mundo") == "486F6C61206D756E646F"


def test_ascii_to_hex_long_text_roundtrip():
    text = "ACTUALIZACION DECLINADA CONFIGURACION X GRUPO - HORA FUERA DE RANGO"
    assert converters.hex_to_ascii(converters.ascii_to_hex(text)) == text


def test_ascii_to_hex_empty():
    assert converters.ascii_to_hex("") == ""


# ---------------------------------------------------------------------------
# HEX ↔ BINARIO
# ---------------------------------------------------------------------------

def test_hex_to_binary_single_byte():
    assert converters.hex_to_binary("FF") == "11111111"
    assert converters.hex_to_binary("00") == "00000000"
    assert converters.hex_to_binary("64") == "01100100"


def test_hex_to_binary_multi_byte_ordered():
    assert converters.hex_to_binary("0064") == "00000000 01100100"


def test_hex_to_binary_rejects_invalid():
    with pytest.raises(ValueError):
        converters.hex_to_binary("GG")
    with pytest.raises(ValueError, match="par"):
        converters.hex_to_binary("ABC")


def test_binary_to_hex_single_byte():
    assert converters.binary_to_hex("11111111") == "FF"
    assert converters.binary_to_hex("00000000") == "00"


def test_binary_to_hex_multi_byte():
    assert converters.binary_to_hex("00000000 01100100") == "0064"


def test_binary_to_hex_rejects_invalid():
    with pytest.raises(ValueError):
        converters.binary_to_hex("11111112")
    with pytest.raises(ValueError, match="múltiplo de 8"):
        converters.binary_to_hex("101")


# ---------------------------------------------------------------------------
# DECIMAL ↔ HEX / DECIMAL ↔ BINARIO
# ---------------------------------------------------------------------------

def test_hex_to_decimal():
    assert converters.hex_to_decimal("0064") == "100"
    assert converters.hex_to_decimal("FF") == "255"


def test_decimal_to_hex():
    assert converters.decimal_to_hex("255") == "FF"
    assert converters.decimal_to_hex("256") == "100"
    assert converters.decimal_to_hex("0") == "00"


def test_decimal_to_binary():
    assert converters.decimal_to_binary("255") == "11111111"
    assert converters.decimal_to_binary("256") == "100000000"
    assert converters.decimal_to_binary("0") == "0"


def test_binary_to_decimal():
    assert converters.binary_to_decimal("11111111") == "255"
    assert converters.binary_to_decimal("100000000") == "256"


def test_binary_to_decimal_rejects_invalid():
    with pytest.raises(ValueError):
        converters.binary_to_decimal("102")


# ---------------------------------------------------------------------------
# BCD
# ---------------------------------------------------------------------------

def test_bcd_roundtrip():
    assert converters.decimal_to_bcd("123456") == "123456"
    assert converters.bcd_to_decimal("123456") == "123456"


def test_bcd_odd_digits_padded_with_f():
    assert converters.decimal_to_bcd("123") == "123F"


def test_bcd_invalid_nibbles():
    with pytest.raises(ValueError):
        converters.bcd_to_decimal("1A2F")


# ---------------------------------------------------------------------------
# Utilidades de espaciado
# ---------------------------------------------------------------------------

def test_add_spaces():
    assert converters.add_spaces("00646080000001") == "00 64 60 80 00 00 01"


def test_remove_spaces():
    assert converters.remove_spaces("00 64 60 80") == "00646080"
