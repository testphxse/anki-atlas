/* Atlas – Lernansicht.

   Ablauf: Anki ersetzt den Inhalt von #qa. Ein MutationObserver (nur direkte
   Kinder von #qa) bemerkt das und hängt layout() in Ankis onUpdateHook. Der
   läuft, nachdem die Skripte der Karte fertig sind und bevor die Karte
   eingeblendet wird – deshalb gibt es kein Flackern.

   Oberste Regel: Atlas darf nie etwas aufdecken, das die Karte verdeckt.
   Auf die Tafel kommt deshalb nicht das nackte Bild, sondern eine „Einheit“:
   das Bild samt allem, was darüber liegt (Abdeckungen, Beschriftungen) und
   dem Rahmen, an dem diese Dinge ausgerichtet sind. Lässt sich das nicht
   sicher zusammenhalten, bleibt die Karte ungeteilt.

   Performance: ein Durchlauf pro Kartenseite, kein Polling, keine Timer.
   Karten ohne Bild steigen nach einer einzigen Abfrage aus. Schlichte Karten
   (kein CSS, das etwas verstecken oder überlagern könnte) kommen ohne jede
   Stil- oder Layoutberechnung aus. */
(function () {
  "use strict";
  if (window.__atlas) return;
  var cfg = window.ATLAS_CFG || {};
  var root = document.documentElement;
  var on = cfg.split !== false;
  var minSide = cfg.minImg || 140;
  var MAX_UPSCALE = 2;
  var PAGE_PAD = 58; // senkrechter Seitenrand: 30px oben + 28px unten (reviewer.css)
  var CAPTION_H = 47; // Höhe der Bildunterzeile mit Vorschaubildern
  var qa, observer, bar, toggle, zoom, zoomImg;
  var vh = 0; // Fensterhöhe; wird nur bei „resize“ neu gelesen
  // { split, text, inner, stage, units, frames, gone, current, label, thumbs, sizes, cap, answer, expect }
  var state = null;
  var carry = null; // Tafelbreite der Frageseite; die Antwort derselben Karte übernimmt sie
  var blocked = false; // diese Kartenseite ließ sich nicht sicher teilen
  var checkQueued = false;

  function el(tag, cls) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    return n;
  }
  function send(msg) {
    if (typeof window.pycmd === "function") window.pycmd(msg);
  }

  /* ---------- Was kann das CSS dieser Karte? ----------
     mayHide: Irgendetwas kann Elemente verstecken  -> Sichtbarkeit genau prüfen.
     risky:   Irgendetwas kann Elemente überlagern, beschneiden oder verfremden
              -> Lage aller Elemente prüfen, bevor ein Bild bewegt wird.
     Geprüft werden das <style> der Karte, Inline-Stile und – einmal eingelesen –
     die Regeln fremder Stylesheets (andere Add-ons), soweit sie auf der Karte greifen. */
  var HIDE_RE = /display\s*:\s*none|visibility\s*:\s*(?:hidden|collapse)|content-visibility/i;
  var RISK_RE = new RegExp(
    "(?:^|[^-\\w])(?:-webkit-)?(?:position|filter|transform|translate|rotate|scale|opacity|clip-path|clip|" +
      "z-index|mix-blend-mode|grid-area|grid-row|grid-column|inset)\\s*:" +
      "|overflow(?:-[xy])?\\s*:|margin[^:;{}]*:[^;{}]*-\\s*[\\d.]|mask|::?(?:before|after)",
    "i"
  );
  var RISK_ATTR =
    '[style*="position"],[style*="margin"],[style*="transform"],[style*="translate"],[style*="filter"],' +
    '[style*="clip"],[style*="mask"],[style*="opacity"],[style*="overflow"],[style*="z-index"],' +
    '[style*="grid"],[style*="inset"],dialog,[popover],canvas,svg';
  var PSEUDO_RE = /::?(?:before|after|first-line|first-letter|marker|placeholder|selection|backdrop)|:(?:hover|active|focus-within|focus-visible|focus|target|checked)/g;
  var foreign = []; // [{sel, hide, risk}] oder true = fremdes Stylesheet nicht lesbar
  var sheetCount = -1;
  var mayHide = true;
  var risky = true;

  function collectRules(rules, out) {
    for (var j = 0; j < rules.length; j++) {
      var r = rules[j];
      if (!r.selectorText) {
        if (r.cssRules) collectRules(r.cssRules, out); // @media, @supports …
        continue;
      }
      var text = r.cssText;
      var h = HIDE_RE.test(text), k = RISK_RE.test(text);
      if (h || k) out.push({ sel: r.selectorText.replace(PSEUDO_RE, ""), hide: h, risk: k });
    }
  }
  function scanForeignSheets() {
    var out = [];
    var sheets = document.styleSheets;
    sheetCount = sheets.length;
    for (var i = 0; i < sheets.length; i++) {
      var node = sheets[i].ownerNode;
      if (!node || qa.contains(node)) continue;
      var href = sheets[i].href || "";
      if (href && (href.indexOf("/_anki/") >= 0 || (cfg.base && href.indexOf(cfg.base) >= 0))) continue;
      try {
        collectRules(sheets[i].cssRules, out);
      } catch (err) {
        return true; // nicht lesbar: immer genau prüfen
      }
    }
    return out;
  }
  function cardFlags() {
    if (foreign === true || document.styleSheets.length !== sheetCount) foreign = scanForeignSheets();
    var hide = false, risk = false, i;
    var styles = qa.getElementsByTagName("style");
    for (i = 0; i < styles.length; i++) {
      var t = styles[i].textContent;
      if (!hide && HIDE_RE.test(t)) hide = true;
      if (!risk && RISK_RE.test(t)) risk = true;
    }
    if (!risk && qa.querySelector(RISK_ATTR)) risk = true;
    if (foreign === true) {
      hide = risk = true;
    } else {
      for (i = 0; i < foreign.length && !(hide && risk); i++) {
        var r = foreign[i];
        if ((r.hide && !hide) || (r.risk && !risk)) {
          var hit;
          try {
            hit = !!qa.querySelector(r.sel);
          } catch (err) {
            hit = true;
          }
          if (hit) {
            if (r.hide) hide = true;
            if (r.risk) risk = true;
          }
        }
      }
    }
    mayHide = hide;
    risky = risk;
  }

  /* ---------- Ist ein Element gerade zu sehen? ---------- */
  function shownInline(node) {
    for (var n = node; n && n !== qa; n = n.parentElement) {
      if (n.hidden) return false;
      var s = n.style;
      if (s && (s.display === "none" || s.visibility === "hidden" || s.visibility === "collapse")) return false;
      if (n.tagName === "DETAILS" && !n.open && n !== node) return false;
    }
    return true;
  }
  function visible(node) {
    if (!node) return false;
    if (!shownInline(node)) return false;
    if (!mayHide) return true;
    if (typeof node.checkVisibility === "function")
      return node.checkVisibility({ visibilityProperty: true, checkVisibilityCSS: true });
    return !!(node.offsetWidth || node.offsetHeight || node.getClientRects().length);
  }

  /* ---------- Bilder auswählen ---------- */
  function eligible(img) {
    if (/latex|mathjax|emoji|icon/i.test(img.className)) return false;
    if (img.closest("table,a[href],.atlas-keep,.atlas-plate")) return false;
    if (!img.complete || !img.naturalWidth) {
      // Selten: Anki lädt Bilder vor. Nach dem Laden einmal neu prüfen.
      if (!img.__atlasWait) {
        img.__atlasWait = true;
        img.addEventListener("load", queueCheck, { once: true });
      }
      return false;
    }
    if (img.naturalWidth < minSide && img.naturalHeight < minSide) return false;
    // Bilder in zugeklappten Bereichen (Hinweise, Zusatzfelder) bleiben, wo sie sind.
    return visible(img);
  }

  /* ---------- Einheit bestimmen (nur bei „risky“) ----------
     Liefert das Element, das als Ganzes auf die Tafel muss, oder null, wenn das
     Bild im Text bleiben muss. Gemessen wird die echte Lage: Alles, was das
     Bild auf dem Bildschirm überlappt, gehört zur Einheit – gleich, mit
     welcher CSS-Technik es dorthin kommt. */
  function overlaps(a, b) {
    return (
      Math.min(a.right, b.right) - Math.max(a.left, b.left) > 2 &&
      Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > 2
    );
  }
  function containingBlock(node) {
    for (var p = node.parentElement; p && p !== qa; p = p.parentElement)
      if (getComputedStyle(p).position !== "static") return p;
    return null;
  }
  function hasEffect(cs) {
    return (
      cs.filter !== "none" || cs.clipPath !== "none" || cs.opacity !== "1" || cs.transform !== "none" ||
      (cs.clip && cs.clip !== "auto") ||
      (cs.webkitMaskImage && cs.webkitMaskImage !== "none") || (cs.mixBlendMode && cs.mixBlendMode !== "normal")
    );
  }
  function pseudoOverlay(node) {
    for (var i = 0; i < 2; i++) {
      var c = getComputedStyle(node, i ? "::after" : "::before");
      if (c.content !== "none" && c.content !== "normal" && (c.position === "absolute" || c.position === "fixed"))
        return true;
    }
    return false;
  }
  /* Etwas liegt über dem Bild und lässt sich nicht mit ihm zusammen bewegen.
     Dann wird die ganze Kartenseite nicht geteilt: Schon das Umbrechen des
     Textes in eine schmalere Spalte könnte die Überlagerung verrutschen lassen. */
  function fixedInPlace() {
    blocked = true;
    return null;
  }
  function ownText(node) {
    for (var c = node.firstChild; c; c = c.nextSibling) if (c.nodeType === 3 && /\S/.test(c.nodeValue)) return true;
    return false;
  }
  /* Liegt ein an der Seite (nicht an einem Rahmen der Karte) ausgerichtetes Element
     über Text oder Bild? Dann darf sich am Umbruch der Karte nichts ändern. */
  function pageLevelOverlay() {
    var all = qa.getElementsByTagName("*");
    for (var i = 0; i < all.length; i++) {
      var e = all[i];
      var pos = getComputedStyle(e).position;
      if (pos !== "absolute" && pos !== "fixed") continue;
      if (pos === "absolute" && containingBlock(e)) continue;
      var er = e.getBoundingClientRect();
      if (er.width < 2 || er.height < 2) continue;
      if (ownText(qa) && overlaps(er, qa.getBoundingClientRect())) return true;
      for (var k = 0; k < all.length; k++) {
        var x = all[k];
        if (x === e || x.contains(e) || e.contains(x)) continue;
        if (x.tagName !== "IMG" && !ownText(x)) continue;
        var xr = x.getBoundingClientRect();
        if (xr.width >= 2 && xr.height >= 2 && overlaps(er, xr)) return true;
      }
    }
    return false;
  }
  function unitFor(img, all) {
    var R = img.getBoundingClientRect();
    if (R.width < 2 || R.height < 2) return null;
    var ics = getComputedStyle(img);
    var floated = ics.float !== "none";
    // Auch ein selbst positioniertes Bild (etwa aus dem Sichtfeld geschoben) wird nachgeprüft.
    var special = hasEffect(ics) || ics.position !== "static";
    var U = img, a, cs, target;
    for (a = img.parentElement; a && a !== qa; a = a.parentElement) {
      cs = getComputedStyle(a);
      if (hasEffect(cs)) {
        U = a;
      } else if (cs.overflowX !== "visible" || cs.overflowY !== "visible") {
        var ar = a.getBoundingClientRect(); // beschneidet der Vorfahr das Bild?
        if (R.left < ar.left - 1 || R.top < ar.top - 1 || R.right > ar.right + 1 || R.bottom > ar.bottom + 1) U = a;
      }
      if (pseudoOverlay(a)) {
        target = cs.position !== "static" ? a : containingBlock(a);
        if (!target) return fixedInPlace();
        if (target.contains(U)) U = target;
      }
    }
    for (var i = 0; i < all.length; i++) {
      var e = all[i];
      if (e === img || U.contains(e) || e.contains(img)) continue; // gehört schon dazu oder ist Vorfahr
      var tag = e.tagName;
      if (tag === "BR" || tag === "STYLE" || tag === "SCRIPT") continue;
      var er = e.getBoundingClientRect();
      if (er.width < 2 || er.height < 2 || !overlaps(er, R)) continue;
      var pos = getComputedStyle(e).position;
      if (pos === "fixed") return fixedInPlace();
      if (pos === "absolute") {
        target = containingBlock(e); // daran ist die Überlagerung ausgerichtet
        if (!target || !target.contains(img)) return fixedInPlace();
      } else {
        if (floated) continue; // Text, der ein umflossenes Bild umläuft
        target = e.parentElement; // kleinster gemeinsamer Vorfahr
        while (target && target !== qa && !target.contains(img)) target = target.parentElement;
        if (!target || target === qa) return fixedInPlace();
      }
      if (target.contains(U)) U = target;
    }
    if (U !== img) {
      // Enthält die Einheit den Kartentext selbst, ist sie keine Abbildung mehr.
      if (U.querySelector("#answer,#typeans,hr,table,textarea") || U.textContent.length > 400) return fixedInPlace();
    }
    return { el: U, img: img, bare: U === img, special: special || U !== img };
  }
  function pick(scope) {
    var imgs = scope.getElementsByTagName("img");
    if (!imgs.length) return [];
    if (qa.querySelector("#image-occlusion-container,#io-wrapper,#io-overlay,.atlas-nosplit")) return [];
    var units = [], i;
    var good = [];
    for (i = 0; i < imgs.length; i++) if (eligible(imgs[i])) good.push(imgs[i]);
    if (!good.length) return units;
    if (!risky) {
      for (i = 0; i < good.length; i++) units.push({ el: good[i], img: good[i], bare: true, special: false });
      return units;
    }
    var all = Array.prototype.slice.call(qa.getElementsByTagName("*"));
    good.forEach(function (img) {
      for (var k = 0; k < units.length; k++) if (units[k].el.contains(img)) return; // steckt schon in einer Einheit
      var u = unitFor(img, all);
      if (!u) return;
      units = units.filter(function (x) {
        return !u.el.contains(x.el);
      });
      units.push(u);
    });
    return units;
  }

  /* Vorher-Nachher-Vergleich: Sieht die Einheit auf der Tafel noch so aus wie
     in der Karte? CSS-Regeln, die an einem Vorfahren hängen, gehen beim
     Umsetzen verloren – das darf keine Abdeckung kosten. */
  var SIG = ["display", "visibility", "opacity", "position", "backgroundColor", "backgroundImage", "filter",
    "clipPath", "clip", "webkitMaskImage", "mixBlendMode", "zIndex", "color", "fontSize"];
  // Ein nacktes Bild bekommt auf der Tafel von Atlas display und Rand neu gesetzt;
  // verglichen wird dort nur, was das Bild verfremden oder verbergen kann.
  var SIG_BARE = ["visibility", "opacity", "filter", "clipPath", "clip", "webkitMaskImage", "mixBlendMode", "position"];
  function signature(unit) {
    var nodes = [unit.el].concat(Array.prototype.slice.call(unit.el.getElementsByTagName("*"), 0, 150));
    var keys = unit.bare ? SIG_BARE : SIG;
    var out = [];
    for (var i = 0; i < nodes.length; i++) {
      var c = getComputedStyle(nodes[i]), s = "";
      for (var k = 0; k < keys.length; k++) s += c[keys[k]] + "|";
      if (!unit.bare && c.borderTopStyle !== "none") s += c.borderTopStyle + c.borderTopColor + "|";
      s += c.transform === "none" ? "n|" : "t|";
      for (var p = 0; p < 2; p++) {
        var pc = getComputedStyle(nodes[i], p ? "::after" : "::before");
        if (pc.content !== "none" && pc.content !== "normal")
          s += pc.content + pc.position + pc.backgroundColor + pc.display + pc.opacity + "|";
      }
      out.push(s);
    }
    return out.join("\n");
  }

  /* ---------- Breite der Tafel ----------
     „Passend zum Bild“: Die Tafel wird so breit wie das größte Bild in seiner
     Anzeigegröße. Gerechnet wird nur mit Zahlen, die schon bekannt sind
     (Bildgröße, Fensterhöhe). Dieselbe Rechnung läuft schon auf der Frageseite
     mit den Bildgrößen, die Python mitschickt. Eintrag: [Breite, Höhe, größter
     Vergrößerungsfaktor]. */
  function shownWidth(size, availH) {
    var cap = size[2] || (cfg.fit !== false ? MAX_UPSCALE : 1);
    return Math.min(size[0] * cap, (availH * size[0]) / size[1]);
  }
  function availHeight(count) {
    return vh - PAGE_PAD - 2 - 28 - (count > 1 ? CAPTION_H : 0);
  }
  function plateWidth(sizes) {
    if (!cfg.hug || !sizes.length) return "";
    var availH = availHeight(sizes.length);
    if (availH < 80) return "";
    var best = 0;
    for (var i = 0; i < sizes.length; i++) {
      if (!(sizes[i][0] > 0 && sizes[i][1] > 0)) return ""; // unbekannte Größe: volle Breite
      var shown = shownWidth(sizes[i], availH);
      if (shown > best) best = shown;
    }
    return best ? Math.max(260, Math.ceil(best) + 30) : "";
  }
  function applyPlateWidth() {
    if (!state) return;
    // Hat die Frage die Tafel schon freigehalten, bleibt deren Breite stehen –
    // auch wenn die Antwort am Ende andere Bilder zeigt als angekündigt.
    var w = state.answer && carry !== null ? carry : plateWidth(state.sizes);
    if (!state.answer) carry = state.expect ? w : null;
    state.cap = w || Infinity;
    if (w) state.split.style.setProperty("--at-plate", w + "px");
    else state.split.style.removeProperty("--at-plate");
    // Einheiten mit Abdeckung behalten ihre eigene Größenlogik; Atlas gibt nur
    // die Breite vor, bei der das Bild in die Höhe der Tafel passt.
    var availH = availHeight(state.units.length);
    for (var i = 0; i < state.units.length; i++) {
      var u = state.units[i];
      if (!u.bare)
        state.frames[i].style.width =
          Math.max(60, Math.floor(shownWidth([u.img.naturalWidth, u.img.naturalHeight, 1], Math.max(80, availH)))) + "px";
    }
  }
  function expectedSizes() {
    var mark = qa.querySelector("#atlas-expect");
    var raw = mark && mark.getAttribute("data-sizes");
    if (!raw) return null;
    return raw.split(" ").map(function (s) {
      var p = s.split("x");
      return [parseInt(p[0], 10) || 0, parseInt(p[1], 10) || 0];
    });
  }

  /* ---------- Aufbauen / Zurückbauen ---------- */
  function hideEmptied(node, stop, gone) {
    while (node && node !== stop) {
      if (/\S/.test(node.textContent)) return;
      if (node.querySelector("img,video,audio,canvas,svg,iframe,input,hr")) return;
      node.classList.add("atlas-gone");
      gone.push(node);
      node = node.parentNode;
    }
  }
  function show(i) {
    if (!state || !state.units.length) return;
    var n = state.units.length;
    i = ((i % n) + n) % n;
    state.frames[state.current].classList.remove("atlas-current");
    state.frames[i].classList.add("atlas-current");
    state.current = i;
    var unit = state.units[i];
    state.stage.classList.toggle("atlas-fixed", !unit.bare);
    state.label.textContent = n > 1 ? "Abbildung " + (i + 1) + " von " + n : unit.img.alt || unit.img.title || "";
    if (state.thumbs) {
      var b = state.thumbs.children;
      for (var k = 0; k < b.length; k++) b[k].setAttribute("aria-current", k === i ? "true" : "false");
    }
    if (zoom.classList.contains("atlas-open")) {
      if (unit.bare) {
        zoomImg.src = unit.img.currentSrc || unit.img.src;
        resetZoom();
      } else {
        closeZoom();
      }
    }
  }
  /* Baut die Atlas-Ansicht. Rückgabe false = zurückgebaut, weil die Karte danach
     anders aussähe als vorher. */
  function build(units, preferred, expected) {
    var hr = qa.querySelector("#answer");
    var start = 0, i;
    for (i = 0; i < units.length; i++) {
      if (preferred && (units[i].img === preferred || units[i].el.contains(preferred))) {
        start = i;
        hr = null;
        break;
      }
    }
    if (hr) {
      // Auf der Antwortseite zuerst das Bild zeigen, das neu dazugekommen ist.
      for (i = 0; i < units.length; i++) {
        if (hr.compareDocumentPosition(units[i].el) & Node.DOCUMENT_POSITION_FOLLOWING) {
          start = i;
          break;
        }
      }
    }
    var before = units.map(function (u) {
      return u.special ? signature(u) : null;
    });
    var split = el("div", "atlas-split" + (cfg.flip ? " atlas-flip" : ""));
    var text = el("div", "atlas-text");
    var inner = el("div", "atlas-inner");
    var divider = el("div", "atlas-divider");
    var plate = el("figure", "atlas-plate");
    var stage = el("div", "atlas-stage");
    var cap = el("figcaption", "atlas-caption");
    var label = el("span");
    var thumbs = null;
    var gone = [];
    var frames = [];
    // Tafelbreite: die Bilder dieser Seite; ohne eigene Bilder (freigehaltene
    // Tafel) die angekündigten Bilder der Antwort.
    var sizes = units.length
      ? units.map(function (u) {
          return [u.img.naturalWidth, u.img.naturalHeight, u.bare ? 0 : 1];
        })
      : expected || [];

    while (qa.firstChild) inner.appendChild(qa.firstChild);
    text.appendChild(inner);
    units.forEach(function (u) {
      var ph = document.createComment("atlas");
      var parent = u.el.parentNode;
      var frame = el("div", "atlas-frame " + (u.bare ? "atlas-bare" : "atlas-unit"));
      if (u.bare && cfg.fit !== false) {
        frame.style.maxWidth = u.img.naturalWidth * MAX_UPSCALE + "px";
        frame.style.maxHeight = u.img.naturalHeight * MAX_UPSCALE + "px";
      }
      parent.replaceChild(ph, u.el);
      u.ph = ph;
      frame.appendChild(u.el);
      stage.appendChild(frame);
      frames.push(frame);
      hideEmptied(parent, inner, gone);
    });
    cap.appendChild(label);
    if (units.length > 1) {
      thumbs = el("div", "atlas-thumbs");
      units.forEach(function (u, k) {
        var b = el("button");
        b.type = "button";
        b.title = "Abbildung " + (k + 1);
        // Vorschaubild nur für nackte Bilder – sonst zeigte es das Bild ohne Abdeckung.
        if (u.bare) b.style.backgroundImage = 'url("' + (u.img.currentSrc || u.img.src).replace(/"/g, "%22") + '")';
        else b.textContent = String(k + 1);
        b.onclick = function (e) {
          e.stopPropagation();
          show(k);
          b.blur(); // Leertaste soll weiter die Antwort zeigen
        };
        thumbs.appendChild(b);
      });
      cap.appendChild(thumbs);
    }
    if (!units.length) {
      var wait = el("p", "atlas-wait");
      wait.textContent = "Die Abbildung erscheint mit der Antwort.";
      stage.appendChild(wait);
      plate.classList.add("atlas-empty");
    } else {
      stage.onclick = openZoom;
    }
    plate.appendChild(stage);
    plate.appendChild(cap);
    split.appendChild(text);
    split.appendChild(divider);
    split.appendChild(plate);

    state = {
      split: split, text: text, inner: inner, stage: stage, units: units, frames: frames, gone: gone,
      current: 0, label: label, thumbs: thumbs, sizes: sizes, cap: Infinity,
      answer: !!inner.querySelector("#atlas-answer"), expect: !!expected || !!inner.querySelector("#atlas-expect"),
    };
    applyPlateWidth();
    qa.appendChild(split);
    qa.classList.add("atlas-has-split");
    show(start);
    cap.hidden = !label.textContent && !thumbs;
    divider.onpointerdown = startDrag;

    for (i = 0; i < units.length; i++) {
      if (before[i] === null) continue;
      var after = signature(units[i]);
      if (after !== before[i]) {
        // Für die Diagnose festhalten, woran es lag (erste abweichende Zeile).
        var x = before[i].split("\n"), y = after.split("\n"), d = 0;
        while (d < x.length && x[d] === y[d]) d++;
        api.why = { element: d, vorher: x[d], nachher: y[d] };
        unbuild(); // lieber ungeteilt als falsch
        return false;
      }
    }
    api.why = null;
    return true;
  }
  function unbuild() {
    if (!state) return;
    var s = state;
    state = null;
    qa.classList.remove("atlas-has-split");
    if (!s.split.isConnected) return; // Anki hat die Karte bereits ersetzt
    s.units.forEach(function (u) {
      if (u.ph && u.ph.parentNode) u.ph.parentNode.replaceChild(u.el, u.ph);
      u.ph = null;
    });
    s.gone.forEach(function (n) {
      n.classList.remove("atlas-gone");
      if (!n.classList.length) n.removeAttribute("class");
    });
    while (s.inner.firstChild) qa.insertBefore(s.inner.firstChild, s.split);
    s.split.remove();
  }
  function arrange(preferred) {
    var t0 = performance.now();
    observer.disconnect();
    unbuild();
    cardFlags();
    var expect = qa.querySelector("#atlas-expect");
    var answer = qa.querySelector("#atlas-answer");
    if (!answer) carry = null; // Frageseite: Breite wird neu bestimmt
    var units = blocked ? [] : pick(qa);
    if (blocked) units = []; // pick() hat eine Überlagerung gefunden, die sich nicht mitnehmen lässt
    else if (risky && on && (units.length || expect) && pageLevelOverlay()) blocked = true;
    if (blocked) units = [];
    if (on && !blocked && (units.length || expect)) {
      if (!build(units, preferred, expect ? expectedSizes() : null)) {
        blocked = true;
        units = [];
      }
    }
    toggle.hidden = blocked || !(units.length || expect);
    // Rückmeldung für „platz_reservieren“: Hatte die Antwort ein Bild für die Tafel?
    if (answer && !answer.__atlasSent) {
      answer.__atlasSent = true;
      send("atlas:plate:" + (units.length ? 1 : 0));
    }
    observer.observe(qa, { childList: true });
    api.ms = performance.now() - t0; // Dauer des letzten Durchlaufs, zum Nachmessen
  }
  /* Einmal pro Kartenseite. Mehrfachaufrufe für denselben Inhalt kosten nichts. */
  function layout() {
    if (!qa) return;
    if (state && state.split.isConnected && qa.childNodes.length === 1) return;
    if (!state && qa.__atlasSeen === qa.firstChild && qa.firstChild) return;
    closeZoom();
    arrange(null);
    qa.__atlasSeen = qa.firstChild;
  }
  function onMutate() {
    qa.__atlasSeen = null;
    blocked = false;
    var up = window.onUpdateHook;
    var shown = window.onShownHook;
    if (Array.isArray(up) && Array.isArray(shown)) {
      if (up.indexOf(layout) < 0) up.push(layout);
      if (shown.indexOf(layout) < 0) shown.push(layout); // Sicherheitsnetz
    } else {
      layout();
    }
  }

  /* Nach Klick oder Taste: Wurde ein Bereich mit Bild auf- oder zugeklappt? */
  function check() {
    checkQueued = false;
    if (!qa || !on || blocked) return;
    cardFlags();
    var changed = false;
    var fresh = null;
    if (state) {
      // Leer gewordene Hüllen hat Atlas selbst ausgeblendet (atlas-gone). Für die
      // genaue Prüfung muss diese Klasse kurz weg, sonst gälte jede Hülle als versteckt.
      var gone = state.gone, g;
      if (mayHide) for (g = 0; g < gone.length; g++) gone[g].classList.remove("atlas-gone");
      for (var i = 0; i < state.units.length && !changed; i++) {
        var p = state.units[i].ph && state.units[i].ph.parentElement;
        if (p !== state.inner && !visible(p)) changed = true;
      }
      if (mayHide) for (g = 0; g < gone.length; g++) gone[g].classList.add("atlas-gone");
    }
    var scope = state ? state.inner : qa;
    var all = scope.getElementsByTagName("img");
    for (var k = 0; k < all.length; k++) {
      if (eligible(all[k])) {
        changed = true;
        fresh = all[k];
        break;
      }
    }
    if (changed) arrange(fresh || (state && state.units.length ? state.units[state.current].img : null));
  }
  function queueCheck(e) {
    if (e && e.target && e.target.closest && e.target.closest(".atlas-plate,#atlas-hud,#atlas-zoom")) return;
    if (checkQueued) return;
    checkQueued = true;
    requestAnimationFrame(check);
  }
  var resizeQueued = false;
  function onResize() {
    if (resizeQueued) return;
    resizeQueued = true;
    requestAnimationFrame(function () {
      resizeQueued = false;
      vh = window.innerHeight;
      carry = null; // neue Fenstergröße: neu rechnen
      applyPlateWidth();
    });
  }

  /* ---------- Trenner ziehen ----------
     Der Trenner soll unter dem Mauszeiger bleiben. Stehen Karte und Bild mittig
     (Tafel schmaler als der Restplatz), wandert beim Ziehen die ganze Gruppe
     mit; das rechnet die Formel 2x − B + T heraus. */
  function startDrag(e) {
    if (!state) return;
    var rect = state.split.getBoundingClientRect();
    var plateCap = state.cap;
    var flip = !!cfg.flip;
    var pct = null;
    var frame = 0;
    var divider = e.currentTarget;
    try {
      divider.setPointerCapture(e.pointerId);
    } catch (err) {
      /* ohne Zeigerbindung funktioniert das Ziehen weiter, solange die Maus auf dem Trenner bleibt */
    }
    root.classList.add("atlas-dragging");
    function move(ev) {
      var x = ev.clientX - rect.left;
      if (flip) x = rect.width - x;
      var textW = 2 * x - rect.width + plateCap; // Gruppe steht mittig
      if (!(textW + 14 + plateCap <= rect.width)) textW = x - 7; // Tafel füllt den Rest
      pct = Math.max(25, Math.min(70, (textW / rect.width) * 100));
      if (!frame)
        frame = requestAnimationFrame(function () {
          frame = 0;
          root.style.setProperty("--at-left", pct.toFixed(1) + "%");
        });
    }
    function up() {
      divider.removeEventListener("pointermove", move);
      divider.removeEventListener("pointerup", up);
      divider.removeEventListener("pointercancel", up);
      root.classList.remove("atlas-dragging");
      if (pct !== null) send("atlas:left:" + Math.round(pct));
    }
    divider.addEventListener("pointermove", move);
    divider.addEventListener("pointerup", up);
    divider.addEventListener("pointercancel", up);
    e.preventDefault();
  }

  /* ---------- Vergrößerung: Mausrad zoomt, Ziehen verschiebt ----------
     Nur für nackte Bilder. Eine Einheit mit Abdeckung wird nie vergrößert,
     weil die Vergrößerung das Bild ohne Abdeckung zeigen würde. */
  var z = { s: 1, x: 0, y: 0, frame: 0 };
  function paintZoom() {
    z.frame = 0;
    zoomImg.style.transform = "translate(" + z.x + "px," + z.y + "px) scale(" + z.s + ")";
    zoom.classList.toggle("atlas-pan", z.s > 1);
  }
  function queueZoom() {
    if (!z.frame) z.frame = requestAnimationFrame(paintZoom);
  }
  function resetZoom() {
    z.s = 1;
    z.x = z.y = 0;
    queueZoom();
  }
  function onZoomWheel(e) {
    e.preventDefault();
    var next = Math.max(1, Math.min(8, z.s * (e.deltaY < 0 ? 1.2 : 1 / 1.2)));
    if (next === z.s) return;
    var cx = e.clientX - window.innerWidth / 2;
    var cy = e.clientY - window.innerHeight / 2;
    z.x = cx - ((cx - z.x) * next) / z.s;
    z.y = cy - ((cy - z.y) * next) / z.s;
    z.s = next;
    if (next === 1) z.x = z.y = 0;
    queueZoom();
  }
  function onZoomDown(e) {
    if (e.button !== 0) return;
    var sx = e.clientX, sy = e.clientY, ox = z.x, oy = z.y, moved = false;
    try {
      zoom.setPointerCapture(e.pointerId);
    } catch (err) {
      /* siehe startDrag */
    }
    function move(ev) {
      var dx = ev.clientX - sx, dy = ev.clientY - sy;
      if (!moved && Math.abs(dx) + Math.abs(dy) < 5) return;
      moved = true;
      if (z.s > 1) {
        z.x = ox + dx;
        z.y = oy + dy;
        queueZoom();
      }
    }
    function up() {
      zoom.removeEventListener("pointermove", move);
      zoom.removeEventListener("pointerup", up);
      zoom.removeEventListener("pointercancel", up);
      if (!moved) closeZoom();
    }
    zoom.addEventListener("pointermove", move);
    zoom.addEventListener("pointerup", up);
    zoom.addEventListener("pointercancel", up);
    e.preventDefault();
  }
  function onZoomKey(e) {
    if (e.key === "Escape") closeZoom();
    else if (e.key === "ArrowRight" && state) show(state.current + 1);
    else if (e.key === "ArrowLeft" && state) show(state.current - 1);
    else return;
    e.preventDefault();
    e.stopPropagation();
  }
  function openZoom() {
    if (!state || !state.units.length) return;
    var unit = state.units[state.current];
    if (!unit.bare) return;
    zoomImg.src = unit.img.currentSrc || unit.img.src;
    z.s = 1;
    z.x = z.y = 0;
    paintZoom();
    zoom.classList.add("atlas-open");
    document.addEventListener("keydown", onZoomKey, true);
  }
  function closeZoom() {
    if (!zoom || !zoom.classList.contains("atlas-open")) return;
    zoom.classList.remove("atlas-open");
    document.removeEventListener("keydown", onZoomKey, true);
  }

  /* ---------- Schalter und Fortschritt ---------- */
  function paintToggle() {
    toggle.textContent = on ? "Bild einbetten" : "Bild seitlich";
    toggle.title =
      (on ? "Bild wieder in den Kartentext setzen" : "Text links, Bild rechts") +
      (cfg.shortcut ? " (" + cfg.shortcut + ")" : "");
  }
  function setSplit(v) {
    on = !!v;
    paintToggle();
    closeZoom();
    if (qa) arrange(null);
    send("atlas:split:" + (on ? 1 : 0));
  }
  function progress(left, total) {
    if (!bar) return;
    bar.style.transform = "scaleX(" + (total > 0 ? Math.max(0, Math.min(1, 1 - left / total)) : 0) + ")";
  }

  /* ---------- Diagnose (Werkzeuge → Atlas → Diagnose kopieren) ---------- */
  function describe(node) {
    if (!node) return null;
    var c = getComputedStyle(node), r = node.getBoundingClientRect();
    return {
      rect: [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)],
      display: c.display, position: c.position, float: c.float, boxSizing: c.boxSizing,
      width: c.width, maxWidth: c.maxWidth, margin: c.margin, padding: c.padding,
      zoom: c.zoom, transform: c.transform, textAlign: c.textAlign, columns: c.gridTemplateColumns,
    };
  }
  function diag() {
    var sheets = [];
    for (var i = 0; i < document.styleSheets.length; i++) {
      var s = document.styleSheets[i];
      sheets.push(s.href ? s.href.replace(/^https?:\/\/[^/]+/, "") : "inline:" + ((s.ownerNode && s.ownerNode.textContent) || "").length);
    }
    return JSON.stringify({
      window: [window.innerWidth, window.innerHeight, window.devicePixelRatio],
      scroll: [window.scrollX, window.scrollY, root.scrollWidth, root.scrollHeight],
      rootClass: root.className, bodyClass: document.body.className, qaClass: qa ? qa.className : null,
      vars: {
        left: getComputedStyle(root).getPropertyValue("--at-left"),
        plate: state ? state.split.style.getPropertyValue("--at-plate") : null,
      },
      html: describe(root), body: describe(document.body), qa: describe(qa),
      split: describe(state && state.split), text: describe(state && state.text),
      plate: describe(qa && qa.querySelector(".atlas-plate")),
      units: state
        ? state.units.map(function (u) {
            return { tag: u.el.tagName, cls: u.el.className, bare: u.bare, size: [u.img.naturalWidth, u.img.naturalHeight] };
          })
        : null,
      exact: mayHide, risky: risky, blocked: blocked, why: api.why, ms: api.ms,
      foreign: foreign === true ? "nicht lesbar" : foreign.length,
      sheets: sheets, cfg: cfg,
    });
  }

  function init() {
    qa = document.getElementById("qa");
    if (!qa) return;
    var styled = cfg.styled !== false;
    root.classList.add("atlas");
    if (styled) root.classList.add("atlas-styled");
    if (styled && cfg.font !== false) root.classList.add("atlas-font");
    if (styled && cfg.size) root.classList.add("atlas-size");
    if (cfg.fit !== false) root.classList.add("atlas-fit");
    if (cfg.dim) root.classList.add("atlas-dim");
    if (cfg.vcenter) root.classList.add("atlas-vcenter");
    if (cfg.align === "left") root.classList.add("atlas-align-left");
    else if (cfg.align === "center") root.classList.add("atlas-align-center");
    else if (cfg.align !== "keep") root.classList.add("atlas-align-auto");
    vh = window.innerHeight;

    var hud = el("div");
    hud.id = "atlas-hud";
    toggle = el("button");
    toggle.id = "atlas-toggle";
    toggle.type = "button";
    toggle.hidden = true;
    toggle.onclick = function () {
      setSplit(!on);
      toggle.blur(); // Leertaste soll weiter die Antwort zeigen
    };
    paintToggle();
    hud.appendChild(toggle);
    if (cfg.progress !== false) {
      var track = el("div");
      track.id = "atlas-bar";
      bar = el("i");
      track.appendChild(bar);
      document.body.appendChild(track);
    }
    document.body.appendChild(hud);

    zoom = el("div");
    zoom.id = "atlas-zoom";
    zoomImg = el("img");
    zoomImg.alt = "";
    zoomImg.draggable = false;
    zoom.appendChild(zoomImg);
    zoom.addEventListener("wheel", onZoomWheel, { passive: false });
    zoom.addEventListener("pointerdown", onZoomDown);
    document.body.appendChild(zoom);

    qa.addEventListener("click", queueCheck);
    document.addEventListener("keyup", queueCheck);
    window.addEventListener("resize", onResize);

    observer = new MutationObserver(onMutate);
    observer.observe(qa, { childList: true });
    if (qa.firstChild) layout();
  }

  var api = (window.__atlas = {
    progress: progress,
    toggle: function () {
      setSplit(!on);
    },
    layout: layout,
    diag: diag,
    ms: 0,
    why: null, // warum die letzte Karte ungeteilt blieb
    exact: function () {
      return mayHide; // true = für diese Karte war die genaue Sichtbarkeitsprüfung nötig
    },
    risky: function () {
      return risky; // true = Lage aller Elemente wurde geprüft, bevor ein Bild bewegt wurde
    },
    blocked: function () {
      return blocked; // true = Karte blieb ungeteilt, weil sie sich nicht sicher teilen ließ
    },
  });
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
