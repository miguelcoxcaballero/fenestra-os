// SPDX-License-Identifier: GPL-3.0-or-later
// The print dialog of desktop/portal/fenestra_portal (dialog.py, printing.py, render.py, service.py)
// ported line by line to the browser, with the same layout (metrics.py), strings and behaviour.
"use strict";

// ------------------------------------------------------------------ i18n, theme
let LANG = "es";
const _ = (s) => (LANG === "es" && STRINGS_ES[s] !== undefined ? STRINGS_ES[s] : s);
const fmt = (s, o) => s.replace(/\{(\w+)\}/g, (_m, k) => o[k]);
const $ = (sel, root = document) => root.querySelector(sel);
const el = (tag, cls, html) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (html !== undefined) e.innerHTML = html;
  return e;
};
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

const Theme = {
  dark: false, accent: "blue", pal: {},
  apply() {
    const pal = Object.assign({}, this.dark ? M.DARK : M.LIGHT);
    const acc = M.ACCENTS[this.accent][this.dark ? 1 : 0];
    const [r, g, b] = [1, 3, 5].map((i) => parseInt(acc.slice(i, i + 2), 16));
    pal.accent = acc;
    pal["accent-hover"] = `rgba(${r},${g},${b},0.9)`;
    pal["accent-press"] = `rgba(${r},${g},${b},0.8)`;
    const lum = [r, g, b].map((v) => { v /= 255; return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; });
    pal["on-accent"] = 0.2126 * lum[0] + 0.7152 * lum[1] + 0.0722 * lum[2] > 0.25 ? "#000000" : "#ffffff";
    pal["accent-text"] = M.ACCENT_TEXT[this.accent] ? M.ACCENT_TEXT[this.accent][this.dark ? 1 : 0] : acc;
    this.pal = pal;
    const root = document.documentElement;
    for (const [k, v] of Object.entries(pal)) root.style.setProperty("--" + k, v);
    root.dataset.simTheme = this.dark ? "dark" : "light";
    if (Dialog.current) Dialog.current.preview.refresh();
  },
};

// ------------------------------------------------------------------ the remembered settings (print-portal.ini)
const Config = {
  KEY: "fenestra-print-sim.ini",
  // Until the simulator saves its own, it starts from the settings of this laptop's dialog.
  SEED: { printer: "ET-2710-Series", allow_app: "1", orientation: "portrait", color: "1", paper: "iso_a4", number_up: "1",
    margins: "normal", duplex: "manual-long",
    "driver-ET-2710-Series": "MediaType=Plain;StpQuality=Standard;StpFullBleed=False;StpImageType=TextGraphics;StpColorCorrection=None;StpSaturation=None;StpDensity=None;StpBrightness=None;StpContrast=None" },
  load() {
    try {
      const v = localStorage.getItem(this.KEY);
      return v === null ? Object.assign({}, this.SEED) : JSON.parse(v) || {};
    } catch (e) { return Object.assign({}, this.SEED); }
  },
  get(k, d = "") { const v = this.load()[k]; return v === undefined ? d : v; },
  set(values) {
    const c = this.load();
    for (const [k, v] of Object.entries(values)) c[k] = String(v);
    try { localStorage.setItem(this.KEY, JSON.stringify(c)); } catch (e) { /* private window */ }
  },
  clear() { try { localStorage.setItem(this.KEY, "{}"); } catch (e) { /* ignore */ } },
  ini() {
    const c = this.load();
    return "[print]\n" + Object.entries(c).map(([k, v]) => `${k}=${v}`).join("\n");
  },
};

// ------------------------------------------------------------------ printing.py
const PDF_PRINTER = "Print to File";

function parseRanges(text, nPages) {
  const out = [];
  const parts = text.replace(/;/g, ",").split(",").map((p) => p.trim());
  if (!parts.some(Boolean)) throw new Error("empty");
  const int = (s) => { if (!/^\d+$/.test(s)) throw new Error(s); return parseInt(s, 10); };
  for (const p of parts) {
    if (!p) continue;
    let start, end;
    if (p.includes("-")) {
      const i = p.indexOf("-");
      const a = p.slice(0, i).trim(), b = p.slice(i + 1).trim();
      start = a ? int(a) : 1;
      if (b) end = int(b);
      else if (nPages) end = nPages;
      else throw new Error(p);
    } else {
      start = end = int(p);
    }
    if (start < 1 || end < start) throw new Error(p);
    if (nPages !== undefined && nPages !== null) {
      if (start > nPages) throw new Error(p);
      end = Math.min(end, nPages);
    }
    out.push([start - 1, end - 1]);
  }
  return out;
}

class Choice {
  constructor(o = {}) {
    Object.assign(this, {
      printer: PDF_PRINTER, copies: 1, collate: true, orientation: "portrait", pages: "all", ranges_text: "",
      color: true, paper: "iso_a4", number_up: 1, margins: "normal", duplex: "simplex", output_uri: "", driver: {},
    }, o);
    this.driver = Object.assign({}, this.driver);
  }
  clone() { return new Choice(JSON.parse(JSON.stringify(this))); }
  get is_pdf() { return this.printer === PDF_PRINTER; }
  sheet_mm() {
    const [w, h] = PAPER_MM[this.paper] || PAPER_MM.iso_a4;
    return this.orientation === "landscape" ? [h, w] : [w, h];
  }
  margins_mm() {
    if (this.margins === "none") return [0, 0, 0, 0];
    if (this.margins === "narrow") return Array(4).fill(M.NARROW_MARGIN_MM);
    return Array(4).fill(GTK_DEFAULT_MARGIN_MM);
  }
  selected_pages(n) {
    let idx;
    if (this.pages === "ranges") {
      let rs;
      try { rs = parseRanges(this.ranges_text, n); } catch (e) { rs = [[0, n - 1]]; }
      idx = [];
      for (const [a, b] of rs) for (let i = a; i <= b; i++) idx.push(i);
    } else {
      idx = [...Array(n).keys()];
    }
    if (this.pages === "odd") idx = idx.filter((i) => i % 2 === 0);
    else if (this.pages === "even") idx = idx.filter((i) => i % 2 === 1);
    return idx;
  }
}

// render.py
function gridFor(n, landscapeSheet) {
  const table = { 1: [1, 1], 2: [1, 2], 4: [2, 2], 6: [2, 3], 9: [3, 3], 16: [4, 4] };
  const [cols, rows] = table[n] || [1, 1];
  return landscapeSheet ? [rows, cols] : [cols, rows];
}
function sheetsFor(choice, n) {
  const idx = choice.selected_pages(n);
  const k = Math.max(1, choice.number_up);
  const out = [];
  for (let i = 0; i < idx.length; i += k) out.push(idx.slice(i, i + k));
  return out.length ? out : [[]];
}
function* cells(numberUp, w, h) {
  const [cols, rows] = gridFor(numberUp, w > h);
  const gap = numberUp > 1 ? Math.min(w, h) * M.PREVIEW_NUP_GAP : 0;
  const cw = (w - gap * (cols + 1)) / cols, ch = (h - gap * (rows + 1)) / rows;
  for (let i = 0; i < cols * rows; i++) {
    const r = Math.floor(i / cols), c = i % cols;
    yield [gap + c * (cw + gap), gap + r * (ch + gap), cw, ch];
  }
}
const rgba = (c) => `rgba(${Math.round(c[0] * 255)},${Math.round(c[1] * 255)},${Math.round(c[2] * 255)},${c[3] === undefined ? 1 : c[3]})`;

// draw_sheet(): one sheet w x h at the origin. pages: page indices, or null for a blank sheet.
function drawSheet(ctx, choice, w, h, pages, doc, colors, printing = false) {
  colors = colors || M.PREVIEW_LIGHT;
  const target = ctx;
  let off = null;
  if (!choice.color) {
    off = document.createElement("canvas");
    off.width = Math.max(1, Math.ceil(w)); off.height = Math.max(1, Math.ceil(h));
    ctx = off.getContext("2d");
  }
  if (!printing) { ctx.fillStyle = rgba(colors.sheet); ctx.fillRect(0, 0, w, h); }
  const [sw] = choice.sheet_mm();
  const scaleMm = w / sw;
  const cl = [...cells(choice.number_up, w, h)];
  const slots = pages !== null ? pages : cl.map(() => null);
  cl.forEach(([cx, cy, cw, ch], k) => {
    if (k >= slots.length) return;
    const page = slots[k];
    if (page === null || page === undefined || !doc) {
      if (pages === null || !doc) blankPage(ctx, choice, cx, cy, cw, ch, scaleMm, colors);
      return;
    }
    const [pw, ph] = doc.pageSize(page);
    const s = Math.min(cw / pw, ch / ph);
    const ox = cx + (cw - pw * s) / 2, oy = cy + (ch - ph * s) / 2;
    ctx.save();
    ctx.beginPath(); ctx.rect(ox, oy, pw * s, ph * s); ctx.clip();
    ctx.fillStyle = "#fff"; if (!printing) ctx.fillRect(ox, oy, pw * s, ph * s);
    ctx.translate(ox, oy);
    doc.drawPage(ctx, page, pw * s, ph * s);
    ctx.restore();
    if (choice.number_up > 1 && !printing) {
      ctx.strokeStyle = rgba(colors.outline); ctx.lineWidth = 1;
      ctx.strokeRect(ox + 0.5, oy + 0.5, pw * s - 1, ph * s - 1);
    }
  });
  if (off) {
    target.save();
    target.filter = "grayscale(1)";
    target.drawImage(off, 0, 0);
    target.restore();
  }
}

function blankPage(ctx, choice, cx, cy, cw, ch, scaleMm, colors) {
  const [pwMm, phMm] = choice.sheet_mm();
  const s = Math.min(cw / pwMm, ch / phMm);
  const pw = pwMm * s, ph = phMm * s;
  const ox = cx + (cw - pw) / 2, oy = cy + (ch - ph) / 2;
  if (choice.number_up > 1) {
    ctx.strokeStyle = rgba(colors.outline); ctx.lineWidth = 1;
    ctx.strokeRect(ox + 0.5, oy + 0.5, pw - 1, ph - 1);
  }
  const [top, bottom, left, right] = choice.margins_mm().map((m) => m * s);
  const inset = Math.min(pw, ph) * 0.04;
  const x0 = ox + Math.max(left, inset), y0 = oy + Math.max(top, inset);
  const x1 = ox + pw - Math.max(right, inset), y1 = oy + ph - Math.max(bottom, inset);
  const lineH = Math.max(1, ph * 0.012), step = lineH * 2.6;
  ctx.fillStyle = rgba(colors.hint);
  ctx.fillRect(x0, y0, (x1 - x0) * 0.45, lineH * 1.6);
  let y = y0 + step * 1.8, i = 0;
  while (y + lineH <= y1) {
    const frac = i % 7 === 6 ? 0.62 : (i % 3 ? 0.94 : 1.0);
    if (i % 7 !== 0 || i === 0) ctx.fillRect(x0, y, (x1 - x0) * frac, lineH);
    y += step; i++;
  }
}

// ------------------------------------------------------------------ documents
const Docs = {
  sample(key, pages) {
    const d = DOCS[key];
    const n = pages || d.pages;
    return {
      key, title: d.title, n, orientation: d.orientation,
      pageSize: () => d.size,
      drawPage: (ctx, i, w, h) => { ctx.save(); d.draw(ctx, i, n, w, h); ctx.restore(); },
    };
  },
  async pdf(file) {
    if (!window.pdfjsLib) {
      await new Promise((ok, bad) => {
        const s = document.createElement("script");
        s.src = "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js";
        s.onload = ok; s.onerror = () => bad(new Error("No se pudo cargar pdf.js (sin conexión)"));
        document.head.appendChild(s);
      });
      pdfjsLib.GlobalWorkerOptions.workerSrc = "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js";
    }
    const data = new Uint8Array(await file.arrayBuffer());
    const pdf = await pdfjsLib.getDocument({ data }).promise;
    const pages = [];
    for (let i = 1; i <= pdf.numPages; i++) {
      const p = await pdf.getPage(i);
      const vp1 = p.getViewport({ scale: 1 });
      const scale = 1400 / Math.max(vp1.width, vp1.height);
      const vp = p.getViewport({ scale });
      const c = document.createElement("canvas");
      c.width = Math.ceil(vp.width); c.height = Math.ceil(vp.height);
      const cx = c.getContext("2d"); cx.fillStyle = "#fff"; cx.fillRect(0, 0, c.width, c.height);
      await p.render({ canvasContext: cx, viewport: vp }).promise;
      pages.push({ size: [vp1.width, vp1.height], canvas: c });
    }
    return {
      key: "pdf", title: file.name, n: pages.length,
      orientation: pages[0].size[0] > pages[0].size[1] ? "landscape" : "portrait",
      pageSize: (i) => pages[i].size,
      drawPage: (ctx, i, w, h) => ctx.drawImage(pages[i].canvas, 0, 0, w, h),
    };
  },
};

// ------------------------------------------------------------------ combo boxes (Choices)
let openMenu = null;
function closeMenu() {
  if (openMenu) { openMenu.menu.remove(); openMenu.combo.btn.classList.remove("open"); openMenu = null; }
}
document.addEventListener("mousedown", (e) => {
  if (openMenu && !openMenu.menu.contains(e.target) && !openMenu.combo.btn.contains(e.target)) closeMenu();
}, true);

class Combo {
  // items: [[id, label]]; icons: {id: svg}
  constructor(items, selected, icons, onChange) {
    this.icons = icons || null;
    this.onChange = onChange;
    this.btn = el("button", "fp-dd" + (icons ? " icon" : ""));
    this.btn.type = "button";
    this.btn.innerHTML = `${icons ? '<span class="ico"></span>' : ""}<span class="txt"></span><span class="chev">${ICONS.chevron}</span>`;
    this.btn.addEventListener("click", () => (openMenu && openMenu.combo === this ? closeMenu() : this.popup()));
    this.btn.addEventListener("keydown", (e) => this.key(e));
    this.tooltips = {};
    this.setItems(items, selected);
  }
  setItems(items, keep) {
    const cur = keep !== undefined ? keep : this.value;
    this.ids = items.map((i) => i[0]);
    this.labels = items.map((i) => i[1]);
    this.sel = this.ids.indexOf(cur);
    if (this.sel < 0) this.sel = 0;
    this.render();
  }
  get value() { return this.ids ? this.ids[this.sel] : undefined; }
  setValue(v, quiet = true) {
    const i = this.ids.indexOf(v);
    if (i >= 0 && i !== this.sel) { this.sel = i; this.render(); if (!quiet && this.onChange) this.onChange(); }
  }
  setSelected(i, quiet = false) {
    if (i === this.sel) return;
    this.sel = i; this.render();
    if (!quiet && this.onChange) this.onChange();
  }
  render() {
    $(".txt", this.btn).textContent = this.labels[this.sel] || "";
    if (this.icons) $(".ico", this.btn).innerHTML = this.icons[this.value] || "";
  }
  key(e) {
    if (openMenu && openMenu.combo === this) {
      const m = openMenu;
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        m.kbd = Math.max(0, Math.min(this.ids.length - 1, m.kbd + (e.key === "ArrowDown" ? 1 : -1)));
        [...m.menu.children].forEach((r, i) => r.classList.toggle("kbd", i === m.kbd));
        m.menu.children[m.kbd].scrollIntoView({ block: "nearest" });
        e.preventDefault();
      } else if (e.key === "Enter" || e.key === " ") {
        closeMenu(); this.setSelected(m.kbd); e.preventDefault(); e.stopPropagation();
      } else if (e.key === "Escape") {
        closeMenu(); e.preventDefault(); e.stopPropagation();
      }
      return;
    }
    if (e.key === "ArrowDown" && e.altKey || e.key === " " || e.key === "Enter") {
      this.popup(); e.preventDefault(); e.stopPropagation();
    }
  }
  popup() {
    closeMenu();
    const layer = $("#overlay");
    const lr = layer.getBoundingClientRect(), b0 = this.btn.getBoundingClientRect();
    const k = lr.width / layer.offsetWidth || 1;          // the stage may be scaled to fit
    const br = { left: (b0.left - lr.left) / k, top: (b0.top - lr.top) / k, width: b0.width / k };
    const L = { left: 0, top: 0, width: layer.offsetWidth, height: layer.offsetHeight };
    const icon = !!this.icons;
    const rowH = icon ? 40 : 33, pitch = rowH + 4, inset = 1 + 4 + 2;
    const menu = el("div", "fp-menu" + (icon ? " icon" : ""));
    this.ids.forEach((id, i) => {
      const r = el("div", "row" + (i === this.sel ? " sel" : ""),
        `${icon ? `<span class="ico">${this.icons[id] || ""}</span>` : ""}<span>${esc(this.labels[i])}</span>`);
      if (this.tooltips[id]) r.title = this.tooltips[id];
      r.addEventListener("click", () => { closeMenu(); this.setSelected(i); this.btn.focus(); });
      menu.appendChild(r);
    });
    menu.style.width = br.width + "px";
    menu.style.left = br.left + "px";
    layer.appendChild(menu);
    // GTK: the list opens over the combo, the selected row on top of it (menu_over_combo()).
    const shift = icon ? -3 : 1;
    const full = this.ids.length * pitch + 2 * 4 + 2;
    const maxH = L.height - 16;
    menu.style.maxHeight = maxH + "px";
    let top = br.top + shift - inset - this.sel * pitch;
    const h = Math.min(full, maxH);
    top = Math.max(8, Math.min(top, L.height - 8 - h));
    menu.style.top = top + "px";
    if (full > maxH) menu.children[this.sel].scrollIntoView({ block: "center" });
    this.btn.classList.add("open");
    openMenu = { combo: this, menu, kbd: this.sel };
  }
}

// ------------------------------------------------------------------ the preview
class Preview {
  constructor(dialog) {
    this.dialog = dialog;
    this.box = el("div", "fp-preview");
    this.canvas = el("canvas");
    this.note = el("div", "note", esc(_("This app doesn't support print preview")));
    this.box.append(this.canvas, this.note);
    this.index = 0;
    this.fitWidth = false;
  }
  sheets() {
    const d = this.dialog;
    if (!d.doc) return [null];
    return sheetsFor(d.choice, d.doc.n);
  }
  refresh() {
    const d = this.dialog;
    const n = this.sheets().length;
    this.index = Math.max(0, Math.min(this.index, n - 1));
    const hasDoc = !!d.doc;
    d.counter.textContent = hasDoc ? `${this.index + 1} / ${n}` : "";
    d.prevBtn.disabled = !(hasDoc && this.index > 0);
    d.nextBtn.disabled = !(hasDoc && this.index < n - 1);
    this.note.style.display = hasDoc ? "none" : "";
    this.canvas.style.display = hasDoc ? "" : "none";
    this.box.classList.toggle("fit", this.fitWidth && hasDoc);
    if (hasDoc) this.draw();
  }
  go(delta) { this.index += delta; this.refresh(); }
  setFitWidth(on) { this.fitWidth = on; this.refresh(); }
  draw() {
    const d = this.dialog, c = d.choice;
    const width = M.PREVIEW_BOX[2] - 2;
    let height = M.PREVIEW_BOX[3] - 2;
    const [sw, sh] = c.sheet_mm();
    const m = M.PREVIEW_MARGIN;
    if (this.fitWidth) height = Math.round((width - 2 * m) * sh / sw + 2 * m);
    const dpr = window.devicePixelRatio || 1;
    this.canvas.width = Math.round(width * dpr); this.canvas.height = Math.round(height * dpr);
    this.canvas.style.width = width + "px"; this.canvas.style.height = height + "px";
    const cr = this.canvas.getContext("2d");
    cr.scale(dpr, dpr);
    const colors = Theme.dark ? M.PREVIEW_DARK : M.PREVIEW_LIGHT;
    const availW = Math.max(1, width - 2 * m), availH = Math.max(1, height - 2 * m);
    const s = this.fitWidth ? availW / sw : Math.min(availW / sw, availH / sh);
    const w = sw * s, h = sh * s;
    const x = Math.round((width - w) / 2), y = this.fitWidth ? m : Math.round((height - h) / 2);
    const sc = colors.shadow;
    for (let i = M.PREVIEW_SHADOW; i > 0; i--) {
      cr.fillStyle = rgba([sc[0], sc[1], sc[2], sc[3] / M.PREVIEW_SHADOW]);
      cr.fillRect(x - i / 2, y - i / 4, w + i, h + i);
    }
    const sheets = this.sheets();
    const sheet = sheets[Math.min(this.index, sheets.length - 1)];
    cr.save(); cr.translate(x, y); cr.beginPath(); cr.rect(0, 0, w, h); cr.clip();
    drawSheet(cr, c, w, h, sheet, d.doc, colors);
    cr.restore();
  }
}

// ------------------------------------------------------------------ the dialog
class Dialog {
  // opts: {title, has_current, has_selection, modal}; onDone(response, choice)
  constructor(appTitle, choice, opts, onDone, doc) {
    Dialog.current = this;
    this.opts = opts;
    this.choice = choice;
    this.appChoice = choice.clone();
    this.doc = doc;
    this.onDone = onDone;
    this.finished = false;
    this.loading = false;
    this.userPickedPrinter = false;
    this.printers = {};
    this.printerIds = [];
    this.root = el("div", "fp fv");
    this.root.tabIndex = -1;
    this.build(appTitle);
    if (!this.allowApp.on) this.applyRemembered();
    this.syncFromChoice();
    this.watcher = Sim.watchPrinters((info) => this.printerAdded(info), () => this.updateStatus());
    this.root.addEventListener("keydown", (e) => this.onKey(e));
    this.root.addEventListener("mousedown", () => this.root.classList.remove("fv"));
    this.root.addEventListener("keydown", (e) => { if (e.key === "Tab") this.root.classList.add("fv"); });
  }
  mount(holder) {
    holder.innerHTML = "";
    holder.appendChild(this.root);
    this.preview.refresh();
    // The reference opens with the keyboard focus (ring and pill) on the printer combo.
    this.printerDd.btn.focus({ preventScroll: true });
  }

  // ---------------------------------------------------------------- building
  build(appTitle) {
    const r = this.root;
    // title row
    const title = appTitle ? fmt(_("{title} - Printing"), { title: appTitle }) : _("Printing");
    const tl = el("div", "abs fp-title", esc(title));
    Object.assign(tl.style, { left: "24px", top: "27px", width: (488 - 32 - 24) + "px" });
    r.appendChild(tl);
    this.summary = el("div", "abs fp-hint");
    Object.assign(this.summary.style, { left: "24px", top: "44px" });
    r.appendChild(this.summary);
    const hb = 32;
    const put = (btn, [gx, gy, gw, gh]) => {
      btn.style.left = (gx + gw / 2 - hb / 2) + "px"; btn.style.top = (gy + gh / 2 - hb / 2) + "px"; r.appendChild(btn);
    };
    this.prevBtn = el("button", "fp-nav", ICONS.caretL); this.prevBtn.title = _("Previous page");
    this.nextBtn = el("button", "fp-nav", ICONS.caretR); this.nextBtn.title = _("Next page");
    this.fitBtn = el("button", "fp-nav", ICONS.fit); this.fitBtn.title = _("Fit to width");
    put(this.prevBtn, [488, 43, 6, 8]); put(this.nextBtn, [584, 43, 6, 8]); put(this.fitBtn, [643, 41, 16, 12]);
    this.counter = el("div", "fp-counter");
    const cx0 = 488 + 3 + hb / 2, cx1 = 584 + 3 - hb / 2;
    Object.assign(this.counter.style, { left: cx0 + "px", width: (cx1 - cx0) + "px", top: (43 + 4 - hb / 2) + "px" });
    r.appendChild(this.counter);
    this.prevBtn.onclick = () => this.preview.go(-1);
    this.nextBtn.onclick = () => this.preview.go(+1);
    this.fitBtn.onclick = () => { this.fitBtn.classList.toggle("checked"); this.preview.setFitWidth(this.fitBtn.classList.contains("checked")); };
    const close = el("button", "fp-close", ICONS.close); close.title = _("Close"); close.tabIndex = -1;
    close.onclick = () => this.finish(1);
    r.appendChild(close);

    // settings column
    const col = el("div", "fp-col");
    this.mainPage = el("div", "fp-page main");
    this.morePage = el("div", "fp-page more");
    col.append(this.mainPage, this.morePage);
    r.appendChild(col);
    this.buildMain(this.mainPage);
    this.buildMore(this.morePage);

    this.preview = new Preview(this);
    r.appendChild(this.preview.box);

    // footer
    const footer = el("div", "fp-footer");
    // Web version: no "Allow the app to change print preferences": the app's request always wins.
    this.allowApp = { on: true };
    this.printButton = el("button", "fp-btn", esc(this.opts.accept_label || _("Print")));
    this.cancelButton = el("button", "fp-btn", esc(_("Cancel")));
    Object.assign(this.printButton.style, { left: "433px", width: "193px" });
    Object.assign(this.cancelButton.style, { left: "634px", width: "192px" });
    footer.append(this.printButton, this.cancelButton);
    r.appendChild(footer);
    this.printButton.onclick = () => this.onPrint();
    this.cancelButton.onclick = () => this.finish(1);
  }

  label(text, top, cls = "fp-label") {
    const l = el("div", cls, `<span>${esc(text)}</span>`);
    l.style.marginTop = top + "px";
    return l;
  }
  // A label over its control: label box 17 px, control 12 px under it.
  field(box, text, widget, top = 17) {
    const l = this.label(text, top);
    box.appendChild(l);
    widget.style.marginTop = "12px";
    box.appendChild(widget);
    return l;
  }
  check(text, on, onToggle) {
    const node = el("div", "fp-check" + (on ? " on" : ""), `<span class="box">${ICONS.check}</span><span class="fp-check-text">${esc(text)}</span>`);
    node.tabIndex = 0;
    const obj = {
      node, get on() { return node.classList.contains("on"); },
      set(v, quiet) { node.classList.toggle("on", v); if (!quiet && onToggle) onToggle(); },
    };
    node.addEventListener("click", () => obj.set(!obj.on));
    node.addEventListener("keydown", (e) => { if (e.key === " ") { obj.set(!obj.on); e.preventDefault(); } });
    return obj;
  }
  link(text, icon) {
    const b = el("button", "fp-link" + (icon ? " icon" : ""), `${icon ? `<span class="ico">${icon}</span>` : ""}<span>${esc(text)}</span>`);
    b.type = "button";
    return b;
  }

  buildMain(box) {
    const changed = () => this.onChanged();
    this.printerDd = new Combo([], undefined, null, () => this.onPrinterChanged());
    this.printerLabel = this.field(box, _("Printer"), this.printerDd.btn, 1);
    this.printerStatus = el("div", "fp-caption"); this.printerStatus.style.display = "none";
    box.appendChild(this.printerStatus);
    this.addPrinterInfo({ name: PDF_PRINTER, label: _("Save as PDF"), is_pdf: true });

    this.addPrinter = this.link(_("Add a printer"), ICONS.add);
    this.addPrinter.style.marginTop = "13px";
    this.addPrinter.onclick = () => Sim.addPrinterDialog();
    const lw = el("div"); lw.appendChild(this.addPrinter); box.appendChild(lw);

    // copies
    this.copies = el("div", "fp-spin", `<input inputmode="numeric" value="1"><button type="button" tabindex="-1">${ICONS.minus}</button><button type="button" tabindex="-1">${ICONS.plus}</button>`);
    const [ci, minus, plus] = this.copies.children;
    this.copiesInput = ci;
    const setCopies = (v) => { v = Math.max(1, Math.min(999, v | 0 || 1)); ci.value = v; minus.disabled = v <= 1; plus.disabled = v >= 999; changed(); };
    minus.onclick = () => setCopies(+ci.value - 1);
    plus.onclick = () => setCopies(+ci.value + 1);
    ci.addEventListener("change", () => setCopies(+ci.value));
    ci.addEventListener("keydown", (e) => {
      if (e.key === "ArrowUp") { setCopies(+ci.value + 1); e.preventDefault(); }
      if (e.key === "ArrowDown") { setCopies(+ci.value - 1); e.preventDefault(); }
      if (e.key === "PageUp") { setCopies(+ci.value + 10); e.preventDefault(); }
      if (e.key === "PageDown") { setCopies(+ci.value - 10); e.preventDefault(); }
    });
    ci.addEventListener("input", () => { if (/^\d+$/.test(ci.value)) { minus.disabled = +ci.value <= 1; changed(); } });
    this.setCopies = (v) => { ci.value = v; minus.disabled = v <= 1; plus.disabled = v >= 999; };
    this.copiesLabel = this.field(box, _("Copies"), this.copies, 2);
    this.collate = this.check(_("Collate"), true, changed);
    this.collate.node.style.marginTop = "8px";
    box.appendChild(this.collate.node);

    this.orientation = new Combo([["landscape", _("Landscape")], ["portrait", _("Portrait")]], "portrait",
      { portrait: ICONS.portrait, landscape: ICONS.landscape }, changed);
    this.orientationLabel = this.field(box, _("Orientation"), this.orientation.btn, 17);

    this.pagesSlotMain = el("div"); box.appendChild(this.pagesSlotMain);
    this.pagesField = el("div");
    const pages = [["all", _("All pages")], ["odd", _("Odd pages only")], ["even", _("Even pages only")]];
    if (this.opts.has_current) pages.push(["current", _("Current page")]);
    if (this.opts.has_selection) pages.push(["selection", _("Selection")]);
    pages.push(["ranges", _("Custom range")]);
    this.pages = new Combo(pages, "all", null, changed);
    this.pagesLabel = this.field(this.pagesField, _("Pages"), this.pages.btn);
    this.ranges = el("div", "fp-entry", `<input placeholder="${esc(_("e.g. 1-5, 8, 11-13"))}">`);
    this.ranges.style.marginTop = "8px";
    this.rangesInput = this.ranges.firstChild;
    this.rangesInput.addEventListener("input", changed);
    this.pagesField.appendChild(this.ranges);
    this.pagesSlotMain.appendChild(this.pagesField);

    this.color = new Combo([["color", _("Color")], ["mono", _("Black and white")]], "color", null, changed);
    this.colorLabel = this.field(box, _("Color mode"), this.color.btn);

    // Web version: no "Print to file" (Save as PDF stays in the printer list).
    this.moreLink = this.link(_("More settings"));
    this.moreLink.style.marginTop = "20px";
    this.moreLink.onclick = () => this.root.classList.add("show-more");
    const mw = el("div"); mw.appendChild(this.moreLink); box.appendChild(mw);
  }

  buildMore(box) {
    const changed = () => this.onChanged();
    const top = el("div"); top.style.cssText = "display:flex;align-items:center;gap:8px;height:32px;margin-top:-3px";
    const back = el("button", "fp-nav", ICONS.back); back.title = _("Back");
    back.style.position = "relative"; back.style.marginLeft = "-8px";
    back.onclick = () => this.root.classList.remove("show-more");
    const head = el("div", "fp-title", `<span style="position:relative;top:var(--nudge,0px)">${esc(_("More settings"))}</span>`);
    top.append(back, head);
    box.appendChild(top);
    this.pagesSlotMore = el("div"); box.appendChild(this.pagesSlotMore);
    const papers = [...M.PAPER_SIZES];
    if (!papers.includes(this.choice.paper)) papers.push(this.choice.paper);
    this.paper = new Combo(papers.map((p) => [p, _(PAPER_LABELS[p] || p)]), this.choice.paper, null, changed);
    this.field(box, _("Paper size"), this.paper.btn, 12);
    this.driverBox = el("div"); box.appendChild(this.driverBox);
    this.driverColorBox = el("div");
    this.driverRows = {};
    this.driverFor = null;
    this.numberUp = new Combo(M.PAGES_PER_SHEET.map((n) => [String(n), String(n)]), "1", null, changed);
    this.field(box, _("Pages per sheet"), this.numberUp.btn);
    this.margins = new Combo([["normal", _("Normal")], ["narrow", _("Narrow")], ["none", _("None")]], "normal", null, changed);
    this.field(box, _("Margins"), this.margins.btn);
    this.duplex = new Combo(Dialog.duplexItems(true), "simplex", null, changed);
    this.duplexAuto = true;
    this.duplexLabel = this.field(box, _("Two-sided printing"), this.duplex.btn);
    box.appendChild(this.driverColorBox);
  }

  static duplexItems(auto) {
    if (auto) return [["simplex", _("Print on one side")], ["long", _("Print on both sides, flip on long edge")],
      ["short", _("Print on both sides, flip on short edge")]];
    return [["simplex", _("Print on one side")], ["manual-long", _("Print on both sides manually, flip on long edge")],
      ["manual-short", _("Print on both sides manually, flip on short edge")]];
  }
  syncDuplex(printer) {
    const auto = Sim.autoDuplex(printer);
    if (auto === this.duplexAuto) return;
    this.duplexAuto = auto;
    const cur = this.duplex.value || "simplex";
    this.duplex.setItems(Dialog.duplexItems(auto));
    const twin = { long: "manual-long", short: "manual-short", "manual-long": "long", "manual-short": "short" };
    this.duplex.setValue(twin[cur] || cur);
  }

  // ---------------------------------------------------------------- the printer's own options
  driverKey(printer) { return "driver-" + printer.replace(/[^A-Za-z0-9_-]/g, "_"); }
  driverSaved(printer) {
    const out = {};
    for (const part of Config.get(this.driverKey(printer), "").split(";")) {
      const i = part.indexOf("=");
      if (i > 0) out[part.slice(0, i)] = part.slice(i + 1);
    }
    return out;
  }
  buildDriverRows(printer) {
    if (printer === this.driverFor) return;
    this.driverFor = printer;
    this.driverBox.innerHTML = ""; this.driverColorBox.innerHTML = "";
    this.driverRows = {};
    const wanted = Object.assign({}, this.driverSaved(printer), this.choice.printer === printer ? this.choice.driver : {});
    const options = Sim.driverOptions(printer).filter((o) => o.section !== "hidden");
    let headerDone = false;
    for (const o of options) {
      const target = o.section === "color" ? this.driverColorBox : this.driverBox;
      if (o.section === "color" && !headerDone) {
        target.appendChild(this.label(_("Colour adjustments"), 17 + 8, "fp-label fp-section"));
        headerDone = true;
      }
      const sel = wanted[o.keyword] !== undefined ? wanted[o.keyword] : o.default;
      const dd = new Combo(o.choices.map(([v, t]) => [v, _(t)]), sel, null, () => this.onChanged());
      this.field(target, _(o.label), dd.btn);
      this.driverRows[o.keyword] = dd;
    }
  }
  readDriver() {
    const out = {};
    for (const [kw, dd] of Object.entries(this.driverRows)) if (dd.value) out[kw] = dd.value;
    return out;
  }

  // ---------------------------------------------------------------- printers
  addPrinterInfo(info) {
    this.printers[info.name] = info;
    const pos = this.printerIds.length && !info.is_pdf ? this.printerIds.length - 1 : this.printerIds.length;
    this.printerIds.splice(pos, 0, info.name);
    this.loading = true;
    // GTK keeps the selected row when a printer is inserted before it.
    const curId = this.printerDd.value;
    this.printerDd.setItems(this.printerIds.map((n) => [n, this.printers[n].label]), curId);
    this.printerDd.tooltips = Object.fromEntries(this.printerIds.map((n) => [n, this.printers[n].location || ""]));
    this.loading = false;
  }
  printerAdded(info) {
    if (this.finished) return;
    this.addPrinterInfo(info);
    const want = this.preferredPrinter;
    if (info.name === want || (info.is_default && !this.userPickedPrinter && this.currentPrinter() !== want)) {
      this.selectPrinter(info.name);
    }
  }
  printerRemoved(name) {
    const i = this.printerIds.indexOf(name);
    if (i < 0) return;
    const cur = this.currentPrinter();
    this.printerIds.splice(i, 1);
    delete this.printers[name];
    this.printerDd.setItems(this.printerIds.map((n) => [n, this.printers[n].label]), cur === name ? PDF_PRINTER : cur);
    this.onChanged();
  }
  currentPrinter() { return this.printerDd.value || PDF_PRINTER; }
  selectPrinter(name) {
    if (this.printerIds.includes(name)) {
      this.loading = true;
      this.printerDd.setSelected(this.printerIds.indexOf(name), true);
      this.loading = false;
      this.onChanged();
    }
  }
  onPrinterChanged() {
    if (!this.loading) this.userPickedPrinter = true;
    this.onChanged();
  }
  updateStatus() {
    const info = this.printers[this.currentPrinter()];
    let text = "";
    if (info && !info.is_pdf) {
      const st = Sim.cupsState(info.name);
      if (st.state && st.problem) text = st.state;
    }
    this.printerStatus.textContent = text;
    this.printerStatus.style.display = text ? "" : "none";
  }

  // ---------------------------------------------------------------- state
  syncFromChoice() {
    const c = this.choice;
    this.loading = true;
    this.preferredPrinter = c.printer || Config.get("printer", "");
    this.setCopies(c.copies);
    this.collate.set(c.collate, true);
    this.orientation.setValue(c.orientation);
    this.pages.setValue(this.pages.ids.includes(c.pages) ? c.pages : "all");
    this.rangesInput.value = c.ranges_text;
    this.color.setValue(c.color ? "color" : "mono");
    this.paper.setValue(c.paper);
    this.numberUp.setValue(String(c.number_up));
    this.margins.setValue(c.margins);
    const twin = { long: "manual-long", short: "manual-short", "manual-long": "long", "manual-short": "short" };
    this.duplex.setValue(this.duplex.ids.includes(c.duplex) ? c.duplex : (twin[c.duplex] || "simplex"));
    this.loading = false;
    this.selectPrinter(this.preferredPrinter);
    this.onChanged();
  }
  readChoice() {
    const c = this.choice;
    c.printer = this.currentPrinter();
    c.copies = parseInt(this.copiesInput.value, 10) || 1;
    c.collate = this.collate.on;
    c.orientation = this.orientation.value;
    c.pages = this.pages.value;
    c.ranges_text = this.rangesInput.value.trim();
    c.color = this.color.value === "color";
    c.paper = this.paper.value;
    c.number_up = parseInt(this.numberUp.value, 10);
    c.margins = this.margins.value;
    c.duplex = this.duplex.value;
    c.driver = this.driverFor === c.printer ? this.readDriver() : {};
  }
  rangesValid() {
    if (this.choice.pages !== "ranges") return true;
    try { parseRanges(this.choice.ranges_text, this.doc ? this.doc.n : undefined); return true; } catch (e) { return false; }
  }
  onChanged() {
    if (this.loading || !this.duplex) return;
    const printer = this.currentPrinter();
    if (printer !== this.driverFor) {
      this.loading = true;
      this.buildDriverRows(printer);
      this.syncDuplex(printer);
      this.loading = false;
    }
    this.readChoice();
    const c = this.choice;
    const info = this.printers[printer];
    const printerIsPdf = !info || info.is_pdf;
    const vis = (w, on) => { w.style.display = on ? "" : "none"; };
    for (const w of [this.copiesLabel, this.copies, this.colorLabel, this.color.btn]) vis(w, !printerIsPdf);
    vis(this.collate.node, !printerIsPdf && c.copies > 1);
    this.orientationLabel.style.marginTop = (printerIsPdf ? 2 : 17) + "px";
    const slot = printerIsPdf ? this.pagesSlotMore : this.pagesSlotMain;
    if (this.pagesField.parentNode !== slot) slot.appendChild(this.pagesField);
    this.pagesLabel.style.marginTop = (printerIsPdf ? 12 : 17) + "px";
    vis(this.ranges, c.pages === "ranges");
    const ok = this.rangesValid();
    this.ranges.classList.toggle("error", !ok);
    this.printButton.disabled = !ok;
    vis(this.duplex.btn, !c.is_pdf);
    vis(this.duplexLabel, !c.is_pdf);
    this.updateStatus();
    this.updateSummary();
    this.preview.refresh();
    Sim.dialogChanged(this);
  }

  // "Allow the app to change print preferences": off = the last settings used here win.
  static REMEMBERED = ["orientation", "color", "paper", "number_up", "margins", "duplex"];
  remembered() {
    const out = {};
    for (const k of Dialog.REMEMBERED) {
      const v = Config.get(k, "");
      if (v === "") continue;
      if (k === "color") out[k] = v === "1";
      else if (k === "number_up") { const n = parseInt(v, 10); if (!isNaN(n)) out[k] = n; }
      else out[k] = v;
    }
    return out;
  }
  applyRemembered() { Object.assign(this.choice, this.remembered()); }
  onAllowApp() {
    if (this.loading) return;
    if (this.allowApp.on) {
      for (const k of Dialog.REMEMBERED) this.choice[k] = this.appChoice[k];
    } else {
      this.readChoice();
      this.applyRemembered();
    }
    const printer = this.currentPrinter();
    this.choice.printer = printer;
    this.syncFromChoice();
    this.selectPrinter(printer);
  }
  updateSummary() {
    if (!this.doc) { this.summary.style.display = "none"; return; }
    const c = this.choice;
    let sheets = sheetsFor(c, this.doc.n).filter((s) => s.length).length;
    if (c.duplex !== "simplex" && !c.is_pdf) sheets = Math.ceil(sheets / 2);
    const total = sheets * c.copies;
    let text;
    if (c.is_pdf) text = total === 1 ? _("Total: 1 page") : fmt(_("Total: {n} pages"), { n: total });
    else text = total === 1 ? _("Total: 1 sheet of paper") : fmt(_("Total: {n} sheets of paper"), { n: total });
    this.summary.textContent = text;
    this.summary.style.display = "";
  }

  // ---------------------------------------------------------------- finishing
  onKey(e) {
    if (e.key === "Escape" && !openMenu) { this.finish(1); e.preventDefault(); }
    else if (e.key === "Enter" && !openMenu && !e.target.classList.contains("fp-dd") && e.target.tagName !== "BUTTON") {
      if (!this.printButton.disabled) this.onPrint();
      e.preventDefault();
    }
  }
  onPrint() {
    this.readChoice();
    if (!this.rangesValid()) return;
    const c = this.choice;
    if (c.is_pdf && !c.output_uri) {
      if (this.opts.no_save_dialog) c.output_uri = "file:///home/usuario/Documentos/" + safeBasename(this.opts.title) + ".pdf";
      else { this.askPdfPath(); return; }
    }
    this.finish(0);
  }
  askPdfPath() {
    SaveDialog.open(safeBasename(this.opts.title) + ".pdf", (name) => {
      if (name === null) return;          // cancelled: stay in the print dialog
      let uri = "file:///home/usuario/Documentos/" + name;
      if (!uri.toLowerCase().endsWith(".pdf")) uri += ".pdf";
      this.choice.output_uri = uri;
      this.finish(0);
    });
  }
  finish(response) {
    if (this.finished) return;
    this.finished = true;
    closeMenu();
    this.watcher.stop();
    if (response === 0) {
      const c = this.choice;
      Config.set({
        printer: this.currentPrinter(), allow_app: this.allowApp.on ? "1" : "0", orientation: c.orientation,
        color: c.color ? "1" : "0", paper: c.paper, number_up: c.number_up, margins: c.margins, duplex: c.duplex,
      });
      if (Object.keys(c.driver).length && !c.is_pdf) {
        Config.set({ [this.driverKey(c.printer)]: Object.entries(c.driver).map(([k, v]) => `${k}=${v}`).join(";") });
      }
    }
    const cb = this.onDone; this.onDone = null;
    this.root.remove();
    if (Dialog.current === this) Dialog.current = null;
    if (cb) cb(response, this.choice);
  }
}
Dialog.current = null;

function safeBasename(title) {
  const name = (title || "").replace(/[/\\:*?"<>|\n\r\t]/g, "").replace(/^[ .]+|[ .]+$/g, "");
  return (name || "document").slice(0, 120);
}

// ------------------------------------------------------------------ small windows
// A window of the dialog's look floating over the "screen": title row, draggable, close button.
function floatingWindow(title, inner, width) {
  const w = el("div", "fp fp-small");
  w.style.width = width + "px";
  const bar = el("div", "wtitle", `<span>${esc(title)}</span>`);
  const close = el("button", "fp-close", ICONS.close);
  bar.appendChild(close);
  w.appendChild(bar);
  w.style.paddingTop = "48px";
  w.appendChild(inner);
  const layer = $("#overlay");
  w.style.position = "absolute";
  layer.appendChild(w);
  w.style.left = Math.max(8, (layer.offsetWidth - width) / 2) + "px";
  w.style.top = Math.max(8, (layer.offsetHeight - w.offsetHeight) / 2) + "px";
  let drag = null;
  const scale = () => layer.getBoundingClientRect().width / layer.offsetWidth || 1;
  bar.addEventListener("mousedown", (e) => {
    if (e.target.closest(".fp-close")) return;
    drag = [e.clientX, e.clientY, w.offsetLeft, w.offsetTop, scale()];
  });
  window.addEventListener("mousemove", (e) => {
    if (!drag) return;
    w.style.left = (drag[2] + (e.clientX - drag[0]) / drag[4]) + "px";
    w.style.top = (drag[3] + (e.clientY - drag[1]) / drag[4]) + "px";
  });
  window.addEventListener("mouseup", () => { drag = null; });
  return { win: w, close };
}

// GtkFileDialog stand-in for Save as PDF.
const SaveDialog = {
  open(name, done) {
    const inner = el("div");
    inner.innerHTML = `<div style="margin-bottom:8px">Nombre</div><div class="fp-entry"><input value="${esc(name)}"></div>
      <div class="fp-hint" style="margin-top:8px">Carpeta: Documentos · Tipo: ${esc(_("PDF documents"))}</div>
      <div class="rowbtn"><button class="fp-btn accent">${esc(_("Save"))}</button><button class="fp-btn">${esc(_("Cancel"))}</button></div>`;
    const { win, close } = floatingWindow(_("Save as PDF"), inner, 480);
    const input = $("input", inner);
    input.focus(); input.select();
    const [ok, cancel] = inner.querySelectorAll(".fp-btn");
    const end = (v) => { win.remove(); done(v); };
    ok.onclick = () => end(input.value.trim() || name);
    cancel.onclick = close.onclick = () => end(null);
    input.addEventListener("keydown", (e) => { if (e.key === "Enter") ok.click(); if (e.key === "Escape") cancel.click(); });
  },
};

// dialog.py ManualDuplexWindow
class ManualDuplexWindow {
  constructor(title, choice, sides, onContinue, onCancel) {
    this.cb = [onContinue, onCancel];
    const box = el("div");
    box.style.cssText = "display:flex;flex-direction:column;gap:12px";
    const fronts = Math.floor((sides + 1) / 2);
    const head = el("div", "fp-title", esc(_("Print the other side")));
    box.appendChild(head);
    box.appendChild(el("div", "", esc(fmt(_("The front sides are printing ({n} sheets). When the printer has finished:"), { n: fronts }))));
    // Same turn for both edges: the short edge's backs are already printed upside down.
    const steps = [_("Take out all the printed sheets without changing their order."),
      _("Turn the stack over like the page of a book, so the printed side faces down."),
      _("Load them in the paper tray again the way the blank paper was loaded, the top of the pages going in first.")];
    if (sides % 2) steps.push(_("The last sheet has nothing on its back: leave it in the stack, the printer passes it through without printing."));
    steps.forEach((t, i) => box.appendChild(el("div", "", `${i + 1}.&nbsp; ${esc(t)}`)));
    const row = el("div", "rowbtn");
    const go = el("button", "fp-btn accent", esc(_("Continue")));
    const stop = el("button", "fp-btn", esc(_("Cancel")));
    row.append(go, stop);
    box.appendChild(row);
    const { win, close } = floatingWindow(_("Print the other side"), box, 480);
    this.win = win;
    go.onclick = () => this.done(0);
    stop.onclick = close.onclick = () => this.done(1);
    win.addEventListener("keydown", (e) => { if (e.key === "Enter") this.done(0); if (e.key === "Escape") this.done(1); });
    go.focus();
  }
  done(which) {
    const cb = this.cb; this.cb = null;
    if (!cb) return;
    this.win.remove();
    cb[which]();
  }
}

// ------------------------------------------------------------------ GtkPrintSettings (printing.choice_to_gtk)
function choiceToGtk(c) {
  const s = {};
  s.printer = c.printer;
  s["n-copies"] = String(c.copies);
  s.collate = c.collate ? "true" : "false";
  s.orientation = c.orientation;
  s["use-color"] = c.color ? "true" : "false";
  s["page-set"] = "all";
  if (c.pages === "ranges") {
    s["print-pages"] = "ranges";
    try {
      s["page-ranges"] = parseRanges(c.ranges_text).map(([a, b]) => (a === b ? `${a}` : `${a}-${b}`)).join(",");
    } catch (e) { s["print-pages"] = "all"; }
  } else if (c.pages === "current" || c.pages === "selection") {
    s["print-pages"] = c.pages;
  } else {
    s["print-pages"] = "all";
    if (c.pages === "odd" || c.pages === "even") s["page-set"] = c.pages;
  }
  s["paper-format"] = c.paper;
  const [pw, ph] = PAPER_MM[c.paper] || PAPER_MM.iso_a4;
  s["paper-width"] = pw.toFixed(2); s["paper-height"] = ph.toFixed(2);
  s["number-up"] = String(c.number_up);
  s.duplex = { long: "horizontal", short: "vertical", "manual-long": "horizontal", "manual-short": "vertical" }[c.duplex] || "simplex";
  if (c.is_pdf) { s["output-file-format"] = "pdf"; if (c.output_uri) s["output-uri"] = c.output_uri; }
  const [top, bottom, left, right] = c.margins_mm();
  const setup = { PaperSize: c.paper, Orientation: c.orientation, MarginTop: top, MarginBottom: bottom, MarginLeft: left, MarginRight: right };
  return [s, setup];
}

// printing.job_settings(): the CUPS options of the job ('cups-<name>' keys go to CUPS as <name>).
function jobSettings(c, appAlreadyApplied, side) {
  const [s] = choiceToGtk(c);
  s["cups-print-color-mode"] = c.color ? "color" : "monochrome";
  s["cups-sides"] = { long: "two-sided-long-edge", short: "two-sided-short-edge" }[c.duplex] || "one-sided";
  if (c.number_up > 1) s["cups-number-up"] = String(c.number_up);
  if (c.copies > 1) { s["cups-copies"] = String(c.copies); s["cups-collate"] = c.collate ? "true" : "false"; }
  if (appAlreadyApplied) {
    s["print-pages"] = "all"; delete s["page-ranges"]; s["page-set"] = "all"; s.reverse = "false"; s.scale = "100";
  } else if (c.pages === "ranges") {
    try {
      s["cups-page-ranges"] = parseRanges(c.ranges_text).map(([a, b]) => (a === b ? `${a + 1}` : `${a + 1}-${b + 1}`)).join(",");
    } catch (e) { /* invalid: no ranges */ }
  }
  for (const [kw, v] of Object.entries(c.driver)) if (kw !== "ColorModel" && v) s["cups-" + kw] = v;
  for (const o of Sim.driverOptions(c.printer)) {
    if (o.keyword === "ColorModel" && o.choices[0][0]) s["cups-ColorModel"] = c.color ? o.choices[1][0] : o.choices[0][0];
  }
  if (side) {
    s["page-set"] = side === "front" ? "odd" : "even";
    s["cups-page-set"] = side === "front" ? "odd" : "even";
    s["cups-sides"] = "one-sided";
    s["cups-page-delivery"] = "same-order";
    s["cups-outputorder"] = "normal";
    s["cups-OutputOrder"] = "Normal";
    if (side === "back" && c.duplex === "manual-short") s["cups-orientation-requested"] = c.orientation === "landscape" ? "5" : "6";
  }
  return s;
}

// What GTK's CUPS backend makes of those settings: the job's IPP/PPD options as CUPS receives them.
function cupsOptions(s, c) {
  const o = {};
  for (const [k, v] of Object.entries(s)) if (k.startsWith("cups-")) o[k.slice(5)] = v;
  if (!o["page-set"] && s["page-set"] && s["page-set"] !== "all") o["page-set"] = s["page-set"];
  if (!o["page-ranges"] && s["print-pages"] === "ranges" && s["page-ranges"]) {
    o["page-ranges"] = s["page-ranges"].split(",").map((r) => r.split("-").map((x) => +x + 1).join("-")).join(",");
  }
  o.PageSize = { iso_a4: "A4", na_letter: "Letter", na_legal: "Legal", iso_a3: "A3", iso_a5: "A5", iso_b5: "B5", na_executive: "Executive" }[c.paper] || c.paper;
  if (c.orientation === "landscape" && !o["orientation-requested"]) o["orientation-requested"] = "4";
  if (!o.copies) o.copies = "1";
  return o;
}
