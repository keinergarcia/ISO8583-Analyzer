# -*- coding: utf-8 -*-
"""Tests de la fachada pública core.api."""

import core.api as api
from core.model.message import Message
from core.parser import ParseError, ParseOptions, parse_message
from tests.fixtures.frames import (
    FRAME_ASCII_HEX,
    FRAME_ASCII_ND_HEX,
    FRAME_ASCII_TRAIL_HEX,
    FRAME_BASIC,
    FRAME_EMV,
    FRAME_HYBRID,
)


def test_decode_basic_matches_legacy():
    msg = api.decode(FRAME_BASIC)
    result = msg.legacy
    legacy = parse_message(FRAME_BASIC)
    assert result.raw_clean == legacy.raw_clean
    assert result.mti.hex == legacy.mti.hex
    assert [f.number for f in result.fields] == [f.number for f in legacy.fields]
    assert result.warnings == legacy.warnings


def test_decode_ascii():
    msg = api.decode(FRAME_ASCII_HEX)
    assert msg.encoding == "ascii"
    assert msg.legacy.mti.hex == "0810"
    assert msg.active_fields == [3, 11]
    fields = {f.number: f for f in msg.legacy.fields}
    assert fields[3].value == "990001"
    assert fields[11].value == "000853"
    assert not msg.issues.warnings


def test_decode_invalid_raises():
    try:
        api.decode("ZZZ")
        raise AssertionError("debería lanzar ParseError")
    except ParseError:
        pass


def test_detect_ascii_non_numeric_length():
    msg = api.decode(FRAME_ASCII_ND_HEX)
    assert msg.encoding == "ascii"
    assert msg.legacy.mti.hex == "0200"
    assert msg.active_fields == [3]
    assert any("no numérico" in i.message for i in msg.issues)


def test_ascii_remaining_warning():
    msg = api.decode(FRAME_ASCII_TRAIL_HEX)
    assert msg.encoding == "ascii"
    assert any("sin analizar" in i.message for i in msg.issues)


def test_decode_emv():
    msg = api.decode(FRAME_EMV)
    assert sum(1 for n in msg.walk() if n.kind == "tlv") == 8
    assert 55 in msg.active_fields


def test_decode_hybrid_auto():
    msg = api.decode(FRAME_HYBRID)
    assert msg.encoding == "hybrid"
    assert msg.legacy.mti.hex == "0200"
    assert msg.active_fields == [3, 4, 11, 41, 49]
    fields = {f.number: f for f in msg.legacy.fields}
    assert fields[3].value == "003000"
    assert fields[4].value == "000000000336"
    assert fields[11].value == "123456"
    assert fields[41].value == "ABC12345"
    assert fields[49].value == "604"
    assert not any("no coincide" in i.message for i in msg.issues)
    assert not msg.legacy.errors


def test_decode_hybrid_forced_bcd_still_works():
    msg = api.decode(FRAME_HYBRID, options=ParseOptions(numeric_encoding="bcd"))
    assert msg.encoding == "bcd"
    assert msg.legacy.mti.hex == "0200"



def test_validate_returns_issues():
    msg = api.decode(FRAME_BASIC)
    issues = api.validate(msg)
    assert list(issues) == list(msg.issues)


def test_list_decoders():
    assert "iso8583" in api.list_decoders()


def test_profiles_api():
    assert any(p["name"] == "iso8583_1993" for p in api.list_profiles())
    assert api.load_profile("iso8583_2003").name == "iso8583_2003"
    assert api.get_default_profile().name == "iso8583_1987"


def test_format_frame_api():
    out = api.format_frame("0064608000000108", "hex", 8)
    assert "00000000" in out
    assert "00 64 60 80" in out


def test_tools_api():
    msg = api.decode(FRAME_BASIC)
    table = api.bitmap_table(msg)
    assert len(table) >= 120
    present = [r for r in table if r["present"]]
    assert [r["number"] for r in present] == [3, 11, 41, 60, 63, 64]
    assert len(api.dictionary_all()) >= 90
    assert api.dictionary_search("processing code")[0]["number"] == 3
