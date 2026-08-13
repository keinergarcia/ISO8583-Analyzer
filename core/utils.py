# -*- coding: utf-8 -*-
"""Utilidades generales compartidas por el núcleo y la interfaz."""

import os
import sys
import unicodedata
from pathlib import Path

# ---------------------------------------------------------------------------
# Caracteres aceptados / descartables (fuente única de verdad para limpieza
# y validación). El validador y el limpiador comparten estas definiciones para
# no divergir: un carácter que clean_hex() va a eliminar NUNCA debe reportarse
# como error.
# ---------------------------------------------------------------------------

HEX_CHARS = "0123456789abcdefABCDEF"
HEX_SET = frozenset(HEX_CHARS)

# Separadores explícitos que se aceptan y se eliminan sin error.
SEPARATORS = " \t\n\r\v\f-:,.;|/"
SEPARATOR_SET = frozenset(SEPARATORS)

# Categorías Unicode de caracteres "invisibles" que el portapapeles, Word,
# PDF o un editor inyectan sin mostrarse: formato (Cf), espaciadores (Zs),
# controles (Cc) y separadores de línea/párrafo (Zl, Zp).
INVISIBLE_CATEGORIES = frozenset({"Cc", "Cf", "Zs", "Zl", "Zp"})

# Modo de diagnóstico temporal: si ISO8583_DIAGNOSTICS=1 (por defecto) se
# imprimen RAW/CLEAN/INVALID/HEX/POSICIÓN antes de rechazar una trama.
DIAGNOSTICS_DEFAULT = os.environ.get("ISO8583_DIAGNOSTICS", "1") not in ("0", "false", "no", "")


def is_invisible(ch):
    """True si el carácter es invisible/no imprimible (se elimina sin error)."""
    try:
        return unicodedata.category(ch) in INVISIBLE_CATEGORIES
    except TypeError:
        return False


def is_removable(ch):
    """True si el carácter es descartable: separador común o invisible."""
    return ch in SEPARATOR_SET or is_invisible(ch)


def clean_hex(text):
    """Elimina espacios, separadores y caracteres invisibles, conservando solo hex."""
    if text is None:
        return ""
    return "".join(ch for ch in str(text) if ch in HEX_SET)


def clean_frame(text):
    """Limpia una trama conservando caracteres visibles no hex.

    Elimina únicamente separadores y caracteres Unicode invisibles. Los
    caracteres visibles que no sean hexadecimales se conservan: pueden ser
    parte del VALOR de un Data Element (ASCII, JSON, XML, Base64, datos
    propietarios) y no deben rechazarse ni validarse como hex de la trama.
    """
    if text is None:
        return ""
    return "".join(ch for ch in str(text) if not is_removable(ch))


def is_hex_text(text):
    """True si la cadena es hexadecimal válido (par y con bytes.fromhex)."""
    if not text or len(text) % 2 != 0:
        return False
    try:
        bytes.fromhex(text)
        return True
    except (ValueError, TypeError):
        return False


def diagnostics_log_path():
    """Ruta del archivo de diagnóstico (junto al .exe cuando está empaquetado)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "ISO8583_Analyzer_diag.log"
    return Path.cwd() / "ISO8583_Analyzer_diag.log"


def report_diagnostics(raw_text, clean_text, bad_items):
    """Imprime y persiste el diagnóstico de una trama rechazada.

    bad_items: lista de tuplas (carácter, posición).
    """
    lines = ["=== DIAGNÓSTICO DE VALIDACIÓN ISO8583 ==="]
    lines.append(f"RAW: {raw_text!r}")
    lines.append(f"CLEAN: {clean_text!r}")
    lines.append("INVALID:")
    for ch, idx in bad_items:
        lines.append(f"  Carácter inválido: {ch!r}")
        lines.append(f"  Unicode: 0x{ord(ch):04X}")
        lines.append(f"  Posición: {idx}")
    msg = "\n".join(lines)
    try:
        print(msg)
    except Exception:
        pass
    try:
        with open(diagnostics_log_path(), "a", encoding="utf-8") as fh:
            fh.write(msg + "\n\n")
    except OSError:
        pass


def report_parse_debug(lines):
    """Imprime y persiste un diagnóstico de depuración del parseo.

    lines: lista de líneas de texto ya formateadas.
    """
    if not lines:
        return
    header = "=== DIAGNÓSTICO DE PARSEO ISO8583 (depuración) ==="
    if header not in lines:
        lines.insert(0, header)
    msg = "\n".join(lines)
    try:
        print(msg)
    except Exception:
        pass
    try:
        with open(diagnostics_log_path(), "a", encoding="utf-8") as fh:
            fh.write(msg + "\n\n")
    except OSError:
        pass


def validate_hex(text, diagnostics=None):
    """Valida una trama y devuelve (limpia, mensaje_error).

    Se aceptan dígitos hex (0-9, A-F, a-f) y cualquier carácter que
    clean_hex() vaya a eliminar: separadores comunes (espacio, tab, nueva
    línea, retorno de carro, guiones, dos puntos, coma, punto, etc.) y
    caracteres Unicode invisibles (ZWSP, BOM, NBSP, soft hyphen, marcas LTR/
    RTL...). Solo se reporta como error un carácter visible que no sea hex.
    """
    if text is None:
        return "", ""
    s = str(text)
    bad = [(ch, i) for i, ch in enumerate(s)
           if ch not in HEX_SET and not is_removable(ch)]
    if bad:
        if diagnostics is None:
            diagnostics = DIAGNOSTICS_DEFAULT
        if diagnostics:
            report_diagnostics(s, clean_hex(s), bad)
        shown = "".join(dict.fromkeys(ch for ch, _ in bad))[:20]
        return "", f"Caracteres no permitidos en la trama: {shown}"
    cleaned = clean_hex(s)
    if not cleaned:
        return "", "La trama está vacía."
    if len(cleaned) % 2 != 0:
        return "", "La trama debe tener un número par de caracteres hexadecimales."
    return cleaned, ""


def chunk_bytes(hex_str):
    """Agrupa la cadena hex en bytes separados por espacios."""
    pairs = [hex_str[i:i + 2] for i in range(0, len(hex_str), 2)]
    return " ".join(pairs)


def organize_hex(text, bytes_per_line=16):
    """Organiza visualmente una trama HEX continua en líneas de N bytes.

    Devuelve (organizado, mensaje_error). No analiza la trama ni la modifica:
    únicamente elimina espacios, tabs y saltos de línea, valida que el resto
    sea HEX válido y par, inserta saltos de línea cada ``bytes_per_line``
    bytes y comprueba que al quitar de nuevo los saltos el resultado sea
    exactamente igual a la trama normalizada original.
    """
    if text is None:
        return "", "La trama está vacía."
    s = str(text)
    cleaned = "".join(ch for ch in s if ch not in (" ", "\t", "\r", "\n"))
    if not cleaned:
        return "", "La trama está vacía."
    if any(ch not in HEX_SET for ch in cleaned):
        return "", "La trama contiene caracteres que no son hexadecimales válidos."
    if len(cleaned) % 2 != 0:
        return "", "La trama debe tener un número par de caracteres hexadecimales."
    per_line = max(1, int(bytes_per_line)) * 2
    lines = [cleaned[i:i + per_line] for i in range(0, len(cleaned), per_line)]
    organized = "\n".join(lines)
    if organized.replace("\n", "").replace("\r", "") != cleaned:
        return "", "La verificación de integridad falló: no se modificó el contenido."
    return organized, ""
