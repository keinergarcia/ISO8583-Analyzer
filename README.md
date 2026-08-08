# ISO8583 Analyzer

<img src="https://www.python.org/static/community_logos/python-logo-master-v3-TM.png" alt="Python" width="180">

Aplicación de escritorio profesional para analizar, interpretar y decodificar
mensajes **ISO 8583** utilizados en sistemas financieros y transacciones
electrónicas. Pensada para equipos de **QA**, **desarrollo** e **integración**.

> Creado por **Keiner** — también conocido como **el Chivalez**.

## Características

- **Análisis automático** de la trama: Longitud, TPDU, MTI, bitmap primario y secundario.
- **Diccionario ISO 8583**: descripción de los 128 Data Elements (DE).
- **Decodificador EMV** (Campo 55) con interpretación de tags (BER-TLV): criptograma,
  AIP, ATC, moneda, tipo de transacción, etc.
- **Interpretación automática** de: campos presentes/ausentes, longitud de cada campo,
  tipo, valor y bytes en bruto.
- **Validaciones**: hexadecimal inválido, caracteres no permitidos, longitud incorrecta,
  bitmap inválido, campos incompletos y longitudes inconsistentes.
- **Modo BCD (empacado) y ASCII**, con detección automática de codificación.
- **Conversores**: HEX ⇄ ASCII, BCD ⇄ Decimal, HEX ⇄ Decimal (int), HEX ⇄ Binario,
  Decimal ⇄ Binario, eliminar/agregar espacios, copiar resultado.
- **Resumen de transacción**: monto con minor units según moneda, moneda, hora y fecha.
- **Exportación** del análisis completo a **TXT** y **JSON** (PDF planificado).
- **Historial automático** de los últimos análisis (fecha, hora, MTI, TPDU, nº de campos)
  con recarga de la trama en un clic.
- **Perfiles configurables** por entidad (especificaciones JSON, p. ej. Promerica).
- **Interfaz oscura moderna**, responsive, con iconos y tipografías legibles.

## Tecnologías

- Python 3.13
- PySide6
- PyInstaller
- Pillow
- pyperclip
- darkdetect
- pyqtdarktheme
- pytest / pytest-cov

## Instalación

```bash
pip install -r requirements.txt
```

## Uso

```bash
python main.py
```

1. Pegue la trama ISO 8583 en hexadecimal (con o sin espacios).
2. Presione **Analizar** (o Enter).
3. Explore los resultados por secciones: Longitud, TPDU, MTI, Bitmap, Campos activos
   y cada Data Element con su valor y bytes.
4. Use **Historial** para recargar análisis previos y **Conversores** para utilidades.

### Ejemplos rápidos

- Botón **Ejemplo básico**: trama con DE3, DE11, DE41, DE60, DE63 y DE64.
- Botón **Ejemplo EMV**: trama con Campo 55 decodificado.

## Estructura del proyecto

```
ISO8583_Analyzer/
├── app.py                    # Punto de entrada: tema, icono y ventana
├── main.py                   # Acceso directo (python main.py)
├── conftest.py               # Configuración de pytest
├── requirements.txt
├── README.md
├── ISO8583_Analyzer.spec     # Especificación de PyInstaller
├── assets/                   # Iconos de la aplicación
│   └── app_icon.png
├── currencies.json           # Monedas ISO 4217 (código y minor units)
├── fields.json               # Diccionario de Data Elements (personalizable)
├── core/                     # Lógica de análisis (sin dependencias de UI)
│   ├── api.py                # API pública de análisis
│   ├── parser.py             # Analizador principal
│   ├── bitmap.py             # Bitmap primario/secundario
│   ├── tpdu.py               # TPDU
│   ├── mti.py                # MTI y su interpretación
│   ├── emv.py                # Decodificador EMV (BER-TLV)
│   ├── converters.py         # HEX/ASCII/BCD/Decimal/Binario
│   ├── currency.py           # Detección y formato de moneda
│   ├── fields.py             # Diccionario de Data Elements
│   ├── field_interpreter.py  # Interpretación de valores por campo
│   ├── transaction_summary.py# Resumen de transacción (monto, hora, moneda)
│   ├── exporter.py           # Exportación TXT/JSON
│   ├── history.py            # Historial JSON
│   ├── issues.py             # Validaciones y problemas detectados
│   ├── utils.py              # Utilidades compartidas
│   ├── model/                # Modelo de mensaje
│   │   └── message.py
│   ├── profiles/             # Perfiles de entidades
│   │   ├── model.py          # Modelo de perfil
│   │   ├── registry.py       # Registro de perfiles
│   │   └── specs/            # Especificaciones JSON (p. ej. promerica.json)
│   ├── protocols/            # Protocolos de mensajería
│   │   ├── base.py           # Protocolo base
│   │   ├── registry.py       # Registro de protocolos
│   │   └── iso8583/          # Implementación ISO 8583
│   │       └── decoder.py
│   ├── services/             # Servicios de aplicación
│   │   └── session.py
│   └── tools/                # Herramientas auxiliares
│       ├── bitmap_view.py    # Vista del bitmap
│       ├── dictionary.py     # Diccionario dinámico
│       └── formatter.py      # Formato de bytes estilo Notepad++ (hex/ascii/bin/bcd)
├── ui/                       # Interfaz gráfica
│   ├── main_window.py        # Ventana principal
│   ├── controller.py         # Controlador de eventos
│   ├── styles.py             # Hoja de estilos QSS (tema oscuro)
│   ├── dialogs.py            # Diálogos (errores, Acerca de)
│   ├── widgets.py            # Widgets reutilizables (tarjetas, badges…)
│   └── panels/               # Paneles de la UI
│       └── formatter.py      # Panel de conversores/formateador
├── plugins/                  # Carpeta para plugins
├── history/
│   └── history.json          # Historial persistente
├── tests/                    # Pruebas (pytest)
│   ├── fixtures/
│   │   └── frames.py         # Tramas de ejemplo
│   ├── test_api.py
│   ├── test_converters.py
│   ├── test_core.py
│   ├── test_currency.py
│   ├── test_exporter.py
│   ├── test_formatter.py
│   ├── test_history.py
│   ├── test_interpretation.py
│   ├── test_model.py
│   ├── test_offsets.py
│   ├── test_profiles.py
│   ├── test_promerica.py
│   ├── test_transaction_summary.py
│   └── test_validation.py
└── dist/                     # Ejecutable generado
    └── ISO8583 Analyzer.exe
```

## Generar ejecutable (.exe) con PyInstaller

```bash
pip install -r requirements.txt
python -m PyInstaller ISO8583_Analyzer.spec --noconfirm --clean
```

El ejecutable se genera en `dist/ISO8583 Analyzer.exe` (ventana sin consola,
con icono y recursos `assets/` y `history/` incluidos).

Alternativa manual:

```bash
pyinstaller --noconfirm --windowed --onefile --name "ISO8583 Analyzer" ^
  --icon assets/app_icon.png --add-data "assets;assets" ^
  --add-data "history;history" --hidden-import qdarktheme app.py
```

> En Linux/macOS reemplace `;` por `:` en `--add-data`.

## Pruebas

```bash
python -m pytest
```

## Hoja de ruta (futuras versiones)

- Comparador de dos tramas ISO 8583.
- Editor / constructor visual de mensajes.
- Visualizador gráfico del Bitmap.
- Soporte para múltiples variantes de ISO 8583.
- Configuración mediante archivos JSON.
- Plugins para nuevos protocolos y campos personalizados.
- Exportación a Excel y PDF.
- Integración con capturas de red y archivos de logs.
