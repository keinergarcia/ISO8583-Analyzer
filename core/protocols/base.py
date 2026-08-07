# -*- coding: utf-8 -*-
"""Contrato de los decodificadores de protocolo.

Un Decoder traduce bytes crudos + perfil a un Message (árbol universal).
Es una función pura y sin estado: recibe raw y profile, devuelve Message.
"""

from ..model.message import Message


class ProtocolDecoder:
    protocol_id = "base"

    def decode(self, raw, profile, options=None) -> Message:
        raise NotImplementedError
