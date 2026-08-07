# -*- coding: utf-8 -*-
"""Bitmap Viewer: tabla de Data Elements (presente/ausente) desde un mensaje."""

from ..profiles import registry as profile_registry


def de_table(message=None, profile=None):
    """Genera las filas del bitmap: número, nombre, tipo, longitud y estado.

    message puede ser un core.model.message.Message o un AnalysisResult.
    """
    if message is None:
        active = []
    else:
        active = getattr(message, "active_fields", None)
        if active is None and getattr(message, "legacy", None) is not None:
            active = message.legacy.active_fields
    active = set(active or [])

    if profile is None:
        profile = profile_registry.get_default()
    rows = []
    for number in range(2, profile.max_de + 1):
        fdef = profile.data_element(number)
        rows.append({
            "number": number,
            "name": fdef.name if fdef else "Reservado",
            "ftype": fdef.ftype if fdef else "—",
            "length_type": fdef.length_type if fdef else "—",
            "max_length": fdef.length if fdef else "—",
            "present": number in active,
        })
    return rows


def summary(message=None, profile=None):
    rows = de_table(message, profile)
    present = [r for r in rows if r["present"]]
    return {
        "total": len(rows),
        "present": len(present),
        "absent": len(rows) - len(present),
        "active_fields": [r["number"] for r in present],
    }
