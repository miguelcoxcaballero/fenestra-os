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
    box.innerHTML = `<div class="modal-head"><h2>Agregar una impresora</h2><button class="btn sm">Cerrar</button></div>
      <p class="help">En Fenestra este enlace abre la configuración de impresoras del sistema. Aquí añade una cola CUPS al simulador; el diálogo abierto la recibe como un printer-added de GTK.</p>`;
    if (!missing.length) box.appendChild(el("p", "", "Ya están todas instaladas."));
    for (const n of missing) {
      const b = el("button", "btn", `Instalar ${esc(n)} — ${esc(PRINTERS[n].model)}`);
      b.onclick = () => { this.install(n); closeModal(); };
      box.appendChild(b);
    }
    openModal(box);
    $(".btn", box).onclick = closeModal;
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
    const sub = $("#app-sub");
    if (sub) sub.textContent = this.previewDoc ? "El diálogo tal como se ve en Fenestra" : "App que imprime con PreparePrint: el diálogo no tiene vista previa";
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
    this.lastGroup = group;
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
    group.front = this.jobs[this.jobs.length - 1];
    this.lastGroup = group;
    group.sides = sides;
    group.stage = "fronts";
    this.guide = new DuplexGuide(group, {
      onContinue: () => {
        this.log("manual two-sided: printing the backs");
        this.submit(group, file, prepare, "back");
        group.back = this.jobs[this.jobs.length - 1];
        group.stage = "backs";
        this.stateChanged();
      },
      onCancel: () => { group.stage = "cancelled"; this.log("manual two-sided: backs cancelled"); this.stateChanged(); },
      onClose: () => { if (this.guide && this.guide.group === group) this.guide = null; },
    });
    this.stateChanged();
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
    p.current = { job, pages: unit[0], back: false, sheet };
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
      p.current = { job, pages: unit[k], back: k === 1, sheet };
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
    p.current = null;
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
    document.querySelectorAll("#overlay .fp-small, #overlay .guide").forEach((w) => w.remove());
    this.guide = null;
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
