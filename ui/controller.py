# -*- coding: utf-8 -*-
"""Controlador de la interfaz: estado compartido y señales entre vistas.

Los paneles se comunican únicamente a través de este controlador y de la
fachada core.api. Ningún panel referencia a otro directamente.
"""

from PySide6.QtCore import QObject, Signal

from core import api


class Controller(QObject):
    profileChanged = Signal(str)
    messageDecoded = Signal(object)
    historyChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._active_profile = None

    @property
    def active_profile(self):
        return self._active_profile

    def set_profile(self, name):
        self._active_profile = name
        api.session.set_profile(name)
        self.profileChanged.emit(name or "")

    def set_message(self, message):
        api.session.set_message(message)
        self.messageDecoded.emit(message)

    def notify_history_changed(self):
        self.historyChanged.emit()
