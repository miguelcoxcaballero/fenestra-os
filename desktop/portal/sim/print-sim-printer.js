// SPDX-License-Identifier: GPL-3.0-or-later
// The simulated printers and everything around them: CUPS (queues, jobs, the pdftopdf filter's
// page selection, number-up, copies and output order), the paper path (trays, sheets with two faces,
// face-up / face-down delivery, a duplexer or not), ink, faults and the person handling the paper.
"use strict";

// ------------------------------------------------------------------ physical sheets
// A sheet has two faces, A and B, and four edges: N and S (short), E and W (long), named as seen
// on face A with N at the top. A pose says which face is up and which short edge is at the top,
// i.e. which edge enters the printer first when the sheet is loaded as held.
const ORDER = { A: ["N", "E", "S", "W"], B: ["N", "W", "S", "E"] };
const other = (f) => (f === "A" ? "B" : "A");
const opposite = (e) => ({ N: "S", S: "N", E: "W", W: "E" }[e]);
const edgeAt = (face, top, steps) => ORDER[face][(ORDER[face].indexOf(top) + steps) % 4];
const stepsBetween = (face, from, to) => (ORDER[face].indexOf(to) - ORDER[face].indexOf(from) + 4) % 4;

const PAPER_TYPES = {
  plain: { label: "Papel normal (80 g/m²)", tint: "#ffffff", cls: "plain", thick: 1 },
  photo: { label: "Papel fotográfico satinado", tint: "#fbfcff", cls: "photo", thick: 2.5 },
  matte: { label: "Papel fotográfico mate", tint: "#fbfaf6", cls: "matte", thick: 2.2 },
  card: { label: "Cartulina (250 g/m²)", tint: "#f7f3ea", cls: "card", thick: 3.5 },
  envelope: { label: "Sobre", tint: "#f5efe0", cls: "card", thick: 3 },
};
const MEDIA_CLASS = {
  Plain: "plain", PlainFast: "plain", Inkjet: "plain", Other: "plain", Transparency: "film", BackFilm: "film", GlossyFilm: "photo",
  Postcard: "card", Envelope: "card", Matte: "matte", MatteHeavy: "matte", Ilford: "matte", Coated: "photo", Photo: "photo",
  GlossyPhoto: "photo", Semigloss: "photo", Luster: "photo", GlossyPaper: "photo", ColorLife: "photo",
  Stationery: "plain", Cardstock: "card", Labels: "plain",
};

let sheetSeq = 0;
function newSheet(size, type) {
  return { id: ++sheetSeq, size, type, faces: { A: [], B: [] }, pose: { up: "A", top: "N" } };
}
const sheetMm = (s) => PAPER_MM[s.size] || PAPER_MM.iso_a4;

// book flip: around the vertical axis; notepad flip: around the horizontal axis
const Pose = {
  book: (p) => ({ up: other(p.up), top: p.top }),
  notepad: (p) => ({ up: other(p.up), top: opposite(p.top) }),
  rotate: (p) => ({ up: p.up, top: opposite(p.top) }),
};

// Draws what face `face` of the sheet looks like with edge `viewTop` at the top. px per mm: k.
function faceCanvas(sheet, face, viewTop, k) {
  const [w, h] = sheetMm(sheet);
  const side = viewTop === "N" || viewTop === "S";
  const cw = Math.round((side ? w : h) * k), ch = Math.round((side ? h : w) * k);
  const c = document.createElement("canvas");
  c.width = cw; c.height = ch;
  const x = c.getContext("2d");
  const t = PAPER_TYPES[sheet.type] || PAPER_TYPES.plain;
  x.fillStyle = t.tint; x.fillRect(0, 0, cw, ch);
  for (const L of sheet.faces[face]) {
    const a = stepsBetween(face, viewTop, L.lead);
    x.save();
    x.globalCompositeOperation = "multiply";
    x.translate(cw / 2, ch / 2);
    x.rotate(a * Math.PI / 2);
    const lw = (a % 2 ? ch : cw), lh = (a % 2 ? cw : ch);
    x.drawImage(L.canvas, -lw / 2, -lh / 2, lw, lh);
    x.restore();
  }
  if (t.cls === "photo") {
    const g = x.createLinearGradient(0, 0, cw, ch);
    g.addColorStop(0, "rgba(255,255,255,0.18)"); g.addColorStop(0.45, "rgba(255,255,255,0)"); g.addColorStop(1, "rgba(255,255,255,0.08)");
    x.fillStyle = g; x.fillRect(0, 0, cw, ch);
  }
  if (sheet.crumpled) {
    x.strokeStyle = "rgba(0,0,0,.25)"; x.lineWidth = 1.5;
    for (let i = 0; i < 14; i++) { x.beginPath(); x.moveTo(Math.random() * cw, Math.random() * ch); x.lineTo(Math.random() * cw, Math.random() * ch); x.stroke(); }
  }
  return c;
}

// ------------------------------------------------------------------ the simulator
const Sim = {
  speed: 5,
  // libcupsfilters' pdftopdf: page-ranges counts the file's pages; page-set ("designed for manual
  // duplex") is taken here to count the sides after number-up. "input" counts the file's pages instead.
  pageSetMode: "output",
  evenBlank: true,            // libcupsfilters >= 2.1.1: page-set=even adds a blank side when the total is odd
  jamChance: 0,
  jamNext: false,
  printers: {},               // name -> printer state
  installed: ["ET-2710-Series"],
  defaultPrinter: "",         // `lpstat -d`: no system default, as on this laptop
  view: "ET-2710-Series",     // printer shown on the right
  jobs: [],
  jobSeq: 100,
  groups: {},
  hands: null,                // {sheets: [...]} held by the user, top first
  table: [],                  // stacks put down: {id, name, sheets}
  files: [],                  // Save as PDF results
  logLines: [],
  lastResult: null,
  watchers: new Set(),

  init() {
    for (const name of Object.keys(PRINTERS)) this.printers[name] = this.makePrinter(name);
    this.ui();
    this.renderAll();
  },
  makePrinter(name) {
    const def = PRINTERS[name];
    const p = {
      name, def, power: true, connected: true, paused: false, accepting: true,
      tray: [], out: [], jammed: null, wait: null, busy: false, activity: "", progress: 0,
      ink: {}, inkUsed: {}, sheetsPrinted: 0,
    };
    const start = { C: 0.62, M: 0.48, Y: 0.71, K: 0.35 };
    for (const t of Object.keys(def.tanks)) { p.ink[t] = def.tanks[t] * (def.kind === "laser" ? 0.8 : start[t]); p.inkUsed[t] = 0; }
    for (let i = 0; i < (def.kind === "laser" ? 120 : 30); i++) p.tray.push(newSheet("iso_a4", "plain"));
    return p;
  },

  // ---------------------------------------------------------------- what the dialog asks
  watchPrinters(onAdded, onDone) {
    const w = { onAdded, onDone, stopped: false, timers: [] };
    this.watchers.add(w);
    // GTK's CUPS backend reports printers from the main loop a moment after the dialog opens.
    this.installed.forEach((name, i) => {
      w.timers.push(setTimeout(() => { if (!w.stopped) onAdded(this.info(name)); }, 220 + 90 * i));
    });
    w.timers.push(setTimeout(() => { if (!w.stopped && onDone) onDone(); }, 220 + 90 * this.installed.length + 800));
    w.stop = () => { w.stopped = true; w.timers.forEach(clearTimeout); this.watchers.delete(w); };
    return w;
  },
  info(name) {
    const d = PRINTERS[name];
    return { name, label: d.label, location: d.location, is_default: name === this.defaultPrinter, is_pdf: false };
  },
  autoDuplex(name) {
    if (!name || name === PDF_PRINTER) return true;
    return PRINTERS[name] ? PRINTERS[name].duplexer : true;
  },
  driverOptions(name) {
    if (!name || name === PDF_PRINTER || !PRINTERS[name]) return [];
    return PRINTERS[name].options;
  },
  cupsState(name) {
    const p = this.printers[name];
    if (!p) return { state: "", problem: false };
    if (p.paused) return { state: _("Paused"), problem: true };
    if (!p.accepting) return { state: _("Not accepting jobs"), problem: true };
    if (!p.power || !p.connected) return { state: "Esperando a que la impresora esté disponible.", problem: true };
    if (p.wait === "paper") return { state: "Sin papel.", problem: true };
    if (p.wait === "jam") return { state: "Atasco de papel.", problem: true };
    if (p.wait === "ink") return { state: "Hay que rellenar la tinta.", problem: true };
    return { state: "", problem: false };
  },
  dialogChanged() { this.renderTech(); },
  stateChanged() {
    if (Dialog.current) Dialog.current.updateStatus();
    this.renderAll();
  },

  // ---------------------------------------------------------------- "Add a printer"
  addPrinterDialog() {
    const missing = Object.keys(PRINTERS).filter((n) => !this.installed.includes(n));
    const box = el("div", "modal-box");
    box.innerHTML = `<div class="modal-head"><strong>Agregar una impresora (simulada)</strong><button class="simbtn small">Cerrar</button></div>
      <p class="help">En Fenestra este enlace abre la configuración de impresoras del sistema. Aquí añade una cola CUPS al simulador; el diálogo abierto la recibe como un printer-added de GTK.</p>`;
    if (!missing.length) box.appendChild(el("p", "", "Ya están todas instaladas."));
    for (const n of missing) {
      const b = el("button", "simbtn", `Instalar ${esc(n)} — ${esc(PRINTERS[n].model)}`);
      b.onclick = () => { this.install(n); closeModal(); };
      box.appendChild(b);
    }
    openModal(box);
    $(".simbtn", box).onclick = closeModal;
  },
  install(name) {
    if (this.installed.includes(name)) return;
    this.installed.push(name);
    this.log(`lpadmin: cola ${name} creada`);
    for (const w of this.watchers) w.onAdded(this.info(name));
    this.stateChanged();
  },
  uninstall(name) {
    this.installed = this.installed.filter((n) => n !== name);
    if (Dialog.current) Dialog.current.printerRemoved(name);
    this.log(`lpadmin: cola ${name} eliminada`);
    this.stateChanged();
  },

  // ---------------------------------------------------------------- the app and its print request
  docKey: "text",
  appDoc: null,          // what the app prints
  previewDoc: null,      // what the dialog previews (null: PreparePrint, no preview)
  async setDoc(key, file) {
    if (key === "pdf") {
      try { this.appDoc = await Docs.pdf(file); } catch (e) { alert(e.message); return; }
      this.previewDoc = this.appDoc;
    } else if (key === "none") {
      this.appDoc = Docs.sample("text", 3); this.appDoc.title = "Carta.odt";
      this.previewDoc = null;
    } else {
      this.appDoc = Docs.sample(key); this.previewDoc = this.appDoc;
    }
    this.docKey = key;
    this.renderApp();
  },
  renderApp() {
    $("#app-title").textContent = this.appDoc.title + (this.previewDoc ? "" : " — app que imprime con PreparePrint");
    const body = $("#app-body");
    body.innerHTML = "";
    const d = this.appDoc;
    for (let i = 0; i < d.n; i++) {
      const [pw, ph] = d.pageSize(i);
      const s = 150 / Math.max(pw, ph);
      const c = el("canvas");
      c.width = Math.round(pw * s * 2); c.height = Math.round(ph * s * 2);
      c.style.width = Math.round(pw * s) + "px"; c.style.height = Math.round(ph * s) + "px";
      const x = c.getContext("2d"); x.fillStyle = "#fff"; x.fillRect(0, 0, c.width, c.height);
      d.drawPage(x, i, c.width, c.height);
      body.appendChild(c);
    }
  },
  openDialog() {
    if (Dialog.current) return;
    const doc = this.previewDoc;
    // What the app asks for (GtkPrintSettings/GtkPageSetup it sends): no printer, its own orientation.
    const choice = new Choice({ printer: "", orientation: this.appDoc.orientation, paper: "iso_a4" });
    const opts = { title: this.appDoc.title, has_current: !!doc, has_selection: false, accept_label: "", no_save_dialog: false };
    const dlg = new Dialog(this.appDoc.title, choice, opts, (resp, c) => this.dialogDone(resp, c, opts), doc);
    dlg.mount($("#dlg-holder"));
    this.log(`${doc ? "Print()" : "PreparePrint()"}: el diálogo se abre para «${this.appDoc.title}»`);
  },
  dialogDone(response, c, opts) {
    const [settings, setup] = choiceToGtk(c);
    this.lastResult = { response, settings, setup, choice: c.clone() };
    if (response !== 0) { this.log("El diálogo se cerró sin imprimir (response 1)"); this.renderTech(); return; }
    this.log(`response 0 — impresora «${c.is_pdf ? "Guardar como PDF" : c.printer}»`);
    const doc = this.appDoc;
    const prepare = !this.previewDoc;
    // PreparePrint: the app renders the document after the dialog with the page selection applied.
    const file = prepare ? c.selected_pages(doc.n) : [...Array(doc.n).keys()];
    const group = { id: ++this.jobSeq * 10, title: doc.title, choice: c.clone(), doc, expected: sheetsFor(c, doc.n).filter((s) => s.length) };
    this.groups[group.id] = group;
    if (c.is_pdf) { this.savePdf(group, prepare); return; }
    if (!this.printers[c.printer] || !this.installed.includes(c.printer)) { this.log(`ERROR: la impresora ${c.printer} no existe`); return; }
    if (c.duplex.startsWith("manual-")) { this.manualDuplex(group, file, prepare); return; }
    this.submit(group, file, prepare, null);
  },
  savePdf(group, prepare) {
    const c = group.choice;
    // compose_pdf() for Print(); with PreparePrint the app makes the same pages itself.
    const sheets = sheetsFor(c, group.doc.n);
    const name = decodeURIComponent((c.output_uri || "").split("/").pop() || "document.pdf");
    this.files.unshift({ name, uri: c.output_uri, group, sheets, copies: prepare ? c.copies : 1 });
    this.log(`Guardar como PDF: ${c.output_uri} (${sheets.length} páginas)`);
    this.tab("table");
    this.renderAll();
  },

  // service.py _manual_duplex(): fronts, the window, then the backs from the service's own copy.
  manualDuplex(group, file, prepare) {
    const c = group.choice;
    const sides = prepare ? sheetsFor(new Choice({ number_up: c.number_up }), file.length).length
      : sheetsFor(c, group.doc.n).length;
    if (sides < 2) { this.submit(group, file, prepare, null); return; }
    const err = this.submit(group, file, prepare, "front");
    if (err) return;
    this.log(`manual two-sided: fronts queued on '${c.printer}' (${sides} sides)`);
    new ManualDuplexWindow(group.title, c, sides,
      () => { this.log("manual two-sided: printing the backs"); this.submit(group, file, prepare, "back"); },
      () => this.log("manual two-sided: backs cancelled"));
  },

  // ---------------------------------------------------------------- CUPS
  submit(group, file, prepare, side) {
    const c = group.choice;
    const p = this.printers[c.printer];
    if (!p.accepting) { this.log(`ERROR: ${c.printer} no acepta trabajos (cupsreject): el trabajo no se envía`); this.stateChanged(); return "rejected"; }
    const settings = jobSettings(c, prepare, side);
    const opts = cupsOptions(settings, c);
    const job = {
      id: ++this.jobSeq, group, title: group.title + (side ? (side === "front" ? " (delante)" : " (detrás)") : ""), printer: c.printer,
      settings, opts, file, prepare, side, state: "pending", plan: null, done: 0, created: new Date(),
    };
    job.plan = this.pdftopdf(job);
    this.jobs.push(job);
    this.log(`lp: trabajo ${c.printer}-${job.id} en cola — ${job.plan.sides.length} caras · ` +
      Object.entries(opts).map(([k, v]) => `${k}=${v}`).join(" "));
    this.renderTech();
    this.schedule();
    return null;
  },
  // pdftopdf: which pages of the file land on which side of paper, in which order.
  pdftopdf(job) {
    const o = job.opts, c = job.group.choice;
    let pages = job.file.map((orig, i) => ({ orig, no: i + 1 }));     // no: page number in the file CUPS got
    if (o["page-ranges"]) {
      const rs = parseRanges(o["page-ranges"].replace(/-$/, "-" + pages.length), pages.length);
      pages = pages.filter((p) => rs.some(([a, b]) => p.no - 1 >= a && p.no - 1 <= b));
    }
    const ps = o["page-set"];
    const inputTotal = pages.length;
    if (ps && this.pageSetMode === "input") pages = pages.filter((p) => (ps === "odd" ? p.no % 2 === 1 : p.no % 2 === 0));
    const nup = parseInt(o["number-up"] || "1", 10);
    let sides = [];
    for (let i = 0; i < pages.length; i += nup) sides.push(pages.slice(i, i + nup).map((p) => p.orig));
    if (ps === "even" && this.pageSetMode === "input" && inputTotal % 2 && this.evenBlank) sides.push([]);
    if (ps && this.pageSetMode === "output") {
      const total = sides.length;
      sides = sides.filter((_s, i) => (ps === "odd" ? i % 2 === 0 : i % 2 === 1));
      if (ps === "even" && total % 2 && this.evenBlank) sides.push([]);
    }
    const copies = parseInt(o.copies || "1", 10);
    const collate = o.collate !== "false";
    let all = [];
    if (copies > 1 && collate) for (let k = 0; k < copies; k++) all.push(...sides);
    else for (const s of sides) for (let k = 0; k < copies; k++) all.push(s);
    const def = PRINTERS[job.printer];
    const duplex = def.duplexer && /two-sided/.test(o.sides || "") ? o.sides : null;
    let units = duplex ? [] : all.map((s) => [s]);
    if (duplex) {
      // copies of a duplex job start on a new sheet
      const per = copies > 1 && collate ? sides.length : all.length;
      for (let k = 0; k < all.length; k += per) {
        const chunk = all.slice(k, k + per);
        for (let i = 0; i < chunk.length; i += 2) units.push(chunk.slice(i, i + 2));
      }
    }
    const order = (o.OutputOrder || (o.outputorder === "normal" ? "Normal" : o.outputorder === "reverse" ? "Reverse" : "") || def.defaultOutputOrder);
    if (order === "Reverse") units.reverse();
    const rot = o["orientation-requested"] === "5" || o["orientation-requested"] === "6";
    const landscape = c.orientation === "landscape";
    return { sides: all, units, duplex, rot, landscape, nup, order, color: o["print-color-mode"] !== "monochrome" };
  },
  cancelJob(job, why) {
    if (["completed", "canceled", "aborted"].includes(job.state)) return;
    const wasRunning = job.state === "processing";
    job.state = "canceled";
    job.cancelReason = why || "lprm";
    const p = this.printers[job.printer];
    if (wasRunning && p.onButton) p.onButton("cancel");
    this.log(`Trabajo ${job.printer}-${job.id} cancelado (${job.cancelReason})`);
    this.stateChanged();
  },

  // ---------------------------------------------------------------- the printer itself
  schedule() {
    for (const p of Object.values(this.printers)) if (!p.busy) this.run(p);
  },
  async run(p) {
    if (p.busy) return;
    p.busy = true;
    try {
      while (true) {
        const job = this.jobs.find((j) => j.printer === p.name && (j.state === "pending" || j.state === "processing"));
        if (!job) break;
        if (p.paused || !p.power || !p.connected) { p.activity = ""; this.stateChanged(); await this.until(() => !p.paused && p.power && p.connected); continue; }
        job.state = "processing";
        this.stateChanged();
        await this.printJob(p, job);
      }
    } finally {
      p.busy = false; p.activity = ""; p.progress = 0;
      this.stateChanged();
    }
  },
  until(cond) {
    return new Promise((ok) => {
      const t = setInterval(() => { if (cond()) { clearInterval(t); ok(); } }, 120);
    });
  },
  sleep(ms) { return new Promise((ok) => setTimeout(ok, ms)); },
  async printJob(p, job) {
    const plan = job.plan;
    if (job.done === 0) {
      p.activity = "Recibiendo datos…"; this.stateChanged();
      await this.sleep(this.ms(2));
    }
    while (job.done < plan.units.length) {
      if (job.state !== "processing") return;
      if (!p.power || !p.connected || p.paused) { await this.until(() => p.power && p.connected && !p.paused); continue; }
      const unit = plan.units[job.done];
      const ok = await this.printUnit(p, job, unit);
      if (ok === "cancel") { this.cancelJob(job, "botón de parar de la impresora"); return; }
      if (ok) job.done++;
      this.stateChanged();
    }
    job.state = "completed";
    job.finished = new Date();
    this.log(`Trabajo ${p.name}-${job.id} completado (${plan.units.length} hojas)`);
  },
  ms(seconds) { return this.speed === 0 ? 30 : Math.max(30, seconds * 1000 / this.speed); },
  quality(job) {
    const o = job.opts;
    return o.StpQuality || o.cupsPrintQuality || "Standard";
  },
  // One sheet: feed, print one side (or two with a duplexer), deliver. Returns true when done,
  // false to retry it (after a jam), "cancel" when the stop button cancelled the job.
  async printUnit(p, job, unit) {
    const def = p.def;
    // paper
    if (!p.tray.length) {
      p.wait = "paper"; p.activity = "Sin papel: carga papel y pulsa el botón ▷ de la impresora";
      this.log(`${p.name}: sin papel`);
      this.stateChanged();
      const r = await this.waitButton(p);
      if (r === "cancel") return "cancel";
      return false;
    }
    // ink
    const need = job.plan.color && def.color ? Object.keys(def.tanks) : ["K"];
    const empty = need.filter((t) => p.ink[t] <= 0);
    if (empty.length) {
      p.wait = "ink"; p.activity = `Tinta agotada (${empty.join(", ")}): rellena el depósito y pulsa ▷`;
      this.log(`${p.name}: tinta agotada ${empty.join(", ")}`);
      this.stateChanged();
      const r = await this.waitButton(p, () => need.every((t) => p.ink[t] > 0));
      if (r === "cancel") return "cancel";
      return false;
    }
    const sheet = p.tray.shift();
    p.feeding = sheet;
    p.activity = `Imprimiendo hoja ${job.done + 1} de ${job.plan.units.length}`;
    p.progress = 0;
    this.stateChanged();
    this.animate(p, "feed");
    await this.sleep(this.ms(1.2));
    // jam?
    const media = job.opts.MediaType || "Plain";
    const thickMismatch = (PAPER_TYPES[sheet.type] || {}).thick >= 3 && MEDIA_CLASS[media] === "plain";
    if (this.jamNext || Math.random() < this.jamChance / 100 + (thickMismatch ? 0.15 : 0)) {
      this.jamNext = false;
      sheet.crumpled = true;
      p.jammed = sheet; p.feeding = null;
      p.wait = "jam"; p.activity = "Atasco de papel: quita la hoja atascada y pulsa ▷";
      this.log(`${p.name}: ATASCO con la hoja ${sheet.id}${thickMismatch ? " (papel grueso con tipo de papel normal)" : ""}`);
      this.stateChanged();
      const r = await this.waitButton(p, () => !p.jammed);
      if (r === "cancel") return "cancel";
      return false;
    }
    const pose = sheet.pose;
    const per = this.ms(def.speed[this.quality(job)] || 8);
    for (let k = 0; k < unit.length; k++) {
      const face = k === 0 ? pose.up : other(pose.up);
      const lead = k === 0 ? pose.top : pose.top;
      // print, a little at a time, so the stop button can interrupt it
      const t0 = performance.now();
      this.animate(p, "print");
      while (performance.now() - t0 < per) {
        p.progress = (performance.now() - t0) / per;
        if (job.state !== "processing") { p.out.unshift(sheet); p.feeding = null; return "cancel"; }
        if (p.stopPressed) { p.stopPressed = false; p.out.unshift(sheet); p.feeding = null; this.log(`${p.name}: trabajo parado con el botón, la hoja sale a medias`); return "cancel"; }
        if (!p.power) { p.feeding = null; p.jammed = sheet; sheet.crumpled = true; this.log(`${p.name}: apagada mientras imprimía`); return false; }
        this.renderStage();
        await this.sleep(60);
      }
      if (!unit[k].length) { this.log(`${p.name}: cara en blanco (la hoja pasa sin imprimir)`); continue; }
      const L = this.layer(p, job, unit[k], sheet, face, lead, k === 1 ? unit : null);
      sheet.faces[face].push(L);
      if (sheet.faces[face].length > 1) this.log(`${p.name}: AVISO hoja ${sheet.id} impresa encima de algo ya impreso`);
    }
    // deliver
    p.feeding = null;
    if (unit.length === 2) {
      // the duplexer turns the sheet over before printing the back; it leaves with the back up
    }
    if (!def.faceUp) sheet.pose = Pose.notepad(sheet.pose);
    p.out.unshift(sheet);
    p.sheetsPrinted++;
    p.progress = 1;
    this.animate(p, "out");
    return true;
  },
  waitButton(p, extra) {
    return new Promise((ok) => {
      p.onButton = (what) => {
        if (what === "cancel") { p.onButton = null; p.wait = null; ok("cancel"); return; }
        if (extra && !extra()) { this.log(`${p.name}: el botón no hace nada todavía`); return; }
        if (p.wait === "paper" && !p.tray.length) { this.log(`${p.name}: sigue sin papel`); return; }
        p.onButton = null; p.wait = null; ok("go");
      };
    });
  },
  pressButton(p, long) {
    if (!p.power) return;
    if (long || !p.onButton) {
      // stop: cancels the job being printed
      const job = this.jobs.find((j) => j.printer === p.name && j.state === "processing");
      if (p.onButton) { p.onButton("cancel"); return; }
      if (job) { p.stopPressed = true; return; }
      this.log(`${p.name}: botón pulsado (nada que hacer)`);
      return;
    }
    p.onButton("go");
    this.stateChanged();
  },

  // A printed side: the job's sheet drawn as the printer sees the paper (lead edge at the top).
  layer(p, job, pages, sheet, face, lead, duplexPair) {
    const k = 2.2;            // px per mm
    const [sw, sh] = sheetMm(sheet);
    const c = document.createElement("canvas");
    c.width = Math.round(sw * k); c.height = Math.round(sh * k);
    const x = c.getContext("2d");
    const ch = job.group.choice;
    const jobPaper = PAPER_MM[ch.paper] || PAPER_MM.iso_a4;
    const plan = job.plan;
    const o = job.opts;
    const borderless = o.StpFullBleed === "True";
    const hw = borderless ? 0 : (p.def.kind === "laser" ? 4 : 3);
    // content as it should look (upright), job paper size
    const land = plan.landscape;
    const cw = (land ? jobPaper[1] : jobPaper[0]) * k, chh = (land ? jobPaper[0] : jobPaper[1]) * k;
    const content = document.createElement("canvas");
    content.width = Math.round(cw); content.height = Math.round(chh);
    const cx = content.getContext("2d");
    const color = plan.color && p.def.color && (o.ColorModel ? o.ColorModel !== "Gray" : true);
    const choice = new Choice({ orientation: land ? "landscape" : "portrait", paper: ch.paper, number_up: plan.nup, color, margins: ch.margins });
    drawSheet(cx, choice, content.width, content.height, pages, job.group.doc, M.PREVIEW_LIGHT, true);
    // the driver's adjustments and the paper
    const lvl = (kw) => (o[kw] && o[kw] !== "None" ? parseInt(o[kw], 10) / 1000 : 1);
    const filters = [];
    filters.push(`saturate(${lvl("StpSaturation")})`, `brightness(${lvl("StpBrightness")})`, `contrast(${lvl("StpContrast") * (0.85 + 0.15 * lvl("StpDensity"))})`);
    const q = this.quality(job);
    const qOpacity = { Economy: 0.5, Draft: 0.68 }[q] || 1;
    const loaded = (PAPER_TYPES[sheet.type] || PAPER_TYPES.plain).cls;
    const media = MEDIA_CLASS[o.MediaType || "Plain"] || "plain";
    let note = "";
    if (media === "photo" && loaded === "plain") { filters.push("blur(0.7px)", "saturate(1.15)"); note = "tinta corrida (tipo fotográfico en papel normal)"; }
    else if (media === "plain" && (loaded === "photo")) { filters.push("saturate(0.8)", "brightness(1.06)"); note = "colores apagados y tinta sin secar (tipo normal en papel fotográfico)"; }
    if (o.StpColorCorrection === "Bright") filters.push("saturate(1.25)");
    if (o.StpColorCorrection === "Desaturated") filters.push("saturate(0.4)");
    if (o.StpColorCorrection === "Threshold") filters.push("grayscale(1)", "contrast(8)");
    if (!color) filters.push("grayscale(1)");
    // place: rotated onto the sheet as the printer images it
    x.save();
    x.beginPath(); x.rect(hw * k, hw * k, c.width - 2 * hw * k, c.height - 2 * hw * k); x.clip();
    x.globalAlpha = qOpacity;
    x.filter = filters.join(" ");
    const jw = jobPaper[0] * k, jh = jobPaper[1] * k;   // the job's page, portrait, from the lead edge, left aligned
    x.translate(jw / 2, jh / 2);
    let angle = land ? -Math.PI / 2 : 0;          // IPP landscape: content turned 90° counter-clockwise
    if (plan.rot) angle += Math.PI;
    if (duplexPair && p.def.duplexer) angle += this.duplexBackTurn(job, land);
    x.rotate(angle);
    x.drawImage(content, -content.width / 2, -content.height / 2);
    x.restore();
    if (q === "Economy" || q === "Draft") {
      x.fillStyle = "rgba(255,255,255,0.35)";
      for (let y = 0; y < c.height; y += 6) x.fillRect(0, y, c.width, 1.2);
    }
    // inks: what the tanks have left at this moment, and what it takes
    this.inkEffects(p, x, c, color);
    // where the content's top points on this face (for the two-sided checks)
    const turns = ((Math.round(angle / (Math.PI / 2)) % 4) + 4) % 4;   // clockwise quarter turns from lead
    const topEdge = edgeAt(face, lead, turns);
    if (jobPaper[0] > sheetMm(sheet)[0] + 1 || jobPaper[1] > sheetMm(sheet)[1] + 1) note += (note ? "; " : "") + "papel del trabajo más grande que el cargado: se corta";
    if (note) this.log(`${p.name}: hoja ${sheet.id}: ${note}`);
    return { canvas: c, lead, topEdge, pages, job: job.id, group: job.group.id, side: job.side, note };
  },
  // A duplexer turns the sheet itself: what the back needs so that it reads as asked.
  duplexBackTurn(job, land) {
    // The back is imaged with the same lead edge as seen from its own face, which is a book flip:
    // right for the long edge in portrait and landscape alike; the short edge needs half a turn.
    return job.opts.sides === "two-sided-short-edge" ? Math.PI : 0;
  },
  inkEffects(p, x, c, color) {
    const W = c.width, H = c.height;
    const img = x.getImageData(0, 0, W, H);
    const d = img.data;
    const use = { C: 0, M: 0, Y: 0, K: 0 };
    const has = (t) => p.ink[t] === undefined ? false : p.ink[t] > 0;
    const low = Object.fromEntries(Object.keys(p.ink).map((t) => [t, p.ink[t] / p.def.tanks[t] < 0.03]));
    for (let i = 0; i < d.length; i += 4) {
      const a = d[i + 3] / 255;          // unprinted paper is transparent here
      if (a === 0) continue;
      let cc = 1 - d[i] / 255, mm = 1 - d[i + 1] / 255, yy = 1 - d[i + 2] / 255;
      const kk = Math.min(cc, mm, yy);
      if (cc + mm + yy < 0.01) continue;
      if (!color) { use.K += kk * a; continue; }
      let c2 = cc - kk, m2 = mm - kk, y2 = yy - kk, k2 = kk;
      use.C += c2 * a; use.M += m2 * a; use.Y += y2 * a; use.K += k2 * a;
      if (!has("C") || low.C) c2 *= low.C && has("C") ? 0.5 : 0;
      if (!has("M") || low.M) m2 *= low.M && has("M") ? 0.5 : 0;
      if (!has("Y") || low.Y) y2 *= low.Y && has("Y") ? 0.5 : 0;
      if (!has("K") || low.K) k2 *= low.K && has("K") ? 0.5 : 0.15;
      cc = Math.min(1, c2 + k2); mm = Math.min(1, m2 + k2); yy = Math.min(1, y2 + k2);
      d[i] = 255 * (1 - cc); d[i + 1] = 255 * (1 - mm); d[i + 2] = 255 * (1 - yy);
    }
    x.putImageData(img, 0, 0);
    // ml per fully covered A4 side ≈ 0.9 ml per colour; scale by the coverage measured
    const full = W * H;
    for (const t of Object.keys(use)) {
      if (p.ink[t] === undefined) continue;
      const ml = use[t] / full * 0.9 * (p.def.kind === "laser" ? 0.4 : 1);
      p.ink[t] = Math.max(0, p.ink[t] - ml);
      p.inkUsed[t] += ml;
    }
  },

  // ---------------------------------------------------------------- the person handling paper
  takeOutput(p) {
    if (!p.out.length) return;
    this.toHands(p.out.splice(0), `bandeja de salida de ${p.name}`);
  },
  takeInput(p) {
    if (!p.tray.length) return;
    this.toHands(p.tray.splice(0), `bandeja de entrada de ${p.name}`);
  },
  toHands(sheets, from) {
    if (!this.hands) this.hands = { sheets: [] };
    // what you pick up goes on top of what you already hold
    this.hands.sheets = sheets.concat(this.hands.sheets);
    this.log(`Coges ${sheets.length} hojas de la ${from}`);
    this.stateChanged();
  },
  handsDo(op) {
    const h = this.hands;
    if (!h) return;
    const s = h.sheets;
    if (op === "book" || op === "notepad") {
      s.reverse();
      for (const sh of s) sh.pose = Pose[op](sh.pose);
      this.log(op === "book" ? "Das la vuelta al montón como la página de un libro (borde largo)" : "Das la vuelta al montón como un bloc de notas (borde corto)");
    } else if (op === "rotate") {
      for (const sh of s) sh.pose = Pose.rotate(sh.pose);
      this.log("Giras el montón 180° sin darle la vuelta");
    } else if (op === "top-aside" || op === "bottom-aside") {
      const sh = op === "top-aside" ? s.shift() : s.pop();
      if (sh) { this.table.unshift({ id: ++this.jobSeq, name: "Hoja apartada", sheets: [sh] }); this.log(`Apartas la hoja ${op === "top-aside" ? "de arriba" : "de abajo"}`); }
    }
    if (!s.length) this.hands = null;
    this.stateChanged();
  },
  handsLoad(p, where) {
    const h = this.hands;
    if (!h) return;
    const odd = h.sheets.filter((s) => !PAPER_MM[s.size]);
    if (odd.length) return;
    if (where === "replace") {
      const blank = p.tray.splice(0);
      if (blank.length) this.table.unshift({ id: ++this.jobSeq, name: "Papel que había en la bandeja", sheets: blank });
      p.tray = h.sheets;
    } else if (where === "front") {
      p.tray = h.sheets.concat(p.tray);
    } else {
      p.tray = p.tray.concat(h.sheets);
    }
    this.log(`Cargas ${h.sheets.length} hojas en la bandeja de ${p.name} (${{ replace: "quitando el papel que había", front: "delante del papel que había", back: "detrás del papel que había" }[where]})`);
    this.hands = null;
    this.stateChanged();
  },
  handsPutDown(name) {
    const h = this.hands;
    if (!h) return;
    this.table.unshift({ id: ++this.jobSeq, name: name || `Montón de ${h.sheets.length} hojas`, sheets: h.sheets });
    this.hands = null;
    this.log("Dejas el montón en la mesa");
    this.tab("table");
    this.stateChanged();
  },
  addPaper(p, size, type, n) {
    const room = p.def.capacity - p.tray.length;
    const k = Math.max(0, Math.min(n, room));
    for (let i = 0; i < k; i++) p.tray.push(newSheet(size, type));
    this.log(`Añades ${k} hojas de ${PAPER_TYPES[type].label}, ${_(PAPER_LABELS[size] || size)}${k < n ? ` (no caben más de ${p.def.capacity})` : ""}`);
    this.stateChanged();
  },
  clearJam(p) {
    if (!p.jammed) return;
    this.table.unshift({ id: ++this.jobSeq, name: "Hoja atascada (arrugada)", sheets: [p.jammed] });
    p.jammed = null;
    this.log(`${p.name}: quitas la hoja atascada`);
    this.stateChanged();
  },

  // ---------------------------------------------------------------- reading a stack
  // Reads the stack as someone reading the document: top sheet first, the face up is its front.
  // Returns the verdict for two-sided documents (pairing of the pages and the backs' direction).
  check(sheets, bindingOverride) {
    const layersOf = (sh, f) => sh.faces[f];
    const groups = {};
    for (const sh of sheets) for (const f of ["A", "B"]) for (const L of sh.faces[f]) groups[L.group] = (groups[L.group] || 0) + 1;
    const gid = Object.keys(groups).sort((a, b) => groups[b] - groups[a])[0];
    const g = this.groups[gid];
    if (!g) return { ok: false, title: "Hojas en blanco", issues: [] };
    const c = g.choice;
    const twoSided = c.duplex !== "simplex";
    const binding = bindingOverride || (c.duplex.endsWith("short") ? "short" : "long");
    const expected = g.expected;
    const pagesTxt = (ps) => (ps && ps.length ? ps.map((i) => i + 1).join("+") : "—");
    const read = (stack) => {
      const issues = [], rows = [];
      let ok = true, k = 0;
      stack.forEach((sh, i) => {
        const front = layersOf(sh, sh.pose.up), back = layersOf(sh, other(sh.pose.up));
        const exF = expected[k], exB = twoSided ? expected[k + 1] : undefined;
        k += twoSided ? 2 : 1;
        const fp = front[0] ? front[0].pages : null, bp = back[0] ? back[0].pages : null;
        let line = `Hoja ${i + 1}: delante ${pagesTxt(fp)}${twoSided || bp ? `, detrás ${pagesTxt(bp)}` : ""}`;
        const bad = [];
        if (front.length > 1 || back.length > 1) bad.push("impresa dos veces en la misma cara");
        if (String(fp) !== String(exF)) bad.push(`delante debería ir ${pagesTxt(exF)}`);
        if (twoSided && String(bp) !== String(exB || null) && !(exB === undefined && !bp)) bad.push(`detrás debería ir ${pagesTxt(exB)}`);
        if (!twoSided && bp) bad.push("tiene algo impreso detrás");
        if (front[0] && back[0]) {
          const U = front[0].topEdge;
          const portraitView = U === "N" || U === "S";
          const keep = (binding === "long") === portraitView;
          const want = keep ? U : opposite(U);
          const turned = back[0].topEdge === want;
          if (!turned) bad.push(`la cara de detrás sale al revés al voltear por el borde ${binding === "long" ? "largo" : "corto"}`);
        }
        if (bad.length) { ok = false; line += " ✗ " + bad.join("; "); } else line += " ✓";
        rows.push(line);
      });
      if (k < expected.length) { ok = false; issues.push(`Faltan ${expected.length - k} caras del documento`); }
      return { ok, rows, issues };
    };
    const asIs = read(sheets);
    const bad = (r) => r.rows.filter((x) => x.includes("✗")).length + r.issues.length;
    if (!asIs.ok) {
      // People turn a finished stack over before reading it: judge it the way round that reads better.
      const f = sheets.slice().reverse().map((sh) => Object.assign({}, sh, { pose: Pose.book(sh.pose) }));
      const r = read(f);
      if (bad(r) < bad(asIs)) {
        return { ok: r.ok, group: g, twoSided, binding, rows: r.rows, issues: r.issues,
          hint: "El montón estaba boca abajo: se ha leído dándole la vuelta como a un libro (lo normal al recogerlo)." };
      }
    }
    return { ok: asIs.ok, group: g, twoSided, binding, rows: asIs.rows, issues: asIs.issues, hint: "" };
  },

  // Everything back to a fresh start: queues emptied, trays with plain A4, hands and table empty.
  reset() {
    for (const j of this.jobs) if (j.state === "pending" || j.state === "processing") this.cancelJob(j, "reinicio");
    for (const p of Object.values(this.printers)) {
      if (p.onButton) p.onButton("cancel");
      p.stopPressed = false; p.jammed = null; p.feeding = null; p.wait = null;
      p.out = []; p.tray = [];
      for (let i = 0; i < (p.def.kind === "laser" ? 120 : 30); i++) p.tray.push(newSheet("iso_a4", "plain"));
    }
    document.querySelectorAll("#overlay .fp-small").forEach((w) => w.remove());
    this.jobs = []; this.table = []; this.files = []; this.hands = null;
    this.log("Simulación reiniciada");
    this.stateChanged();
  },

  // ---------------------------------------------------------------- log
  log(text) {
    const t = new Date();
    this.logLines.unshift(`${t.toLocaleTimeString("es-ES")}.${String(t.getMilliseconds()).padStart(3, "0")}  ${text}`);
    this.logLines.length = Math.min(this.logLines.length, 500);
    this.renderLog();
  },
};

// ------------------------------------------------------------------ modal helpers
function openModal(node) { const m = $("#modal"); m.innerHTML = ""; m.appendChild(node); m.hidden = false; }
function closeModal() { const m = $("#modal"); m.hidden = true; m.innerHTML = ""; }
$("#modal").addEventListener("mousedown", (e) => { if (e.target.id === "modal") closeModal(); });

// ------------------------------------------------------------------ rendering the printer side
Object.assign(Sim, {
  ui() {
    // simbar
    const acc = $("#sim-accent");
    for (const a of Object.keys(M.ACCENTS)) acc.appendChild(new Option({ blue: "Azul", teal: "Verde azulado", green: "Verde", yellow: "Amarillo", orange: "Naranja", red: "Rojo", pink: "Rosa", purple: "Morado", slate: "Pizarra" }[a], a));
    acc.onchange = () => { Theme.accent = acc.value; Theme.apply(); };
    $("#sim-theme").onchange = (e) => { Theme.dark = e.target.value === "dark"; Theme.apply(); };
    $("#sim-lang").onchange = (e) => { LANG = e.target.value; if (Dialog.current) { Dialog.current.finish(1); this.openDialog(); } };
    $("#sim-doc").onchange = (e) => {
      if (e.target.value === "pdf") { $("#sim-pdf").click(); return; }
      this.setDoc(e.target.value);
    };
    $("#sim-pdf").onchange = (e) => { if (e.target.files[0]) this.setDoc("pdf", e.target.files[0]); };
    $("#sim-open").onclick = () => this.openDialog();
    document.addEventListener("keydown", (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "p") { e.preventDefault(); this.openDialog(); }
    });
    const ps = $("#sim-printer");
    ps.onchange = () => { this.view = ps.value; this.renderAll(); };
    $("#tabs").addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) this.tab(b.dataset.tab); });
  },
  tab(name) {
    document.querySelectorAll("#tabs button").forEach((b) => b.classList.toggle("on", b.dataset.tab === name));
    document.querySelectorAll(".tabpane").forEach((p) => p.classList.toggle("on", p.id === "tab-" + name));
  },
  renderAll() {
    const ps = $("#sim-printer");
    ps.innerHTML = "";
    for (const n of Object.keys(PRINTERS)) ps.appendChild(new Option(n + (this.installed.includes(n) ? "" : " (no instalada)"), n, false, n === this.view));
    const p = this.printers[this.view];
    $("#ph-name").textContent = p.name;
    $("#ph-model").textContent = p.def.model;
    this.renderStage(); this.renderState(); this.renderHands();
    this.renderOut(); this.renderIn(); this.renderQueue(); this.renderInk(); this.renderFaults(); this.renderTable(); this.renderTech();
    const busy = this.jobs.filter((j) => j.state === "pending" || j.state === "processing").length;
    const qb = $('#tabs button[data-tab="queue"]');
    qb.innerHTML = "Cola (CUPS)" + (busy ? `<span class="badge">${busy}</span>` : "");
    const ob = $('#tabs button[data-tab="out"]');
    const outN = p.out.length;
    ob.innerHTML = "Bandeja de salida" + (outN ? `<span class="badge" style="background:var(--sim-accent)">${outN}</span>` : "");
  },
  animate(p, what) { p.anim = what; p.animAt = performance.now(); this.renderStage(); },

  // A generic ink tank printer (rear feed, front output, four tanks) or a laser (cassette, top output).
  renderStage() {
    const p = this.printers[this.view];
    const st = $("#printer-stage");
    const blink = Math.floor(performance.now() / 400) % 2 === 0;
    const led = (on, col, blinking) => (on && (!blinking || blink) ? col : "#3a3a3a");
    const printing = p.feeding && p.anim === "print";
    const prog = p.progress || 0;
    const stackH = (n) => Math.min(60, n * 0.6);
    const tint = (s) => (s ? (PAPER_TYPES[s.type] || PAPER_TYPES.plain).tint : "#fff");
    let svg;
    if (p.def.kind === "inkjet") {
      const inN = p.tray.length, outN = p.out.length;
      const tankCols = { C: "#00a0e0", M: "#e0007a", Y: "#ffd400", K: "#1b1b1b" };
      const tanks = Object.keys(p.def.tanks).map((t, i) => {
        const lvl = p.ink[t] / p.def.tanks[t];
        const x = 432 + i * 20, h = 70 * lvl;
        return `<rect x="${x}" y="150" width="14" height="70" rx="2" fill="#2b2b2b" stroke="#555"/>
          <rect x="${x + 2}" y="${218 - h}" width="10" height="${Math.max(0, h)}" fill="${tankCols[t]}" opacity=".9"/>
          <text x="${x + 7}" y="236" font-size="10" text-anchor="middle" fill="#bbb">${t}</text>`;
      }).join("");
      const headX = 150 + (printing ? (Math.sin(performance.now() / 120) + 1) / 2 * 215 : 30);
      const feedY = p.feeding ? (p.anim === "feed" ? 60 : 90) : null;
      const top = p.tray[0];
      svg = `<svg viewBox="0 0 600 330" xmlns="http://www.w3.org/2000/svg">
        <!-- rear paper support and the paper in it -->
        <path d="M150 105 L175 10 L425 10 L400 105 Z" fill="#cfd3d8" stroke="#9aa0a6"/>
        ${inN ? `<path d="M165 103 L${186 - stackH(inN) * 0.1} 18 L${414} 18 L393 103 Z" fill="${tint(top)}" stroke="#bbb"/>
          <path d="M163 105 L${184 - stackH(inN) * 0.1} 20 L${416} 20 L395 105 Z" fill="none" stroke="#ccc" stroke-dasharray="1 2"/>` : ""}
        <text x="290" y="60" text-anchor="middle" font-size="12" fill="#555">${inN ? inN + " hojas" : "vacía"}</text>
        <!-- body -->
        <rect x="80" y="100" width="440" height="150" rx="16" fill="#3c4046"/>
        <rect x="80" y="100" width="440" height="34" rx="16" fill="#4b5058"/>
        <rect x="100" y="145" width="318" height="60" rx="6" fill="#23262a"/>
        <!-- print head -->
        <rect x="${headX}" y="152" width="44" height="30" rx="4" fill="#5f6670" stroke="#80868b"/>
        ${p.feeding ? `<rect x="190" y="${feedY + 70}" width="220" height="12" fill="${tint(p.feeding)}" opacity=".95"/>` : ""}
        <!-- control panel -->
        <circle cx="112" cy="117" r="7" fill="${led(p.power, "#59d36b", printing)}" stroke="#777"/>
        <text x="124" y="121" font-size="10" fill="#ddd">⏻</text>
        <circle cx="146" cy="117" r="4" fill="${led(p.power && p.connected, "#4cc2ff")}" />
        <circle cx="166" cy="117" r="4" fill="${led(p.power && (p.wait === "paper" || p.wait === "jam"), "#ff9e3d", p.wait === "jam")}" />
        <text x="174" y="121" font-size="10" fill="#ddd">papel</text>
        <circle cx="216" cy="117" r="4" fill="${led(p.power && p.wait === "ink", "#ff9e3d", true)}" />
        <text x="224" y="121" font-size="10" fill="#ddd">tinta</text>
        <!-- tanks -->
        ${tanks}
        <!-- output tray -->
        <path d="M150 250 L130 300 L470 300 L450 250 Z" fill="#555a61" stroke="#3a3d42"/>
        ${outN ? `<path d="M175 ${255 - stackH(outN) * 0.2} L160 ${292 - stackH(outN) * 0.2} L440 ${292 - stackH(outN) * 0.2} L425 ${255 - stackH(outN) * 0.2} Z" fill="${tint(p.out[0])}" stroke="#bbb"/>` : ""}
        <text x="300" y="318" text-anchor="middle" font-size="12" fill="var(--sim-fg2)">${outN ? `${outN} hojas en la bandeja de salida (boca arriba)` : "bandeja de salida vacía"}</text>
        ${p.jammed ? `<g><rect x="230" y="200" width="140" height="30" rx="4" fill="#c42b1c"/><text x="300" y="220" text-anchor="middle" font-size="13" fill="#fff">¡ATASCO!</text></g>` : ""}
        ${!p.power ? `<rect x="80" y="100" width="440" height="150" rx="16" fill="rgba(0,0,0,.35)"/>` : ""}
      </svg>`;
    } else {
      const inN = p.tray.length, outN = p.out.length;
      const lvl = p.ink.K / p.def.tanks.K;
      svg = `<svg viewBox="0 0 600 330" xmlns="http://www.w3.org/2000/svg">
        <rect x="120" y="60" width="360" height="200" rx="12" fill="#e4e6e9" stroke="#b5b9be"/>
        <path d="M170 60 L190 30 L410 30 L430 60 Z" fill="#cdd1d6" stroke="#b5b9be"/>
        ${outN ? `<rect x="200" y="${42 - stackH(outN) * 0.2}" width="200" height="${6 + stackH(outN) * 0.2}" fill="${tint(p.out[0])}" stroke="#bbb"/>` : ""}
        <text x="300" y="22" text-anchor="middle" font-size="12" fill="var(--sim-fg2)">${outN ? outN + " hojas arriba (boca abajo)" : "salida vacía"}</text>
        <rect x="140" y="200" width="320" height="46" rx="6" fill="#d3d6da" stroke="#a9adb2"/>
        <rect x="270" y="218" width="60" height="8" rx="4" fill="#9aa0a6"/>
        <text x="300" y="275" text-anchor="middle" font-size="12" fill="var(--sim-fg2)">bandeja: ${inN} hojas</text>
        <rect x="150" y="80" width="120" height="44" rx="4" fill="#1e2a22"/>
        <text x="160" y="100" font-size="11" fill="#7cf29b">${p.power ? (p.wait ? "ERROR" : p.feeding ? "Imprimiendo" : "Lista") : ""}</text>
        <text x="160" y="116" font-size="10" fill="#7cf29b">${p.power ? `Tóner ${Math.round(lvl * 100)} %` : ""}</text>
        <circle cx="300" cy="100" r="7" fill="${led(p.power, "#59d36b", p.feeding)}"/>
        <circle cx="325" cy="100" r="6" fill="${led(p.power && p.wait, "#ff9e3d", true)}"/>
        ${p.feeding ? `<rect x="200" y="140" width="200" height="${10 + prog * 40}" fill="${tint(p.feeding)}" stroke="#ccc"/>` : ""}
        ${p.jammed ? `<rect x="230" y="150" width="140" height="30" rx="4" fill="#c42b1c"/><text x="300" y="170" text-anchor="middle" font-size="13" fill="#fff">¡ATASCO!</text>` : ""}
        ${!p.power ? `<rect x="120" y="60" width="360" height="200" rx="12" fill="rgba(0,0,0,.35)"/>` : ""}
      </svg>`;
    }
    if (!st.firstChild) {
      st.innerHTML = `<div class="svgwrap" style="height:100%"></div><div style="position:absolute;left:8px;top:8px;display:flex;gap:6px;flex-wrap:wrap">
      <button class="simbtn small" id="b-power"></button>
      <button class="simbtn small" id="b-go" title="Botón de reanudar / papel (el de la impresora)">▷ Botón de papel / reanudar</button>
      <button class="simbtn small danger" id="b-stop" title="Botón de parar: cancela el trabajo que se imprime">⏹ Parar</button></div>`;
      const cur = () => this.printers[this.view];
      $("#b-power").onclick = () => { const q = cur(); q.power = !q.power; this.log(`${q.name}: ${q.power ? "encendida" : "apagada"}`); this.stateChanged(); if (q.power) this.schedule(); };
      $("#b-go").onclick = () => this.pressButton(cur(), false);
      $("#b-stop").onclick = () => this.pressButton(cur(), true);
    }
    $(".svgwrap", st).innerHTML = svg;
    $("#b-power").textContent = p.power ? "⏻ Apagar" : "⏻ Encender";
    if ((p.feeding || p.wait || (p.busy && blink !== undefined)) && !this._ticking) {
      this._ticking = true;
      setTimeout(() => { this._ticking = false; this.renderStage(); this.renderState(); }, 200);
    }
  },
  renderState() {
    const p = this.printers[this.view];
    const st = this.cupsState(p.name);
    let html;
    if (!this.installed.includes(p.name)) html = `<span class="warn">No instalada en CUPS: el diálogo no la lista.</span> <button class="simbtn small" id="b-inst">Instalar</button>`;
    else if (st.problem) html = `<span class="bad">${esc(st.state)}</span> ${esc(p.activity || "")}`;
    else if (p.feeding) html = `<span class="ok">${esc(p.activity)}</span> · ${Math.round((p.progress || 0) * 100)} %`;
    else html = `<span class="ok">Lista</span>${p.activity ? " · " + esc(p.activity) : ""}`;
    if (this._stateHtml === html) return;
    this._stateHtml = html;
    $("#printer-state").innerHTML = html;
    const ib = $("#b-inst"); if (ib) ib.onclick = () => this.install(p.name);
  },
  renderHands() {
    const box = $("#hands");
    const h = this.hands;
    if (!h) { box.innerHTML = ""; return; }
    const top = h.sheets[0];
    const desc = (sh) => {
      const f = sh.faces[sh.pose.up];
      return f.length ? `p. ${f.map((L) => L.pages.map((i) => i + 1).join("+")).join(" sobre ")} ${["N", "S"].includes(f[0].topEdge) && f[0].topEdge === sh.pose.top ? "derecha" : "girada/al revés"}` : "en blanco";
    };
    const p = this.printers[this.view];
    box.innerHTML = `<div class="hands-box"><div><strong>En tus manos: ${h.sheets.length} hojas.</strong>
      Arriba ves: ${esc(desc(top))}. Abajo: ${esc(desc(h.sheets[h.sheets.length - 1]))}.</div>
      <div class="acts">
        <button class="simbtn small" data-op="book">Dar la vuelta como un libro (borde largo)</button>
        <button class="simbtn small" data-op="notepad">Dar la vuelta como un bloc (borde corto)</button>
        <button class="simbtn small" data-op="rotate">Girar 180° (sin dar la vuelta)</button>
        <button class="simbtn small" data-op="top-aside">Apartar la de arriba</button>
        <button class="simbtn small" data-op="bottom-aside">Apartar la de abajo</button>
        <button class="simbtn small" data-op="view">Ver las hojas</button>
      </div><div class="acts">
        <button class="simbtn small primary" data-load="replace">Cargar en ${esc(p.name)} quitando el papel que hay</button>
        <button class="simbtn small" data-load="front">Cargar delante del papel que hay</button>
        <button class="simbtn small" data-load="back">Cargar detrás</button>
        <button class="simbtn small" data-op="table">Dejar en la mesa</button>
      </div></div>`;
    box.querySelectorAll("[data-op]").forEach((b) => b.onclick = () => {
      const op = b.dataset.op;
      if (op === "view") this.viewSheets(h.sheets, "En tus manos (de arriba abajo)");
      else if (op === "table") this.handsPutDown();
      else this.handsDo(op);
    });
    box.querySelectorAll("[data-load]").forEach((b) => b.onclick = () => this.handsLoad(p, b.dataset.load));
  },
  thumb(sheet, label, k = 0.42) {
    const wrap = el("div", "sheet-thumb");
    const c = faceCanvas(sheet, sheet.pose.up, sheet.pose.top, k);
    wrap.appendChild(c);
    wrap.appendChild(el("span", "", esc(label)));
    return wrap;
  },
  renderOut() {
    const p = this.printers[this.view];
    const pane = $("#tab-out");
    pane.innerHTML = `<p class="help">Lo que hay en la bandeja de salida, de arriba abajo, tal como lo ves. ${p.def.faceUp ? "Esta impresora deja las hojas boca arriba." : "Esta impresora deja las hojas boca abajo."} Pulsa una hoja para ver sus dos caras.</p>`;
    const acts = el("div", "form-row");
    const take = el("button", "simbtn primary", "Sacar todas las hojas");
    take.disabled = !p.out.length;
    take.onclick = () => this.takeOutput(p);
    const check = el("button", "simbtn", "Comprobar el documento tal como está");
    check.disabled = !p.out.length;
    check.onclick = () => this.showCheck(p.out, "Bandeja de salida");
    acts.append(take, check);
    pane.appendChild(acts);
    const grid = el("div", "sheets");
    p.out.slice(0, 60).forEach((sh, i) => {
      const t = this.thumb(sh, `${i + 1}${i === 0 ? " (arriba)" : ""}`);
      t.onclick = () => this.inspect(sh);
      grid.appendChild(t);
    });
    if (p.out.length > 60) grid.appendChild(el("div", "", `… y ${p.out.length - 60} más`));
    pane.appendChild(grid);
  },
  renderIn() {
    const p = this.printers[this.view];
    const pane = $("#tab-in");
    const groups = [];
    for (const sh of p.tray) {
      const printed = sh.faces.A.length + sh.faces.B.length > 0;
      const key = `${sh.size}|${sh.type}|${printed}`;
      const last = groups[groups.length - 1];
      if (last && last.key === key) last.n++; else groups.push({ key, n: 1, sh, printed });
    }
    pane.innerHTML = `<p class="help">${p.def.tray === "rear" ? "Alimentador trasero: el papel va de pie, la cara a imprimir hacia ti y el borde de arriba entrando primero. Entra primero la hoja de delante." : "Bandeja (cajón) de 250 hojas."} Caben ${p.def.capacity}.</p>`;
    const list = el("div");
    list.innerHTML = groups.length ? groups.map((g, i) => `<div>${i === 0 ? "Entra primero → " : ""}${g.n} × ${esc(_(PAPER_LABELS[g.sh.size] || g.sh.size))}, ${esc(PAPER_TYPES[g.sh.type].label)}${g.printed ? " <strong>(ya impresas)</strong>" : ""}</div>`).join("") : "<div><strong>Bandeja vacía</strong></div>";
    pane.appendChild(list);
    const form = el("div", "form-row");
    form.style.marginTop = "10px";
    form.innerHTML = `<input type="number" id="pp-n" value="20" min="1" max="250" style="width:70px">
      <select id="pp-size">${Object.keys(PAPER_MM).map((s) => `<option value="${s}">${esc(_(PAPER_LABELS[s]))}</option>`).join("")}</select>
      <select id="pp-type">${Object.entries(PAPER_TYPES).map(([k, v]) => `<option value="${k}">${esc(v.label)}</option>`).join("")}</select>
      <button class="simbtn primary" id="pp-add">Añadir papel</button>
      <button class="simbtn" id="pp-take">Sacar todo el papel</button>`;
    pane.appendChild(form);
    $("#pp-add").onclick = () => this.addPaper(p, $("#pp-size").value, $("#pp-type").value, parseInt($("#pp-n").value, 10) || 1);
    $("#pp-take").onclick = () => this.takeInput(p);
    $("#pp-take").disabled = !p.tray.length;
  },
  renderQueue() {
    const pane = $("#tab-queue");
    pane.innerHTML = `<p class="help">Los trabajos como los ve CUPS (lpstat -o). Las opciones son las que manda el diálogo (printing.job_settings) a través del backend CUPS de GTK.</p>`;
    const stName = { pending: "En espera", processing: "Imprimiendo", completed: "Completado", canceled: "Cancelado", aborted: "Abortado", held: "Retenido" };
    const jobs = this.jobs.slice().reverse();
    if (!jobs.length) pane.appendChild(el("div", "", "No hay trabajos."));
    for (const j of jobs) {
      const d = el("div", "job");
      const pct = j.plan.units.length ? Math.round(j.done / j.plan.units.length * 100) : 0;
      d.innerHTML = `<div class="job-head"><div><span class="st">${esc(j.printer)}-${j.id}</span> · ${esc(j.title)} · ${esc(stName[j.state])}${j.cancelReason ? ` (${esc(j.cancelReason)})` : ""}</div>
        <div>${["pending", "processing"].includes(j.state) ? '<button class="simbtn small danger">Cancelar</button>' : ""}</div></div>
        <div>${j.plan.units.length} hojas · ${j.plan.sides.length} caras · ${j.done} hechas · orden de salida ${esc(j.plan.order)}${j.plan.duplex ? " · dúplex " + esc(j.plan.duplex) : ""}</div>
        <div class="progress"><div style="width:${pct}%"></div></div>
        <details><summary>Opciones CUPS y orden de las caras</summary>
        <div class="kv" style="margin-top:6px">${Object.entries(j.opts).map(([k, v]) => `<span>${esc(k)}</span><span>${esc(v)}</span>`).join("")}</div>
        <div style="margin-top:6px">Caras en el orden en que salen: ${j.plan.units.map((u) => "[" + u.map((s) => s.map((i) => i + 1).join("+")).join(" | ") + "]").join(" ")}</div>
        </details>`;
      const b = $("button", d);
      if (b) b.onclick = () => this.cancelJob(j);
      pane.appendChild(d);
    }
  },
  renderInk() {
    const p = this.printers[this.view];
    const pane = $("#tab-ink");
    const cols = { C: "#00a0e0", M: "#e0007a", Y: "#ffd400", K: "#1b1b1b" };
    const names = { C: "Cian", M: "Magenta", Y: "Amarillo", K: "Negro" };
    pane.innerHTML = `<p class="help">${p.def.kind === "inkjet" ? "Depósitos de tinta (EcoTank). Con menos del 3 % la impresión sale pálida en ese color; vacío, la impresora se para hasta que lo rellenes y pulses ▷." : "Tóner."} Gasto calculado por la cobertura real de cada cara.</p>`;
    const row = el("div", "tanks");
    for (const t of Object.keys(p.ink)) {
      const lvl = p.ink[t] / p.def.tanks[t];
      const d = el("div", "tank");
      d.innerHTML = `<div class="bar"><div style="height:${lvl * 100}%;background:${cols[t]}"></div></div>
        <div>${names[t]}</div><div>${Math.round(lvl * 100)} % · ${p.ink[t].toFixed(1)} ml</div><div style="color:var(--sim-fg2)">gastado ${p.inkUsed[t].toFixed(2)} ml</div>`;
      const fill = el("button", "simbtn small", "Rellenar");
      fill.onclick = () => { p.ink[t] = p.def.tanks[t]; this.log(`${p.name}: rellenas ${names[t]}`); this.stateChanged(); };
      const drain = el("button", "simbtn small", "Vaciar");
      drain.onclick = () => { p.ink[t] = 0; this.log(`${p.name}: ${names[t]} vacío (simulado)`); this.stateChanged(); };
      const lowb = el("button", "simbtn small", "Casi vacío");
      lowb.onclick = () => { p.ink[t] = p.def.tanks[t] * 0.02; this.stateChanged(); };
      d.append(fill, lowb, drain);
      row.appendChild(d);
    }
    pane.appendChild(row);
    pane.appendChild(el("p", "help", `Hojas impresas: ${p.sheetsPrinted}`));
  },
  renderFaults() {
    const p = this.printers[this.view];
    const pane = $("#tab-faults");
    pane.innerHTML = `
      <div class="form-row"><label><input type="checkbox" id="f-conn" ${p.connected ? "" : "checked"}> Cable USB / Wi-Fi desconectado</label></div>
      <div class="form-row"><label><input type="checkbox" id="f-pause" ${p.paused ? "checked" : ""}> Cola pausada en CUPS (cupsdisable)</label></div>
      <div class="form-row"><label><input type="checkbox" id="f-reject" ${p.accepting ? "" : "checked"}> Cola que no acepta trabajos (cupsreject)</label></div>
      <div class="form-row"><button class="simbtn" id="f-jam">Atascar la siguiente hoja</button>
        <label>Probabilidad de atasco por hoja <input type="number" id="f-jamp" min="0" max="100" value="${this.jamChance}" style="width:60px"> %</label>
        <button class="simbtn" id="f-clear" ${p.jammed ? "" : "disabled"}>Quitar la hoja atascada</button></div>
      <div class="form-row"><label>Velocidad <select id="f-speed">
        ${[[1, "real (×1)"], [5, "×5"], [20, "×20"], [0, "instantánea"]].map(([v, t]) => `<option value="${v}" ${this.speed === v ? "selected" : ""}>${t}</option>`).join("")}</select></label></div>
      <div class="form-row"><label>CUPS (pdftopdf) aplica
        <select id="f-pageset"><option value="output" ${this.pageSetMode === "output" ? "selected" : ""}>page-ranges a las páginas del archivo, page-set a las caras ya compuestas (supuesto por defecto)</option>
        <option value="input" ${this.pageSetMode === "input" ? "selected" : ""}>los dos a las páginas del archivo, antes de N por hoja</option></select></label></div>
      <div class="form-row"><label><input type="checkbox" id="f-blank" ${this.evenBlank ? "checked" : ""}> page-set=even añade una cara en blanco si el total es impar (libcupsfilters ≥ 2.1.1; tu Fedora tiene 2.2.1)</label></div>
      <div class="form-row"><label>Impresora predeterminada del sistema (lpstat -d)
        <select id="f-default"><option value="">ninguna (como en tu portátil)</option>${this.installed.map((n) => `<option ${this.defaultPrinter === n ? "selected" : ""}>${esc(n)}</option>`).join("")}</select></label></div>
      <div class="form-row">${this.installed.includes(p.name) ? `<button class="simbtn danger" id="f-uninst">Eliminar la cola ${esc(p.name)} de CUPS</button>` : `<button class="simbtn" id="f-inst">Instalar ${esc(p.name)} en CUPS</button>`}
        <button class="simbtn" id="f-restart">Reiniciar la simulación</button>
        <button class="simbtn danger" id="f-reset">Borrar la configuración recordada (print-portal.ini)</button></div>`;
    $("#f-conn").onchange = (e) => { p.connected = !e.target.checked; this.log(`${p.name}: ${p.connected ? "conectada" : "desconectada"}`); this.stateChanged(); };
    $("#f-pause").onchange = (e) => { p.paused = e.target.checked; this.log(`cupsdisable/cupsenable ${p.name}`); this.stateChanged(); };
    $("#f-reject").onchange = (e) => { p.accepting = !e.target.checked; this.log(`cupsreject/cupsaccept ${p.name}`); this.stateChanged(); };
    $("#f-jam").onclick = () => { this.jamNext = true; this.log("La siguiente hoja se atascará"); };
    $("#f-jamp").onchange = (e) => { this.jamChance = Math.max(0, Math.min(100, +e.target.value || 0)); };
    $("#f-clear").onclick = () => this.clearJam(p);
    $("#f-speed").onchange = (e) => { this.speed = +e.target.value; };
    $("#f-pageset").onchange = (e) => { this.pageSetMode = e.target.value; this.log(`page-set: ${this.pageSetMode}`); };
    $("#f-blank").onchange = (e) => { this.evenBlank = e.target.checked; };
    $("#f-default").onchange = (e) => { this.defaultPrinter = e.target.value; this.log(`lpadmin -d ${this.defaultPrinter || "(ninguna)"}`); };
    const u = $("#f-uninst"); if (u) u.onclick = () => this.uninstall(p.name);
    const i = $("#f-inst"); if (i) i.onclick = () => this.install(p.name);
    $("#f-restart").onclick = () => this.reset();
    $("#f-reset").onclick = () => { Config.clear(); this.log("print-portal.ini borrado"); this.renderTech(); };
  },
  renderTable() {
    const pane = $("#tab-table");
    pane.innerHTML = `<p class="help">Lo que dejas sobre la mesa y los PDF guardados. «Comprobar» lee el montón como lo leería una persona: la hoja de arriba primero y su cara de arriba es la portada.</p>`;
    for (const f of this.files) {
      const d = el("div", "stack-card");
      d.innerHTML = `<strong>📄 ${esc(f.name)}</strong> · ${f.sheets.length} páginas · <span style="color:var(--sim-fg2)">${esc(f.uri)}</span> <button class="simbtn small">Abrir</button>`;
      $("button", d).onclick = () => this.viewPdf(f);
      pane.appendChild(d);
    }
    for (const s of this.table) {
      const d = el("div", "stack-card");
      d.innerHTML = `<div class="job-head"><strong>${esc(s.name)}</strong><span>${s.sheets.length} hojas</span></div>
        <div class="acts" style="display:flex;gap:6px;flex-wrap:wrap;margin-top:6px">
        <button class="simbtn small primary" data-a="check">Comprobar</button>
        <button class="simbtn small" data-a="book">Leer como libro</button>
        <button class="simbtn small" data-a="view">Ver hojas</button>
        <button class="simbtn small" data-a="take">Coger</button>
        <button class="simbtn small danger" data-a="bin">Tirar</button></div>`;
      d.querySelectorAll("[data-a]").forEach((b) => b.onclick = () => {
        const a = b.dataset.a;
        if (a === "check") this.showCheck(s.sheets, s.name);
        if (a === "book") this.bookViewer(s.sheets);
        if (a === "view") this.viewSheets(s.sheets, s.name);
        if (a === "take") { this.table = this.table.filter((x) => x !== s); this.toHands(s.sheets, "mesa"); }
        if (a === "bin") { this.table = this.table.filter((x) => x !== s); this.renderTable(); }
      });
      pane.appendChild(d);
    }
    if (!this.files.length && !this.table.length) pane.appendChild(el("div", "", "La mesa está vacía."));
  },
  renderTech() {
    const pane = $("#tab-tech");
    if (!pane) return;
    const d = Dialog.current;
    let html = "";
    if (d) {
      const c = d.choice;
      html += `<h4>Diálogo abierto: elección actual (printing.Choice)</h4><div class="kv">${Object.entries({
        printer: c.printer, copies: c.copies, collate: c.collate, orientation: c.orientation, pages: c.pages, ranges_text: c.ranges_text,
        color: c.color, paper: c.paper, number_up: c.number_up, margins: c.margins, duplex: c.duplex,
        driver: Object.entries(c.driver).map(([k, v]) => `${k}=${v}`).join(" "),
      }).map(([k, v]) => `<span>${esc(k)}</span><span>${esc(v)}</span>`).join("")}</div>
      <p class="help" style="margin-top:6px">Dúplex automático de la impresora elegida: ${Sim.autoDuplex(c.printer) ? "sí" : "no (se ofrece la doble cara manual)"}</p>`;
    }
    if (this.lastResult) {
      const r = this.lastResult;
      html += `<h4 style="margin-top:12px">Última respuesta del diálogo: response ${r.response}</h4>
        <pre class="code">settings (GtkPrintSettings)\n${Object.entries(r.settings).map(([k, v]) => `  ${k} = ${v}`).join("\n")}\n\npage-setup (GtkPageSetup)\n${Object.entries(r.setup).map(([k, v]) => `  ${k} = ${typeof v === "number" ? v.toFixed(2) + " mm" : v}`).join("\n")}</pre>`;
    }
    html += `<h4 style="margin-top:12px">~/.config/fenestra/print-portal.ini (simulado)</h4><pre class="code">${esc(Config.ini())}</pre>`;
    pane.innerHTML = html;
  },
  renderLog() {
    const pane = $("#tab-log");
    if (!pane) return;
    pane.innerHTML = `<div class="log">${this.logLines.map((l) => `<div>${esc(l)}</div>`).join("")}</div>`;
  },

  // ---------------------------------------------------------------- viewers
  inspect(sheet) {
    const box = el("div", "modal-box");
    box.innerHTML = `<div class="modal-head"><strong>Hoja ${sheet.id} · ${esc(_(PAPER_LABELS[sheet.size]))} · ${esc(PAPER_TYPES[sheet.type].label)}</strong><button class="simbtn small">Cerrar</button></div>`;
    const faces = el("div", "faces");
    const up = sheet.pose.up, top = sheet.pose.top;
    const f1 = el("div", "face"); f1.appendChild(faceCanvas(sheet, up, top, 1.5));
    f1.appendChild(el("div", "", "Cara de arriba, como la ves"));
    // the other face as seen after turning the sheet over like a book page
    const f2 = el("div", "face"); f2.appendChild(faceCanvas(sheet, other(up), top, 1.5));
    f2.appendChild(el("div", "", "Cara de abajo (dándole la vuelta como a la página de un libro)"));
    faces.append(f1, f2);
    box.appendChild(faces);
    const notes = [...sheet.faces.A, ...sheet.faces.B].map((L) => L.note).filter(Boolean);
    if (notes.length) box.appendChild(el("p", "help", "Notas: " + esc(notes.join("; "))));
    openModal(box);
    $(".simbtn", box).onclick = closeModal;
  },
  viewSheets(sheets, title) {
    const box = el("div", "modal-box");
    box.innerHTML = `<div class="modal-head"><strong>${esc(title)}</strong><button class="simbtn small">Cerrar</button></div><p class="help">De arriba abajo; cada hoja como está (cara de arriba).</p>`;
    const g = el("div", "sheets");
    sheets.forEach((sh, i) => { const t = this.thumb(sh, `${i + 1}`, 0.7); t.onclick = () => this.inspect(sh); g.appendChild(t); });
    box.appendChild(g);
    openModal(box);
    $(".simbtn", box).onclick = closeModal;
  },
  showCheck(sheets, title) {
    const r = this.check(sheets);
    const box = el("div", "modal-box");
    box.innerHTML = `<div class="modal-head"><strong>Comprobación: ${esc(title)}</strong><button class="simbtn small">Cerrar</button></div>`;
    if (!r.group) { box.appendChild(el("p", "", "No hay nada impreso.")); openModal(box); $(".simbtn", box).onclick = closeModal; return; }
    const c = r.group.choice;
    box.appendChild(el("p", "help", `Documento «${esc(r.group.title)}» · ${r.twoSided ? `a doble cara, encuadernado por el borde ${r.binding === "long" ? "largo" : "corto"}` : "a una cara"} · ${c.number_up} por hoja · ${c.orientation === "landscape" ? "horizontal" : "vertical"} · se esperaban ${r.group.expected.length} caras`));
    const v = el("div", "verdict " + (r.ok ? "ok" : "bad"));
    v.innerHTML = `<strong>${r.ok ? "✓ El documento está bien" : "✗ El documento no está bien"}</strong>${r.hint ? `<div>${esc(r.hint)}</div>` : ""}
      <ul>${r.rows.concat(r.issues).map((x) => `<li>${esc(x)}</li>`).join("")}</ul>`;
    box.appendChild(v);
    const b = el("button", "simbtn", "Leer como libro");
    b.onclick = () => this.bookViewer(sheets);
    box.appendChild(b);
    openModal(box);
    $(".simbtn", box).onclick = closeModal;
  },
  // Page through the stack turning each sheet over on its binding edge, as a reader would.
  bookViewer(sheets) {
    const r = this.check(sheets);
    let binding = r.binding || "long";
    let i = 0, flipped = false;
    const box = el("div", "modal-box");
    const draw = () => {
      const sh = sheets[i];
      const front = sh.pose.up, back = other(front);
      const fl = sh.faces[front][0];
      const U = fl ? fl.topEdge : sh.pose.top;
      const portrait = U === "N" || U === "S";
      const aroundVertical = (binding === "long") === portrait;
      const backTop = aroundVertical ? U : opposite(U);
      const k = 1.6;
      const fc = faceCanvas(sh, front, U, k), bc = faceCanvas(sh, back, backTop, k);
      box.innerHTML = `<div class="modal-head"><strong>Leer como libro · hoja ${i + 1} de ${sheets.length}</strong><button class="simbtn small" data-a="close">Cerrar</button></div>
        <div class="form-row"><label>Encuadernado por el borde <select data-a="bind"><option value="long" ${binding === "long" ? "selected" : ""}>largo</option><option value="short" ${binding === "short" ? "selected" : ""}>corto</option></select></label>
        <button class="simbtn small" data-a="prev">◀ Hoja anterior</button><button class="simbtn small primary" data-a="flip">Voltear la hoja</button><button class="simbtn small" data-a="next">Hoja siguiente ▶</button></div>
        <p class="help">La portada se pone derecha; al voltear, la hoja gira sobre el borde de encuadernación y la de detrás debe leerse derecha.</p>`;
      const stage = el("div", "flipper");
      const card = el("div", "flip-card");
      const W = Math.max(fc.width, bc.width), H = Math.max(fc.height, bc.height);
      card.style.width = W + "px"; card.style.height = H + "px";
      bc.style.transform = aroundVertical ? "rotateY(180deg)" : "rotateX(180deg)";
      card.append(fc, bc);
      if (flipped) card.style.transform = aroundVertical ? "rotateY(-180deg)" : "rotateX(180deg)";
      stage.appendChild(card);
      box.appendChild(stage);
      box.querySelector('[data-a="close"]').onclick = closeModal;
      box.querySelector('[data-a="bind"]').onchange = (e) => { binding = e.target.value; flipped = false; draw(); };
      box.querySelector('[data-a="prev"]').onclick = () => { if (i > 0) { i--; flipped = false; draw(); } };
      box.querySelector('[data-a="next"]').onclick = () => { if (i < sheets.length - 1) { i++; flipped = false; draw(); } };
      box.querySelector('[data-a="flip"]').onclick = () => {
        flipped = !flipped;
        card.style.transform = flipped ? (aroundVertical ? "rotateY(-180deg)" : "rotateX(180deg)") : "none";
      };
    };
    draw();
    openModal(box);
  },
  viewPdf(f) {
    const box = el("div", "modal-box");
    box.innerHTML = `<div class="modal-head"><strong>${esc(f.name)}</strong><button class="simbtn small">Cerrar</button></div>`;
    const g = el("div", "sheets");
    const c = f.group.choice;
    const choice = new Choice({ orientation: c.orientation, paper: c.paper, number_up: c.number_up, color: true, margins: c.margins });
    f.sheets.forEach((pages, i) => {
      const [sw, sh] = choice.sheet_mm();
      const cv = el("canvas");
      cv.width = Math.round(sw * 1.2); cv.height = Math.round(sh * 1.2);
      const x = cv.getContext("2d");
      drawSheet(x, choice, cv.width, cv.height, pages, f.group.doc, M.PREVIEW_LIGHT, false);
      const w = el("div", "sheet-thumb"); w.append(cv, el("span", "", String(i + 1)));
      g.appendChild(w);
    });
    box.appendChild(g);
    openModal(box);
    $(".simbtn", box).onclick = closeModal;
  },
});

// ------------------------------------------------------------------ start
Theme.apply();
Sim.init();
const SHOT = new URLSearchParams(location.search);
if (SHOT.has("shot")) {
  document.body.classList.add("shot");
  Theme.dark = SHOT.get("theme") === "dark"; Theme.apply();
  Sim.speed = 0;
}
Sim.setDoc(SHOT.get("doc") || "text").then(() => {
  Sim.openDialog();
  const d = Dialog.current;
  if (SHOT.has("shot")) {
    d.root.classList.remove("fv");
    document.activeElement.blur();
    if (SHOT.get("page") === "more") { d.morePage.style.transition = d.mainPage.style.transition = "none"; d.root.classList.add("show-more"); }
  }
});
Sim.log("Simulador listo. ET-2710-Series instalada en CUPS; sin impresora predeterminada del sistema.");
