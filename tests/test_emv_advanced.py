# -*- coding: utf-8 -*-
"""Tests del análisis avanzado del DE55 / EMV.

Cubre la interpretación de tags (montos, moneda, fecha), la consistencia
ISO8583 ↔ EMV (monto DE4 vs 9F02 y fecha DE13 vs 9A) y la exportación
del reporte (TXT/JSON) con interpretación.

Principios: no inventar conversiones sin moneda, no generar validaciones
cuando el tag correspondiente no existe, y omitir la consistencia cuando
la estructura TLV del DE55 es inválida.
"""

import json

from core.emv import enrich_result_emv
from core.exporter import result_to_json, result_to_text
from core.parser import ParseOptions, parse_message
from core.transaction_summary import TransactionSummary
from core.validation import (
    SEVERITY_ERROR,
    SEVERITY_INFO,
    SEVERITY_WARNING,
    validate_result,
)

# TLV EMV de referencia (idéntico a la trama QA del usuario)
EMV_CARGA = (
    "9F26081AD085579EF40B05"
    "9F270180"
    "9F101307010103A0A002010A010000000000EE04E040"
    "9F370454EE45A2"
    "9F3602040F"
    "9505008000E000"
    "9A03230817"
    "9C0100"
    "9F0206000000000336"
    "5F2A020840"
    "82027C00"
    "9F1A020218"
)

EMV_MONTO = "9F0206000000000336"   # Amount, Authorised = 3.36 (con 2 decimales)
EMV_MONEDA = "5F2A020840"          # Transaction Currency Code = USD
EMV_FECHA = "9A03230817"           # Transaction Date = 23/08/17
EMV_TIPO = "9C0100"                # Transaction Type = Bienes y servicios
EMV_CRIPTO = "9F2608123456789ABCDEF0"
EMV_CID = "9F270180"               # ARQC
EMV_ATC = "9F3602040F"             # ATC decimal 1039


def _bcd(code):
    return (code + "F") if len(code) % 2 else code


def _make_frame(*, de4="000000000336", de13="0817", de49="840",
                emv_hex=None):
    """Construye una trama BCD con DE4/DE13/DE49 y DE55 opcionales."""
    bits = {3}
    body = "003000"
    if de4:
        bits.add(4)
        body += de4
    bits.add(11)
    body += "000066"
    if de13:
        bits.add(13)
        body += de13
    if de49 is not None:
        bits.add(49)
        body += _bcd(de49)
    if emv_hex:
        bits.add(55)
        body += "%04d" % (len(emv_hex) // 2) + emv_hex
    bytes_ = [0] * 8
    for b in bits:
        byte, bit = divmod(b - 1, 8)
        bytes_[byte] |= 1 << (7 - bit)
    bitmap = "".join("%02X" % x for x in bytes_)
    frame = "6000018000" + "0200" + bitmap + body
    return "%04X" % (len(frame) // 2) + frame


def _opts():
    return ParseOptions(numeric_encoding="bcd", llvar_prefix_bytes=2,
                        lllvar_prefix_bytes=2, lllvar_4digit_bcd=True)


def _parse(emv_hex, **kw):
    return parse_message(_make_frame(emv_hex=emv_hex, **kw), _opts())


def _enrich(r):
    src = TransactionSummary(r).source
    return enrich_result_emv(r,
                             src.currency if src else None,
                             src.minor_units if src else None)


def _codes(result, severity=None):
    out = [f.code for f in result.findings]
    if severity:
        out = [f.code for f in result.findings if f.severity == severity]
    return out


def _node(r, tag):
    return next(n for n in r.emv if n.tag == tag)


# ---------------------------------------------------------------------------
# 1. Interpretación del tag 9F02 (Amount, Authorised)
# ---------------------------------------------------------------------------

def test_9f02_interpretation_con_moneda():
    """9F02 con moneda detectada: el monto se formatea con minor units."""
    r = _parse(EMV_MONTO + EMV_MONEDA)          # USD (2 decimales)
    _enrich(r)
    assert _node(r, "9F02").interpretation == "3.36 USD"


def test_9f02_interpretation_sin_moneda_no_inventa():
    """Sin moneda ISO 4217 no hay minor units: no se convierte el monto."""
    r = _parse(EMV_MONTO, de49=None)
    _enrich(r)
    assert _node(r, "9F02").interpretation == ""


def test_9f02_sin_currency_code_pero_minor_units():
    """Solo con minor units se formatea el monto sin inventar la moneda."""
    r = _parse(EMV_MONTO, de49=None)
    enrich_result_emv(r, None, 2)
    assert _node(r, "9F02").interpretation == "3.36"


# ---------------------------------------------------------------------------
# 2. Interpretación del tag 5F2A (Transaction Currency Code)
# ---------------------------------------------------------------------------

def test_5f2a_interpretation():
    """5F2A muestra código ISO y nombre: '840 → USD'."""
    r = _parse(EMV_MONEDA)
    _enrich(r)
    node = _node(r, "5F2A")
    assert node.interpretation == "840 → USD"
    assert "USD" in node.note


def test_5f2a_moneda_desconocida_no_inventa():
    """Código no catalogado: no se inventa una moneda."""
    r = _parse("5F2A020353")
    _enrich(r)
    assert _node(r, "5F2A").interpretation == ""


def test_5f2a_pen_peru():
    r = _parse("5F2A020604")
    _enrich(r)
    assert _node(r, "5F2A").interpretation == "604 → PEN"


# ---------------------------------------------------------------------------
# 3. Interpretación del tag 9A (Transaction Date)
# ---------------------------------------------------------------------------

def test_9a_interpretation():
    r = _parse(EMV_FECHA)
    _enrich(r)
    node = _node(r, "9A")
    assert node.interpretation == "Fecha 17/08/23"
    assert "Fecha" in node.note


# ---------------------------------------------------------------------------
# 4. Consistencia de MONTO: DE4 vs 9F02
# ---------------------------------------------------------------------------

def test_amount_match():
    """DE4 = 336 y 9F02 = 000000000336: coinciden."""
    r = validate_result(parse_message(
        _make_frame(de4="000000000336", emv_hex=EMV_MONTO), _opts()))
    assert "AMOUNT_MATCH" in _codes(r, SEVERITY_INFO)
    assert "AMOUNT_MISMATCH" not in _codes(r)
    f = next(x for x in r.findings if x.code == "AMOUNT_MATCH")
    assert "3.36" in f.message


def test_amount_mismatch():
    """DE4 = 500 y 9F02 = 336: no coinciden (error)."""
    r = validate_result(parse_message(
        _make_frame(de4="000000000500", emv_hex=EMV_MONTO), _opts()))
    assert "AMOUNT_MISMATCH" in _codes(r, SEVERITY_ERROR)
    assert "AMOUNT_MATCH" not in _codes(r)
    f = next(x for x in r.findings if x.code == "AMOUNT_MISMATCH")
    assert "5.00" in f.message and "3.36" in f.message


def test_amount_sin_9f02_no_genera_validacion():
    """Sin tag 9F02 no se genera la validación de monto."""
    r = validate_result(parse_message(
        _make_frame(emv_hex=EMV_MONEDA), _opts()))
    assert "AMOUNT_MATCH" not in _codes(r)
    assert "AMOUNT_MISMATCH" not in _codes(r)


def test_amount_de4_ausente_no_genera_validacion():
    r = validate_result(parse_message(
        _make_frame(de4=None, emv_hex=EMV_MONTO), _opts()))
    assert "AMOUNT_MATCH" not in _codes(r)
    assert "AMOUNT_MISMATCH" not in _codes(r)


# ---------------------------------------------------------------------------
# 5. Consistencia de FECHA: DE13 vs 9A
# ---------------------------------------------------------------------------

def test_date_match():
    """DE13 = 0817 (17/08) y 9A = 230817 (17/08/23): coinciden."""
    r = validate_result(parse_message(
        _make_frame(de13="0817", emv_hex=EMV_FECHA), _opts()))
    assert "DATE_MATCH" in _codes(r, SEVERITY_INFO)
    assert "DATE_MISMATCH" not in _codes(r)
    f = next(x for x in r.findings if x.code == "DATE_MATCH")
    assert "17/08" in f.message


def test_date_mismatch():
    """DE13 = 0817 vs 9A = 230916 (16/09/23): no coinciden (error)."""
    r = validate_result(parse_message(
        _make_frame(de13="0817", emv_hex="9A03230916"), _opts()))
    assert "DATE_MISMATCH" in _codes(r, SEVERITY_ERROR)
    assert "DATE_MATCH" not in _codes(r)
    f = next(x for x in r.findings if x.code == "DATE_MISMATCH")
    assert "16/09" in f.message


def test_date_sin_9a_no_genera_validacion():
    r = validate_result(parse_message(
        _make_frame(de13="0817", emv_hex=EMV_MONEDA), _opts()))
    assert "DATE_MATCH" not in _codes(r)
    assert "DATE_MISMATCH" not in _codes(r)


# ---------------------------------------------------------------------------
# 6. Estructura TLV inválida: se omite la consistencia
# ---------------------------------------------------------------------------

def test_tlv_invalido_no_genera_consistencia():
    r = validate_result(parse_message(
        _make_frame(de4="000000000336", de13="0817", emv_hex="5F2A02"),
        _opts()))
    assert "INVALID_EMV_TLV" in _codes(r, SEVERITY_ERROR)
    assert "EMV_TLV_VALID" not in _codes(r)
    assert "AMOUNT_MATCH" not in _codes(r)
    assert "AMOUNT_MISMATCH" not in _codes(r)
    assert "DATE_MATCH" not in _codes(r)
    assert "DATE_MISMATCH" not in _codes(r)


# ---------------------------------------------------------------------------
# 7. Otros tags interpretados
# ---------------------------------------------------------------------------

def test_9c_transaction_type():
    r = _parse(EMV_TIPO)
    assert _node(r, "9C").note == "Bienes y servicios"


def test_9f27_cryptogram_info():
    r = _parse(EMV_CID)
    assert "ARQC" in _node(r, "9F27").note


def test_9f36_atc():
    r = _parse(EMV_ATC)
    note = _node(r, "9F36").note
    assert "Contador" in note and "1039" in note


def test_9f26_criptograma():
    r = _parse(EMV_CRIPTO)
    assert _node(r, "9F26").note == "Criptograma de la aplicación"


def test_tag_no_reconocido():
    r = _parse("AB0101")
    assert _node(r, "AB").name == "Tag no reconocido"


def test_nodo_as_dict_incluye_interpretacion():
    r = _parse(EMV_MONEDA)
    _enrich(r)
    d = _node(r, "5F2A").as_dict()
    assert d["interpretation"] == "840 → USD"


# ---------------------------------------------------------------------------
# 8. Carga real completa
# ---------------------------------------------------------------------------

def test_carga_emv_completa():
    r = _parse(EMV_CARGA)
    tags = [n.tag for n in r.emv]
    assert len(r.emv) == 12
    assert "9F02" in tags and "5F2A" in tags and "9A" in tags
    assert "9C" in tags and "9F26" in tags and "9F36" in tags
    _enrich(r)
    assert _node(r, "9F02").interpretation == "3.36 USD"
    assert _node(r, "5F2A").interpretation == "840 → USD"


def test_f_emv_refrescado_con_interpretacion():
    """f.emv (DE55) se actualiza con la interpretación tras enriquecer."""
    r = _parse(EMV_MONEDA)
    _enrich(r)
    f55 = next(f for f in r.fields if f.number == 55)
    assert f55.emv[0]["interpretation"] == "840 → USD"


# ---------------------------------------------------------------------------
# 9. Consistencia de MONEDA: DE49 vs 5F2A (comprobación cruzada)
# ---------------------------------------------------------------------------

def test_currency_consistency_findings():
    ok = validate_result(parse_message(
        _make_frame(de49="840", emv_hex=EMV_MONEDA), _opts()))
    assert "CURRENCY_MATCH" in _codes(ok, SEVERITY_INFO)
    bad = validate_result(parse_message(
        _make_frame(de49="840", emv_hex="5F2A020170"), _opts()))
    assert "CURRENCY_MISMATCH" in _codes(bad, SEVERITY_WARNING)


# ---------------------------------------------------------------------------
# 10. Reporte TXT / JSON con interpretación
# ---------------------------------------------------------------------------

def test_reporte_txt_con_interpretacion_y_consistencia():
    r = parse_message(
        _make_frame(de4="000000000500", de13="0817",
                    emv_hex=EMV_MONTO + EMV_MONEDA + EMV_FECHA + EMV_TIPO),
        _opts())
    text = result_to_text(r)
    assert "Campo 55 / EMV" in text
    assert "Interpretación: 840 → USD" in text
    assert "Interpretación: 3.36 USD" in text
    assert "Consistencia ISO8583 ↔ EMV" in text
    assert "[AMOUNT_MISMATCH]" in text
    assert "[DATE_MATCH]" in text


def test_reporte_json_con_interpretacion():
    r = parse_message(
        _make_frame(emv_hex=EMV_MONTO + EMV_MONEDA), _opts())
    data = json.loads(result_to_json(r))
    emv_nodes = {n["tag"]: n for n in data["emv"]}
    assert emv_nodes["5F2A"]["interpretation"] == "840 → USD"
    assert emv_nodes["9F02"]["interpretation"] == "3.36 USD"
