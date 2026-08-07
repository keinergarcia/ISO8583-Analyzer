# -*- coding: utf-8 -*-
"""Gestión del Bitmap ISO 8583 (primario y secundario)."""


def parse_bitmap(hex_str):
    """Convierte el bitmap (cadena hex de 8 o 16 bytes) en la lista de DE activos.

    El bit más significativo de cada byte corresponde al DE impar; el bit 1 del
    primer byte indica la presencia del bitmap secundario.
    """
    fields = []
    try:
        raw = bytes.fromhex(hex_str)
    except (ValueError, TypeError):
        return fields
    for idx, byte in enumerate(raw):
        for bit in range(8):
            if byte & (0x80 >> bit):
                fields.append(idx * 8 + bit + 1)
    return fields


def has_secondary_bitmap(primary_hex):
    """True si el bit 1 del bitmap primario está activo (DE65 presente)."""
    if not primary_hex:
        return False
    try:
        return bool(int(primary_hex[:2], 16) & 0x80)
    except ValueError:
        return False


def primary_hex(bitmap_hex):
    """Devuelve los 8 primeros bytes del bitmap."""
    return bitmap_hex[:16] if bitmap_hex else ""


def secondary_hex(bitmap_hex):
    """Devuelve el bitmap secundario (si lo hay)."""
    return bitmap_hex[16:32] if len(bitmap_hex) > 16 else ""


def bits(hex_str):
    """Representación binaria legible del bitmap (bits 1-128)."""
    out = []
    try:
        raw = bytes.fromhex(hex_str)
    except (ValueError, TypeError):
        return out
    for byte in raw:
        out.append(format(byte, "08b"))
    return " ".join(out)
