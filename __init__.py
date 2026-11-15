# -*- coding: utf-8 -*-
"""Atlas – ein ruhiges, schnelles Design für Anki.

Was hier passiert:
  * Stylesheets werden in Ankis Web-Ansichten eingehängt (webview_will_set_content).
  * Die Startseite bekommt einen Kopf mit Tagesstand, Serie und Heatmap.
  * Die Lernansicht bekommt reviewer.js (Atlas-Ansicht: Text links, Bild rechts).

Performance: pro Karte genau ein web.eval (Fortschritt), keine zusätzliche
Datenbankabfrage. Die Heatmap braucht eine SQL-Abfrage und wird gecacht, bis
wieder gelernt oder synchronisiert wurde. Keine Netzwerkzugriffe.
"""

from __future__ import annotations

import datetime
import json
import os
import platform
import re
import urllib.parse
from typing import Any

import aqt
import aqt.deckbrowser
import aqt.overview
import aqt.reviewer
import aqt.toolbar
from aqt import gui_hooks, mw
from aqt.qt import QAction, QImageReader, QMenu

from . import core

ADDON = mw.addonManager.addonFromModule(__name__) if mw else __name__
_cfg: dict[str, Any] = dict(core.DEFAULTS)
_total = 0  # größter Kartenrest dieser Lernsitzung, Bezugsgröße für den Balken
_heat_cache: tuple[int, dict[int, int]] | None = None
_plates = core.PlateStats()
_answer_key: tuple[int, int] | None = None
_size_cache: dict[str, tuple[int, int] | None] = {}
_REMOTE_RE = re.compile(r"^(?:[a-z][a-z0-9+.\-]*:|//)", re.IGNORECASE)

# Leisten-Kontexte gibt es nicht in jeder Anki-Version unter demselben Namen.
_BAR_CONTEXTS = tuple(
    cls
    for cls in (
        getattr(aqt.toolbar, "TopToolbar", None),
        getattr(aqt.toolbar, "BottomToolbar", None),
        getattr(aqt.reviewer, "ReviewerBottomBar", None),
        getattr(aqt.deckbrowser, "DeckBrowserBottomBar", None),
        getattr(aqt.overview, "OverviewBottomBar", None),
    )
    if cls is not None
)


# ---------- Einstellungen ----------

def load_config() -> dict[str, Any]:
    global _cfg
    _cfg = core.clean_config(mw.addonManager.getConfig(__name__))
    return _cfg


def save_config(cfg: dict[str, Any]) -> None:
    global _cfg
    _cfg = core.clean_config(cfg)
    mw.addonManager.writeConfig(__name__, _cfg)


def _web(path: str) -> str:
    return "/_addons/%s/web/%s?v=%s" % (ADDON, path, core.VERSION)


# ---------- Stylesheets einhängen ----------

def on_webview_will_set_content(web_content: Any, context: Any) -> None:
    cfg = _cfg
    if isinstance(context, aqt.reviewer.Reviewer):
        web_content.css += [_web("tokens.css"), _web("reviewer.css")]
        web_content.js.append(_web("reviewer.js"))
        web_content.head += core.reviewer_head(cfg, "/_addons/%s/" % ADDON)
    elif isinstance(context, (aqt.deckbrowser.DeckBrowser, aqt.overview.Overview)):
        if cfg["startseite"]:
            web_content.css += [_web("tokens.css"), _web("home.css")]
            web_content.head += core.theme_style(cfg)
    elif _BAR_CONTEXTS and isinstance(context, _BAR_CONTEXTS):
        if cfg["leisten"]:
            web_content.css += [_web("tokens.css"), _web("chrome.css")]
            web_content.head += core.theme_style(cfg)


# ---------- Startseite ----------

def _review_counts() -> dict[int, int]:
    """Wiederholungen je Tag (0 = heute). Eine Abfrage über den Primärschlüssel."""
    global _heat_cache
    cutoff = int(mw.col.sched.day_cutoff)
    if _heat_cache and _heat_cache[0] == cutoff:
        return _heat_cache[1]
    start_ms = (cutoff - core.HEAT_DAYS * 86400) * 1000
    rows = mw.col.db.all(
        "select (? - id / 1000) / 86400, count() from revlog where id > ? group by 1",
        cutoff,
        start_ms,
    )
    counts = {int(day): int(n) for day, n in rows}
    _heat_cache = (cutoff, counts)
    return counts


def _invalidate_heat(*_args: Any) -> None:
    global _heat_cache
    _heat_cache = None


def on_deck_browser_will_render_content(deck_browser: Any, content: Any) -> None:
    if not _cfg["startseite"]:
        return
    try:
        tree = deck_browser._render_data.tree
        new, learn, review = core.sum_tree(tree.children)
        counts = _review_counts() if _cfg["heatmap"] else None
        # Ankis Tag beginnt nicht um Mitternacht; day_cutoff ist das Ende von „heute“.
        today = datetime.datetime.fromtimestamp(int(mw.col.sched.day_cutoff) - 1)
        content.stats = core.hero_html(new, learn, review, counts, today.weekday()) + content.stats
    except Exception as exc:  # Die Startseite darf nie an Atlas scheitern.
        print("Atlas: Kopf der Startseite ausgelassen:", repr(exc))


def on_overview_will_render_content(_overview: Any, content: Any) -> None:
    """Stapelübersicht: Elternstapel klein über den Namen, statt 'A::B::C'."""
    if not _cfg["startseite"]:
        return
    try:
        parents, leaf = core.split_deck_name(content.deck)
        if parents:
            content.deck = leaf  # Anki maskiert den Namen danach selbst
            content.shareLink = core.crumb_html(parents) + content.shareLink
    except Exception as exc:
        print("Atlas: Stapelname unverändert:", repr(exc))


# ---------- Lernansicht ----------

def _image_size(src: str) -> tuple[int, int] | None:
    """Bildgröße aus dem Dateikopf (ohne das Bild zu laden), je Datei gemerkt.

    None = unbekannt. (0, 0) = Datei fehlt.
    """
    if src in _size_cache:
        return _size_cache[src]
    size: tuple[int, int] | None = None
    if src and not _REMOTE_RE.match(src):
        media = mw.col.media.dir()
        path = os.path.join(media, src)
        if not os.path.exists(path):
            path = os.path.join(media, urllib.parse.unquote(src))
        if os.path.exists(path):
            qsize = QImageReader(path).size()
            if qsize.isValid():
                size = (qsize.width(), qsize.height())
        else:
            size = (0, 0)
    if len(_size_cache) > 4000:
        _size_cache.clear()
    _size_cache[src] = size
    return size


def on_card_will_show(text: str, card: Any, kind: str) -> str:
    """Hängt unsichtbare Marken an, die reviewer.js auswertet.

    Frage:   „Die Antwort bringt ein Bild mit“ -> Tafel schon jetzt freihalten.
    Antwort: „Bitte melden, ob ein Bild auf der Tafel gelandet ist“.
    card.answer() ist an dieser Stelle bereits berechnet (Anki rendert Frage
    und Antwort gemeinsam), kostet also nichts.
    """
    global _answer_key
    if kind not in ("reviewQuestion", "reviewAnswer"):
        return text
    try:
        if kind == "reviewQuestion":
            _answer_key = None
            sizes = core.answer_images(card.answer(), _image_size, _cfg["min_bildgroesse"])
            if sizes is not None:
                _answer_key = (int(card.note().mid), int(card.ord))
                if (
                    _cfg["atlas_ansicht"]
                    and _cfg["platz_reservieren"]
                    and _plates.reserve(_answer_key)
                ):
                    return text + core.expect_mark(sizes)
        elif _answer_key is not None:
            return text + core.ANSWER_MARK
    except Exception as exc:
        print("Atlas: Marke ausgelassen:", repr(exc))
    return text


def _remaining() -> int:
    reviewer = mw.reviewer
    try:
        _idx, counts = reviewer._v3.counts()  # liegt bereits im Speicher
        return int(sum(counts))
    except Exception:
        try:
            return int(sum(mw.col.sched.counts(reviewer.card)))
        except Exception:
            return 0


def on_show_question(_card: Any) -> None:
    global _total
    if not _cfg["fortschritt"]:
        return
    left = _remaining()
    _total = max(_total, left)
    mw.reviewer.web.eval("window.__atlas&&__atlas.progress(%d,%d);" % (left, _total))


def on_state_did_change(new_state: str, old_state: str) -> None:
    # Erst beim Verlassen zurücksetzen: Beim Betreten meldet Anki den
    # Zustandswechsel erst, nachdem die erste Karte schon gezeigt wurde.
    global _total
    if new_state != "review":
        _total = 0


def on_state_shortcuts(state: str, shortcuts: list) -> None:
    key = _cfg["kuerzel_atlas"]
    if state == "review" and key:
        shortcuts.append(
            (key, lambda: mw.reviewer.web.eval("window.__atlas&&__atlas.toggle();"))
        )


def on_js_message(handled: tuple[bool, Any], message: str, _context: Any) -> tuple[bool, Any]:
    parsed = core.parse_message(message)
    if parsed is None:
        return handled
    kind, value = parsed
    if kind == "plate":
        if _answer_key is not None:
            _plates.record(_answer_key, bool(value))
        return (True, None)
    cfg = dict(_cfg)
    if kind == "left":
        cfg["text_breite_prozent"] = value
    else:
        cfg["atlas_ansicht"] = bool(value)
    save_config(cfg)
    return (True, None)


# ---------- Menü ----------

def refresh_views() -> None:
    """Übernimmt neue Einstellungen in die gerade sichtbaren Ansichten."""
    try:
        mw.toolbar.draw()
        if mw.state == "deckBrowser":
            mw.deckBrowser.refresh()
        elif mw.state == "overview":
            mw.overview.refresh()
        elif mw.state == "review":
            # Lernansicht neu aufbauen; die aktuelle Karte bleibt dieselbe.
            mw.moveToState("review")
    except Exception as exc:
        print("Atlas: Ansicht nicht aktualisiert:", repr(exc))


def apply_settings(cfg: dict[str, Any]) -> None:
    save_config(cfg)
    refresh_views()


def open_settings() -> None:
    from .settings import SettingsDialog

    dialog = SettingsDialog(mw, dict(_cfg), on_apply=apply_settings)
    if dialog.exec():
        apply_settings(dialog.values())


def copy_diagnostics() -> None:
    """Sammelt alles, was man zur Fehlersuche am Layout braucht, in die Zwischenablage.

    Enthalten: Versionen, aktive Add-ons, Atlas-Einstellungen und – wenn gerade
    gelernt wird – Maße der Lernansicht sowie CSS und Vorlagen des Notiztyps.
    Nicht enthalten: Karteninhalte.
    """
    from aqt.utils import tooltip

    info: dict[str, Any] = {"atlas": core.VERSION, "system": platform.platform()}
    try:
        from anki.buildinfo import version as anki_version
        from aqt.qt import PYQT_VERSION_STR, QT_VERSION_STR

        info["anki"] = anki_version
        info["qt"] = "%s / PyQt %s" % (QT_VERSION_STR, PYQT_VERSION_STR)
    except Exception as exc:
        info["versionen"] = repr(exc)
    try:
        manager = mw.addonManager
        info["addons"] = [
            "%s (%s)%s" % (manager.addonName(a), a, "" if manager.isEnabled(a) else " – aus")
            for a in manager.allAddons()
        ]
    except Exception as exc:
        info["addons"] = repr(exc)
    info["einstellungen"] = dict(_cfg)
    info["zustand"] = mw.state
    info["fenster"] = [mw.width(), mw.height()]

    def finish(result: Any) -> None:
        try:
            info["lernansicht"] = json.loads(result) if isinstance(result, str) else None
        except Exception:
            info["lernansicht"] = repr(result)[:2000]
        mw.app.clipboard().setText(json.dumps(info, indent=1, ensure_ascii=False))
        tooltip("Atlas: Diagnose kopiert. Füge sie mit Strg+V (Mac: ⌘V) in den Chat ein.", period=5000)

    card = mw.reviewer.card if mw.state == "review" else None
    if card is None:
        finish(None)
        return
    try:
        notetype = card.note_type()
        template = card.template()
        info["notiztyp"] = {
            "name": notetype.get("name"),
            "css": notetype.get("css"),
            "vorne": template.get("qfmt"),
            "hinten": template.get("afmt"),
        }
        info["zoom"] = mw.reviewer.web.zoomFactor()
    except Exception as exc:
        info["notiztyp"] = repr(exc)
    mw.reviewer.web.evalWithCallback("window.__atlas ? __atlas.diag() : null", finish)


def setup() -> None:
    load_config()
    mw.addonManager.setWebExports(__name__, r"web/.*\.(css|js)")
    mw.addonManager.setConfigAction(__name__, open_settings)

    gui_hooks.webview_will_set_content.append(on_webview_will_set_content)
    gui_hooks.deck_browser_will_render_content.append(on_deck_browser_will_render_content)
    gui_hooks.overview_will_render_content.append(on_overview_will_render_content)
    gui_hooks.card_will_show.append(on_card_will_show)
    gui_hooks.reviewer_did_show_question.append(on_show_question)
    gui_hooks.reviewer_did_answer_card.append(_invalidate_heat)
    gui_hooks.state_did_change.append(on_state_did_change)
    gui_hooks.state_shortcuts_will_change.append(on_state_shortcuts)
    gui_hooks.webview_did_receive_js_message.append(on_js_message)
    gui_hooks.sync_did_finish.append(_invalidate_heat)
    gui_hooks.profile_did_open.append(_invalidate_heat)

    menu = QMenu("Atlas", mw)
    settings_action = QAction("Einstellungen …", mw)
    settings_action.triggered.connect(lambda _checked=False: open_settings())
    menu.addAction(settings_action)
    diag_action = QAction("Diagnose kopieren", mw)
    diag_action.triggered.connect(lambda _checked=False: copy_diagnostics())
    menu.addAction(diag_action)
    mw.form.menuTools.addMenu(menu)


if mw:
    setup()
