# -*- coding: utf-8 -*-
"""Formatter: vista de bytes estilo Notepad++ (hex / ascii / bin / bcd).

Genera filas alineadas con offset. Es una función pura (sin Qt): el mismo
modelo alimenta a la vista de la UI, a la exportación y a los scripts.
"""

from dataclasses import dataclass

from ..utils import HEX_SET, clean_hex, is_removable


@dataclass
class FormattedRow:
    offset: int
    hex_part: str
    ascii_part: str = ""


STYLES = ("hex", "ascii", "binary", "bcd")


def _printable(b):
    return chr(b) if 0x20 <= b <= 0x7E else "."


def _validate_hex_input(hex_str):
    """Valida la entrada: solo caracteres hex y separadores/ocultos.

    Rechaza cualquier otro carácter en lugar de eliminarlo silenciosamente
    (p. ej. '12ZZ', 'GG', '0XGG'). Devuelve la cadena hex limpia y continua.
    """
    if hex_str is None:
        return ""
    raw = str(hex_str)
    for ch in raw:
        if ch not in HEX_SET and not is_removable(ch):
            raise ValueError(
                f"HEX inválido: carácter no permitido {ch!r}. "
                "Solo se admiten dígitos hexadecimales y separadores (espacios, saltos de línea)."
            )
    cleaned = clean_hex(raw)
    if len(cleaned) % 2 != 0:
        raise ValueError("HEX inválido: la cantidad de caracteres debe ser par.")
    return cleaned


def render_rows(hex_str, style="hex", cols=16):
    """Devuelve la lista de filas formateadas de la trama."""
    if style not in STYLES:
        raise ValueError(f"Estilo desconocido: {style}. Válidos: {', '.join(STYLES)}")
    if cols < 1:
        raise ValueError("El número de columnas debe ser mayor que cero.")
    cleaned = _validate_hex_input(hex_str)
    if not cleaned:
        return []
    raw = bytes.fromhex(cleaned)

    rows = []
    for i in range(0, len(raw), cols):
        chunk = raw[i:i + cols]
        off = i
        if style == "hex":
            rows.append(FormattedRow(
                off,
                " ".join(f"{b:02X}" for b in chunk),
                "".join(_printable(b) for b in chunk),
            ))
        elif style == "ascii":
            rows.append(FormattedRow(off, "".join(_printable(b) for b in chunk)))
        elif style == "binary":
            rows.append(FormattedRow(off, " ".join(f"{b:08b}" for b in chunk)))
        elif style == "bcd":
            parts = []
            for b in chunk:
                hi, lo = b >> 4, b & 0x0F
                parts.append(f"{hi}{lo}" if hi <= 9 and lo <= 9 else "..")
            rows.append(FormattedRow(off, " ".join(parts)))
    return rows


def render(hex_str, style="hex", cols=16):
    """Devuelve el texto formateado completo (para UI, export y scripts)."""
    rows = render_rows(hex_str, style, cols)
    lines = []
    pad = cols * 3 - 1
    for row in rows:
        off = f"{row.offset:08X}"
        if style == "hex":
            lines.append(f"{off}  {row.hex_part:<{pad}}  {row.ascii_part}")
        else:
            lines.append(f"{off}  {row.hex_part}")
    return "\n".join(lines)


def line_count(hex_str, cols=16):
    cleaned = _validate_hex_input(hex_str)
    if not cleaned:
        return 0
    return (len(cleaned) // 2 + cols - 1) // cols
