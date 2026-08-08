# -*- coding: utf-8 -*-
"""Tests del resumen de transacción (TransactionSummary).

Cubre: monto con minor units (2/0/3 decimales), moneda por DE49/DE51/EMV,
conflictos DE49 vs 5F2A, campos ausentes y valores inválidos (DE12/DE13).
"""

import json

import core.api as api
from core.currency import detect_currency
from core.exporter import result_to_json, result_to_text
from core.parser import ParseOptions, parse_message
from core.transaction_summary import TransactionSummary

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
                de49=None, de51=None, emv_hex=None):
    """Construye una trama BCD con DE3, DE4, DE11, DE12, DE13 y opcionalmente
    DE49, DE51 y DE55. Pasar None (o False) omite el campo del bitmap."""
    bits = {3}
    body = "003000"
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
    if emv_hex is not None:
        bits.add(55)
        n = len(emv_hex) // 2
        body += "%04d" % n + emv_hex

    bytes_ = [0] * 8
    for b in bits:
        byte, bit = divmod(b - 1, 8)
        bytes_[byte] |= 1 << (7 - bit)
    bitmap = "".join("%02X" % x for x in bytes_)
    frame = "6000018000" + "0200" + bitmap + body
    return "%04X" % (len(frame) // 2) + frame


def _emv_opts():
    return ParseOptions(numeric_encoding="bcd", llvar_prefix_bytes=2,
                        lllvar_prefix_bytes=2, lllvar_4digit_bcd=True)


def _summary(frame, opts=None):
    r = parse_message(frame, opts or ParseOptions(numeric_encoding="bcd"))
    return TransactionSummary(r)


# ---------------------------------------------------------------------------
# Monto con minor units según la moneda
# ---------------------------------------------------------------------------

def test_amount_usd():
    s = _summary(_make_frame(de49="840"))
    amt = s.amount()
    assert amt["available"] is True
    assert amt["raw"] == "000000000336"
    assert amt["converted"] == "3.36"
    assert amt["formatted"] == "3.36 USD"


def test_amount_cop():
    s = _summary(_make_frame(de4="000000123456", de49="170"))
    assert s.amount()["formatted"] == "1234.56 COP"
    assert s.amount()["converted"] == "1234.56"


def test_amount_eur():
    s = _summary(_make_frame(de49="978"))
    assert s.amount()["formatted"] == "3.36 EUR"


def test_amount_gbp():
    s = _summary(_make_frame(de49="826"))
    assert s.amount()["formatted"] == "3.36 GBP"


def test_amount_zero_decimals():
    """JPY (392) tiene 0 minor units: el monto no se divide."""
    s = _summary(_make_frame(de49="392"))
    assert s.amount()["formatted"] == "336 JPY"
    assert s.amount()["converted"] == "336"


def test_amount_three_decimals():
    """KWD (414) tiene 3 minor units."""
    s = _summary(_make_frame(de49="414"))
    assert s.amount()["formatted"] == "0.336 KWD"
    assert s.amount()["converted"] == "0.336"


# ---------------------------------------------------------------------------
# Moneda
# ---------------------------------------------------------------------------

def test_currency_from_de49():
    s = _summary(_make_frame(de49="840"))
    cur = s.currency()
    assert cur["detected"] is True
    assert cur["code"] == "840"
    assert cur["currency"] == "USD"
    assert cur["name"] == "Dólar estadounidense"
    assert cur["source"] == "DE49"
    assert cur["minor_units"] == 2


def test_currency_unknown_code():
    """Un código que no existe en el catálogo NO produce moneda ni monto."""
    s = _summary(_make_frame(de49="999"))
    assert s.currency()["detected"] is False
    amt = s.amount()
    assert amt["available"] is False
    assert amt["present"] is True
    assert "moneda ISO 4217" in amt["reason"]


def test_de49_absent_no_currency():
    """Sin DE49/DE51/EMV no hay moneda: el monto no se convierte."""
    s = _summary(_make_frame(de49=None, de51=None))
    assert s.currency()["detected"] is False
    assert s.amount()["available"] is False


def test_de51_fallback():
    """Si DE49 no está, se usa DE51 como fuente."""
    s = _summary(_make_frame(de49=None, de51="170"))
    assert s.currency()["source"] == "DE51"
    assert s.currency()["currency"] == "COP"
    assert s.amount()["formatted"] == "3.36 COP"


def test_emv_fallback():
    """Si DE49 no está, se usa el tag EMV 5F2A."""
    s = _summary(_make_frame(de49=None, emv_hex="5F2A020840"), _emv_opts())
    assert s.currency()["source"] == "DE55 Tag 5F2A"
    assert s.currency()["code"] == "840"
    assert s.amount()["formatted"] == "3.36 USD"


def test_de49_and_emv_match():
    s = _summary(_make_frame(de49="840", emv_hex="5F2A020840"), _emv_opts())
    assert s.currency_report.mismatch is False
    assert s.currency()["mismatch"] is False
    assert s.reliable is True
    txt = "\n".join(s.format_summary())
    assert "Validación EMV:" in txt and "Coincide" in txt


def test_de49_and_emv_mismatch():
    """DE49=840 vs EMV=170: no se elige silenciosamente, se advierte."""
    s = _summary(_make_frame(de49="840", emv_hex="5F2A020170"), _emv_opts())
    assert s.currency_report.mismatch is True
    assert s.currency()["mismatch"] is True
    assert s.reliable is False
    txt = "\n".join(s.format_summary())
    assert "Advertencia de moneda" in txt
    assert "Los códigos de moneda no coinciden" in txt
    assert "840 - USD" in txt and "170 - COP" in txt


# ---------------------------------------------------------------------------
# Campos ausentes / inválidos
# ---------------------------------------------------------------------------

def test_de4_absent():
    s = _summary(_make_frame(de4=False))
    amt = s.amount()
    assert amt["present"] is False
    assert "DE4 no está presente" in amt["reason"]
    txt = "\n".join(s.format_summary())
    assert "No disponible" in txt


def test_de12_invalid():
    """DE12 = 256000: HH fuera de rango -> valor inválido."""
    s = _summary(_make_frame(de12="256000"))
    tm = s.time()
    assert tm["valid"] is False
    assert tm["formatted"] is None
    txt = "\n".join(s.format_summary())
    assert "Valor inválido" in txt


def test_de13_invalid():
    """DE13 = 1317: MM=13 -> valor inválido."""
    s = _summary(_make_frame(de13="1317"))
    dt = s.date()
    assert dt["valid"] is False
    txt = "\n".join(s.format_summary())
    assert "Valor inválido" in txt


# ---------------------------------------------------------------------------
# Hora y fecha válidas
# ---------------------------------------------------------------------------

def test_time_valid():
    s = _summary(_make_frame(de12="120600"))
    tm = s.time()
    assert tm["valid"] is True
    assert tm["formatted"] == "12:06:00"
    assert tm["raw"] == "120600"


def test_date_valid():
    s = _summary(_make_frame(de13="0817"))
    dt = s.date()
    assert dt["valid"] is True
    assert dt["formatted"] == "17/08"
    assert dt["raw"] == "0817"


def test_de12_absent():
    s = _summary(_make_frame(de12=False))
    tm = s.time()
    assert tm["present"] is False
    assert "DE12 no está presente" in tm["reason"]


def test_de13_absent():
    s = _summary(_make_frame(de13=False))
    dt = s.date()
    assert dt["present"] is False
    assert "DE13 no está presente" in dt["reason"]


# ---------------------------------------------------------------------------
# Exportación e integración
# ---------------------------------------------------------------------------

def test_exporter_text_has_summary():
    r = parse_message(_make_frame(de49="840"), ParseOptions(numeric_encoding="bcd"))
    txt = result_to_text(r)
    assert "--- Resumen de Transacción ---" in txt
    assert "Monto de la transacción:" in txt
    assert "3.36 USD" in txt
    assert "Hora de la transacción:" in txt
    assert "12:06:00" in txt
    assert "Fecha de la transacción:" in txt
    assert "17/08" in txt


def test_exporter_json_has_summary():
    r = parse_message(_make_frame(de49="840"), ParseOptions(numeric_encoding="bcd"))
    data = json.loads(result_to_json(r))
    summary = data["summary"]
    assert summary["amount"]["formatted"] == "3.36 USD"
    assert summary["currency"]["code"] == "840"
    assert summary["time"]["formatted"] == "12:06:00"
    assert summary["date"]["formatted"] == "17/08"
    assert summary["reliable"] is True


def test_usuario_frame_expected_output():
    """Trama del usuario: 840/USD, monto 3.36 USD, 12:06:00, 17/08."""
    r = api.decode(FRAME_USUARIO).legacy
    s = TransactionSummary(r)
    assert s.currency()["detected"] is True
    assert s.currency()["code"] == "840"
    amt = s.amount()
    assert amt["available"] is True
    assert amt["formatted"] == "3.36 USD"
    assert s.time()["formatted"] == "12:06:00"
    assert s.date()["valid"] is True
    assert s.date()["formatted"] == "17/08"
