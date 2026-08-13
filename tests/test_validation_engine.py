# -*- coding: utf-8 -*-
"""Tests del Motor de Validación y Detección de Errores ISO 8583.

Cubre las 20 reglas determinísticas mínimas solicitadas:
  1. Longitud correcta.          11. Hora inválida.
  2. Longitud incorrecta.        12. Fecha válida.
  3. HEX inválido.               13. Fecha inválida.
  4. Bitmap correcto.            14. Moneda válida.
  5. Campo ausente.              15. Moneda inexistente.
  6. LLVAR correcto.             16. DE49 y 5F2A coincidentes.
  7. LLVAR incorrecto.           17. DE49 y 5F2A diferentes.
  8. Campo numérico válido.      18. EMV TLV correcto.
  9. Campo numérico inválido.    19. EMV TLV truncado.
  10. Hora válida.               20. Bytes sobrantes.
"""

import core.api as api
from core.parser import ParseOptions, parse_message
from core.validation import (
    SEVERITY_ERROR,
    SEVERITY_INFO,
    SEVERITY_WARNING,
    validate,
    validate_frame,
    validate_result,
)

# Trama de referencia del usuario (truncada, con EMV 5F2A=840)
FRAME_USUARIO = (
    "01be60000180000200b038464120c182100000000000014302003000000000000336"
    "00006612060008175541005200000606179130376262893000001204d240920110000"
    "79600000f323031313033343130303030303038373137303320202000103935303645"
    "4355435441084001499f26081ad085579ef40b059f2701809f101307010103a0a00201"
    "0a010000000000ee04e0409f370454ee45a29f3602040f9505008000e0009a0323081"
    "79c01009f02060000000003365f2a02084082027c009f1a020218"
)


def _bcd(code):
    return (code + "F") if len(code) % 2 else code


def _make_frame(*, de4="000000000336", de12="120600", de13="0817",
                de49=None, de51=None, emv_hex=None, de39=None,
                length_delta=0, trailing="", de3="003000"):
    """Construye una trama BCD configurable. length_delta altera la longitud
    declarada; trailing agrega bytes sobrantes al final."""
    bits = {3}
    body = de3
    if de4:
        bits.add(4)
        body += de4
    bits.add(11)
    body += "000066"
    if de12:
        bits.add(12)
        body += de12
    if de13:
        bits.add(13)
        body += de13
    if de49 is not None:
        bits.add(49)
        body += _bcd(de49)
    if de51 is not None:
        bits.add(51)
        body += _bcd(de51)
    if de39 is not None:
        bits.add(39)
        body += _bcd(de39)
    if emv_hex is not None:
        bits.add(55)
        n = len(emv_hex) // 2
        body += "%04d" % n + emv_hex

    bytes_ = [0] * 8
    for b in bits:
        byte, bit = divmod(b - 1, 8)
        bytes_[byte] |= 1 << (7 - bit)
    bitmap = "".join("%02X" % x for x in bytes_)
    frame = "6000018000" + "0200" + bitmap + body + trailing
    length = len(frame) // 2 + length_delta
    return "%04X" % length + frame


def _emv_opts():
    return ParseOptions(numeric_encoding="bcd", llvar_prefix_bytes=2,
                        lllvar_prefix_bytes=2, lllvar_4digit_bcd=True)


def _parse(frame, opts=None):
    return parse_message(frame, opts or ParseOptions(numeric_encoding="bcd"))


def _codes(result, severity=None):
    out = [f.code for f in result.findings]
    if severity:
        out = [f.code for f in result.findings if f.severity == severity]
    return out


# ---------------------------------------------------------------------------
# 1. Longitud correcta / 2. Longitud incorrecta
# ---------------------------------------------------------------------------

def test_frame_length_ok():
    r = validate_result(_parse(_make_frame(de49="840")))
    assert "FRAME_LENGTH_MATCH" in _codes(r, SEVERITY_INFO)
    assert r.status == "valid"


def test_frame_length_mismatch():
    r = validate_result(_parse(_make_frame(de49="840", length_delta=2)))
    assert "FRAME_LENGTH_MISMATCH" in _codes(r, SEVERITY_ERROR)
    assert r.has_errors


# ---------------------------------------------------------------------------
# 3. HEX inválido
# ---------------------------------------------------------------------------

def test_hex_odd_length():
    r = validate_frame("ABC")
    assert "HEX_INVALID_LENGTH" in _codes(r, SEVERITY_ERROR)


def test_hex_invalid_char():
    r = validate_frame("0064ls00")
    assert "HEX_INVALID_CHAR" in _codes(r, SEVERITY_ERROR)


def test_hex_empty():
    r = validate_frame("")
    assert "FRAME_EMPTY" in _codes(r, SEVERITY_ERROR)


# ---------------------------------------------------------------------------
# 4. Bitmap correcto / 5. Campo ausente
# ---------------------------------------------------------------------------

def test_bitmap_ok():
    r = validate_result(_parse(_make_frame(de49="840")))
    assert "BITMAP_FIELD_MISSING" not in _codes(r)
    assert "BITMAP_INVALID_LENGTH" not in _codes(r)


def test_bitmap_field_missing():
    """Bitmap indica DE2 (LLVAR) con prefijo que supera los datos: el parser
    se detiene en DE2 y los campos posteriores (DE3/DE11) no se reportan como
    errores independientes sino como una única advertencia de parseo."""
    # DE2 LLVAR n: prefijo declara 99 bytes, hay 3
    bitmap = "6004000000000000"  # DE2, DE3, DE11
    body = "99" + "123456" + "003000" + "000066"
    frame = "6000018000" + "0200" + bitmap + body
    frame = "%04X" % (len(frame) // 2) + frame
    r = validate_result(_parse(frame))
    assert "PARSING_STOPPED_AFTER_DE2" in _codes(r, SEVERITY_WARNING)
    # Sin cascada de falsos positivos: los campos tras el corte no son errores.
    assert "BITMAP_FIELD_MISSING" not in _codes(r, SEVERITY_ERROR)
    # El error raíz (DE2 truncado) sí se reporta.
    assert "INVALID_FIELD_LENGTH" in _codes(r, SEVERITY_ERROR)


# ---------------------------------------------------------------------------
# 6. LLVAR correcto / 7. LLVAR incorrecto
# ---------------------------------------------------------------------------

def test_llvar_ok():
    r = validate_result(_parse(_make_frame()))
    assert "INVALID_FIELD_LENGTH" not in _codes(r)


def test_llvar_prefix_too_long():
    """Prefijo LLVAR declara más de lo disponible: INVALID_FIELD_LENGTH."""
    bitmap = "6004000000000000"  # DE2, DE3, DE11
    body = "99" + "123456" + "003000" + "000066"
    frame = "6000018000" + "0200" + bitmap + body
    frame = "%04X" % (len(frame) // 2) + frame
    r = validate_result(_parse(frame))
    assert "INVALID_FIELD_LENGTH" in _codes(r, SEVERITY_ERROR)


# ---------------------------------------------------------------------------
# 8. Campo numérico válido / 9. Campo numérico inválido
# ---------------------------------------------------------------------------

def test_numeric_field_ok():
    r = validate_result(_parse(_make_frame()))
    assert "INVALID_NUMERIC_FIELD" not in _codes(r)


def test_numeric_field_invalid():
    """DE3 numérico con un nibble no decimal (A)."""
    bitmap = "2000000000000000"  # DE3
    body = "93001A"
    frame = "6000018000" + "0200" + bitmap + body
    frame = "%04X" % (len(frame) // 2) + frame
    r = validate_result(_parse(frame))
    assert "INVALID_NUMERIC_FIELD" in _codes(r, SEVERITY_ERROR)
    field = next(f for f in r.findings if f.code == "INVALID_NUMERIC_FIELD")
    assert field.field == "DE3"


# ---------------------------------------------------------------------------
# 10. Hora válida / 11. Hora inválida
# ---------------------------------------------------------------------------

def test_time_valid():
    r = validate_result(_parse(_make_frame(de12="120600")))
    assert "VALID_TIME" in _codes(r, SEVERITY_INFO)


def test_time_invalid():
    r = validate_result(_parse(_make_frame(de12="256099")))
    assert "INVALID_TIME" in _codes(r, SEVERITY_ERROR)


# ---------------------------------------------------------------------------
# 12. Fecha válida / 13. Fecha inválida
# ---------------------------------------------------------------------------

def test_date_valid():
    r = validate_result(_parse(_make_frame(de13="0817")))
    assert "VALID_DATE" in _codes(r, SEVERITY_INFO)


def test_date_invalid():
    r = validate_result(_parse(_make_frame(de13="1317")))
    assert "INVALID_DATE" in _codes(r, SEVERITY_ERROR)


# ---------------------------------------------------------------------------
# 14. Moneda válida / 15. Moneda inexistente
# ---------------------------------------------------------------------------

def test_currency_valid():
    r = validate_result(_parse(_make_frame(de49="840")))
    assert "VALID_CURRENCY" in _codes(r, SEVERITY_INFO)
    f = next(x for x in r.findings if x.code == "VALID_CURRENCY")
    assert "840" in f.value


def test_currency_unknown():
    r = validate_result(_parse(_make_frame(de49="999")))
    assert "AMOUNT_CURRENCY_UNKNOWN" in _codes(r, SEVERITY_WARNING)


# ---------------------------------------------------------------------------
# 16. DE49 y 5F2A coincidentes / 17. DE49 y 5F2A diferentes
# ---------------------------------------------------------------------------

def test_currency_de49_emv_match():
    r = validate_result(_parse(_make_frame(de49="840", emv_hex="5F2A020840"),
                               _emv_opts()))
    assert "CURRENCY_MATCH" in _codes(r, SEVERITY_INFO)
    assert "CURRENCY_MISMATCH" not in _codes(r)


def test_currency_de49_emv_mismatch():
    r = validate_result(_parse(_make_frame(de49="840", emv_hex="5F2A020170"),
                               _emv_opts()))
    assert "CURRENCY_MISMATCH" in _codes(r, SEVERITY_WARNING)
    f = next(x for x in r.findings if x.code == "CURRENCY_MISMATCH")
    assert "840" in f.value and "170" in f.value


# ---------------------------------------------------------------------------
# 18. EMV TLV correcto / 19. EMV TLV truncado
# ---------------------------------------------------------------------------

def test_emv_tlv_valid():
    r = validate_result(_parse(_make_frame(emv_hex="5F2A0208409F36020042"),
                               _emv_opts()))
    assert "EMV_TLV_VALID" in _codes(r, SEVERITY_INFO)
    assert "INVALID_EMV_TLV" not in _codes(r)


def test_emv_tlv_truncated():
    """5F2A declara 2 bytes pero no hay valor disponible."""
    r = validate_result(_parse(_make_frame(emv_hex="5F2A02"), _emv_opts()))
    assert "INVALID_EMV_TLV" in _codes(r, SEVERITY_ERROR)
    f = next(x for x in r.findings if x.code == "INVALID_EMV_TLV")
    assert "5F2A" in f.value


# ---------------------------------------------------------------------------
# 20. Bytes sobrantes
# ---------------------------------------------------------------------------

def test_trailing_data():
    r = validate_result(_parse(_make_frame(de49="840", trailing="A1B2C3")))
    assert "TRAILING_DATA" in _codes(r, SEVERITY_WARNING)
    f = next(x for x in r.findings if x.code == "TRAILING_DATA")
    assert "3 bytes" in f.value


# ---------------------------------------------------------------------------
# DE39 (código de respuesta) e integración
# ---------------------------------------------------------------------------

def test_response_code_documented():
    # DE39 es un campo fijo de 3 dígitos; "000" corresponde al código "00".
    r = validate_result(_parse(_make_frame(de39="000")))
    assert "RESPONSE_CODE_DOCUMENTED" in _codes(r, SEVERITY_INFO)


def test_response_code_unknown_is_info():
    r = validate_result(_parse(_make_frame(de39="159")))
    assert "RESPONSE_CODE_UNKNOWN" in _codes(r, SEVERITY_INFO)
    assert "RESPONSE_CODE_UNKNOWN" not in _codes(r, SEVERITY_ERROR)


def test_validate_accepts_message_and_raw():
    frame = _make_frame(de49="840")
    assert validate(frame).status == "valid"
    msg = api.decode(frame)
    assert validate(msg).status == "valid"
    assert validate(msg.legacy).status == "valid"


def test_estado_general():
    ok = validate(_make_frame(de49="840"))
    assert ok.status == "valid"
    assert ok.status_label == "✓ TRAMA VÁLIDA"

    warn = validate(_make_frame(de49="999"))
    assert warn.status == "warnings"
    assert warn.status_label == "⚠ TRAMA CON ADVERTENCIAS"

    err = validate(_make_frame(de49="840", length_delta=2))
    assert err.status == "errors"
    assert err.status_label == "❌ TRAMA CON ERRORES"


def test_usuario_frame_valid():
    # La trama del usuario está truncada (declara 446 bytes, tiene 197):
    # el motor debe detectar los errores reales y no inventar otros.
    r = validate(FRAME_USUARIO)
    assert r.has_errors
    codes = _codes(r)
    assert "FRAME_LENGTH_MISMATCH" in codes
    assert "INVALID_FIELD_LENGTH" in codes
    # No debe reportar errores fabricados (p. ej. de moneda o fecha).
    assert "INVALID_DATE" not in codes
    assert "CURRENCY_MISMATCH" not in codes


def test_usuario_frame_full_valid():
    # Una trama completa y bien formada no debe generar falsos positivos.
    r = validate(_make_frame(de49="840", emv_hex="5F2A020840"), _emv_opts())
    assert not r.has_errors
    codes = _codes(r)
    assert "FRAME_LENGTH_MATCH" in codes


def test_formato_reporte():
    r = validate(_make_frame(de49="840"))
    lines = "\n".join(r.format_lines())
    assert "--- Validación de Trama ---" in lines
    assert "✓ TRAMA VÁLIDA" in lines
    assert "[FRAME_LENGTH_MATCH]" in lines
    assert "[VALID_TIME]" in lines


# ---------------------------------------------------------------------------
# Reporte del usuario (trama QA real del historial) y casos derivados
# ---------------------------------------------------------------------------

# Trama completa del reporte: prefijo de longitud 01bd, DE12=256099, DE32
# con prefijo LLVAR de 1 byte que supera el máximo y desincroniza el parseo
# bajo el perfil Promerica (prefijos de 2 bytes).
FRAME_QA = (
    "01bd60000180000200b038464120c18210000000000001430200300000000000"
    "033600006625609908175541005200000606179130376262893000001204d240"
    "92011000079600000f3230313130333431303030303030383731373033202020"
    "001039353036454355435441084001499f26081ad085579ef40b059f2701809f"
    "101307010103a0a002010a010000000000ee04e0409f370454ee45a29f360204"
    "0f9505008000e0009a032308179c01009f02060000000003365f2a0201708202"
    "7c009f1a0202189f03060000000000009f3303e0f8c89f34031e03009f350121"
    "9f1e0832303039343336308408a0000003330101029f090200209f4104000000"
    "665f340100008430334d32343032303030363030303330303030303030303030"
    "3030313244323630303030303030303030333030323138303030303030303030"
    "3055323330323030303630303033303030303030303030303030310012303035"
    "3030363034303330300006303030303431002430303030303030303033303030"
    "3030303030303030303030001431313030303030303030303336003546303030"
    "30324630313130322e332e352e32343037463032313039323230303934333630"
)


def test_padding_nibble_stripped():
    """Los campos numéricos BCD de longitud impar llevan un nibble de relleno
    que no forma parte del valor: DE22/DE23/DE49 no deben reportar longitud
    incorrecta ni '4 dígitos en campo de 3'."""
    result = parse_message(FRAME_QA, ParseOptions(numeric_encoding="bcd"))
    values = {f.number: f.value for f in result.fields}
    assert values[22] == "005"
    assert values[23] == "000"
    assert values[49] == "353"
    r = validate_result(result)
    assert "INVALID_FIELD_LENGTH" not in [f.code for f in r.findings
                                          if f.field in ("DE22", "DE23", "DE49")]


def test_parse_stop_single_warning_no_cascade():
    """DE32 con longitud imposible: se reporta el error raíz y una única
    advertencia PARSING_STOPPED, sin cascada de errores por campos posteriores."""
    opts = ParseOptions(numeric_encoding="bcd", llvar_prefix_bytes=2,
                        lllvar_prefix_bytes=2, lllvar_4digit_bcd=True)
    r = validate_result(parse_message(FRAME_QA, opts))
    codes = _codes(r)
    # Error raíz: DE32 no pudo decodificarse.
    assert "INVALID_FIELD_LENGTH" in codes
    root = next(f for f in r.errors if f.field == "DE32")
    assert "incomplet" in root.message
    # Punto de desincronización marcado como advertencia única.
    assert "PARSING_STOPPED_AFTER_DE32" in _codes(r, SEVERITY_WARNING)
    # Sin cascada de falsos positivos.
    assert "BITMAP_FIELD_MISSING" not in codes
    assert not any(f.field not in ("DE32", "FRAME") and f.severity == SEVERITY_ERROR
                   and f.code != "INVALID_TIME" for f in r.findings)


def test_findings_have_stage_and_derived_from():
    """Los hallazgos distinguen etapa de parseo vs validación y marcan los
    derivados del error raíz."""
    opts = ParseOptions(numeric_encoding="bcd", llvar_prefix_bytes=2,
                        lllvar_prefix_bytes=2, lllvar_4digit_bcd=True)
    r = validate_result(parse_message(FRAME_QA, opts))
    stop = next(f for f in r.findings
                if f.code == "PARSING_STOPPED_AFTER_DE32")
    assert stop.stage == "parse"
    assert stop.derived_from == "DE32"
    root = next(f for f in r.errors if f.field == "DE32")
    assert root.stage == "parse"
    assert root.derived_from is None
    time = next(f for f in r.errors if f.code == "INVALID_TIME")
    assert time.stage == "validation"


def test_report_status_es_fuente_unica_de_verdad():
    """El estado general corresponde exactamente a la lista de errores."""
    r = validate(FRAME_QA)
    assert r.status == "errors"
    assert (r.status == "errors") == bool(r.errors)
    assert (r.status == "warnings") == (bool(r.warnings) and not r.errors)
    assert (r.status == "valid") == (not r.errors and not r.warnings)


def test_exporter_errores_consistentes_con_estado():
    """El reporte de texto no puede mostrar 'Errores: Ninguno' cuando el
    estado general es 'TRAMA CON ERRORES'."""
    from core.exporter import result_to_text
    result = parse_message(FRAME_QA, ParseOptions(numeric_encoding="bcd"))
    text = result_to_text(result)
    assert "❌ TRAMA CON ERRORES" in text
    assert "[FRAME_LENGTH_MISMATCH]" in text
    assert "[INVALID_TIME]" in text
    # La sección de errores ya no dice "Ninguno" con el estado en errores.
    assert "Errores: Ninguno" not in text
