# -*- coding: utf-8 -*-
"""Preparador de tramas: extrae la trama HEX real desde distintos formatos.

Detecta de forma determinística el formato de entrada (HEX continuo, HEX
separado por espacios, hexdump con offset, hexdump con columna ASCII) y
extrae únicamente la trama HEX real.

Reglas:
- NO usa IA ni heurísticas ambiguas: solo estructuras bien definidas.
- La columna ASCII de un hexdump NUNCA forma parte de la trama, incluso si
  contiene letras hex (A-F) o dígitos.
- Se preservan los bytes 00 y el orden; nunca se inventan bytes.
- Si el formato no puede determinarse con seguridad se devuelve un error y
  NO se modifica la entrada.
- No toca el parser, la validación, los conversores ni las funciones EMV.
"""

from dataclasses import dataclass
import re
from typing import List, Optional

from .utils import HEX_SET, clean_frame, clean_hex

# ---------------------------------------------------------------------------
# Formatos detectables
# ---------------------------------------------------------------------------

FMT_CONTINUO = "hex_continuo"
FMT_ESPACIADO = "hex_espaciado"
FMT_HEXDUMP = "hexdump"
FMT_HEXDUMP_ASCII = "hexdump_ascii"

FORMAT_LABELS = {
    FMT_CONTINUO: "HEX continuo",
    FMT_ESPACIADO: "HEX separado por espacios",
    FMT_HEXDUMP: "Hexdump con offset",
    FMT_HEXDUMP_ASCII: "Hexdump con offset + ASCII",
}

ERROR_UNDETERMINED = "No se pudo determinar el formato de la trama."

# Línea de hexdump: offset de 4-8 hex seguido de 2+ espacios y los bytes.
_OFFSET_RE = re.compile(r"^([0-9a-fA-F]{4,8})[ \t]{2,}(.*)$")
# Columna de bytes: pares hex separados por espacios individuales.
_HEX_COL_RE = re.compile(r"^((?:[0-9a-fA-F]{2})(?: [0-9a-fA-F]{2})*)")


@dataclass
class FramePrepResult:
    """Resultado del preparador de tramas."""

    ok: bool = False
    format: Optional[str] = None
    format_label: str = ""
    hex_clean: str = ""
    bytes_count: int = 0
    error: str = ""
    lines_processed: int = 0
    has_ascii: bool = False
    integritas_ok: bool = False


def _non_empty_lines(text: str) -> List[str]:
    return [ln for ln in (text or "").splitlines() if ln.strip()]


def _is_byte_token(token: str) -> bool:
    return len(token) == 2 and all(ch in HEX_SET for ch in token)


def _all_byte_pairs(lines: List[str]) -> bool:
    for ln in lines:
        tokens = ln.split()
        if not tokens:
            return False
        if any(not _is_byte_token(t) for t in tokens):
            return False
    return True


def _hexdump_info(lines: List[str]):
    """Devuelve (bytes_por_linea, tiene_ascii) si TODAS las líneas son hexdump.

    bytes_por_linea: lista con la columna HEX de cada línea (tokens unidos).
    Si alguna línea no cumple la estructura estricta devuelve None (ambigüo).
    """
    columns: List[str] = []
    has_ascii = False
    for ln in lines:
        m = _OFFSET_RE.match(ln.strip())
        if m is None:
            return None
        rest = m.group(2)
        col = _HEX_COL_RE.match(rest)
        if col is None:
            return None
        hex_col = col.group(1)
        after = rest[len(hex_col):]
        # Tras la columna HEX solo puede haber: fin de línea, espacios sueltos
        # o una columna ASCII separada por 2+ espacios.
        stripped = after.lstrip(" \t")
        if stripped:
            sep = len(after) - len(after.lstrip(" \t"))
            if sep < 2:
                return None
            has_ascii = True
        columns.append("".join(hex_col.split()))
    return columns, has_ascii


def detect_format(text: str) -> Optional[str]:
    """Detecta el formato de la entrada. Devuelve clave de FORMAT_LABELS o None."""
    if not text or not text.strip():
        return None
    lines = _non_empty_lines(text)
    if not lines:
        return None

    # 1) Hexdump (todas las líneas deben cumplir la estructura estricta).
    info = _hexdump_info(lines)
    if info is not None:
        return FMT_HEXDUMP_ASCII if info[1] else FMT_HEXDUMP

    # 2) Ambigüedad: alguna línea parece hexdump pero no todas lo son.
    #    En ese caso NO se extrae nada para no mezclar offset/ASCII con HEX.
    if any(_OFFSET_RE.match(ln.strip()) for ln in lines):
        return None

    # 3) HEX separado por espacios (todos los tokens son bytes de 2 hex).
    if _all_byte_pairs(lines):
        return FMT_ESPACIADO

    # 4) HEX continuo: tras limpiar solo separadores/invisibles deben quedar
    #    únicamente caracteres HEX (paridad se valida en prepare_frame).
    cleaned = clean_frame(text)
    if cleaned and all(ch in HEX_SET for ch in cleaned):
        return FMT_CONTINUO

    return None


def extract_hex(text: str, fmt: Optional[str] = None):
    """Devuelve (hex_clean, error). Si fmt es None se detecta solo."""
    fmt = fmt or detect_format(text)
    if fmt is None:
        return "", ERROR_UNDETERMINED
    lines = _non_empty_lines(text)

    if fmt in (FMT_HEXDUMP, FMT_HEXDUMP_ASCII):
        info = _hexdump_info(lines)
        if info is None:
            return "", ERROR_UNDETERMINED
        return "".join(info[0]), ""

    if fmt == FMT_ESPACIADO:
        return "".join(ln.replace(" ", "").replace("\t", "") for ln in lines), ""

    # FMT_CONTINUO
    return clean_hex(text), ""


def prepare_frame(text: str) -> FramePrepResult:
    """Prepara una trama: detecta formato, extrae HEX y valida integridad."""
    text = text or ""
    result = FramePrepResult(lines_processed=len(_non_empty_lines(text)))

    fmt = detect_format(text)
    if fmt is None:
        result.error = ERROR_UNDETERMINED
        return result

    hex_clean, err = extract_hex(text, fmt)
    if err:
        result.format = fmt
        result.format_label = FORMAT_LABELS[fmt]
        result.error = err
        return result

    # Validación estricta: caracteres hex, paridad, bytes reales.
    if not hex_clean:
        result.format = fmt
        result.format_label = FORMAT_LABELS[fmt]
        result.error = "La trama extraída está vacía."
        return result

    if any(ch not in HEX_SET for ch in hex_clean):
        result.format = fmt
        result.format_label = FORMAT_LABELS[fmt]
        result.error = "La trama extraída contiene caracteres que no son HEX."
        return result

    if len(hex_clean) % 2 != 0:
        result.format = fmt
        result.format_label = FORMAT_LABELS[fmt]
        result.error = "La trama extraída debe tener una cantidad par de caracteres HEX."
        return result

    # Integridad: los bytes extraídos == los bytes normalizados (sin perder 00).
    try:
        integritas_ok = bytes.fromhex(hex_clean) == bytes.fromhex(hex_clean.lower())
    except ValueError:
        integritas_ok = False

    result.ok = True
    result.format = fmt
    result.format_label = FORMAT_LABELS[fmt]
    result.hex_clean = hex_clean
    result.bytes_count = len(hex_clean) // 2
    result.has_ascii = fmt == FMT_HEXDUMP_ASCII
    result.integritas_ok = integritas_ok
    return result
