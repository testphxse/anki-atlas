# -*- coding: utf-8 -*-
"""Atlas – Einstellungsdialog (Werkzeuge → Atlas → Einstellungen …)."""

from __future__ import annotations

from typing import Any, Callable

from aqt.qt import (
    QCheckBox,
    QColor,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QIcon,
    QKeySequence,
    QKeySequenceEdit,
    QLabel,
    QPainter,
    QPixmap,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from . import core


def _swatch(left: str, right: str | None = None) -> QIcon:
    """Kleines Farbfeld für die Auswahllisten; zwei Farben = hell | dunkel."""
    pix = QPixmap(28, 16)
    pix.fill(QColor(left))
    if right:
        painter = QPainter(pix)
        painter.fillRect(14, 0, 14, 16, QColor(right))
        painter.end()
    return QIcon(pix)


class ColorButton(QPushButton):
    """Knopf, der eine Farbe zeigt und per Klick den Farbwähler öffnet."""

    def __init__(self, color: str, title: str) -> None:
        super().__init__()
        self._title = title
        self._color = color
        self.clicked.connect(self._choose)
        self._paint()

    def _paint(self) -> None:
        self.setIcon(_swatch(self._color))
        self.setText(self._color)

    def _choose(self) -> None:
        picked = QColorDialog.getColor(QColor(self._color), self, self._title)
        if picked.isValid():
            self._color = picked.name()
            self._paint()

    def color(self) -> str:
        return self._color


class SettingsDialog(QDialog):
    def __init__(self, parent: Any, cfg: dict[str, Any],
                 on_apply: Callable[[dict[str, Any]], None] | None = None) -> None:
        super().__init__(parent)
        self._cfg = core.clean_config(cfg)
        self._on_apply = on_apply
        self.setWindowTitle("Atlas-Einstellungen")
        self.setMinimumWidth(520)
        outer = QVBoxLayout(self)
        tabs = QTabWidget()
        outer.addWidget(tabs)
        c = self._cfg

        # ------------------------------------------------ Farben
        page, form = self._page(tabs, "Farben")
        self.theme = QComboBox()
        for key, theme in core.THEMES.items():
            if key == "eigene":
                self.theme.addItem(theme["name"], key)
            else:
                self.theme.addItem(_swatch(theme["light"], theme["dark"]), theme["name"], key)
        self._select(self.theme, c["thema"])
        form.addRow("Akzentfarbe", self.theme)
        self.accent = ColorButton(c["eigene_akzentfarbe"], "Akzentfarbe wählen")
        form.addRow("Eigene Akzentfarbe", self.accent)

        self.background = QComboBox()
        for key, bg in core.BACKGROUNDS.items():
            if key == "eigene":
                self.background.addItem(bg["name"], key)
            else:
                self.background.addItem(_swatch(bg["light"], bg["dark"]), bg["name"], key)
        self._select(self.background, c["hintergrund"])
        form.addRow("Hintergrund", self.background)
        self.bg_light = ColorButton(c["eigener_hintergrund_hell"], "Hintergrund im hellen Modus")
        self.bg_dark = ColorButton(c["eigener_hintergrund_dunkel"], "Hintergrund im dunklen Modus")
        row = QHBoxLayout()
        row.addWidget(QLabel("hell"))
        row.addWidget(self.bg_light)
        row.addSpacing(12)
        row.addWidget(QLabel("dunkel"))
        row.addWidget(self.bg_dark)
        row.addStretch(1)
        holder = QWidget()
        holder.setLayout(row)
        form.addRow("Eigener Hintergrund", holder)
        self._note(form, "Jede Farbe gibt es für den hellen und den dunklen Modus (im Farbfeld links | rechts). "
                         "Welcher gilt, bestimmt Anki unter Einstellungen → Erscheinungsbild. "
                         "Flächen, Linien und Textfarben berechnet Atlas passend zum Hintergrund.")
        self.theme.currentIndexChanged.connect(self._sync_enabled)
        self.background.currentIndexChanged.connect(self._sync_enabled)

        # ------------------------------------------------ Karten
        page, form = self._page(tabs, "Karten")
        self.styled = self._check("Kartenfläche und Farben von Atlas verwenden", "karten_stylen")
        form.addRow(self.styled)
        self.form_ = self._combo(core.CARD_FORMS, c["kartenform"])
        form.addRow("Kartenform", self.form_)
        self.corners = self._spin(0, 28, c["ecken"], " px")
        form.addRow("Eckenrundung", self.corners)
        self.density = self._combo({k: v[0] for k, v in core.DENSITIES.items()}, c["innenabstand"])
        form.addRow("Innenabstand", self.density)
        self.font = self._combo({k: v[0] for k, v in core.FONTS.items()}, c["schrift"])
        form.addRow("Schrift", self.font)
        self.size = self._spin(0, 32, c["schriftgroesse"], " px")
        self.size.setSpecialValueText("Wie im Notiztyp")
        form.addRow("Schriftgröße", self.size)
        self.align = self._combo(core.ALIGNMENTS, c["ausrichtung"])
        form.addRow("Textausrichtung", self.align)
        self.position = self._combo(core.TEXT_POSITIONS, c["text_position"])
        form.addRow("Text auf der Karte", self.position)
        self.width = self._spin(480, 1400, c["karten_breite"], " px", step=20)
        form.addRow("Breite einer Karte ohne Bild", self.width)
        self.progress = self._check("Fortschrittsbalken über der Karte zeigen", "fortschritt")
        form.addRow(self.progress)
        self._note(form, "„Senkrecht mittig“ sieht ruhiger aus, solange nur die Frage dasteht. "
                         "Beim Aufdecken rückt der Text dann aber ein Stück nach oben.")

        # ------------------------------------------------ Atlas-Ansicht
        page, form = self._page(tabs, "Text und Bild")
        self.split = self._check("Bilder neben den Text setzen (Atlas-Ansicht)", "atlas_ansicht")
        form.addRow(self.split)
        self.side = self._combo(core.SIDES, c["bild_seite"])
        form.addRow("Platz der Bildtafel", self.side)
        self.plate_width = self._combo(core.PLATE_WIDTHS, c["tafel_breite"])
        form.addRow("Breite der Bildtafel", self.plate_width)
        self.left = self._spin(25, 70, c["text_breite_prozent"], " %")
        form.addRow("Breite der Textspalte", self.left)
        self.plate_bg = self._combo(core.PLATE_BACKGROUNDS, c["tafel_hintergrund"])
        form.addRow("Fläche hinter dem Bild", self.plate_bg)
        self.reserve = self._check(
            "Tafel schon bei der Frage freihalten, wenn die Antwort ein Bild hat", "platz_reservieren"
        )
        form.addRow(self.reserve)
        self.fit = self._check("Kleine Bilder bis zum Doppelten vergrößern", "bild_einpassen")
        form.addRow(self.fit)
        self.dim = self._check("Bilder im dunklen Modus leicht abdunkeln", "bild_abdunkeln")
        form.addRow(self.dim)
        self.min_img = self._spin(40, 600, c["min_bildgroesse"], " px", step=10)
        form.addRow("Bilder unter dieser Größe bleiben im Text", self.min_img)
        self.key = QKeySequenceEdit(QKeySequence(c["kuerzel_atlas"]))
        if hasattr(self.key, "setClearButtonEnabled"):
            self.key.setClearButtonEnabled(True)
        if hasattr(self.key, "setMaximumSequenceLength"):
            self.key.setMaximumSequenceLength(1)
        form.addRow("Tastenkürzel zum Umschalten", self.key)

        # ------------------------------------------------ Übrige Ansichten
        page, form = self._page(tabs, "Startseite und Leisten")
        self.home = self._check("Startseite und Stapelübersicht gestalten", "startseite")
        form.addRow(self.home)
        self.heat = self._check("Lernverlauf der letzten 18 Wochen auf der Startseite zeigen", "heatmap")
        form.addRow(self.heat)
        self.bars = self._check("Obere Leiste und Antwortknöpfe gestalten", "leisten")
        form.addRow(self.bars)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Apply
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Speichern")
        buttons.button(QDialogButtonBox.StandardButton.Apply).setText("Anwenden")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Abbrechen")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self._apply)
        outer.addWidget(buttons)
        self._sync_enabled()

    # --- Bausteine ---
    @staticmethod
    def _page(tabs: QTabWidget, title: str) -> tuple[QWidget, QFormLayout]:
        page = QWidget()
        form = QFormLayout(page)
        tabs.addTab(page, title)
        return page, form

    @staticmethod
    def _note(form: QFormLayout, text: str) -> None:
        label = QLabel(text)
        label.setWordWrap(True)
        form.addRow(label)

    def _check(self, label: str, key: str) -> QCheckBox:
        box = QCheckBox(label)
        box.setChecked(bool(self._cfg[key]))
        return box

    @staticmethod
    def _select(combo: QComboBox, value: str) -> None:
        combo.setCurrentIndex(max(0, combo.findData(value)))

    def _combo(self, options: dict[str, str], current: str) -> QComboBox:
        combo = QComboBox()
        for value, label in options.items():
            combo.addItem(label, value)
        self._select(combo, current)
        return combo

    @staticmethod
    def _spin(low: int, high: int, value: int, suffix: str, step: int = 1) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(low, high)
        spin.setSingleStep(step)
        spin.setSuffix(suffix)
        spin.setValue(value)
        return spin

    def _sync_enabled(self, *_args: Any) -> None:
        self.accent.setEnabled(self.theme.currentData() == "eigene")
        own_bg = self.background.currentData() == "eigene"
        self.bg_light.setEnabled(own_bg)
        self.bg_dark.setEnabled(own_bg)

    def _apply(self) -> None:
        if self._on_apply:
            self._on_apply(self.values())

    def values(self) -> dict[str, Any]:
        cfg = dict(self._cfg)
        size = self.size.value()
        cfg.update(
            thema=self.theme.currentData(),
            eigene_akzentfarbe=self.accent.color(),
            hintergrund=self.background.currentData(),
            eigener_hintergrund_hell=self.bg_light.color(),
            eigener_hintergrund_dunkel=self.bg_dark.color(),
            karten_stylen=self.styled.isChecked(),
            kartenform=self.form_.currentData(),
            ecken=self.corners.value(),
            innenabstand=self.density.currentData(),
            schrift=self.font.currentData(),
            schriftgroesse=0 if size < 12 else size,
            ausrichtung=self.align.currentData(),
            text_position=self.position.currentData(),
            karten_breite=self.width.value(),
            fortschritt=self.progress.isChecked(),
            atlas_ansicht=self.split.isChecked(),
            bild_seite=self.side.currentData(),
            tafel_breite=self.plate_width.currentData(),
            text_breite_prozent=self.left.value(),
            tafel_hintergrund=self.plate_bg.currentData(),
            platz_reservieren=self.reserve.isChecked(),
            bild_einpassen=self.fit.isChecked(),
            bild_abdunkeln=self.dim.isChecked(),
            min_bildgroesse=self.min_img.value(),
            kuerzel_atlas=self.key.keySequence().toString(),
            startseite=self.home.isChecked(),
            heatmap=self.heat.isChecked(),
            leisten=self.bars.isChecked(),
        )
        return core.clean_config(cfg)
