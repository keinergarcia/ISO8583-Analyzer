# -*- coding: utf-8 -*-
"""Interpretación del MTI (Message Type Identifier)."""

from dataclasses import dataclass

VERSIONS = {
    "0": "ISO 8583:1987",
    "1": "ISO 8583:1993",
    "2": "ISO 8583:2003",
}

CLASSES = {
    "0": "Adquisición",
    "1": "Autorización",
    "2": "Transacción Financiera",
    "3": "Transferencia de Archivos",
    "4": "Reversa",
    "5": "Conciliación",
    "6": "Administración",
    "7": "Cambio de Claves",
    "8": "Gestión de Red",
}

FUNCTIONS = {
    "0": "Petición",
    "1": "Respuesta a Petición",
    "2": "Aviso",
    "3": "Respuesta a Aviso",
    "4": "Notificación",
    "5": "Respuesta a Notificación",
    "6": "Instrucción",
    "7": "Respuesta a Instrucción",
    "8": "Acuse de Recibo",
    "9": "Acuse Negativo",
}

ORIGINS = {
    "0": "Adquirente",
    "1": "Adquirente (repetición)",
    "2": "Emisor",
    "3": "Emisor (repetición)",
    "4": "Otro",
    "5": "Otro (repetición)",
    "6": "Agente de Autorización",
    "7": "Agente de Autorización (repetición)",
}

MTI_DESCRIPTIONS = {
    "0100": "Solicitud de Autorización",
    "0110": "Respuesta de Autorización",
    "0120": "Aviso de Autorización",
    "0130": "Respuesta de Aviso de Autorización",
    "0200": "Solicitud de Transacción Financiera",
    "0210": "Respuesta de Transacción Financiera",
    "0220": "Aviso Financiero",
    "0230": "Respuesta de Aviso Financiero",
    "0400": "Solicitud de Reversa",
    "0410": "Respuesta de Reversa",
    "0420": "Aviso de Reversa",
    "0430": "Respuesta de Aviso de Reversa",
    "0500": "Solicitud de Conciliación",
    "0510": "Respuesta de Conciliación",
    "0520": "Aviso de Conciliación",
    "0530": "Respuesta de Aviso de Conciliación",
    "0600": "Solicitud de Administración",
    "0610": "Respuesta de Administración",
    "0620": "Aviso de Administración",
    "0630": "Respuesta de Aviso de Administración",
    "0800": "Solicitud de Gestión de Red",
    "0810": "Respuesta de Gestión de Red",
    "0820": "Aviso de Gestión de Red",
    "0830": "Respuesta de Aviso de Gestión de Red",
}

# Conjunto de MTI válidos usados por el detector automático de inicio del
# mensaje: si un offset produce uno de estos MTI seguido de un bitmap válido,
# el parser lo adopta automáticamente como posición del MTI.
KNOWN_MTIS = frozenset(MTI_DESCRIPTIONS.keys())


@dataclass
class MtiInfo:
    hex: str
    description: str
    version: str
    message_class: str
    function: str
    origin: str

    def as_dict(self):
        return {
            "hex": self.hex,
            "description": self.description,
            "version": self.version,
            "message_class": self.message_class,
            "function": self.function,
            "origin": self.origin,
        }


def decode_mti(mti_hex):
    """Decodifica un MTI de 4 dígitos en sus componentes y descripción."""
    m = (mti_hex or "").upper()
    if len(m) != 4 or not m.isdigit():
        return MtiInfo(m, "MTI inválido", "", "", "", "")
    description = MTI_DESCRIPTIONS.get(m, "MTI no registrado")
    return MtiInfo(
        m,
        description,
        VERSIONS.get(m[0], "Versión desconocida"),
        CLASSES.get(m[1], "Clase desconocida"),
        FUNCTIONS.get(m[2], "Función desconocida"),
        ORIGINS.get(m[3], "Origen desconocido"),
    )
