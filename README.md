# Atlas – ruhiges Design mit Bildtafel für Anki

Ein ruhiges, schnelles Design für Anki. Atlas gestaltet Lernansicht, Startseite und
Leisten neu und setzt Bilder auf Karten in eine eigene **Bildtafel neben den Text**
(Text links, Bild rechts) – ideal für Anatomie, Histologie und alles mit Abbildungen.

## Funktionen

- **Atlas-Ansicht:** Bilder wandern aus dem Kartentext in eine Bildtafel daneben.
  Die Breite der Textspalte lässt sich beim Lernen mit der Maus ziehen.
  Umschalten mit `Shift+B`.
- **Kein Springen beim Aufdecken:** Hat die Antwort ein Bild, wird die Tafel schon
  bei der Frage freigehalten.
- **Farbthemen:** `tinte`, `eosin`, `salbei`, `petrol`, `bernstein`, `koralle`,
  `graphit` oder eine eigene Akzentfarbe.
- **Hintergründe** mit heller und dunkler Fassung, passend zu Ankis Hell-/Dunkelmodus.
- **Kartenstil:** Form, Eckenrundung, Innenabstand, Schrift, Schriftgröße und
  Ausrichtung einstellbar – oder das CSS deiner Notiztypen unberührt lassen.
- **Fortschrittsbalken** über der Karte für die aktuelle Lernsitzung.
- **Startseite** mit Tagesstand, Serie und Heatmap der letzten 18 Wochen.
- **Schnell:** pro Karte genau ein `web.eval`, keine zusätzliche Datenbankabfrage,
  keine Netzwerkzugriffe.

## Installation

1. Die Datei `Atlas.ankiaddon` unter
   [Releases](../../releases/latest) herunterladen.
2. In Anki: **Werkzeuge → Add-ons → Add-on-Datei installieren …** und die Datei auswählen.
3. Anki neu starten.

Alternativ den Inhalt dieses Repositorys als Ordner (z. B. `atlas_design`) nach
**Werkzeuge → Add-ons → Add-on-Ordner öffnen** kopieren.

Benötigt Anki **24.06** oder neuer (`min_point_version: 240600`).

## Einstellungen

**Werkzeuge → Atlas → Einstellungen …** – oder über
**Werkzeuge → Add-ons → Atlas → Einstellungen**. Alle Schlüssel sind in
[`config.md`](config.md) erklärt.

### Für eigene Kartenvorlagen

- `class="atlas-keep"` an einem Element: Bilder darin bleiben im Text.
- `class="atlas-nosplit"` irgendwo auf der Karte: Diese Karte wird nie geteilt.

## Wenn etwas schief aussieht

**Werkzeuge → Atlas → Diagnose kopieren** legt Versionen, Add-on-Liste,
Einstellungen, die Maße der Lernansicht und das CSS des Notiztyps in die
Zwischenablage (keine Karteninhalte). Das kannst du in ein Issue einfügen.

## Aufbau

| Datei | Inhalt |
|---|---|
| `__init__.py` | Einbindung in Anki (Hooks, Menü, Startseite, Lernansicht) |
| `core.py` | Reine Logik ohne Anki-Importe (Farben, Themen, CSS-Variablen) |
| `settings.py` | Einstellungsdialog |
| `web/` | Stylesheets und `reviewer.js` für die Atlas-Ansicht |
