# -*- coding: utf-8 -*-
"""Modelo estructurado de validaciones y avisos del análisis.

Sustituye las listas planas de strings por issues tipados con severidad y
código, lo que permite reportes, filtrado en UI y reglas reutilizables.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class ValidationIssue:
    severity: str  # info | warning | error
    code: str
    message: str
    field_no: Optional[int] = None

    def as_dict(self):
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "field_no": self.field_no,
        }


class IssueList(list):
    """Colección de ValidationIssue con accesos por severidad."""

    @property
    def errors(self):
        return [i for i in self if i.severity == "error"]

    @property
    def warnings(self):
        return [i for i in self if i.severity == "warning"]

    @property
    def infos(self):
        return [i for i in self if i.severity == "info"]

    def add(self, severity, code, message, field_no=None):
        self.append(ValidationIssue(severity, code, message, field_no))

    @property
    def has_errors(self):
        return any(i.severity == "error" for i in self)

    def as_list(self):
        return [i.as_dict() for i in self]
