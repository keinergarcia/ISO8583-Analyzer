# -*- coding: utf-8 -*-
"""Tramas golden de prueba (idénticas a los ejemplos de la app)."""

FRAME_BASIC = (
    "0037608000000108102020000000800013"
    "990001000853313630303030363606000000"
    "0D41435455414C495A4143494F4E"
    "A1B23C44A1B23C44"
)

FRAME_EMV = (
    "0046608000000102002020000000000200"
    "000000000853047F"
    "9F2608123456789ABCDEF0"
    "9F270180"
    "9F10079F260411223344"
    "9A03260820"
    "5F2A020604"
    "9C0100"
    "9F36020042"
    "82023800"
)

FRAME_ASCII_TEXT = (
    "0042" + "6080000001" + "0810" + "2020000000000000" + "990001" + "000853"
)

FRAME_ASCII_HEX = FRAME_ASCII_TEXT.encode("ascii").hex().upper()

FRAME_ASCII_ND_TEXT = (
    "12BE" + "6080000001" + "0200" + "2000000000000000" + "990001"
)

FRAME_ASCII_ND_HEX = FRAME_ASCII_ND_TEXT.encode("ascii").hex().upper()

FRAME_ASCII_TRAIL_TEXT = (
    "0042" + "6080000001" + "0810" + "2000000000000000" + "990001" + "AA"
)

FRAME_ASCII_TRAIL_HEX = FRAME_ASCII_TRAIL_TEXT.encode("ascii").hex().upper()

# Trama híbrida: cabeceras binarias (longitud, TPDU, MTI, bitmap) + campos
# de datos en ASCII (formato usado por varias redes reales).
# Longitud 0032 = 50 bytes después del campo de longitud.
# Bitmap 3020000000808000 -> DE3, DE4, DE11, DE41, DE49.
FRAME_HYBRID = (
    "0032"          # longitud binaria (2 bytes)
    + "6000018000"  # TPDU
    + "0200"        # MTI
    + "3020000000808000"  # bitmap primario
    + "303033303030"                # DE3  = "003000"
    + "303030303030303030333336"    # DE4  = "000000000336"
    + "313233343536"                # DE11 = "123456"
    + "4142433132333435"            # DE41 = "ABC12345"
    + "363034"                      # DE49 = "604"
)
