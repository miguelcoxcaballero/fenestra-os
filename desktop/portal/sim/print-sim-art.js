// SPDX-License-Identifier: GPL-3.0-or-later
// The printer drawings of the digital twin. The SVG is built once per printer and then animated by
// changing attributes every frame (carriage, sheet being fed and coming out, stacks, lights), so the
// motion is smooth and nothing is rebuilt while it prints.
"use strict";

let artSeq = 0;
const SVGNS = "http://www.w3.org/2000/svg";

// Small glyphs drawn on the printer's control strip (16 × 16 boxes).
const GLYPH = {
  power: "M8 2.2v5.2M5.1 4.1a5 5 0 1 0 5.8 0",
  wifi: "M2.5 7a8 8 0 0 1 11 0M4.7 9.3a5 5 0 0 1 6.6 0M7 11.4a1.7 1.7 0 0 1 2 0",
  paper: "M4.5 2.5h5l2.5 2.5v8.5h-7.5zM8 6v3.6M8 11.2v.3",
  ink: "M8 2.5c2.6 3.3 4 5.4 4 7.2a4 4 0 0 1-8 0c0-1.8 1.4-3.9 4-7.2z",
  stop: "M4.5 4.5h7v7h-7z",
};

class PrinterArt {
  constructor(host, kind) {
    this.id = "pa" + (++artSeq);
    this.kind = kind;
    host.innerHTML = kind === "laser" ? this.laser() : this.inkjet();
    this.svg = host.firstElementChild;
    this.q = (n) => this.svg.querySelector(`[data-n="${n}"]`);
  }
  defs() {
    const i = this.id;
    return `<defs>
      <linearGradient id="${i}-front" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#4b525e"/><stop offset=".55" stop-color="#383e48"/><stop offset="1" stop-color="#2a2e35"/></linearGradient>
      <linearGradient id="${i}-top" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#6a7381"/><stop offset="1" stop-color="#525a67"/></linearGradient>
      <linearGradient id="${i}-feeder" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#dfe3e8"/><stop offset="1" stop-color="#b9c0c9"/></linearGradient>
      <linearGradient id="${i}-tray" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#2f343c"/><stop offset="1" stop-color="#454b55"/></linearGradient>
      <linearGradient id="${i}-paper" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffffff"/><stop offset="1" stop-color="#eef0f3"/></linearGradient>
      <linearGradient id="${i}-glass" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#fff" stop-opacity=".35"/><stop offset=".4" stop-color="#fff" stop-opacity="0"/></linearGradient>
      <pattern id="${i}-text" width="600" height="5" patternUnits="userSpaceOnUse"><rect width="600" height="5" fill="#fff"/><rect x="200" y="1.5" width="200" height="1.3" fill="#9aa1ab"/></pattern>
      <filter id="${i}-soft" x="-20%" y="-50%" width="140%" height="200%"><feGaussianBlur stdDeviation="6"/></filter>
      <filter id="${i}-glow" x="-100%" y="-100%" width="300%" height="300%"><feGaussianBlur stdDeviation="1.6" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
      <clipPath id="${i}-above-slot"><rect x="0" y="0" width="600" height="101"/></clipPath>
      <clipPath id="${i}-below-slot"><rect x="0" y="172" width="600" height="80"/></clipPath>
    </defs>`;
  }
  glyph(n, x, y, name, label) {
    return `<g transform="translate(${x} ${y})" data-n="${n}"><title>${label}</title>
      <circle cx="8" cy="8" r="10" fill="#22262c" stroke="#59606b" stroke-width=".8"/>
      <path d="${GLYPH[name]}" fill="${name === "ink" ? "currentColor" : "none"}" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" filter="url(#${this.id}-glow)"/></g>`;
  }
  inkjet() {
    const i = this.id;
    const tanks = ["C", "M", "Y", "K"].map((t, k) => {
      const x = 452 + k * 9.5;
      const col = { C: "#14a7e0", M: "#e2187f", Y: "#ffd21f", K: "#2b2e33" }[t];
      return `<rect x="${x}" y="140" width="7" height="58" rx="2" fill="#15181c" stroke="#5c636e" stroke-width=".8"/>
        <rect data-n="tank-${t}" x="${x + 1}" y="141" width="5" height="56" rx="1.4" fill="${col}"/>
        <rect x="${x}" y="140" width="7" height="58" rx="2" fill="url(#${i}-glass)"/>`;
    }).join("");
    return `<svg viewBox="0 0 600 258" xmlns="${SVGNS}" role="img" aria-label="Impresora de tinta con alimentador trasero">${this.defs()}
      <ellipse cx="300" cy="238" rx="235" ry="12" fill="#000" opacity=".28" filter="url(#${i}-soft)"/>
      <!-- rear feeder and the paper standing in it -->
      <path d="M186 101 L204 20 Q205 16 209 16 L391 16 Q395 16 396 20 L414 101 Z" fill="url(#${i}-feeder)" stroke="#9ea6b0" stroke-width="1"/>
      <path d="M204 30 L396 30" stroke="#a9b0ba" stroke-width="1"/>
      <g data-n="in-stack">
        <path data-n="in-edge" d="" fill="#e4e7eb" stroke="#c4c9d0" stroke-width=".8"/>
        <path data-n="in-top" d="" fill="url(#${i}-paper)" stroke="#c4c9d0" stroke-width=".8"/>
      </g>
      <g clip-path="url(#${i}-above-slot)"><path data-n="feed" d="" fill="#fff" stroke="#c4c9d0" stroke-width=".8" opacity="0"/></g>
      <!-- body -->
      <path d="M126 96 H474 Q488 96 494 108 L500 122 H100 L106 108 Q112 96 126 96 Z" fill="url(#${i}-top)"/>
      <rect x="198" y="99" width="204" height="3" rx="1.5" fill="#1d2025"/>
      <rect x="150" y="108" width="300" height="9" rx="3" fill="#1b1e23"/>
      <g data-n="carriage"><rect x="0" y="105.5" width="40" height="14" rx="3" fill="#7d8694" stroke="#a3abb6" stroke-width=".8"/><rect x="6" y="117" width="28" height="2" rx="1" fill="#4cc2ff" opacity="0" data-n="spray"/></g>
      <path d="M100 122 H500 V206 Q500 222 484 222 H116 Q100 222 100 206 Z" fill="url(#${i}-front)"/>
      <path d="M100 122 H500" stroke="#7a8392" stroke-width="1"/>
      <!-- control strip -->
      <rect x="118" y="134" width="132" height="28" rx="14" fill="#262a30" stroke="#454c56" stroke-width=".8"/>
      ${this.glyph("led-power", 124, 140, "power", "Encendido")}
      ${this.glyph("led-wifi", 156, 140, "wifi", "Wi-Fi")}
      ${this.glyph("led-paper", 188, 140, "paper", "Papel")}
      ${this.glyph("led-ink", 220, 140, "ink", "Tinta")}
      <!-- ink tanks -->
      <rect x="446" y="132" width="46" height="74" rx="8" fill="#2a2e35" stroke="#4d545f" stroke-width=".8"/>
      ${tanks}
      <!-- output slot and tray -->
      <rect x="176" y="168" width="248" height="6" rx="3" fill="#121418"/>
      <path d="M170 200 H430 L452 236 Q454 240 449 240 H151 Q146 240 148 236 Z" fill="url(#${i}-tray)" stroke="#555c66" stroke-width=".8"/>
      <g data-n="out-stack">
        <path data-n="out-edge" d="" fill="#dfe2e6" stroke="#c4c9d0" stroke-width=".8"/>
        <path data-n="out-top" d="" fill="url(#${i}-paper)" stroke="#c4c9d0" stroke-width=".8"/>
        <text data-n="out-label" x="300" y="226" text-anchor="middle" font-size="12" font-weight="600" fill="#1b1b1b" font-family="Segoe UI Variable Text, Segoe UI, sans-serif"></text>
      </g>
      <g clip-path="url(#${i}-below-slot)">
        <path data-n="emerge" d="" fill="url(#${i}-text)" stroke="#c4c9d0" stroke-width=".8" opacity="0"/>
        <text data-n="emerge-label" x="300" y="0" text-anchor="middle" font-size="12" font-weight="600" fill="#1b1b1b" font-family="Segoe UI Variable Text, Segoe UI, sans-serif"></text>
      </g>
      <!-- states -->
      <g data-n="jam" opacity="0"><rect x="222" y="178" width="156" height="26" rx="13" fill="#c42b1c"/><text x="300" y="195" text-anchor="middle" font-size="12" font-weight="600" fill="#fff" font-family="Segoe UI Variable Text, Segoe UI, sans-serif">Atasco de papel</text></g>
      <path data-n="dim" d="M100 96 H500 V206 Q500 222 484 222 H116 Q100 222 100 206 Z" fill="#000" opacity="0"/>
    </svg>`;
  }
  laser() {
    const i = this.id;
    return `<svg viewBox="0 0 600 258" xmlns="${SVGNS}" role="img" aria-label="Impresora láser con dúplex">${this.defs()}
      <linearGradient id="${i}-lfront" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#f1f3f5"/><stop offset="1" stop-color="#cdd2d8"/></linearGradient>
      <ellipse cx="300" cy="238" rx="210" ry="12" fill="#000" opacity=".25" filter="url(#${i}-soft)"/>
      <path d="M128 52 H472 Q486 52 488 66 L490 222 H110 L112 66 Q114 52 128 52 Z" fill="url(#${i}-lfront)" stroke="#a9b0b8"/>
      <path d="M170 52 L186 30 H414 L430 52 Z" fill="#d9dde2" stroke="#a9b0b8"/>
      <path d="M196 46 H404" stroke="#8e959e" stroke-width="2"/>
      <g data-n="out-stack"><path data-n="out-edge" d="" fill="#e4e7eb" stroke="#c4c9d0"/><path data-n="out-top" d="" fill="url(#${i}-paper)" stroke="#c4c9d0"/></g>
      <text data-n="out-label" x="300" y="0" text-anchor="middle" font-size="11" font-weight="600" fill="#1b1b1b" font-family="Segoe UI Variable Text, Segoe UI, sans-serif"></text>
      <rect x="140" y="72" width="128" height="50" rx="6" fill="#16211b" stroke="#40514a"/>
      <text data-n="lcd1" x="152" y="93" font-size="12" fill="#7cf29b" font-family="Segoe UI Variable Text, Segoe UI, sans-serif"></text>
      <text data-n="lcd2" x="152" y="111" font-size="11" fill="#7cf29b" opacity=".85" font-family="Segoe UI Variable Text, Segoe UI, sans-serif"></text>
      ${this.glyph("led-power", 292, 84, "power", "Encendido")}
      ${this.glyph("led-paper", 324, 84, "paper", "Atención")}
      <rect x="132" y="160" width="336" height="50" rx="8" fill="#d5d9de" stroke="#a6adb5"/>
      <rect x="270" y="180" width="60" height="9" rx="4.5" fill="#99a0a8"/>
      <g data-n="jam" opacity="0"><rect x="222" y="128" width="156" height="26" rx="13" fill="#c42b1c"/><text x="300" y="145" text-anchor="middle" font-size="12" font-weight="600" fill="#fff" font-family="Segoe UI Variable Text, Segoe UI, sans-serif">Atasco de papel</text></g>
      <path data-n="dim" d="M128 52 H472 Q486 52 488 66 L490 222 H110 L112 66 Q114 52 128 52 Z" fill="#000" opacity="0"/>
    </svg>`;
  }

  // ---------------------------------------------------------------- per frame
  set(n, attrs) {
    const e = this.q(n);
    if (!e) return;
    for (const [k, v] of Object.entries(attrs)) {
      if (k === "text") { if (e.textContent !== v) e.textContent = v; } else if (e.getAttribute(k) !== String(v)) e.setAttribute(k, v);
    }
  }
  led(n, on, color, blinking) {
    const t = performance.now();
    const lit = on && (!blinking || Math.floor(t / 450) % 2 === 0);
    this.set(n, { color: lit ? color : "#5b626d", style: `color:${lit ? color : "#5b626d"}` });
  }
  update(p, sim) {
    const t = performance.now();
    const pages = (s) => Math.max(0, Math.min(1, s / Math.max(1, p.def.capacity)));
    if (this.kind === "laser") {
      const lvl = p.ink.K / p.def.tanks.K;
      this.set("lcd1", { text: p.power ? (p.wait ? "Atención" : p.feeding ? "Imprimiendo" : "Lista") : "" });
      this.set("lcd2", { text: p.power ? `Tóner ${Math.round(lvl * 100)} %` : "" });
      this.led("led-power", p.power, "#3fd35f", !!p.feeding);
      this.led("led-paper", p.power && !!p.wait, "#ff9e3d", true);
      const h = p.out.length ? 3 + pages(p.out.length) * 14 : 0;
      this.set("out-edge", { d: h ? `M200 ${44 - h} H400 V44 H200 Z` : "" });
      this.set("out-top", { d: h ? `M196 ${40 - h} H404 L400 ${44 - h} H200 Z` : "" });
    } else {
      // rear stack: thicker with more paper
      const n = p.tray.length, th = n ? 2 + pages(n) * 10 : 0;
      this.set("in-top", { d: n ? `M200 ${98 - th * .2} L216 ${32 - th} H384 L400 ${98 - th * .2} Z` : "" });
      this.set("in-edge", { d: n ? `M200 98 L216 32 H384 L400 98 Z` : "" });
      // carriage
      const printing = p.feeding && p.anim === "print";
      const cx = printing ? 158 + (Math.sin(t / 150) + 1) / 2 * 252 : 158;
      this.set("carriage", { transform: `translate(${cx.toFixed(1)} 0)` });
      this.set("spray", { opacity: printing && Math.floor(t / 90) % 2 ? .9 : 0 });
      // the sheet going in at the back
      const feedP = p.feeding && p.anim === "feed" ? Math.min(1, (t - p.animAt) / (sim.ms(1.2) || 1)) : 0;
      if (feedP > 0 && feedP < 1) {
        const y = 32 + feedP * 70;
        this.set("feed", { d: `M${206 + feedP * 4} ${y} H${394 - feedP * 4} L${398} ${y + 66} H202 Z`, opacity: 1 });
      } else this.set("feed", { opacity: 0 });
      // the sheet coming out at the front while it prints
      const cur = p.current;
      if (printing || (p.anim === "out" && t - p.animAt < 350)) {
        const k = printing ? Math.max(.05, p.progress || 0) : 1;
        const y1 = 174 + k * 52;
        this.set("emerge", { d: `M184 172 H416 L${416 + k * 14} ${y1} H${184 - k * 14} Z`, opacity: 1 });
        this.set("emerge-label", { y: (y1 - 8).toFixed(1), text: cur && cur.pages.length && k > .35 ? String(cur.pages.map((i) => i + 1).join("+")) : "" });
      } else {
        this.set("emerge", { opacity: 0 });
        this.set("emerge-label", { text: "" });
      }
      // output stack and its top page
      const m = p.out.length, oh = m ? 1.5 + pages(m) * 6 : 0;
      this.set("out-edge", { d: m ? `M176 212 H424 L442 234 H158 Z` : "" });
      this.set("out-top", { d: m ? `M176 ${212 - oh} H424 L442 ${234 - oh} H158 Z` : "" });
      const top = p.out[0];
      const L = top && top.faces[top.pose.up][0];
      this.set("out-label", { y: (227 - oh).toFixed(1), text: L ? `p. ${L.pages.map((i) => i + 1).join("+")}` : "" });
      // ink
      for (const tk of ["C", "M", "Y", "K"]) {
        const lvl = Math.max(0, Math.min(1, p.ink[tk] / p.def.tanks[tk]));
        this.set("tank-" + tk, { y: (141 + 56 * (1 - lvl)).toFixed(1), height: (56 * lvl).toFixed(1) });
      }
      this.led("led-power", p.power, "#3fd35f", !!printing);
      this.led("led-wifi", p.power && p.connected, "#4cc2ff", false);
      this.led("led-paper", p.power && (p.wait === "paper" || p.wait === "jam"), "#ff9e3d", p.wait === "jam");
      this.led("led-ink", p.power && p.wait === "ink", "#ff9e3d", true);
    }
    this.set("jam", { opacity: p.jammed ? 1 : 0 });
    this.set("dim", { opacity: p.power ? 0 : .38 });
  }
}
