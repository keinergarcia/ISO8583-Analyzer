# -*- coding: utf-8 -*-
"""Detector de moneda ISO 8583 (CurrencyDetector).

Detecta la moneda de una transacción SOLO a partir de fuentes designadas:

1. DE49 - Transaction Currency Code (ISO 4217 numérico de 3 dígitos).
2. DE51 - Currency Code of Cardholder Account (moneda secundaria).
3. DE55 - EMV: Tag 5F2A (Transaction Currency Code).

Regla clave: NO se asume que cualquier número de 3 dígitos es una moneda.
Solo se interpreta cuando el dato proviene de DE49, DE51 o del tag EMV 5F2A.
Esta capa es independiente del parser: no modifica offsets ni valores.
"""

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from .converters import bcd_to_decimal

# Tag EMV que codifica la moneda de la transacción
EMV_CURRENCY_TAG = "5F2A"


def _config_path():
    """Ruta a currencies.json (compatible con PyInstaller)."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "currencies.json"
    return Path(__file__).resolve().parent.parent / "currencies.json"


@dataclass
class CurrencySource:
    """Moneda detectada desde una fuente concreta de la trama."""
    source: str        # "DE49", "DE51" o "DE55 Tag 5F2A"
    code: str          # "840"
    currency: str      # "USD"
    name: str          # "Dólar estadounidense"
    minor_units: Optional[int] = None  # decimales ISO 4217 (0, 2, 3...)

    def as_dict(self) -> dict:
        return {
            "source": self.source,
            "code": self.code,
            "currency": self.currency,
            "name": self.name,
            "minor_units": self.minor_units,
        }


@dataclass
class CurrencyReport:
    """Resultado completo de la detección de moneda."""
    primary: Optional[CurrencySource] = None      # DE49
    secondary: Optional[CurrencySource] = None    # DE51
    emv: Optional[CurrencySource] = None          # DE55 Tag 5F2A

    @property
    def detected(self) -> bool:
        return any((self.primary, self.emv, self.secondary))

    @property
    def mismatch(self) -> bool:
        """True si DE49 y el tag EMV 5F2A difieren."""
        if self.primary and self.emv and self.primary.code != self.emv.code:
            return True
        return False

    def as_dict(self) -> dict:
        return {
            "detected": self.detected,
            "primary": self.primary.as_dict() if self.primary else None,
            "secondary": self.secondary.as_dict() if self.secondary else None,
            "emv": self.emv.as_dict() if self.emv else None,
            "mismatch": self.mismatch,
        }


class CurrencyDetector:
    """Detecta la moneda de un análisis ISO 8583."""

    def __init__(self, config_path=None):
        self._currencies = {}
        self._load(config_path)

    def _load(self, config_path):
        path = Path(config_path) if config_path else _config_path()
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            data = {}
        for code, value in (data or {}).items():
            if isinstance(value, dict) and value.get("code"):
                self._currencies[str(code)] = value

    # ------------------------------------------------------------ consultas
    def getISO4217Name(self, code):
        """Devuelve (código, nombre) para un código ISO 4217 o None si no existe."""
        entry = self._currencies.get(str(code))
        if not entry:
            return None
        return entry.get("code", str(code)), entry.get("name", "")

    def getMinorUnits(self, code):
        """Decimales ISO 4217 (minor units) para un código, o None si no existe."""
        entry = self._currencies.get(str(code))
        if not entry:
            return None
        return entry.get("minor_units")

    # ------------------------------------------------------------ detección
    def detectFromDE49(self, result):
        """Moneda principal desde el DE49."""
        return self._detect_from_de(result, 49, "DE49")

    def detectFromDE51(self, result):
        """Moneda secundaria desde el DE51."""
        return self._detect_from_de(result, 51, "DE51")

    def detectFromEMV55(self, result):
        """Moneda desde el DE55 (tag EMV 5F2A).

        Primero usa el DE55 ya parseado (nodos EMV / valor); si no está
        disponible, localiza el TLV 5F2A en la trama cruda como respaldo
        (tramas incompletas o con DE55 no alineado).
        """
        for f in result.fields:
            if f.number == 55 and not f.has_error:
                value_hex = self._find_5f2a(f.value, f.emv)
                if value_hex:
                    code = self._bcd_code(value_hex)
                    if code is not None:
                        return self._build_emv_source(code)
        value_hex = self._scan_raw_for_5f2a(result.raw_clean)
        if value_hex:
            code = self._bcd_code(value_hex)
            if code is not None:
                return self._build_emv_source(code)
        return None

    def detect(self, result) -> CurrencyReport:
        """Detecta la moneda en orden: DE49 (principal), DE51 (secundaria), EMV."""
        return CurrencyReport(
            primary=self.detectFromDE49(result),
            secondary=self.detectFromDE51(result),
            emv=self.detectFromEMV55(result),
        )

    def formatCurrencyResult(self, report) -> List[str]:
        """Líneas de texto para la sección '--- Moneda de Transacción ---'."""
        lines = []
        if report.primary:
            lines += [
                "Fuente principal:",
                "DE49",
                "",
                "Código ISO:",
                report.primary.code,
                "Moneda:",
                report.primary.currency,
                "Descripción:",
                report.primary.name,
            ]
            if report.secondary:
                lines += self._secondary_block(report.secondary)
            if report.emv:
                lines += [
                    "",
                    "Fuente EMV:",
                    "DE55 Tag 5F2A",
                    "",
                    "Código:",
                    report.emv.code,
                ]
                if report.mismatch:
                    lines += [
                        "",
                        "⚠ Advertencia:",
                        "Diferencia de moneda detectada",
                        "",
                        "DE49:",
                        f"{report.primary.code} {report.primary.currency}",
                        "EMV:",
                        f"{report.emv.code} {report.emv.currency}",
                    ]
                else:
                    lines += ["", "Resultado:", "Coincide con DE49"]
        elif report.emv:
            lines += [
                "Moneda detectada desde EMV",
                "",
                "Fuente:",
                "DE55 Tag 5F2A",
                "",
                "Código:",
                report.emv.code,
                "Moneda:",
                report.emv.currency,
            ]
            if report.secondary:
                lines += self._secondary_block(report.secondary)
        elif report.secondary:
            lines += self._secondary_block(report.secondary)
        else:
            lines += ["Moneda:", "No detectada"]
        return lines

    # ------------------------------------------------------------- internos
    def _build_emv_source(self, code):
        info = self.getISO4217Name(code)
        if info is None:
            return None
        currency, name = info
        return CurrencySource("DE55 Tag 5F2A", code, currency, name,
                              minor_units=self.getMinorUnits(code))

    def _secondary_block(self, source):
        return [
            "",
            "Moneda secundaria (DE51):",
            f"{source.code} {source.currency}",
            "",
            "Código ISO:",
            source.code,
            "Moneda:",
            source.currency,
            "Descripción:",
            source.name,
        ]

    def _detect_from_de(self, result, number, label):
        for f in result.fields:
            if f.number == number and not f.has_error and f.value:
                code = f.value.strip()
                if code.isdigit() and len(code) <= 3:
                    code = code.lstrip("0") or "0"
                    info = self.getISO4217Name(code)
                    if info:
                        currency, name = info
                        return CurrencySource(label, code, currency, name,
                                              minor_units=self.getMinorUnits(code))
        return None

    def _find_5f2a(self, value, emv_nodes):
        if emv_nodes:
            res = self._search_emv_nodes(emv_nodes)
            if res:
                return res
        value = (value or "").strip().replace(" ", "")
        if value:
            try:
                from .emv import parse_tlv
                nodes = parse_tlv(value)
                res = self._search_emv_nodes([n.as_dict() for n in nodes])
                if res:
                    return res
            except (ValueError, IndexError):
                pass
        return None

    def _search_emv_nodes(self, nodes):
        for node in nodes:
            if node.get("tag") == EMV_CURRENCY_TAG and node.get("value_hex"):
                return node["value_hex"]
            children = node.get("children") or []
            if children:
                res = self._search_emv_nodes(children)
                if res:
                    return res
        return None

    def _scan_raw_for_5f2a(self, raw_hex):
        """Busca el TLV 5F2A en la trama cruda como respaldo.

        Solo acepta un TLV bien formado: tag 5F2A + byte de longitud + valor.
        """
        up = (raw_hex or "").upper()
        idx = 0
        while True:
            idx = up.find(EMV_CURRENCY_TAG, idx)
            if idx < 0:
                return None
            after = idx + len(EMV_CURRENCY_TAG)
            if after + 2 <= len(up):
                try:
                    n = int(up[after:after + 2], 16)
                except ValueError:
                    n = -1
                if 0 <= n < 0x80:
                    start = after + 2
                    end = start + n * 2
                    if end <= len(up):
                        return up[start:end]
            idx = after
        return None

    def _bcd_code(self, value_hex):
        try:
            return bcd_to_decimal(value_hex).lstrip("0") or "0"
        except ValueError:
            return None


_default = None


def detector():
    """Instancia singleton del detector (carga currencies.json una sola vez)."""
    global _default
    if _default is None:
        _default = CurrencyDetector()
    return _default


def detect_currency(result) -> CurrencyReport:
    """Detecta la moneda de un AnalysisResult usando el detector por defecto."""
    return detector().detect(result)
