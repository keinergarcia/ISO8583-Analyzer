# -*- coding: utf-8 -*-
"""Tests de perfiles (Profile, ProfileRegistry, carga JSON)."""

import json

from core.profiles import registry
from core.profiles.model import Profile


def test_default_profile():
    p = registry.get_default()
    assert p.name == "iso8583_1987"
    assert p.protocol == "iso8583"
    assert p.max_de >= 128
    assert p.data_element(3) is not None
    assert p.data_element(3).ftype == "n"


def test_list_profiles_include_specs():
    names = [p["name"] for p in registry.list_profiles()]
    assert "iso8583_1987" in names
    assert "iso8583_1993" in names
    assert "iso8583_2003" in names


def test_get_unknown_returns_default():
    assert registry.get("no_existe") is registry.get_default()


def test_get_loads_specs_before_lookup(monkeypatch):
    """get() debe cargar los specs antes de buscar: pedir un perfil como
    primera llamada (sin que el registro se haya poblado) debe devolver ese
    perfil y no caer silenciosamente en el perfil por defecto."""
    import core.profiles.registry as registry_mod
    monkeypatch.setattr(registry_mod, "_registry", {})
    monkeypatch.setattr(registry_mod, "_cache_valid", False)
    p = registry_mod.get("promerica")
    assert p.name == "promerica"
    assert p is registry_mod.get("promerica")


def test_load_json(tmp_path):
    data = {
        "name": "test_profile",
        "protocol": "iso8583",
        "encoding": "bcd",
        "elements": {
            "3": {"name": "Processing Code", "ftype": "n", "length": 6},
            "55": {"name": "EMV Data", "ftype": "b", "length": 999, "length_type": "lllvar"},
        },
    }
    path = tmp_path / "test.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    profile = registry.load_json(path)
    assert profile.name == "test_profile"
    assert profile.encoding == "bcd"
    assert profile.data_element(55).length_type == "lllvar"
    assert registry.get("test_profile") is profile


def test_fielddef_from_dict():
    from core.fields import FieldDef
    fd = registry.fielddef_from_dict(3, {"name": "PC", "ftype": "n", "length": 6})
    assert isinstance(fd, FieldDef)
    assert fd.number == 3 and fd.length == 6 and fd.ftype == "n"
