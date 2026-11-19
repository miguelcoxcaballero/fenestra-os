// SPDX-License-Identifier: GPL-3.0-or-later
// Guided manual two-sided printing (web version of dialog.py's ManualDuplexWindow): a window in the
// print dialog's style that follows the job — fronts printing, turning the stack over (illustrated),
// backs printing, done with a check of the result. Continue only once the fronts are out.
"use strict";

class DuplexGuide {
  constructor(group, cb) {
    this.group = group;
    this.cb = cb;
    this.win = el("div", "guide");
    this.win.setAttribute("role", "dialog");
    this.win.setAttribute("aria-modal", "true");
    const layer = $("#overlay");
    document.querySelectorAll("#overlay .guide").forEach((w) => w.remove());
    layer.appendChild(this.win);
    this.key = null;
    this.render();
    this.place();
    this.win.addEventListener("keydown", (e) => { if (e.key === "Escape") this.cancel(); });
  }
  place() {
    const layer = $("#overlay");
    this.win.style.left = Math.max(8, (layer.offsetWidth - this.win.offsetWidth) / 2) + "px";
    this.win.style.top = Math.max(8, (layer.offsetHeight - this.win.offsetHeight) / 2) + "px";
  }
  stage() {
    const g = this.group;
    if (g.stage === "cancelled") return "cancelled";
    if (g.stage === "fronts") return g.front.state === "completed" ? "turn" : (g.front.state === "canceled" ? "failed" : "fronts");
    if (g.back && g.back.state === "completed") return "done";
    if (g.back && g.back.state === "canceled") return "failed";
    return "backs";
  }
  update() {
    const s = this.stage();
    const g = this.group;
    const p = Sim.printers[g.choice.printer];
    const prog = (j) => `${j.done}/${j.plan.units.length}`;
    const key = s + (s === "fronts" ? prog(g.front) : s === "backs" ? prog(g.back) : "") + (p.wait || "") + p.power;
    if (key === this.key) {
      this.progress(p);
      return;
    }
    this.key = key;
    this.render();
  }
  progress(p) {
    const bar = $(".bar > div", this.win);
    const j = this.stage() === "fronts" ? this.group.front : this.group.back;
    const art = $(".printing-scene.twinart", this.win);
    if (art && (p.busy || p.wait)) art.innerHTML = Twin.svg(p);
    if (bar && j) bar.style.width = Math.round((j.done + (p.feeding ? p.progress || 0 : 0)) / j.plan.units.length * 100) + "%";
  }
  render() {
    const g = this.group, s = this.stage();
    const p = Sim.printers[g.choice.printer];
    const sheets = g.front.plan.units.length;
    const backs = Math.floor(g.sides / 2);
    const now = { fronts: 0, turn: 1, backs: 2, done: 3, failed: 0, cancelled: 1 }[s];
    const step = (i, t) => `<div class="st ${i < now ? "done" : i === now ? "now" : ""}"><i>${i < now ? "✓" : i + 1}</i><span>${t}</span></div>`;
    let body = "", left = "", right = "";
    const printing = (title, j, total) => {
      const problem = p.wait || !p.power ? `<div class="note">${ICON.warn}<div><b>${esc(!p.power ? "La impresora está apagada" : Twin.waitText(p))}.</b> Resuélvelo en la impresora; el trabajo sigue donde estaba.</div></div>` : "";
      return `<div class="printing-scene twinart">${Twin.svg(p)}</div>
        <div class="status"><span>${esc(title)}</span><span>${Math.min(j.done + (p.feeding ? 1 : 0), total)} de ${total} hojas</span></div>
        <div class="bar"><div style="width:0"></div></div>${problem}`;
    };
    if (s === "fronts") {
      body = `<div class="lead">Primero se imprimen las caras delanteras. No toques el papel hasta que terminen.</div>${printing("Imprimiendo las caras delanteras", g.front, sheets)}`;
      left = `<span class="fp-hint">Continuar se activa cuando terminen</span>`;
      right = `<button class="fp-btn accent" data-a="go" disabled>${esc(_("Continue"))}</button><button class="fp-btn" data-a="cancel">${esc(_("Cancel"))}</button>`;
    } else if (s === "turn") {
      const top = p.out[0] && p.out[0].faces[p.out[0].pose.up][0];
      body = `<div class="lead">Las caras delanteras están listas. Ahora pon las hojas para imprimir los reversos:</div>
        ${howtoHTML(top ? top.pages[0] + 1 : "", false)}
        ${g.sides % 2 ? `<div class="note">${ICON.info}<div>La última hoja no lleva nada detrás: <b>déjala en el montón</b>, la impresora la pasará sin imprimir.</div></div>` : ""}`;
      left = `<button class="fp-link" data-a="auto">Hacerlo en la simulación</button>`;
      right = `<button class="fp-btn accent" data-a="go">${esc(_("Continue"))}</button><button class="fp-btn" data-a="cancel">${esc(_("Cancel"))}</button>`;
    } else if (s === "backs") {
      body = `<div class="lead">Imprimiendo los reversos. Las hojas salen ya en orden.</div>${printing("Imprimiendo los reversos", g.back, g.back.plan.units.length)}`;
      left = `<span class="fp-hint">${backs} ${backs === 1 ? "reverso" : "reversos"}${g.sides % 2 ? " y una hoja que pasa en blanco" : ""}</span>`;
      right = `<button class="fp-btn" data-a="close">Ocultar</button>`;
    } else if (s === "done") {
      body = `<div class="result">${ICON.ok.replace("<svg", '<svg style="fill:var(--accent)"')}<div><b>Documento terminado</b><div class="fp-hint">${sheets} hojas a doble cara. Al recogerlas, dales la vuelta como a un libro: la página 1 queda arriba.</div></div></div>`;
      right = `<button class="fp-btn accent" data-a="collect">Recoger y comprobar</button><button class="fp-btn" data-a="close">${esc(_("Close"))}</button>`;
    } else if (s === "failed") {
      body = `<div class="result">${ICON.warn.replace("<svg", '<svg style="fill:var(--danger)"')}<div><b>El trabajo se ha cancelado</b><div class="fp-hint">Se cancelaron las páginas en la impresora o en la cola.</div></div></div>`;
      right = `<button class="fp-btn" data-a="close">${esc(_("Close"))}</button>`;
    } else {
      this.close(); return;
    }
    this.win.innerHTML = `
      <div class="guide-head"><div><h1>${esc(_("Print the other side"))}</h1><p>${esc(g.title)} · ${sheets} ${sheets === 1 ? "hoja" : "hojas"} · ${esc(g.choice.printer)} · ${g.choice.duplex === "manual-short" ? "borde corto" : "borde largo"}</p></div>
        <button class="fp-close" data-a="close" title="${esc(_("Close"))}">${ICONS.close}</button></div>
      <div class="stepper">${step(0, "Caras delanteras")}${step(1, "Dar la vuelta")}${step(2, "Reversos")}</div>
      <div class="guide-body">${body}</div>
      <div class="guide-foot"><div>${left}</div><div class="right">${right}</div></div>`;
    this.win.querySelectorAll("[data-a]").forEach((b) => b.onclick = () => this.act(b.dataset.a));
    this.progress(p);
    if (this.win.isConnected) this.place();
    const go = $('[data-a="go"]:not(:disabled)', this.win);
    if (go) go.focus();
  }
  act(a) {
    const p = Sim.printers[this.group.choice.printer];
    if (a === "go") { this.cb.onContinue(); }
    else if (a === "cancel") this.cancel();
    else if (a === "auto") Sim.doTurnOver(p);
    else if (a === "collect") { Sim.collect(p); this.close(); }
    else if (a === "close") {
      // the backs are queued: the window may go, the job goes on (the twin keeps showing it)
      if (this.stage() === "turn" || this.stage() === "fronts") { this.cancel(); return; }
      this.close();
    }
  }
  cancel() {
    const cb = this.cb;
    if (this.stage() === "fronts") Sim.cancelJob(this.group.front, "cancelado en la ventana de doble cara");
    this.close();
    cb.onCancel();
  }
  close() {
    this.win.remove();
    if (this.cb.onClose) this.cb.onClose();
  }
}
