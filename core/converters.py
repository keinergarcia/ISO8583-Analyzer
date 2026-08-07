# -*- coding: utf-8 -*-
"""Utilidades de conversión: HEX, ASCII, BCD, Decimal, formateo."""


def clean_text(text):
    """Normaliza una entrada eliminando espacios y separadores comunes."""
    if text is None:
        return ""
    return "".join(
        ch for ch in str(text)
        if ch not in (" ", "\t", "\n", "\r", "-", ":", ",", ".", ";", "|", "/")
    )


def is_hex(text):
    """True si el texto contiene únicamente dígitos hexadecimales."""
    if not text:
        return False
    return all(ch in "0123456789abcdefABCDEF" for ch in text)


def hex_to_ascii(text):
    """Convierte una cadena hex en su representación ASCII."""
    cleaned = clean_text(text)
    if not is_hex(cleaned):
        raise ValueError("Entrada no válida: solo se permiten caracteres hexadecimales.")
    if len(cleaned) % 2 != 0:
        raise ValueError("La entrada hexadecimal debe tener un número par de caracteres.")
    raw = bytes.fromhex(cleaned)
    return "".join(chr(b) if 0x20 <= b <= 0x7E else "." for b in raw)


def ascii_to_hex(text):
    """Convierte una cadena ASCII a su representación hex."""
    return (str(text).encode("utf-8")).hex().upper()


def bcd_to_decimal(text):
    """Interpreta una cadena hex como dígitos BCD y devuelve el número decimal."""
    cleaned = clean_text(text)
    if not is_hex(cleaned):
        raise ValueError("Entrada no válida: solo se permiten caracteres hexadecimales.")
    if len(cleaned) % 2 != 0:
        raise ValueError("La entrada hexadecimal debe tener un número par de caracteres.")
    digits = []
    for byte in bytes.fromhex(cleaned):
        high, low = byte >> 4, byte & 0x0F
        if high > 9 or low > 9:
            raise ValueError("Secuencia BCD inválida (contiene nibbles fuera de 0-9).")
        digits.append(str(high))
        digits.append(str(low))
    return "".join(digits)


def decimal_to_bcd(text):
    """Convierte dígitos decimales a BCD (hex). Con n dígitos impares se rellena con F."""
    cleaned = clean_text(text)
    if not cleaned:
        raise ValueError("Entrada vacía.")
    if not cleaned.isdigit():
        raise ValueError("Entrada no válida: solo se permiten dígitos decimales (0-9).")
    if len(cleaned) % 2 != 0:
        cleaned = cleaned + "F"
    pairs = [cleaned[i:i + 2] for i in range(0, len(cleaned), 2)]
    out = []
    for p in pairs:
        if not all(ch in "0123456789F" for ch in p.upper()):
            raise ValueError("Entrada no válida para codificación BCD.")
        out.append(p.upper())
    return "".join(out)


def hex_to_decimal(text):
    """Interpreta una cadena hex como entero y devuelve su valor decimal."""
    cleaned = clean_text(text)
    if not is_hex(cleaned):
        raise ValueError("Entrada no válida: solo se permiten caracteres hexadecimales.")
    return str(int(cleaned, 16))


def decimal_to_hex(text):
    """Convierte un entero decimal a su representación hex."""
    cleaned = clean_text(text)
    if not cleaned or not cleaned.isdigit():
        raise ValueError("Entrada no válida: solo se permiten dígitos decimales.")
    value = int(cleaned)
    if value == 0:
        return "00"
    return format(value, "X")


def remove_spaces(text):
    """Elimina todos los espacios, tabulaciones y saltos de línea."""
    return clean_text(text)


def add_spaces(text):
    """Agrega un espacio cada dos caracteres (agrupación por byte)."""
    cleaned = clean_text(text)
    if not cleaned:
        return ""
    pairs = [cleaned[i:i + 2] for i in range(0, len(cleaned), 2)]
    return " ".join(pairs)
