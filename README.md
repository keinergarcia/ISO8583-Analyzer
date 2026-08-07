# ISO8583 Analyzer

Aplicación de escritorio profesional para analizar, interpretar y decodificar
mensajes **ISO 8583** utilizados en sistemas financieros y transacciones
electrónicas. Pensada para equipos de **QA**, **desarrollo** e **integración**.

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
- **Conversores**: HEX ⇄ ASCII, BCD ⇄ Decimal, HEX ⇄ Decimal (int), eliminar/agregar
  espacios, copiar resultado.
- **Exportación** del análisis completo a **TXT** y **JSON** (PDF planificado).
- **Historial automático** de los últimos análisis (fecha, hora, MTI, TPDU, nº de campos)
  con recarga de la trama en un clic.
- **Interfaz oscura moderna**, responsive, con iconos y tipografías legibles.

## Tecnologías

- Python 3.13
- PySide6
- PyInstaller
- Pillow
- pyperclip
- darkdetect
- pyqtdarktheme

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
├── app.py                # Arranque: tema, icono y ventana
├── main.py               # Acceso directo (python main.py)
├── requirements.txt
├── README.md
├── assets/               # Iconos de la aplicación
├── core/                 # Lógica de análisis (sin dependencias de UI)
│   ├── parser.py         # Analizador principal
│   ├── bitmap.py         # Bitmap primario/secundario
│   ├── tpdu.py           # TPDU
│   ├── mti.py            # MTI y su interpretación
│   ├── emv.py            # Decodificador EMV (BER-TLV)
│   ├── converters.py     # HEX/ASCII/BCD/Decimal
│   ├── fields.py         # Diccionario de Data Elements
│   ├── exporter.py       # Exportación TXT/JSON
│   ├── history.py        # Historial JSON
│   └── utils.py          # Utilidades compartidas
├── ui/                   # Interfaz gráfica
│   ├── main_window.py    # Ventana principal
│   ├── styles.py         # Hoja de estilos QSS (tema oscuro)
│   ├── dialogs.py        # Diálogos (errores, Acerca de)
│   └── widgets.py        # Widgets reutilizables (tarjetas, badges…)
├── history/
│   └── history.json      # Historial persistente
└── tests/
    └── test_core.py      # Pruebas del núcleo
```

## Generar ejecutable (.exe) con PyInstaller

```bash
pip install pyinstaller
pyinstaller --noconfirm ISO8583_Analyzer.spec
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

## Hoja de ruta (futuras versiones)

- Comparador de dos tramas ISO 8583.
- Editor / constructor visual de mensajes.
- Visualizador gráfico del Bitmap.
- Soporte para múltiples variantes de ISO 8583.
- Configuración mediante archivos JSON.
- Plugins para nuevos protocolos y campos personalizados.
- Exportación a Excel y PDF.
- Integración con capturas de red y archivos de logs.

## Pruebas

```bash
python tests/test_core.py
```
