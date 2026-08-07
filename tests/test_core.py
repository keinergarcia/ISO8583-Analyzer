# -*- coding: utf-8 -*-
"""Prueba rápida del núcleo del analizador."""
import sys
sys.path.insert(0, ".")

from core.parser import parse_message, ParseError
from core import converters
from core.emv import parse_tlv

def test_basic():
    # Mensaje BCD consistente: DE3, DE11, DE41, DE60, DE63, DE64
    # bitmap 2020000000800013 -> byte1 DE3, byte2 DE11, byte6 DE41, byte8 DE60/63/64
    data = ("990001" + "000853" + "3136303030303636"
            + "06" + "000000"
            + "0D" + "41435455414C495A4143494F4E"
            + "A1B23C44A1B23C44")
    total_bytes = 15 + len(data) // 2
    msg = format(total_bytes, "04X") + "6080000001" + "0810" + "2020000000800013" + data
    res = parse_message(msg)
    print("== BÁSICO ==")
    print("longitud:", res.length_hex, res.length_value)
    print("tpdu:", res.tpdu.hex)
    print("mti:", res.mti.hex, "-", res.mti.description)
    print("bitmap:", res.bitmap_primary_hex)
    print("activos:", res.active_fields)
    for f in res.fields:
        print(f"DE{f.number} [{f.ftype}/{f.length_type}] len={f.length_digits} valor={f.value!r} hex={f.raw_hex}")
    print("warnings:", res.warnings)
    print("errors:", res.errors)
    assert res.length_value == total_bytes, res.length_value
    assert res.mti.hex == "0810"
    assert [f.number for f in res.fields] == [3, 11, 41, 60, 63, 64], res.active_fields
    assert res.fields[0].value == "990001"
    assert res.fields[2].value == "16000066"
    assert res.fields[3].value == "000000"
    assert res.fields[4].value == "ACTUALIZACION"
    assert res.fields[5].raw_hex == "A1B23C44A1B23C44"
    assert not res.warnings
    print("OK básico\n")

def test_emv():
    tlv = ("9F2608" + "123456789ABCDEF0"
           + "9F2701" + "80"
           + "9F1007" + "9F260411223344"
           + "9A03" + "260820"
           + "5F2A02" + "0604"
           + "9C01" + "00"
           + "9F3602" + "0042"
           + "8202" + "3800")
    nodes = parse_tlv(tlv)
    print("== EMV directo ==")
    for n in nodes:
        print(f"[{n.tag}] {n.name} len={n.length} hex={n.value_hex} note={n.note!r}")
        for c in n.children:
            print(f"   - [{c.tag}] {c.name} = {c.value_hex}")
    assert nodes[0].tag == "9F26" and nodes[0].name == "Application Cryptogram"
    assert nodes[3].tag == "9A" and "Fecha" in nodes[3].note
    assert nodes[4].note.startswith("PEN")
    assert nodes[5].note == "Bienes y servicios"
    # Mensaje completo con DE55
    data = "000000" + "000853" + "047F" + tlv
    total_bytes = 15 + len(data) // 2
    msg = format(total_bytes, "04X") + "6080000001" + "0200" + "2020000000000200" + data
    res = parse_message(msg)
    print("== MSG con DE55 ==")
    print("activos:", res.active_fields)
    for f in res.fields:
        print(f"DE{f.number} len={f.length_digits} valor={f.value[:20]}... hex={f.raw_hex[:40]}...")
    assert 55 in res.active_fields
    assert res.emv and res.emv[0].tag == "9F26"
    print("OK EMV\n")

def test_errors():
    print("== VALIDACIONES ==")
    try:
        parse_message("ZZZ")
        print("FALLO: debería lanzar")
    except ParseError as e:
        print("caracteres inválidos ->", e)
    try:
        parse_message("0064608000000108102020000002800010")
    except ParseError as e:
        print("corta ->", e)
    res = parse_message("0064608000000108102020000002800010930010")
    print("length mismatch warnings:", res.warnings)
    print("OK validaciones\n")

def test_converters():
    print("== CONVERSORES ==")
    print(converters.hex_to_ascii("486F6C61206D756E646F"))
    print(converters.ascii_to_hex("Hola mundo"))
    print(converters.bcd_to_decimal("123456"))
    print(converters.decimal_to_bcd("123456"))
    print(converters.bcd_to_decimal(converters.decimal_to_bcd("123456")))
    print(converters.hex_to_decimal("0064"))
    print(converters.decimal_to_hex("100"))
    print(converters.add_spaces("00646080000001"))
    print(converters.remove_spaces("00 64 60 80"))
    print("OK conversores\n")

if __name__ == "__main__":
    test_basic()
    test_emv()
    test_errors()
    test_converters()
    print("TODAS LAS PRUEBAS PASARON")
