# -*- coding: utf-8 -*-
"""Motor de Validación y Detección de Errores ISO 8583.

Capa independiente encima del parser existente: reutiliza los datos que el
parser ya decodificó y emite hallazgos ERROR / WARNING / INFO mediante reglas
determinísticas verificables. Nunca adivina errores ni inventa causas.

Uso:
    from core.validation import validate, validate_result, validate_frame

    res = validate(trama_hex)          # valida trama cruda (la decodifica)
    res = validate(analysis_result)    # valida un AnalysisResult ya parseado
"""

from .emv_rules import run_emv_rules
from .field_rules import run_field_rules
from .iso8583_rules import run_iso8583_rules
from .result import (
    SEVERITY_ERROR,
    SEVERITY_INFO,
    SEVERITY_WARNING,
    STATUS_ERRORS,
    STATUS_LABELS,
    STATUS_VALID,
    STATUS_WARNINGS,
    ValidationFinding,
    ValidationResult,
)
from .validator import validate, validate_frame, validate_result

__all__ = [
    "validate",
    "validate_frame",
    "validate_result",
    "run_iso8583_rules",
    "run_field_rules",
    "run_emv_rules",
    "ValidationResult",
    "ValidationFinding",
    "SEVERITY_ERROR",
    "SEVERITY_WARNING",
    "SEVERITY_INFO",
    "STATUS_VALID",
    "STATUS_WARNINGS",
    "STATUS_ERRORS",
    "STATUS_LABELS",
]
