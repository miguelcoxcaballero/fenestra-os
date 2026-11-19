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
function howtoHTML(topPage, lastAside) {
  const n = topPage ? String(topPage) : "";
  const steps = [
    ["Saca todas las hojas impresas de la bandeja de salida, sin cambiar su orden.",
      `<div class="scene s-lift"><div class="tray-out"></div><div class="pg b"><div class="lines"></div></div><div class="pg"><div class="lines"></div><div class="n">${n}</div></div></div>`],
    ["Dale la vuelta al montón como a la página de un libro: lo impreso queda hacia abajo.",
      `<div class="scene s-flip"><div class="axis"></div><div class="card3d"><div class="pg"><div class="top"></div><div class="lines"></div><div class="n">${n}</div></div><div class="pg back blankface"><div class="top"></div></div></div></div>`],
    ["Ponlo en la bandeja trasera como el papel en blanco: la parte de arriba entra primero.",
      `<div class="scene s-load"><div class="hint">arriba ↓ primero</div><div class="tray-rear"></div><div class="body"></div><div class="arrow"></div><div class="pg blankface"><div class="top"></div></div></div>`],
  ];
  return `<div class="howto">${steps.map(([cap, scene], i) =>
    `<div class="howto-step${i === 0 ? " hi" : ""}">${scene}<div class="cap"><span class="num">${i + 1}</span><span>${esc(cap)}</span></div></div>`).join("")}</div>
    ${lastAside ? `<div class="note-line">La última hoja no lleva nada detrás: déjala en el montón, la impresora la pasará sin imprimir.</div>` : ""}`;
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
      if (p && (p.busy || p.wait)) { this.live(); if (Sim.guide) Sim.guide.progress(p); }
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  },

  // ---------------------------------------------------------------- the drawing
  svg(p) {
    const blink = Math.floor(performance.now() / 450) % 2 === 0;
    const led = (on, col, b) => (on && (!b || blink) ? col : "#4a4f57");
    const printing = p.feeding && p.anim === "print";
    const stackH = (n, max) => Math.max(0, Math.min(max, n * max / p.def.capacity * 2.2));
    const tint = (s) => (s ? (PAPER_TYPES[s.type] || PAPER_TYPES.plain).tint : "#fff");
    if (p.def.kind === "laser") {
      const lvl = p.ink.K / p.def.tanks.K;
      return `<svg viewBox="0 0 560 220" role="img" aria-label="Impresora láser">
        <defs><linearGradient id="lz" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#eef0f3"/><stop offset="1" stop-color="#cfd3d9"/></linearGradient></defs>
        <ellipse cx="280" cy="206" rx="200" ry="8" fill="rgba(0,0,0,.12)"/>
        <rect x="110" y="44" width="340" height="156" rx="14" fill="url(#lz)" stroke="#aeb3ba"/>
        <path d="M150 44 L170 22 L390 22 L410 44 Z" fill="#dde1e6" stroke="#aeb3ba"/>
        ${p.out.length ? `<rect x="190" y="${18 - stackH(p.out.length, 10)}" width="180" height="${4 + stackH(p.out.length, 10)}" fill="${tint(p.out[0])}" stroke="#bbb"/>` : ""}
        <rect x="130" y="150" width="300" height="40" rx="6" fill="#d6d9de" stroke="#a9adb4"/>
        <rect x="250" y="166" width="60" height="7" rx="3.5" fill="#9aa0a7"/>
        <rect x="140" y="64" width="120" height="44" rx="5" fill="#1d2a22"/>
        <text x="150" y="84" font-size="12" fill="#7cf29b" font-family="Segoe UI, sans-serif">${p.power ? (p.wait ? "Error" : p.feeding ? "Imprimiendo" : "Lista") : ""}</text>
        <text x="150" y="100" font-size="11" fill="#7cf29b" font-family="Segoe UI, sans-serif">${p.power ? `Tóner ${Math.round(lvl * 100)} %` : ""}</text>
        <circle cx="290" cy="86" r="6" fill="${led(p.power, "#3fd35f", p.feeding)}"/>
        <circle cx="312" cy="86" r="6" fill="${led(p.power && p.wait, "#ff9e3d", true)}"/>
        ${p.jammed ? `<g><rect x="210" y="118" width="140" height="26" rx="13" fill="#c42b1c"/><text x="280" y="135" text-anchor="middle" font-size="12" font-weight="600" fill="#fff" font-family="Segoe UI, sans-serif">Atasco de papel</text></g>` : ""}
        ${!p.power ? `<rect x="110" y="44" width="340" height="156" rx="14" fill="rgba(0,0,0,.28)"/>` : ""}
      </svg>`;
    }
    const tankCol = { C: "#00a3e0", M: "#e0007a", Y: "#ffd400", K: "#26282c" };
    const tanks = Object.keys(p.def.tanks).map((t, i) => {
      const lvl = Math.max(0, p.ink[t] / p.def.tanks[t]);
      const x = 404 + i * 16, h = 48 * lvl;
      return `<rect x="${x}" y="112" width="11" height="52" rx="2" fill="#1f2226" stroke="#5a606a"/>
        <rect x="${x + 1.5}" y="${162.5 - h}" width="8" height="${h}" rx="1" fill="${tankCol[t]}"/>`;
    }).join("");
    const t = performance.now();
    const headX = printing ? 140 + (Math.sin(t / 140) + 1) / 2 * 190 : 150;
    const inH = stackH(p.tray.length, 26), outH = stackH(p.out.length, 12);
    const feedP = p.feeding && p.anim === "feed" ? Math.min(1, (t - p.animAt) / 400) : 0;
    const outP = p.anim === "out" ? Math.min(1, (t - p.animAt) / 450) : 1;
    return `<svg viewBox="0 0 560 220" role="img" aria-label="Impresora de tinta con alimentador trasero">
      <defs>
        <linearGradient id="bd" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#4f5560"/><stop offset="1" stop-color="#30343b"/></linearGradient>
        <linearGradient id="lid" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#5d646f"/><stop offset="1" stop-color="#474d56"/></linearGradient>
      </defs>
      <ellipse cx="280" cy="206" rx="210" ry="8" fill="rgba(0,0,0,.14)"/>
      <!-- rear sheet feeder, paper standing in it -->
      <path d="M160 86 L182 14 L378 14 L400 86 Z" fill="#c9ced5" stroke="#a5abb3"/>
      ${p.tray.length ? `<path d="M174 86 L${193 - inH * .1} ${22 - inH * .2} L${367 + inH * .1} ${22 - inH * .2} L386 86 Z" fill="${tint(p.tray[0])}" stroke="#c9ccd1"/>
        <path d="M174 86 L193 22 L367 22 L386 86" fill="none" stroke="#d9dce0" stroke-width="${Math.max(1, inH / 4)}" opacity=".7"/>` : ""}
      ${feedP > 0 ? `<rect x="196" y="${70 + feedP * 18}" width="168" height="6" fill="${tint(p.feeding)}" opacity=".9"/>` : ""}
      <!-- body -->
      <rect x="90" y="80" width="380" height="104" rx="18" fill="url(#bd)"/>
      <rect x="90" y="80" width="380" height="30" rx="18" fill="url(#lid)"/>
      <rect x="112" y="122" width="270" height="44" rx="6" fill="#1b1e22"/>
      <rect x="${headX}" y="128" width="44" height="22" rx="4" fill="#6b7380" stroke="#8d94a0"/>
      ${printing ? `<rect x="${headX + 6}" y="152" width="32" height="2" fill="${blink ? "#4cc2ff" : "#ffffff"}" opacity=".8"/>` : ""}
      <!-- panel -->
      <circle cx="112" cy="95" r="6" fill="${led(p.power, "#3fd35f", printing)}"/>
      <circle cx="132" cy="95" r="4" fill="${led(p.power && p.connected, "#4cc2ff")}"/>
      <circle cx="150" cy="95" r="4" fill="${led(p.power && (p.wait === "paper" || p.wait === "jam"), "#ff9e3d", p.wait === "jam")}"/>
      <circle cx="168" cy="95" r="4" fill="${led(p.power && p.wait === "ink", "#ff9e3d", true)}"/>
      <text x="182" y="99" font-size="10" fill="#c9ced6" font-family="Segoe UI, sans-serif">Wi-Fi · papel · tinta</text>
      ${tanks}
      <!-- output tray -->
      <path d="M150 184 L132 200 L428 200 L410 184 Z" fill="#5a606a"/>
      ${p.out.length ? `<path d="M170 ${186 - outH} L156 ${197 - outH} L404 ${197 - outH} L390 ${186 - outH} Z" fill="${tint(p.out[0])}" stroke="#c9ccd1" opacity="${outP}"/>` : ""}
      ${p.jammed ? `<g><rect x="200" y="132" width="150" height="26" rx="13" fill="#c42b1c"/><text x="275" y="149" text-anchor="middle" font-size="12" font-weight="600" fill="#fff" font-family="Segoe UI, sans-serif">Atasco de papel</text></g>` : ""}
      ${!p.power ? `<rect x="90" y="80" width="380" height="104" rx="18" fill="rgba(0,0,0,.3)"/>` : ""}
    </svg>`;
  },

  // ---------------------------------------------------------------- updates
  live() {
    const p = Sim.printers[Sim.view];
    $("#tw-svg").innerHTML = this.svg(p);
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
        howtoHTML(top ? top.pages[0] + 1 : "", g.sides % 2 === 1) +
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
