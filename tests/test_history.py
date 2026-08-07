# -*- coding: utf-8 -*-
"""Tests del historial persistente."""

from core.history import HistoryManager
from tests.fixtures.frames import FRAME_BASIC
from core.api import decode


def test_add_and_load(tmp_path):
    mgr = HistoryManager(path=tmp_path / "hist.json")
    result = decode(FRAME_BASIC).legacy
    rec = mgr.add(FRAME_BASIC, result)
    assert rec["mti"] == "0810"
    assert rec["field_count"] == 6
    assert rec["active_fields"] == [3, 11, 41, 60, 63, 64]
    assert len(mgr.records) == 1

    mgr2 = HistoryManager(path=tmp_path / "hist.json")
    assert len(mgr2.records) == 1


def test_delete_clear(tmp_path):
    mgr = HistoryManager(path=tmp_path / "hist.json", max_records=100)
    result = decode(FRAME_BASIC).legacy
    mgr.add(FRAME_BASIC, result)
    mgr.add(FRAME_BASIC, result)
    assert len(mgr.records) == 2
    mgr.delete(0)
    assert len(mgr.records) == 1
    mgr.clear()
    assert len(mgr.records) == 0
    assert mgr.get(0) is None


def test_max_records(tmp_path):
    mgr = HistoryManager(path=tmp_path / "hist.json", max_records=3)
    result = decode(FRAME_BASIC).legacy
    for _ in range(5):
        mgr.add(FRAME_BASIC, result)
    assert len(mgr.records) == 3


def test_corrupt_file(tmp_path):
    path = tmp_path / "hist.json"
    path.write_text("{no json", encoding="utf-8")
    mgr = HistoryManager(path=path)
    assert mgr.records == []
