# -*- coding: utf-8 -*-
"""Tests del Formatter (hex/ascii/binary/bcd)."""

import pytest

from core.tools import formatter


def test_render_hex():
    out = formatter.render("0064608000000108000102", "hex", 8)
    lines = out.splitlines()
    assert lines[0].startswith("00000000")
    assert "00 64 60 80" in lines[0]
    assert lines[1].startswith("00000008")
    assert "00 01 02" in lines[1]


def test_render_ascii():
    out = formatter.render("486F6C61204D756E646F", "ascii", 16)
    assert "Hola Mundo" in out


def test_render_binary():
    out = formatter.render("0F", "binary", 16)
    assert "00001111" in out


def test_render_bcd():
    out = formatter.render("123456", "bcd", 16)
    assert "12 34 56" in out


def test_render_bcd_non_decimal():
    out = formatter.render("1A2F", "bcd", 16)
    assert ".." in out


def test_render_empty():
    assert formatter.render("", "hex", 16) == ""
    assert formatter.render_rows("", "hex", 16) == []


def test_render_odd_length_raises():
    with pytest.raises(ValueError):
        formatter.render("123", "hex", 16)


def test_render_odd_length_message():
    with pytest.raises(ValueError, match="debe ser par"):
        formatter.render("123", "hex", 16)


@pytest.mark.parametrize("bad", ["12ZZ", "GG", "0XGG"])
def test_render_rejects_non_hex(bad):
    with pytest.raises(ValueError, match="carácter no permitido"):
        formatter.render(bad, "hex", 16)
    with pytest.raises(ValueError, match="carácter no permitido"):
        formatter.line_count(bad, 16)


def test_render_does_not_mutate_frame():
    frame = "00 64 60 80\n00 01 02"
    copy = frame
    out = formatter.render(frame, "hex", 8)
    assert frame == copy
    assert "00 64 60 80" in out
    assert out == formatter.render("00646080000102", "hex", 8)


def test_render_bad_style_raises():
    with pytest.raises(ValueError):
        formatter.render("12", "xml", 16)


def test_line_count():
    assert formatter.line_count("0064608000000108", 8) == 1
    assert formatter.line_count("0064608000000108000102", 8) == 2
    assert formatter.line_count("", 8) == 0
