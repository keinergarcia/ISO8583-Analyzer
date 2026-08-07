# -*- coding: utf-8 -*-
"""Sesión: estado compartido de la aplicación (perfil activo).

Independiente de Qt para poder reutilizarse desde la UI, scripts o una API.
"""


class Session:
    def __init__(self):
        self.active_profile = None
        self.current_message = None

    def set_profile(self, name):
        self.active_profile = name or None

    def set_message(self, message):
        self.current_message = message


_session = Session()


def get_session():
    return _session
