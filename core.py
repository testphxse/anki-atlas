# -*- coding: utf-8 -*-
"""Atlas – reine Logik ohne Anki-Importe (damit sie ohne Anki testbar ist)."""

from __future__ import annotations

import colorsys
import html
import json
import re
from typing import Any, Callable, Iterable

VERSION = "0.2.1"

# ---------------------------------------------------------------- Farben

RGB = tuple[float, float, float]
_HEX_RE = re.compile(r"^#?([0-9a-fA-F]{6})$")


def parse_hex(value: Any) -> RGB | None:
    m = _HEX_RE.match(value.strip()) if isinstance(value, str) else None
    if not m:
        return None
    h = m.group(1)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def to_hex(rgb: RGB) -> str:
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(round(c)))) for c in rgb)


def mix(a: RGB, b: RGB, t: float) -> RGB:
    """a bei t=0, b bei t=1."""
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t)


def luminance(rgb: RGB) -> float:
    """Relative Helligkeit nach WCAG, 0 (schwarz) bis 1 (weiß)."""
    def channel(c: float) -> float:
        c = c / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (channel(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: RGB, b: RGB) -> float:
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


WHITE: RGB = (255, 255, 255)
BLACK: RGB = (0, 0, 0)
INK_LIGHT: RGB = (23, 28, 38)      # Text auf hellem Grund
INK_DARK: RGB = (231, 234, 240)    # Text auf dunklem Grund

# Farben für „Nochmal / Schwer / Gut / Einfach“ und für neu / lernen / fällig
STATES_ON_LIGHT = {"again": "#c2413c", "hard": "#a86a12", "good": "#23804f", "easy": "#2b66cf"}
STATES_ON_DARK = {"again": "#ef7d77", "hard": "#e0aa54", "good": "#6cc795", "easy": "#7fa9f2"}

# Akzentfarben: (für hellen Grund, für dunklen Grund)
THEMES: dict[str, dict[str, str]] = {
    "tinte": {"name": "Tinte", "light": "#4a44c6", "dark": "#a09cff"},
    "eosin": {"name": "Eosin", "light": "#b8306a", "dark": "#f28ab3"},
    "salbei": {"name": "Salbei", "light": "#26724f", "dark": "#74cfa3"},
    "petrol": {"name": "Petrol", "light": "#0b6f8a", "dark": "#62c9e2"},
    "bernstein": {"name": "Bernstein", "light": "#96590a", "dark": "#ebb252"},
    "koralle": {"name": "Koralle", "light": "#c2472d", "dark": "#ff9b82"},
    "graphit": {"name": "Graphit", "light": "#3d4654", "dark": "#c3cad6"},
    "eigene": {"name": "Eigene Farbe", "light": "#4a44c6", "dark": "#a09cff"},
}

# Hintergründe: (im hellen Modus, im dunklen Modus). Flächen, Linien und
# Textfarben werden daraus berechnet (surface_palette).
BACKGROUNDS: dict[str, dict[str, str]] = {
    "nebel": {"name": "Nebel (kühles Grau)", "light": "#f2f4f7", "dark": "#12151b"},
    "papier": {"name": "Papier (warm)", "light": "#f4f1ea", "dark": "#1a1815"},
    "klar": {"name": "Klar (Weiß / Schwarz)", "light": "#ffffff", "dark": "#000000"},
    "graphit": {"name": "Graphit (neutral)", "light": "#ececee", "dark": "#1c1c1e"},
    "salbei": {"name": "Salbei (grünlich)", "light": "#ecf2ed", "dark": "#101613"},
    "himmel": {"name": "Himmel (bläulich)", "light": "#eaf1f9", "dark": "#0e1621"},
    "lavendel": {"name": "Lavendel (violett)", "light": "#f1eff9", "dark": "#15131f"},
    "rose": {"name": "Rosé", "light": "#f8eff1", "dark": "#1b1316"},
    "eigene": {"name": "Eigene Farbe", "light": "#f2f4f7", "dark": "#12151b"},
}

SIDES = {"rechts": "Rechts vom Text", "links": "Links vom Text"}
ALIGNMENTS = {
    "auto": "Linksbündig, sobald ein Bild daneben steht",
    "links": "Immer linksbündig",
    "zentriert": "Immer zentriert",
    "notiztyp": "Wie im Notiztyp festgelegt",
}
FONTS: dict[str, tuple[str, str]] = {
    "system": ("Systemschrift", ""),  # leer = --at-font aus tokens.css
    "serif": ("Serifenschrift (wie im Lehrbuch)",
              '"Iowan Old Style", "Palatino Linotype", Palatino, "Book Antiqua", Charter, "Bitstream Charter", Georgia, serif'),
    "rund": ("Rundschrift",
             'ui-rounded, "SF Pro Rounded", "Arial Rounded MT Bold", Nunito, "Segoe UI", "Helvetica Neue", sans-serif'),
    "notiztyp": ("Schrift des Notiztyps", ""),
}
CARD_FORMS = {
    "rand": "Fläche mit Rand",
    "flaeche": "Fläche ohne Rand",
    "flach": "Ohne Fläche (Text direkt auf dem Hintergrund)",
}
DENSITIES = {"kompakt": ("Kompakt", "22px 26px"), "normal": ("Normal", "34px 40px"), "luftig": ("Luftig", "48px 58px")}
TEXT_POSITIONS = {"oben": "Oben", "mitte": "Senkrecht mittig"}
PLATE_WIDTHS = {"passend": "Passend zum Bild, Karte und Bild stehen mittig", "voll": "Volle Restbreite"}
PLATE_BACKGROUNDS = {"karte": "Wie die Karte", "weiss": "Immer weiß", "ohne": "Ohne Fläche"}

DEFAULTS: dict[str, Any] = {
    # Farben
    "thema": "tinte",
    "eigene_akzentfarbe": "#4a44c6",
    "hintergrund": "nebel",
    "eigener_hintergrund_hell": "#f2f4f7",
    "eigener_hintergrund_dunkel": "#12151b",
    # Atlas-Ansicht
    "atlas_ansicht": True,
    "bild_seite": "rechts",
    "text_breite_prozent": 44,
    "tafel_breite": "passend",
    "tafel_hintergrund": "karte",
    "platz_reservieren": True,
    "bild_einpassen": True,
    "bild_abdunkeln": False,
    "min_bildgroesse": 140,
    # Karten
    "karten_stylen": True,
    "kartenform": "rand",
    "ecken": 12,
    "innenabstand": "normal",
    "schrift": "system",
    "schriftgroesse": 19,
    "ausrichtung": "auto",
    "text_position": "oben",
    "karten_breite": 760,
    "fortschritt": True,
    # Übrige Ansichten
    "startseite": True,
    "heatmap": True,
    "leisten": True,
    "kuerzel_atlas": "Shift+B",
}

_CHOICES: dict[str, Iterable[str]] = {
    "thema": THEMES, "hintergrund": BACKGROUNDS, "bild_seite": SIDES, "ausrichtung": ALIGNMENTS,
    "schrift": FONTS, "kartenform": CARD_FORMS, "innenabstand": DENSITIES, "text_position": TEXT_POSITIONS,
    "tafel_breite": PLATE_WIDTHS, "tafel_hintergrund": PLATE_BACKGROUNDS,
}
_COLOR_KEYS = ("eigene_akzentfarbe", "eigener_hintergrund_hell", "eigener_hintergrund_dunkel")
_RANGES = {"text_breite_prozent": (25, 70), "karten_breite": (480, 1400), "min_bildgroesse": (40, 600), "ecken": (0, 28)}

HEAT_WEEKS = 18
HEAT_DAYS = HEAT_WEEKS * 7


def clean_config(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Ergänzt fehlende Schlüssel und fängt unsinnige Werte ab."""
    raw = dict(raw or {})
    # Version 0.1.0 kannte nur „schrift_ersetzen“ (ja/nein).
    if "schrift" not in raw and raw.get("schrift_ersetzen") is False:
        raw["schrift"] = "notiztyp"
    cfg = dict(DEFAULTS)
    for key, value in raw.items():
        if key not in DEFAULTS:
            continue
        default = DEFAULTS[key]
        if isinstance(default, bool):
            if isinstance(value, bool):
                cfg[key] = value
        elif isinstance(default, int):
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                cfg[key] = int(value)
        elif isinstance(value, str):
            cfg[key] = value
    for key, allowed in _CHOICES.items():
        if cfg[key] not in allowed:
            cfg[key] = DEFAULTS[key]
    for key in _COLOR_KEYS:
        rgb = parse_hex(cfg[key])
        cfg[key] = to_hex(rgb) if rgb else DEFAULTS[key]
    for key, (low, high) in _RANGES.items():
        cfg[key] = max(low, min(high, cfg[key]))
    cfg["schriftgroesse"] = 0 if cfg["schriftgroesse"] <= 0 else max(12, min(32, cfg["schriftgroesse"]))
    cfg["kuerzel_atlas"] = cfg["kuerzel_atlas"].strip()
    return cfg


# ---------------------------------------------------------------- Farbwerte fürs CSS

def is_dark(bg: RGB) -> bool:
    return luminance(bg) < 0.18  # ab hier ist heller Text besser lesbar als dunkler


def with_lightness(rgb: RGB, lightness: float) -> RGB:
    """Gleiche Farbrichtung und Sättigung, andere Helligkeit (0–1)."""
    h, _l, sat = colorsys.rgb_to_hls(rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0)
    r, g, b = colorsys.hls_to_rgb(h, max(0.0, min(1.0, lightness)), sat)
    return (r * 255.0, g * 255.0, b * 255.0)


def lightness(rgb: RGB) -> float:
    return colorsys.rgb_to_hls(rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0)[1]


def surface_palette(bg: RGB) -> dict[str, str]:
    """Flächen-, Linien- und Textfarben passend zu einer Hintergrundfarbe.

    Ob Text hell oder dunkel wird, entscheidet die Helligkeit des Hintergrunds –
    nicht der Modus. So bleibt auch eine frei gewählte Farbe lesbar. Flächen
    und Linien behalten den Farbton des Hintergrunds und ändern nur die Helligkeit.
    """
    li = lightness(bg)
    if is_dark(bg):
        ink = mix(INK_DARK, bg, 0.04)
        surface = with_lightness(bg, li + 0.038)
        raised = with_lightness(bg, li + 0.066)
        line = with_lightness(bg, li + 0.125)
    else:
        ink = mix(INK_LIGHT, bg, 0.03)
        if luminance(bg) > 0.94:  # (fast) weißer Hintergrund: Fläche bleibt weiß, der Rand trägt
            surface = bg
            raised = with_lightness(bg, li - 0.035)
            line = with_lightness(bg, li - 0.115)
        else:
            surface = with_lightness(bg, 1.0 - (1.0 - li) * 0.1)
            raised = with_lightness(bg, 1.0 - (1.0 - li) * 0.5)
            line = with_lightness(bg, li - 0.095)
    return {
        "bg": to_hex(bg),
        "surface": to_hex(surface),
        "raised": to_hex(raised),
        "line": to_hex(line),
        "ink": to_hex(ink),
        "ink2": to_hex(mix(ink, surface, 0.34)),
        "ink3": to_hex(mix(ink, surface, 0.47)),
    }


def fit_accent(accent: RGB, surface: RGB, minimum: float = 3.0) -> RGB:
    """Schiebt eine Akzentfarbe so weit Richtung Weiß oder Schwarz, bis sie sich abhebt."""
    target = WHITE if is_dark(surface) else BLACK
    out = accent
    for _ in range(14):
        if contrast(out, surface) >= minimum:
            break
        out = mix(out, target, 0.12)
    return out


def background_color(cfg: dict[str, Any], night: bool) -> RGB:
    if cfg["hintergrund"] == "eigene":
        value = cfg["eigener_hintergrund_dunkel" if night else "eigener_hintergrund_hell"]
    else:
        value = BACKGROUNDS[cfg["hintergrund"]]["dark" if night else "light"]
    rgb = parse_hex(value)
    return rgb if rgb is not None else (242, 244, 247)


def slot_tokens(cfg: dict[str, Any], night: bool) -> dict[str, str]:
    """Alle Farbwerte für einen Modus (hell oder dunkel)."""
    bg = background_color(cfg, night)
    dark = is_dark(bg)
    pal = surface_palette(bg)
    surface = parse_hex(pal["surface"]) or bg
    if cfg["thema"] == "eigene":
        accent = parse_hex(cfg["eigene_akzentfarbe"]) or (74, 68, 198)
        if dark and luminance(accent) < 0.2:
            accent = mix(accent, WHITE, 0.42)  # dunkle Wunschfarbe für dunklen Grund aufhellen
    else:
        accent = parse_hex(THEMES[cfg["thema"]]["dark" if dark else "light"]) or (74, 68, 198)
    accent = fit_accent(accent, surface)
    # Reines Schwarz statt Tintenfarbe: Nur so erreicht die Schrift auf jeder
    # Akzentfarbe mindestens 4,5:1.
    on_accent = WHITE if contrast(WHITE, accent) >= contrast(BLACK, accent) else BLACK
    states = STATES_ON_DARK if dark else STATES_ON_LIGHT
    pal["accent"] = to_hex(accent)
    pal["accent-ink"] = to_hex(on_accent)
    pal.update(states)
    pal.update(new=states["easy"], learn=states["again"], review=states["good"])
    return pal


def _vars(tokens: dict[str, str]) -> str:
    return "".join("--at-%s:%s;" % (k, v) for k, v in tokens.items())


def shape_vars(cfg: dict[str, Any]) -> dict[str, str]:
    """Form der Karten und der Bildtafel als CSS-Variablen (für beide Modi gleich)."""
    form = cfg["kartenform"]
    card_bg = "transparent" if form == "flach" else "var(--at-surface)"
    card_line = "var(--at-line)" if form == "rand" else "transparent"
    plate_bg = {"karte": card_bg, "weiss": "#ffffff", "ohne": "transparent"}[cfg["tafel_hintergrund"]]
    plate_line = "transparent" if cfg["tafel_hintergrund"] == "ohne" else card_line
    out = {
        "radius": "%dpx" % cfg["ecken"],
        "radius-s": "%dpx" % min(8, cfg["ecken"]),
        "pad": DENSITIES[cfg["innenabstand"]][1],
        "card-bg": card_bg,
        "card-line": card_line,
        "plate-bg": plate_bg,
        "plate-line": plate_line,
    }
    stack = FONTS[cfg["schrift"]][1]
    if stack:
        out["font-card"] = stack
    return out


def theme_style(cfg: dict[str, Any]) -> str:
    """<style>-Block mit allen Farben und Formen. Gilt für jede Atlas-Ansicht."""
    return "<style>:root{%s%s}:root.night-mode{%s}</style>" % (
        _vars(slot_tokens(cfg, False)), _vars(shape_vars(cfg)), _vars(slot_tokens(cfg, True)),
    )


def js_config(cfg: dict[str, Any], base: str = "") -> dict[str, Any]:
    """Die Einstellungen, wie reviewer.js sie erwartet.

    base: Web-Pfad des Add-ons, damit das Skript die eigenen Stylesheets erkennt.
    """
    return {
        "base": base,
        "split": cfg["atlas_ansicht"],
        "flip": cfg["bild_seite"] == "links",
        "fit": cfg["bild_einpassen"],
        "hug": cfg["tafel_breite"] == "passend",
        "dim": cfg["bild_abdunkeln"],
        "minImg": cfg["min_bildgroesse"],
        "styled": cfg["karten_stylen"],
        "font": cfg["schrift"] != "notiztyp",
        "size": cfg["schriftgroesse"] > 0,
        "align": {"auto": "auto", "links": "left", "zentriert": "center", "notiztyp": "keep"}[cfg["ausrichtung"]],
        "vcenter": cfg["text_position"] == "mitte",
        "progress": cfg["fortschritt"],
        "shortcut": cfg["kuerzel_atlas"],
    }


def reviewer_head(cfg: dict[str, Any], base: str = "") -> str:
    """Kopf-Einschub für die Lernansicht: Farben, Maße, Einstellungen fürs Skript."""
    size = "--at-size:%dpx;" % cfg["schriftgroesse"] if cfg["schriftgroesse"] else ""
    return (
        theme_style(cfg)
        + "<style>:root{--at-left:%d%%;--at-width:%dpx;%s}</style>"
        % (cfg["text_breite_prozent"], cfg["karten_breite"], size)
        + "<script>window.ATLAS_CFG=%s;</script>" % json.dumps(js_config(cfg, base)).replace("</", "<\\/")
    )


# ---------------------------------------------------------------- Lernansicht: Platz für das Antwortbild

_IMG_TAG_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
_SRC_RE = re.compile(r"""\bsrc\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))""", re.IGNORECASE)
_SKIP_CLASS_RE = re.compile(r"""\bclass\s*=\s*["'][^"']*(?:latex|mathjax|emoji|icon)""", re.IGNORECASE)
_OCCLUSION_RE = re.compile(r"image-occlusion|io-wrapper|io-overlay", re.IGNORECASE)

ANSWER_MARK = '<span id="atlas-answer" hidden></span>'
Size = "tuple[int, int] | None"
SizeOf = Callable[[str], Any]


def image_sources(card_html: str) -> list[str]:
    """Die src-Werte aller <img> im HTML, ohne Formel- und Symbolbilder."""
    out = []
    for tag in _IMG_TAG_RE.findall(card_html):
        if _SKIP_CLASS_RE.search(tag):
            continue
        m = _SRC_RE.search(tag)
        if m:
            out.append(html.unescape(m.group(1) or m.group(2) or m.group(3) or ""))
    return out


def answer_images(answer_html: str, size_of: SizeOf | None = None, min_side: int = 140) -> list[Any] | None:
    """Vorprüfung: Welche Bilder der Antwort könnten auf die Tafel?

    Rückgabe None = keines. Sonst eine Liste mit (Breite, Höhe) je Bild; ein
    Eintrag None heißt „Größe unbekannt“ (z. B. Internetadresse).
    Ob ein Bild in einem zugeklappten Bereich oder einer Tabelle steckt, weiß
    erst reviewer.js – dafür gibt es die Trefferstatistik (PlateStats).
    """
    if not answer_html or "<img" not in answer_html.lower():
        return None
    if _OCCLUSION_RE.search(answer_html):
        return None
    found: list[Any] = []
    for src in image_sources(answer_html):
        size = size_of(src) if size_of else None
        if size is None:
            found.append(None)
        elif size[0] >= min_side or size[1] >= min_side:
            found.append((int(size[0]), int(size[1])))
    return found or None


def answer_has_image(answer_html: str, size_of: SizeOf | None = None, min_side: int = 140) -> bool:
    return answer_images(answer_html, size_of, min_side) is not None


def expect_mark(sizes: list[Any] | None) -> str:
    """Unsichtbare Marke für die Frageseite: „Die Antwort bringt diese Bilder mit“.

    Sind alle Größen bekannt, kann reviewer.js die Tafel schon bei der Frage
    genau so breit machen wie später bei der Antwort.
    """
    if sizes and all(s is not None for s in sizes):
        data = " ".join("%dx%d" % (s[0], s[1]) for s in sizes)
        return '<span id="atlas-expect" hidden data-sizes="%s"></span>' % data
    return '<span id="atlas-expect" hidden></span>'


def should_reserve(hits: int, misses: int) -> bool:
    """Tafel schon bei der Frage freihalten?

    hits/misses zählen je Kartenvorlage, ob das Antwortbild wirklich auf der
    Tafel landete. Ein einzelner Fehlgriff ändert noch nichts; überwiegen die
    Fehlgriffe, wird für diese Vorlage nicht mehr reserviert.
    """
    return misses < 2 or misses <= hits


class PlateStats:
    """Trefferzähler je Kartenvorlage (Notiztyp-ID, Kartennummer). Nur im Speicher."""

    def __init__(self) -> None:
        self._data: dict[tuple[int, int], list[int]] = {}

    def record(self, key: tuple[int, int], hit: bool) -> None:
        entry = self._data.setdefault(key, [0, 0])
        entry[0 if hit else 1] += 1

    def reserve(self, key: tuple[int, int]) -> bool:
        hits, misses = self._data.get(key, (0, 0))
        return should_reserve(hits, misses)


# ---------------------------------------------------------------- Startseite

def streak(counts: dict[int, int], window: int = HEAT_DAYS) -> int:
    """Tage in Folge mit Wiederholungen. Tag 0 = heute.

    Ein noch leerer heutiger Tag unterbricht die Serie nicht.
    """
    day = 0 if counts.get(0) else 1
    n = 0
    while day < window and counts.get(day):
        n += 1
        day += 1
    return n


def heat_levels(counts: dict[int, int], days: int = HEAT_DAYS) -> list[int]:
    """Stufe 0–4 je Tag, ältester Tag zuerst. Stufen relativ zum stärksten Tag."""
    top = max([counts.get(d, 0) for d in range(days)] or [0])
    out = []
    for d in range(days - 1, -1, -1):
        c = counts.get(d, 0)
        if c <= 0 or top <= 0:
            out.append(0)
        else:
            out.append(min(4, 1 + (c * 4 - 1) // top))
    return out


def heat_html(counts: dict[int, int], weekday_today: int, weeks: int = HEAT_WEEKS) -> str:
    """Raster: Spalten = Wochen (Montag oben), die letzte Spalte endet heute.

    weekday_today: 0 = Montag … 6 = Sonntag.
    """
    days = (weeks - 1) * 7 + weekday_today + 1
    levels = heat_levels(counts, days)
    cells = []
    for i, lvl in enumerate(levels):
        age = days - 1 - i
        n = counts.get(age, 0)
        cls = ("l%d" % lvl) + (" today" if age == 0 else "")
        when = "Heute" if age == 0 else ("Gestern" if age == 1 else "Vor %d Tagen" % age)
        cells.append('<i class="%s" title="%s: %d %s"></i>' % (cls, when, n, "Karte" if n == 1 else "Karten"))
    return (
        '<div class="at-heat" role="img" aria-label="Wiederholungen der letzten %d Wochen">%s</div>'
        % (weeks, "".join(cells))
    )


def hero_html(new: int, learn: int, review: int, counts: dict[int, int] | None,
              weekday_today: int = 0) -> str:
    """Kopf der Startseite: was heute ansteht, Serie, Heatmap."""
    total = new + learn + review
    if total:
        title = "%d Karte%s für heute" % (total, "" if total == 1 else "n")
    else:
        title = "Für heute ist alles gelernt"
    parts = ["<div><h1>%s</h1>" % html.escape(title)]
    if total:
        parts.append(
            '<div class="at-counts">'
            '<span><b class="new-count">%d</b> neu</span>'
            '<span><b class="learn-count">%d</b> im Lernen</span>'
            '<span><b class="review-count">%d</b> fällig</span></div>' % (new, learn, review)
        )
    if counts is not None:
        s = streak(counts)
        if s >= HEAT_DAYS - 1:
            parts.append("<p>Serie: über %d Tage in Folge</p>" % (HEAT_DAYS - 2))
        elif s > 1:
            parts.append("<p>Serie: %d Tage in Folge</p>" % s)
        elif s == 1:
            parts.append("<p>Serie: 1 Tag</p>")
    parts.append("</div>")
    if counts is not None:
        parts.append(heat_html(counts, weekday_today))
    return '<div id="atlas-hero">%s</div>' % "".join(parts)


def split_deck_name(name: str) -> tuple[str, str]:
    """'Anatomie::Thorax::Herz' -> ('Anatomie › Thorax', 'Herz')."""
    parts = [p for p in name.split("::") if p]
    if len(parts) < 2:
        return "", name
    return " › ".join(parts[:-1]), parts[-1]


def crumb_html(parents: str) -> str:
    return '<div class="at-crumb">%s</div>' % html.escape(parents) if parents else ""


def sum_tree(children: Iterable[Any]) -> tuple[int, int, int]:
    """Summiert neu/lernen/fällig über die obersten Stapel."""
    new = learn = review = 0
    for node in children:
        new += int(getattr(node, "new_count", 0))
        learn += int(getattr(node, "learn_count", 0))
        review += int(getattr(node, "review_count", 0))
    return new, learn, review


# ---------------------------------------------------------------- Nachrichten aus der Lernansicht

_MESSAGES = ("left", "split", "plate")


def parse_message(message: Any) -> tuple[str, int] | None:
    """'atlas:left:44' -> ('left', 44). Alles andere -> None."""
    if not isinstance(message, str) or not message.startswith("atlas:"):
        return None
    bits = message.split(":")
    if len(bits) != 3 or bits[1] not in _MESSAGES:
        return None
    try:
        return bits[1], int(bits[2])
    except ValueError:
        return None
