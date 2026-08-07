# -*- coding: utf-8 -*-
"""Registro de decodificadores de protocolo.

Punto de extensión Open/Closed: un protocolo nuevo se añade implementando
ProtocolDecoder y registrándose, sin tocar código existente.
"""

_DECODERS = {}


def register_decoder(decoder_cls):
    _DECODERS[decoder_cls.protocol_id] = decoder_cls()
    return decoder_cls


def get_decoder(protocol_id):
    return _DECODERS.get(protocol_id)


def list_decoders():
    return sorted(_DECODERS.keys())
