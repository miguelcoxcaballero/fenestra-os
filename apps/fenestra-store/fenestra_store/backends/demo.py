"""Deterministic in-memory catalogue for --demo-data, screenshots and tests.

Every name, developer and text here is invented for Fenestra; icons and screenshots are
drawn at runtime by art.py from the (hue, glyph) pair. Operations only change this
in-memory state and report simulated progress.
"""
from __future__ import annotations

import threading
import time

from .. import util
from ..i18n import pick
from ..model import App, Screenshot, Source, StoreError
from . import Backend

# Fixed reference date so "New and updated" is stable.
TODAY = "2026-10-30"

DEV_ALAMEDA = "Estudio Alameda"
DEV_FARO = "Colectivo Faro"
DEV_BRISA = "Proyecto Brisa"
DEV_LUDO = "Ludoteca Libre"
DEV_COMETA = "Equipo Cometa"
DEV_NUBE = "Taller Nube"
DEV_SENDA = "Cooperativa Senda"

FLATPAK_DEFAULT = ["network", "wayland", "dri"]

# id, name, developer, source, categories, kind, hue, glyph, version, size MB, license,
# released, popularity, flags (i=installed, u=update, f=featured), permissions, summary, description
_CATALOGUE = [
    ("org.fenestra.demo.Lienzo", "Lienzo", DEV_ALAMEDA, "flathub", ["creativity"], "app", 0.03, "brush",
     "3.2.0", 84, "GPL-3.0-or-later", "2026-10-22", 980, "f", ["wayland", "dri", "pictures", "documents"],
     {"en": "Paint, sketch and paint again", "es": "Pinta, dibuja y vuelve a pintar"},
     {"en": ["Lienzo is a friendly painting app with natural brushes, layers and a calm, distraction-free canvas.",
             "• Pressure-sensitive brushes, pencils and inks",
             "• Unlimited layers with blend modes",
             "• Exports to PNG, JPEG and OpenRaster"],
      "es": ["Lienzo es una aplicación de pintura sencilla con pinceles naturales, capas y un lienzo tranquilo y sin distracciones.",
             "• Pinceles, lápices y tintas sensibles a la presión",
             "• Capas ilimitadas con modos de fusión",
             "• Exporta a PNG, JPEG y OpenRaster"]}),
    ("org.fenestra.demo.NotasRapidas", "Notas rápidas", DEV_NUBE, "fedora", ["productivity"], "app", 0.13, "note",
     "1.8.4", 6, "MIT", "2026-08-14", 870, "i", None,
     {"en": "Jot things down before they fly away", "es": "Apunta las ideas antes de que se escapen"},
     {"en": ["Notas rápidas keeps small notes one click away. Notes are saved as you type and can be pinned, coloured and searched.",
             "Everything stays on your computer as plain text files."],
      "es": ["Notas rápidas tiene tus notas a un clic. Se guardan mientras escribes y puedes fijarlas, darles color y buscarlas.",
             "Todo se queda en tu equipo como archivos de texto plano."]}),
    ("org.fenestra.demo.ReproductorOla", "Reproductor Ola", DEV_SENDA, "flathub", ["multimedia"], "app", 0.55, "wave",
     "2.4.1", 31, "GPL-3.0-or-later", "2026-10-02", 940, "iu", ["wayland", "audio", "music", "network"],
     {"en": "Your music library, gently", "es": "Tu biblioteca de música, con calma"},
     {"en": ["Reproductor Ola plays your local music collection with gapless playback, smart playlists and a compact mini player.",
             "It reads tags and cover art from your files and never uploads anything."],
      "es": ["Reproductor Ola reproduce tu colección de música local sin cortes entre pistas, con listas inteligentes y un minirreproductor compacto.",
             "Lee las etiquetas y carátulas de tus archivos y nunca sube nada."]}),
    ("org.fenestra.demo.HojaClara", "Hoja Clara", DEV_NUBE, "fedora", ["productivity"], "app", 0.36, "grid",
     "5.0.2", 58, "MPL-2.0", "2026-09-18", 700, "", None,
     {"en": "Spreadsheets without the clutter", "es": "Hojas de cálculo sin complicaciones"},
     {"en": ["Hoja Clara is a lightweight spreadsheet with formulas, charts and sorting that opens common file formats.",
             "Ideal for budgets, lists and quick calculations."],
      "es": ["Hoja Clara es una hoja de cálculo ligera con fórmulas, gráficos y ordenación que abre los formatos habituales.",
             "Ideal para presupuestos, listas y cálculos rápidos."]}),
    ("org.fenestra.demo.PlumaSerena", "Pluma Serena", DEV_NUBE, "flathub", ["productivity"], "app", 0.72, "pen",
     "4.1.0", 27, "GPL-3.0-or-later", "2026-10-25", 820, "f", ["wayland", "documents"],
     {"en": "Write long texts in peace", "es": "Escribe textos largos con calma"},
     {"en": ["Pluma Serena is a focused writing app with chapters, word goals and a typewriter mode that keeps the current line centred.",
             "Export to Markdown, ODT or PDF when you are done."],
      "es": ["Pluma Serena es una aplicación de escritura concentrada con capítulos, objetivos de palabras y un modo máquina de escribir que centra la línea actual.",
             "Exporta a Markdown, ODT o PDF cuando termines."]}),
    ("org.fenestra.demo.MapaEstelar", "Mapa Estelar", DEV_COMETA, "flathub", ["education"], "app", 0.66, "star",
     "0.9.7", 120, "GPL-2.0-or-later", "2026-10-28", 760, "f", FLATPAK_DEFAULT,
     {"en": "A planetarium on your desk", "es": "Un planetario en tu escritorio"},
     {"en": ["Explore the night sky from any place and time. Mapa Estelar shows stars, planets and constellations with smooth zoom.",
             "Includes guided tours for beginners."],
      "es": ["Explora el cielo nocturno desde cualquier lugar y momento. Mapa Estelar muestra estrellas, planetas y constelaciones con un zoom suave.",
             "Incluye recorridos guiados para principiantes."]}),
    ("org.fenestra.demo.Cartografo", "Cartógrafo", DEV_SENDA, "fedora", ["utilities"], "app", 0.30, "pin",
     "2.2.0", 18, "GPL-3.0-or-later", "2026-07-30", 400, "", None,
     {"en": "Offline maps and routes", "es": "Mapas y rutas sin conexión"},
     {"en": ["Cartógrafo shows maps you have downloaded before, plans walking and cycling routes and works without a connection."],
      "es": ["Cartógrafo muestra mapas descargados previamente, planifica rutas a pie y en bicicleta y funciona sin conexión."]}),
    ("org.fenestra.demo.Cofre", "Cofre", DEV_FARO, "flathub", ["utilities"], "app", 0.08, "lock",
     "1.5.3", 12, "GPL-3.0-or-later", "2026-09-29", 650, "iu", ["wayland"],
     {"en": "Keep your passwords locked away", "es": "Guarda tus contraseñas bajo llave"},
     {"en": ["Cofre stores passwords and notes in an encrypted file that only you can open.",
             "• Strong password generator",
             "• Works completely offline"],
      "es": ["Cofre guarda contraseñas y notas en un archivo cifrado que solo tú puedes abrir.",
             "• Generador de contraseñas seguras",
             "• Funciona totalmente sin conexión"]}),
    ("org.fenestra.demo.Bitacora", "Bitácora", DEV_NUBE, "flathub", ["productivity"], "app", 0.09, "book",
     "1.0.0", 9, "Apache-2.0", "2026-10-29", 300, "", ["wayland"],
     {"en": "A private journal for every day", "es": "Un diario privado para cada día"},
     {"en": ["Bitácora is a simple journal with a calendar view, tags and photos. Your entries stay on this computer."],
      "es": ["Bitácora es un diario sencillo con vista de calendario, etiquetas y fotos. Tus entradas se quedan en este equipo."]}),
    ("org.fenestra.demo.TallerCodigo", "Taller de Código", DEV_FARO, "fedora", ["development"], "app", 0.60, "code",
     "7.3.0", 142, "MIT", "2026-10-12", 890, "iu", None,
     {"en": "A code editor that gets out of the way", "es": "Un editor de código que no estorba"},
     {"en": ["Taller de Código is a fast editor with syntax highlighting for many languages, a project tree, split views and an integrated terminal.",
             "Plugins add language servers and formatters."],
      "es": ["Taller de Código es un editor rápido con resaltado de sintaxis para muchos lenguajes, árbol de proyecto, vistas divididas y terminal integrada.",
             "Los complementos añaden servidores de lenguaje y formateadores."]}),
    ("org.fenestra.demo.TerminalFaro", "Terminal Faro", DEV_FARO, "fedora", ["development", "utilities"], "app", 0.0, "prompt",
     "3.9.1", 4, "GPL-3.0-or-later", "2026-06-05", 520, "", None,
     {"en": "A tidy terminal with tabs", "es": "Una terminal ordenada con pestañas"},
     {"en": ["Terminal Faro offers tabs, split panes, profiles and readable themes for working on the command line."],
      "es": ["Terminal Faro ofrece pestañas, paneles divididos, perfiles y temas legibles para trabajar en la línea de órdenes."]}),
    ("org.fenestra.demo.PrismaFoto", "Prisma Foto", DEV_ALAMEDA, "flathub", ["creativity"], "app", 0.83, "prism",
     "2.0.5", 96, "GPL-3.0-or-later", "2026-09-07", 720, "", ["wayland", "dri", "pictures"],
     {"en": "Develop and retouch your photos", "es": "Revela y retoca tus fotos"},
     {"en": ["Prisma Foto develops RAW photos and offers non-destructive adjustments, crops and gentle retouching tools."],
      "es": ["Prisma Foto revela fotos RAW y ofrece ajustes no destructivos, recortes y herramientas de retoque suaves."]}),
    ("org.fenestra.demo.EstudioRitmo", "Estudio Ritmo", DEV_ALAMEDA, "flathub", ["creativity", "multimedia"], "app", 0.92, "drum",
     "1.3.2", 210, "GPL-3.0-or-later", "2026-10-18", 480, "", ["wayland", "audio", "devices", "music"],
     {"en": "Make beats and record songs", "es": "Crea ritmos y graba canciones"},
     {"en": ["Estudio Ritmo is a small music studio: a step sequencer, a mixer with effects and multitrack recording."],
      "es": ["Estudio Ritmo es un pequeño estudio de música: secuenciador por pasos, mezclador con efectos y grabación multipista."]}),
    ("org.fenestra.demo.Charla", "Charla", DEV_BRISA, "flathub", ["communication"], "app", 0.50, "bubble",
     "0.18.0", 45, "AGPL-3.0-or-later", "2026-10-26", 610, "", ["network", "wayland", "audio", "downloads"],
     {"en": "Chat with friends on open networks", "es": "Chatea con amigos en redes abiertas"},
     {"en": ["Charla connects to open, decentralised chat networks with end-to-end encrypted rooms and voice calls."],
      "es": ["Charla se conecta a redes de chat abiertas y descentralizadas con salas cifradas de extremo a extremo y llamadas de voz."]}),
    ("org.fenestra.demo.CorreoBrisa", "Correo Brisa", DEV_BRISA, "fedora", ["communication"], "app", 0.57, "mail",
     "6.2.3", 64, "GPL-3.0-or-later", "2026-09-01", 590, "", None,
     {"en": "Email that feels light", "es": "Un correo que se siente ligero"},
     {"en": ["Correo Brisa handles several accounts, conversations and quick search, with a clean reading view."],
      "es": ["Correo Brisa gestiona varias cuentas, conversaciones y búsqueda rápida, con una vista de lectura limpia."]}),
    ("org.fenestra.demo.CineCasero", "Cine Casero", DEV_SENDA, "fedora", ["multimedia"], "app", 0.97, "play",
     "4.0.1", 22, "GPL-2.0-or-later", "2026-05-20", 800, "i", None,
     {"en": "Play any video file", "es": "Reproduce cualquier vídeo"},
     {"en": ["Cine Casero plays local videos with subtitles, chapters and hardware decoding."],
      "es": ["Cine Casero reproduce vídeos locales con subtítulos, capítulos y decodificación por hardware."]}),
    ("org.fenestra.demo.Archivero", "Archivero", DEV_SENDA, "fedora", ["utilities"], "app", 0.11, "box",
     "3.4.0", 3, "GPL-2.0-or-later", "2026-04-11", 450, "i", None,
     {"en": "Open and create compressed files", "es": "Abre y crea archivos comprimidos"},
     {"en": ["Archivero opens zip, tar and 7z archives and creates new ones by dragging files in."],
      "es": ["Archivero abre archivos zip, tar y 7z y crea otros nuevos arrastrando archivos."]}),
    ("org.fenestra.demo.Medidor", "Medidor", DEV_SENDA, "fedora", ["utilities"], "app", 0.25, "ring",
     "1.1.0", 2, "GPL-3.0-or-later", "2026-03-15", 260, "", None,
     {"en": "See what is filling your disk", "es": "Descubre qué llena tu disco"},
     {"en": ["Medidor scans a folder and draws a ring chart of what takes up the most space."],
      "es": ["Medidor analiza una carpeta y dibuja un gráfico de anillos con lo que más espacio ocupa."]}),
    ("org.fenestra.demo.Atomo", "Átomo", DEV_COMETA, "flathub", ["education"], "app", 0.42, "atom",
     "2.6.0", 15, "GPL-3.0-or-later", "2026-10-10", 330, "", ["wayland"],
     {"en": "The periodic table, explained", "es": "La tabla periódica, explicada"},
     {"en": ["Átomo shows every element with its properties, history and simple experiments to try at school."],
      "es": ["Átomo muestra cada elemento con sus propiedades, su historia y experimentos sencillos para el aula."]}),
    ("org.fenestra.demo.Abaco", "Ábaco", DEV_COMETA, "fedora", ["education", "utilities"], "app", 0.18, "calc",
     "45.1", 5, "GPL-3.0-or-later", "2026-08-02", 540, "", None,
     {"en": "Calculator with history and graphs", "es": "Calculadora con historial y gráficas"},
     {"en": ["Ábaco calculates, converts units and draws function graphs, keeping a history you can reuse."],
      "es": ["Ábaco calcula, convierte unidades y dibuja gráficas de funciones, con un historial reutilizable."]}),
    ("org.fenestra.demo.BloquesCaidos", "Bloques Caídos", DEV_LUDO, "flathub", ["games"], "game", 0.78, "blocks",
     "1.12.0", 38, "GPL-3.0-or-later", "2026-10-20", 990, "f", ["wayland", "dri", "audio"],
     {"en": "Stack falling blocks, clear the lines", "es": "Apila bloques que caen y limpia líneas"},
     {"en": ["A classic falling-blocks puzzle with a relaxing marathon mode, daily challenges and colour-blind friendly pieces."],
      "es": ["Un rompecabezas clásico de bloques que caen con modo maratón relajado, retos diarios y piezas aptas para daltonismo."]}),
    ("org.fenestra.demo.LaberintoLunar", "Laberinto Lunar", DEV_LUDO, "flathub", ["games"], "game", 0.69, "moon",
     "0.5.0", 140, "MIT", "2026-10-27", 410, "", ["wayland", "dri", "audio"],
     {"en": "Find your way out of moon caves", "es": "Encuentra la salida de las cuevas lunares"},
     {"en": ["Guide a little rover through glowing caves, collect crystals and avoid the falling rocks in 60 handmade levels."],
      "es": ["Guía a un pequeño explorador por cuevas brillantes, recoge cristales y esquiva las rocas en 60 niveles hechos a mano."]}),
    ("org.fenestra.demo.AjedrezBolsillo", "Ajedrez de Bolsillo", DEV_LUDO, "fedora", ["games"], "game", 0.06, "knight",
     "3.38.2", 7, "GPL-3.0-or-later", "2026-02-28", 670, "i", None,
     {"en": "Play chess against the computer", "es": "Juega al ajedrez contra el ordenador"},
     {"en": ["Ajedrez de Bolsillo has adjustable difficulty, move hints and a clean 2D board."],
      "es": ["Ajedrez de Bolsillo tiene dificultad ajustable, pistas de jugadas y un tablero 2D limpio."]}),
    ("org.fenestra.demo.PixelRally", "Pixel Rally", DEV_LUDO, "flathub", ["games"], "game", 0.15, "flag",
     "2.1.0", 260, "GPL-3.0-or-later", "2026-09-24", 580, "", ["wayland", "dri", "audio", "devices"],
     {"en": "Retro racing on tiny tracks", "es": "Carreras retro en pistas diminutas"},
     {"en": ["Drift around 24 pixel-art tracks alone or with friends in split-screen, with gamepad support."],
      "es": ["Derrapa en 24 pistas de pixel art solo o con amigos en pantalla dividida, con soporte para mandos."]}),
    ("org.fenestra.demo.GranjaTranquila", "Granja Tranquila", DEV_LUDO, "flathub", ["games"], "game", 0.27, "leaf",
     "1.0.3", 310, "GPL-3.0-or-later", "2026-08-21", 690, "", ["wayland", "dri", "audio"],
     {"en": "Grow a small farm at your own pace", "es": "Cultiva una pequeña granja a tu ritmo"},
     {"en": ["Plant, harvest and decorate a cosy farm through the seasons. No timers, no hurry."],
      "es": ["Siembra, cosecha y decora una granja acogedora a lo largo de las estaciones. Sin temporizadores ni prisas."]}),
    ("org.fenestra.demo.SopaLetras", "Sopa de Letras", DEV_LUDO, "fedora", ["games", "education"], "game", 0.47, "letters",
     "1.4.0", 3, "GPL-3.0-or-later", "2026-10-05", 350, "", None,
     {"en": "Word search puzzles in many languages", "es": "Sopas de letras en muchos idiomas"},
     {"en": ["Hundreds of word search puzzles by theme, with English and Spanish word lists."],
      "es": ["Cientos de sopas de letras por temas, con listas de palabras en español e inglés."]}),
    ("org.fenestra.demo.GitRamas", "Ramas", DEV_FARO, "flathub", ["development"], "app", 0.38, "branch",
     "0.30.1", 33, "GPL-3.0-or-later", "2026-10-15", 380, "", ["wayland", "network", "home"],
     {"en": "See and tidy your Git history", "es": "Ve y ordena tu historial de Git"},
     {"en": ["Ramas draws your repository history as a graph and makes staging, committing and branching visual."],
      "es": ["Ramas dibuja el historial del repositorio como un grafo y hace visual preparar, confirmar y crear ramas."]}),
]

# Lienzo is also packaged in the Fedora repositories (shows the "also available from" switch).
_ALSO_FEDORA = {"org.fenestra.demo.Lienzo": ("3.1.4", 79)}

_UPDATES = {"org.fenestra.demo.ReproductorOla": "2.5.0", "org.fenestra.demo.Cofre": "1.6.0",
            "org.fenestra.demo.TallerCodigo": "7.4.1"}

_CAPTIONS = [
    {"en": "Main window", "es": "Ventana principal"},
    {"en": "Working on a project", "es": "Trabajando en un proyecto"},
    {"en": "Preferences", "es": "Preferencias"},
]


class DemoBackend(Backend):
    id = "demo"
    label = "Demo"

    def __init__(self):
        self._lock = threading.Lock()
        self.installed = {}          # uid -> version
        self.updates = {}            # uid -> new version
        self._sources = [
            Source("flathub", self.id, "flathub", "Flathub",
                   "dl.flathub.org", True),
            Source("fedora", self.id, "fedora", "Fedora 43 - x86_64", "", True, False),
            Source("updates", self.id, "fedora", "Fedora 43 - x86_64 - Updates", "", True),
            Source("updates-testing", self.id, "fedora", "Fedora 43 - x86_64 - Test Updates", "", False),
        ]
        self.checked_once = False

    def available(self):
        return True

    # ------------------------------------------------------------------ catalogue
    def _make(self, row, source, version=None, size=None):
        (aid, name, dev, _src, cats, kind, hue, glyph, ver, size_mb, lic, rel, pop, flags, perms,
         summary, desc) = row
        uid = f"demo:{source}:{aid}"
        size_mb = size or size_mb
        app = App(uid=uid, app_id=aid, backend=self.id, source=source, name=name,
                  summary=pick(summary), description=list(pick(desc)), developer=dev,
                  categories=list(cats), kind=kind, version=version or ver, license=lic,
                  download_size=int(size_mb * 1e6 * 0.42), installed_size=int(size_mb * 1e6),
                  permissions=(list(perms) if source == "flathub" else None),
                  homepage="", keywords=[], art=(hue, glyph),
                  featured="f" in flags and source == "flathub", popularity=pop, released=rel,
                  ref=(f"app/{aid}/x86_64/stable" if source == "flathub" else f"{name.lower()};{ver};x86_64;fedora"),
                  origin=("flathub" if source == "flathub" else "fedora"),
                  screenshots=[Screenshot(caption=pick(c), art=i) for i, c in enumerate(_CAPTIONS)],
                  details_loaded=True)
        if "i" in flags and source == row[3]:
            self.installed.setdefault(uid, app.version)
        return app

    def load(self):
        time.sleep(0.05 * util.DEMO_SPEED)
        apps = []
        for row in _CATALOGUE:
            apps.append(self._make(row, row[3]))
            if row[0] in _ALSO_FEDORA:
                v, s = _ALSO_FEDORA[row[0]]
                apps.append(self._make(row, "fedora", v, s))
        with self._lock:
            if not self.checked_once:
                for a in apps:
                    if a.app_id in _UPDATES and a.source in ("flathub", "fedora") and a.uid in self.installed:
                        self.updates[a.uid] = _UPDATES[a.app_id]
            for a in apps:
                if a.uid in self.installed:
                    a.installed = True
                    a.version = self.installed[a.uid]
                    a.update_version = self.updates.get(a.uid, "")
                a.sync_state()
        return apps

    def refresh_updates(self, apps):
        time.sleep(0.6 * util.DEMO_SPEED)
        with self._lock:
            self.checked_once = True
            return {uid: v for uid, v in self.updates.items() if uid in self.installed}

    def details(self, app):
        app.details_loaded = True

    # ------------------------------------------------------------------ operations
    def _simulate(self, progress, steps):
        total = sum(n for _t, n in steps)
        done = 0
        for text, n in steps:
            for _i in range(n):
                time.sleep(0.06 * util.DEMO_SPEED)
                done += 1
                progress(done / total, text)

    def _source_on(self, app):
        kinds = {s.kind: s.enabled for s in self._sources if s.id in ("flathub", "fedora")}
        return kinds.get(app.source, True)

    def install(self, app, progress):
        if not self._source_on(app):
            raise StoreError("source-disabled")
        progress(0.0, "Preparing")
        self._simulate(progress, [("Downloading", 24), ("Installing", 8)])
        with self._lock:
            self.installed[app.uid] = app.version
            self.updates.pop(app.uid, None)

    def remove(self, app, progress):
        progress(0.0, "Preparing")
        self._simulate(progress, [("Uninstalling", 10)])
        with self._lock:
            self.installed.pop(app.uid, None)
            self.updates.pop(app.uid, None)

    def update(self, app, progress):
        progress(0.0, "Preparing")
        self._simulate(progress, [("Downloading", 16), ("Installing", 6)])
        with self._lock:
            new = self.updates.pop(app.uid, app.update_version or app.version)
            self.installed[app.uid] = new

    def launch(self, app):
        return True  # nothing to start in demo mode; the UI shows a short notice

    # ------------------------------------------------------------------ sources
    def sources(self):
        return list(self._sources)

    def set_source_enabled(self, source, enabled):
        time.sleep(0.2 * util.DEMO_SPEED)
        for s in self._sources:
            if s.id == source.id:
                s.enabled = enabled

