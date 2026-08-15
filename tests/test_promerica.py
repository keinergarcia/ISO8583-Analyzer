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

# Trama 0200 completa de la red Promerica (autorización, real): cabeceras
# binarias + campos BCD. LLVAR de 1 byte (DE32/35), LLLVAR de 2 bytes con
# BCD de 4 dígitos (DE48/55/60/63/112/114/119/120/127) y padding leading.
# Longitud 01be = 446 bytes. DE55 = 149 bytes con 21 TLV.
FRAME_PROMERICA_0200 = (
    "01be60000180000200b038464120c182"
    "10000000000001430200300000000000"
    "03360000661206000817554100520000"
    "0606179130376262893000001204d240"
    "92011000079600000f32303131303334"
    "31303030303030383731373033202020"
    "00103935303645435543544108400149"
    "9f26081ad085579ef40b059f2701809f"
    "101307010103a0a002010a0100000000"
    "00ee04e0409f370454ee45a29f360204"
    "0f9505008000e0009a032308179c0100"
    "9f02060000000003365f2a0208408202"
    "7c009f1a0202189f0306000000000000"
    "9f3303e0f8c89f34031e03009f350121"
    "9f1e0832303039343336308408a00000"
    "03330101029f090200209f4104000000"
    "665f340100008430334d323430323030"
    "30363030303330303030303030303030"
    "30303132443236303030303030303030"
    "30333030323138303030303030303030"
    "30553233303230303036303030333030"
    "30303030303030303030310012303035"
    "30303630343033303000063030303034"
    "31002430303030303030303033303030"
    "30303030303030303030300014313130"
    "30303030303030303033360035463030"
    "30324630313130322e332e352e323430"
    "37463032313039323230303934333630"
)


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
    se leen en orden correcto, sin desbordes. DE64 permanece fixed de 8 bytes
    (ISO 8583) y el GZIP que continúa tras el campo se explica como payload
    propietario encapsulado, no como 'bytes sin analizar'."""
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


def _frame_de64(de64_hex, trailing_hex=""):
    """Construye una trama BCD mínima con DE3 y DE64 como último campo."""
    bitmap = "2000000000000001"  # DE3 + DE64
    body = "6000000000" + "0200" + bitmap + "990001" + de64_hex + trailing_hex
    return "%04X" % (len(body) // 2) + body


def test_promerica_de63_trailing_payload_confirmed():
    """El DE64 (02501F8B08000000) declara 0x0250 = 592 bytes de payload
    comprimido. Los 592 bytes (6 dentro del campo + 586 posteriores) forman un
    stream GZIP válido que descomprime a 1415 bytes: la trama queda explicada
    y NO se reporta 'bytes sin analizar'."""
    r = parse_message(FRAME_PROMERICA_DE63, _opts())
    tp = r.trailing_payload
    assert tp is not None
    assert tp.status == "confirmed"
    assert tp.kind == "gzip"
    assert tp.declared_length == 592
    assert tp.available_length == 592
    assert tp.decompressed_length == 1415
    assert tp.offset_hex == 324
    assert tp.payload_hex.startswith("1F8B08")
    assert len(tp.payload_hex) // 2 == 592
    assert not any("sin analizar" in w for w in r.warnings)
    assert any("payload propietario encapsulado tras DE64" in w for w in r.warnings)


def test_promerica_de63_trailing_payload_in_validation():
    """El motor de validación emite TRAILING_DATA_EXPLAINED (INFO) en lugar de
    la advertencia TRAILING_DATA para un payload propietario confirmado."""
    from core.validation import SEVERITY_WARNING, validate_result
    r = parse_message(FRAME_PROMERICA_DE63, _opts())
    vr = validate_result(r)
    codes = [f.code for f in vr.findings]
    assert "TRAILING_DATA_EXPLAINED" in codes
    assert "TRAILING_DATA" not in [
        f.code for f in vr.findings if f.severity == SEVERITY_WARNING
    ]
    info = next(f for f in vr.findings if f.code == "TRAILING_DATA_EXPLAINED")
    assert "592" in info.value


def test_promerica_de64_trailing_not_gzip_preserves_warning():
    """Test negativo: trailing data real que NO es GZIP. DE64 con un MAC normal
    (A1B23C44A1B23C44) seguido de bytes arbitrarios no debe detectarse como
    payload propietario y debe conservar la advertencia TRAILING_DATA."""
    from core.validation import SEVERITY_WARNING, validate_result
    frame = _frame_de64("A1B23C44A1B23C44", "DEADBEEF00")
    r = parse_message(frame, ParseOptions(numeric_encoding="bcd"))
    assert r.trailing_payload is None
    assert any("sin analizar" in w for w in r.warnings)
    vr = validate_result(r)
    assert "TRAILING_DATA" in [
        f.code for f in vr.findings if f.severity == SEVERITY_WARNING
    ]
    f = next(x for x in vr.findings if x.code == "TRAILING_DATA")
    assert "5 bytes" in f.value


def test_promerica_de64_possible_gzip_keeps_warning():
    """Magic GZIP presente y prefijo de longitud, pero la longitud declarada no
    coincide con la disponible: la detección queda 'possible' y se conserva la
    advertencia de datos sin analizar."""
    from core.validation import SEVERITY_WARNING, validate_result
    frame = _frame_de64("02501F8B08000000", "AABBCCDD")
    r = parse_message(frame, ParseOptions(numeric_encoding="bcd"))
    tp = r.trailing_payload
    assert tp is not None
    assert tp.status == "possible"
    assert tp.kind == "possible_gzip"
    assert tp.declared_length == 592
    assert tp.available_length == 10
    assert tp.decompressed_length is None
    assert any("sin analizar" in w for w in r.warnings)
    assert any("Posible payload propietario" in w for w in r.warnings)
    vr = validate_result(r)
    assert "TRAILING_DATA" in [
        f.code for f in vr.findings if f.severity == SEVERITY_WARNING
    ]


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


def test_promerica_0200_completa_cadena():
    """Cadena completa de la trama 0200 real: pick_profile → TPDU → MTI →
    Bitmap → DE3...DE55 → TLV DE55 → DE60...DE127. 446/446 bytes, 0 errores
    y 0 warnings."""
    assert api.pick_profile(FRAME_PROMERICA_0200) == PROMERICA_PROFILE
    msg = api.decode(FRAME_PROMERICA_0200, profile_name=PROMERICA_PROFILE)
    r = msg.legacy
    assert r.tpdu.hex == "6000018000"
    assert r.mti.hex == "0200"
    assert r.bitmap_primary_hex == "b038464120c18210"
    assert r.bitmap_secondary_hex == "0000000000014302"
    assert r.consumed_hex == r.declared_hex
    assert r.declared_hex // 2 == 446
    assert not r.errors
    assert not r.warnings
    fields = {f.number: f for f in r.fields}
    assert [f.number for f in r.fields] == [
        3, 4, 11, 12, 13, 18, 22, 23, 26, 32, 35, 41, 42, 48, 49, 55,
        60, 112, 114, 119, 120, 127,
    ]
    expected = {
        3: "003000", 4: "000000000336", 11: "000066", 12: "120600",
        13: "0817", 18: "5541", 22: "052", 23: "000", 26: "06",
        32: "179130", 35: "6262893000001204=24092011000079600000",
        41: "20110341", 42: "000000871703   ", 48: "9506ECUCTA", 49: "840",
        60: "03M24020006000300000000000012D2600000000003002180000000000"
            "U2302000600030000000000001",
        112: "005006040300", 114: "000041",
        119: "000000000300000000000000", 120: "11000000000036",
        127: "F0002F01102.3.5.2407F02109220094360",
    }
    for num, val in expected.items():
        assert fields[num].value == val, f"DE{num}"
    f55 = fields[55]
    assert f55.length_digits == 149
    assert not f55.has_error
    assert [getattr(n, "tag") for n in r.emv] == [
        "9F26", "9F27", "9F10", "9F37", "9F36", "95", "9A", "9C", "9F02",
        "5F2A", "82", "9F1A", "9F03", "9F33", "9F34", "9F35", "9F1E", "84",
        "9F09", "9F41", "5F34",
    ]


def _walk_nodes(nodes):
    """Recorre nodos (dicts) en profundidad."""
    for n in nodes:
        yield n
        yield from _walk_nodes(n.get("children", []))


def test_decode_0200_de55_21_tlv_autosuficiente():
    """api.decode() entrega el árbol EMV completo y autosuficiente: 21 TLV
    con Tag + Length + Value HEX + Value ASCII + Name EN/ES + Interpretación
    + Constructed + Children, sin depender de enrich_result_emv (UI/exporter).
    El árbol Message y result.emv contienen la misma información."""
    msg = api.decode(FRAME_PROMERICA_0200, profile_name=PROMERICA_PROFILE)
    r = msg.legacy
    assert len(r.emv) == 21
    for n in r.emv:
        assert n.tag
        assert n.length == len(n.value_hex) // 2 > 0
        assert n.value_hex
        assert isinstance(n.value_ascii, str)
        assert n.name
        assert n.name_es
        assert isinstance(n.constructed, bool)
        assert isinstance(n.interpretation, str)
    by_tag = {n.tag: n for n in r.emv}
    assert by_tag["9F26"].name == "Application Cryptogram"
    assert by_tag["9F26"].name_es == "Criptograma de la aplicación"
    assert by_tag["9F26"].interpretation == "Criptograma de la aplicación"
    assert by_tag["5F2A"].interpretation == "840 → USD"
    assert by_tag["9F02"].interpretation == "3.36 USD"
    assert by_tag["9F10"].value_hex == "07010103A0A002010A010000000000EE04E040"
    assert by_tag["9F10"].children == []

    tree = {n.get("tag"): n for n in _walk_nodes([msg.as_dict()["root"]])
            if n.get("kind") == "tlv"}
    assert len(tree) == 21
    for n in r.emv:
        t = tree[n.tag]
        assert t["value"] == n.value_hex
        assert t["name_es"] == n.name_es
        assert t["interpretation"] == n.interpretation
        assert t["tlv_length"] == n.length
        assert t["constructed"] == n.constructed
        assert t["note"] == n.note
    assert tree["9F26"]["name_es"] == "Criptograma de la aplicación"
    assert tree["9F26"]["tlv_length"] == 8
    assert tree["5F2A"]["interpretation"] == "840 → USD"
    assert tree["9F02"]["interpretation"] == "3.36 USD"
