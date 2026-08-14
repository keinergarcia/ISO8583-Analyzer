# -*- coding: utf-8 -*-
"""Panel Centro de Referencia ISO 8583.

Herramienta de consulta de documentación del estándar (DE, MTI, códigos de
respuesta, monedas, tipos, versiones, perfiles), bilingüe es/en. Totalmente
independiente del parser: depende solo de core.api y widgets compartidos.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from core import api

from ..widgets import Card, SectionTitle, make_badge

# Secciones: (id, título_en, título_es)
SECTIONS = [
    ("fields", "Data Elements", "Elementos de Datos"),
    ("mti", "MTI", "MTI"),
    ("response_codes", "Response Codes", "Códigos de Respuesta"),
    ("currencies", "Currencies (ISO 4217)", "Monedas (ISO 4217)"),
    ("data_types", "Data Types", "Tipos de Datos"),
    ("length_types", "Length Types", "Tipos de Longitud"),
    ("versions", "Versions", "Versiones"),
    ("profiles", "Profiles", "Perfiles"),
    ("emv_tags", "DE55 EMV Tags (ICC Data)", "Tags EMV DE55 (Datos ICC)"),
]

KIND_BADGE = {
    "field": "DE", "mti": "MTI", "response_code": "RC",
    "currency": "ISO 4217", "data_type": "Type", "length_type": "LV",
    "version": "ISO", "profile": "Profile", "emv_tag": "DE55",
}

CHROME = {
    "search_ph": {"en": "Search: DE, MTI, code, currency, country…",
                  "es": "Buscar: DE, MTI, código, moneda, país…"},
    "no_results": {"en": "No results.", "es": "Sin resultados."},
    "welcome": {"en": "Select a section or type to search.",
                "es": "Seleccione una sección o busque para empezar."},
    "hint": {"en": "Click a row to open its full record.",
             "es": "Haga clic en una fila para abrir su ficha completa."},
}


class ReferenceCenterPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("referencePanel")
        self.ref = api.reference_service()
        self._lang = "es"
        self._context = None
        self._build_ui()
        self._render_welcome()

    # ------------------------------------------------------------- UI
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(6)

        top = QHBoxLayout()
        top.setSpacing(8)
        title = QLabel("ISO 8583 Reference Center")
        title.setObjectName("panelTitle")
        top.addWidget(title)
        top.addStretch(1)
        self.btn_es = QPushButton("ES")
        self.btn_es.setObjectName("toggleButton")
        self.btn_es.setCheckable(True)
        self.btn_es.setChecked(True)
        self.btn_en = QPushButton("EN")
        self.btn_en.setObjectName("toggleButton")
        self.btn_en.setCheckable(True)
        for b in (self.btn_es, self.btn_en):
            b.setFixedWidth(44)
            b.setCursor(Qt.PointingHandCursor)
        top.addWidget(self.btn_es)
        top.addWidget(self.btn_en)
        root.addLayout(top)

        search_row = QHBoxLayout()
        search_row.setSpacing(8)
        self.inp_search = QLineEdit()
        self.inp_search.setPlaceholderText(CHROME["search_ph"][self._lang])
        self.inp_search.setFixedHeight(34)
        self.btn_search = QPushButton("Buscar")
        self.btn_search.setObjectName("primaryButton")
        self.btn_search.setFixedHeight(34)
        self.btn_search.setCursor(Qt.PointingHandCursor)
        self.btn_clear = QPushButton("Limpiar")
        self.btn_clear.setObjectName("ghostButton")
        self.btn_clear.setFixedHeight(34)
        self.btn_clear.setCursor(Qt.PointingHandCursor)
        search_row.addWidget(self.inp_search, 1)
        search_row.addWidget(self.btn_search)
        search_row.addWidget(self.btn_clear)
        root.addLayout(search_row)

        splitter = QSplitter()
        self.list_sections = QListWidget()
        for _sid, en_name, es_name in SECTIONS:
            self.list_sections.addItem(f"{en_name}  ·  {es_name}")
        self.list_sections.setFixedWidth(250)
        splitter.addWidget(self.list_sections)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.container = QWidget()
        self.container.setObjectName("refContainer")
        self.layout = QVBoxLayout(self.container)
        self.layout.setContentsMargins(8, 8, 8, 8)
        self.layout.setSpacing(10)
        self.scroll.setWidget(self.container)
        splitter.addWidget(self.scroll)
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter, 1)

        self.btn_es.clicked.connect(lambda: self._set_lang("es"))
        self.btn_en.clicked.connect(lambda: self._set_lang("en"))
        self.btn_search.clicked.connect(self._do_search)
        self.inp_search.returnPressed.connect(self._do_search)
        self.btn_clear.clicked.connect(self._clear_search)
        self.list_sections.itemClicked.connect(self._on_section_click)

    # --------------------------------------------------------- helpers
    def _set_lang(self, lang):
        self._lang = lang
        self.btn_es.setChecked(lang == "es")
        self.btn_en.setChecked(lang == "en")
        self.inp_search.setPlaceholderText(CHROME["search_ph"][lang])
        if self._context:
            self._render()

    def _loc(self, entry, key):
        return self.ref.loc(entry, key, self._lang) if entry else ""

    def _clear(self):
        while self.layout.count():
            item = self.layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _add(self, widget):
        self.layout.addWidget(widget)

    def _render_welcome(self):
        self._clear()
        card = Card()
        card.layout.addWidget(SectionTitle("Reference Center"))
        label = QLabel(CHROME["welcome"][self._lang])
        label.setObjectName("muted")
        label.setWordWrap(True)
        card.layout.addWidget(label)
        self._add(card)

    def _render(self):
        ctx = self._context
        if not ctx:
            self._render_welcome()
            return
        if ctx["mode"] == "list":
            self._render_list(ctx["section"])
        elif ctx["mode"] == "search":
            self._render_search(ctx["hits"])
        else:
            self._render_detail(ctx["entry"], ctx["kind"])

    # ------------------------------------------------------------ list
    def _section_title(self, sid):
        for _id, en_name, es_name in SECTIONS:
            if _id == sid:
                return en_name if self._lang == "en" else es_name
        return sid

    def _catalog(self, sid):
        if sid == "fields":
            return sorted(self.ref.fields(), key=lambda e: e["number"])
        if sid == "mti":
            return sorted(self.ref.mtis(), key=lambda e: str(e["code"]))
        if sid == "response_codes":
            return sorted(self.ref.response_codes(), key=lambda e: str(e["code"]))
        if sid == "currencies":
            return sorted(self.ref.currencies(), key=lambda e: e["alpha"])
        if sid == "data_types":
            return self.ref.data_types()
        if sid == "length_types":
            return self.ref.length_types()
        if sid == "versions":
            return self.ref.versions()
        if sid == "profiles":
            return self.ref.profiles()
        if sid == "emv_tags":
            return sorted(self.ref.emv_tags(), key=lambda e: str(e["tag"]))
        return []

    def _render_list(self, sid):
        self._clear()
        self._add(SectionTitle(self._section_title(sid)))
        hint = QLabel(CHROME["hint"][self._lang])
        hint.setObjectName("muted")
        self._add(hint)
        items = self._catalog(sid)
        card = Card()
        for e in items:
            kind = {"fields": "field", "mti": "mti", "response_codes": "response_code",
                    "currencies": "currency", "data_types": "data_type",
                    "length_types": "length_type", "versions": "version",
                    "profiles": "profile", "emv_tags": "emv_tag"}[sid]
            card.layout.addWidget(self._entry_button(e, kind))
        self._add(card)

    # ----------------------------------------------------------- search
    def _render_search(self, hits):
        self._clear()
        self._add(SectionTitle("Search results · Resultados"))
        if not hits:
            row = Card()
            row.layout.addWidget(make_badge(CHROME["no_results"][self._lang], "warn"))
            self._add(row)
            return
        groups = {}
        for h in hits:
            groups.setdefault(h["kind"], []).append(h)
        for kind, items in groups.items():
            self._add(SectionTitle(KIND_BADGE.get(kind, kind)))
            card = Card()
            for h in items:
                card.layout.addWidget(self._entry_button(h["entry"], kind))
            self._add(card)

    # ----------------------------------------------------------- detail
    def _render_detail(self, entry, kind):
        self._clear()
        title_card = Card()
        head = QHBoxLayout()
        head.setSpacing(8)
        head.addWidget(make_badge(KIND_BADGE.get(kind, kind), "accent"))
        label = QLabel(self._entry_label(entry, kind))
        label.setObjectName("fieldName")
        label.setWordWrap(True)
        head.addWidget(label, 1)
        title_card.layout.addLayout(head)
        self._add(title_card)

        detail = Card()
        for key, value in self._detail_pairs(kind, entry):
            row = QHBoxLayout()
            row.setSpacing(10)
            key_label = QLabel(key)
            key_label.setObjectName("muted")
            key_label.setMinimumWidth(120)
            key_label.setWordWrap(True)
            val = QLabel(value if value else "—")
            val.setObjectName("refValue")
            val.setWordWrap(True)
            val.setTextInteractionFlags(Qt.TextSelectableByMouse)
            row.addWidget(key_label)
            row.addWidget(val, 1)
            detail.layout.addLayout(row)
        self._add(detail)

    # ------------------------------------------------- entry labels
    def _entry_label(self, entry, kind):
        lang = self._lang
        if kind == "field":
            name = self.ref.loc(entry, "name", lang)
            other = self.ref.loc(entry, "name", "en" if lang == "es" else "es")
            return f"DE{entry['number']} · {name}  ({other})"
        if kind == "mti":
            return f"{entry['code']} · {self.ref.loc(entry, 'name', lang)}"
        if kind == "response_code":
            return f"{entry['code']} · {self.ref.loc(entry, 'name', lang)}"
        if kind == "currency":
            return f"{entry['numeric']} · {entry['alpha']} — {self.ref.loc(entry, 'name', lang)}"
        if kind in ("data_type", "length_type"):
            return f"{entry.get('code', '')} · {self.ref.loc(entry, 'name', lang)}"
        if kind == "version":
            return f"ISO 8583:{entry.get('code', '')}"
        if kind == "profile":
            return self.ref.loc(entry, "title", lang) or self.ref.loc(entry, "name", "en")
        if kind == "emv_tag":
            name = self.ref.loc(entry, "name", lang)
            other = self.ref.loc(entry, "name", "en" if lang == "es" else "es")
            return f"Tag {entry['tag']} · {name}  ({other})"
        return str(entry.get("code", ""))

    def _entry_button(self, entry, kind):
        btn = QPushButton(self._entry_label(entry, kind))
        btn.setObjectName("refEntry")
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(lambda _=False, e=entry, k=kind: self._open_detail(k, e))
        return btn

    # ----------------------------------------------------- detail pairs
    def _detail_pairs(self, kind, entry):
        lang = self._lang
        loc = self.ref.loc
        L = []
        if kind == "field":
            L += [("DE", str(entry["number"])),
                  ("Name", loc(entry, "name", lang)),
                  ("Description", loc(entry, "description", lang)),
                  ("Data type", str(entry.get("data_type", ""))),
                  ("Length type", str(entry.get("length_type", ""))),
                  ("Min / Max", f"{entry.get('min_length', '')} / {entry.get('max_length', '')}"),
                  ("Example", str(entry.get("example", ""))),
                  ("Example explanation", loc(entry, "example_explanation", lang)),
                  ("Observations", loc(entry, "observations", lang)),
                  ("Profiles", ", ".join(entry.get("profiles", [])))]
        elif kind == "mti":
            L += [("Code", str(entry.get("code", ""))),
                  ("Name", loc(entry, "name", lang)),
                  ("Meaning", loc(entry, "meaning", lang)),
                  ("When used", loc(entry, "when_used", lang)),
                  ("Flow", loc(entry, "flow", lang)),
                  ("Response", str(entry.get("response_code", ""))),
                  ("Example", loc(entry, "example", lang))]
        elif kind == "response_code":
            L += [("Code", str(entry.get("code", ""))),
                  ("Name", loc(entry, "name", lang)),
                  ("Explanation", loc(entry, "explanation", lang)),
                  ("Use cases", loc(entry, "use_cases", lang)),
                  ("Possible causes", loc(entry, "causes", lang))]
        elif kind == "currency":
            L += [("Numeric", str(entry.get("numeric", ""))),
                  ("Alpha", str(entry.get("alpha", ""))),
                  ("Name", loc(entry, "name", lang)),
                  ("Symbol", str(entry.get("symbol", ""))),
                  ("Country", loc(entry, "country", lang)),
                  ("Decimals", str(entry.get("decimals", ""))),
                  ("Status", str(entry.get("status", "")))]
        elif kind in ("data_type", "length_type"):
            L += [("Code", str(entry.get("code", ""))),
                  ("Name", loc(entry, "name", lang)),
                  ("Description", loc(entry, "description", lang)),
                  ("Format", loc(entry, "format", lang) or loc(entry, "prefix", lang)),
                  ("Example", loc(entry, "example", lang) or
                   self._example_plain(entry))]
        elif kind == "version":
            L += [("Version", str(entry.get("code", ""))),
                  ("What changed", loc(entry, "changes", lang)),
                  ("Advantages", loc(entry, "advantages", lang)),
                  ("Compatibility", loc(entry, "compatibility", lang)),
                  ("Current usage", loc(entry, "usage", lang))]
        elif kind == "profile":
            L += [("Profile", loc(entry, "title", lang) or loc(entry, "name", "en")),
                  ("Description", loc(entry, "description", lang)),
                  ("Notes", loc(entry, "notes", lang))]
        elif kind == "emv_tag":
            other = "en" if lang == "es" else "es"
            L += [("Tag", str(entry.get("tag", ""))),
                  ("Name", loc(entry, "name", lang)),
                  ("Name (EN/ES)", loc(entry, "name", other)),
                  ("Length (bytes)", str(entry.get("length", "")) or "—"),
                  ("Value example", str(entry.get("value_example", "")) or "—")]
        return L

    @staticmethod
    def _example_plain(entry):
        ex = entry.get("example")
        if isinstance(ex, dict):
            return ex.get("value", "")
        return str(ex or "")

    # ----------------------------------------------------- navigation
    def _open_detail(self, kind, entry):
        self._context = {"mode": "detail", "kind": kind, "entry": entry}
        self._render_detail(entry, kind)

    def _show_list(self, sid):
        self._context = {"mode": "list", "section": sid}
        self._render_list(sid)

    def _do_search(self):
        q = self.inp_search.text().strip()
        if q:
            hits = api.reference_search(q, lang=self._lang)
            self._context = {"mode": "search", "hits": hits}
            self._render_search(hits)

    def _clear_search(self):
        self.inp_search.clear()
        self._context = None
        self._render_welcome()

    def _on_section_click(self, item):
        idx = self.list_sections.row(item)
        self._show_list(SECTIONS[idx][0])

    # ------------------------------------------- openers (integración)
    def open_field(self, number):
        entry = self.ref.field(number)
        if entry:
            self._open_detail("field", entry)

    def open_mti(self, code):
        entry = self.ref.mti(code)
        if entry:
            self._open_detail("mti", entry)

    def open_response_code(self, code):
        entry = self.ref.response_code(code)
        if entry:
            self._open_detail("response_code", entry)

    def open_currency(self, code):
        entry = self.ref.currency(code)
        if entry:
            self._open_detail("currency", entry)
        else:
            self.open_field(code)

    def open_emv_tag(self, tag):
        entry = self.ref.emv_tag(tag)
        if entry:
            self._open_detail("emv_tag", entry)

    def open(self, kind, code):
        method = {"field": "open_field", "mti": "open_mti",
                  "response_code": "open_response_code",
                  "currency": "open_currency", "emv_tag": "open_emv_tag"}.get(kind)
        if method:
            getattr(self, method)(code)
        else:
            self.open_field(code)