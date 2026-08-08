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


def hex_to_binary(text):
    """Convierte una cadena hex en bits binarios (8 bits por byte).

    'FF'   -> '11111111'
    '0064' -> '00000000 01100100'
    Mantiene el orden de los bytes.
    """
    cleaned = clean_text(text)
    if not is_hex(cleaned):
        raise ValueError("Entrada no válida: solo se permiten caracteres hexadecimales.")
    if len(cleaned) % 2 != 0:
        raise ValueError("HEX inválido: la cantidad de caracteres debe ser par.")
    return " ".join(f"{b:08b}" for b in bytes.fromhex(cleaned))


def binary_to_hex(text):
    """Convierte una cadena de bits (0/1) en su representación hex.

    '11111111'          -> 'FF'
    '00000000 01100100' -> '0064'
    Cada byte debe tener exactamente 8 bits.
    """
    if text is None:
        raise ValueError("Entrada vacía.")
    cleaned = "".join(ch for ch in str(text) if ch not in (" ", "\t", "\n", "\r", "-", "_"))
    if not cleaned:
        raise ValueError("Entrada vacía.")
    if not all(ch in "01" for ch in cleaned):
        raise ValueError("Entrada no válida: solo se permiten dígitos binarios (0 y 1).")
    if len(cleaned) % 8 != 0:
        raise ValueError("BINARIO inválido: la cantidad de bits debe ser múltiplo de 8.")
    return "".join(f"{int(cleaned[i:i + 8], 2):02X}" for i in range(0, len(cleaned), 8))


def decimal_to_binary(text):
    """Convierte un entero decimal a su representación binaria.

    '255' -> '11111111'
    '256' -> '100000000'
    """
    cleaned = clean_text(text)
    if not cleaned or not cleaned.isdigit():
        raise ValueError("Entrada no válida: solo se permiten dígitos decimales.")
    value = int(cleaned)
    if value == 0:
        return "0"
    return format(value, "b")


def binary_to_decimal(text):
    """Convierte una cadena de bits (0/1) en su valor decimal.

    '11111111' -> '255'
    """
    if text is None:
        raise ValueError("Entrada vacía.")
    cleaned = "".join(ch for ch in str(text) if ch not in (" ", "\t", "\n", "\r", "-", "_"))
    if not cleaned:
        raise ValueError("Entrada vacía.")
    if not all(ch in "01" for ch in cleaned):
        raise ValueError("Entrada no válida: solo se permiten dígitos binarios (0 y 1).")
    return str(int(cleaned, 2))


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
