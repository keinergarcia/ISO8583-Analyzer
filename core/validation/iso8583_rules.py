# -*- coding: utf-8 -*-
"""Reglas determinísticas de validación de la estructura ISO 8583.

Todas las reglas operan sobre los datos que el parser ya decodificó
(AnalysisResult). NO re-parsean la trama ni duplican la lógica del parser.

Reglas incluidas:
- Longitud de trama (declarada vs real).
- TPDU (estructura configurada).
- MTI (4 dígitos + catálogo).
- Bitmap (longitud, formato, secundario, consistencia con campos).
- Bytes sobrantes (TRAILING_DATA).

Regla de oro: un hallazgo solo se emite si puede demostrarse con los datos
disponibles. Nunca se afirma la causa de un problema si no puede probarse.
"""

from typing import Callable

from ..bitmap import has_secondary_bitmap
from ..mti import KNOWN_MTIS
from ..utils import is_hex_text

# Adder: Callable[[severity, code, message, field, value, rule], None]
Adder = Callable[..., None]


def _length_field_hex_chars(result) -> int:
    """Caracteres hex que ocupa el campo de longitud en la trama cruda.

    - BCD / híbrido: 2 bytes de longitud = 4 caracteres hex.
    - ASCII: 4 caracteres ASCII = 4 bytes = 8 caracteres hex.
    Devuelve 0 si la trama no tiene campo de longitud.
    """
    if not result.length_hex:
        return 0
    if getattr(result, "numeric_encoding", "bcd") == "ascii":
        return 8
    return 4


def _real_frame_bytes(result) -> int:
    """Bytes reales de la trama DESPUÉS del campo de longitud."""
    total_hex = len(result.raw_clean)
    return (total_hex - _length_field_hex_chars(result)) // 2


# ---------------------------------------------------------------------------
# 1. LONGITUD DE TRAMA
# ---------------------------------------------------------------------------

def check_frame_length(result, add: Adder):
    """Compara la longitud declarada en el encabezado con la real."""
    if not result.length_hex:
        return  # sin campo de longitud no hay nada que comparar
    declared = result.length_value
    if declared <= 0:
        add("WARNING", "FRAME_LENGTH_UNKNOWN",
            "No se puede validar la longitud declarada (valor no numérico o cero).",
            "FRAME", value=f"Declarada: {result.length_hex!r}", rule="FRAME_LENGTH_MATCH")
        return
    real = _real_frame_bytes(result)
    value = f"Declarada: {declared} bytes\nReal: {real} bytes"
    if declared == real:
        add("INFO", "FRAME_LENGTH_MATCH",
            "Longitud de trama válida.",
            "FRAME", value=f"Declarada: {declared} bytes = Real: {real} bytes",
            rule="FRAME_LENGTH_MATCH")
    else:
        add("ERROR", "FRAME_LENGTH_MISMATCH",
            "La longitud declarada no coincide con la longitud real.",
            "FRAME", value=value, rule="FRAME_LENGTH_MATCH")


# ---------------------------------------------------------------------------
# 3. TPDU
# ---------------------------------------------------------------------------

def check_tpdu(result, add: Adder):
    """Valida únicamente la estructura del TPDU según la configuración actual."""
    tpdu = result.tpdu
    if tpdu is None:
        return
    if len(tpdu.hex) != 10:
        add("ERROR", "TPDU_INVALID_LENGTH",
            "El TPDU debe tener 5 bytes (10 caracteres hex).",
            "TPDU", value=f"TPDU: {tpdu.hex} ({len(tpdu.hex) // 2} bytes)",
            rule="TPDU_LENGTH")
        return
    add("INFO", "TPDU_VALID",
        "TPDU decodificado correctamente.",
        "TPDU",
        value=f"{tpdu.hex} · Destino={tpdu.destination} Origen={tpdu.source} Control={tpdu.control}",
        rule="TPDU_LENGTH")


# ---------------------------------------------------------------------------
# 4. MTI
# ---------------------------------------------------------------------------

def check_mti(result, add: Adder):
    """Valida el MTI: 4 dígitos + interpretación según catálogo."""
    mti = result.mti
    if mti is None:
        return
    h = mti.hex or ""
    if len(h) != 4 or not h.isdigit():
        add("ERROR", "MTI_INVALID_FORMAT",
            "El MTI debe tener exactamente 4 dígitos.",
            "MTI", value=f"MTI: {h or '(vacío)'}", rule="MTI_FORMAT")
        return
    if h not in KNOWN_MTIS:
        add("WARNING", "MTI_UNKNOWN",
            "El MTI tiene formato válido pero no está registrado en el catálogo.",
            "MTI", value=h, rule="MTI_CATALOG")
        return
    add("INFO", "MTI_VALID",
        "MTI interpretado correctamente.",
        "MTI", value=f"{h} · {mti.description}", rule="MTI_FORMAT")


# ---------------------------------------------------------------------------
# 5. BITMAP
# ---------------------------------------------------------------------------

def check_bitmap(result, add: Adder, stop=None):
    """Valida longitud, formato, secundario y consistencia con los campos.

    `stop` es el número del campo donde el parser se detuvo por un error de
    decodificación (ver validator._parse_stop_field). Cuando existe, los
    campos posteriores del bitmap no pudieron decodificarse por esa causa:
    no se reportan como errores independientes (cascada de falsos positivos)
    sino como una única advertencia PARSING_STOPPED_AFTER_DE<stop>.
    """
    primary = result.bitmap_primary_hex or ""
    secondary = result.bitmap_secondary_hex or ""

    if len(primary) != 16 or not is_hex_text(primary):
        add("ERROR", "BITMAP_INVALID_LENGTH",
            "El bitmap primario debe tener 8 bytes (16 caracteres hex).",
            "BITMAP", value=f"Bitmap: {primary or '(vacío)'}",
            rule="BITMAP_LENGTH")

    if has_secondary_bitmap(primary):
        if len(secondary) != 16 or not is_hex_text(secondary):
            add("ERROR", "BITMAP_SECONDARY_INVALID",
                "El bit 1 está activo (bitmap secundario presente) pero no hay "
                "8 bytes de bitmap secundario válidos.",
                "BITMAP", value=f"Primario: {primary}",
                rule="BITMAP_SECONDARY")
    elif secondary:
        add("WARNING", "BITMAP_UNEXPECTED_SECONDARY",
            "Se encontró un bitmap secundario aunque el bit 1 no lo indica.",
            "BITMAP", value=f"Secundario: {secondary}",
            rule="BITMAP_SECONDARY")

    # Consistencia bitmap <-> campos decodificados
    active = set(result.active_fields)
    present = {f.number for f in result.fields}
    missing = sorted(n for n in active if n != 1 and n not in present)

    if stop is not None:
        # El parser se detuvo en `stop`: los campos posteriores no se
        # decodificaron como consecuencia, no como errores independientes.
        after = [n for n in missing if n > stop]
        if after:
            add("WARNING", f"PARSING_STOPPED_AFTER_DE{stop}",
                f"El parser se detuvo en DE{stop}; los campos posteriores no "
                "se decodificaron y no se validan de forma independiente.",
                "FRAME", value=", ".join(f"DE{n}" for n in after),
                rule="PARSING_STOP", stage="parse", derived_from=f"DE{stop}")
        before = [n for n in missing if n <= stop]
        if before:
            add("ERROR", "BITMAP_FIELD_MISSING",
                "El bitmap indica campos presentes que no pudieron ser decodificados.",
                "BITMAP", value=", ".join(f"DE{n}" for n in before),
                rule="BITMAP_FIELD_MISSING", derived_from=f"DE{stop}")
    elif missing:
        add("ERROR", "BITMAP_FIELD_MISSING",
            "El bitmap indica campos presentes que no pudieron ser decodificados.",
            "BITMAP", value=", ".join(f"DE{n}" for n in missing),
            rule="BITMAP_FIELD_MISSING")

    unexpected = sorted(n for n in present if n != 1 and n not in active)
    if unexpected:
        add("ERROR", "FIELD_NOT_IN_BITMAP",
            "Se encontraron campos que el bitmap no indica.",
            "BITMAP", value=", ".join(f"DE{n}" for n in unexpected),
            rule="FIELD_NOT_IN_BITMAP")


# ---------------------------------------------------------------------------
# 13. BYTES SOBRANTES
# ---------------------------------------------------------------------------

def check_trailing_data(result, add: Adder):
    """Comprueba si quedan bytes sin consumir tras el último campo esperado.

    Si el parser detectó y validó un payload propietario (p. ej. GZIP tras
    DE64), esos bytes ya están explicados: se emite una INFO documentada en
    lugar de la advertencia de datos sobrantes. Si la detección es solo
    "posible" (sin verificación concluyente), se conserva TRAILING_DATA.
    """
    total_hex = len(result.raw_clean)
    length_field = _length_field_hex_chars(result)
    remaining_hex = total_hex - length_field - result.consumed_hex
    if remaining_hex <= 0:
        return
    payload = getattr(result, "trailing_payload", None)
    if payload is not None and payload.status == "confirmed":
        add("INFO", "TRAILING_DATA_EXPLAINED",
            "Los bytes posteriores al último campo pertenecen a un payload "
            "propietario detectado en DE64 y validado por descompresión GZIP.",
            "FRAME",
            value=f"Payload posterior: {payload.kind}, {payload.declared_length} "
                  f"bytes declarados, {payload.decompressed_length} bytes "
                  f"descomprimidos",
            rule="TRAILING_DATA")
        return
    remaining_bytes = remaining_hex // 2
    tail_hex = result.raw_clean[total_hex - remaining_hex:]
    add("WARNING", "TRAILING_DATA",
        "Bytes restantes después del último campo esperado.",
        "FRAME",
        value=f"Cantidad: {remaining_bytes} bytes\nHEX sobrante: {tail_hex}",
        rule="TRAILING_DATA")


# ---------------------------------------------------------------------------
# Orquestador de reglas ISO 8583
# ---------------------------------------------------------------------------

def run_iso8583_rules(result, add: Adder, stop=None):
    """Ejecuta todas las reglas estructurales ISO 8583 sobre un resultado."""
    check_frame_length(result, add)
    check_tpdu(result, add)
    check_mti(result, add)
    check_bitmap(result, add, stop=stop)
    check_trailing_data(result, add)
