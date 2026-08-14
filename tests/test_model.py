# -*- coding: utf-8 -*-
"""Tests del modelo universal de mensaje (árbol de nodos)."""

import core.api as api
from core.model.message import DecodedNode, Message
from tests.fixtures.frames import FRAME_BASIC, FRAME_EMV


def test_decode_basic_tree():
    msg = api.decode(FRAME_BASIC)
    assert isinstance(msg, Message)
    assert msg.protocol == "iso8583"
    assert msg.profile == "iso8583_1987"
    assert msg.encoding == "bcd"
    assert msg.field_count == 6
    assert msg.active_fields == [3, 11, 41, 60, 63, 64]

    kinds = [n.kind for n in msg.walk()]
    assert "root" in kinds and "header" in kinds and "field" in kinds

    headers = [n.label for n in msg.nodes_of_kind("header")]
    assert "Longitud" in headers and "TPDU" in headers and "MTI" in headers and "Bitmap" in headers

    fields = [n for n in msg.walk() if n.kind == "field"]
    assert fields[0].label.startswith("DE3")
    assert fields[0].value == "990001"


def test_decode_emv_tree():
    msg = api.decode(FRAME_EMV)
    # 9 (antes 8): el 9F10 de FRAME_EMV expone el sub-tag 9F26 parseado.
    tlvs = [n for n in msg.walk() if n.kind == "tlv"]
    assert len(tlvs) == 9
    tags = {n.label.split()[0] for n in tlvs}
    assert "9F26" in tags and "8202" in tags or "82" in tags


def test_node_as_dict():
    node = DecodedNode("X", "v", raw_hex="00", kind="field")
    node.add(DecodedNode("Hijo", "h", kind="bit"))
    d = node.as_dict()
    assert d["label"] == "X" and len(d["children"]) == 1


def test_message_as_dict():
    msg = api.decode(FRAME_BASIC)
    d = msg.as_dict()
    assert d["protocol"] == "iso8583"
    assert d["root"]["label"] == "Mensaje ISO 8583"
    assert "issues" in d and "metadata" in d
