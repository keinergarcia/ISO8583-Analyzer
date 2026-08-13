# -*- coding: utf-8 -*-
"""Reglas determinísticas de validación estructural del DE55 / EMV.

Reutiliza el parser EMV existente (core.emv.parse_tlv) para interpretar los
nodos. Además realiza un escaneo estructural independiente para detectar
solo errores demostrables:

- TLV incompleto (falta tag / prefijo de longitud).
- Tag sin longitud.
- Prefijo de longitud truncado.
- Longitud que excede los datos disponibles (valor truncado).

NO se inventan problemas de la tarjeta ni causas técnicas.
"""

from typing import Callable, List, Tuple

from ..converters import bcd_to_decimal
from ..emv import CONSTRUCTED_TAGS, parse_tlv
from ..transaction_summary import (
    TransactionSummary,
    _find_field,
    _format_amount,
    _format_date,
)

Adder = Callable[..., None]


def _read_tag(buf, i):
    """Lee un tag BER-TLV. Devuelve (tag, constructed, nueva_pos)."""
    if i + 2 > len(buf):
        return None, False, i
    first = int(buf[i:i + 2], 16)
    i += 2
    tag = format(first, "02X")
    if first & 0x1F == 0x1F:
        while True:
            if i + 2 > len(buf):
                return None, bool(first & 0x20), i
            b = int(buf[i:i + 2], 16)
            i += 2
            tag += format(b, "02X")
            if not (b & 0x80):
                break
    return tag, bool(first & 0x20), i


def _read_length(buf, i):
    """Lee la longitud BER-TLV. Devuelve (length, nueva_pos) o lanza ValueError."""
    if i + 2 > len(buf):
        raise ValueError("tag-sin-longitud")
    first = int(buf[i:i + 2], 16)
    i += 2
    if first < 0x80:
        return first, i
    n = first & 0x7F
    if n == 0:
        raise ValueError("longitud-indefinida")
    if i + n * 2 > len(buf):
        raise ValueError("prefijo-longitud-truncado")
    length = int(buf[i:i + n * 2], 16)
    i += n * 2
    return length, i


def _scan(value_hex: str, out: List[Tuple[str, str]]):
    """Escanea una secuencia TLV y recopila errores estructurales.

    out: lista de tuplas (tag, mensaje). Vacía si la estructura es válida.
    """
    buf = (value_hex or "").replace(" ", "").upper()
    if not buf:
        return
    if len(buf) % 2 != 0:
        out.append(("", "La cantidad de caracteres HEX del DE55 debe ser par."))
        return
    i = 0
    while i < len(buf):
        tag, constructed, i = _read_tag(buf, i)
        if tag is None:
            out.append(("", "TLV incompleto: faltan bytes del tag."))
            return
        try:
            length, i = _read_length(buf, i)
        except ValueError as exc:
            if str(exc) == "tag-sin-longitud":
                out.append((tag, f"Tag {tag} sin longitud."))
            elif str(exc) == "longitud-indefinida":
                out.append((tag, f"Tag {tag}: longitud indefinida no soportada."))
            elif str(exc) == "prefijo-longitud-truncado":
                out.append((tag, f"Tag {tag}: prefijo de longitud truncado."))
            else:
                out.append((tag, f"Tag {tag}: longitud inválida."))
            return
        value_start = i
        if i + length * 2 > len(buf):
            available = (len(buf) - i) // 2
            out.append((
                tag,
                f"Tag {tag} declara {length} bytes pero los datos disponibles "
                f"son insuficientes ({available}).",
            ))
            return
        i += length * 2
        value_hex = buf[value_start:i]
        if constructed and tag in CONSTRUCTED_TAGS:
            _scan(value_hex, out)
            if out:
                return


def _find_emv_tag(nodes, target):
    """Busca un tag por nombre en la lista de nodos TLV (recursivo)."""
    for n in nodes or []:
        tag = getattr(n, "tag", None)
        if tag is None and isinstance(n, dict):
            tag = n.get("tag")
        if tag == target:
            return n
        children = getattr(n, "children", None)
        if children is None and isinstance(n, dict):
            children = n.get("children")
        found = _find_emv_tag(children, target)
        if found is not None:
            return found
    return None


def _source_currency(result):
    """CurrencySource detectado (DE49 > EMV > DE51) o None."""
    return TransactionSummary(result).source


def check_emv(result, add: Adder) -> bool:
    """Valida la estructura TLV del DE55 de la trama.

    Devuelve True solo si existe un DE55 con estructura TLV válida.
    """
    valid = False
    for f in getattr(result, "fields", []) or []:
        if f.number != 55 or f.has_error:
            continue
        value_hex = (f.value or "").replace(" ", "").upper()
        if not value_hex:
            continue
        errors: List[Tuple[str, str]] = []
        _scan(value_hex, errors)
        if errors:
            for tag, message in errors:
                add("ERROR", "INVALID_EMV_TLV", message, "DE55/EMV",
                    value=f"Tag {tag}" if tag else value_hex, rule="EMV_TLV")
            continue
        # Estructura válida: confirmar con el parser EMV existente.
        nodes = f.emv or []
        count = len(nodes)
        add("INFO", "EMV_TLV_VALID",
            f"Estructura TLV del DE55 válida ({count} tags).",
            "DE55/EMV", value=value_hex[:40] + ("…" if len(value_hex) > 40 else ""),
            rule="EMV_TLV")
        valid = True
    return valid


def check_amount_consistency(result, add: Adder):
    """Compara DE4 con el Tag 9F02 (Amount, Authorised) del DE55.

    Solo se genera la validación si ambos montos existen y son numéricos;
    sin 9F02 o con DE55 inválido no se emite ningún hallazgo.
    """
    de4 = _find_field(result, 4)
    if de4 is None or de4.has_error or not (de4.value or "").strip():
        return
    de55 = _find_field(result, 55)
    if de55 is None or de55.has_error or not (de55.value or "").strip():
        return
    try:
        nodes = parse_tlv(de55.value)
    except ValueError:
        return
    node_9f02 = _find_emv_tag(nodes, "9F02")
    if node_9f02 is None:
        return  # sin 9F02 no se genera la validación de monto
    raw_de4 = de4.value.strip()
    try:
        raw_9f02 = bcd_to_decimal(node_9f02.value_hex)
    except ValueError:
        return
    if not raw_de4.isdigit() or not raw_9f02.isdigit():
        return

    src = _source_currency(result)
    mu = src.minor_units if src else None
    cc = src.currency if src else None

    def _fmt(raw):
        if mu is None:
            return raw
        amount = _format_amount(raw, mu)
        if amount is None:
            return raw
        return f"{amount} {cc}" if cc else amount

    de4_fmt = _fmt(raw_de4)
    emv_fmt = _fmt(raw_9f02)
    value = f"DE4: {de4_fmt}\n9F02: {emv_fmt}"
    if raw_de4.lstrip("0") == raw_9f02.lstrip("0"):
        add("INFO", "AMOUNT_MATCH",
            f"Monto DE4 = {de4_fmt} y 9F02 = {emv_fmt}: los montos coinciden.",
            "DE4/EMV", value=value, rule="AMOUNT_CONSISTENCY")
    else:
        add("ERROR", "AMOUNT_MISMATCH",
            f"Monto DE4 = {de4_fmt} vs 9F02 = {emv_fmt}: los montos NO coinciden.",
            "DE4/EMV", value=value, rule="AMOUNT_CONSISTENCY")


def check_date_consistency(result, add: Adder):
    """Compara DE13 (MMDD) con el Tag 9A (YYMMDD) del DE55."""
    de13 = _find_field(result, 13)
    if de13 is None or de13.has_error:
        return
    raw_de13 = (de13.value or "").strip()
    if len(raw_de13) != 4 or not raw_de13.isdigit():
        return
    date_de13 = _format_date(raw_de13)
    if date_de13 is None:
        return  # DE13 inválido ya se reporta como INVALID_DATE
    de55 = _find_field(result, 55)
    if de55 is None or de55.has_error or not (de55.value or "").strip():
        return
    try:
        nodes = parse_tlv(de55.value)
    except ValueError:
        return
    node_9a = _find_emv_tag(nodes, "9A")
    if node_9a is None:
        return  # sin 9A no se genera la validación de fecha
    yy = node_9a.value_hex[0:2]
    mm = node_9a.value_hex[2:4]
    dd = node_9a.value_hex[4:6]
    if len(node_9a.value_hex) < 6 or not (yy + mm + dd).isdigit():
        return

    date_9a = f"{dd}/{mm}/{yy}"
    value = f"DE13: {date_de13}\n9A: {date_9a}"
    if (raw_de13[0:2], raw_de13[2:4]) == (mm, dd):
        add("INFO", "DATE_MATCH",
            f"Fecha DE13 = {date_de13} y 9A = {date_9a}: las fechas coinciden.",
            "DE13/EMV", value=value, rule="DATE_CONSISTENCY")
    else:
        add("ERROR", "DATE_MISMATCH",
            f"Fecha DE13 = {date_de13} vs 9A = {date_9a}: las fechas NO coinciden.",
            "DE13/EMV", value=value, rule="DATE_CONSISTENCY")


def run_emv_rules(result, add: Adder):
    """Ejecuta las reglas EMV sobre un resultado."""
    structurally_valid = check_emv(result, add)
    if structurally_valid:
        check_amount_consistency(result, add)
        check_date_consistency(result, add)
