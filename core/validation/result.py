# -*- coding: utf-8 -*-
"""Modelo de resultado del motor de validación.

Cada hallazgo (ValidationFinding) representa UNA regla determinística
verificada sobre los datos reales de la trama. La severidad es una de:

- ERROR:   problema objetivamente demostrado.
- WARNING: inconsistencia que merece revisión pero que no puede afirmarse
           como error definitivo.
- INFO:    información útil que fue determinada correctamente.

El motor NUNCA inventa causas: solo emite un hallazgo cuando una regla
puede comprobarse con los datos disponibles.
"""

from dataclasses import dataclass, field
from typing import List, Optional

SEVERITY_ERROR = "ERROR"
SEVERITY_WARNING = "WARNING"
SEVERITY_INFO = "INFO"

STATUS_VALID = "valid"
STATUS_WARNINGS = "warnings"
STATUS_ERRORS = "errors"

STATUS_LABELS = {
    STATUS_VALID: "✓ TRAMA VÁLIDA",
    STATUS_WARNINGS: "⚠ TRAMA CON ADVERTENCIAS",
    STATUS_ERRORS: "❌ TRAMA CON ERRORES",
}


@dataclass(frozen=True)
class ValidationFinding:
    """Un hallazgo emitido por una regla de validación determinística."""

    severity: str          # ERROR | WARNING | INFO
    code: str              # p. ej. FRAME_LENGTH_MISMATCH
    message: str           # descripción en español, sin causas inventadas
    field: Optional[str] = None   # p. ej. "FRAME", "DE4", "DE55/EMV"
    value: Optional[str] = None   # datos concretos verificados
    rule: Optional[str] = None    # nombre de la regla
    stage: str = "validation"     # "parse" (origen en el parser) | "validation"
    derived_from: Optional[str] = None  # campo raíz del que es consecuencia

    def as_dict(self) -> dict:
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "field": self.field,
            "value": self.value,
            "rule": self.rule,
            "stage": self.stage,
            "derived_from": self.derived_from,
        }


class ValidationResult:
    """Colección de hallazgos con estado general de la trama."""

    def __init__(self):
        self.findings: List[ValidationFinding] = []

    # ------------------------------------------------------------ registro
    def add(self, severity, code, message, field=None, value=None, rule=None,
            stage="validation", derived_from=None):
        self.findings.append(
            ValidationFinding(severity, code, message, field, value, rule,
                              stage, derived_from)
        )

    def extend(self, findings):
        for f in findings:
            self.findings.append(f)

    # ---------------------------------------------------------- consultas
    @property
    def errors(self) -> List[ValidationFinding]:
        return [f for f in self.findings if f.severity == SEVERITY_ERROR]

    @property
    def warnings(self) -> List[ValidationFinding]:
        return [f for f in self.findings if f.severity == SEVERITY_WARNING]

    @property
    def infos(self) -> List[ValidationFinding]:
        return [f for f in self.findings if f.severity == SEVERITY_INFO]

    @property
    def has_errors(self) -> bool:
        return any(f.severity == SEVERITY_ERROR for f in self.findings)

    @property
    def has_warnings(self) -> bool:
        return any(f.severity == SEVERITY_WARNING for f in self.findings)

    @property
    def status(self) -> str:
        """Estado general: valid | warnings | errors."""
        if self.has_errors:
            return STATUS_ERRORS
        if self.has_warnings:
            return STATUS_WARNINGS
        return STATUS_VALID

    @property
    def status_label(self) -> str:
        return STATUS_LABELS[self.status]

    # ------------------------------------------------------------ salida
    def as_dict(self) -> dict:
        return {
            "status": self.status,
            "status_label": self.status_label,
            "findings": [f.as_dict() for f in self.findings],
        }

    def format_lines(self) -> List[str]:
        """Líneas de la sección '--- Validación de Trama ---' del reporte."""
        lines = ["--- Validación de Trama ---", self.status_label]
        if self.errors:
            lines += ["", "Errores:"]
            for f in self.errors:
                lines += [f"❌ [{f.code}]", f.message]
                if f.value:
                    lines += [f.value]
        if self.warnings:
            lines += ["", "Advertencias:"]
            for f in self.warnings:
                lines += [f"⚠ [{f.code}]", f.message]
                if f.value:
                    lines += [f.value]
        if self.infos:
            lines += ["", "Información:"]
            for f in self.infos:
                lines += [f"✓ [{f.code}]", f.message]
                if f.value:
                    lines += [f.value]
        if not self.findings:
            lines += ["", "No se detectaron hallazgos adicionales."]
        return lines
