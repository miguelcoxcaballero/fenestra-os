// SPDX-License-Identifier: GPL-3.0-or-later
// Fenestra Print Studio: the page around the dialog and the twin — toolbar, the stage scaled to fit,
// the side panels (trays, CUPS queue, ink, faults, table, technical view, log) and the viewers.
"use strict";

const STATE_NAMES = { pending: "En espera", processing: "Imprimiendo", completed: "Completado", canceled: "Cancelado", aborted: "Abortado", held: "Retenido" };
const INK_NAMES = { C: "Cian", M: "Magenta", Y: "Amarillo", K: "Negro" };
const INK_COLS = { C: "#00a3e0", M: "#e0007a", Y: "#ffd400", K: "#26282c" };

Object.assign(Sim, {
  ui() {
    const acc = $("#sim-accent");
    const names = { blue: "Azul", teal: "Verde azulado", green: "Verde", yellow: "Amarillo", orange: "Naranja", red: "Rojo", pink: "Rosa", purple: "Morado", slate: "Pizarra" };
    for (const a of Object.keys(M.ACCENTS)) acc.appendChild(new Option(names[a], a));
    acc.onchange = () => { Theme.accent = acc.value; Theme.apply(); this.renderAll(); };
    $("#sim-theme").addEventListener("click", (e) => {
      const b = e.target.closest("button"); if (!b) return;
      $("#sim-theme").querySelectorAll("button").forEach((x) => x.classList.toggle("on", x === b));
      Theme.dark = b.dataset.v === "dark"; Theme.apply(); Twin.cache = {}; this.renderAll();
    });
    $("#sim-lang").onchange = (e) => { LANG = e.target.value; if (Dialog.current) { Dialog.current.finish(1); this.openDialog(); } };
    $("#sim-doc").onchange = (e) => {
      if (e.target.value === "pdf") { $("#sim-pdf").click(); return; }
      this.setDoc(e.target.value).then(() => this.reopen());
    };
    $("#sim-pdf").onchange = (e) => { if (e.target.files[0]) this.setDoc("pdf", e.target.files[0]).then(() => this.reopen()); };
    $("#sim-open").onclick = () => this.openDialog();
    document.addEventListener("keydown", (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "p") { e.preventDefault(); this.openDialog(); }
    });
    const ps = $("#sim-printer");
    ps.onchange = () => { this.view = ps.value; Twin.cache = {}; this.renderAll(); };
    $("#tabs").addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) this.tab(b.dataset.tab); });
    Twin.mount();
    // the stage keeps its real size (850 × 732 dialog) and is scaled down to the card's width
    const fit = () => {
      const box = $("#stage-fit"), scr = $("#screen");
      const k = Math.min(1, box.clientWidth / 900);
      scr.style.transform = `scale(${k})`;
      box.style.height = Math.round(790 * k) + "px";
    };
    new ResizeObserver(fit).observe($("#stage-fit"));
    fit();
  },
  reopen() { if (Dialog.current) { Dialog.current.finish(1); this.openDialog(); } },
  tab(name) {
    document.querySelectorAll("#tabs button").forEach((b) => b.classList.toggle("on", b.dataset.tab === name));
    document.querySelectorAll(".tabpane").forEach((p) => p.classList.toggle("on", p.id === "tab-" + name));
  },
  animate(p, what) { p.anim = what; p.animAt = performance.now(); },
  renderStage() { Twin.live(); },
  renderAll() {
    const ps = $("#sim-printer");
    const want = Object.keys(PRINTERS).map((n) => n + this.installed.includes(n)).join();
    if (ps.dataset.k !== want) {
      ps.dataset.k = want;
      ps.innerHTML = "";
      for (const n of Object.keys(PRINTERS)) ps.appendChild(new Option(n + (this.installed.includes(n) ? "" : " (no instalada)"), n, false, n === this.view));
    }
    Twin.update();
    if (this.guide) this.guide.update();
    this.renderOut(); this.renderIn(); this.renderQueue(); this.renderInk(); this.renderFaults(); this.renderTable(); this.renderTech();
    const p = this.printers[this.view];
    const busy = this.jobs.filter((j) => j.state === "pending" || j.state === "processing").length;
    $('#tabs [data-tab="queue"]').innerHTML = "Cola CUPS" + (busy ? `<span class="badge">${busy}</span>` : "");
    $('#tabs [data-tab="out"]').innerHTML = "Salida" + (p.out.length ? `<span class="badge">${p.out.length}</span>` : "");
    const low = Object.keys(p.ink).some((t) => p.ink[t] / p.def.tanks[t] < 0.1);
    $('#tabs [data-tab="ink"]').innerHTML = "Tinta" + (low ? '<span class="badge bad">!</span>' : "");
  },

  // the person, in one go: take the fronts out, turn them over like a book, load them
  doTurnOver(p) {
    if (!p.out.length) return;
    this.takeOutput(p);
    this.handsDo("book");
    this.handsLoad(p, "front");
  },
  collect(p) {
    if (!p.out.length) return;
    const name = (this.lastGroup && this.lastGroup.title) || "Documento";
    this.takeOutput(p);
    this.handsDo("book");          // what anyone does when picking up a face-up stack to read it
    this.handsPutDown(name);
    this.showCheck(this.table[0].sheets, name);
  },

  // ---------------------------------------------------------------- panels
  thumb(sheet, label, k = 0.42) {
    const wrap = el("button", "sheet-thumb");
    wrap.appendChild(faceCanvas(sheet, sheet.pose.up, sheet.pose.top, k));
    wrap.appendChild(el("span", "", esc(label)));
    return wrap;
  },
  renderOut() {
    const p = this.printers[this.view];
    const pane = $("#tab-out");
    const key = "out" + p.out.map((s) => s.id + s.faces.A.length + s.faces.B.length).join() + Theme.dark;
    if (pane.dataset.k === key) return;
    pane.dataset.k = key;
    pane.innerHTML = `<p class="help">Hojas en la bandeja de salida, de arriba abajo, tal como las ves (${p.def.faceUp ? "boca arriba" : "boca abajo"}). Pulsa una para ver sus dos caras.</p>`;
    const acts = el("div", "row");
    const take = el("button", "btn primary sm", "Sacar las hojas");
    take.disabled = !p.out.length; take.onclick = () => this.takeOutput(p);
    const check = el("button", "btn sm", "Comprobar el documento");
    check.disabled = !p.out.length; check.onclick = () => this.showCheck(p.out, "Bandeja de salida");
    acts.append(take, check);
    pane.appendChild(acts);
    const grid = el("div", "sheets");
    p.out.slice(0, 48).forEach((sh, i) => {
      const t = this.thumb(sh, i === 0 ? "1 · arriba" : String(i + 1));
      t.onclick = () => this.inspect(sh);
      grid.appendChild(t);
    });
    if (p.out.length > 48) grid.appendChild(el("div", "help", `y ${p.out.length - 48} más`));
    if (!p.out.length) grid.appendChild(el("div", "help", "La bandeja de salida está vacía."));
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
    const key = "in" + groups.map((g) => g.key + g.n).join();
    if (pane.dataset.k === key) return;
    pane.dataset.k = key;
    pane.innerHTML = `<p class="help">${p.def.tray === "rear" ? "Alimentador trasero: el papel va de pie, la cara a imprimir hacia ti y la parte de arriba entrando primero. Entra primero la hoja de delante." : "Cajón de papel."} Capacidad: ${p.def.capacity} hojas.</p>`;
    for (const [i, g] of groups.entries()) {
      const d = el("div", "list-item");
      d.innerHTML = `<div class="list-head"><strong>${g.n} × ${esc(_(PAPER_LABELS[g.sh.size] || g.sh.size))}</strong>${i === 0 ? '<span class="state-tag processing">entra primero</span>' : ""}</div>
        <div class="meta">${esc(PAPER_TYPES[g.sh.type].label)}${g.printed ? " · ya impresas por una cara" : ""}</div>`;
      pane.appendChild(d);
    }
    if (!groups.length) pane.appendChild(el("div", "help", "La bandeja está vacía."));
    const form = el("div", "row");
    form.style.marginTop = "12px";
    form.innerHTML = `<input type="number" id="pp-n" value="20" min="1" max="250" style="width:72px" aria-label="Hojas">
      <select id="pp-size" aria-label="Tamaño">${Object.keys(PAPER_MM).map((s) => `<option value="${s}">${esc(_(PAPER_LABELS[s]))}</option>`).join("")}</select>
      <select id="pp-type" aria-label="Tipo">${Object.entries(PAPER_TYPES).map(([k, v]) => `<option value="${k}">${esc(v.label)}</option>`).join("")}</select>
      <button class="btn primary sm" id="pp-add">Añadir papel</button>
      <button class="btn sm" id="pp-take" ${p.tray.length ? "" : "disabled"}>Sacar el papel</button>`;
    pane.appendChild(form);
    $("#pp-add").onclick = () => this.addPaper(p, $("#pp-size").value, $("#pp-type").value, parseInt($("#pp-n").value, 10) || 1);
    $("#pp-take").onclick = () => this.takeInput(p);
  },
  renderQueue() {
    const pane = $("#tab-queue");
    const jobs = this.jobs.slice().reverse();
    const key = "q" + jobs.map((j) => j.id + j.state + j.done).join();
    if (pane.dataset.k === key) return;
    pane.dataset.k = key;
    pane.innerHTML = `<p class="help">Trabajos como los ve CUPS (lpstat -o), con las opciones que manda el diálogo.</p>`;
    if (!jobs.length) pane.appendChild(el("div", "help", "No hay trabajos."));
    for (const j of jobs) {
      const d = el("div", "list-item");
      const pct = j.plan.units.length ? Math.round(j.done / j.plan.units.length * 100) : 0;
      d.innerHTML = `<div class="list-head"><div><strong>${esc(j.title)}</strong> <span class="state-tag ${j.state}">${esc(STATE_NAMES[j.state])}</span></div>
          ${["pending", "processing"].includes(j.state) ? '<button class="btn sm danger">Cancelar</button>' : ""}</div>
        <div class="meta">${esc(j.printer)}-${j.id} · ${j.plan.units.length} hojas · ${j.plan.sides.length} caras · orden ${esc(j.plan.order === "Reverse" ? "inverso" : "normal")}${j.plan.duplex ? " · dúplex " + esc(j.plan.duplex) : ""}${j.cancelReason ? " · " + esc(j.cancelReason) : ""}</div>
        <div class="progress"><div style="width:${pct}%"></div></div>
        <details><summary>Opciones CUPS y orden de las caras</summary>
        <div class="kv" style="margin-top:6px">${Object.entries(j.opts).map(([k, v]) => `<span>${esc(k)}</span><span>${esc(v)}</span>`).join("")}</div>
        <p class="help" style="margin-top:6px">Hojas en el orden en que salen: ${j.plan.units.map((u) => "[" + u.map((s) => s.map((i) => i + 1).join("+") || "blanca").join(" | ") + "]").join(" ")}</p></details>`;
      const b = $(".btn", d);
      if (b) b.onclick = () => this.cancelJob(j);
      pane.appendChild(d);
    }
  },
  renderInk() {
    const p = this.printers[this.view];
    const pane = $("#tab-ink");
    const key = "ink" + Object.keys(p.ink).map((t) => (p.ink[t]).toFixed(2)).join();
    if (pane.dataset.k === key) return;
    pane.dataset.k = key;
    pane.innerHTML = `<p class="help">${p.def.kind === "inkjet" ? "Depósitos de tinta. Por debajo del 3 % ese color sale pálido; vacío, la impresora se para hasta que lo rellenes y pulses ▷." : "Tóner."} El gasto se calcula con lo que se imprime de verdad en cada cara.</p>`;
    const row = el("div", "tanks");
    for (const t of Object.keys(p.ink)) {
      const lvl = Math.max(0, p.ink[t] / p.def.tanks[t]);
      const d = el("div", "tank");
      d.innerHTML = `<div class="bar"><div style="height:${lvl * 100}%;background:${INK_COLS[t]}"></div></div>
        <strong>${INK_NAMES[t]}</strong><span>${Math.round(lvl * 100)} % · ${p.ink[t].toFixed(1)} ml</span><span class="muted">gastado ${p.inkUsed[t].toFixed(2)} ml</span>
        <div class="acts"><button class="btn sm" data-a="fill">Rellenar</button><button class="btn sm ghost" data-a="low">2 %</button><button class="btn sm ghost" data-a="empty">0</button></div>`;
      d.querySelectorAll("[data-a]").forEach((b) => b.onclick = () => {
        const a = b.dataset.a;
        p.ink[t] = a === "fill" ? p.def.tanks[t] : a === "low" ? p.def.tanks[t] * 0.02 : 0;
        this.log(`${p.name}: ${INK_NAMES[t]} ${a === "fill" ? "rellenado" : a === "low" ? "casi vacío (simulado)" : "vacío (simulado)"}`);
        this.stateChanged();
      });
      row.appendChild(d);
    }
    pane.appendChild(row);
    pane.appendChild(el("p", "help", `Hojas impresas: ${p.sheetsPrinted}`));
  },
  renderFaults() {
    const p = this.printers[this.view];
    const pane = $("#tab-faults");
    const key = ["f", p.name, p.connected, p.paused, p.accepting, !!p.jammed, this.installed.join(), this.defaultPrinter].join("|");
    if (pane.dataset.k === key) return;
    pane.dataset.k = key;
    pane.innerHTML = `<div class="settings-grid">
      <h3>Impresora</h3>
      <label><input type="checkbox" id="f-conn" ${p.connected ? "" : "checked"}> Cable USB / Wi-Fi desconectado</label>
      <div class="row"><button class="btn sm" id="f-jam">Atascar la siguiente hoja</button>
        <label>Probabilidad de atasco <input type="number" id="f-jamp" min="0" max="100" value="${this.jamChance}" style="width:64px"> %</label>
        <button class="btn sm" id="f-clear" ${p.jammed ? "" : "disabled"}>Sacar la hoja atascada</button></div>
      <label>Velocidad <select id="f-speed">${[[1, "real (×1)"], [5, "×5"], [20, "×20"], [0, "instantánea"]].map(([v, t]) => `<option value="${v}" ${this.speed === v ? "selected" : ""}>${t}</option>`).join("")}</select></label>
      <h3 style="margin-top:6px">CUPS</h3>
      <label><input type="checkbox" id="f-pause" ${p.paused ? "checked" : ""}> Cola pausada (cupsdisable)</label>
      <label><input type="checkbox" id="f-reject" ${p.accepting ? "" : "checked"}> La cola no acepta trabajos (cupsreject)</label>
      <label>pdftopdf cuenta page-set sobre <select id="f-pageset"><option value="output" ${this.pageSetMode === "output" ? "selected" : ""}>las caras ya compuestas (supuesto por defecto)</option><option value="input" ${this.pageSetMode === "input" ? "selected" : ""}>las páginas del archivo</option></select></label>
      <label><input type="checkbox" id="f-blank" ${this.evenBlank ? "checked" : ""}> page-set=even añade un reverso en blanco si el total es impar (libcupsfilters ≥ 2.1.1)</label>
      <label>Predeterminada del sistema <select id="f-default"><option value="">ninguna</option>${this.installed.map((n) => `<option ${this.defaultPrinter === n ? "selected" : ""}>${esc(n)}</option>`).join("")}</select></label>
      <div class="row">${this.installed.includes(p.name) ? `<button class="btn sm danger" id="f-uninst">Eliminar la cola ${esc(p.name)}</button>` : `<button class="btn sm" id="f-inst">Instalar ${esc(p.name)}</button>`}
        <button class="btn sm" id="f-restart">Reiniciar la simulación</button>
        <button class="btn sm danger" id="f-reset">Olvidar la configuración recordada</button></div></div>`;
    $("#f-conn").onchange = (e) => { p.connected = !e.target.checked; this.log(`${p.name}: ${p.connected ? "conectada" : "desconectada"}`); this.stateChanged(); };
    $("#f-pause").onchange = (e) => { p.paused = e.target.checked; this.log(`${p.paused ? "cupsdisable" : "cupsenable"} ${p.name}`); this.stateChanged(); };
    $("#f-reject").onchange = (e) => { p.accepting = !e.target.checked; this.log(`${p.accepting ? "cupsaccept" : "cupsreject"} ${p.name}`); this.stateChanged(); };
    $("#f-jam").onclick = () => { this.jamNext = true; this.log("La siguiente hoja se atascará"); };
    $("#f-jamp").onchange = (e) => { this.jamChance = Math.max(0, Math.min(100, +e.target.value || 0)); };
    $("#f-clear").onclick = () => this.clearJam(p);
    $("#f-speed").onchange = (e) => { this.speed = +e.target.value; };
    $("#f-pageset").onchange = (e) => { this.pageSetMode = e.target.value; };
    $("#f-blank").onchange = (e) => { this.evenBlank = e.target.checked; };
    $("#f-default").onchange = (e) => { this.defaultPrinter = e.target.value; this.log(`lpadmin -d ${this.defaultPrinter || "(ninguna)"}`); };
    const u = $("#f-uninst"); if (u) u.onclick = () => this.uninstall(p.name);
    const i = $("#f-inst"); if (i) i.onclick = () => this.install(p.name);
    $("#f-restart").onclick = () => this.reset();
    $("#f-reset").onclick = () => { Config.clear(); this.log("Configuración recordada borrada"); this.renderTech(); };
  },
  renderTable() {
    const pane = $("#tab-table");
    const key = "t" + this.files.length + this.table.map((s) => s.id + ":" + s.sheets.length).join();
    if (pane.dataset.k === key) return;
    pane.dataset.k = key;
    pane.innerHTML = `<p class="help">Lo que dejas sobre la mesa y los PDF guardados. «Comprobar» lee el montón como una persona: la hoja de arriba primero.</p>`;
    for (const f of this.files) {
      const d = el("div", "list-item");
      d.innerHTML = `<div class="list-head"><strong>${esc(f.name)}</strong><button class="btn sm">Abrir</button></div><div class="meta">${f.sheets.length} páginas · ${esc(f.uri)}</div>`;
      $(".btn", d).onclick = () => this.viewPdf(f);
      pane.appendChild(d);
    }
    for (const s of this.table) {
      const d = el("div", "list-item");
      d.innerHTML = `<div class="list-head"><strong>${esc(s.name)}</strong><span class="meta">${s.sheets.length} ${s.sheets.length === 1 ? "hoja" : "hojas"}</span></div>
        <div class="row" style="margin:8px 0 0">
        <button class="btn sm primary" data-a="check">Comprobar</button><button class="btn sm" data-a="book">Leer como libro</button>
        <button class="btn sm" data-a="view">Ver hojas</button><button class="btn sm" data-a="take">Coger</button>
        <button class="btn sm ghost danger" data-a="bin">Tirar</button></div>`;
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
    if (!this.files.length && !this.table.length) pane.appendChild(el("div", "help", "La mesa está vacía."));
  },
  renderTech() {
    const pane = $("#tab-tech");
    if (!pane) return;
    const d = Dialog.current;
    let html = "";
    if (d) {
      const c = d.choice;
      html += `<h3>Elección actual del diálogo (printing.Choice)</h3><div class="kv">${Object.entries({
        printer: c.printer, copies: c.copies, collate: c.collate, orientation: c.orientation, pages: c.pages, ranges_text: c.ranges_text,
        color: c.color, paper: c.paper, number_up: c.number_up, margins: c.margins, duplex: c.duplex,
        driver: Object.entries(c.driver).map(([k, v]) => `${k}=${v}`).join(" "),
      }).map(([k, v]) => `<span>${esc(k)}</span><span>${esc(v)}</span>`).join("")}</div>
      <p class="help" style="margin-top:8px">Dúplex automático: ${Sim.autoDuplex(c.printer) ? "sí" : "no (se ofrece la doble cara manual)"}</p>`;
    }
    if (this.lastResult) {
      const r = this.lastResult;
      html += `<h3 style="margin-top:14px">Última respuesta del diálogo · response ${r.response}</h3>
        <pre class="code">settings (GtkPrintSettings)\n${Object.entries(r.settings).map(([k, v]) => `  ${k} = ${v}`).join("\n")}\n\npage-setup (GtkPageSetup)\n${Object.entries(r.setup).map(([k, v]) => `  ${k} = ${typeof v === "number" ? v.toFixed(2) + " mm" : v}`).join("\n")}</pre>`;
    }
    html += `<h3 style="margin-top:14px">print-portal.ini (simulado)</h3><pre class="code">${esc(Config.ini())}</pre>`;
    if (pane.dataset.k === html) return;
    pane.dataset.k = html;
    pane.innerHTML = html;
  },
  renderLog() {
    const pane = $("#tab-log");
    if (pane) pane.innerHTML = `<div class="log">${this.logLines.map((l) => `<div>${esc(l)}</div>`).join("")}</div>`;
  },

  // ---------------------------------------------------------------- viewers
  modal(title, sub) {
    const box = el("div", "modal-box");
    box.innerHTML = `<div class="modal-head"><div><h2>${esc(title)}</h2>${sub ? `<p class="help" style="margin:2px 0 0">${sub}</p>` : ""}</div><button class="btn sm ghost" data-close>Cerrar</button></div>`;
    $("[data-close]", box).onclick = closeModal;
    return box;
  },
  inspect(sheet) {
    const box = this.modal(`Hoja ${sheet.id}`, `${esc(_(PAPER_LABELS[sheet.size]))} · ${esc(PAPER_TYPES[sheet.type].label)}`);
    const faces = el("div", "faces");
    const up = sheet.pose.up, top = sheet.pose.top;
    const f1 = el("div", "face"); f1.append(faceCanvas(sheet, up, top, 1.5), el("div", "", "Cara de arriba, como la ves"));
    const f2 = el("div", "face"); f2.append(faceCanvas(sheet, other(up), top, 1.5), el("div", "", "Cara de abajo, dándole la vuelta como a un libro"));
    faces.append(f1, f2);
    box.appendChild(faces);
    const notes = [...sheet.faces.A, ...sheet.faces.B].map((L) => L.note).filter(Boolean);
    if (notes.length) box.appendChild(el("p", "help", "Notas: " + esc(notes.join("; "))));
    openModal(box);
  },
  viewSheets(sheets, title) {
    const box = this.modal(title, "De arriba abajo, cada hoja como está.");
    const g = el("div", "sheets");
    sheets.forEach((sh, i) => { const t = this.thumb(sh, String(i + 1), 0.7); t.onclick = () => this.inspect(sh); g.appendChild(t); });
    box.appendChild(g);
    openModal(box);
  },
  showCheck(sheets, title) {
    const r = this.check(sheets);
    const box = this.modal(`Comprobación · ${title}`);
    if (!r.group) { box.appendChild(el("p", "", "No hay nada impreso.")); openModal(box); return; }
    const c = r.group.choice;
    box.appendChild(el("p", "help", `«${esc(r.group.title)}» · ${r.twoSided ? `doble cara, borde ${r.binding === "long" ? "largo" : "corto"}` : "una cara"} · ${c.number_up} por hoja · ${c.orientation === "landscape" ? "horizontal" : "vertical"} · ${r.group.expected.length} caras`));
    const v = el("div", "verdict " + (r.ok ? "ok" : "bad"));
    v.innerHTML = `<strong>${r.ok ? "Todas las páginas están en su sitio y derechas" : "El documento no ha salido bien"}</strong>${r.hint ? `<div class="help" style="margin:4px 0 0">${esc(r.hint)}</div>` : ""}
      <ul>${r.rows.concat(r.issues).map((x) => `<li>${esc(x)}</li>`).join("")}</ul>`;
    box.appendChild(v);
    const b = el("button", "btn primary sm", "Leer como libro");
    b.onclick = () => this.bookViewer(sheets);
    box.appendChild(b);
    openModal(box);
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
      const fc = faceCanvas(sh, front, U, 1.6), bc = faceCanvas(sh, back, backTop, 1.6);
      box.innerHTML = `<div class="modal-head"><div><h2>Leer como libro</h2><p class="help" style="margin:2px 0 0">Hoja ${i + 1} de ${sheets.length}</p></div><button class="btn sm ghost" data-a="close">Cerrar</button></div>
        <div class="row"><label class="field">Encuadernado por el borde <select data-a="bind"><option value="long" ${binding === "long" ? "selected" : ""}>largo</option><option value="short" ${binding === "short" ? "selected" : ""}>corto</option></select></label>
        <button class="btn sm" data-a="prev">Anterior</button><button class="btn sm primary" data-a="flip">Pasar la hoja</button><button class="btn sm" data-a="next">Siguiente</button></div>`;
      const stage = el("div", "flipper");
      const card = el("div", "flip-card");
      card.style.width = Math.max(fc.width, bc.width) + "px"; card.style.height = Math.max(fc.height, bc.height) + "px";
      bc.style.transform = aroundVertical ? "rotateY(180deg)" : "rotateX(180deg)";
      card.append(fc, bc);
      if (flipped) card.style.transform = aroundVertical ? "rotateY(-180deg)" : "rotateX(180deg)";
      stage.appendChild(card);
      box.appendChild(stage);
      $('[data-a="close"]', box).onclick = closeModal;
      $('[data-a="bind"]', box).onchange = (e) => { binding = e.target.value; flipped = false; draw(); };
      $('[data-a="prev"]', box).onclick = () => { if (i > 0) { i--; flipped = false; draw(); } };
      $('[data-a="next"]', box).onclick = () => { if (i < sheets.length - 1) { i++; flipped = false; draw(); } };
      $('[data-a="flip"]', box).onclick = () => {
        flipped = !flipped;
        card.style.transform = flipped ? (aroundVertical ? "rotateY(-180deg)" : "rotateX(180deg)") : "none";
      };
    };
    draw();
    openModal(box);
  },
  viewPdf(f) {
    const box = this.modal(f.name, esc(f.uri));
    const g = el("div", "sheets");
    const c = f.group.choice;
    const choice = new Choice({ orientation: c.orientation, paper: c.paper, number_up: c.number_up, color: true, margins: c.margins });
    f.sheets.forEach((pages, i) => {
      const [sw, sh] = choice.sheet_mm();
      const cv = el("canvas");
      cv.width = Math.round(sw * 1.2); cv.height = Math.round(sh * 1.2);
      drawSheet(cv.getContext("2d"), choice, cv.width, cv.height, pages, f.group.doc, M.PREVIEW_LIGHT, false);
      const w = el("div", "sheet-thumb"); w.append(cv, el("span", "", String(i + 1)));
      g.appendChild(w);
    });
    box.appendChild(g);
    openModal(box);
  },
});

// ------------------------------------------------------------------ start
const SHOT = new URLSearchParams(location.search);
if (SHOT.has("shot")) document.body.classList.add("shot");
Theme.dark = SHOT.get("theme") === "dark" || (!SHOT.has("shot") && matchMedia("(prefers-color-scheme: dark)").matches);
document.querySelectorAll("#sim-theme button").forEach((b) => b.classList.toggle("on", (b.dataset.v === "dark") === Theme.dark));
Theme.apply();
Sim.init();
if (SHOT.has("shot")) Sim.speed = 0;
Sim.setDoc(SHOT.get("doc") || "text").then(() => {
  Sim.openDialog();
  const d = Dialog.current;
  if (SHOT.has("shot")) {
    d.root.classList.remove("fv");
    document.activeElement.blur();
    if (SHOT.get("page") === "more") { d.morePage.style.transition = d.mainPage.style.transition = "none"; d.root.classList.add("show-more"); }
  }
});
Sim.log("Listo. ET-2710-Series instalada en CUPS, sin impresora predeterminada del sistema.");
