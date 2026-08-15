# -*- coding: utf-8 -*-
"""Analizador principal de mensajes ISO 8583.

Soporta tramas en modo BCD (empacado, estándar en redes de pago) y modo
ASCII (cada carácter se transmite como un byte). La codificación numérica
se detecta automáticamente o puede forzarse mediante ParseOptions.

El inicio del mensaje ISO 8583 (MTI) NO se asume fijo en "2 bytes longitud +
5 bytes TPDU". Puede configurarse manualmente (mti_offset) o detectarse de
forma automática: se escanea la trama buscando un MTI válido seguido de un
bitmap válido y un conjunto de campos que quepan dentro de la trama.
"""

import gzip
from dataclasses import dataclass, field
from typing import List, Optional

from .bitmap import has_secondary_bitmap, parse_bitmap
from .fields import DATA_ELEMENTS
from .mti import KNOWN_MTIS, MtiInfo, decode_mti
from .tpdu import TpduInfo, decode_tpdu
from .utils import (
    HEX_SET,
    clean_frame,
    is_hex_text,
    is_removable,
    report_parse_debug,
)


class ParseError(Exception):
    """Error de validación al analizar una trama."""


@dataclass
class ParseOptions:
    has_tpdu: bool = True
    tpdu_length_bytes: int = 5
    numeric_encoding: str = "auto"  # auto | bcd | ascii | hybrid
    mti_offset: Optional[int] = None  # bytes antes del MTI (None = automático)
    mti_auto: bool = True             # permitir detección automática del MTI
    debug: bool = False               # imprimir diagnóstico de parseo
    llvar_prefix_bytes: int = 1       # bytes para prefijo LLVAR en BCD (1=estándar, 2=algunas redes)
    lllvar_prefix_bytes: int = 2      # bytes para prefijo LLLVAR en BCD (2=estándar, 3=algunas redes)
    lllvar_4digit_bcd: bool = False   # prefijo LLLVAR de 2 bytes como BCD completo de 4 dígitos (no 3)
    bcd_padding: str = "trailing"     # "trailing"=nibble de relleno al final | "leading"=nibble de relleno al inicio
    field_defs: Optional[dict] = None  # definiciones de campos del perfil (None = diccionario embebido)


@dataclass
class ParsedField:
    number: int
    name: str
    description: str
    ftype: str
    length_type: str
    max_length: int
    length_digits: int
    value: str
    raw_hex: str
    offset_hex: int
    has_error: bool = False
    error: str = ""
    emv: Optional[list] = None
    note: str = ""

    def as_dict(self):
        return {
            "number": self.number,
            "name": self.name,
            "description": self.description,
            "ftype": self.ftype,
            "length_type": self.length_type,
            "max_length": self.max_length,
            "length_digits": self.length_digits,
            "value": self.value,
            "raw_hex": self.raw_hex,
            "offset_hex": self.offset_hex,
            "has_error": self.has_error,
            "error": self.error,
            "emv": self.emv,
            "note": self.note,
        }


@dataclass
class TrailingPayload:
    """Payload propietario detectado tras el último campo del bitmap.

    Representa una extensión encapsulada (p. ej. GZIP tras DE64) en lugar de
    reportar los bytes como "sin analizar". La detección es conservadora:

    - "confirmed": magic GZIP en el byte 2 del campo, el prefijo de longitud
      coincide exactamente con los bytes disponibles y la descompresión OK.
    - "possible": hay indicios (magic GZIP / prefijo) pero la longitud no
      coincide o la descompresión falla; se conserva la advertencia original.
    """

    kind: str                 # "gzip" | "possible_gzip"
    declared_length: int      # bytes declarados por el prefijo de longitud
    available_length: int     # bytes realmente disponibles para el payload
    payload_hex: str          # hex del payload (desde el fin del prefijo)
    offset_hex: int           # offset hex en la trama donde inicia el payload
    status: str               # "confirmed" | "possible"
    reason: str = ""          # motivo cuando no se pudo confirmar
    decompressed_length: Optional[int] = None
    preview: str = ""

    def as_dict(self):
        return {
            "kind": self.kind,
            "declared_length": self.declared_length,
            "available_length": self.available_length,
            "payload_hex": self.payload_hex,
            "offset_hex": self.offset_hex,
            "status": self.status,
            "reason": self.reason,
            "decompressed_length": self.decompressed_length,
            "preview": self.preview,
        }


@dataclass
class AnalysisResult:
    raw_clean: str
    length_hex: str
    length_value: int
    tpdu: Optional[TpduInfo]
    mti: Optional[MtiInfo]
    bitmap_primary_hex: str
    bitmap_secondary_hex: str
    active_fields: List[int]
    fields: List[ParsedField]
    warnings: List[str]
    errors: List[str]
    emv: Optional[list]
    numeric_encoding: str
    consumed_hex: int
    declared_hex: int
    stats: dict = field(default_factory=dict)
    mti_offset_bytes: Optional[int] = None
    header_hex: str = ""
    trailing_payload: Optional[TrailingPayload] = None

    def as_dict(self):
        return {
            "raw_clean": self.raw_clean,
            "length_hex": self.length_hex,
            "length_value": self.length_value,
            "tpdu": self.tpdu.as_dict() if self.tpdu else None,
            "mti": self.mti.as_dict() if self.mti else None,
            "bitmap_primary_hex": self.bitmap_primary_hex,
            "bitmap_secondary_hex": self.bitmap_secondary_hex,
            "active_fields": self.active_fields,
            "fields": [f.as_dict() for f in self.fields],
            "warnings": self.warnings,
            "errors": self.errors,
            "emv": [n.as_dict() for n in self.emv] if self.emv else None,
            "numeric_encoding": self.numeric_encoding,
            "consumed_hex": self.consumed_hex,
            "declared_hex": self.declared_hex,
            "stats": self.stats,
            "mti_offset_bytes": self.mti_offset_bytes,
            "header_hex": self.header_hex,
            "trailing_payload": self.trailing_payload.as_dict()
            if self.trailing_payload else None,
        }


# ---------------------------------------------------------------------------
# Detección de codificación
# ---------------------------------------------------------------------------

def _looks_hybrid(hex_str, opts):
    """Detecta formato híbrido: cabeceras binarias + campos de datos ASCII.

    Se leen las cabeceras (longitud, TPDU, MTI, bitmaps) en modo binario. Si
    los bytes que quedan tras el último bitmap son casi todos imprimibles, la
    trama es híbrida (cabeceras binarias + datos en ASCII), muy común en
    redes reales de pago.
    """
    errors = []
    try:
        headers = _parse_headers(hex_str, opts, errors, encoding="hybrid")
    except Exception:
        return False
    if errors:
        return False
    data_hex = hex_str[headers["pos"]:]
    if len(data_hex) < 4:
        return False
    try:
        raw = bytes.fromhex(data_hex)
    except (ValueError, TypeError):
        return False
    printable = sum(1 for b in raw if 0x20 <= b <= 0x7E)
    return printable / len(raw) >= 0.98


def _detect_encoding(hex_str, opts=None):
    """Detecta la codificación de la trama.

    - ASCII si el 98% o más de los bytes son imprimibles.
    - Híbrido (cabeceras binarias + datos ASCII) si no es ASCII puro pero la
      parte de datos tras el bitmap es casi toda imprimible.
    - BCD en cualquier otro caso.
    """
    try:
        raw = bytes.fromhex(hex_str)
    except (ValueError, TypeError):
        return "bcd"
    if not raw:
        return "bcd"
    printable = sum(1 for b in raw if 0x20 <= b <= 0x7E)
    if printable / len(raw) >= 0.98:
        return "ascii"
    if _looks_hybrid(hex_str, opts or ParseOptions()):
        return "hybrid"
    return "bcd"


# ---------------------------------------------------------------------------
# Lectura de campos
# ---------------------------------------------------------------------------

def _bcd_len_value(seg, length_type="llvar", lllvar_4digit=False):
    """Interpreta un prefijo de longitud BCD como decimal.

    - llvar: 2 hex chars (1 byte) o 4 hex chars (2 bytes)
    - lllvar: 4 hex chars (2 bytes, 3 nibbles) o 6 hex chars (3 bytes)
      Si lllvar_4digit es True, el prefijo lllvar de 2 bytes se interpreta
      como BCD completo de 4 dígitos (formato usado por algunas redes).
    """
    if not seg:
        return 0
    # Si todos son dígitos decimales, interpretar como decimal directo
    if all(c in "0123456789" for c in seg):
        if length_type == "llvar" and len(seg) == 4:
            return int(seg, 10)  # 2 bytes BCD = 4 dígitos
        if length_type == "lllvar" and len(seg) == 6:
            return int(seg, 10)  # 3 bytes BCD = 6 dígitos
        if length_type == "llvar" and len(seg) == 2:
            return int(seg, 10)  # 1 byte BCD = 2 dígitos
        if length_type == "lllvar" and len(seg) == 4:
            if lllvar_4digit:
                return int(seg, 10)  # 2 bytes BCD = 4 dígitos completos
            return int(seg[:3], 10)  # 2 bytes BCD, usar 3 nibbles
    # Fallback: interpretar como hex
    try:
        if length_type == "lllvar" and len(seg) == 4:
            if seg[3] == "F":
                return int(seg[:3], 10)  # 3 dígitos BCD + nibble de relleno F
            if lllvar_4digit:
                return int(seg, 16)
            return int(seg[:3], 16)
        return int(seg, 16)
    except ValueError:
        return 0


def _read_len_digits_bcd(h, pos, length_type, debug=None, llvar_bytes=1, lllvar_bytes=2,
                         lllvar_4digit=False):
    if debug is None:
        debug = []
    start = pos
    if length_type == "llvar":
        hex_chars = llvar_bytes * 2
        seg = h[pos:pos + hex_chars]
        if len(seg) < hex_chars:
            raise ParseError("Prefijo de longitud (LLVAR) incompleto.")
        value = _bcd_len_value(seg, "llvar")
        npos = pos + hex_chars
    else:
        hex_chars = lllvar_bytes * 2
        seg = h[pos:pos + hex_chars]
        if len(seg) < hex_chars:
            raise ParseError("Prefijo de longitud (LLLVAR) incompleto.")
        value = _bcd_len_value(seg, "lllvar", lllvar_4digit=lllvar_4digit)
        npos = pos + hex_chars
    debug.append(
        f"    Longitud BCD {length_type}: offset inicial byte {start // 2} (hex {start}), "
        f"bytes usados '{seg}' ({hex_chars//2} bytes), longitud interpretada {value}, "
        f"offset final byte {npos // 2} (hex {npos})"
    )
    return value, npos


def _read_len_digits_ascii(h, pos, length_type, debug=None):
    if debug is None:
        debug = []
    start = pos
    nd = {"llvar": 2, "lllvar": 3, "llllvar": 4}[length_type]
    take = nd * 2
    seg = h[pos:pos + take]
    if len(seg) < take:
        raise ParseError("Prefijo de longitud (ASCII) incompleto.")
    text = bytes.fromhex(seg).decode("ascii", errors="replace")
    if not text.isdigit():
        raise ParseError("Prefijo de longitud inválido (no numérico).")
    value = int(text)
    npos = pos + take
    debug.append(
        f"    Longitud ASCII {length_type}: offset inicial byte {start // 2} (hex {start}), "
        f"bytes usados '{seg}', longitud interpretada {value}, offset final byte {npos // 2} (hex {npos})"
    )
    return value, npos


def _bcd_to_digits(raw_hex, digits, padding="trailing"):
    """Convierte un campo numérico BCD a su valor (hex de dígitos).

    La posición del nibble de relleno en campos de dígitos impares depende de
    la red: con padding "trailing" el valor ocupa los nibbles más
    significativos y el nibble final es relleno (se descarta); con padding
    "leading" el valor va alineado a la derecha y el primer nibble es relleno
    (se descarta). El relleno NO forma parte del valor en ninguno de los dos
    casos. El padding es una propiedad del perfil/encoding, no una suposición
    universal del estándar.
    """
    s = raw_hex.upper()
    if digits % 2 == 1 and s:
        if padding == "leading":
            # Valor alineado a la derecha: el primer nibble es relleno.
            s = s[1:]
        else:
            # Valor alineado a la izquierda: el último nibble es relleno.
            s = s[:-1]
    return s


def _z_to_track2(raw_hex):
    """Decodifica Track 2 (z) empacado en BCD: cada nibble es un carácter.

    Los dígitos se conservan, 'D' es el separador '=' y 'F' es el nibble de
    relleno final, que se descarta (no forma parte del valor). No aplica
    ningún cambio de padding: el relleno de Track 2 siempre es 'F' final.
    """
    out = []
    for c in (raw_hex or "").upper():
        if c == "D":
            out.append("=")
        elif c == "F":
            continue
        else:
            out.append(c)
    return "".join(out)


def _hex_to_text(raw_hex, ftype):
    if ftype == "b":
        return raw_hex.upper()
    try:
        raw = bytes.fromhex(raw_hex)
    except ValueError:
        return raw_hex
    return "".join(chr(b) if 0x20 <= b <= 0x7E else "." for b in raw)


def _take_bytes(h, pos, nbytes):
    """Toma `nbytes` bytes de la trama.

    En una trama hexadecimal, cada byte son 2 caracteres. Si el segmento no es
    hex válido (p. ej. porque el DE contiene texto/JSON/XML/Base64 literal),
    se leen `nbytes` caracteres literales y se devuelven hex-encodificados.
    Devuelve (raw_hex, nueva_pos).
    """
    seg = h[pos:pos + nbytes * 2]
    if len(seg) == nbytes * 2 and is_hex_text(seg):
        return seg.upper(), pos + nbytes * 2
    # Fallback literal: 1 carácter = 1 byte (valor del DE, no hex de trama).
    seg = h[pos:pos + nbytes]
    if len(seg) < nbytes:
        raise ParseError(
            f"Datos del campo incompletos: se declararon {nbytes} bytes y hay {len(seg)}."
        )
    return seg.encode("utf-8").hex().upper(), pos + nbytes


def _read_field_bcd(h, pos, fdef, issues, debug=None, llvar_bytes=1, lllvar_bytes=2,
                    lllvar_4digit=False, padding="trailing"):
    start = pos
    if fdef.length_type == "fixed":
        if fdef.is_numeric:
            digits = fdef.length
            nbytes = (digits + 1) // 2
        elif fdef.ftype == "z":
            # Track 2 fijo (nibbles por carácter).
            digits = fdef.length
            nbytes = (digits + 1) // 2
        else:
            nbytes = fdef.length
            digits = fdef.length
        raw, pos = _take_bytes(h, pos, nbytes)
        if fdef.is_numeric:
            value = _bcd_to_digits(raw, digits, padding)
        elif fdef.ftype == "z":
            value = _z_to_track2(raw)
        else:
            value = _hex_to_text(raw, fdef.ftype)
        return _build_field(fdef, digits, value, raw, start), pos
    length_digits, pos = _read_len_digits_bcd(h, pos, fdef.length_type, debug,
                                               llvar_bytes=llvar_bytes, lllvar_bytes=lllvar_bytes,
                                               lllvar_4digit=lllvar_4digit)
    return _read_field_data(h, pos, fdef, length_digits, issues, start, padding)


def _read_field_ascii(h, pos, fdef, issues, debug=None):
    start = pos
    if fdef.length_type == "fixed":
        if fdef.is_numeric:
            digits = fdef.length
            nbytes = digits
        else:
            nbytes = fdef.length
            digits = fdef.length
        raw, pos = _take_bytes(h, pos, nbytes)
        if fdef.is_numeric:
            value = bytes.fromhex(raw).decode("ascii", errors="replace")
        else:
            value = _hex_to_text(raw, fdef.ftype)
        return _build_field(fdef, digits, value, raw, start), pos
    length_digits, pos = _read_len_digits_ascii(h, pos, fdef.length_type, debug)
    return _read_field_data_ascii(h, pos, fdef, length_digits, issues, start)


def _read_field_data(h, pos, fdef, length_digits, issues, start, padding="trailing"):
    if length_digits > fdef.length:
        issues.append(
            f"DE{fdef.number}: la longitud del campo ({length_digits}) supera el máximo ({fdef.length})."
        )
    if fdef.is_numeric:
        nbytes = (length_digits + 1) // 2
    elif fdef.ftype == "z":
        # Track 2 (z) va empacado en BCD: cada nibble es un carácter, con un
        # nibble de relleno 'F' final para longitudes impares.
        nbytes = (length_digits + 1) // 2
    else:
        nbytes = length_digits
    raw, pos = _take_bytes(h, pos, nbytes)
    if fdef.is_numeric:
        value = _bcd_to_digits(raw, length_digits, padding)
    elif fdef.ftype == "z":
        value = _z_to_track2(raw)
    else:
        value = _hex_to_text(raw, fdef.ftype)
    return _build_field(fdef, length_digits, value, raw, start), pos


def _read_field_data_ascii(h, pos, fdef, length_digits, issues, start):
    """Igual que _read_field_data pero en modo ASCII: un byte por dígito."""
    if length_digits > fdef.length:
        issues.append(
            f"DE{fdef.number}: la longitud del campo ({length_digits}) supera el máximo ({fdef.length})."
        )
    nbytes = length_digits
    raw, pos = _take_bytes(h, pos, nbytes)
    if fdef.is_numeric:
        value = bytes.fromhex(raw).decode("ascii", errors="replace")
    else:
        value = _hex_to_text(raw, fdef.ftype)
    return _build_field(fdef, length_digits, value, raw, start), pos


def _gzip_note(raw_hex):
    """Detecta una cabecera GZIP (1F 8B 08) dentro de un campo.

    No altera el parseo: solo anota que el contenido es binario comprimido.
    Si la cabecera aparece en el byte 2 y los 2 bytes previos son un prefijo
    de longitud (patrón habitual: LONGITUD + stream gzip), se indica cuántos
    bytes de payload comprimido continúan tras el campo.
    """
    up = (raw_hex or "").upper()
    idx = up.find("1F8B08")
    if idx < 0:
        return ""
    byte_pos = idx // 2
    parts = [f"Cabecera GZIP (1F 8B 08) en el byte {byte_pos} de este campo"]
    if byte_pos == 2 and len(up) >= 4:
        try:
            plen = int(up[:4], 16)
            parts.append(
                f"los 2 primeros bytes son un prefijo de longitud: "
                f"payload comprimido de {plen} bytes que continúa tras este campo "
                f"(estructura propietaria detectada)"
            )
        except ValueError:
            pass
    return " · ".join(parts) + "."


def _build_field(fdef, length_digits, value, raw, start):
    f = ParsedField(
        number=fdef.number,
        name=fdef.name,
        description=fdef.description,
        ftype=fdef.ftype,
        length_type=fdef.length_type,
        max_length=fdef.length,
        length_digits=length_digits,
        value=value,
        raw_hex=raw.upper(),
        offset_hex=start,
    )
    note = _gzip_note(raw.upper())
    if note:
        f.note = note
    return f


# ---------------------------------------------------------------------------
# Detección del inicio del mensaje (MTI)
# ---------------------------------------------------------------------------

def _default_offset(opts):
    """Offset por defecto: 2 bytes de longitud + TPDU (si la hay)."""
    return 2 + (opts.tpdu_length_bytes if opts.has_tpdu else 0)


def _find_mti_offset(clean, opts, encoding="bcd"):
    """Resuelve el offset (en bytes) donde comienza el MTI.

    Prioridad:
    1. Si opts.mti_offset está definido (modo manual), se usa tal cual.
    2. Si opts.mti_auto está activo, se escanea la trama buscando un MTI
       válido seguido de un bitmap válido y campos que quepan.
    3. En caso contrario se usa el layout clásico (2 + TPDU).
    """
    if opts.mti_offset is not None:
        return opts.mti_offset
    if not opts.mti_auto:
        return _default_offset(opts)
    total_bytes = len(clean) // 2
    max_scan = min(24, max(0, total_bytes - 4))
    best, best_score = None, -1
    for off in range(0, max_scan + 1):
        score, ok = _score_offset(clean, off, opts, encoding)
        if ok and score > best_score:
            best, best_score = off, score
    return best if best is not None else _default_offset(opts)


def _score_offset(clean, off, opts, encoding):
    """Puntúa un offset candidato (bytes antes del MTI). Devuelve (score, ok)."""
    try:
        headers = _headers_at(clean, off, opts)
    except (ParseError, ValueError):
        return 0, False

    mti_hex = clean[off * 2:off * 2 + 4]
    if len(mti_hex) != 4 or not is_hex_text(mti_hex) or mti_hex not in KNOWN_MTIS:
        return 0, False

    score = 100
    primary = headers["primary"]
    if len(primary) == 16 and is_hex_text(primary):
        score += 50
        if primary != "0" * 16:
            score += 10
        if headers["secondary"]:
            score += 10
    if headers["declared_hex"]:
        approx = (len(clean) - 4)
        if abs(headers["declared_hex"] - approx) <= 4:
            score += 30
    if off == _default_offset(opts):
        score += 20

    issues, errors = [], []
    fields, pos, active = _read_fields_hex(clean, headers, encoding, issues, errors,
                                           llvar_bytes=opts.llvar_prefix_bytes,
                                           lllvar_bytes=opts.lllvar_prefix_bytes,
                                           field_defs=opts.field_defs,
                                           lllvar_4digit=opts.lllvar_4digit_bcd,
                                           padding=opts.bcd_padding)
    if any(f.has_error for f in fields):
        score -= 20
    else:
        score += 40
    score += len(fields) * 2
    return score, True


def _headers_at(clean, off, opts, errors=None, debug=None):
    """Construye los encabezados asumiendo que el MTI está en el byte `off`.

    El offset `off` es el número de BYTES que hay antes del MTI. La región
    completa clean[0:off*2] es la cabecera pre-MTI (longitud + TPDU + header
    propietario). No se asume un layout fijo: se descompone por heurística.
    """
    if errors is None:
        errors = []
    if debug is None:
        debug = []
    total_hex = len(clean)
    mti_hex_start = off * 2

    # --- Longitud (campo binario de 2 bytes al inicio, si hay espacio) ---
    length_hex = ""
    length_value = 0
    declared_hex = 0
    if off >= 2 and total_hex >= 4:
        cand = clean[0:4]
        if is_hex_text(cand):
            length_hex = cand
            length_value = int(length_hex, 16)
            declared_hex = length_value * 2

    # --- TPDU (5 bytes justo después del campo de longitud, si hay espacio) ---
    tpdu = None
    tpdu_hex = ""
    if opts.has_tpdu and off >= 2 + opts.tpdu_length_bytes and total_hex >= (2 + opts.tpdu_length_bytes) * 2:
        cand = clean[4:(2 + opts.tpdu_length_bytes) * 2]
        if is_hex_text(cand):
            tpdu_hex = cand
            tpdu = decode_tpdu(tpdu_hex)

    header_hex = clean[0:mti_hex_start]

    # --- MTI ---
    mti = None
    mti_hex = clean[mti_hex_start:mti_hex_start + 4]
    if len(mti_hex) == 4 and is_hex_text(mti_hex):
        mti = decode_mti(mti_hex)
    else:
        errors.append("MTI no localizado en la posición esperada.")

    # --- Bitmaps ---
    primary = clean[mti_hex_start + 4:mti_hex_start + 20]
    if len(primary) < 16 or not is_hex_text(primary):
        errors.append(
            f"Bitmap primario inválido: se esperaban 8 bytes (16 hex) y hay {len(primary) // 2}."
        )
        primary = primary.ljust(16, "0")
    secondary = ""
    if has_secondary_bitmap(primary):
        secondary = clean[mti_hex_start + 20:mti_hex_start + 36]
        if len(secondary) < 16 or not is_hex_text(secondary):
            errors.append(
                "Bitmap secundario inválido: el bit 1 está activo pero faltan 8 bytes."
            )
            secondary = secondary.ljust(16, "0")

    pos = mti_hex_start + 4 + 16 + len(secondary)

    if debug is not None:
        debug.append(f"Modo offset MTI: {'Manual' if opts.mti_offset is not None else 'Automático'}")
        debug.append(f"Offset inicial usado (bytes antes del MTI): {off}")
        if length_hex:
            debug.append(f"Longitud: {length_hex} ({length_value} bytes)")
        else:
            debug.append("Longitud: (no detectada)")
        if header_hex:
            debug.append(f"Header pre-MTI: {header_hex} ({off} bytes)")
        if tpdu_hex:
            debug.append(f"TPDU: {tpdu_hex} (destino={tpdu.destination} origen={tpdu.source} control={tpdu.control})")
        debug.append(f"MTI encontrado: {mti_hex} (offset byte {off})")
        debug.append(f"Bitmap encontrado: {primary} (offset byte {off + 2})")
        if secondary:
            debug.append(f"Bitmap secundario: {secondary} (offset byte {off + 2 + 8})")
        debug.append(f"DE2 comienza en: byte {off + 2 + len(primary) // 2 + len(secondary) // 2} "
                     f"(posición hex {pos})")

    return {
        "length_hex": length_hex,
        "length_value": length_value,
        "declared_hex": declared_hex,
        "mti_offset": off,
        "header_hex": header_hex,
        "tpdu_hex": tpdu_hex,
        "tpdu": tpdu,
        "mti": mti,
        "primary": primary,
        "secondary": secondary,
        "pos": pos,
        "data_start_hex": 4 if length_hex else 0,
    }


def _parse_headers(clean, opts, errors, encoding="bcd"):
    """Resuelve el offset del MTI y construye los encabezados."""
    off = _find_mti_offset(clean, opts, encoding)
    debug = []
    headers = _headers_at(clean, off, opts, errors, debug)
    mti_hex = clean[off * 2:off * 2 + 4]
    if len(mti_hex) != 4 or not is_hex_text(mti_hex):
        bad = "".join(
            dict.fromkeys(ch for ch in clean if ch not in HEX_SET and not is_removable(ch))
        )[:20]
        if bad:
            raise ParseError(f"Caracteres no permitidos en la trama: {bad}")
        raise ParseError("No se pudo localizar un MTI válido en la trama.")
    headers["debug"] = debug
    return headers


# ---------------------------------------------------------------------------
# Lectura de campos según el bitmap
# ---------------------------------------------------------------------------

def _read_fields_hex(clean, headers, encoding, issues, errors, debug=None,
                     llvar_bytes=1, lllvar_bytes=2, field_defs=None, lllvar_4digit=False,
                     padding="trailing"):
    """Lee todos los campos activos. Devuelve (fields, pos, active)."""
    pos = headers["pos"]
    if debug is None:
        debug = []
    combined = headers["primary"] + headers["secondary"]
    active = parse_bitmap(combined)

    fields: List[ParsedField] = []
    for number in active:
        if number == 1:
            continue
        fdef = field_defs.get(number) if field_defs else DATA_ELEMENTS.get(number)
        if fdef is None:
            fields.append(
                ParsedField(
                    number=number,
                    name="Desconocido",
                    description="Reservado sin definición",
                    ftype="an",
                    length_type="lllvar",
                    max_length=999,
                    length_digits=0,
                    value="",
                    raw_hex="",
                    offset_hex=pos,
                    has_error=True,
                    error="Definición de campo no encontrada en el diccionario.",
                )
            )
            continue
        field_start = pos
        try:
            field_encoding = fdef.encoding or encoding
            if field_encoding in ("ascii", "hybrid"):
                field, pos = _read_field_ascii(clean, pos, fdef, issues)
            else:
                field, pos = _read_field_bcd(clean, pos, fdef, issues,
                                             llvar_bytes=llvar_bytes, lllvar_bytes=lllvar_bytes,
                                             lllvar_4digit=lllvar_4digit, padding=padding)
            fields.append(field)
        except ParseError as exc:
            fields.append(
                ParsedField(
                    number=number,
                    name=fdef.name,
                    description=fdef.description,
                    ftype=fdef.ftype,
                    length_type=fdef.length_type,
                    max_length=fdef.length,
                    length_digits=0,
                    value="",
                    raw_hex="",
                    offset_hex=pos,
                    has_error=True,
                    error=str(exc),
                )
            )
            break
        if debug is not None:
            consumed_bytes = (pos - field_start) // 2
            remaining_bytes = (len(clean) - pos) // 2
            if fdef.length_type == "fixed":
                prefix_bytes = 0
            elif field_encoding in ("ascii", "hybrid"):
                prefix_bytes = {"llvar": 2, "lllvar": 3, "llllvar": 4}[fdef.length_type]
            else:
                prefix_bytes = llvar_bytes if fdef.length_type == "llvar" else lllvar_bytes
            debug.append(
                f"DE{number}: offset inicial byte {field_start // 2} (hex {field_start}), "
                f"offset final byte {pos // 2} (hex {pos}), "
                f"longitud del prefijo {prefix_bytes} byte(s), "
                f"longitud interpretada {field.length_digits}, "
                f"bytes consumidos {consumed_bytes}, "
                f"bytes restantes {remaining_bytes}"
            )
            if field.note:
                debug.append(f"  DE{number} nota: {field.note}")
    return fields, pos, active


# ---------------------------------------------------------------------------
# Detección de payload propietario tras el último campo (p. ej. GZIP tras DE64)
# ---------------------------------------------------------------------------

GZIP_MAGIC = "1F8B08"
GZIP_MAGIC_BYTES = 3


def _detect_trailing_payload(clean, fields, data_start_hex, consumed_hex):
    """Detecta un payload encapsulado que continúa tras el último campo.

    Solo aplica cuando el último campo parseado es DE64 (binario fixed de
    8 bytes, sin error) y dentro de él aparece la estructura:

        [2 bytes prefijo de longitud big-endian] [1F 8B 08 ... GZIP]

    El payload declarado por el prefijo comienza en el byte 2 del campo
    (offset_hex = campo.offset_hex + 4). Devuelve un TrailingPayload en
    estados "confirmed" (magic + longitud exacta + descompresión OK) o
    "possible" (indicios presentes pero sin verificación concluyente), o None
    si no hay evidencia. NUNCA consume bytes: solo describe lo que ya hay.
    """
    total_hex = len(clean)
    remaining_hex = total_hex - data_start_hex - consumed_hex
    if remaining_hex <= 0 or not fields:
        return None
    last = fields[-1]
    if last.has_error or last.number != 64:
        return None
    if last.length_type != "fixed" or len(last.raw_hex) != 16:
        return None

    raw = last.raw_hex.upper()
    if raw[4:4 + len(GZIP_MAGIC)] != GZIP_MAGIC:
        return None
    try:
        plen = int(raw[0:4], 16)
    except ValueError:
        return None
    if plen <= 0:
        return None

    remaining_bytes = remaining_hex // 2
    payload_hex = raw[4:] + clean[total_hex - remaining_hex:]
    available = (8 - 2) + remaining_bytes
    offset_hex = last.offset_hex + 4

    declared_hex_len = plen * 2
    attempt = payload_hex[:declared_hex_len] if plen <= available else payload_hex
    decompressed_length = None
    preview = ""
    decompress_error = ""
    try:
        out = gzip.decompress(bytes.fromhex(attempt))
        decompressed_length = len(out)
        preview = "".join(
            chr(b) if 0x20 <= b <= 0x7E else "." for b in out[:160]
        )
    except Exception as exc:  # BadGzipFile / EOFError / zlib.error
        decompress_error = str(exc) or type(exc).__name__

    if decompressed_length is not None and plen == available:
        status, kind = "confirmed", "gzip"
        reason = ""
    else:
        status, kind = "possible", "possible_gzip"
        if decompressed_length is None:
            reason = (f"el prefijo declara {plen} bytes y hay {available} "
                      f"disponibles; el stream GZIP no pudo descomprimirse"
                      + (f" ({decompress_error})" if decompress_error else "") + ".")
        else:
            reason = (f"el prefijo declara {plen} bytes pero solo hay {available} "
                      f"disponibles.")
    return TrailingPayload(
        kind=kind,
        declared_length=plen,
        available_length=available,
        payload_hex=payload_hex,
        offset_hex=offset_hex,
        status=status,
        reason=reason,
        decompressed_length=decompressed_length,
        preview=preview,
    )


def _assemble(clean, encoding, headers, fields, issues, consumed_hex, mti_offset):
    warnings = list(issues)
    errors = []
    primary = headers["primary"]
    secondary = headers["secondary"]
    combined = primary + secondary
    active = parse_bitmap(combined)

    declared = headers["declared_hex"]
    remaining = len(clean) - headers["data_start_hex"] - consumed_hex
    payload = _detect_trailing_payload(clean, fields, headers["data_start_hex"],
                                       consumed_hex)

    if payload is not None and payload.status == "confirmed":
        # Payload propietario detectado y validado: los bytes posteriores al
        # último campo quedan explicados. Se reemplaza el aviso genérico de
        # "bytes sin analizar" por una descripción exacta y verificada.
        total_after_start = len(clean) - headers["data_start_hex"]
        if declared and consumed_hex != declared and total_after_start != declared:
            warnings.append(
                f"Longitud declarada ({headers['length_value']} bytes = {declared} hex) "
                f"no coincide con el contenido de la trama "
                f"({total_after_start // 2} bytes = {total_after_start} hex)."
            )
        warnings.append(
            f"Se detectó un payload propietario encapsulado tras DE64: prefijo de "
            f"longitud 0x{payload.declared_length:04X} = {payload.declared_length} bytes "
            f"y stream GZIP ({GZIP_MAGIC}) desde el byte 2 del campo. El payload de "
            f"{payload.declared_length} bytes (6 dentro del campo + "
            f"{remaining // 2} posteriores) fue descomprimido correctamente "
            f"({payload.decompressed_length} bytes). Todos los bytes de la trama "
            f"quedan explicados."
        )
    else:
        if declared and consumed_hex != declared:
            warnings.append(
                f"Longitud declarada ({headers['length_value']} bytes = {declared} hex) "
                f"no coincide con el contenido analizado ({consumed_hex // 2} bytes = {consumed_hex} hex)."
            )
        if remaining > 0:
            warnings.append(
                f"Hay {remaining // 2} bytes de datos sin analizar después del último campo."
            )
        if payload is not None:
            warnings.append(
                f"Posible payload propietario después de DE64 "
                f"(prefijo {payload.declared_length} bytes + cabecera {GZIP_MAGIC}), "
                f"pero no puede confirmarse: {payload.reason}"
            )

    emv = None
    for f in fields:
        if f.number == 55 and not f.has_error and f.value:
            try:
                from .emv import parse_tlv
                emv = parse_tlv(f.value)
                f.emv = [n.as_dict() for n in emv]
            except (ValueError, IndexError) as exc:
                warnings.append(f"No se pudo decodificar el EMV del campo 55: {exc}")

    data_bytes = sum(_byte_len(f, encoding) for f in fields)
    stats = {
        "total_fields": len(fields),
        "active_bits": len(active),
        "header_bytes": consumed_hex // 2 - data_bytes,
        "data_bytes": data_bytes,
        "mti_offset_bytes": mti_offset,
    }

    return AnalysisResult(
        raw_clean=clean,
        length_hex=headers["length_hex"],
        length_value=headers["length_value"],
        tpdu=headers["tpdu"],
        mti=headers["mti"],
        bitmap_primary_hex=primary,
        bitmap_secondary_hex=secondary,
        active_fields=active,
        fields=fields,
        warnings=warnings,
        errors=errors,
        emv=emv,
        numeric_encoding=encoding,
        consumed_hex=consumed_hex,
        declared_hex=declared,
        stats=stats,
        mti_offset_bytes=mti_offset,
        header_hex=headers["header_hex"],
        trailing_payload=payload,
    )


def _byte_len(f, encoding="bcd"):
    if f.ftype == "n":
        if encoding in ("ascii", "hybrid"):
            return f.length_digits
        return (f.length_digits + 1) // 2
    return f.length_digits


# ---------------------------------------------------------------------------
# Parsea BCD
# ---------------------------------------------------------------------------

def _parse_bcd(clean, opts):
    errors = []
    issues = []
    headers = _parse_headers(clean, opts, errors, encoding="bcd")
    debug = headers.get("debug") if opts.debug else None
    fields, pos, _active = _read_fields_hex(clean, headers, "bcd", issues, errors, debug,
                                             llvar_bytes=opts.llvar_prefix_bytes,
                                             lllvar_bytes=opts.lllvar_prefix_bytes,
                                             field_defs=opts.field_defs,
                                             lllvar_4digit=opts.lllvar_4digit_bcd,
                                             padding=opts.bcd_padding)
    consumed_hex = pos - headers["data_start_hex"]
    if opts.debug and debug:
        report_parse_debug(debug)
    return _assemble(clean, "bcd", headers, fields, issues, consumed_hex,
                     headers["mti_offset"])


# ---------------------------------------------------------------------------
# Parsea Híbrido (cabeceras binarias + campos de datos ASCII)
# ---------------------------------------------------------------------------

def _parse_hybrid(clean, opts):
    """Cabeceras binarias (longitud, TPDU, MTI, bitmaps) y campos en ASCII.

    Formato muy común en redes reales: los campos de datos se transmiten como
    texto (1 byte por carácter) mientras la cabecera y los bitmaps van en
    binario, igual que en modo BCD.
    """
    errors = []
    issues = []
    headers = _parse_headers(clean, opts, errors, encoding="hybrid")
    debug = headers.get("debug") if opts.debug else None
    fields, pos, _active = _read_fields_hex(clean, headers, "hybrid", issues, errors, debug,
                                             llvar_bytes=opts.llvar_prefix_bytes,
                                             lllvar_bytes=opts.lllvar_prefix_bytes,
                                             field_defs=opts.field_defs,
                                             lllvar_4digit=opts.lllvar_4digit_bcd,
                                             padding=opts.bcd_padding)
    consumed_hex = pos - headers["data_start_hex"]
    if opts.debug and debug:
        report_parse_debug(debug)
    return _assemble(clean, "hybrid", headers, fields, issues, consumed_hex,
                     headers["mti_offset"])


# ---------------------------------------------------------------------------
# Parsea ASCII
# ---------------------------------------------------------------------------

def _find_mti_offset_ascii(text, opts):
    """Detecta el offset (en caracteres ASCII) donde comienza el MTI."""
    if opts.mti_offset is not None:
        return opts.mti_offset
    if not opts.mti_auto:
        return _default_offset_ascii(opts)
    n = len(text)
    best, best_score = None, -1
    for off in range(0, min(24, max(0, n - 4)) + 1):
        score, ok = _score_offset_ascii(text, off, opts)
        if ok and score > best_score:
            best, best_score = off, score
    return best if best is not None else _default_offset_ascii(opts)


def _score_offset_ascii(text, off, opts):
    """Puntúa un offset candidato en modo ASCII (caracteres). Devuelve (score, ok)."""
    mti = text[off:off + 4]
    if len(mti) != 4 or mti not in KNOWN_MTIS:
        return 0, False
    pos = off + 4
    primary = text[pos:pos + 16]
    if len(primary) < 16 or not primary.isdigit() or primary == "0" * 16:
        return 0, False
    pos += 16
    secondary = ""
    if has_secondary_bitmap(primary):
        secondary = text[pos:pos + 16]
        if len(secondary) < 16 or not secondary.isdigit():
            return 0, False
        pos += 16
    score = 100 + 50 + (10 if secondary else 0)
    if len(text) >= 4 and text[0:4].isdigit():
        try:
            declared = int(text[0:4]) * 2
            if abs(declared - (len(text) - 4)) <= 4:
                score += 30
        except ValueError:
            pass
    if off == _default_offset_ascii(opts):
        score += 20
    h = "".join(format(ord(c), "02X") for c in text[pos:])
    fake = {"primary": primary, "secondary": secondary, "pos": 0}
    issues, errors = [], []
    fields, _p, _a = _read_fields_hex(h, fake, "ascii", issues, errors,
                                      field_defs=opts.field_defs)
    if any(f.has_error for f in fields):
        score -= 20
    else:
        score += 40 + len(fields) * 2
    return score, True


def _default_offset_ascii(opts):
    return 4 + (opts.tpdu_length_bytes * 2 if opts.has_tpdu else 0)


def _parse_ascii(clean, opts):
    errors = []
    issues = []
    debug = []
    text = bytes.fromhex(clean).decode("ascii", errors="replace")
    if len(text) < 4:
        errors.append("Trama demasiado corta (menos de 4 caracteres).")
        return AnalysisResult(clean, "", 0, None, None, "", "", [], [], issues, errors,
                              None, "ascii", 0, 0)

    off = _find_mti_offset_ascii(text, opts)
    mti_hex = text[off:off + 4]
    if len(mti_hex) != 4 or mti_hex not in KNOWN_MTIS:
        bad = "".join(
            dict.fromkeys(ch for ch in clean if ch not in HEX_SET and not is_removable(ch))
        )[:20]
        if bad:
            raise ParseError(f"Caracteres no permitidos en la trama: {bad}")
        raise ParseError("No se pudo localizar un MTI válido en la trama.")

    try:
        length_value = int(text[0:4])
    except ValueError:
        length_value = 0
        issues.append(
            f"Prefijo de longitud no numérico ({text[0:4]!r}): no se puede validar la longitud."
        )
    declared_hex = length_value * 2

    # Longitud + TPDU + header propietario hasta el MTI
    length_hex = text[0:4] if off >= 4 else ""
    tpdu = None
    tpdu_hex = ""
    if opts.has_tpdu and off >= 4 + opts.tpdu_length_bytes * 2:
        tpdu_hex = text[4:4 + opts.tpdu_length_bytes * 2]
        tpdu = decode_tpdu(tpdu_hex)
    header_hex = text[0:off]

    if debug is not None:
        debug.append("MODO ASCII")
        debug.append(f"Offset inicial usado (bytes antes del MTI): {off}")
        debug.append(f"Longitud: {length_hex} ({length_value} bytes)")
        if header_hex:
            debug.append(f"Header pre-MTI: {header_hex} ({off} bytes)")
        if tpdu_hex:
            debug.append(f"TPDU: {tpdu_hex}")
        debug.append(f"MTI encontrado: {mti_hex} (offset byte {off})")

    mti = decode_mti(mti_hex)
    pos = off + 4
    primary = text[pos:pos + 16]
    if len(primary) < 16:
        errors.append("Bitmap primario inválido en modo ASCII.")
        primary = primary.ljust(16, "0")
        pos += len(primary)
    else:
        pos += 16
    if debug is not None:
        debug.append(f"Bitmap encontrado: {primary} (offset byte {off + 2 + 2})")

    secondary = ""
    if has_secondary_bitmap(primary):
        secondary = text[pos:pos + 16]
        if len(secondary) < 16:
            errors.append("Bitmap secundario inválido en modo ASCII.")
            secondary = secondary.ljust(16, "0")
            pos += len(secondary)
        else:
            pos += 16

    # Reconstruir la representación hex de los datos restantes
    data_text = text[pos:]
    h = "".join(format(ord(c), "02X") for c in data_text)
    pos_hex = 0

    combined = primary + secondary
    active = parse_bitmap(combined)

    fields: List[ParsedField] = []
    for number in active:
        if number == 1:
            continue
        fdef = (opts.field_defs or DATA_ELEMENTS).get(number)
        if fdef is None:
            fields.append(
                ParsedField(number, "Desconocido", "Reservado", "an", "lllvar", 999, 0, "",
                            "", pos_hex, has_error=True, error="Definición de campo no encontrada.")
            )
            continue
        field_start = pos_hex
        try:
            field, pos_hex = _read_field_ascii(h, pos_hex, fdef, issues)
            fields.append(field)
        except ParseError as exc:
            fields.append(
                ParsedField(number, fdef.name, fdef.description, fdef.ftype, fdef.length_type,
                            fdef.length, 0, "", "", pos_hex, has_error=True, error=str(exc))
            )
            break
        if debug is not None:
            if fdef.length_type == "fixed":
                prefix_bytes = 0
            else:
                prefix_bytes = {"llvar": 2, "lllvar": 3, "llllvar": 4}[fdef.length_type]
            base = off + 2 + 8 + len(secondary) // 2
            debug.append(
                f"DE{number}: offset inicial byte {base + field_start // 2} (hex {field_start}), "
                f"offset final byte {base + pos_hex // 2} (hex {pos_hex}), "
                f"longitud del prefijo {prefix_bytes} byte(s), "
                f"longitud interpretada {field.length_digits}, "
                f"bytes consumidos {(pos_hex - field_start) // 2}, "
                f"bytes restantes {(len(h) - pos_hex) // 2}"
            )
            if field.note:
                debug.append(f"  DE{number} nota: {field.note}")

    consumed_chars = (len(text) - len(length_hex) - len(data_text)) + pos_hex // 2
    consumed_hex = consumed_chars * 2

    remaining_chars = len(text) - len(length_hex) - consumed_chars
    if remaining_chars > 0:
        issues.append(
            f"Hay {remaining_chars} bytes de datos sin analizar después del último campo."
        )

    if declared_hex and consumed_hex != declared_hex:
        issues.append(
            f"Longitud declarada ({length_value} bytes = {declared_hex} hex) no coincide "
            f"con el contenido analizado ({consumed_hex} hex)."
        )

    if opts.debug:
        report_parse_debug(debug)

    emv = None
    for f in fields:
        if f.number == 55 and not f.has_error and f.value:
            try:
                from .emv import parse_tlv
                emv = parse_tlv(f.value)
                f.emv = [n.as_dict() for n in emv]
            except (ValueError, IndexError) as exc:
                issues.append(f"No se pudo decodificar el EMV del campo 55: {exc}")

    headers = {
        "length_hex": length_hex,
        "length_value": length_value,
        "declared_hex": declared_hex,
        "tpdu": tpdu,
        "tpdu_hex": tpdu_hex,
        "mti": mti,
        "primary": primary,
        "secondary": secondary,
        "mti_offset": off,
        "header_hex": header_hex,
    }
    return AnalysisResult(
        raw_clean=clean,
        length_hex=length_hex,
        length_value=length_value,
        tpdu=tpdu,
        mti=mti,
        bitmap_primary_hex=primary,
        bitmap_secondary_hex=secondary,
        active_fields=active,
        fields=fields,
        warnings=issues,
        errors=errors,
        emv=emv,
        numeric_encoding="ascii",
        consumed_hex=consumed_hex,
        declared_hex=declared_hex,
        stats={"total_fields": len(fields), "active_bits": len(active),
               "mti_offset_bytes": off},
        mti_offset_bytes=off,
        header_hex=header_hex,
    )


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

def parse_message(raw, options: Optional[ParseOptions] = None) -> AnalysisResult:
    """Analiza una trama ISO 8583 y devuelve un AnalysisResult.

    Lanza ParseError si la trama está vacía, es impar o no puede localizarse
    un MTI/bitmap válidos. Los valores de los Data Elements no se validan
    como hex de la trama: pueden contener texto, JSON, XML, Base64, etc.
    """
    opts = options or ParseOptions()
    clean = clean_frame(raw)
    if not clean:
        raise ParseError("La trama está vacía.")

    encoding = opts.numeric_encoding
    if encoding == "auto":
        encoding = _detect_encoding(clean, opts)

    if encoding == "ascii":
        return _parse_ascii(clean, opts)
    if encoding == "hybrid":
        return _parse_hybrid(clean, opts)
    return _parse_bcd(clean, opts)
