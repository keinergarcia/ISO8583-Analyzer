# -*- coding: utf-8 -*-
"""Modelo de perfiles de mensaje (MessageSpec).

Un Profile describe CÓMO se decodifica una variante de protocolo: codificación,
layout de cabeceras y tabla de Data Elements. La lógica de decodificación vive
en los Decoder; los datos de cada variante viven en los perfiles.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class HeaderField:
    name: str
    length_bytes: int
    encoding: str = "hex"


@dataclass
class Profile:
    name: str
    protocol: str = "iso8583"
    encoding: str = "auto"  # auto | bcd | ascii | hybrid | ebcdic
    has_length_field: bool = True
    length_field_bytes: int = 2
    has_tpdu: bool = True
    tpdu_length: int = 5
    mti_length_bytes: int = 2
    bitmap_length_bytes: int = 8
    supports_secondary_bitmap: bool = True
    elements: Dict[int, object] = field(default_factory=dict)
    description: str = ""
    llvar_prefix_bytes: int = 1
    lllvar_prefix_bytes: int = 2

    def data_element(self, number):
        return self.elements.get(number)

    @property
    def max_de(self):
        return max(self.elements, default=128)

    def as_dict(self):
        return {
            "name": self.name,
            "protocol": self.protocol,
            "encoding": self.encoding,
            "has_length_field": self.has_length_field,
            "length_field_bytes": self.length_field_bytes,
            "has_tpdu": self.has_tpdu,
            "tpdu_length": self.tpdu_length,
            "mti_length_bytes": self.mti_length_bytes,
            "bitmap_length_bytes": self.bitmap_length_bytes,
            "supports_secondary_bitmap": self.supports_secondary_bitmap,
            "description": self.description,
            "llvar_prefix_bytes": self.llvar_prefix_bytes,
            "lllvar_prefix_bytes": self.lllvar_prefix_bytes,
        }
