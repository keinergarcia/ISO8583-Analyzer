# -*- coding: utf-8 -*-
"""Tests de exportación TXT y JSON."""

import json

from core.exporter import result_to_json, result_to_text
from tests.fixtures.frames import FRAME_BASIC, FRAME_EMV
from core.api import decode


def test_result_to_text():
    result = decode(FRAME_BASIC).legacy
    text = result_to_text(result)
    assert "ISO8583 Analyzer" in text
    assert "0810" in text
    assert "DE3" in text
    assert "DE64" in text
    assert "Advertencias" in text


def test_result_to_text_emv():
    result = decode(FRAME_EMV).legacy
    text = result_to_text(result)
    assert "Campo 55 / EMV" in text
    assert "9F26" in text


def test_result_to_json():
    result = decode(FRAME_EMV).legacy
    data = json.loads(result_to_json(result))
    assert data["mti"]["hex"] == "0200"
    assert data["active_fields"] == [3, 11, 55]
    assert data["generator"] == "ISO8583 Analyzer"
