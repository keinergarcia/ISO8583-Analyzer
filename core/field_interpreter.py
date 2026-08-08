# -*- coding: utf-8 -*-
"""Capa de interpretación de campos (FieldInterpreter).

Clasifica cada Data Element activo según su configuración en `fields.json`
y, en ausencia de configuración, aplica reglas genéricas conservadoras.

Reglas:
- "text": SOLO si el campo está configurado como texto en fields.json.
  Nunca se clasifica como mensaje por heurística (evita que cualquier valor
  ASCII sea tratado como mensaje).
- "code" / "response_code" / "identifier": por configuración o por el nombre
  del Data Element.
- "data": valor genérico (por defecto).

Esta capa es independiente del parser: no altera offsets, longitudes ni
valores de los campos; solo añade información de interpretación.
"""

import json
import sys
from pathlib import Path

# Etiquetas de las categorías (español)
CATEGORY_LABELS = {
    "text": "Mensaje / Texto",
    "code": "Código",
    "response_code": "Código respuesta",
    "identifier": "Identificador",
    "data": "Dato",
}

# Frase corta de cada categoría para la sección "Interpretación del Campo"
CATEGORY_SUMMARY = {
    "text": "Mensaje de texto",
    "code": "Código",
    "response_code": "Código de respuesta",
    "identifier": "Identificador",
    "data": "Dato genérico",
}

# Palabras clave para clasificar identificadores por nombre del DE
IDENTIFIER_KEYWORDS = (
    "identification",
    "identifier",
    "terminal id",
    "merchant id",
    "account identification",
)


def _config_path():
    """Ruta a fields.json (compatible con PyInstaller, igual que los perfiles)."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "fields.json"
    return Path(__file__).resolve().parent.parent / "fields.json"


class FieldInterpretation:
    """Resultado de la interpretación de un campo."""

    def __init__(self, category="data", label="Dato", summary="Dato genérico",
                 description=""):
        self.category = category
        self.label = label
        self.summary = summary
        self.description = description

    def as_dict(self):
        return {
            "category": self.category,
            "label": self.label,
            "summary": self.summary,
            "description": self.description,
        }


class FieldInterpreter:
    """Clasifica Data Elements según fields.json y reglas genéricas."""

    def __init__(self, config_path=None):
        self._config = {}
        self._load(config_path)

    def _load(self, config_path):
        path = Path(config_path) if config_path else _config_path()
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            data = {}
        for key, value in (data or {}).items():
            try:
                number = int(key)
            except (ValueError, TypeError):
                continue
            if isinstance(value, dict):
                self._config[number] = value

    # ------------------------------------------------------------------ API
    def getDescription(self, number):
        """Descripción configurada para el campo (o vacío si no hay)."""
        entry = self._config.get(int(number))
        if entry and entry.get("description"):
            return entry["description"]
        return ""

    def isTextField(self, field):
        """True si el campo está clasificado como mensaje/texto."""
        return self.detectFieldType(field) == "text"

    def isCodeField(self, field):
        """True si el campo está clasificado como código."""
        return self.detectFieldType(field) in ("code", "response_code")

    def detectFieldType(self, field):
        """Devuelve la categoría del campo: text|code|response_code|identifier|data."""
        number = getattr(field, "number", None)
        if number is None:
            return "data"
        entry = self._config.get(int(number))
        if entry and entry.get("category"):
            return entry["category"]
        return self._default_category(field)

    def interpret(self, field):
        """Interpreta un campo y devuelve un FieldInterpretation."""
        category = self.detectFieldType(field)
        number = int(getattr(field, "number", 0))
        description = (
            self.getDescription(number)
            or getattr(field, "description", "")
            or getattr(field, "name", "")
        )
        return FieldInterpretation(
            category=category,
            label=CATEGORY_LABELS.get(category, "Dato"),
            summary=CATEGORY_SUMMARY.get(category, "Dato genérico"),
            description=description,
        )

    # ----------------------------------------------------------- internals
    def _default_category(self, field):
        name = (getattr(field, "name", "") or "").lower()
        if not name:
            return "data"
        if "response code" in name:
            return "response_code"
        if "code" in name or "código" in name:
            return "code"
        if any(keyword in name for keyword in IDENTIFIER_KEYWORDS):
            return "identifier"
        return "data"


_default = None


def interpreter():
    """Instancia singleton del intérprete (carga fields.json una sola vez)."""
    global _default
    if _default is None:
        _default = FieldInterpreter()
    return _default


def interpret(field):
    """Interpreta un campo usando el intérprete por defecto."""
    return interpreter().interpret(field)
