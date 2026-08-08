# -*- coding: utf-8 -*-
"""Tests del detector de moneda ISO 8583 (CurrencyDetector).

Cubre DE49, DE51, EMV 5F2A (DE55 parseado y trama truncada), sin falsos
positivos y los distintos formatos de salida.
"""

import core.api as api
from core.currency import (
    CurrencyDetector,
    CurrencyReport,
    CurrencySource,
    detect_currency,
    detector,
)
from core.exporter import result_to_text
from core.parser import ParseOptions, parse_message

# Trama de referencia del usuario: está truncada (199 bytes vs 446 declarados),
# por lo que el parser no alinea DE55; contiene el TLV 5F2A020840.
FRAME_TRUNCATED_EMV = (
    "01be60000180000200b038464120c182100000000000014302003000000000000336"
    "00006612060008175541005200000606179130376262893000001204d240920110000"
    "79600000f323031313033343130303030303038373137303320202000103935303645"
    "4355435441084001499f26081ad085579ef40b059f2701809f101307010103a0a00201"
    "0a010000000000ee04e0409f370454ee45a29f3602040f9505008000e0009a0323081"
    "79c01009f02060000000003365f2a02084082027c009f1a020218"
)


def _bcd(code):
    return (code + "F") if len(code) % 2 else code


def _de49_frame(code):
    return "0011" + "6000018000" + "0200" + "0000000000008000" + _bcd(code)


def _de49_de51_frame(c49, c51):
    return "0013" + "6000018000" + "0200" + "000000000000A000" + _bcd(c49) + _bcd(c51)


def _de49_emv_frame(c49, emv_hex):
    n = len(emv_hex) // 2
    prefix = "%04d" % n
    return "0018" + "6000018000" + "0200" + "0000000000008200" + _bcd(c49) + prefix + emv_hex


def _emv_opts():
    return ParseOptions(numeric_encoding="bcd", llvar_prefix_bytes=2,
                        lllvar_prefix_bytes=2, lllvar_4digit_bcd=True)


def test_get_iso4217_name():
    d = CurrencyDetector()
    assert d.getISO4217Name("840") == ("USD", "Dólar estadounidense")
    assert d.getISO4217Name("170") == ("COP", "Peso colombiano")
    assert d.getISO4217Name("999") is None


def test_detect_de49_primary():
    r = parse_message(_de49_frame("840"), ParseOptions(numeric_encoding="bcd"))
    rep = detect_currency(r)
    assert rep.primary is not None
    assert rep.primary.source == "DE49"
    assert rep.primary.code == "840"
    assert rep.primary.currency == "USD"
    assert rep.primary.name == "Dólar estadounidense"
    assert rep.emv is None


def test_detect_de51_secondary():
    r = parse_message(_de49_de51_frame("840", "170"), ParseOptions(numeric_encoding="bcd"))
    rep = detect_currency(r)
    assert rep.primary.code == "840"
    assert rep.secondary is not None
    assert rep.secondary.source == "DE51"
    assert rep.secondary.code == "170"
    assert rep.secondary.currency == "COP"


def test_detect_emv_from_truncated_frame():
    """Trama truncada: DE55 no alineado, el detector localiza el TLV 5F2A."""
    r = api.decode(FRAME_TRUNCATED_EMV).legacy
    rep = detect_currency(r)
    assert rep.emv is not None
    assert rep.emv.source == "DE55 Tag 5F2A"
    assert rep.emv.code == "840"
    assert rep.emv.currency == "USD"


def test_detect_emv_from_parsed_de55():
    frame = _de49_emv_frame("840", "5F2A020840")
    r = parse_message(frame, _emv_opts())
    rep = detect_currency(r)
    assert rep.primary.code == "840"
    assert rep.emv is not None
    assert rep.emv.code == "840"
    assert not rep.mismatch


def test_emv_mismatch_detected():
    frame = _de49_emv_frame("840", "5F2A020170")
    r = parse_message(frame, _emv_opts())
    rep = detect_currency(r)
    assert rep.primary.code == "840"
    assert rep.emv.code == "170"
    assert rep.mismatch


def test_no_false_positive_from_invalid_de49():
    """DE49 con 4 dígitos no es un código ISO válido: no se interpreta."""
    r = api.decode(FRAME_TRUNCATED_EMV).legacy
    rep = detect_currency(r)
    assert rep.primary is None


def test_format_no_detected():
    lines = detector().formatCurrencyResult(CurrencyReport())
    assert "No detectada" in lines


def test_format_emv_only():
    rep = CurrencyReport(emv=CurrencySource("DE55 Tag 5F2A", "840", "USD",
                                            "Dólar estadounidense"))
    lines = detector().formatCurrencyResult(rep)
    joined = "\n".join(lines)
    assert "Moneda detectada desde EMV" in joined
    assert "DE55 Tag 5F2A" in joined
    assert "840" in joined and "USD" in joined


def test_format_match():
    rep = CurrencyReport(
        primary=CurrencySource("DE49", "840", "USD", "Dólar estadounidense"),
        emv=CurrencySource("DE55 Tag 5F2A", "840", "USD", "Dólar estadounidense"),
    )
    joined = "\n".join(detector().formatCurrencyResult(rep))
    assert "Coincide con DE49" in joined


def test_format_mismatch():
    rep = CurrencyReport(
        primary=CurrencySource("DE49", "840", "USD", "Dólar estadounidense"),
        emv=CurrencySource("DE55 Tag 5F2A", "170", "COP", "Peso colombiano"),
    )
    joined = "\n".join(detector().formatCurrencyResult(rep))
    assert "Diferencia de moneda detectada" in joined
    assert "840 USD" in joined
    assert "170 COP" in joined


def test_exporter_has_currency_section():
    r = parse_message(_de49_frame("840"), ParseOptions(numeric_encoding="bcd"))
    txt = result_to_text(r)
    assert "--- Moneda de Transacción ---" in txt
    assert "Código ISO:" in txt
    assert "840" in txt
    assert "USD" in txt


def test_exporter_json_has_currency():
    import json as _json
    from core.exporter import result_to_json

    r = parse_message(_de49_de51_frame("840", "170"), ParseOptions(numeric_encoding="bcd"))
    data = _json.loads(result_to_json(r))
    assert data["currency"]["detected"] is True
    assert data["currency"]["primary"]["code"] == "840"
    assert data["currency"]["primary"]["currency"] == "USD"
    assert data["currency"]["secondary"]["code"] == "170"
    assert data["currency"]["emv"] is None


def test_exporter_json_currency_undetected():
    import json as _json
    from core.exporter import result_to_json

    r = parse_message("000F" + "6000018000" + "0200" + "0000000000008000", ParseOptions(numeric_encoding="bcd"))
    data = _json.loads(result_to_json(r))
    assert data["currency"]["detected"] is False
    assert data["currency"]["primary"] is None
    assert data["currency"]["mismatch"] is False
