# -*- coding: utf-8 -*-
"""Centro de Referencia ISO 8583 (núcleo).

Catálogos JSON bilingües (es/en) + ReferenceService. No depende de Qt y no
modifica el parser ni las exportaciones existentes.
"""

from .service import ReferenceService, get_reference  # noqa: F401

__all__ = ["ReferenceService", "get_reference"]