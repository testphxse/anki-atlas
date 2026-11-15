# Atlas – Einstellungen

Bequemer geht es über **Werkzeuge → Atlas → Einstellungen …**. Diese Liste erklärt dieselben Schalter.

| Schlüssel | Werte | Bedeutung |
|---|---|---|
| `thema` | `tinte`, `eosin`, `salbei`, `petrol`, `bernstein`, `koralle`, `graphit`, `eigene` | Akzentfarbe. `eigene` nimmt `eigene_akzentfarbe`. |
| `eigene_akzentfarbe` | `#rrggbb` | Eigene Akzentfarbe. Atlas passt sie an, bis sie sich vom Hintergrund abhebt. |
| `hintergrund` | `nebel`, `papier`, `klar`, `graphit`, `salbei`, `himmel`, `lavendel`, `rose`, `eigene` | Hintergrund. Jede Wahl hat eine helle und eine dunkle Fassung; welche gilt, bestimmt Anki. |
| `eigener_hintergrund_hell` | `#rrggbb` | Eigener Hintergrund im hellen Modus (bei `hintergrund: eigene`). |
| `eigener_hintergrund_dunkel` | `#rrggbb` | Eigener Hintergrund im dunklen Modus. |
| `atlas_ansicht` | `true` / `false` | Bilder neben den Text setzen (Text links, Bildtafel rechts). |
| `bild_seite` | `rechts`, `links` | Auf welcher Seite die Bildtafel steht. |
| `text_breite_prozent` | 25–70 | Breite der Textspalte. Lässt sich beim Lernen auch mit der Maus ziehen. |
| `tafel_breite` | `passend`, `voll` | `passend`: Die Tafel ist so breit wie das Bild; Karte und Bild stehen gemeinsam in der Fenstermitte. `voll`: Die Tafel füllt den Rest. |
| `tafel_hintergrund` | `karte`, `weiss`, `ohne` | Fläche hinter dem Bild. |
| `platz_reservieren` | `true` / `false` | Tafel schon bei der Frage freihalten, wenn die Antwort ein Bild hat. So springt der Text beim Aufdecken nicht. |
| `bild_einpassen` | `true` / `false` | Kleine Bilder bis höchstens zum Doppelten vergrößern. |
| `bild_abdunkeln` | `true` / `false` | Bilder im dunklen Modus leicht abdunkeln. |
| `min_bildgroesse` | 40–600 | Bilder, die in Breite und Höhe kleiner sind (Pixel), bleiben im Text. |
| `karten_stylen` | `true` / `false` | Kartenfläche, Hintergrund und Textfarbe von Atlas. `false` lässt das CSS deiner Notiztypen unberührt. |
| `kartenform` | `rand`, `flaeche`, `flach` | Fläche mit Rand, Fläche ohne Rand oder Text direkt auf dem Hintergrund. |
| `ecken` | 0–28 | Eckenrundung in Pixeln. |
| `innenabstand` | `kompakt`, `normal`, `luftig` | Abstand zwischen Kartenrand und Text. |
| `schrift` | `system`, `serif`, `rund`, `notiztyp` | Schrift der Karten. `notiztyp` lässt die Schrift des Notiztyps stehen. |
| `schriftgroesse` | 0 oder 12–32 | Schriftgröße in Pixeln. `0` übernimmt die Größe des Notiztyps. |
| `ausrichtung` | `auto`, `links`, `zentriert`, `notiztyp` | `auto`: linksbündig, sobald ein Bild daneben steht. |
| `text_position` | `oben`, `mitte` | `mitte` stellt den Text senkrecht in die Mitte. Beim Aufdecken rückt er dann etwas nach oben. |
| `karten_breite` | 480–1400 | Breite einer Karte ohne Bild (Pixel). |
| `fortschritt` | `true` / `false` | Dünner Balken über der Karte: Anteil der erledigten Karten dieser Sitzung. |
| `startseite` | `true` / `false` | Startseite und Stapelübersicht gestalten. |
| `heatmap` | `true` / `false` | Lernverlauf der letzten 18 Wochen auf der Startseite. |
| `leisten` | `true` / `false` | Obere Leiste und Antwortknöpfe gestalten. |
| `kuerzel_atlas` | z. B. `Shift+B` | Schaltet die Atlas-Ansicht beim Lernen um. Leer = kein Kürzel. |

## Für eigene Kartenvorlagen

- `class="atlas-keep"` an einem Element: Bilder darin bleiben im Text.
- `class="atlas-nosplit"` irgendwo auf der Karte: Diese Karte wird nie geteilt.

## Wenn etwas schief aussieht

**Werkzeuge → Atlas → Diagnose kopieren** legt Versionen, Add-on-Liste, Einstellungen, die Maße der Lernansicht und das CSS des Notiztyps in die Zwischenablage (keine Karteninhalte).
