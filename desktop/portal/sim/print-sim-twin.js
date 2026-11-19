// SPDX-License-Identifier: GPL-3.0-or-later
// The digital twin of the printer: what it is doing right now, where every sheet is (rear tray,
// under the print head, output tray), the steps of the job, and what the person has to do next,
// with the same illustrations as the two-sided guide.
"use strict";

const ICON = {
  power: '<svg viewBox="0 0 16 16"><path d="M7.25 1h1.5v7h-1.5zM4.3 3.2l1 1.1A4.75 4.75 0 1 0 10.7 4.3l1-1.1A6.25 6.25 0 1 1 4.3 3.2z"/></svg>',
  play: '<svg viewBox="0 0 16 16"><path d="M4 2.5v11l9-5.5z"/></svg>',
  stop: '<svg viewBox="0 0 16 16"><rect x="3" y="3" width="10" height="10" rx="1.5"/></svg>',
  warn: '<svg viewBox="0 0 16 16"><path d="M8 1 15.5 14.5H.5zm-.75 5v4.5h1.5V6zm0 5.75v1.5h1.5v-1.5z"/></svg>',
  info: '<svg viewBox="0 0 16 16"><path d="M8 1a7 7 0 1 1 0 14A7 7 0 0 1 8 1zm-.75 6v5h1.5V7zm0-2.75v1.5h1.5v-1.5z"/></svg>',
  ok: '<svg viewBox="0 0 16 16"><path d="M8 1a7 7 0 1 1 0 14A7 7 0 0 1 8 1zm3.2 4.2L7 9.4 4.8 7.2 3.7 8.3 7 11.6l5.3-5.3z"/></svg>',
  flip: '<svg viewBox="0 0 16 16"><path d="M8 1.5A6.5 6.5 0 0 0 2.2 5H.5l2.5 3 2.5-3H3.9A5 5 0 0 1 13 7h1.5A6.5 6.5 0 0 0 8 1.5zM13 8l-2.5 3h1.6A5 5 0 0 1 3 9H1.5a6.5 6.5 0 0 0 12.3 2h1.7z"/></svg>',
};

// The three "how to turn the stack over" pictures, shared by the twin and the guide.
const SCENE_DEFS = `<defs>
  <linearGradient id="hs-metal" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#5a626f"/><stop offset="1" stop-color="#363b44"/></linearGradient>
  <linearGradient id="hs-tray" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#2f343c"/><stop offset="1" stop-color="#4a505a"/></linearGradient>
  <linearGradient id="hs-feeder" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#cfd5dc"/><stop offset="1" stop-color="#e6e9ed"/></linearGradient>
  <pattern id="hs-text" width="60" height="6" patternUnits="userSpaceOnUse"><rect width="60" height="6" fill="#fff"/><rect y="2" width="46" height="1.6" rx=".8" fill="#a3a9b2"/></pattern>
  <marker id="hs-arrow" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 z" fill="var(--accent)"/></marker>
</defs>`;
function sceneSVG(kind, n) {
  const sheet = (dy, top) => `<path d="M52 ${70 + dy} H148 L160 ${92 + dy} H40 Z" fill="${top ? "url(#hs-text)" : "#f3f4f6"}" stroke="#c3c8cf" stroke-width=".8"/>`;
  if (kind === "lift") {
    return `<svg viewBox="0 0 200 120" aria-hidden="true">${SCENE_DEFS}
      <rect x="22" y="8" width="156" height="40" rx="10" fill="url(#hs-metal)"/><rect x="48" y="40" width="104" height="4" rx="2" fill="#111"/>
      <path d="M44 74 H156 L174 106 Q175 109 171 109 H29 Q25 109 26 106 Z" fill="url(#hs-tray)"/>
      <g class="anim-lift">${sheet(6)}${sheet(3)}${sheet(0, true)}
        <text x="100" y="86" text-anchor="middle" font-size="13" font-weight="700" fill="#1b1b1b" font-family="Segoe UI Variable Text, Segoe UI, sans-serif">${n}</text></g>
      <path class="anim-arrow" d="M170 72 C 184 56, 182 34, 166 22" fill="none" stroke="var(--accent)" stroke-width="2.4" stroke-linecap="round" marker-end="url(#hs-arrow)"/>
    </svg>`;
  }
  if (kind === "load") {
    return `<svg viewBox="0 0 200 120" aria-hidden="true">${SCENE_DEFS}
      <path d="M118 66 L150 8 Q152 5 155 6 L164 10 Q167 12 165 15 L136 68 Z" fill="url(#hs-feeder)" stroke="#a6aeb8" stroke-width=".8"/>
      <g class="anim-load"><g transform="translate(136 30) rotate(28)">
        <rect x="-2.8" y="-34" width="5.6" height="62" rx="1.2" fill="#fff" stroke="#c3c8cf" stroke-width=".8"/>
        <rect x="1.4" y="-34" width="1.6" height="62" fill="#a3a9b2"/>
        <rect x="-2.8" y="22" width="5.6" height="6" rx="1" fill="var(--accent)"/></g></g>
      <rect x="40" y="62" width="112" height="44" rx="10" fill="url(#hs-metal)"/>
      <rect x="40" y="62" width="112" height="10" rx="5" fill="#69717f"/>
      <path d="M40 94 L12 104 Q8 106 12 107 L40 104 Z" fill="url(#hs-tray)"/>
      <path d="M110 40 C 116 44, 120 50, 122 58" fill="none" stroke="var(--accent)" stroke-width="2.4" stroke-linecap="round" marker-end="url(#hs-arrow)"/>
      <text x="8" y="16" font-size="10.5" font-weight="600" fill="var(--accent)" font-family="Segoe UI Variable Text, Segoe UI, sans-serif">Arriba, primero</text>
      <text x="8" y="30" font-size="10" fill="currentColor" opacity=".7" font-family="Segoe UI Variable Text, Segoe UI, sans-serif">lo impreso, hacia atrás</text>
    </svg>`;
  }
  return "";
}
function howtoHTML(topPage) {
  const n = topPage ? String(topPage) : "";
  const flip = `<div class="scene s-flip">
      <svg class="flip-arc" viewBox="0 0 200 120" aria-hidden="true">${SCENE_DEFS}<path d="M128 22 C 112 4, 84 4, 70 20" fill="none" stroke="var(--accent)" stroke-width="2.4" stroke-linecap="round" marker-end="url(#hs-arrow)"/></svg>
      <div class="landing"></div>
      <div class="leaf"><div class="face front"><i class="band"></i><b>${n}</b><i class="lines"></i></div><div class="face back"><span>en blanco</span></div></div>
    </div>`;
  const steps = [
    ["Saca todas las hojas impresas de la bandeja de salida, sin cambiar su orden.", `<div class="scene">${sceneSVG("lift", n)}</div>`],
    ["Dale la vuelta al montón como a la página de un libro: lo impreso queda hacia abajo.", flip],
    ["Ponlo en la bandeja trasera como el papel en blanco: la parte de arriba entra primero.", `<div class="scene">${sceneSVG("load", n)}</div>`],
  ];
  return `<div class="howto">${steps.map(([cap, scene], i) =>
    `<div class="howto-step${i === 0 ? " hi" : ""}">${scene}<div class="cap"><span class="num">${i + 1}</span><span>${esc(cap)}</span></div></div>`).join("")}</div>`;
}
// highlight the step whose picture is playing (the animations last 3.2 s)
setInterval(() => {
  document.querySelectorAll(".howto").forEach((h) => {
    const s = [...h.children];
    const i = s.findIndex((x) => x.classList.contains("hi"));
    s.forEach((x, k) => x.classList.toggle("hi", k === (i + 1) % s.length));
  });
}, 3200);

const Twin = {
  cache: {},
  mount() {
    const root = $("#twin");
    root.innerHTML = `
      <div class="twin-art"><div id="tw-svg"></div>
        <div class="twin-controls">
          <button class="icon-btn" id="tw-power" title="Encender o apagar">${ICON.power}</button>
          <button class="icon-btn" id="tw-go" title="Botón de reanudar / papel">${ICON.play}</button>
          <button class="icon-btn stop" id="tw-stop" title="Botón de parar: cancela el trabajo">${ICON.stop}</button>
        </div></div>
      <div class="flow">
        <div class="zone"><div class="zone-title">Bandeja trasera <b id="tw-in-n"></b></div><div class="stack" id="tw-in"></div><div class="zone-note" id="tw-in-note"></div></div>
        <div class="zone head-zone"><div class="zone-title">Cabezal <b id="tw-head-pct"></b></div><div class="sheet-live idle" id="tw-live"><div class="ink"></div><div class="lbl"></div></div><div class="zone-note" id="tw-head-note"></div><div class="progress"><div id="tw-job-bar" style="width:0"></div></div></div>
        <div class="zone"><div class="zone-title">Bandeja de salida <b id="tw-out-n"></b></div><div class="stack" id="tw-out"></div><div class="zone-note" id="tw-out-note"></div></div>
      </div>
      <div class="timeline" id="tw-timeline"></div>
      <div id="tw-callout"></div>
      <div class="hands" id="hands"></div>`;
    const cur = () => Sim.printers[Sim.view];
    $("#tw-power").onclick = () => { const q = cur(); q.power = !q.power; Sim.log(`${q.name}: ${q.power ? "encendida" : "apagada"}`); Sim.stateChanged(); if (q.power) Sim.schedule(); };
    $("#tw-go").onclick = () => Sim.pressButton(cur(), false);
    $("#tw-stop").onclick = () => Sim.pressButton(cur(), true);
    this.loop();
  },
  loop() {
    const tick = () => {
      const p = Sim.printers[Sim.view];
      if (p) this.drawArt(p);
      if (p && (p.busy || p.wait)) this.live();
      if (Sim.guide) Sim.guide.progress(Sim.printers[Sim.guide.group.choice.printer]);
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  },

  // ---------------------------------------------------------------- updates
  live() {
    const p = Sim.printers[Sim.view];
    this.drawArt(p);
    const live = $("#tw-live");
    const cur = p.current;
    live.classList.toggle("idle", !p.feeding);
    const pct = p.feeding && p.anim === "print" ? Math.round((p.progress || 0) * 100) : 0;
    $(".ink", live).style.height = pct + "%";
    $(".lbl", live).textContent = cur && p.feeding ? (cur.pages.length ? "p. " + cur.pages.map((i) => i + 1).join("+") : "en blanco") : "";
    $("#tw-head-pct").textContent = p.feeding ? pct + " %" : "";
    let note;
    if (!p.power) note = "Apagada";
    else if (p.wait) note = `<b>${esc(this.waitText(p))}</b>`;
    else if (p.feeding && cur) note = `Imprimiendo ${cur.back ? "el reverso" : "la cara"} ${cur.pages.length ? "con la página " + cur.pages.map((i) => i + 1).join("+") : "en blanco"}`;
    else if (p.busy) note = "Preparando el trabajo…";
    else note = "Esperando trabajos";
    $("#tw-head-note").innerHTML = note;
    const job = Sim.jobs.find((j) => j.printer === p.name && j.state === "processing");
    $("#tw-job-bar").style.width = job ? Math.round((job.done + (p.feeding ? p.progress || 0 : 0)) / job.plan.units.length * 100) + "%" : "0";
    this.pill(p);
  },
  drawArt(p) {
    if (!this.art || this.artFor !== p.name) {
      this.art = new PrinterArt($("#tw-svg"), p.def.kind);
      this.artFor = p.name;
    }
    this.art.update(p, Sim);
  },
  waitText(p) {
    return { paper: "Sin papel", jam: "Atasco de papel", ink: "Falta tinta" }[p.wait] || "";
  },
  pill(p) {
    const pill = $("#twin-pill");
    let cls = "", txt = "Lista";
    const st = Sim.cupsState(p.name);
    if (!Sim.installed.includes(p.name)) { cls = "off"; txt = "No instalada"; }
    else if (!p.power) { cls = "off"; txt = "Apagada"; }
    else if (st.problem) { cls = "bad"; txt = p.wait ? this.waitText(p) : st.state.replace(/\.$/, ""); }
    else if (Sim.lastGroup && Sim.lastGroup.stage === "fronts" && Sim.lastGroup.front.state === "completed" && Sim.lastGroup.choice.printer === p.name) { cls = "warn"; txt = "Acción necesaria"; }
    else if (p.busy) { cls = "busy"; txt = "Imprimiendo"; }
    pill.className = "pill " + cls;
    pill.textContent = txt;
  },
  // a stack with its top sheet drawn as it lies (only redrawn when it changes)
  stack(id, sheets, label) {
    const box = $("#" + id);
    const top = sheets[0];
    const key = top ? `${top.id}:${top.pose.up}${top.pose.top}:${top.faces.A.length}${top.faces.B.length}:${sheets.length}` : "empty";
    if (this.cache[id] === key) return;
    this.cache[id] = key;
    box.innerHTML = "";
    box.classList.toggle("empty", !top);
    const n = Math.min(4, Math.max(0, sheets.length - 1));
    for (let i = n; i >= 1; i--) {
      const g = el("div", "ghost");
      g.style.transform = `translate(${i * 2.5}px, ${i * 2.5}px)`;
      box.appendChild(g);
    }
    if (!top) { box.appendChild(el("div", "blank")); return; }
    const c = faceCanvas(top, top.pose.up, top.pose.top, 0.4);
    box.appendChild(c);
    if (label) c.title = label;
  },
  topDesc(sheets) {
    const s = sheets[0];
    if (!s) return "";
    const up = s.faces[s.pose.up], down = s.faces[other(s.pose.up)];
    const pg = (L) => L.map((x) => x.pages.map((i) => i + 1).join("+")).join(" y ");
    if (up.length) return `Arriba se ve la página <b>${pg(up)}</b>`;
    if (down.length) return `Cara en blanco arriba · detrás la página <b>${pg(down)}</b>`;
    return "Papel en blanco";
  },
  update() {
    if (!$("#tw-svg")) return;
    const p = Sim.printers[Sim.view];
    $("#ph-model").textContent = p.def.model;
    this.live();
    this.stack("tw-in", p.tray);
    this.stack("tw-out", p.out);
    $("#tw-in-n").textContent = p.tray.length ? `${p.tray.length}` : "vacía";
    $("#tw-out-n").textContent = p.out.length ? `${p.out.length}` : "vacía";
    $("#tw-in-note").innerHTML = p.tray.length ? `Entra primero: ${this.topDesc(p.tray)}` : "<b>Sin papel</b>";
    $("#tw-out-note").innerHTML = p.out.length ? `${this.topDesc(p.out)} · ${p.def.faceUp ? "boca arriba" : "boca abajo"}` : "Vacía";
    this.timeline(p);
    this.callout(p);
    this.hands(p);
  },

  activeGroup(p) {
    const lg = Sim.lastGroup;
    if (lg && lg.front && lg.choice.printer === p.name && lg.stage !== "cancelled" && !(lg.back && lg.back.state === "completed" && !p.out.length)) return lg;
    const j = [...Sim.jobs].reverse().find((x) => x.printer === p.name && (x.state === "processing" || x.state === "pending"));
    return j ? j.group : null;
  },
  timeline(p) {
    const box = $("#tw-timeline");
    const g = this.activeGroup(p);
    if (!g) { box.innerHTML = ""; box.style.display = "none"; return; }
    box.style.display = "";
    const prog = (j) => (j ? `${Math.min(j.done, j.plan.units.length)} de ${j.plan.units.length} hojas` : "—");
    let steps;
    if (g.front) {
      const fDone = g.front.state === "completed", bDone = g.back && g.back.state === "completed";
      steps = [
        ["Caras delanteras", prog(g.front), fDone ? "done" : "now"],
        ["Dar la vuelta", fDone ? (g.stage === "fronts" ? "Te toca a ti" : "Hecho") : "Cuando terminen", g.stage === "fronts" ? (fDone ? "now action" : "") : "done"],
        ["Reversos", g.back ? prog(g.back) : "Pendiente", bDone ? "done" : g.back ? "now" : ""],
        ["Recoger", bDone ? "Listo" : "", bDone ? "now" : ""],
      ];
    } else {
      const j = [...Sim.jobs].reverse().find((x) => x.group === g);
      const done = j && j.state === "completed";
      steps = [["En cola", j ? `${j.printer}-${j.id}` : "", "done"], ["Imprimiendo", prog(j), done ? "done" : "now"], ["Recoger", done ? "Listo" : "", done ? "now" : ""]];
    }
    box.innerHTML = steps.map(([t, s, c]) => `<div class="tl-step ${c}"><b>${esc(t)}</b><span>${esc(s)}</span></div>`).join("");
  },
  callout(p) {
    const box = $("#tw-callout");
    const g = Sim.lastGroup && Sim.lastGroup.front ? Sim.lastGroup : null;
    let key, html;
    const head = (cls, icon, title, text) => `<div class="callout ${cls}"><div class="callout-head">${icon}<div><strong>${esc(title)}</strong>${text ? `<span>${text}</span>` : ""}</div></div>`;
    if (!Sim.installed.includes(p.name)) {
      key = "uninst"; html = head("info", ICON.info, "Esta impresora no está instalada en CUPS", "El diálogo no la muestra hasta que la instales.") + `<div class="acts"><button class="btn sm primary" data-a="install">Instalar</button></div></div>`;
    } else if (!p.power) {
      key = "off"; html = head("info", ICON.info, "La impresora está apagada", "Los trabajos esperan en la cola de CUPS.") + `<div class="acts"><button class="btn sm primary" data-a="power">Encender</button></div></div>`;
    } else if (!p.connected) {
      key = "conn"; html = head("bad", ICON.warn, "Sin conexión con la impresora", "CUPS espera a que vuelva a estar disponible.") + `<div class="acts"><button class="btn sm primary" data-a="connect">Reconectar</button></div></div>`;
    } else if (p.wait === "paper") {
      key = "paper" + p.tray.length; html = head("bad", ICON.warn, "Sin papel", "Carga papel en la bandeja trasera y pulsa el botón ▷ de la impresora.") + `<div class="acts"><button class="btn sm" data-a="paper">Cargar 20 hojas A4</button><button class="btn sm primary" data-a="go" ${p.tray.length ? "" : "disabled"}>Pulsar ▷</button></div></div>`;
    } else if (p.wait === "jam") {
      key = "jam" + !!p.jammed; html = head("bad", ICON.warn, "Atasco de papel", "Saca con cuidado la hoja atascada y pulsa ▷. La página se vuelve a imprimir.") + `<div class="acts"><button class="btn sm" data-a="clear" ${p.jammed ? "" : "disabled"}>Sacar la hoja atascada</button><button class="btn sm primary" data-a="go" ${p.jammed ? "disabled" : ""}>Pulsar ▷</button></div></div>`;
    } else if (p.wait === "ink") {
      key = "ink"; html = head("bad", ICON.warn, "Se ha acabado la tinta", "Rellena el depósito vacío y pulsa ▷.") + `<div class="acts"><button class="btn sm" data-a="refill">Rellenar los depósitos vacíos</button><button class="btn sm primary" data-a="go">Pulsar ▷</button></div></div>`;
    } else if (g && g.choice.printer === p.name && g.stage === "fronts" && g.front.state === "completed") {
      const top = p.out[0] && p.out[0].faces[p.out[0].pose.up][0];
      key = "flip" + p.out.length + !!Sim.hands;
      html = head("action", ICON.flip, "Ahora te toca: dale la vuelta a las hojas",
        `Las caras delanteras han terminado (${g.front.plan.units.length} hojas). Hazlo así y luego pulsa <b>Continuar</b> en la ventana de doble cara.`) +
        howtoHTML(top ? top.pages[0] + 1 : "") + (g.sides % 2 === 1 ? `<div class="callout-note">${ICON.info}<span>La última hoja no lleva nada detrás: déjala en el montón, la impresora la pasará sin imprimir.</span></div>` : "") +
        `<div class="acts"><button class="btn sm primary" data-a="auto">Hacerlo en la simulación</button></div></div>`;
    } else if (g && g.choice.printer === p.name && g.back && g.back.state === "completed") {
      key = "done" + p.out.length;
      html = head("ok", ICON.ok, "Documento terminado", "Recoge las hojas y dales la vuelta como a un libro: la página 1 queda arriba.") + `<div class="acts"><button class="btn sm primary" data-a="collect" ${p.out.length ? "" : "disabled"}>Recoger y comprobar</button></div></div>`;
    } else {
      key = ""; html = "";
    }
    if (this.cache.callout === key) return;
    this.cache.callout = key;
    box.innerHTML = html;
    box.querySelectorAll("[data-a]").forEach((b) => b.onclick = () => this.act(p, b.dataset.a));
  },
  act(p, a) {
    if (a === "install") Sim.install(p.name);
    if (a === "power") { p.power = true; Sim.log(`${p.name}: encendida`); Sim.schedule(); }
    if (a === "connect") { p.connected = true; Sim.log(`${p.name}: conectada`); }
    if (a === "paper") Sim.addPaper(p, "iso_a4", "plain", 20);
    if (a === "go") Sim.pressButton(p, false);
    if (a === "clear") Sim.clearJam(p);
    if (a === "refill") { for (const t of Object.keys(p.ink)) if (p.ink[t] <= 0) p.ink[t] = p.def.tanks[t]; Sim.log(`${p.name}: depósitos rellenados`); }
    if (a === "auto") Sim.doTurnOver(p);
    if (a === "collect") Sim.collect(p);
    Sim.stateChanged();
  },
  hands(p) {
    const box = $("#hands");
    const h = Sim.hands;
    const key = h ? h.sheets.map((s) => s.id + s.pose.up + s.pose.top).join(",") + p.name : "";
    if (this.cache.hands === key) return;
    this.cache.hands = key;
    if (!h) { box.innerHTML = ""; return; }
    const desc = (s) => this.topDesc([s]).replace(/<\/?b>/g, "");
    box.innerHTML = `<div class="callout info"><div class="callout-head">${ICON.info}<div><strong>Tienes ${h.sheets.length} ${h.sheets.length === 1 ? "hoja" : "hojas"} en la mano</strong>
      <span>Arriba: ${esc(desc(h.sheets[0]))}. Abajo: ${esc(desc(h.sheets[h.sheets.length - 1]))}.</span></div></div>
      <div class="acts">
        <button class="btn sm" data-op="book">Dar la vuelta como un libro</button>
        <button class="btn sm" data-op="notepad">Como un bloc</button>
        <button class="btn sm" data-op="rotate">Girar 180°</button>
        <button class="btn sm" data-op="top-aside">Apartar la de arriba</button>
        <button class="btn sm" data-op="bottom-aside">Apartar la de abajo</button>
        <button class="btn sm ghost" data-op="view">Ver las hojas</button>
      </div>
      <div class="acts">
        <button class="btn sm primary" data-load="replace">Cargar en la bandeja</button>
        <button class="btn sm" data-load="front">Cargar delante del papel</button>
        <button class="btn sm" data-load="back">Cargar detrás del papel</button>
        <button class="btn sm" data-op="table">Dejar en la mesa</button>
      </div></div>`;
    box.querySelectorAll("[data-op]").forEach((b) => b.onclick = () => {
      const op = b.dataset.op;
      if (op === "view") Sim.viewSheets(h.sheets, "En tu mano (de arriba abajo)");
      else if (op === "table") Sim.handsPutDown();
      else Sim.handsDo(op);
    });
    box.querySelectorAll("[data-load]").forEach((b) => b.onclick = () => Sim.handsLoad(p, b.dataset.load));
  },
};
