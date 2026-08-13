# -*- coding: utf-8 -*-
"""Orquestador del motor de validación ISO 8583.

Arquitectura (independiente del parser):

    TRAMA HEX
      → Parser existente (core.parser.parse_message)
      → Datos ya decodificados (AnalysisResult)
      → Este motor de validación
      → Reglas determinísticas
      → ValidationResult (ERROR / WARNING / INFO)

La IA NO decide si existe un error: cada hallazgo proviene de una regla
verificable sobre los datos reales. La validación opera sobre AnalysisResult
(ya parseado) o sobre una trama cruda (en ese caso primero se parsea con el
mismo parser existente y los ParseError se convierten en hallazgos).
"""

from typing import Optional, Union

from ..parser import ParseError, ParseOptions, parse_message
from ..utils import HEX_SET, clean_frame, clean_hex, is_removable
from .emv_rules import run_emv_rules
from .field_rules import run_field_rules
from .iso8583_rules import run_iso8583_rules
from .result import ValidationResult


def _parse_stop_field(result) -> Optional[int]:
    """Número del campo donde el parser se detuvo por un error de
    decodificación, o None si el parseo llegó al final.

    Cuando `_read_fields_hex` encuentra un campo que no puede decodificar,
    lo registra (has_error=True) y rompe el bucle: ese campo es siempre el
    último de result.fields. Un campo sin definición (has_error=True con
    "Definición de campo no encontrada") NO detiene el parseo y se ignora.
    """
    fields = getattr(result, "fields", None) or []
    if not fields:
        return None
    last = fields[-1]
    if not last.has_error:
        return None
    msg = (last.error or "").lower()
    if "definición de campo no encontrada" in msg:
        return None
    return last.number


def validate_result(result) -> ValidationResult:
    """Valida un AnalysisResult ya decodificado por el parser existente."""
    findings = ValidationResult()
    stop = _parse_stop_field(result)

    # Hallazgos de nivel trama que el parser ya determinó (nunca inventados).
    for w in result.warnings:
        findings.add("WARNING", "PARSE_WARNING", w, "FRAME", rule="PARSE",
                     stage="parse")
    for e in result.errors:
        findings.add("ERROR", "PARSE_ERROR", e, "FRAME", rule="PARSE",
                     stage="parse")

    run_iso8583_rules(result, findings.add, stop=stop)
    run_field_rules(result, findings.add, stop=stop)
    run_emv_rules(result, findings.add)
    return findings


def validate_frame(raw, options: Optional[ParseOptions] = None) -> ValidationResult:
    """Valida una trama cruda: valida el HEX y la decodifica con el parser
    existente antes de aplicar las reglas determinísticas.

    Los errores que el parser rechaza (ParseError) se convierten en hallazgos
    ERROR con código específico. No se adivina la causa.
    """
    findings = ValidationResult()

    clean = clean_frame(raw)
    if not clean:
        findings.add("ERROR", "FRAME_EMPTY", "La trama está vacía.",
                     "FRAME", rule="HEX_VALIDITY")
        return findings

    hex_part = clean_hex(clean)
    if len(hex_part) % 2 != 0:
        findings.add("ERROR", "HEX_INVALID_LENGTH",
                     "La cantidad de caracteres HEX debe ser par.",
                     "FRAME", value=f"Caracteres: {len(hex_part)}",
                     rule="HEX_VALIDITY")
        return findings

    visible_bad = "".join(dict.fromkeys(
        ch for ch in clean if ch not in HEX_SET and not is_removable(ch)))
    if visible_bad:
        findings.add("ERROR", "HEX_INVALID_CHAR",
                     "Caracteres no permitidos en la trama.",
                     "FRAME", value=f"Caracteres: {visible_bad}",
                     rule="HEX_VALIDITY")
        return findings

    try:
        result = parse_message(raw, options or ParseOptions())
    except ParseError as exc:
        findings.add("ERROR", "PARSE_FAILED", str(exc), "FRAME", rule="PARSE")
        return findings

    findings.extend(validate_result(result).findings)
    return findings


def validate(message_or_result_or_raw: Union[object, str],
             options: Optional[ParseOptions] = None) -> ValidationResult:
    """Punto de entrada unificado.

    - Si recibe un AnalysisResult (objeto con .fields / .raw_clean), lo valida.
    - Si recibe un Message (core.model.message), valida su .legacy.
    - Si recibe texto, lo trata como trama cruda y la decodifica.
    """
    if isinstance(message_or_result_or_raw, str):
        return validate_frame(message_or_result_or_raw, options)

    legacy = getattr(message_or_result_or_raw, "legacy", None)
    result = legacy if legacy is not None else message_or_result_or_raw
    if hasattr(result, "raw_clean"):
        return validate_result(result)
    return ValidationResult()
