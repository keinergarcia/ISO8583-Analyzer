# -*- coding: utf-8 -*-
"""Modelo universal de mensaje decodificado.

Todo mensaje analizado se representa como una estructura homogénea:
bytes crudos + árbol de nodos (DecodedNode). Los viewers, comparadores,
exportadores e inspectores operan sobre este modelo, independientemente
del protocolo de origen.
"""

from dataclasses import dataclass, field
from typing import List, Optional

from ..issues import IssueList


@dataclass
class DecodedNode:
    """Nodo del árbol de decodificación de un mensaje.

    kind: root | header | field | bit | tlv | group
    """

    label: str
    value: str = ""
    raw_hex: str = ""
    note: str = ""
    kind: str = "field"
    offset_hex: int = 0
    length_hex: int = 0
    tag: str = ""
    name_es: str = ""
    value_ascii: str = ""
    constructed: bool = False
    interpretation: str = ""
    tlv_length: int = 0
    children: List["DecodedNode"] = field(default_factory=list)

    def add(self, node: "DecodedNode") -> "DecodedNode":
        self.children.append(node)
        return node

    def as_dict(self):
        return {
            "label": self.label,
            "value": self.value,
            "raw_hex": self.raw_hex,
            "note": self.note,
            "kind": self.kind,
            "offset_hex": self.offset_hex,
            "length_hex": self.length_hex,
            "tag": self.tag,
            "name_es": self.name_es,
            "value_ascii": self.value_ascii,
            "constructed": self.constructed,
            "interpretation": self.interpretation,
            "tlv_length": self.tlv_length,
            "children": [c.as_dict() for c in self.children],
        }


@dataclass
class Message:
    """Mensaje decodificado por un protocolo.

    `legacy` conserva el AnalysisResult original (compatibilidad con la API
    previa). No se serializa.
    """

    raw_clean: str
    protocol: str
    profile: str
    root: DecodedNode
    issues: IssueList = field(default_factory=IssueList)
    encoding: str = "bcd"
    metadata: dict = field(default_factory=dict)
    legacy: Optional[object] = None

    @property
    def active_fields(self) -> List[int]:
        return list(self.metadata.get("active_fields", []))

    @property
    def field_count(self) -> int:
        return self.metadata.get("field_count", 0)

    def walk(self):
        """Itera el árbol en profundidad (raíz incluida)."""
        stack = [self.root]
        while stack:
            node = stack.pop(0)
            yield node
            stack[:0] = node.children

    def nodes_of_kind(self, kind: str):
        return [n for n in self.walk() if n.kind == kind]

    def as_dict(self):
        return {
            "raw_clean": self.raw_clean,
            "protocol": self.protocol,
            "profile": self.profile,
            "encoding": self.encoding,
            "root": self.root.as_dict(),
            "issues": [i.as_dict() for i in self.issues],
            "metadata": self.metadata,
        }
