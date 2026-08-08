# -*- coding: utf-8 -*-
"""Decoder ISO 8583.

Envuelve el analizador estable (core.parser.parse_message) y convierte su
AnalysisResult en un Message (árbol universal). Así la arquitectura nueva
descansa sobre la lógica ya probada, sin duplicarla.
"""

from ...issues import IssueList
from ...model.message import DecodedNode, Message
from ...parser import ParseError, ParseOptions, parse_message
from ...fields import DATA_ELEMENTS
from ..base import ProtocolDecoder
from ..registry import register_decoder


def _header_offsets(encoding, has_tpdu, tpdu_len, mti_offset=None):
    """Posiciones (en caracteres hex de la trama) de cada cabecera.

    `mti_offset` es el offset en bytes del MTI resuelto por el parser. Si no
    se provee, se usa el layout clásico (longitud 2 + TPDU).
    """
    off = {}
    if mti_offset is None:
        mti_offset = 2 + (tpdu_len if has_tpdu else 0)
    mti_hex = mti_offset * 2
    off["mti"] = mti_hex
    off["bitmap"] = mti_hex + 4
    if has_tpdu and mti_offset >= 2 + tpdu_len:
        off["tpdu"] = 4
    else:
        off["tpdu"] = 0
    return off


def _tlv_from_dict(raw):
    node = DecodedNode(
        label=f"{raw.get('tag', '')} {raw.get('name', '')}".strip(),
        value=raw.get("value_hex", ""),
        raw_hex=raw.get("value_hex", ""),
        note=raw.get("note", ""),
        kind="tlv",
    )
    for child in raw.get("children", []):
        node.children.append(_tlv_from_dict(child))
    return node


def _field_node(f):
    node = DecodedNode(
        label=f"DE{f.number} {f.name}",
        value=f.value,
        raw_hex=f.raw_hex,
        kind="field",
        offset_hex=f.offset_hex,
        length_hex=len(f.raw_hex),
    )
    if f.has_error:
        node.note = f"ERROR: {f.error}"
        return node
    node.note = (
        f"Tipo {f.ftype} · {f.length_type.upper()} máx {f.max_length} · "
        f"longitud {f.length_digits}"
    )
    if f.number == 55 and f.emv:
        for raw in f.emv:
            node.children.append(_tlv_from_dict(raw))
    return node


def analysis_to_message(result, profile_name, protocol="iso8583"):
    """Convierte un AnalysisResult al modelo universal Message."""
    off = _header_offsets(result.numeric_encoding, bool(result.tpdu), 5,
                          result.mti_offset_bytes)

    root = DecodedNode("Mensaje ISO 8583", kind="root", raw_hex=result.raw_clean)
    if result.length_hex:
        root.add(DecodedNode(
            "Longitud", result.length_hex,
            note=f"{result.length_value} bytes",
            kind="header", offset_hex=0, length_hex=4,
        ))

    if result.header_hex:
        root.add(DecodedNode(
            "Header pre-MTI", result.header_hex,
            note=f"{len(result.header_hex) // 2} bytes antes del MTI"
                 + (f" · offset {result.mti_offset_bytes} bytes" if result.mti_offset_bytes is not None else ""),
            kind="header", offset_hex=0, length_hex=len(result.header_hex),
        ))

    if result.tpdu:
        tpdu = result.tpdu
        node = DecodedNode(
            "TPDU", tpdu.hex, kind="header",
            offset_hex=off.get("tpdu", 4), length_hex=len(tpdu.hex),
            note=f"Destino={tpdu.destination} Origen={tpdu.source} Control={tpdu.control}",
        )
        node.add(DecodedNode("Destino", tpdu.destination, kind="bit", offset_hex=off.get("tpdu", 4)))
        node.add(DecodedNode("Origen", tpdu.source, kind="bit", offset_hex=off.get("tpdu", 4) + 4))
        node.add(DecodedNode("Control", tpdu.control, kind="bit", offset_hex=off.get("tpdu", 4) + 8))
        root.add(node)

    if result.mti:
        mti = result.mti
        node = DecodedNode(
            "MTI", mti.hex, kind="header",
            offset_hex=off.get("mti", 14), length_hex=4,
            note=mti.description,
        )
        node.add(DecodedNode("Versión", mti.version, kind="bit"))
        node.add(DecodedNode("Clase", mti.message_class, kind="bit"))
        node.add(DecodedNode("Función", mti.function, kind="bit"))
        node.add(DecodedNode("Origen", mti.origin, kind="bit"))
        root.add(node)

    bitmap = DecodedNode(
        "Bitmap", result.bitmap_primary_hex, kind="header",
        offset_hex=off.get("bitmap", 18), length_hex=len(result.bitmap_primary_hex),
        note=f"{len(result.active_fields)} campos activos",
    ) 
    bitmap.add(DecodedNode(
        "Primario", result.bitmap_primary_hex,
        raw_hex=result.bitmap_primary_hex, kind="bit",
    ))
    if result.bitmap_secondary_hex:
        bitmap.add(DecodedNode(
            "Secundario", result.bitmap_secondary_hex,
            raw_hex=result.bitmap_secondary_hex, kind="bit",
        ))
    bitmap.add(DecodedNode(
        "Campos activos", " ".join(str(n) for n in result.active_fields),
        kind="group",
    ))
    root.add(bitmap)

    for f in result.fields:
        root.add(_field_node(f))

    issues = IssueList()
    for w in result.warnings:
        issues.add("warning", "parse.warning", w)
    for e in result.errors:
        issues.add("error", "parse.error", e)

    metadata = {
        "active_fields": list(result.active_fields),
        "field_count": len(result.fields),
        "consumed_hex": result.consumed_hex,
        "declared_hex": result.declared_hex,
        "mti_offset_bytes": result.mti_offset_bytes,
        "stats": dict(result.stats),
    }
    return Message(
        raw_clean=result.raw_clean,
        protocol=protocol,
        profile=profile_name,
        root=root,
        issues=issues,
        encoding=result.numeric_encoding,
        metadata=metadata,
        legacy=result,
    )


@register_decoder
class ISO8583Decoder(ProtocolDecoder):
    protocol_id = "iso8583"

    def decode(self, raw, profile, options=None) -> Message:
        field_defs = dict(DATA_ELEMENTS)
        for number, fdef in getattr(profile, "elements", {}).items():
            field_defs[number] = fdef
        opts = ParseOptions(
            has_tpdu=profile.has_tpdu,
            tpdu_length_bytes=profile.tpdu_length,
            numeric_encoding=profile.encoding,
            llvar_prefix_bytes=getattr(profile, "llvar_prefix_bytes", 1),
            lllvar_prefix_bytes=getattr(profile, "lllvar_prefix_bytes", 2),
            lllvar_4digit_bcd=getattr(profile, "lllvar_4digit_bcd", False),
            field_defs=field_defs,
        )
        if options is not None:
            if getattr(options, "has_tpdu", None) is not None:
                opts.has_tpdu = options.has_tpdu
            if getattr(options, "tpdu_length_bytes", None) is not None:
                opts.tpdu_length_bytes = options.tpdu_length_bytes
            enc = getattr(options, "numeric_encoding", None)
            if enc and enc != "auto":
                opts.numeric_encoding = enc
            if getattr(options, "mti_offset", None) is not None:
                opts.mti_offset = options.mti_offset
            if getattr(options, "mti_auto", None) is not None:
                opts.mti_auto = options.mti_auto
            if getattr(options, "debug", None):
                opts.debug = True
            # El layout de prefijos y la codificación los define el perfil; un
            # caller que deje los valores por defecto no debe pisarlos.
            if getattr(options, "llvar_prefix_bytes", None) not in (None, 1):
                opts.llvar_prefix_bytes = options.llvar_prefix_bytes
            if getattr(options, "lllvar_prefix_bytes", None) not in (None, 2):
                opts.lllvar_prefix_bytes = options.lllvar_prefix_bytes
            if getattr(options, "lllvar_4digit_bcd", None) not in (None, False):
                opts.lllvar_4digit_bcd = options.lllvar_4digit_bcd
            if getattr(options, "field_defs", None):
                opts.field_defs = options.field_defs
        result = parse_message(raw, opts)
        return analysis_to_message(result, profile.name, profile.protocol)
