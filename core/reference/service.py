# -*- coding: utf-8 -*-
"""Centro de Referencia ISO 8583 — servicio de datos.

Carga todos los catálogos JSON y ofrece consultas (ficha de campo, MTI,
código de respuesta, moneda, tipos, versiones, perfiles) y búsqueda global,
con soporte bilingüe (es / en).

La UI y los scripts DEBEN acceder solo mediante este servicio (o la fachada
core.api), nunca leer los archivos JSON directamente.
"""

import json
import sys
import unicodedata
from pathlib import Path

# Nombre del archivo JSON → clave de catálogo dentro del JSON.
CATALOGS = {
    "fields": "fields",
    "mti": "mtis",
    "response_codes": "response_codes",
    "currencies": "currencies",
    "versions": "versions",
    "data_types": "data_types",
    "length_types": "length_types",
    "profiles": "profiles",
    "emv_tags": "emv_tags",
}

LANGS = ("en", "es")


def _norm(text):
    """Minúsculas y sin acentos, para búsquedas tolerantes."""
    text = unicodedata.normalize("NFD", str(text or ""))
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return text.lower()


class ReferenceService:
    """Servicio de consulta de la información de referencia ISO 8583."""

    def __init__(self, data_dir=None):
        if data_dir is None:
            base = Path(sys._MEIPASS) if getattr(sys, "frozen", False) \
                else Path(__file__).resolve().parent.parent.parent
            data_dir = base / "core" / "reference" / "data"
        self._dir = data_dir
        self._cache = {}

    # ------------------------------------------------------------- carga
    def _load(self, name):
        if name not in self._cache:
            path = self._dir / f"{name}.json"
            with open(path, "r", encoding="utf-8") as fh:
                self._cache[name] = json.load(fh)
        return self._cache[name]

    def _catalog(self, name):
        return self._load(name)[CATALOGS[name]]

    # ------------------------------------------------------------- util
    @staticmethod
    def loc(entry, key, lang):
        """Extrae y localiza un valor (admite string o {en, es})."""
        val = entry.get(key)
        if isinstance(val, dict):
            return val.get(lang) or val.get("en") or val.get("es") or ""
        return "" if val is None else str(val)

    def languages(self):
        return list(LANGS)

    # --------------------------------------------------------- catálogos
    def field(self, number, lang=None):
        num = str(number)
        for e in self._catalog("fields"):
            if str(e["number"]) == num:
                return e
        return None

    def fields(self, lang=None):
        return list(self._catalog("fields"))

    def mti(self, code, lang=None):
        code = str(code).upper()
        for e in self._catalog("mti"):
            if str(e["code"]) == code:
                return e
        return None

    def mtis(self, lang=None):
        return list(self._catalog("mti"))

    def response_code(self, code, lang=None):
        code = str(code).zfill(2)
        for e in self._catalog("response_codes"):
            if str(e["code"]).zfill(2) == code:
                return e
        return None

    def response_codes(self, lang=None):
        return list(self._catalog("response_codes"))

    def currency(self, code, lang=None):
        code = str(code).strip().upper()
        for e in self._catalog("currencies"):
            if str(e["numeric"]) == code or e["alpha"].upper() == code:
                return e
        return None

    def currencies(self, lang=None):
        return list(self._catalog("currencies"))

    def versions(self, lang=None):
        return list(self._catalog("versions"))

    def data_types(self, lang=None):
        return list(self._catalog("data_types"))

    def length_types(self, lang=None):
        return list(self._catalog("length_types"))

    def profiles(self, lang=None):
        return list(self._catalog("profiles"))

    def emv_tag(self, tag, lang=None):
        tag = str(tag).strip().upper()
        for e in self._catalog("emv_tags"):
            if str(e["tag"]).strip().upper() == tag:
                return e
        return None

    def emv_tags(self, lang=None):
        return list(self._catalog("emv_tags"))

    # ----------------------------------------------------------- búsqueda
    def search(self, query, lang="es", limit=60):
        q = _norm(query)
        if not q:
            return []
        hits = []
        append = hits.append

        for e in self._catalog("fields"):
            blob = " ".join([
                str(e["number"]),
                _norm(self.loc(e, "name", "en")), _norm(self.loc(e, "name", "es")),
                _norm(self.loc(e, "description", "en")), _norm(self.loc(e, "description", "es")),
                " ".join(p for p in e.get("profiles", [])),
            ])
            if q in blob:
                append({"kind": "field", "code": str(e["number"]), "entry": e})

        for e in self._catalog("mti"):
            if (q == _norm(str(e["code"])) or
                    q in _norm(self.loc(e, "name", "en") + self.loc(e, "name", "es"))):
                append({"kind": "mti", "code": str(e["code"]), "entry": e})

        for e in self._catalog("response_codes"):
            if (q == _norm(str(e["code"])) or
                    q in _norm(self.loc(e, "name", "en") + self.loc(e, "name", "es"))):
                append({"kind": "response_code", "code": str(e["code"]), "entry": e})

        for e in self._catalog("currencies"):
            blob = " ".join([
                str(e["numeric"]), e["alpha"].upper(),
                _norm(self.loc(e, "name", "en")), _norm(self.loc(e, "name", "es")),
                _norm(self.loc(e, "country", "es")), _norm(self.loc(e, "country", "en")),
            ])
            if q in blob:
                append({"kind": "currency", "code": e["alpha"], "entry": e})

        for e in self._catalog("data_types"):
            if (q == _norm(str(e["code"])) or
                    q in _norm(self.loc(e, "name", "en") + self.loc(e, "name", "es"))):
                append({"kind": "data_type", "code": str(e["code"]), "entry": e})

        for e in self._catalog("length_types"):
            if (q == _norm(str(e["code"])) or
                    q in _norm(self.loc(e, "name", "en") + self.loc(e, "name", "es"))):
                append({"kind": "length_type", "code": str(e["code"]), "entry": e})

        for e in self._catalog("versions"):
            blob = str(e["code"]) + _norm(self.loc(e, "name", "en")) + _norm(self.loc(e, "name", "es"))
            if q in blob:
                append({"kind": "version", "code": str(e["code"]), "entry": e})

        for e in self._catalog("profiles"):
            blob = (_norm(self.loc(e, "name", "en")) + _norm(self.loc(e, "title", "en")) +
                    _norm(self.loc(e, "name", "es")) + _norm(self.loc(e, "title", "es")))
            if q in blob:
                append({"kind": "profile", "code": str(e.get("name", "")), "entry": e})

        for e in self._catalog("emv_tags"):
            if (q == _norm(str(e["tag"])) or
                    q in _norm(self.loc(e, "name", "en") + self.loc(e, "name", "es"))):
                append({"kind": "emv_tag", "code": str(e["tag"]), "entry": e})

        return hits[:limit]


_reference = None


def get_reference():
    """Devuelve la instancia única del servicio de referencia."""
    global _reference
    if _reference is None:
        _reference = ReferenceService()
    return _reference