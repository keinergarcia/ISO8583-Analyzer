# -*- coding: utf-8 -*-
"""Reglas determinísticas de validación de Data Elements.

Operan sobre los valores que el parser ya decodificó (ParsedField). Reutiliza
el detector de moneda existente (core.currency) y el resumen de transacción
(core.transaction_summary) para el monto, sin duplicar su lógica.

Reglas incluidas:
- Errores de decodificación reportados por el parser.
- Longitudes de campos (fixed / LLVAR / LLLVAR).
- Campos numéricos (contenido).
- DE12 (hora HHMMSS).
- DE13 (fecha MMDD).
- DE4 (monto, con minor units de la moneda).
- DE49 / EMV 5F2A (comparación de moneda).
- DE39 (código de respuesta, catálogo).
"""

from typing import Callable, Optional

from ..currency import detect_currency
from ..reference import get_reference
from ..transaction_summary import TransactionSummary

Adder = Callable[..., None]


def _find_field(result, number) -> Optional[object]:
    for f in getattr(result, "fields", []) or []:
        if f.number == number:
            return f
    return None


def _declared_units(field) -> str:
    """Unidad de la longitud declarada (dígitos para 'n', bytes si no)."""
    return "dígitos" if field.ftype == "n" else "bytes"


def _days_in_month(mm) -> int:
    if mm == 2:
        return 29  # sin año no puede comprobarse bisiesto
    return {1: 31, 3: 31, 4: 30, 5: 31, 6: 30, 7: 31, 8: 31, 9: 30, 10: 31,
            11: 30, 12: 31}[mm]


# ---------------------------------------------------------------------------
# 6. LONGITUDES DE CAMPOS
# ---------------------------------------------------------------------------

def check_field_lengths(result, add: Adder):
    """Comprueba longitudes de campos fixed y variables según la definición."""
    for f in result.fields:
        if f.has_error:
            continue
        if f.length_type == "fixed":
            expected = f.max_length
            if f.ftype == "n":
                actual = len(f.value or "")
            else:
                actual = len(f.raw_hex or "") // 2
            if actual != expected:
                add("ERROR", "INVALID_FIELD_LENGTH",
                    f"DE{f.number} declara {expected} {_declared_units(f)} "
                    f"pero contiene {actual}.",
                    f"DE{f.number}", value=f.value, rule="FIELD_LENGTH")
        else:  # llvar / lllvar / llllvar
            if f.length_digits > f.max_length:
                add("ERROR", "INVALID_FIELD_LENGTH",
                    f"DE{f.number} declara {f.length_digits} {_declared_units(f)} "
                    f"pero el máximo definido es {f.max_length}.",
                    f"DE{f.number}", value=f.value, rule="FIELD_LENGTH")


# ---------------------------------------------------------------------------
# 6b. Errores de decodificación reportados por el parser
# ---------------------------------------------------------------------------

def check_field_decode_errors(result, add: Adder, stop=None):
    """Convierte errores del parser (campo incompleto/truncado) en hallazgos.

    Son hallazgos de ETAPA DE PARSEO (no de validación): provienen de un
    campo que el parser no pudo decodificar. El campo donde el parser se
    detuvo (`stop`) es el error raíz (no deriva de nada); los demás son
    déficits de definición.
    """
    for f in result.fields:
        if not f.has_error:
            continue
        msg = f.error or "No se pudo decodificar el campo."
        if "incomple" in msg.lower() or "supera" in msg.lower() or "longitud" in msg.lower():
            add("ERROR", "INVALID_FIELD_LENGTH",
                f"DE{f.number}: {msg}", f"DE{f.number}",
                value=f.value or "", rule="FIELD_LENGTH",
                stage="parse")
        else:
            add("ERROR", "FIELD_DECODE_ERROR",
                f"DE{f.number}: {msg}", f"DE{f.number}",
                value=f.value or "", rule="FIELD_DECODE",
                stage="parse")


# ---------------------------------------------------------------------------
# 7. CAMPOS NUMÉRICOS
# ---------------------------------------------------------------------------

def check_numeric_fields(result, add: Adder):
    """Campos definidos como numéricos no deben contener caracteres inválidos."""
    for f in result.fields:
        if f.has_error or f.ftype != "n":
            continue
        value = (f.value or "").strip()
        if value and not value.isdigit():
            add("ERROR", "INVALID_NUMERIC_FIELD",
                f"DE{f.number} contiene caracteres que no corresponden a un "
                f"campo numérico.",
                f"DE{f.number}", value=value, rule="NUMERIC_CONTENT")


# ---------------------------------------------------------------------------
# 8. DE12 — HORA
# ---------------------------------------------------------------------------

def check_time(result, add: Adder):
    """Valida DE12 (HHMMSS). No corrige el valor."""
    f = _find_field(result, 12)
    if f is None or f.has_error:
        return
    raw = (f.value or "").strip()
    if len(raw) != 6 or not raw.isdigit():
        add("ERROR", "INVALID_TIME",
            "DE12 debe tener el formato HHMMSS (6 dígitos).",
            "DE12", value=raw, rule="TIME_FORMAT")
        return
    hh, mm, ss = int(raw[0:2]), int(raw[2:4]), int(raw[4:6])
    if hh > 23 or mm > 59 or ss > 59:
        add("ERROR", "INVALID_TIME",
            "DE12 contiene una hora fuera de rango (HH 00-23, MM 00-59, SS 00-59).",
            "DE12", value=raw, rule="TIME_RANGE")
        return
    add("INFO", "VALID_TIME",
        f"DE12 = {raw} → {hh:02d}:{mm:02d}:{ss:02d}.",
        "DE12", value=raw, rule="TIME_FORMAT")


# ---------------------------------------------------------------------------
# 9. DE13 — FECHA
# ---------------------------------------------------------------------------

def check_date(result, add: Adder):
    """Valida DE13 (MMDD). No inventa el año."""
    f = _find_field(result, 13)
    if f is None or f.has_error:
        return
    raw = (f.value or "").strip()
    if len(raw) != 4 or not raw.isdigit():
        add("ERROR", "INVALID_DATE",
            "DE13 debe tener el formato MMDD (4 dígitos).",
            "DE13", value=raw, rule="DATE_FORMAT")
        return
    mm, dd = int(raw[0:2]), int(raw[2:4])
    if mm < 1 or mm > 12:
        add("ERROR", "INVALID_DATE",
            "DE13 contiene un mes fuera de rango (MM 01-12).",
            "DE13", value=raw, rule="DATE_RANGE")
        return
    if dd < 1 or dd > _days_in_month(mm):
        add("ERROR", "INVALID_DATE",
            f"DE13 contiene un día no válido para el mes {mm:02d}.",
            "DE13", value=raw, rule="DATE_RANGE")
        return
    add("INFO", "VALID_DATE",
        f"DE13 = {raw} → {dd:02d}/{mm:02d}.",
        "DE13", value=raw, rule="DATE_FORMAT")


# ---------------------------------------------------------------------------
# 10. DE4 — MONTO
# ---------------------------------------------------------------------------

def check_amount(result, add: Adder):
    """Valida DE4 usando los minor units de la moneda detectada."""
    f = _find_field(result, 4)
    if f is None or f.has_error:
        return
    raw = (f.value or "").strip()
    if not raw:
        return
    if not raw.isdigit():
        # Lo reporta la regla de campos numéricos.
        return
    summary = TransactionSummary(result)
    amt = summary.amount()
    if amt.get("available"):
        add("INFO", "VALID_AMOUNT",
            f"DE4 corresponde a {amt['formatted']}.",
            "DE4", value=f"{raw} → {amt['formatted']}", rule="AMOUNT_FORMAT")
    else:
        add("WARNING", "AMOUNT_CURRENCY_UNKNOWN",
            "No se puede interpretar de forma monetaria el DE4 porque no "
            "existe un código de moneda válido.",
            "DE4", value=raw, rule="AMOUNT_CURRENCY")


# ---------------------------------------------------------------------------
# 11. DE49 / EMV 5F2A — MONEDA
# ---------------------------------------------------------------------------

def check_currency(result, add: Adder):
    """Compara DE49 y EMV 5F2A cuando ambas fuentes existen."""
    report = detect_currency(result)
    primary = report.primary
    emv = report.emv

    if primary and emv:
        if primary.code != emv.code:
            add("WARNING", "CURRENCY_MISMATCH",
                "Los códigos de moneda encontrados no coinciden.",
                "DE49/EMV",
                value=f"DE49: {primary.code} {primary.currency}\n"
                      f"EMV 5F2A: {emv.code} {emv.currency}",
                rule="CURRENCY_MISMATCH")
        else:
            add("INFO", "CURRENCY_MATCH",
                "DE49 y EMV 5F2A coinciden.",
                "DE49/EMV",
                value=f"{primary.code} {primary.currency}",
                rule="CURRENCY_MISMATCH")
        return

    source = primary or emv or report.secondary
    if source is None:
        return
    if source.code:
        add("INFO", "VALID_CURRENCY",
            f"{source.source} = {source.code} → {source.currency}.",
            source.source, value=f"{source.code} → {source.currency}",
            rule="CURRENCY")


# ---------------------------------------------------------------------------
# 12. DE39 — CÓDIGO DE RESPUESTA
# ---------------------------------------------------------------------------

def check_response_code(result, add: Adder):
    """Consulta el catálogo de códigos de respuesta. No inventa códigos."""
    f = _find_field(result, 39)
    if f is None or f.has_error:
        return
    code = (f.value or "").strip()
    if not code or not code.isdigit():
        return
    ref = get_reference()
    entry = ref.response_code(code)
    if entry is None and code.isdigit():
        # DE39 se define como 3 dígitos pero el catálogo usa 2: normaliza
        # el relleno a la izquierda sin inventar códigos.
        stripped = code.lstrip("0") or "0"
        if stripped != code:
            entry = ref.response_code(stripped)
    if entry is None:
        add("INFO", "RESPONSE_CODE_UNKNOWN",
            "Código de respuesta no documentado en el catálogo actual.",
            "DE39", value=code, rule="RESPONSE_CODE")
        return
    add("INFO", "RESPONSE_CODE_DOCUMENTED",
        f"DE39 = {code} → {ref.loc(entry, 'name', 'es')}.",
        "DE39", value=code, rule="RESPONSE_CODE")


# ---------------------------------------------------------------------------
# Orquestador de reglas de campos
# ---------------------------------------------------------------------------

def run_field_rules(result, add: Adder, stop=None):
    """Ejecuta todas las reglas de campos sobre un resultado."""
    check_field_decode_errors(result, add, stop=stop)
    check_field_lengths(result, add)
    check_numeric_fields(result, add)
    check_time(result, add)
    check_date(result, add)
    check_amount(result, add)
    check_currency(result, add)
    check_response_code(result, add)
