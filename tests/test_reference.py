# -*- coding: utf-8 -*-
"""Tests del Centro de Referencia ISO 8583 (core.reference + fachada api).

Validan que la nueva funcionalidad sea aditiva: no toca el parser ni la API
pública existente.
"""

import core.api as api


def test_reference_service_loaded():
    assert api.reference_search("terminal")


def test_field_lookup_bilingual():
    f = api.reference_field(39)
    assert f["number"] == 39
    assert f["name"]["en"] == "Response Code"
    assert f["name"]["es"] == "Código de Respuesta"
    assert f["description"]["es"]


def test_fields_dictionary_complete():
    # Usamos el catálogo directo del servicio (90 DEs).
    service = api._get_reference()
    assert len(service.fields()) == 90
    assert service.field(41) is not None
    assert service.field(0) is None


def test_mti_lookup_and_response_bilateral():
    m = api.reference_mti("0200")
    assert m["code"] == "0200"
    assert m["name"]["es"] == "Solicitud de Transacción Financiera"
    assert m["response_code"] == "0210"
    r = api.reference_mti("0210")
    assert r["response_code"] == "0200"
    assert api.reference_mti("0ZZZ") is None


def test_response_code_lookup():
    c = api.reference_response_code("51")
    assert c["name"]["es"] == "Fondos Insuficientes"
    assert c["name"]["en"] == "Insufficient Funds"
    assert api.reference_response_code("05")["name"]["en"] == "Do Not Honor"


def test_currency_numeric_and_alpha():
    for code, alpha, es in [("170", "COP", "Peso Colombiano"),
                            ("840", "USD", "Dólar Estadounidense"),
                            ("978", "EUR", "Euro"),
                            ("188", "CRC", "Colón Costarricense"),
                            ("484", "MXN", "Peso Mexicano")]:
        c = api.reference_currency(code)
        assert c and c["alpha"] == alpha, (code, c)
        assert c["name"]["es"] == es, (code, c)
    # búsqueda por código alfabético
    assert api.reference_currency("COP")["numeric"] == "170"


def test_search_by_terms():
    # Por DE
    hits = api.reference_search("terminal")
    assert any(h["kind"] == "field" and h["code"] == "41" for h in hits)
    # Por código de moneda numérico
    hits = api.reference_search("170")
    assert any(h["kind"] == "currency" and h["code"] == "COP" for h in hits)
    # Por MTI
    hits = api.reference_search("0810")
    assert any(h["kind"] == "mti" and h["code"] == "0810" for h in hits)
    # Por código de respuesta
    hits = api.reference_search("suficiente")
    assert any(h["kind"] == "response_code" for h in hits)


def test_documentation_catalogs():
    versions = {v["code"] for v in api.reference_versions()}
    assert {"1987", "1993", "2003"} <= versions
    types = {t["code"] for t in api.reference_data_types()}
    assert {"n", "an", "ans", "b", "z"} <= types
    lv = {l["code"] for l in api.reference_length_types()}
    assert {"fixed", "llvar", "lllvar", "ascii", "bcd"} <= lv
    profiles = [p.get("name") for p in api.reference_profiles()]
    assert "promerica" in profiles


def test_search_is_bilingual_agnostic():
    es = api.reference_search("código de procesamiento", lang="es")
    en = api.reference_search("processing code", lang="en")
    assert any(h["kind"] == "field" and h["code"] == "3" for h in es)
    assert any(h["kind"] == "field" and h["code"] == "3" for h in en)


def test_api_public_surface():
    for name in ("reference_search", "reference_field", "reference_mti",
                 "reference_response_code", "reference_currency",
                 "reference_versions", "reference_data_types",
                 "reference_length_types", "reference_profiles",
                 "reference_currencies", "reference_languages",
                 "reference_emv_tags", "reference_emv_tag"):
        assert hasattr(api, name), name
        assert name in api.__all__, name
    assert "decode" in api.__all__  # API preexistente intacta
    assert "parse_message" in api.__all__


# ---------------------------------------------------------------------------
# DE55 — EMV TLV (ICC Data): catálogo de referencia bilingüe
# ---------------------------------------------------------------------------

# (tag, nombre_en, nombre_es) tal como se documentó en la referencia DE55.
EMV_TAGS_REQUERIDOS = [
    ("5F2A", "Transaction Currency Code", "Código de moneda de la transacción"),
    ("5F34", "Application PAN Sequence Number", "Número de secuencia del PAN de la aplicación"),
    ("82", "Application Interchange Profile (AIP)", "Perfil de intercambio de la aplicación"),
    ("84", "Dedicated File Name (DF Name)", "Nombre del archivo dedicado"),
    ("95", "Terminal Verification Results (TVR)", "Resultados de verificación del terminal"),
    ("9A", "Transaction Date", "Fecha de la transacción"),
    ("9B", "Transaction Status Information (TSI)", "Información del estado de la transacción"),
    ("9C", "Transaction Type", "Tipo de transacción"),
    ("9F02", "Amount, Authorised", "Importe autorizado"),
    ("9F03", "Amount, Other", "Otro importe"),
    ("9F09", "Application Version Number", "Número de versión de la aplicación"),
    ("9F10", "Issuer Application Data (IAD)", "Datos de aplicación del emisor"),
    ("9F1A", "Terminal Country Code", "Código de país del terminal"),
    ("9F26", "Application Cryptogram", "Criptograma de la aplicación"),
    ("9F27", "Cryptogram Information Data (CID)", "Datos de información del criptograma"),
    ("9F33", "Terminal Capabilities", "Capacidades del terminal"),
    ("9F34", "Cardholder Verification Method (CVM) Results",
     "Resultados del método de verificación del titular"),
    ("9F35", "Terminal Type", "Tipo de terminal"),
    ("9F36", "Application Transaction Counter (ATC)", "Contador de transacciones de la aplicación"),
    ("9F37", "Unpredictable Number", "Número impredecible"),
    ("9F6E", "Third Party Data", "Datos de terceros"),
    ("9F1E", "Interface Device (IFD) Serial Number", "Número de serie del dispositivo de interfaz"),
    ("9F41", "Transaction Sequence Counter", "Contador de secuencia de transacciones"),
]


def test_emv_catalog_presente_con_minimo_de_tags():
    tags = api.reference_emv_tags()
    assert len(tags) >= len(EMV_TAGS_REQUERIDOS)
    codes = {e["tag"] for e in tags}
    assert {t[0] for t in EMV_TAGS_REQUERIDOS} <= codes


def test_emv_tags_documentados_bilingue_exactos():
    """Los nombres deben coincidir literalmente con la referencia DE55."""
    catalog = {e["tag"]: e for e in api.reference_emv_tags()}
    for tag, name_en, name_es in EMV_TAGS_REQUERIDOS:
        entry = catalog[tag]
        assert entry["name"]["en"] == name_en, (tag, entry)
        assert entry["name"]["es"] == name_es, (tag, entry)


def test_emv_tag_lookup_9f10_con_ejemplo():
    e = api.reference_emv_tag("9F10")
    assert e is not None
    assert e["name"]["en"] == "Issuer Application Data (IAD)"
    assert e["name"]["es"] == "Datos de aplicación del emisor"
    # Ejemplo LENGTH / VALUE conservado tal como se proporcionó.
    assert e["length"] == "12"
    assert e["value_example"] == "01 10 A0 40 01 24 00 00 00 00 00 FF"


def test_emv_tag_unknown_devuelve_none():
    assert api.reference_emv_tag("FFFF") is None
    assert api.reference_emv_tag(" 9F10 ") is not None  # tolerante a espacios


def test_emv_search_por_tag_y_nombre():
    hits = api.reference_search("9F36")
    assert any(h["kind"] == "emv_tag" and h["code"] == "9F36" for h in hits)
    hits = api.reference_search("criptograma")
    assert any(h["kind"] == "emv_tag" for h in hits)
    hits = api.reference_search("cryptogram", lang="en")
    assert any(h["kind"] == "emv_tag" for h in hits)