# -*- coding: utf-8 -*-
"""Registro y carga de perfiles de mensaje.

- `get_default()` construye el perfil por defecto a partir del diccionario
  embebido (core.fields.DATA_ELEMENTS), por lo que la app funciona aunque no
  existan archivos JSON.
- Los perfiles JSON viven en core/profiles/specs/*.json y se cargan con caché.
"""

import json
import sys
from pathlib import Path

from ..fields import DATA_ELEMENTS, FieldDef
from .model import Profile


def _resource_base():
    """Directorio base para recursos de solo lectura (compatible con PyInstaller)."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent.parent


def _specs_dir():
    return _resource_base() / "core" / "profiles" / "specs"


def _default_elements():
    return {n: FieldDef(f.number, f.name, f.ftype, f.length, f.length_type, f.description)
            for n, f in DATA_ELEMENTS.items()}


DEFAULT_PROFILE_NAME = "iso8583_1987"

_registry = {}
_cache_valid = False


def _build_default():
    return Profile(
        name=DEFAULT_PROFILE_NAME,
        description="ISO 8583:1987 (diccionario embebido)",
        elements=_default_elements(),
    )


def fielddef_from_dict(number, d):
    """Construye un FieldDef desde una entrada del JSON del perfil."""
    return FieldDef(
        int(number),
        d.get("name", f"DE{number}"),
        d.get("ftype", "an"),
        int(d.get("length", 0)),
        d.get("length_type", "fixed"),
        d.get("description", d.get("name", f"DE{number}")),
        d.get("encoding", ""),
    )


def profile_from_dict(data):
    elements = {}
    for key, d in data.get("elements", {}).items():
        try:
            n = int(key)
        except (ValueError, TypeError):
            continue
        elements[n] = fielddef_from_dict(n, d)
    return Profile(
        name=data.get("name", "sin_nombre"),
        protocol=data.get("protocol", "iso8583"),
        encoding=data.get("encoding", "auto"),
        has_length_field=bool(data.get("has_length_field", True)),
        length_field_bytes=int(data.get("length_field_bytes", 2)),
        has_tpdu=bool(data.get("has_tpdu", True)),
        tpdu_length=int(data.get("tpdu_length", 5)),
        mti_length_bytes=int(data.get("mti_length_bytes", 2)),
        bitmap_length_bytes=int(data.get("bitmap_length_bytes", 8)),
        supports_secondary_bitmap=bool(data.get("supports_secondary_bitmap", True)),
        elements=elements,
        description=data.get("description", ""),
        llvar_prefix_bytes=int(data.get("llvar_prefix_bytes", 1)),
        lllvar_prefix_bytes=int(data.get("lllvar_prefix_bytes", 2)),
        lllvar_4digit_bcd=bool(data.get("lllvar_4digit_bcd", False)),
        bcd_padding=str(data.get("bcd_padding", "trailing")),
    )


def load_json(path):
    """Carga un perfil desde un archivo JSON."""
    path = Path(path)
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    profile = profile_from_dict(data)
    profile._source = str(path)
    register(profile)
    return profile


def register(profile):
    _registry[profile.name] = profile
    return profile


def get(name):
    """Devuelve un perfil por nombre; si no existe, el perfil por defecto."""
    _ensure_builtin()
    if not name:
        return get_default()
    profile = _registry.get(name)
    if profile is not None:
        return profile
    return get_default()


def get_default():
    _ensure_builtin()
    return _registry[DEFAULT_PROFILE_NAME]


def _ensure_builtin():
    global _cache_valid
    if not _registry.get(DEFAULT_PROFILE_NAME):
        register(_build_default())
    if not _cache_valid:
        _load_specs_dir()
        _cache_valid = True


def _load_specs_dir():
    specs = _specs_dir()
    if not specs.exists():
        return
    for path in sorted(specs.glob("*.json")):
        try:
            load_json(path)
        except (OSError, ValueError):
            continue


def list_profiles():
    """Devuelve metadatos de todos los perfiles disponibles."""
    _ensure_builtin()
    out = []
    for name, profile in _registry.items():
        out.append({
            "name": profile.name,
            "protocol": profile.protocol,
            "encoding": profile.encoding,
            "elements": len(profile.elements),
            "description": profile.description,
        })
    return out
