# -*- coding: utf-8 -*-
"""Tests del perfil Promerica (trama real de la red).

Cubre el caso reportado: DE39 = "00" (no "3030"), DE60/61/62 con prefijo de
longitud BCD de 4 dígitos (2 bytes) y datos ASCII, sin desbordes ni warnings.
"""

import core.api as api
from core.fields import DATA_ELEMENTS
from core.parser import ParseOptions, parse_message
from tests.fixtures.frames import FRAME_BASIC, FRAME_PROMERICA, FRAME_PROMERICA_DE63

PROMERICA_PROFILE = "promerica"


def _field_defs():
    defs = dict(DATA_ELEMENTS)
    profile = api.load_profile(PROMERICA_PROFILE)
    for number, fdef in profile.elements.items():
        defs[number] = fdef
    return defs


def _opts():
    return ParseOptions(
        numeric_encoding="bcd",
        llvar_prefix_bytes=2,
        lllvar_prefix_bytes=2,
        lllvar_4digit_bcd=True,
        field_defs=_field_defs(),
    )


def _fields(result):
    return {f.number: f for f in result.fields}


def test_profile_is_registered():
    names = [p["name"] for p in api.list_profiles()]
    assert PROMERICA_PROFILE in names


def test_promerica_parses_header_and_offsets():
    msg = api.decode(FRAME_PROMERICA, profile_name=PROMERICA_PROFILE)
    r = msg.legacy
    assert r.mti.hex == "0810"
    assert r.mti_offset_bytes == 7
    assert r.tpdu is not None
    assert [f.number for f in r.fields] == [3, 11, 39, 41, 60, 61, 62]


def test_promerica_de39_is_ascii_00():
    """DE39 debe ser '00' y no '3030' (interpretación BCD incorrecta)."""
    r = parse_message(FRAME_PROMERICA, _opts())
    fields = _fields(r)
    assert fields[3].value == "990001"
    assert fields[11].value == "000159"
    assert fields[39].value == "00"
    assert fields[41].value == "22210095"


def test_promerica_variable_fields_read_ascii_with_2byte_prefix():
    r = parse_message(FRAME_PROMERICA, _opts())
    fields = _fields(r)
    assert fields[60].value == "[9220_9222750206_20250918_130414_945, NEW9220, 9222750206]"
    assert fields[61].value == "APROBADO - SE ALMACENO EL RECIBO"
    assert fields[62].value.startswith("https://notificaciones-qa.promerica.fi.cr/voucher-merchant/")
    assert fields[62].value.endswith("NnqHp9JkD")
    assert len(fields[62].value) == 253
    assert not r.errors


def test_promerica_full_length_matches_no_warnings():
    msg = api.decode(FRAME_PROMERICA, profile_name=PROMERICA_PROFILE)
    r = msg.legacy
    assert r.consumed_hex == 760
    assert r.declared_hex == 760
    assert not r.errors
    assert not r.warnings
    assert len(r.raw_clean) == 764


def test_decoder_keeps_profile_settings_with_caller_default_options():
    """Simula la UI: caller pasa ParseOptions() con valores por defecto. El
    layout del perfil (prefijos 2 bytes, lllvar 4 dígitos, codificación bcd)
    no debe ser pisado por los valores por defecto del caller."""
    msg = api.decode(FRAME_PROMERICA, profile_name=PROMERICA_PROFILE,
                     options=ParseOptions(debug=False))
    r = msg.legacy
    assert r.consumed_hex == 760
    assert not r.warnings
    fields = _fields(r)
    assert fields[39].value == "00"
    assert fields[60].value.startswith("[9220_")
    assert fields[61].value == "APROBADO - SE ALMACENO EL RECIBO"


def test_decoder_respects_explicit_encoding_override():
    """Un override explícito de codificación del caller (valor distinto de
    'auto') sí se respeta, a diferencia de un valor por defecto."""
    msg = api.decode(FRAME_PROMERICA, profile_name=PROMERICA_PROFILE,
                     options=ParseOptions(numeric_encoding="bcd"))
    r = msg.legacy
    assert r.numeric_encoding == "bcd"
    assert r.consumed_hex == 760
    assert not r.warnings


def test_pick_profile_selects_promerica_for_promerica_frames():
    """El modo 'Automático' (pick_profile) elige el perfil correcto de forma
    genérica: promerica para las tramas de Promerica y el perfil por defecto
    para una trama genérica."""
    opts = ParseOptions(has_tpdu=True, numeric_encoding="auto", mti_auto=True, debug=False)
    assert api.pick_profile(FRAME_PROMERICA, opts) == "promerica"
    assert api.pick_profile(FRAME_PROMERICA_DE63, opts) == "promerica"
    assert api.pick_profile(FRAME_BASIC, opts) == "iso8583_1987"


def test_promerica_de63_frame_parses_fields():
    """Trama 0800 con DE63 (JSON) y DE64 (MAC con cabecera GZIP): los campos
    se leen en orden correcto, sin desbordes. El contenido GZIP que sigue al
    DE64 no está mapeado por el bitmap, así que queda como 'bytes sin analizar'
    (no es un desborde del parser)."""
    msg = api.decode(FRAME_PROMERICA_DE63, profile_name=PROMERICA_PROFILE)
    r = msg.legacy
    assert r.mti.hex == "0800"
    assert r.mti_offset_bytes == 7
    assert [f.number for f in r.fields] == [3, 11, 41, 60, 63, 64]
    fields = {f.number: f for f in r.fields}
    assert fields[60].value == "[9220_9222428677_20250521_095832_148, NEW9220, 9222428677]"
    assert fields[60].length_digits == 58
    assert fields[63].value == ('[["GENERIC","PROMERICA","COMPRA_PAGO_RAPIDO",'
                                '"MERCHANT_COPY","V1"]]')
    assert fields[63].length_digits == 67
    assert fields[64].raw_hex == "02501F8B08000000"
    assert fields[64].length_digits == 8
    assert not r.errors


def test_promerica_de64_gzip_note():
    """El DE64 de la trama 0800 contiene la cabecera GZIP (1F 8B 08) y debe
    anotarse sin alterar offsets: 0250 = 592 bytes de payload comprimido que
    continúan tras el campo."""
    msg = api.decode(FRAME_PROMERICA_DE63, profile_name=PROMERICA_PROFILE)
    fields = {f.number: f for f in msg.legacy.fields}
    note = fields[64].note
    assert "GZIP" in note
    assert "1F 8B 08" in note
    assert "592" in note
    assert "offset_hex" in fields[64].as_dict()
    assert fields[64].as_dict()["note"] == note


def test_promerica_debug_prints_field_details(capsys):
    """Con debug=True cada campo reporta offset inicial, offset final,
    longitud del prefijo, longitud interpretada, bytes consumidos y bytes
    restantes (para comparar paso a paso con el Transaction Decoder)."""
    opts = ParseOptions(
        numeric_encoding="bcd",
        llvar_prefix_bytes=2,
        lllvar_prefix_bytes=2,
        lllvar_4digit_bcd=True,
        field_defs=_field_defs(),
        debug=True,
    )
    parse_message(FRAME_PROMERICA_DE63, opts)
    out = capsys.readouterr().out
    assert "DE3: offset inicial byte 17 (hex 34)" in out
    assert "DE60: offset inicial byte 31 (hex 62)" in out
    assert "DE63: offset inicial byte 91 (hex 182)" in out
    assert "DE64: offset inicial byte 160 (hex 320)" in out
    for number in (3, 11, 41, 60, 63, 64):
        marker = f"DE{number}: offset inicial byte "
        assert marker in out
        assert "offset final byte " in out
        assert "longitud del prefijo " in out
        assert "longitud interpretada " in out
        assert "bytes consumidos " in out
        assert "bytes restantes " in out
    assert "DE64 nota: Cabecera GZIP" in out
