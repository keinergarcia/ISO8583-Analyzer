# -*- coding: utf-8 -*-
"""Exportación del análisis a texto plano y JSON."""

import json

from .currency import detect_currency, detector as currency_detector
from .field_interpreter import interpret
from .transaction_summary import TransactionSummary


def _fmt_value(field):
    if field.ftype == "b":
        return field.value
    return field.value


def result_to_text(result) -> str:
    """Genera un reporte de texto completo del análisis."""
    lines = []
    lines.append("=" * 60)
    lines.append("  ISO8583 Analyzer - Reporte de Análisis")
    lines.append("=" * 60)
    lines.append(f"Trama (hex):   {result.raw_clean}")
    lines.append("")

    lines.append("--- Longitud ---")
    lines.append(f"Hex:           {result.length_hex}")
    lines.append(f"Decimal:       {result.length_value} bytes")
    lines.append("")

    if result.tpdu:
        lines.append("--- TPDU ---")
        lines.append(f"TPDU:          {result.tpdu.hex}")
        lines.append(f"Destino:       {result.tpdu.destination}")
        lines.append(f"Origen:        {result.tpdu.source}")
        lines.append(f"Control:       {result.tpdu.control}")
        lines.append("")

    if result.mti:
        lines.append("--- MTI ---")
        lines.append(f"MTI:           {result.mti.hex}")
        lines.append(f"Descripción:   {result.mti.description}")
        lines.append(f"Versión:       {result.mti.version}")
        lines.append(f"Clase:         {result.mti.message_class}")
        lines.append(f"Función:       {result.mti.function}")
        lines.append(f"Origen:        {result.mti.origin}")
        lines.append("")

    lines.append("--- Bitmap ---")
    lines.append(f"Primario:      {result.bitmap_primary_hex}")
    if result.bitmap_secondary_hex:
        lines.append(f"Secundario:    {result.bitmap_secondary_hex}")
    lines.append("")

    lines.append("--- Campos activos ---")
    for n in result.active_fields:
        if n != 1:
            lines.append(f"  ✓ DE{n}")
    lines.append("")

    lines.append("--- Moneda de Transacción ---")
    currency_report = detect_currency(result)
    lines.extend(currency_detector().formatCurrencyResult(currency_report))
    lines.append("")

    if result.emv:
        lines.append("--- Campo 55 / EMV ---")
        for node in result.emv:
            lines.append(f"  [{node.tag}] {node.name}  ({node.length} B)")
            if node.value_hex:
                lines.append(f"      Hex: {node.value_hex}")
            if node.value_ascii:
                lines.append(f"      Ascii: {node.value_ascii}")
            if node.note:
                lines.append(f"      {node.note}")
            for child in node.children:
                lines.append(f"    - [{child.tag}] {child.name}  = {child.value_hex}")
        lines.append("")

    lines.append("--- Data Elements ---")
    for f in result.fields:
        lines.append("")
        lines.append(f"DE{f.number}  {f.name}")
        if f.description and f.description != f.name:
            lines.append(f"    Descripción: {f.description}")
        lines.append(f"    Tipo: {f.ftype}  |  Longitud: {f.length_type}")
        lines.append(f"    Longitud campo: {f.length_digits}")
        lines.append(f"    Valor:  {f.value}")
        lines.append(f"    Hex:    {f.raw_hex}")
        interp = interpret(f)
        lines.append(f"    Clasificación: {interp.label}")
        if f.note:
            lines.append(f"    Nota:   {f.note}")
        if f.has_error:
            lines.append(f"    ERROR: {f.error}")

    lines.append("")
    lines.append("--- Interpretación del Campo ---")
    for f in result.fields:
        if f.has_error:
            continue
        interp = interpret(f)
        lines.append(f"DE{f.number} detectado como:")
        lines.append(f"{interp.summary}")
        if interp.category == "text" and f.value:
            lines.append("Contenido:")
            lines.append(f"{f.value}")
        lines.append("")

    lines.extend(TransactionSummary(result).format_summary())
    lines.append("")

    lines.append("--- Advertencias ---")
    if result.warnings:
        for w in result.warnings:
            lines.append(f"  ⚠ {w}")
    else:
        lines.append("  Ninguna.")
    lines.append("--- Errores ---")
    if result.errors:
        for e in result.errors:
            lines.append(f"  ✗ {e}")
    else:
        lines.append("  Ninguno.")
    lines.append("")
    lines.append("=" * 60)
    return "\n".join(lines)


def result_to_json(result) -> str:
    """Serializa el análisis completo a JSON (legible)."""
    data = result.as_dict()
    data["generator"] = "ISO8583 Analyzer"
    data["version"] = "1.0"
    fields_out = data.get("fields") or []
    for field_out, field in zip(fields_out, result.fields):
        field_out["interpretation"] = interpret(field).as_dict()
    data["currency"] = detect_currency(result).as_dict()
    data["summary"] = TransactionSummary(result).as_dict()
    return json.dumps(data, indent=2, ensure_ascii=False)
