# -*- coding: utf-8 -*-
"""Definiciones de los Data Elements (DE) del estándar ISO 8583.

Cada campo define su tipo, longitud y si es de longitud fija o variable
(LLVAR / LLLVAR / LLLLVAR). La longitud de los campos numéricos se expresa
en dígitos; la de los campos alfanuméricos y binarios en bytes/caracteres.
"""


class FieldDef:
    """Definición estática de un Data Element."""

    def __init__(self, number, name, ftype, length, length_type="fixed", description="",
                 encoding=""):
        self.number = number
        self.name = name
        self.ftype = ftype
        self.length = length
        self.length_type = length_type
        self.description = description
        # "" = hereda la codificación global del mensaje; "bcd"|"ascii" la fuerza.
        self.encoding = encoding

    @property
    def is_variable(self):
        return self.length_type != "fixed"

    @property
    def is_numeric(self):
        return self.ftype == "n"

    @property
    def length_label(self):
        labels = {
            "fixed": "Fijo",
            "llvar": "LLVAR",
            "lllvar": "LLLVAR",
            "llllvar": "LLLLVAR",
        }
        return labels.get(self.length_type, self.length_type.upper())

    def __repr__(self):
        return f"DE{self.number} {self.name} ({self.ftype})"


def _def(number, name, ftype, length, length_type="fixed", encoding=""):
    return FieldDef(number, name, ftype, length, length_type, description=name, encoding=encoding)


DATA_ELEMENTS = {1: _def(1, "Bitmap", "b", 64)}

for _item in [
    (2, "Primary Account Number", "n", 19, "llvar"),
    (3, "Processing Code", "n", 6),
    (4, "Transaction Amount", "n", 12),
    (5, "Amount, Settlement", "n", 12),
    (6, "Amount, Cardholder Billing", "n", 12),
    (7, "Transmission Date & Time", "n", 10),
    (8, "Amount, Cardholder Billing Fee", "n", 8),
    (9, "Conversion Rate, Settlement", "n", 8),
    (10, "Conversion Rate, Cardholder Billing", "n", 8),
    (11, "System Trace Audit Number", "n", 6),
    (12, "Time, Local Transaction", "n", 6),
    (13, "Date, Local Transaction", "n", 4),
    (14, "Date, Card Expiration", "n", 4),
    (15, "Date, Settlement", "n", 4),
    (16, "Date, Conversion", "n", 4),
    (17, "Date, Capture", "n", 4),
    (18, "Merchant Type", "n", 4),
    (19, "Acquiring Institution Country Code", "n", 3),
    (20, "PAN Extended Country Code", "n", 3),
    (21, "Forwarding Institution Country Code", "n", 3),
    (22, "Point of Service Entry Mode", "n", 3),
    (23, "Card Sequence Number", "n", 3),
    (24, "Network International Identifier (NII)", "n", 3),
    (25, "Point of Service Condition Mode", "n", 2),
    (26, "Point of Service Capture Code", "n", 2),
    (27, "Authorizing Identification Response Length", "n", 1),
    (28, "Amount, Transaction Fee", "n", 9),
    (29, "Amount, Settlement Fee", "n", 9),
    (30, "Amount, Transaction Processing Fee", "n", 9),
    (31, "Amount, Settlement Processing Fee", "n", 9),
    (32, "Acquiring Institution Identification Code", "n", 11, "llvar"),
    (33, "Sending Institution Identification Code", "n", 11, "llvar"),
    (34, "PAN Extended", "n", 28, "llvar"),
    (35, "Track 2 Data", "z", 37, "llvar"),
    (36, "Track 3 Data", "n", 104, "lllvar"),
    (37, "Retrieval Reference Number", "an", 12),
    (38, "Authorization Identification Response", "an", 6),
    (39, "Response Code", "n", 3),
    (40, "Service Restriction Code", "n", 3),
    (41, "Terminal ID", "ans", 8),
    (42, "Merchant ID", "ans", 15),
    (43, "Card Acceptor Name/Location", "ans", 40),
    (44, "Additional Response Data", "an", 25, "llvar"),
    (45, "Track 1 Data", "an", 76, "llvar"),
    (46, "Additional Data - ISO", "an", 999, "lllvar"),
    (47, "Additional Data - National", "an", 999, "lllvar"),
    (48, "Additional Data - Private", "an", 999, "lllvar"),
    (49, "Currency Code", "n", 3),
    (50, "Currency Code, Settlement", "n", 3),
    (51, "Currency Code, Cardholder Billing", "n", 3),
    (52, "Personal Identification Number Data", "b", 8),
    (53, "Security Related Control Information", "n", 16),
    (54, "Amount, Cardholder Billing Fee", "an", 24),
    (55, "EMV Data", "b", 999, "lllvar"),
    (56, "Reserved for ISO use", "n", 17),
    (57, "Reserved for ISO use", "n", 3),
    (58, "Reserved for ISO use", "n", 11),
    (59, "Reserved for National use", "n", 4),
    (60, "Reserved National", "n", 999, "llvar"),
    (61, "Reserved for National use", "an", 999, "lllvar"),
    (62, "Reserved for Private use", "an", 999, "lllvar"),
    (63, "Reserved Private", "an", 999, "llvar"),
    (64, "MAC", "b", 8),
    (65, "Bitmap, Extended", "b", 64),
    (70, "Network Management Information Code", "n", 3),
    (90, "Original Data Elements", "n", 42),
    (91, "File Update Code", "an", 1),
    (92, "File Security Code", "n", 5),
    (93, "Response Indicator", "n", 5),
    (94, "Service Indicator", "an", 7),
    (95, "Replacement Amounts", "an", 42),
    (96, "Message Security Code", "b", 8),
    (97, "Amount, Net Reconciliation", "n", 16),
    (98, "Payee", "an", 25),
    (99, "Settlement Institution Identification Code", "n", 11, "llvar"),
    (100, "Receiving Institution Identification Code", "n", 11, "llvar"),
    (101, "File Name", "ans", 17),
    (102, "Account Identification 1", "ans", 28, "llvar"),
    (103, "Account Identification 2", "ans", 28, "llvar"),
    (104, "Transaction Description", "ans", 100, "lllvar"),
    (120, "Relay Data", "ans", 999, "lllvar"),
    (121, "Relay Data", "ans", 999, "lllvar"),
    (122, "Reserved for Private use", "ans", 999, "lllvar"),
    (123, "Reserved for Private use", "ans", 999, "lllvar"),
    (124, "Reserved for Private use", "ans", 999, "lllvar"),
    (125, "Reserved for Private use", "ans", 999, "lllvar"),
    (126, "Reserved for Private use", "ans", 999, "lllvar"),
    (127, "Reserved for Private use", "ans", 999, "lllvar"),
    (128, "Reserved for Private use", "b", 8),
]:
    _n, _name, _t, _l = _item[0], _item[1], _item[2], _item[3]
    _lt = _item[4] if len(_item) > 4 else "fixed"
    DATA_ELEMENTS[_n] = _def(_n, _name, _t, _l, _lt)


def get_field(number):
    """Devuelve la definición del campo o None si no existe."""
    return DATA_ELEMENTS.get(number)


def describe(number):
    """Devuelve el nombre legible de un Data Element."""
    f = DATA_ELEMENTS.get(number)
    return f.name if f else "Reserved"


SPANISH_NAMES = {
    1: "Mapa de Bits",
    2: "Número de Cuenta Principal (PAN)",
    3: "Código de Procesamiento",
    4: "Monto de Transacción",
    5: "Monto, Liquidación",
    6: "Monto, Facturación del Titular",
    7: "Fecha y Hora de Transmisión",
    8: "Comisión, Facturación del Titular",
    9: "Tasa de Conversión, Liquidación",
    10: "Tasa de Conversión, Facturación del Titular",
    11: "Número de Traza (STAN)",
    12: "Hora, Transacción Local",
    13: "Fecha, Transacción Local",
    14: "Fecha de Expiración de la Tarjeta",
    15: "Fecha, Liquidación",
    16: "Fecha, Conversión",
    17: "Fecha, Captura",
    18: "Tipo de Comercio (MCC)",
    19: "Código de País de la Institución Adquirente",
    20: "Código de País Extendido del PAN",
    21: "Código de País de la Institución Receptora",
    22: "Modo de Ingreso en el Punto de Servicio",
    23: "Número de Secuencia de la Tarjeta",
    24: "Identificador Internacional de Red (NII)",
    25: "Modo de Condición del Punto de Servicio",
    26: "Código de Captura del Punto de Servicio",
    27: "Longitud de Identificación de Respuesta de Autorización",
    28: "Comisión, Transacción",
    29: "Comisión, Liquidación",
    30: "Comisión, Procesamiento de Transacción",
    31: "Comisión, Procesamiento de Liquidación",
    32: "Código de Identificación de la Institución Adquirente",
    33: "Código de Identificación de la Institución Emisora",
    34: "PAN Extendido",
    35: "Datos de Banda 2 (Track 2)",
    36: "Datos de Banda 3 (Track 3)",
    37: "Número de Referencia (RRN)",
    38: "Identificación de Respuesta de Autorización",
    39: "Código de Respuesta",
    40: "Código de Restricción de Servicio",
    41: "ID de Terminal",
    42: "ID de Comercio",
    43: "Nombre/Ubicación del Aceptador",
    44: "Datos Adicionales de Respuesta",
    45: "Datos de Banda 1 (Track 1)",
    46: "Datos Adicionales - ISO",
    47: "Datos Adicionales - Nacionales",
    48: "Datos Adicionales - Privados",
    49: "Código de Moneda",
    50: "Código de Moneda, Liquidación",
    51: "Código de Moneda, Facturación del Titular",
    52: "Datos del PIN",
    53: "Información de Control de Seguridad",
    54: "Monto, Comisión de Facturación del Titular",
    55: "Datos EMV",
    56: "Reservado para uso ISO",
    57: "Reservado para uso ISO",
    58: "Reservado para uso ISO",
    59: "Reservado para uso Nacional",
    60: "Nacional Reservado",
    61: "Reservado para uso Nacional",
    62: "Reservado para uso Privado",
    63: "Privado Reservado",
    64: "Código de Autenticación de Mensaje (MAC)",
    65: "Mapa de Bits Extendido",
    70: "Código de Información de Gestión de Red",
    90: "Elementos de Datos Originales",
    91: "Código de Actualización de Archivo",
    92: "Código de Seguridad de Archivo",
    93: "Indicador de Respuesta",
    94: "Indicador de Servicio",
    95: "Montos de Reemplazo",
    96: "Código de Seguridad del Mensaje",
    97: "Monto Neto de Conciliación",
    98: "Beneficiario",
    99: "Código de Identificación de la Institución de Liquidación",
    100: "Código de Identificación de la Institución Receptora",
    101: "Nombre de Archivo",
    102: "Identificación de Cuenta 1",
    103: "Identificación de Cuenta 2",
    104: "Descripción de Transacción",
    120: "Datos de Relevo",
    121: "Datos de Relevo",
    122: "Reservado para uso Privado",
    123: "Reservado para uso Privado",
    124: "Reservado para uso Privado",
    125: "Reservado para uso Privado",
    126: "Reservado para uso Privado",
    127: "Reservado para uso Privado",
    128: "Reservado para uso Privado",
}


def translate(number):
    """Traducción al español del nombre de un Data Element.

    Devuelve el nombre en español si existe; si no, el nombre original.
    """
    es = SPANISH_NAMES.get(number)
    if es:
        return es
    f = DATA_ELEMENTS.get(number)
    return f.name if f else "Reservado"
