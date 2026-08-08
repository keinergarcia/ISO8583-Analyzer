# -*- coding: utf-8 -*-
"""Tests de la capa de interpretación de campos (FieldInterpreter).

Valida la trama de referencia (DE3, DE11, DE39, DE41, DE60) y que la nueva
clasificación no altera el parseo ni el valor de los campos.
"""

import core.api as api
from core.exporter import result_to_json, result_to_text
from core.field_interpreter import FieldInterpreter, interpret
from core.parser import ParseOptions, parse_message

PROMERICA_PROFILE = "promerica"

FRAME_VALIDATION = (
    "0064608000000108102020000002800010"
    "93001000008530313630303030363635"
    "006741435455414C495A4143494F4E204445434C494E41444120434F4E46494755524143494F4E205820475255504F202D20484F52412046554552412044452052414E474F"
)


def _parse():
    return api.decode(FRAME_VALIDATION, profile_name=PROMERICA_PROFILE).legacy


def _fields(result):
    return {f.number: f for f in result.fields}


def test_frame_still_parses_same_fields():
    r = _parse()
    assert [f.number for f in r.fields] == [3, 11, 39, 41, 60]
    assert not r.errors


def test_de60_value_unchanged():
    r = _parse()
    assert _fields(r)[60].value == (
        "ACTUALIZACION DECLINADA CONFIGURACION X GRUPO - HORA FUERA DE RANGO"
    )
    assert _fields(r)[3].value == "930010"
    assert _fields(r)[11].value == "000085"
    assert _fields(r)[39].value == "01"
    assert _fields(r)[41].value == "60000665"


def test_config_is_loaded_from_fields_json():
    it = FieldInterpreter()
    assert it.getDescription(3) == "Processing Code"
    assert it.getDescription(60) == "Reserved National Message"
    assert it.getDescription(999) == ""


def test_detect_field_type():
    it = FieldInterpreter()
    f = _fields(_parse())
    assert it.detectFieldType(f[3]) == "code"
    assert it.detectFieldType(f[11]) == "identifier"
    assert it.detectFieldType(f[39]) == "response_code"
    assert it.detectFieldType(f[41]) == "identifier"
    assert it.detectFieldType(f[60]) == "text"


def test_is_text_and_is_code():
    it = FieldInterpreter()
    f = _fields(_parse())
    assert it.isTextField(f[60])
    assert not it.isTextField(f[39])
    assert it.isCodeField(f[39])
    assert it.isCodeField(f[3])
    assert not it.isCodeField(f[60])
    assert not it.isCodeField(f[41])


def test_not_every_field_is_classified_as_text():
    """Solo los campos configurados como texto se clasifican como mensaje."""
    it = FieldInterpreter()
    f = _fields(_parse())
    cats = [it.detectFieldType(f[n]) for n in (3, 11, 39, 41, 60)]
    assert cats.count("text") == 1


def test_default_rules_without_config():
    """Sin configuración: los nombres con 'code' son código, otros 'data'."""
    it = FieldInterpreter(config_path="__no_existe__.json")
    f = _fields(_parse())
    assert it.detectFieldType(f[3]) == "code"          # Processing Code
    assert it.detectFieldType(f[39]) == "response_code"
    assert it.detectFieldType(f[11]) == "data"         # no matchea keywords
    assert it.detectFieldType(f[60]) == "data"         # nunca texto por heurística


def test_report_contains_interpretation_section():
    txt = result_to_text(_parse())
    assert "--- Interpretación del Campo ---" in txt
    assert "DE60 detectado como:" in txt
    assert "Mensaje de texto" in txt
    assert "ACTUALIZACION DECLINADA CONFIGURACION X GRUPO - HORA FUERA DE RANGO" in txt
    assert "Clasificación: Código" in txt
    assert "DE39 detectado como:" in txt
    assert "Código de respuesta" in txt


def test_json_export_includes_interpretation():
    import json
    data = json.loads(result_to_json(_parse()))
    by_number = {f["number"]: f for f in data["fields"]}
    assert by_number[60]["interpretation"]["category"] == "text"
    assert by_number[60]["interpretation"]["summary"] == "Mensaje de texto"
    assert by_number[3]["interpretation"]["category"] == "code"
    assert by_number[60]["value"] == (
        "ACTUALIZACION DECLINADA CONFIGURACION X GRUPO - HORA FUERA DE RANGO"
    )

