# -*- coding: utf-8 -*-
"""Interpretación del TPDU (Transport Protocol Data Unit)."""

from dataclasses import dataclass


@dataclass
class TpduInfo:
    hex: str
    length_bytes: int
    destination: str
    source: str
    control: str

    def as_dict(self):
        return {
            "hex": self.hex,
            "length_bytes": self.length_bytes,
            "destination": self.destination,
            "source": self.source,
            "control": self.control,
        }


def decode_tpdu(hex_str):
    """Decodifica un TPDU de 5 bytes (10 caracteres hex).

    Formato típico: 2 bytes destino, 2 bytes origen, 1 byte control.
    """
    h = (hex_str or "").upper()
    if len(h) < 10:
        return TpduInfo(h, len(h) // 2, h[0:4], h[4:8], h[8:10])
    return TpduInfo(h, len(h) // 2, h[0:4], h[4:8], h[8:10])
