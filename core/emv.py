# -*- coding: utf-8 -*-
"""Decodificador EMV (Campo 55) basado en BER-TLV.

Parsea los tags EMV y muestra su significado según el diccionario EMV.
Los tags construidos (ej. 6F, A5, 9F10) se recorren de forma recursiva.
"""

from dataclasses import dataclass, field
from typing import List

from .converters import bcd_to_decimal
from .transaction_summary import _format_amount


@dataclass
class TlvNode:
    tag: str
    name: str
    length: int
    value_hex: str
    value_ascii: str
    constructed: bool
    note: str = ""
    interpretation: str = ""
    children: List["TlvNode"] = field(default_factory=list)

    def as_dict(self):
        return {
            "tag": self.tag,
            "name": self.name,
            "length": self.length,
            "value_hex": self.value_hex,
            "value_ascii": self.value_ascii,
            "constructed": self.constructed,
            "note": self.note,
            "interpretation": self.interpretation,
            "children": [c.as_dict() for c in self.children],
        }


TAG_DICTIONARY = {
    "4F": "Application Identifier (AID)",
    "50": "Application Label",
    "57": "Track 2 Equivalent Data",
    "5A": "Application Primary Account Number (PAN)",
    "5F20": "Application Currency Code",
    "5F24": "Application Expiration Date",
    "5F25": "Application Effective Date",
    "5F2A": "Transaction Currency Code",
    "5F30": "Service Code",
    "5F34": "Application PAN Sequence Number",
    "5F50": "Issuer URL",
    "61": "Application Template",
    "70": "EMV Proprietary Template",
    "71": "Issuer Script Template 1",
    "72": "Issuer Script Template 2",
    "77": "Response Message Template Format 2",
    "82": "Application Interchange Profile (AIP)",
    "84": "Dedicated File (DF) Name",
    "87": "Application Priority Indicator",
    "88": "Short File Identifier (SFI)",
    "8A": "Authorisation Response Code",
    "8C": "Card Risk Management Data Object List 1 (CDOL1)",
    "8D": "Card Risk Management Data Object List 2 (CDOL2)",
    "8E": "Cardholder Verification Method (CVM) List",
    "8F": "Certification Authority Public Key Index",
    "90": "Issuer Public Key Certificate",
    "91": "Issuer Authentication Data",
    "92": "Issuer Public Key Remainder",
    "93": "Signed Static Application Data",
    "94": "Application File Locator (AFL)",
    "95": "Terminal Verification Results (TVR)",
    "9A": "Transaction Date",
    "9B": "Transaction Status Information",
    "9C": "Transaction Type",
    "9F02": "Amount, Authorised (Numeric)",
    "9F03": "Amount, Other (Numeric)",
    "9F06": "Application Identifier (AID) - Terminal",
    "9F07": "Application Usage Control",
    "9F09": "Application Version Number",
    "9F0D": "Issuer Action Code - Default",
    "9F0E": "Issuer Action Code - Denial",
    "9F0F": "Issuer Action Code - Online",
    "9F10": "Issuer Application Data (IAD)",
    "9F11": "Issuer Code Table Index",
    "9F12": "Application Preferred Name",
    "9F13": "Application Currency Exponent",
    "9F14": "Terminal Currency Exponent",
    "9F15": "Merchant Category Code",
    "9F16": "Merchant Identifier",
    "9F17": "PIN Try Counter",
    "9F18": "Issuer Script Identifier",
    "9F1A": "Terminal Country Code",
    "9F1E": "Interface Device (IFD) Serial Number",
    "9F1F": "Track 1 Discretionary Data",
    "9F20": "Track 2 Discretionary Data",
    "9F21": "Transaction Time",
    "9F26": "Application Cryptogram",
    "9F27": "Cryptogram Information Data",
    "9F2D": "ICC PIN Encipherment Public Key Certificate",
    "9F2E": "ICC PIN Encipherment Public Key Exponent",
    "9F2F": "ICC PIN Encipherment Public Key Modulus",
    "9F32": "Issuer Public Key Exponent",
    "9F33": "Terminal Capabilities",
    "9F34": "Cardholder Verification Method (CVM) Results",
    "9F35": "Terminal Type",
    "9F36": "Application Transaction Counter (ATC)",
    "9F37": "Unpredictable Number",
    "9F40": "Issuer Authorization Requested Amount",
    "9F41": "Transaction Sequence Counter",
    "9F42": "Application Currency Exponent",
    "9F43": "Application Reference Currency",
    "9F44": "Application Reference Currency Exponent",
    "9F45": "Data Authentication Code",
    "9F46": "ICC Public Key Certificate",
    "9F47": "ICC Public Key Exponent",
    "9F48": "ICC Public Key Modulus",
    "9F49": "Dynamic Data Authentication Data Object List (DDOL)",
    "9F4A": "Static Data Authentication Tag List (SDAT)",
    "9F4B": "Signed Dynamic Application Data",
    "9F4C": "ICC Dynamic Number",
    "9F4D": "Log Entry",
    "9F4E": "Merchant Name and Location",
    "9F5A": "Application Program Identifier (API)",
    "9F6B": "Track 2 Equivalent Data",
    "9F6E": "Third Party Data",
    "9F7C": "Merchant Custom Data",
}

CONSTRUCTED_TAGS = {"6F", "A5", "BF0C", "77", "70", "61", "71", "72", "9F10"}

# Spanish tag names (parallel dictionary for reference/UI display)
SPANISH_TAGS = {
    "4F": "Identificador de aplicación",
    "50": "Etiqueta de aplicación",
    "57": "Datos equivalentes del Track 2",
    "5A": "Número principal de cuenta de la aplicación",
    "5F20": "Código de moneda de aplicación",
    "5F24": "Fecha de expiración de aplicación",
    "5F25": "Fecha de efectividad de aplicación",
    "5F2A": "Código de moneda de la transacción",
    "5F30": "Código de servicio",
    "5F34": "Número de secuencia del PAN de la aplicación",
    "5F50": "URL del emisor",
    "61": "Plantilla de aplicación",
    "70": "Plantilla propietaria EMV",
    "71": "Plantilla de script del emisor 1",
    "72": "Plantilla de script del emisor 2",
    "77": "Formato de mensaje de respuesta 2",
    "82": "Perfil de intercambio de la aplicación",
    "84": "Nombre de archivo dedicado",
    "87": "Indicador de prioridad de aplicación",
    "88": "Identificador de archivo corto",
    "8A": "Código de respuesta de autorización",
    "8C": "Lista de objetos de gestión de riesgo de tarjeta 1",
    "8D": "Lista de objetos de gestión de riesgo de tarjeta 2",
    "8E": "Lista de métodos de verificación del titular",
    "8F": "Índice de clave pública de la autoridad de certificación",
    "90": "Certificado de clave pública del emisor",
    "91": "Datos de autenticación del emisor",
    "92": "Resto de la clave pública del emisor",
    "93": "Datos estáticos de aplicación firmados",
    "94": "Localizador de archivo de aplicación",
    "95": "Resultados de verificación del terminal",
    "9A": "Fecha de la transacción",
    "9B": "Información del estado de la transacción",
    "9C": "Tipo de transacción",
    "9F02": "Importe autorizado",
    "9F03": "Otro importe",
    "9F06": "Identificador de aplicación - Terminal",
    "9F07": "Control de uso de aplicación",
    "9F09": "Número de versión de la aplicación",
    "9F0D": "Código de acción del emisor - Default",
    "9F0E": "Código de acción del emisor - Denegación",
    "9F0F": "Código de acción del emisor - En línea",
    "9F10": "Datos de aplicación del emisor",
    "9F11": "Índice de tabla de códigos del emisor",
    "9F12": "Nombre preferido de aplicación",
    "9F13": "Expónente de moneda de aplicación",
    "9F14": "Expónente de moneda del terminal",
    "9F15": "Código de categoría de comerciante (MCC)",
    "9F16": "Identificador de comerciante",
    "9F17": "Contador de intentos de PIN",
    "9F18": "Identificador de script del emisor",
    "9F1A": "Código de país del terminal",
    "9F1E": "Número de serie del dispositivo de interfaz",
    "9F1F": "Datos discretos del Track 1",
    "9F20": "Datos discretos del Track 2",
    "9F21": "Hora de la transacción",
    "9F26": "Criptograma de la aplicación",
    "9F27": "Datos de información del criptograma",
    "9F2D": "Certificado de clave pública de cifrado PIN ICC",
    "9F2E": "Expónente de clave pública de cifrado PIN ICC",
    "9F2F": "Módulo de clave pública de cifrado PIN ICC",
    "9F32": "Expónente de clave pública del emisor",
    "9F33": "Capacidades del terminal",
    "9F34": "Resultados del método de verificación del titular",
    "9F35": "Tipo de terminal",
    "9F36": "Contador de transacciones de la aplicación",
    "9F37": "Número impredecible",
    "9F40": "Solicitado importe de autorización del emisor",
    "9F41": "Contador de secuencia de transacciones",
    "9F42": "Expónente de moneda de aplicación",
    "9F43": "Moneda de referencia de aplicación",
    "9F44": "Expónente de moneda de referencia de aplicación",
    "9F45": "Código de autenticación de datos",
    "9F46": "Certificado de clave pública ICC",
    "9F47": "Expónente de clave pública ICC",
    "9F48": "Módulo de clave pública ICC",
    "9F49": "Lista de objetos de datos de autenticación dinámica",
    "9F4A": "Lista de etiquetas de autenticación estática",
    "9F4B": "Datos dinámicos de aplicación firmados",
    "9F4C": "Número dinámico ICC",
    "9F4D": "Entrada de registro",
    "9F4E": "Nombre y ubicación del comerciante",
    "9F5A": "Identificador de programa de aplicación",
    "9F6B": "Datos equivalentes del Track 2",
    "9F6E": "Datos de terceros",
    "9F7C": "Datos personalizados del comerciante",
}

CURRENCIES = {
    "032": "ARS (Peso argentino)",
    "124": "CAD (Dólar canadiense)",
    "152": "CLP (Peso chileno)",
    "170": "COP (Peso colombiano)",
    "484": "MXN (Peso mexicano)",
    "604": "PEN (Sol peruano)",
    "840": "USD (Dólar estadounidense)",
    "978": "EUR (Euro)",
    "826": "GBP (Libra esterlina)",
    "392": "JPY (Yen japonés)",
    "986": "BRL (Real brasileño)",
}

TX_TYPES = {
    "00": "Bienes y servicios",
    "01": "Efectivo",
    "02": "Devolución",
    "03": "Ajuste",
    "09": "Consulta",
    "20": "Venta de efectivo",
    "22": "Servicios con cargo",
    "27": "Efectivo de cajero automático",
    "30": "Consumo sin terminal",
    "90": "Consulta de saldo",
}

CRYPTOGRAM_INFO = {
    "00": "AAC (Transacción rechazada)",
    "40": "TC (Transacción completada)",
    "80": "ARQC (Solicitud de criptograma en línea)",
}


def _read_tag(buf, i):
    first = int(buf[i:i + 2], 16)
    i += 2
    if first & 0x1F == 0x1F:
        tag = format(first, "02X")
        while True:
            b = int(buf[i:i + 2], 16)
            i += 2
            tag += format(b, "02X")
            if not (b & 0x80):
                break
    else:
        tag = format(first, "02X")
    constructed = bool(first & 0x20)
    return tag, constructed, i


def _read_length(buf, i):
    first = int(buf[i:i + 2], 16)
    i += 2
    if first < 0x80:
        return first, i
    n = first & 0x7F
    if n == 0:
        raise ValueError("Longitud indefinida no soportada")
    if i + n * 2 > len(buf):
        raise ValueError("Prefijo de longitud truncado")
    value = int(buf[i:i + n * 2], 16)
    i += n * 2
    return value, i


def _to_ascii(value_hex):
    try:
        raw = bytes.fromhex(value_hex)
    except ValueError:
        return ""
    return "".join(chr(b) if 0x20 <= b <= 0x7E else "." for b in raw)


def _interpret(tag, value_hex):
    value_hex = value_hex.upper()
    if tag == "9F27":
        return CRYPTOGRAM_INFO.get(value_hex, "")
    if tag == "9C":
        return TX_TYPES.get(value_hex, "")
    if tag == "9A":
        if len(value_hex) >= 6:
            y, m, d = value_hex[0:2], value_hex[2:4], value_hex[4:6]
            return f"Fecha {d}/{m}/{y}"
        return ""
    if tag in ("5F2A", "5F20", "9F1A"):
        try:
            digits = bcd_to_decimal(value_hex).lstrip("0")
        except ValueError:
            digits = ""
        return CURRENCIES.get(digits, "")
    if tag == "9F36":
        return f"Contador (decimal: {int(value_hex, 16)})"
    if tag == "9F26":
        return "Criptograma de la aplicación"
    if tag == "95":
        return "TVR (Resultados de verificación del terminal)"
    if tag == "82":
        return "Perfil de intercambio de la aplicación"
    return ""


def _currency_interpret(value_hex):
    """Interpreta un tag de moneda (5F2A/5F20/9F1A) como '604 → PEN'."""
    try:
        digits = bcd_to_decimal(value_hex or "").lstrip("0")
    except ValueError:
        return ""
    name = CURRENCIES.get(digits, "")
    if not name:
        return ""
    code = name.split("(", 1)[0].strip()
    return f"{digits} → {code}"


def interpret_value(tag, value_hex, minor_units=None, currency_code=None):
    """Interpreta el valor de un tag con más detalle que `_interpret`.

    - 9F02/9F03 (montos): se formatea usando los minor units de la moneda
      detectada. Sin minor units no se inventa la conversión.
    - 5F2A/5F20/9F1A (moneda): '840 → USD'.
    - Resto: mismo resultado que `_interpret`.
    """
    tag = (tag or "").upper()
    if tag in ("9F02", "9F03"):
        if minor_units is None:
            return ""
        try:
            digits = bcd_to_decimal(value_hex or "")
        except ValueError:
            return ""
        amount = _format_amount(digits, minor_units)
        if amount is None:
            return ""
        if currency_code:
            return f"{amount} {currency_code}"
        return amount
    if tag in ("5F2A", "5F20", "9F1A"):
        return _currency_interpret(value_hex)
    return _interpret(tag, value_hex)


def enrich_emv_nodes(nodes, currency_code=None, minor_units=None):
    """Rellena `interpretation` en cada nodo TLV (recursivo)."""
    for n in nodes or []:
        n.interpretation = interpret_value(n.tag, n.value_hex,
                                           minor_units, currency_code)
        enrich_emv_nodes(n.children, currency_code, minor_units)
    return nodes


def enrich_result_emv(result, currency_code=None, minor_units=None):
    """Enriquece `result.emv` y refresca los dicts de `f.emv` del DE55."""
    if not getattr(result, "emv", None):
        return result
    enrich_emv_nodes(result.emv, currency_code, minor_units)
    for f in getattr(result, "fields", []) or []:
        if getattr(f, "number", None) == 55 and getattr(f, "emv", None):
            f.emv = [n.as_dict() for n in result.emv]
    return result


def _parse(buf, out):
    i = 0
    while i < len(buf):
        tag, constructed, i = _read_tag(buf, i)
        length, i = _read_length(buf, i)
        value_hex = buf[i:i + length * 2]
        if len(value_hex) < length * 2:
            raise ValueError("TLV truncado (valor incompleto)")
        i += length * 2
        name = TAG_DICTIONARY.get(tag, "Tag no reconocido")
        children = []
        if constructed and tag in CONSTRUCTED_TAGS:
            try:
                _parse(value_hex, children)
            except ValueError:
                children = []
        note = _interpret(tag, value_hex)
        node = TlvNode(
            tag=tag,
            name=name,
            length=length,
            value_hex=value_hex,
            value_ascii=_to_ascii(value_hex),
            constructed=constructed,
            note=note,
            children=children,
        )
        out.append(node)


def parse_tlv(hex_value):
    """Parsea un valor hex (Campo 55) y devuelve la lista de nodos TLV."""
    nodes: List[TlvNode] = []
    hex_value = (hex_value or "").strip().replace(" ", "")
    if hex_value:
        _parse(hex_value.upper(), nodes)
    return nodes
