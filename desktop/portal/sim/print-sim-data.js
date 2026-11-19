// SPDX-License-Identifier: GPL-3.0-or-later
// Data of the print simulator: metrics.py palette and sizes, the Spanish catalog (locale/es.py),
// the printers (the ET-2710's options as its CUPS queue reports them) and the sample documents.
"use strict";

const M = {
  PAPER_SIZES: ["iso_a4", "na_letter", "na_legal", "iso_a3", "iso_a5", "iso_b5", "na_executive"],
  PAGES_PER_SHEET: [1, 2, 4, 6, 9, 16],
  NARROW_MARGIN_MM: 3.2,
  PREVIEW_BOX: [315, 79, 511, 548],
  PREVIEW_MARGIN: 32,
  PREVIEW_SHADOW: 8,
  PREVIEW_NUP_GAP: 0.04,
  PREVIEW_LIGHT: { sheet: [1, 1, 1], shadow: [0, 0, 0, 0.16], outline: [0, 0, 0, 0.10], hint: [0, 0, 0, 0.07] },
  PREVIEW_DARK: { sheet: [1, 1, 1], shadow: [0, 0, 0, 0.45], outline: [0, 0, 0, 0.25], hint: [0, 0, 0, 0.07] },
  ACCENTS: {
    blue: ["#0067c0", "#4cc2ff"], teal: ["#00777a", "#3fd5d9"], green: ["#107c10", "#6ccb5f"],
    yellow: ["#8a6100", "#ffd04a"], orange: ["#c24e00", "#ff9e5e"], red: ["#c42b1c", "#ff99a4"],
    pink: ["#bf0077", "#ff8ad8"], purple: ["#744da9", "#c8a8ff"], slate: ["#4a5a70", "#a9b8cc"],
  },
  ACCENT_TEXT: { blue: ["#003e92", "#99ebff"] },
  DARK: {
    bg: "#282828", footer: "#202020", "footer-border": "#373737", frame: "#3e3e3e",
    fg: "#ffffff", "fg-ctl": "#ffffff", fg2: "#c5c5c5", fg3: "#9d9d9d", "fg-disabled": "#767676",
    ctl: "#353535", "ctl-hover": "#3a3a3a", "ctl-press": "#2f2f2f", "ctl-focus": "#414141", "ctl-focus-hover": "#464646",
    "ctl-focus-border": "#484848", "ctl-focus-border-bottom": "#434343",
    "ctl-border": "#373737", "ctl-border-top": "#3c3c3c", "ctl-border-bottom": "#373737",
    btn: "#2d2d2d", "btn-hover": "#323232", "btn-press": "#272727",
    "btn-border": "#303030", "btn-border-top": "#353535", "btn-border-bottom": "#303030",
    "input-focus": "#1f1f1f", "input-bottom": "rgba(255,255,255,0.54)",
    "subtle-hover": "#353535", "subtle-press": "#303030", divider: "#3c3c3c",
    "preview-border": "#3c3c3c",
    popover: "#2c2c2c", "popover-border": "#202020", "menu-select": "#343434", "menu-hover": "#343434",
    shadow: "rgba(0,0,0,0.30)",
    "toggle-off": "#242424", "toggle-off-hover": "#313131", "toggle-outline": "#9b9b9b", "knob-off": "#cdcdcd",
    "check-off": "#242424", "check-outline": "#9b9b9b",
    focus: "#ffffff", "focus-gap": "#353535", chevron: "#c5c5c5",
    danger: "#ff99a4", "close-hover": "#c42b1c",
  },
  LIGHT: {
    bg: "#f9f9f9", footer: "#f3f3f3", "footer-border": "#eaeaea", frame: "#adadad",
    fg: "#1a1a1a", "fg-ctl": "#1b1b1b", fg2: "#5f5f5f", fg3: "#8a8a8a", "fg-disabled": "#9f9f9f",
    ctl: "#fdfdfd", "ctl-hover": "#f9f9f9", "ctl-press": "#f9f9f9", "ctl-focus": "#fefefe", "ctl-focus-hover": "#fbfbfb",
    "ctl-focus-border": "#eeeeee", "ctl-focus-border-bottom": "#d4d4d4",
    "ctl-border": "#eaeaea", "ctl-border-top": "#eaeaea", "ctl-border-bottom": "#d1d1d1",
    btn: "#fbfbfb", "btn-hover": "#f6f6f6", "btn-press": "#f5f5f5",
    "btn-border": "#e5e5e5", "btn-border-top": "#e5e5e5", "btn-border-bottom": "#cccccc",
    "input-focus": "#ffffff", "input-bottom": "rgba(0,0,0,0.45)",
    "subtle-hover": "#f0f0f0", "subtle-press": "#ebebeb", divider: "#eaeaea",
    "preview-border": "#d1d1d1",
    popover: "#f9f9f9", "popover-border": "#eaeaea", "menu-select": "#f3f3f3", "menu-hover": "#f3f3f3",
    shadow: "rgba(0,0,0,0.14)",
    "toggle-off": "#f3f3f3", "toggle-off-hover": "#eaeaea", "toggle-outline": "#8a8a8a", "knob-off": "#5c5c5c",
    "check-off": "#f3f3f3", "check-outline": "#8a8a8a",
    focus: "#1a1a1a", "focus-gap": "#fdfdfd", chevron: "#5f5f5f",
    danger: "#c42b1c", "close-hover": "#c42b1c",
  },
};

// Paper sizes (mm) and GTK's default margins for them (0.25 in).
const PAPER_MM = {
  iso_a4: [210, 297], na_letter: [215.9, 279.4], na_legal: [215.9, 355.6], iso_a3: [297, 420],
  iso_a5: [148, 210], iso_b5: [176, 250], na_executive: [184.15, 266.7],
};
const GTK_DEFAULT_MARGIN_MM = 6.35;
const PAPER_LABELS = {
  iso_a4: "A4 (210 × 297 mm)", na_letter: "Letter (8.5 × 11 in)", na_legal: "Legal (8.5 × 14 in)",
  iso_a3: "A3 (297 × 420 mm)", iso_a5: "A5 (148 × 210 mm)", iso_b5: "B5 (176 × 250 mm)",
  na_executive: "Executive (7.25 × 10.5 in)",
};

// locale/es.py, unchanged.
const STRINGS_ES = {
  "Print": "Imprimir", "Cancel": "Cancelar", "Save": "Guardar", "Printer": "Impresora",
  "Save as PDF": "Guardar como PDF", "Saves the document as a PDF file": "Guarda el documento como archivo PDF",
  "Ready": "Lista", "Copies": "Copias", "Collate": "Intercalar", "Orientation": "Orientación",
  "Portrait": "Vertical", "Landscape": "Horizontal", "Pages": "Páginas", "All pages": "Todas las páginas",
  "Odd pages only": "Solo páginas impares", "Even pages only": "Solo páginas pares", "Current page": "Página actual",
  "Selection": "Selección", "Custom range": "Intervalo personalizado", "e.g. 1-5, 8, 11-13": "p. ej. 1-5, 8, 11-13",
  "Color mode": "Modo de color", "Color": "Color", "Black and white": "Blanco y negro",
  "More settings": "Más opciones de configuración", "Back": "Atrás", "Paper size": "Tamaño del papel",
  "Pages per sheet": "Páginas por hoja", "Margins": "Márgenes", "Normal": "Normales", "Narrow": "Estrechos",
  "None": "Ninguno", "Two-sided printing": "Impresión a doble cara", "Print on one side": "Imprimir en una cara",
  "Print on both sides, flip on long edge": "Imprimir en ambas caras, voltear por el borde largo",
  "Print on both sides, flip on short edge": "Imprimir en ambas caras, voltear por el borde corto",
  "Previous page": "Página anterior", "Next page": "Página siguiente", "PDF documents": "Documentos PDF",
  "Total: 1 page": "Total: 1 página", "Total: {n} pages": "Total: {n} páginas",
  "Total: 1 sheet of paper": "Total: 1 hoja de papel", "Total: {n} sheets of paper": "Total: {n} hojas de papel",
  "A4 (210 × 297 mm)": "A4 (210 × 297 mm)", "Letter (8.5 × 11 in)": "Carta (8,5 × 11 in)",
  "Legal (8.5 × 14 in)": "Oficio (8,5 × 14 in)", "A3 (297 × 420 mm)": "A3 (297 × 420 mm)",
  "A5 (148 × 210 mm)": "A5 (148 × 210 mm)", "B5 (176 × 250 mm)": "B5 (176 × 250 mm)",
  "Executive (7.25 × 10.5 in)": "Ejecutivo (7,25 × 10,5 in)",
  "{title} - Printing": "{title} - Impresión", "Printing": "Impresión", "Close": "Cerrar",
  "Fit to width": "Ajustar al ancho", "Add a printer": "Agregar una impresora", "Print to file": "Imprimir en archivo",
  "Stores printing output to a file": "Guarda la impresión en un archivo", "On": "Activado", "Off": "Desactivado",
  "Allow the app to change print preferences.": "Permitir que la aplicación cambie las preferencias de impresión.",
  "This app doesn't support print preview": "Esta aplicación no admite la vista previa de impresión",
  "Paused": "En pausa", "Not accepting jobs": "No acepta trabajos",
  "Paper type": "Tipo de papel", "Print quality": "Calidad de impresión", "Borderless": "Sin bordes",
  "Document type": "Tipo de documento", "Colour correction": "Corrección de color",
  "Colour saturation": "Saturación del color", "Ink density": "Densidad de la tinta", "Brightness": "Brillo",
  "Contrast": "Contraste", "Colour adjustments": "Ajustes de color",
  "Plain Paper": "Papel normal", "Plain Paper Fast Load": "Papel normal (carga rápida)", "Postcard": "Postal / cartulina",
  "Glossy Film": "Película brillante", "Transparencies": "Transparencias", "Envelopes": "Sobres",
  "Back Light Film": "Película retroiluminada", "Matte Paper": "Papel mate",
  "Matte Paper Heavyweight": "Papel mate de alto gramaje (grueso)", "Inkjet Paper": "Papel para inyección de tinta",
  "Photo Quality Inkjet Paper": "Papel de calidad fotográfica", "Photo Paper": "Papel fotográfico",
  "Premium Glossy Photo Paper": "Papel fotográfico satinado Premium",
  "Premium Semigloss Photo Paper": "Papel fotográfico semibrillo Premium",
  "Premium Luster Photo Paper": "Papel fotográfico perla Premium",
  "Photo Quality Glossy Paper": "Papel satinado de calidad fotográfica", "Ilford Heavy Paper": "Papel Ilford grueso",
  "ColorLife Paper": "Papel ColorLife", "Other": "Otro", "Economy": "Económica", "Draft": "Borrador",
  "Standard": "Estándar", "High": "Alta", "Photo": "Foto", "Super Photo": "Foto superior", "Ultra Photo": "Foto ultra",
  "Best": "Máxima", "Text": "Texto", "Graphics": "Gráficos", "Mixed Text and Graphics": "Texto y gráficos",
  "Photograph": "Fotografía", "Line Art": "Dibujo lineal", "Default": "Predeterminada", "High Accuracy": "Alta precisión",
  "Bright Colors": "Colores vivos", "Correct Hue Only": "Corregir solo el tono", "Uncorrected": "Sin corregir",
  "Desaturated": "Desaturado", "Threshold": "Umbral", "Density": "Densidad", "Raw": "Sin procesar",
  "Pre-Dithered": "Pretramado", "No": "No", "Yes": "Sí", "Plain": "Normal", "Glossy": "Satinado", "Matte": "Mate",
  "Stationery": "Papel normal", "Photographic": "Fotográfico", "Photographic Glossy": "Fotográfico satinado",
  "Photographic Matte": "Fotográfico mate", "Photographic High Gloss": "Fotográfico muy brillante",
  "Photographic Semi-Gloss": "Fotográfico semibrillo", "Cardstock": "Cartulina", "Envelope": "Sobre",
  "Labels": "Etiquetas", "Transparency": "Transparencia",
  "Print on both sides manually, flip on long edge": "Imprimir a doble cara manualmente, girar por el borde largo",
  "Print on both sides manually, flip on short edge": "Imprimir a doble cara manualmente, girar por el borde corto",
  "Print the other side": "Imprimir la otra cara",
  "The front sides are printing ({n} sheets). When the printer has finished:": "Se están imprimiendo las caras delanteras ({n} hojas). Cuando la impresora termine:",
  "Turn the stack over like the page of a book, so the printed side faces down.": "Da la vuelta al montón como si pasaras la página de un libro, de modo que la cara impresa quede hacia abajo.",
  "Take out all the printed sheets without changing their order.": "Saca todas las hojas impresas sin cambiar su orden.",
  "Load them in the paper tray again the way the blank paper was loaded, the top of the pages going in first.": "Vuelve a cargarlas en la bandeja igual que estaba el papel en blanco, con la parte de arriba de las páginas entrando primero.",
  "The last sheet has nothing on its back: leave it in the stack, the printer passes it through without printing.": "La última hoja no lleva nada detrás: déjala en el montón, la impresora la pasará sin imprimir.",
  "Continue": "Continuar",
  "Document": "Document",
};

const LEVEL = (kw) => ({
  keyword: kw, section: "color", default: "None",
  choices: [["500", "-50 %"], ["600", "-40 %"], ["700", "-30 %"], ["800", "-20 %"], ["900", "-10 %"], ["None", "Normal"],
    ["1100", "+10 %"], ["1200", "+20 %"], ["1300", "+30 %"], ["1400", "+40 %"], ["1500", "+50 %"]],
});

// What printing.driver_options() returns for the user's ET-2710 (Gutenprint 5.3.5 PPD).
const ET2710_OPTIONS = [
  { keyword: "MediaType", label: "Paper type", section: "paper", default: "Plain", choices: [
    ["Plain", "Plain Paper"], ["PlainFast", "Plain Paper Fast Load"], ["Postcard", "Postcard"], ["GlossyFilm", "Glossy Film"],
    ["Transparency", "Transparencies"], ["Envelope", "Envelopes"], ["BackFilm", "Back Light Film"], ["Matte", "Matte Paper"],
    ["MatteHeavy", "Matte Paper Heavyweight"], ["Inkjet", "Inkjet Paper"], ["Coated", "Photo Quality Inkjet Paper"],
    ["Photo", "Photo Paper"], ["GlossyPhoto", "Premium Glossy Photo Paper"], ["Semigloss", "Premium Semigloss Photo Paper"],
    ["Luster", "Premium Luster Photo Paper"], ["GlossyPaper", "Photo Quality Glossy Paper"], ["Ilford", "Ilford Heavy Paper"],
    ["ColorLife", "ColorLife Paper"], ["Other", "Other"]] },
  { keyword: "StpQuality", label: "Print quality", section: "paper", default: "Standard", choices: [
    ["Economy", "Economy"], ["Draft", "Draft"], ["Standard", "Standard"], ["High", "High"], ["Photo", "Photo"],
    ["HighPhoto", "Super Photo"], ["UltraPhoto", "Ultra Photo"], ["Best", "Best"]] },
  { keyword: "StpFullBleed", label: "Borderless", section: "paper", default: "False", choices: [["False", "No"], ["True", "Yes"]] },
  { keyword: "StpImageType", label: "Document type", section: "color", default: "TextGraphics", choices: [
    ["Text", "Text"], ["Graphics", "Graphics"], ["TextGraphics", "Mixed Text and Graphics"], ["Photo", "Photograph"], ["LineArt", "Line Art"]] },
  { keyword: "StpColorCorrection", label: "Colour correction", section: "color", default: "None", choices: [
    ["None", "Default"], ["Accurate", "High Accuracy"], ["Bright", "Bright Colors"], ["Hue", "Correct Hue Only"],
    ["Uncorrected", "Uncorrected"], ["Desaturated", "Desaturated"], ["Threshold", "Threshold"], ["Density", "Density"],
    ["Raw", "Raw"], ["Predithered", "Pre-Dithered"]] },
  Object.assign(LEVEL("StpSaturation"), { label: "Colour saturation" }),
  Object.assign(LEVEL("StpDensity"), { label: "Ink density" }),
  Object.assign(LEVEL("StpBrightness"), { label: "Brightness" }),
  Object.assign(LEVEL("StpContrast"), { label: "Contrast" }),
  { keyword: "ColorModel", label: "", section: "hidden", default: "RGB", choices: [["Gray", "gray"], ["RGB", "color"]] },
];

// A driverless (IPP Everywhere) laser with a duplexer, for comparison: CUPS makes its PPD from IPP.
const LASER_OPTIONS = [
  { keyword: "MediaType", label: "Paper type", section: "paper", default: "Stationery", choices: [
    ["Stationery", "Stationery"], ["Cardstock", "Cardstock"], ["Envelope", "Envelope"], ["Labels", "Labels"], ["Transparency", "Transparency"]] },
  { keyword: "cupsPrintQuality", label: "Print quality", section: "paper", default: "Normal", choices: [
    ["Draft", "Draft"], ["Normal", "Normal"], ["High", "High"]] },
  { keyword: "ColorModel", label: "", section: "hidden", default: "Gray", choices: [["Gray", "gray"], ["Gray", "color"]] },
];

// The simulated printers. Physical behaviour the dialog cannot see lives here.
const PRINTERS = {
  "ET-2710-Series": {
    label: "ET-2710-Series", location: "", model: "Epson Expression ET-2700 EcoTank - CUPS+Gutenprint v5.3.5",
    kind: "inkjet", duplexer: false, faceUp: true, defaultOutputOrder: "Reverse", color: true,
    options: ET2710_OPTIONS, tray: "rear", capacity: 100, maxPaper: "na_legal",
    // seconds per side at each StpQuality, before the speed multiplier
    speed: { Economy: 4, Draft: 5, Standard: 9, High: 14, Photo: 22, HighPhoto: 30, UltraPhoto: 40, Best: 45 },
    tanks: { C: 70, M: 70, Y: 70, K: 127 },  // ml per bottle-filled tank
  },
  "Laser-Oficina": {
    label: "Laser-Oficina", location: "Oficina", model: "Láser monocromo con dúplex (IPP Everywhere, simulada)",
    kind: "laser", duplexer: true, faceUp: false, defaultOutputOrder: "Normal", color: false,
    options: LASER_OPTIONS, tray: "cassette", capacity: 250, maxPaper: "na_legal",
    speed: { Draft: 1.6, Normal: 2, High: 3 },
    tanks: { K: 100 },
  },
};

// Sample documents: page size in pt and a drawing function (ctx, page index, width, height in px).
const DOCS = (() => {
  const lorem = "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.";
  const palette = ["#0067c0", "#c42b1c", "#107c10", "#8a6100", "#744da9", "#00777a", "#c24e00"];
  function textPage(ctx, i, n, w, h) {
    const s = w / 595;
    ctx.fillStyle = "#000";
    ctx.font = `600 ${28 * s}px "Segoe UI", sans-serif`;
    ctx.fillText(`Página ${i + 1}`, 60 * s, 90 * s);
    ctx.fillStyle = palette[i % palette.length];
    ctx.fillRect(380 * s, 40 * s, 150 * s, 60 * s);
    ctx.fillStyle = "#fff";
    ctx.font = `600 ${30 * s}px "Segoe UI", sans-serif`;
    ctx.fillText(String(i + 1), 440 * s, 82 * s);
    ctx.fillStyle = "#222";
    ctx.font = `${10.5 * s}px "Segoe UI", sans-serif`;
    for (let l = 0; l < 38; l++) ctx.fillText(lorem.slice(0, 70 + (l * 7) % 40), 60 * s, (130 + l * 17) * s);
    // an arrow pointing to the top of the page, to check orientation on paper
    ctx.strokeStyle = "#444"; ctx.lineWidth = 2 * s;
    ctx.beginPath(); ctx.moveTo(520 * s, 780 * s); ctx.lineTo(520 * s, 720 * s);
    ctx.lineTo(508 * s, 734 * s); ctx.moveTo(520 * s, 720 * s); ctx.lineTo(532 * s, 734 * s); ctx.stroke();
    ctx.fillStyle = "#666"; ctx.font = `${10 * s}px "Segoe UI", sans-serif`;
    ctx.fillText(`${i + 1} / ${n}`, 280 * s, 815 * s);
  }
  function slidePage(ctx, i, n, w, h) {
    const s = w / 842;
    const g = ctx.createLinearGradient(0, 0, w, h);
    g.addColorStop(0, palette[i % palette.length]); g.addColorStop(1, "#1b1b1b");
    ctx.fillStyle = g; ctx.fillRect(0, 0, w, h);
    ctx.fillStyle = "#fff"; ctx.font = `600 ${44 * s}px "Segoe UI", sans-serif`;
    ctx.fillText(`Diapositiva ${i + 1}`, 60 * s, 140 * s);
    ctx.font = `${20 * s}px "Segoe UI", sans-serif`;
    ["Primer punto de la lista", "Segundo punto, algo más largo", "Tercero"].forEach((t, k) =>
      ctx.fillText("•  " + t, 70 * s, (220 + k * 44) * s));
    ctx.fillStyle = "rgba(255,255,255,.85)";
    ctx.fillRect(560 * s, 220 * s, 220 * s, 260 * s);
    ctx.fillStyle = palette[(i + 2) % palette.length];
    [120, 200, 90, 170].forEach((v, k) => ctx.fillRect((585 + k * 50) * s, (460 - v) * s, 32 * s, v * s));
    ctx.fillStyle = "#fff"; ctx.font = `${12 * s}px "Segoe UI", sans-serif`;
    ctx.fillText(`${i + 1} / ${n}  ↑ arriba`, 60 * s, 560 * s);
  }
  function photoPage(ctx, i, n, w, h) {
    const sky = ctx.createLinearGradient(0, 0, 0, h * 0.65);
    sky.addColorStop(0, "#2a6fdb"); sky.addColorStop(1, "#f6c27a");
    ctx.fillStyle = sky; ctx.fillRect(0, 0, w, h);
    ctx.fillStyle = "#ffdf6b"; ctx.beginPath(); ctx.arc(w * 0.72, h * 0.42, w * 0.08, 0, 7); ctx.fill();
    const hills = [["#2f6b3a", 0.62], ["#1f4d2a", 0.72], ["#173a20", 0.84]];
    hills.forEach(([c, y], k) => {
      ctx.fillStyle = c; ctx.beginPath(); ctx.moveTo(0, h);
      for (let x = 0; x <= w; x += w / 40) ctx.lineTo(x, h * y + Math.sin(x / w * 6 + k * 2) * h * 0.04);
      ctx.lineTo(w, h); ctx.fill();
    });
    ctx.fillStyle = "rgba(255,255,255,.9)"; ctx.font = `600 ${w * 0.035}px "Segoe UI", sans-serif`;
    ctx.fillText("↑ arriba", w * 0.04, h * 0.06);
  }
  function mixedPage(ctx, i, n, w, h) {
    const s = w / 595;
    ctx.fillStyle = palette[i % palette.length]; ctx.fillRect(0, 0, w, 150 * s);
    ctx.fillStyle = "#fff"; ctx.font = `600 ${30 * s}px "Segoe UI", sans-serif`;
    ctx.fillText(`Folleto · página ${i + 1}`, 40 * s, 95 * s);
    ctx.save(); ctx.translate(40 * s, 180 * s);
    photoPage(ctx, i, n, 250 * s, 180 * s); ctx.restore();
    ctx.fillStyle = "#222"; ctx.font = `${10.5 * s}px "Segoe UI", sans-serif`;
    for (let l = 0; l < 12; l++) ctx.fillText(lorem.slice(0, 38), 310 * s, (195 + l * 15) * s);
    for (let l = 0; l < 22; l++) ctx.fillText(lorem.slice(0, 80), 40 * s, (400 + l * 16) * s);
    ctx.fillStyle = "#666"; ctx.fillText(`${i + 1} / ${n}  ↑`, 280 * s, 815 * s);
  }
  return {
    text: { title: "Informe.pdf", pages: 5, size: [595, 842], draw: textPage, orientation: "portrait" },
    text7: { title: "Apuntes.pdf", pages: 7, size: [595, 842], draw: textPage, orientation: "portrait" },
    slides: { title: "Presentación.pdf", pages: 4, size: [842, 595], draw: slidePage, orientation: "landscape" },
    photo: { title: "Foto.jpg", pages: 1, size: [842, 595], draw: photoPage, orientation: "landscape" },
    mixed: { title: "Folleto.pdf", pages: 6, size: [595, 842], draw: mixedPage, orientation: "portrait" },
  };
})();

const ICONS = {
  add: '<svg viewBox="0 0 13 13" width="13" height="13"><path fill-rule="evenodd" d="M6 0h1v6h6v1H7v6H6V7H0V6h6Z"/></svg>',
  back: '<svg viewBox="0 0 16 16" width="16" height="16"><path fill-rule="evenodd" d="M6.15 2.65 6.85 3.35 2.71 7.5H15v1H2.71l4.14 4.15-0.7 0.7L0.79 8Z"/></svg>',
  caretL: '<svg viewBox="0 0 6 8" width="6" height="8"><path d="M6 0v8L0 4Z"/></svg>',
  caretR: '<svg viewBox="0 0 6 8" width="6" height="8"><path d="M0 0v8l6-4Z"/></svg>',
  check: '<svg viewBox="0 0 12 12" width="12" height="12"><path fill-rule="evenodd" d="M1 6.6 1.9 5.7 4.5 8.3 10.1 2 11 2.8 4.5 10.1Z"/></svg>',
  chevron: '<svg viewBox="0 0 16 16" width="16" height="16"><path fill-rule="evenodd" d="M4 6 4.9 5.1 8 8.2 11.1 5.1 12 6 8 10Z"/></svg>',
  close: '<svg viewBox="0 0 10 10" width="10" height="10"><path fill-rule="evenodd" d="M0.6 0 5 4.4 9.4 0l0.6 0.6L5.6 5l4.4 4.4-0.6 0.6L5 5.6 0.6 10 0 9.4 4.4 5 0 0.6Z"/></svg>',
  fit: '<svg viewBox="0 0 16 12" width="16" height="12"><path fill-rule="evenodd" d="M2 0h12a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2V2a2 2 0 0 1 2-2ZM2 1a1 1 0 0 0-1 1v8a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V2a1 1 0 0 0-1-1ZM3 3h2v1H4v1H3ZM11 3h2v2h-1V4h-1ZM12 7h1v2h-2V8h1ZM3 7h1v1h1v1H3Z"/></svg>',
  landscape: '<svg viewBox="0 0 16 16" width="16" height="16"><path fill-rule="evenodd" d="M0 3h12.2L16 6.8V14H0ZM1 4v9h14V8h-4V4ZM12 4.5V7h2.5Z"/></svg>',
  portrait: '<svg viewBox="0 0 16 16" width="16" height="16"><path fill-rule="evenodd" d="M2 0h8.2L14 3.8V16H2ZM3 1v14h10V5H9V1ZM10 1.5V4h2.5Z"/></svg>',
  minus: '<svg viewBox="0 0 10 10" width="10" height="10"><path d="M0 4.5h10v1H0Z"/></svg>',
  plus: '<svg viewBox="0 0 10 10" width="10" height="10"><path d="M4.5 0h1v4.5H10v1H5.5V10h-1V5.5H0v-1h4.5Z"/></svg>',
};
