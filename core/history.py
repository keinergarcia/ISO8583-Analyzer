# -*- coding: utf-8 -*-
"""Gestión del historial de análisis en un archivo JSON."""

import json
import sys
from datetime import datetime
from pathlib import Path


def _default_history_path():
    """Ubicación estable del historial (persistente también en modo ejecutable).

    En modo empaquetado (PyInstaller) se guarda junto al .exe; en desarrollo,
    en la carpeta history/ del proyecto.
    """
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
    else:
        base = Path(__file__).resolve().parent.parent
    return base / "history" / "history.json"


class HistoryManager:
    """Persiste los últimos análisis en un archivo JSON."""

    def __init__(self, path=None, max_records=100):
        self.path = Path(path) if path else _default_history_path()
        self.max_records = max_records
        self._records = []
        self.load()

    def load(self):
        try:
            if self.path.exists():
                with open(self.path, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                    self._records = data if isinstance(data, list) else []
            else:
                self._records = []
        except (OSError, ValueError):
            self._records = []

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.path, "w", encoding="utf-8") as fh:
                json.dump(self._records, fh, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def add(self, raw, result):
        """Registra un análisis nuevo al inicio del historial."""
        now = datetime.now()
        record = {
            "timestamp": now.isoformat(timespec="seconds"),
            "date": now.strftime("%d/%m/%Y"),
            "time": now.strftime("%H:%M:%S"),
            "raw": raw,
            "mti": result.mti.hex if result.mti else "",
            "tpdu": result.tpdu.hex if result.tpdu else "",
            "field_count": len(result.fields),
            "active_fields": result.active_fields,
        }
        self._records.insert(0, record)
        if len(self._records) > self.max_records:
            self._records = self._records[: self.max_records]
        self.save()
        return record

    @property
    def records(self):
        return list(self._records)

    def get(self, index):
        if 0 <= index < len(self._records):
            return self._records[index]
        return None

    def delete(self, index):
        if 0 <= index < len(self._records):
            removed = self._records.pop(index)
            self.save()
            return removed
        return None

    def clear(self):
        self._records = []
        self.save()
