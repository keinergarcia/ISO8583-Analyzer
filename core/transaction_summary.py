# -*- coding: utf-8 -*-
"""Resumen de transacción (TransactionSummary).

Capa de interpretación/resumen independiente del parser: lee los valores que
el parser ya obtuvo (DE4, DE12, DE13, DE49/DE51/DE55) y reutiliza el detector
de moneda existente (`core.currency`).

- Monto: convierte DE4 (dígitos brutos) usando los *minor units* ISO 4217 de
  la moneda detectada. No se asume 2 decimales ni se inventa una moneda.
- Hora: DE12 (HHMMSS) validado; si es inválido se reporta sin corregir.
- Fecha: DE13 (MMDD) validado; se muestra DD/MM sin inventar el año.

No modifica offsets, longitudes ni valores: solo añade información.
"""

from typing import List, Optional

from .currency import detect_currency

# Etiquetas de los campos usados
DE_AMOUNT = 4
DE_TIME = 12
DE_DATE = 13


def _find_field(result, number):
    """Devuelve el ParsedField con el DE dado, o None si no está presente."""
    for f in getattr(result, "fields", []) or []:
        if f.number == number:
            return f
    return None


def _format_amount(raw: str, minor_units: int) -> Optional[str]:
    """Convierte dígitos brutos de DE4 a un monto con `minor_units` decimales.

    '000000000336', 2 -> '3.36'
    '000000000336', 0 -> '336'
    '000000000336', 3 -> '0.336'
    Devuelve None si el valor no es numérico.
    """
    raw = (raw or "").strip()
    if not raw.isdigit():
        return None
    try:
        value = int(raw)
    except (ValueError, TypeError):
        return None
    sign = "-" if value < 0 else ""
    magnitude = abs(value)
    if not minor_units:
        return f"{sign}{magnitude}"
    divisor = 10 ** minor_units
    whole, frac = divmod(magnitude, divisor)
    return f"{sign}{whole}.{frac:0{minor_units}d}"


def _format_time(raw: str) -> Optional[str]:
    """Valida DE12 (HHMMSS) y devuelve 'HH:MM:SS', o None si es inválido."""
    raw = (raw or "").strip()
    if len(raw) != 6 or not raw.isdigit():
        return None
    hh, mm, ss = int(raw[0:2]), int(raw[2:4]), int(raw[4:6])
    if hh > 23 or mm > 59 or ss > 59:
        return None
    return f"{hh:02d}:{mm:02d}:{ss:02d}"


def _format_date(raw: str) -> Optional[str]:
    """Valida DE13 (MMDD) y devuelve 'DD/MM', o None si es inválido.

    DE13 no contiene el año; no se asume ninguno.
    """
    raw = (raw or "").strip()
    if len(raw) != 4 or not raw.isdigit():
        return None
    mm, dd = int(raw[0:2]), int(raw[2:4])
    if mm < 1 or mm > 12 or dd < 1 or dd > 31:
        return None
    return f"{dd:02d}/{mm:02d}"


def _no_field(reason: str) -> dict:
    return {
        "present": False,
        "raw": None,
        "formatted": None,
        "valid": False,
        "reason": reason,
    }


def _invalid_field(raw: str, reason: str = "Valor inválido") -> dict:
    return {
        "present": True,
        "raw": raw or "",
        "formatted": None,
        "valid": False,
        "reason": reason,
    }


def _valid_field(raw: str, formatted: str) -> dict:
    return {
        "present": True,
        "raw": raw,
        "formatted": formatted,
        "valid": True,
        "reason": None,
    }


class TransactionSummary:
    """Resumen interpretativo de una transacción ISO 8583."""

    def __init__(self, result):
        self.result = result
        self.currency_report = detect_currency(result)
        self._de4 = _find_field(result, DE_AMOUNT)
        self._de12 = _find_field(result, DE_TIME)
        self._de13 = _find_field(result, DE_DATE)

    # ------------------------------------------------------------- moneda
    @property
    def source(self):
        """CurrencySource principal (DE49 > EMV > DE51) o None."""
        rep = self.currency_report
        return rep.primary or rep.emv or rep.secondary

    def currency(self) -> dict:
        """Información de la moneda detectada para el resumen."""
        rep = self.currency_report
        src = self.source
        if not rep.detected or src is None:
            return {
                "detected": False,
                "code": None,
                "currency": None,
                "name": None,
                "source": None,
                "minor_units": None,
                "mismatch": False,
                "primary": None,
                "emv": None,
            }
        return {
            "detected": True,
            "code": src.code,
            "currency": src.currency,
            "name": src.name,
            "source": src.source,
            "minor_units": src.minor_units,
            "mismatch": rep.mismatch,
            "primary": rep.primary.as_dict() if rep.primary else None,
            "emv": rep.emv.as_dict() if rep.emv else None,
        }

    # ------------------------------------------------------------- monto
    def amount(self) -> dict:
        """Monto de DE4: bruto + conversión con minor units de la moneda."""
        f = self._de4
        if f is None or f.has_error or not (f.value or "").strip():
            return {
                "present": False,
                "raw": None,
                "converted": None,
                "formatted": None,
                "available": False,
                "reason": "DE4 no está presente.",
            }
        raw = f.value.strip()
        src = self.source
        if src is None or src.minor_units is None:
            return {
                "present": True,
                "raw": raw,
                "converted": None,
                "formatted": None,
                "available": False,
                "reason": "No se detectó una moneda ISO 4217 válida.",
            }
        converted = _format_amount(raw, src.minor_units)
        if converted is None:
            return {
                "present": True,
                "raw": raw,
                "converted": None,
                "formatted": None,
                "available": False,
                "reason": "El valor de DE4 no es numérico.",
            }
        return {
            "present": True,
            "raw": raw,
            "converted": converted,
            "formatted": f"{converted} {src.currency}",
            "available": True,
            "reason": None,
        }

    # ------------------------------------------------------------- hora
    def time(self) -> dict:
        """Hora local de la transacción desde DE12."""
        f = self._de12
        if f is None:
            return _no_field("DE12 no está presente.")
        if f.has_error or not (f.value or "").strip():
            return _invalid_field(f.value)
        formatted = _format_time(f.value)
        if formatted is None:
            return _invalid_field(f.value)
        return _valid_field(f.value.strip(), formatted)

    # ------------------------------------------------------------- fecha
    def date(self) -> dict:
        """Fecha local de la transacción desde DE13."""
        f = self._de13
        if f is None:
            return _no_field("DE13 no está presente.")
        if f.has_error or not (f.value or "").strip():
            return _invalid_field(f.value)
        formatted = _format_date(f.value)
        if formatted is None:
            return _invalid_field(f.value)
        return _valid_field(f.value.strip(), formatted)

    # ------------------------------------------------------------ confianza
    @property
    def reliable(self) -> bool:
        """El monto convertido es confiable (moneda válida y sin conflicto)."""
        if not self.amount()["available"]:
            return False
        return not self.currency_report.mismatch

    # ------------------------------------------------------------- salida
    def as_dict(self) -> dict:
        return {
            "amount": self.amount(),
            "currency": self.currency(),
            "time": self.time(),
            "date": self.date(),
            "reliable": self.reliable,
        }

    def format_summary(self) -> List[str]:
        """Líneas de la sección '--- Resumen de Transacción ---'."""
        lines = ["--- Resumen de Transacción ---"]

        # Monto
        amt = self.amount()
        if amt["available"]:
            lines += ["", "Monto de la transacción:", amt["formatted"]]
            lines += ["", "Monto bruto DE4:", amt["raw"]]
        elif amt["present"]:
            lines += ["", "Monto bruto:", amt["raw"]]
            lines += ["", "Monto interpretado:", "No disponible"]
            lines += ["", "Motivo:", amt["reason"]]
        else:
            lines += ["", "Monto:", "No disponible"]
            lines += ["", "Motivo:", amt["reason"]]

        # Moneda
        cur = self.currency()
        if cur["detected"]:
            if cur["name"]:
                lines += ["", "Moneda:", f"{cur['currency']} - {cur['name']}"]
            else:
                lines += ["", "Moneda:", cur["currency"]]
            lines += ["", "Código ISO:", cur["code"]]
            lines += ["", "Fuente de moneda:", cur["source"]]
            if cur["minor_units"] is not None:
                lines += ["", "Minor units:", str(cur["minor_units"])]
            if cur["mismatch"]:
                lines += [
                    "",
                    "⚠ Advertencia de moneda",
                    "DE49:",
                    f"{cur['primary']['code']} - {cur['primary']['currency']}",
                    "EMV 5F2A:",
                    f"{cur['emv']['code']} - {cur['emv']['currency']}",
                    "Estado:",
                    "Los códigos de moneda no coinciden.",
                ]
            elif cur["primary"] and cur["emv"]:
                lines += ["", "Validación EMV:", "Coincide"]
        else:
            lines += ["", "Moneda:", "No detectada"]

        # Hora
        tm = self.time()
        if tm["valid"]:
            lines += ["", "Hora de la transacción:", tm["formatted"]]
            lines += ["", "DE12:", tm["raw"]]
        elif tm["present"]:
            lines += ["", "Hora:", "Valor inválido"]
        else:
            lines += ["", "Hora:", "No disponible"]
            lines += ["", "Motivo:", tm["reason"]]

        # Fecha
        dt = self.date()
        if dt["valid"]:
            lines += ["", "Fecha de la transacción:", dt["formatted"]]
            lines += ["", "DE13:", dt["raw"]]
        elif dt["present"]:
            lines += ["", "Fecha:", "Valor inválido"]
        else:
            lines += ["", "Fecha:", "No disponible"]
            lines += ["", "Motivo:", dt["reason"]]

        return lines



