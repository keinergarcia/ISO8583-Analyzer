# -*- coding: utf-8 -*-
"""Field Dictionary: consultas al diccionario de un perfil."""

from ..profiles import registry as profile_registry


def all_fields(profile=None):
    profile = profile or profile_registry.get_default()
    out = []
    for number in range(1, profile.max_de + 1):
        fdef = profile.data_element(number)
        if fdef is None:
            continue
        out.append({
            "number": fdef.number,
            "name": fdef.name,
            "ftype": fdef.ftype,
            "length_type": fdef.length_type,
            "max_length": fdef.length,
            "description": fdef.description,
        })
    return out


def search(profile, query):
    """Busca por número, nombre o descripción (sin distinguir mayúsculas)."""
    profile = profile or profile_registry.get_default()
    q = (query or "").strip().lower()
    if not q:
        return all_fields(profile)
    out = []
    for f in all_fields(profile):
        if q in str(f["number"]) or q in f["name"].lower() or q in f["description"].lower():
            out.append(f)
    return out
