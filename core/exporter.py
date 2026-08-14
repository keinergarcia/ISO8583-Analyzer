# -*- coding: utf-8 -*-
"""Exportación del análisis a texto plano y JSON."""

import json

from .currency import detect_currency, detector as currency_detector
from .emv import enrich_result_emv
from .field_interpreter import interpret, interpret_data
from .transaction_summary import TransactionSummary
from .validation import validate_result


def _count_emv_tags(nodes) -> int:
    """Cuenta tags EMV incluyendo los anidados (hijos)."""
    total = 0
    for n in nodes:
        total += 1 + _count_emv_tags(getattr(n, "children", None) or [])
    return total


def result_to_text(result) -> str:
    """Genera un reporte de texto completo del análisis."""
    lines = []
    lines.append("=" * 60)
    lines.append("  ISO8583 Analyzer - Reporte de Análisis")
    lines.append("=" * 60)
    lines.append(f"Trama (hex):   {result.raw_clean}")
    lines.append("")

    # Resumen, moneda y validación se calculan una sola vez y se reutilizan.
    summary = TransactionSummary(result)
    currency_report = detect_currency(result)
    src = summary.source
    enrich_result_emv(result,
                      src.currency if src else None,
                      src.minor_units if src else None)
    vr = validate_result(result)

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
    lines.extend(currency_detector().formatCurrencyResult(currency_report))
    lines.append("")

    if result.emv:
        lines.append("--- Campo 55 / EMV ---")
        if any(x.code == "INVALID_EMV_TLV" for x in vr.findings):
            lines.append("Estructura TLV: ✗ Inválida (error estructural)")
        elif any(x.code == "EMV_TLV_VALID" for x in vr.findings):
            lines.append("Estructura TLV: ✓ Válida")
        else:
            lines.append("Estructura TLV: no validada")
        lines.append(f"Tags encontrados: {_count_emv_tags(result.emv)}")
        lines.append("")
        for node in result.emv:
            lines.append(f"  [{node.tag}] {node.name}  ({node.length} B)")
            if node.value_hex:
                lines.append(f"      Hex: {node.value_hex}")
            if node.value_ascii:
                lines.append(f"      Ascii: {node.value_ascii}")
            if node.note:
                lines.append(f"      Nota: {node.note}")
            if node.interpretation:
                lines.append(f"      Interpretación: {node.interpretation}")
            for child in node.children:
                lines.append(f"    - [{child.tag}] {child.name}  = {child.value_hex}")
        lines.append("")

    consistency_codes = {"AMOUNT_MATCH", "AMOUNT_MISMATCH",
                         "DATE_MATCH", "DATE_MISMATCH",
                         "CURRENCY_MATCH", "CURRENCY_MISMATCH"}
    consistency = [x for x in vr.findings if x.code in consistency_codes]
    if result.emv or consistency:
        lines.append("--- Consistencia ISO8583 ↔ EMV ---")
        if consistency:
            marks = {"AMOUNT_MATCH": "✓", "AMOUNT_MISMATCH": "✗",
                     "DATE_MATCH": "✓", "DATE_MISMATCH": "✗",
                     "CURRENCY_MATCH": "✓", "CURRENCY_MISMATCH": "⚠"}
            for x in consistency:
                lines.append(f"  {marks.get(x.code, '•')} [{x.code}] {x.message}")
        else:
            lines.append("  Sin diferencias detectadas entre ISO8583 y EMV.")
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
    if result.trailing_payload is not None:
        p = result.trailing_payload
        lines.append("--- Payload posterior ---")
        if p.status == "confirmed":
            lines.append("Tipo:              GZIP (gzip comprimido)")
        else:
            lines.append("Tipo:              posible_gzip — no verificado")
            lines.append(f"Motivo:            {p.reason}")
        lines.append(f"Longitud declarada: {p.declared_length} bytes (prefijo 0x{p.declared_length:04X} de DE64)")
        lines.append(f"Longitud disponible: {p.available_length} bytes")
        if p.decompressed_length is not None:
            lines.append(f"Estado:            Descomprimido correctamente — {p.decompressed_length} bytes")
        else:
            lines.append(f"Estado:            No se pudo descomprimir ({p.reason})")
        lines.append(f"Offset hex:        {p.offset_hex}")
        if p.preview:
            lines.append("Vista previa:")
            lines.append(p.preview)
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
            jdata = interpret_data(f)
            if jdata["json_like"]:
                lines.append("Estructura JSON/lista:")
                lines.append(jdata["compact"])
        lines.append("")

    lines.extend(summary.format_summary())
    lines.append("")

    lines.extend(vr.format_lines())
    lines.append("")

    # Las secciones de Advertencias/Errores provienen de los hallazgos de
    # validación (fuente única de verdad), para que el estado general de la
    # trama siempre corresponda con la lista de errores mostrada.
    lines.append("--- Advertencias ---")
    if vr.warnings:
        for w in vr.warnings:
            lines.append(f"  ⚠ [{w.code}] {w.message}")
    else:
        lines.append("  Ninguna.")
    lines.append("--- Errores ---")
    if vr.errors:
        for e in vr.errors:
            lines.append(f"  ✗ [{e.code}] {e.message}")
    else:
        lines.append("  Ninguno.")
    lines.append("")
    lines.append("=" * 60)
    return "\n".join(lines)


def result_to_json(result) -> str:
    """Serializa el análisis completo a JSON (legible)."""
    summary = TransactionSummary(result)
    src = summary.source
    enrich_result_emv(result,
                      src.currency if src else None,
                      src.minor_units if src else None)
    data = result.as_dict()
    data["generator"] = "ISO8583 Analyzer"
    data["version"] = "1.0"
    fields_out = data.get("fields") or []
    for field_out, field in zip(fields_out, result.fields):
        field_out["interpretation"] = interpret(field).as_dict()
    data["currency"] = detect_currency(result).as_dict()
    data["summary"] = TransactionSummary(result).as_dict()
    data["validation"] = validate_result(result).as_dict()
    return json.dumps(data, indent=2, ensure_ascii=False)
