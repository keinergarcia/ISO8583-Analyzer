# -*- coding: utf-8 -*-
"""Fachada pública de la aplicación (core.api).

Única puerta de entrada recomendada para la UI, plugins y scripts.
Mantiene compatibilidad total con la API previa: parse_message,
AnalysisResult, ParseOptions, ParseError y core.converters siguen
disponibles y funcionando.
"""

from . import converters
from .issues import IssueList, ValidationIssue
from .model.message import DecodedNode, Message
from .parser import ParseError, ParseOptions, parse_message
from .protocols.iso8583 import decoder as _iso8583_decoder  # noqa: F401  (registra el decoder)
from .protocols.registry import get_decoder as _get_decoder
from .profiles import registry as profile_registry
from .services.session import get_session
from .tools import bitmap_view, dictionary, formatter

session = get_session()


def list_profiles():
    return profile_registry.list_profiles()


def load_profile(name):
    return profile_registry.get(name)


def get_default_profile():
    return profile_registry.get_default()


def list_decoders():
    from .protocols.registry import list_decoders as _list
    return _list()


def decode(raw, profile_name=None, options=None, protocol=None):
    """Decodifica una trama y devuelve un Message (árbol universal).

    Lanza ParseError si la entrada es inválida (misma semántica que
    parse_message). `profile_name=None` usa el perfil por defecto.
    """
    profile = profile_registry.get(profile_name)
    decoder = _get_decoder(protocol or profile.protocol)
    if decoder is None:
        raise ValueError(f"Protocolo no soportado: {protocol or profile.protocol}")
    return decoder.decode(raw, profile, options=options)


def _score_parse(result):
    """Puntúa un resultado de análisis para comparar perfiles entre sí.

    Premia: cero errores, pocas advertencias, más campos leídos y coincidencia
    de longitud. Penaliza: campos variables interpretados con longitud 0
    (síntoma clásico de un layout de prefijo incorrecto) y campos con error.
    """
    if result.errors:
        return -100000
    score = 100 - 10 * len(result.warnings)
    score += 2 * len(result.fields)
    if result.consumed_hex and result.declared_hex:
        if result.consumed_hex == result.declared_hex:
            score += 50
    for f in result.fields:
        if f.has_error:
            score -= 50
        elif f.length_type != "fixed" and f.length_digits == 0:
            score -= 10
    return score


def pick_profile(raw, options=None):
    """Devuelve el nombre del perfil que mejor analiza la trama.

    Prueba todos los perfiles registrados y puntúa cada resultado. En empate
    gana el que aparezca primero (el perfil por defecto). Devuelve None si
    ningún perfil pudo analizar la trama.
    """
    from .parser import ParseError

    best_name = None
    best_score = None
    for meta in profile_registry.list_profiles():
        name = meta["name"]
        try:
            msg = decode(raw, profile_name=name, options=options)
        except ParseError:
            continue
        score = _score_parse(msg.legacy)
        if best_score is None or score > best_score:
            best_score = score
            best_name = name
    return best_name


def analyze(raw, profile_name=None, options=None, protocol=None):
    """Alias de decode()."""
    return decode(raw, profile_name=profile_name, options=options, protocol=protocol)


def validate(message):
    """Devuelve la lista de issues de validación del mensaje."""
    if isinstance(message, Message):
        return message.issues
    return IssueList()


def format_frame(hex_str, style="hex", cols=16):
    return formatter.render(hex_str, style, cols)


def format_rows(hex_str, style="hex", cols=16):
    return formatter.render_rows(hex_str, style, cols)


def bitmap_table(message=None, profile_name=None):
    return bitmap_view.de_table(message, profile_registry.get(profile_name))


def bitmap_summary(message=None, profile_name=None):
    return bitmap_view.summary(message, profile_registry.get(profile_name))


def dictionary_all(profile_name=None):
    return dictionary.all_fields(profile_registry.get(profile_name))


def dictionary_search(query, profile_name=None):
    return dictionary.search(profile_registry.get(profile_name), query)


__all__ = [
    "Message", "DecodedNode", "IssueList", "ValidationIssue",
    "ParseError", "ParseOptions", "parse_message",
    "decode", "analyze", "validate", "list_profiles", "load_profile",
    "get_default_profile", "list_decoders", "format_frame", "format_rows",
    "bitmap_table", "bitmap_summary", "dictionary_all", "dictionary_search",
    "pick_profile",
    "session", "converters",
]
