#!/usr/bin/env python3
"""DeskLens: visor local de proyectos y archivos.

Abre una ventana en modo aplicación (Edge, Chrome, Chromium o Brave); al cerrarla, el servidor se apaga.
Windows: doble clic en desklens.pyw · macOS: desklens.command · Linux: desklens.sh
Uso: desklens.pyw [archivo ...]   (arrastrar archivos sobre el icono los abre en pestañas)
     python desklens.pyw --sin-ventana   (solo servidor, para desarrollo)
"""
import base64
import codecs
import difflib
import gzip
import hashlib
import io
import json
import mimetypes
import os
import re
import shlex
import shutil
import signal
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unicodedata
import webbrowser
import xml.etree.ElementTree as ET
import zipfile
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "config.json"
WINDOWS, MAC = os.name == "nt", sys.platform == "darwin"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)  # Windows: sin ventana negra (en macOS y Linux no existe)
HIDDEN = {".git", "__pycache__", ".ipynb_checkpoints", ".idea", ".vs"}


# ---------- configuración y permisos ----------

def load_config():
    """config.json (proyectos, sueltos, ajustes, IA, ventana…); si falta o está roto, una configuración vacía."""
    try:
        return json.loads(CONFIG.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return {"proyectos": [], "sueltos": []}


def save_config(cfg):
    """Escribe config.json y anula la caché de ajustes para que la próxima lectura vea lo nuevo."""
    global _settings
    _settings = None  # los ajustes se vuelven a leer
    CONFIG.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")


# ---------- ajustes (antes valores fijos en el código; se cambian en ⚙ Ajustes) ----------
# clave, grupo, etiqueta, valor por defecto, mínimo, máximo (True/False = casilla)
SETTINGS = [
    ("puerto", "General", "Puerto del servidor local (se aplica al reabrir DeskLens)", 8765, 1024, 65535),
    ("vista_max_mb", "General", "Tamaño máximo para ver y editar un archivo de texto (MB)", 2, 1, 200),
    ("indice_max_mb", "Índice", "Texto máximo indexado por archivo (MB)", 20, 1, 500),
    ("indice_repaso_min", "Índice", "Repasar los cambios cada (minutos)", 5, 1, 240),
    ("bitacora_max_lineas", "Bitácora", "Aviso «Bitácora grande» a partir de (líneas)", 200, 20, 100000),
    ("bitacora_conservar", "Bitácora", "Entradas que se quedan al archivar", 20, 1, 1000),
    ("git_cache_seg", "Git", "Volver a consultar git cada (segundos)", 10, 1, 3600),
    ("git_fetch_min", "Git", "Buscar novedades en los remotos cada (minutos; 0 = nunca)", 5, 0, 1440),
    ("ia_espera_seg", "IA", "Tiempo máximo de espera de una respuesta (segundos)", 600, 30, 3600),
    ("ia_explicar_lineas", "IA", "Líneas de la consola que envía «Explicar error»", 40, 5, 500),
    ("ia_pdf_en_adelante", "IA", "Páginas que toma «página N en adelante»", 10, 1, 100),
    ("ia_pdf_max_paginas", "IA", "Máximo de páginas de un PDF por mensaje", 50, 1, 500),
    ("ia_limite_tokens", "IA", "Límite de tokens por mensaje antes de preguntar", 2000, 100, 200000),
    ("ia_permitir_sensibles", "IA", "Permitir adjuntar y enviar a la IA archivos sensibles (.env, claves, credenciales…)", True, None, None),
    ("ia_confirmar_aplicar", "IA", "Pedir confirmación antes de aplicar los cambios que propone la IA (si no, se aplican solos y queda «Deshacer»)", False, None, None),
    ("reglas_aviso_tokens", "IA", "Aviso de reglas largas a partir de (tokens)", 300, 50, 100000),
    ("recup_espera_seg", "Recuperación", "Copia de seguridad al dejar de escribir (segundos)", 2, 1, 60),
    ("recup_max_seg", "Recuperación", "Copia como máximo cada (segundos) mientras escribes", 10, 2, 600),
    ("editor_tab", "Editor y lectura", "Espacios por tabulación", 4, 1, 8),
    ("letra_documento", "Editor y lectura", "Tamaño de letra de los documentos (px)", 18, 10, 32),
    ("letra_codigo", "Editor y lectura", "Tamaño de letra del código (px)", 13, 9, 28),
    ("pestanas_vista_previa", "Editor y lectura", "Pestaña de vista previa: un clic reemplaza la anterior", True, None, None),
    ("revelar_en_arbol", "Editor y lectura", "Desplegar el árbol hasta el archivo abierto", True, None, None),
    ("recargar_preguntar", "Editor y lectura", "Preguntar antes de recargar un archivo abierto que cambió en el disco (si no, se recarga solo; con cambios sin guardar siempre se pregunta)", False, None, None),
    ("historial_dias", "Historial de cambios", "Borrar el historial de un archivo tras (días sin editarlo)", 7, 1, 3650),
    ("historial_mb", "Historial de cambios", "Espacio máximo de todo el historial (MB)", 1000, 50, 100000),
    ("historial_pausa_seg", "Historial de cambios", "Al escribir, un paso nuevo tras una pausa de (segundos)", 2, 1, 30),
    # lista de opciones: valor por defecto de texto y en «mínimo» las opciones (valor, nombre)
    ("web_buscador", "Web", "Buscador de la pestaña web (Google, Bing, Yahoo y Wikipedia se ven dentro de DeskLens; los demás, con «Abrir en el navegador»)",
     "google", [("google", "Google"), ("bing", "Bing"), ("yahoo", "Yahoo"), ("wikipedia", "Wikipedia (español)"),
                ("duckduckgo", "DuckDuckGo"), ("ecosia", "Ecosia"), ("brave", "Brave Search")], None),
]
_settings = None


def ajustes():
    """Valores de ⚙ Ajustes (los guardados y, para el resto, los de SETTINGS); se leen una vez y quedan en caché."""
    global _settings
    if _settings is None:
        saved = load_config().get("ajustes", {})
        _settings = {k: saved.get(k, d) for k, _, _, d, _, _ in SETTINGS}
        if "ia_limite_tokens" not in saved:  # antes vivía en «Conectar IA»: se respeta lo que ya hubiera
            _settings["ia_limite_tokens"] = load_config().get("ia", {}).get("limite", 2000)
    return _settings


def ajuste(key):
    return ajustes()[key]


def set_ajustes(data):
    """Valida tipo y rango; lo que no cumple se queda como estaba."""
    cfg = load_config()
    current = {**ajustes()}
    for k, _, _, d, lo, hi in SETTINGS:
        if k not in data:
            continue
        v = data[k]
        if isinstance(d, bool):
            current[k] = bool(v)
        elif isinstance(d, str):  # lista de opciones: solo una de las previstas
            if v in [c for c, _ in lo]:
                current[k] = v
        else:
            try:
                v = int(v)
            except (TypeError, ValueError):
                continue
            if lo <= v <= hi:
                current[k] = v
    cfg["ajustes"] = current
    save_config(cfg)
    return current


def add_paths(kind, paths):
    """Añade carpetas («proyectos») o archivos («sueltos») a config.json, sin repetir, y despierta al indexador."""
    cfg = load_config()
    for p in paths:
        p = str(Path(p).resolve())
        if p not in cfg[kind]:
            cfg[kind].append(p)
    save_config(cfg)
    idx_wake.set()  # el índice incorpora lo nuevo enseguida


def allowed(path):
    """Solo se sirve lo que está dentro de un proyecto o es un archivo suelto añadido."""
    p = Path(path).resolve()
    cfg = load_config()
    return (any(p.is_relative_to(Path(r).resolve()) for r in cfg["proyectos"])
            or any(p == Path(s).resolve() for s in cfg["sueltos"]))


# ---------- lectura ----------

def read_text(path):
    """Devuelve (texto, codificación, truncado) o (None, None, False) si es binario."""
    with open(path, "rb") as f:
        limit = ajuste("vista_max_mb") * 1_000_000
        raw = f.read(limit + 1)
    truncated = len(raw) > limit
    if truncated:
        raw = raw[:raw.rfind(b"\n", 0, limit) + 1 or limit]
    text, enc = decode_bytes(raw)
    return (text, enc, truncated) if text is not None else (None, None, False)


def decode_bytes(raw):
    """(texto, codificación) o (None, None) si son datos binarios."""
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16", errors="replace"), "utf-16"
    if b"\0" in raw[:8192]:
        return None, None
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw[3:].decode("utf-8", errors="replace"), "utf-8-bom"
    try:
        return raw.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        # ponytail: se asume ANSI de Windows; los .bat de consola en cp850 verán mal ñ/tildes, detectar si molesta
        return raw.decode("cp1252", errors="replace"), "cp1252"


# ---------- guardar ----------

backed_up = set()  # archivos que ya tienen su .bak en esta sesión


def in_git(p):
    """¿Está dentro de un repositorio git? (Entonces no hace falta .bak: el historial ya lo guarda git.)"""
    return any((d / ".git").exists() for d in p.parents)


def backup_once(p):
    """.bak la primera vez que se guarda el archivo en esta sesión, si no está en git. Devuelve su ruta o None."""
    p = Path(p).resolve()
    if p in backed_up or in_git(p):
        return None
    bak = p.with_name(p.name + ".bak")
    shutil.copy2(p, bak)
    backed_up.add(p)
    return bak


def replace_atomic(p, src, busy):
    """Escribe de golpe (temporal + os.replace): nunca queda el archivo a medias.
    src: bytes, o una ruta que se copia con sus fechas. busy: el aviso si otro programa lo tiene abierto."""
    tmp = p.with_name(p.name + ".desklens-tmp")
    if isinstance(src, Path):
        shutil.copy2(src, tmp)
    else:
        tmp.write_bytes(src)
    try:
        os.replace(tmp, p)
    except PermissionError:
        tmp.unlink(missing_ok=True)
        raise PermissionError(busy)


def save_text(path, text, encoding, eol, mtime, force=False):
    """Guarda en el original conservando codificación y saltos de línea. Devuelve (código HTTP, datos)."""
    p = Path(path).resolve()
    current, _, truncated = read_text(p)
    if current is None or truncated:
        return 400, {"error": "Este archivo es de solo lectura en DeskLens (binario o mayor de 2 MB)."}
    st = p.stat()
    if not force and str(st.st_mtime_ns) != str(mtime):
        return 409, {"error": "conflicto", "fecha": st.st_mtime}
    text = text.replace("\r\n", "\n")
    if eol == "CRLF":
        text = text.replace("\n", "\r\n")
    try:
        if encoding == "utf-8-bom":
            data = b"\xef\xbb\xbf" + text.encode("utf-8")
        elif encoding in ("utf-8", "utf-16", "cp1252"):
            data = text.encode(encoding)
        else:
            return 400, {"error": f"Codificación desconocida: {encoding}"}
    except UnicodeEncodeError as e:
        line = text.count("\n", 0, e.start) + 1
        return 422, {"error": f"El carácter «{text[e.start]}» (línea {line}) no existe en {encoding}. "
                              "No se guardó para no romper el archivo."}
    bak = backup_once(p)
    p.write_bytes(data)
    idx_update(p)
    return 200, {"mtime": str(p.stat().st_mtime_ns), "bak": str(bak) if bak else None}


# ---------- plantillas y bitácora ----------

TEMPLATES = ["AGENTS.md", "CLAUDE.md", "GEMINI.md", "reglas.md", "bitacora.md"]


def is_project(path):
    return any(Path(path).resolve() == Path(r).resolve() for r in load_config()["proyectos"])


def template_info(project):
    """Para el aviso «Sin reglas / Sin bitácora»: qué archivos de plantillas/ tiene ya el proyecto y su texto."""
    p = Path(project)
    return {"proyecto": p.name, "tecnologia": " · ".join(project_tags(p)),
            "archivos": [{"nombre": n, "existe": (p / n).exists()} for n in TEMPLATES],
            "plantillas": {n: (ROOT / "plantillas" / n).read_text(encoding="utf-8") for n in TEMPLATES}}


def create_from_templates(project, names, descripcion, tecnologia):
    """Crea los archivos elegidos que no existan. Nunca sobrescribe (modo 'x')."""
    p = Path(project)
    values = {"proyecto": p.name, "descripcion": descripcion.strip(), "tecnologia": tecnologia.strip() or "sin definir",
              "fecha": time.strftime("%Y-%m-%d")}
    created = []
    for name in names:
        if name not in TEMPLATES:
            continue
        text = (ROOT / "plantillas" / name).read_text(encoding="utf-8")
        for k, v in values.items():
            text = text.replace("{{" + k + "}}", v)
        try:
            with open(p / name, "x", encoding="utf-8", newline="\n") as f:
                f.write(text)
            created.append(name)
        except FileExistsError:
            pass
    return created


def split_log(text):
    """Separa la bitácora en cabecera + entradas (cada una empieza con '## ')."""
    parts = re.split(r"(?m)^(?=## )", text)
    return parts[0], parts[1:]


def plan_archive(project):
    """Plan de «Archivar bitácora»: las N entradas más nuevas se quedan; el resto, agrupado por año.
    Devuelve (texto completo, cabecera, entradas que quedan, {año: entradas}) sin escribir nada."""
    text = (Path(project) / "bitacora.md").read_text(encoding="utf-8")
    head, entries = split_log(text)
    n = ajuste("bitacora_conservar")
    keep, by_year = entries[:n], {}
    for e in entries[n:]:
        m = re.match(r"## (\d{4})-", e)
        if m:
            by_year.setdefault(m.group(1), []).append(e)
        else:
            keep.append(e)  # sin fecha en el título: se queda donde está
    return text, head, keep, by_year


def archive_log(project):
    """Mueve las entradas viejas de bitacora.md a bitacora/AAAA.md (las nuevas arriba en cada año).
    Primero escribe los archivos anuales y al final recorta bitacora.md: si algo falla a medias, nada se pierde."""
    _, head, keep, by_year = plan_archive(project)
    folder = Path(project) / "bitacora"
    folder.mkdir(exist_ok=True)
    for year, moved in by_year.items():  # primero los archivos anuales: si algo falla, no se pierde nada
        f = folder / f"{year}.md"
        old_head, old = split_log(f.read_text(encoding="utf-8")) if f.exists() else (f"# Bitácora {year}\n\n", [])
        f.write_text(old_head + "".join(e if e.endswith("\n") else e + "\n" for e in moved + old),
                     encoding="utf-8", newline="\n")
    (Path(project) / "bitacora.md").write_text(head + "".join(keep), encoding="utf-8", newline="\n")
    return {y: len(m) for y, m in by_year.items()}


def status(project):
    """Avisos de un proyecto para el árbol: «Sin reglas», «Sin bitácora», «Bitácora grande» o «En orden»."""
    p = Path(project)
    if not p.is_dir():
        return ["No encontrado"]
    avisos = []
    if not (p / "reglas.md").exists():  # AGENTS.md/CLAUDE.md/GEMINI.md son opcionales: DeskLens no los necesita
        avisos.append("Sin reglas")
    bit = p / "bitacora.md"
    if not bit.exists():
        avisos.append("Sin bitácora")
    else:
        with bit.open(encoding="utf-8", errors="ignore") as f:
            if sum(1 for _ in f) > ajuste("bitacora_max_lineas"):
                avisos.append("Bitácora grande")
    return avisos


CODE_MTIME = Path(__file__).stat().st_mtime_ns  # desklens.pyw al arrancar: si cambia, hay que reiniciar DeskLens


def estado():
    """Lo que dibuja la barra lateral: proyectos con sus avisos y archivos sueltos (con su estado de git).
    reiniciar: desklens.pyw cambió desde que arrancó este servidor (index.html se lee nuevo; el servidor, no)."""
    cfg = load_config()
    return {
        "reiniciar": Path(__file__).stat().st_mtime_ns != CODE_MTIME,
        "proyectos": [{"ruta": r, "nombre": Path(r).name or r, "avisos": status(r)} for r in cfg["proyectos"]],
        "sueltos": [{"ruta": s, "nombre": Path(s).name, "existe": Path(s).is_file(), "git": git_state(s)}
                    for s in cfg["sueltos"]],
    }


def list_dir(path):
    """Contenido de una carpeta para el árbol: sin las carpetas ocultas (HIDDEN), carpetas primero y por nombre."""
    items = []
    for e in Path(path).iterdir():
        if e.name in HIDDEN:
            continue
        try:
            d = e.is_dir()
            items.append({"nombre": e.name, "ruta": str(e), "dir": d, "git": None if d else git_state(e),
                          "fecha": e.stat().st_mtime})  # para ordenar por fecha de modificación
        except OSError:
            pass
    return sorted(items, key=lambda i: (not i["dir"], i["nombre"].lower()))


# ---------- explorador para añadir (solo nombres: nunca lee contenido fuera de lo añadido) ----------

MARKERS = [("artisan", "Laravel"), ("composer.json", "PHP"), ("package.json", "Node"),
           ("requirements.txt", "Python"), ("pyproject.toml", "Python"), ("setup.py", "Python"), (".git", "git")]
HEAVY = {"node_modules", "vendor", ".venv", "venv", "dist", "build"}


def drives():
    """Unidades para el explorador de «Añadir»: C:\\, D:\\… en Windows; «/» en macOS y Linux."""
    if not WINDOWS:  # macOS y Linux: una sola raíz (los discos cuelgan de /Volumes o /media)
        return ["/"]
    out = []
    for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        try:
            if Path(f"{letter}:\\").exists():
                out.append(f"{letter}:\\")
        except OSError:
            pass
    return out


def project_tags(path):
    """Tecnologías que se reconocen por sus archivos (MARKERS): Laravel, Node, Python, git… Laravel ya implica PHP."""
    try:
        names = set(os.listdir(path))
    except OSError:
        return []
    tags = []
    for marker, tag in MARKERS:
        if marker in names and tag not in tags and not (tag == "PHP" and "Laravel" in tags):
            tags.append(tag)
    return tags


def explore(ruta):
    """Datos del explorador «Añadir proyecto o archivos»: unidades, lugares (Inicio, Escritorio…), proyectos
    añadidos y el contenido de `ruta`, con cada elemento marcado como «añadido», «dentro» (de un proyecto) o libre."""
    cfg = load_config()
    projects = [Path(r).resolve() for r in cfg["proyectos"]]
    loose = {Path(s).resolve() for s in cfg["sueltos"]}

    def state(p, is_dir):
        """«añadido» si ya es un proyecto o suelto; «dentro» si cuelga de un proyecto; None si no."""
        if (is_dir and p in projects) or (not is_dir and p in loose):
            return "añadido"
        if any(p.is_relative_to(r) for r in projects):
            return "dentro"
        return None

    units = drives()
    home = Path.home()
    places = [{"nombre": "Inicio", "ruta": str(home)}]
    for name, label in (("Desktop", "Escritorio"), ("Documents", "Documentos"), ("Downloads", "Descargas")):
        # OneDrive puede redirigirlas; en Linux en español se llaman como la etiqueta
        p = next((c for c in (home / name, home / "OneDrive" / name, home / label) if c.is_dir()), None)
        if p:
            places.append({"nombre": label, "ruta": str(p)})
    side = {"unidades": units, "lugares": places,
            "proyectos": [{"nombre": Path(r).name or r, "ruta": str(r)} for r in cfg["proyectos"]]}
    if not ruta or not Path(ruta).is_dir():  # la última ubicación pudo borrarse o desconectarse
        return {**side, "ruta": "", "padre": None, "migas": [], "items": [
            {"nombre": d, "ruta": d, "dir": True, "tipo": [], "estado": state(Path(d), True), "avisos": []} for d in units]}
    base = Path(ruta).resolve()
    items = []
    with os.scandir(base) as it:
        entries = sorted(it, key=lambda e: (not e.is_dir(), e.name.lower()))
    for e in entries:
        if e.name in HIDDEN or e.name.startswith("$") or e.name == "System Volume Information":
            continue
        try:
            is_dir = e.is_dir()
        except OSError:
            continue
        p = Path(e.path)
        item = {"nombre": e.name, "ruta": str(p), "dir": is_dir, "estado": state(p, is_dir),
                "atenuada": e.name in HEAVY, "tipo": [], "avisos": []}
        if is_dir and len(items) < 300 and not item["atenuada"]:  # ponytail: sin detección más allá de 300 carpetas
            item["tipo"] = project_tags(p)
            item["avisos"] = status(p)
        items.append(item)
    migas = [{"nombre": base.anchor, "ruta": base.anchor}]
    for part in base.parts[1:]:
        migas.append({"nombre": part, "ruta": str(Path(migas[-1]["ruta"]) / part)})
    return {**side, "ruta": str(base), "padre": str(base.parent) if base.parent != base else "", "migas": migas,
            "items": items, "tipo": project_tags(base), "avisos": status(base),
            "estado": state(base, True)}


# ---------- consola: ejecutar scripts y pruebas ----------

def oem_encoding():
    """Codificación de la consola de Windows (cp850, cp437…): la que usan los .bat y PowerShell al escribir."""
    try:
        import ctypes
        return f"cp{ctypes.windll.kernel32.GetOEMCP()}"
    except (ImportError, AttributeError, OSError):
        return "utf-8"


def find_venv_python(p, gui=False):
    """Python del entorno virtual del proyecto (.venv o venv, subiendo carpetas), para ejecutar sus .py con sus paquetes."""
    sub, exe = ("Scripts", "pythonw.exe" if gui else "python.exe") if WINDOWS else ("bin", "python")
    for d in p.parents:
        for name in (".venv", "venv"):
            if (d / name / sub / exe).exists():
                return str(d / name / sub / exe)
    return None


def git_bash():
    """bash.exe que trae Git para Windows (para los .sh); el «bash» del PATH puede ser el de WSL, que no ve las rutas igual."""
    git = shutil.which("git")  # 'bash' en el PATH puede ser el de WSL; se usa el que trae Git
    if git:
        for cand in (Path(git).parents[1] / "bin" / "bash.exe", Path(git).parents[1] / "usr" / "bin" / "bash.exe"):
            if cand.exists():
                return str(cand)
    return None


def command_for(path):
    """(argumentos, codificación de la salida) para ejecutar el archivo, o (None, motivo)."""
    p = Path(path)
    ext = p.suffix.lower()
    here = Path(sys.executable).parent  # con desklens.pyw, sys.executable es pythonw.exe
    if ext in (".py", ".pyw"):
        gui = ext == ".pyw"
        exe = find_venv_python(p, gui) or (str(here / ("pythonw.exe" if gui else "python.exe")) if WINDOWS else sys.executable)
        return [exe, str(p)], "utf-8"
    if ext in (".bat", ".cmd", ".vbs") and not WINDOWS:
        return None, "Solo se ejecuta en Windows"
    if ext == ".ps1" and not WINDOWS:  # PowerShell 7 existe para macOS y Linux
        return (["pwsh", "-NoProfile", "-File", str(p)], "utf-8") if shutil.which("pwsh") else (None, "PowerShell (pwsh) no está instalado")
    if ext in (".bat", ".cmd"):
        return ["cmd", "/c", str(p)], oem_encoding()
    if ext == ".ps1":
        return ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(p)], oem_encoding()
    if ext == ".vbs":
        return ["cscript", "//nologo", str(p)], oem_encoding()
    if ext in (".js", ".mjs", ".cjs"):
        return ([shutil.which("node"), str(p)], "utf-8") if shutil.which("node") else (None, "Node no está instalado")
    if ext == ".php":
        return ([shutil.which("php"), str(p)], "utf-8") if shutil.which("php") else (None, "PHP no está instalado")
    if ext in (".sh", ".bash"):
        bash = git_bash() if WINDOWS else shutil.which("bash")
        return ([bash, str(p)], "utf-8") if bash else (None, "Git Bash no está instalado")
    return None, None  # no es ejecutable


def run_info(path):
    """Para el botón ▶: la orden que se ejecutaría y en qué carpeta, o el motivo por el que no se puede."""
    args, enc = command_for(path)
    if args is None:
        return {"error": enc} if enc else None
    return {"texto": subprocess.list2cmdline([Path(args[0]).name if os.sep in args[0] else args[0], *args[1:]]),
            "carpeta": str(Path(path).parent)}


def detect_tests(project):
    """Comando de pruebas que se propone según el proyecto: Laravel, npm (si package.json tiene «test») o pytest."""
    p = Path(project)
    if (p / "artisan").exists():
        return "php artisan test"
    try:
        if "test" in json.loads((p / "package.json").read_text(encoding="utf-8")).get("scripts", {}):
            return "npm test"
    except (OSError, ValueError, AttributeError):
        pass
    if (p / "pytest.ini").exists() or (p / "tests").is_dir():
        py = find_venv_python(p / "x")
        return f'"{py}" -m pytest' if py else "python -m pytest"
    return ""


runs = {}
runs_lock = threading.Lock()


class Run:
    """Un proceso en ejecución; su salida se guarda en trozos que la interfaz va pidiendo."""

    def __init__(self, args, cwd, encoding, label, env=None):
        """Lanza el proceso con su salida y su error por tuberías; dos hilos los leen sin bloquear y un tercero
        espera al final para guardar el código de salida y la duración. env: variables extra (p. ej. para git)."""
        self.args, self.cwd, self.label, self.encoding = args, cwd, label, encoding  # args: lista, o texto para cmd /c
        self.chunks, self.code, self.start, self.end = [], None, time.time(), None
        self.lock = threading.Lock()
        env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1", **(env or {})}
        self.proc = subprocess.Popen(args, cwd=cwd, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, creationflags=NO_WINDOW,
                                     start_new_session=not WINDOWS)  # macOS/Linux: su propio grupo, para detener también los hijos
        readers = [threading.Thread(target=self.read, args=(s, k, encoding), daemon=True)
                   for s, k in ((self.proc.stdout, "out"), (self.proc.stderr, "err"))]
        for t in readers:
            t.start()

        def wait():
            """Cuando terminan los dos lectores (ya no queda salida por leer), se guarda el código de salida."""
            for t in readers:
                t.join()
            self.code = self.proc.wait()
            self.end = time.time()
        threading.Thread(target=wait, daemon=True).start()

    def read(self, stream, kind, encoding):
        """Lee la salida a trozos de 4 KB y la decodifica de forma incremental (un carácter puede quedar partido entre dos trozos)."""
        dec = codecs.getincrementaldecoder(encoding)(errors="replace")
        while chunk := stream.read1(4096):
            text = dec.decode(chunk).replace("\r\n", "\n")
            if text:
                with self.lock:
                    self.chunks.append([kind, text])

    def output(self, since):
        """Los trozos desde `since` (la ventana pide solo lo nuevo), si terminó, el código de salida y la duración."""
        with self.lock:
            return {"trozos": self.chunks[since:], "total": len(self.chunks), "fin": self.end is not None,
                    "codigo": self.code, "dur": round((self.end or time.time()) - self.start, 1)}

    def send(self, text):
        """Una línea de la caja de entrada de la consola al proceso (input() de Python, set /p de un .bat…)."""
        try:
            self.proc.stdin.write((text + "\r\n").encode(self.encoding, errors="replace"))
            self.proc.stdin.flush()
        except OSError:
            pass

    def kill(self):
        """Detener: el proceso y sus hijos (taskkill /T en Windows; en macOS y Linux, su grupo de procesos)."""
        if self.end is None and WINDOWS:  # /T: también los procesos hijos (un .bat que lanza otros programas)
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(self.proc.pid)], capture_output=True,
                           creationflags=NO_WINDOW)
        elif self.end is None:
            try:
                os.killpg(self.proc.pid, signal.SIGKILL)
            except OSError:
                pass


def start_run(args, cwd, encoding, label, env=None):
    """Arranca un proceso y lo registra en `runs` con un id para que la consola pida su salida."""
    r = Run(args, cwd, encoding, label, env)
    with runs_lock:
        rid = str(len(runs) + 1)
        runs[rid] = r
    return rid


def open_console(rid):
    """Para programas interactivos: misma orden en una consola real."""
    r = runs[rid]
    if WINDOWS:
        line = r.args if isinstance(r.args, str) else subprocess.list2cmdline(r.args)
    else:
        line = r.args[-1] if r.args[:2] == ["bash", "-lc"] else shlex.join(r.args)
    open_terminal(line, r.cwd, "DeskLens")


def open_terminal(line, cwd, title):
    """Una terminal del sistema que ejecuta la orden y se queda abierta."""
    if WINDOWS:
        return subprocess.Popen(f'start "{title}" cmd /k {line}', shell=True, cwd=cwd)
    if MAC:
        script = f"cd {shlex.quote(str(cwd))}; {line}"
        return subprocess.Popen(["osascript", "-e", f'tell application "Terminal" to do script {json.dumps(script)}',
                                 "-e", 'tell application "Terminal" to activate'])
    keep = f"{line}; exec bash"
    for term, flag in (("x-terminal-emulator", "-e"), ("gnome-terminal", "--"), ("konsole", "-e"), ("xfce4-terminal", "-x"), ("xterm", "-e")):
        if shutil.which(term):
            return subprocess.Popen([term, flag, "bash", "-c", keep], cwd=cwd)
    raise RuntimeError("No se encontró ninguna terminal (x-terminal-emulator, gnome-terminal, konsole, xterm…)")


# ---------- IA: CLIs con la suscripción de cada uno (DeskLens no guarda claves) ----------

AIS = {
    "claude": {"nombre": "Claude", "instalar": "npm install -g @anthropic-ai/claude-code", "login": "claude",
               "sesion": [".claude/.credentials.json"], "env": "ANTHROPIC_API_KEY"},
    "codex": {"nombre": "Codex", "instalar": "npm install -g @openai/codex", "login": "codex login",
              "sesion": [".codex/auth.json"], "env": "OPENAI_API_KEY"},
    "gemini": {"nombre": "Gemini", "instalar": "npm install -g @google/gemini-cli", "login": "gemini",
               "sesion": [".gemini/oauth_creds.json"], "env": "GEMINI_API_KEY"},
}
# Carpeta neutra: así los CLIs no cargan AGENTS.md, la bitácora ni archivos del proyecto en cada petición
IA_DIR = Path(tempfile.gettempdir()) / "desklens-ia"
SENSITIVE = {".env", ".pem", ".key", ".asc", ".crt", ".cer", ".csr", ".p12", ".pfx", ".gpg", ".pgp", ".der", ".p7b", ".p7c",
             ".ppk", ".jks", ".keystore", ".kdbx", ".ovpn"}
# archivos de configuración con claves o contraseñas, por nombre
SENSITIVE_NAMES = {".npmrc", ".pypirc", ".netrc", ".htpasswd", ".git-credentials", "id_rsa", "id_dsa", "id_ecdsa",
                   "id_ed25519", "credentials", "credentials.json", "secrets.json", "secrets.yml", "secrets.yaml",
                   "wp-config.php", "auth.json", "service-account.json", ".dockercfg"}
ia_cache = {}


def is_sensitive(path):
    """Archivo con claves o contraseñas (.env, .pem, id_rsa, credentials.json…): 🔒 en el árbol y aviso antes de enviarlo a la IA."""
    name = Path(path).name.lower()
    return name.startswith(".env") or name in SENSITIVE_NAMES or Path(name).suffix in SENSITIVE


def blocked_for_ai(path):
    """🔒 solo bloquea el envío a la IA si el usuario lo pidió (⚙ Ajustes); por defecto se permite: son sus archivos."""
    return is_sensitive(path) and not ajuste("ia_permitir_sensibles")


def ia_prefs():
    # el límite vive en Ajustes (un solo valor para «Conectar IA» y ⚙ Ajustes)
    """Preferencias de IA para la ventana: la predeterminada, el límite de tokens y la carga fija medida de cada CLI."""
    ia = load_config().get("ia", {})
    # carga fija medida con «Probar»: solo vale la medida con el modo mínimo actual (CARGA_V);
    # las antiguas (≈ 27.000–41.000 tokens del modo completo) se ignoran hasta volver a medir
    carga = {k: v["tokens"] for k, v in ia.get("carga", {}).items() if isinstance(v, dict) and v.get("v") == CARGA_V}
    return {"predeterminada": "gemini", **ia, "carga": carga, "limite": ajuste("ia_limite_tokens")}


CARGA_V = 2  # súbelo si cambian las opciones con que se lanza un CLI


def ia_status(refresh=False):
    """Instalada y versión (sin gastar tokens). La sesión se deduce del archivo de login de cada CLI."""
    if refresh or not ia_cache:
        for key, a in AIS.items():
            exe, version = shutil.which(key), ""
            if exe:
                try:
                    r = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=20,
                                       creationflags=NO_WINDOW)
                    version = (r.stdout or r.stderr).strip().splitlines()[0][:40] if (r.stdout or r.stderr).strip() else ""
                except (OSError, subprocess.TimeoutExpired):
                    pass
            # ponytail: sesión deducida por archivo de credenciales; si un CLI cambia de sitio, "Probar" lo confirma
            session = bool(os.environ.get(a["env"])) or any((Path.home() / s).exists() for s in a["sesion"])
            ia_cache[key] = {"id": key, "nombre": a["nombre"], "instalada": bool(exe), "version": version,
                             "sesion": session, "instalar": a["instalar"]}
    return {"ias": list(ia_cache.values()), "pref": ia_prefs()}


def estimate_tokens(text):
    return -(-len(text) // 4)  # ponytail: aproximación de ~4 caracteres por token; los tokens reales llegan con la respuesta


def claude_result(out):
    """El objeto «result» de Claude: toda la salida (--output-format json) o su última línea (stream-json, con imágenes)."""
    for line in reversed(out.strip().splitlines()):
        d = json.loads(line)
        if d.get("type") == "result":
            return d
    return json.loads(out)


def parse_ai(ai, out):
    """(respuesta, tokens) de la salida JSON de cada CLI. Si el formato cambia, devuelve el texto tal cual."""
    try:
        if ai == "claude":
            d = claude_result(out)
            u = d.get("usage") or {}
            inp = sum(u.get(k) or 0 for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
            return d.get("result", ""), {"entrada": inp, "salida": u.get("output_tokens") or 0}
        if ai == "gemini":
            d = json.loads(out)
            models = (d.get("stats") or {}).get("models") or {}
            tok = [m.get("tokens") or {} for m in models.values()]
            usage = {"entrada": sum(t.get("prompt") or 0 for t in tok),
                     "salida": sum(t.get("candidates") or 0 for t in tok)} if tok else None
            return d.get("response", ""), usage
        if ai == "codex":  # JSONL de eventos: se queda con el último mensaje y el uso de tokens
            text, usage = "", None
            for line in out.splitlines():
                try:
                    ev = json.loads(line)
                except ValueError:
                    continue
                item = ev.get("item") or {}
                if item.get("type") in ("agent_message", "assistant_message") and item.get("text"):
                    text = item["text"]
                if ev.get("usage"):
                    u = ev["usage"]
                    usage = {"entrada": u.get("input_tokens") or 0, "salida": u.get("output_tokens") or 0}
            if text:
                return text, usage
    except (ValueError, AttributeError, TypeError):
        pass
    return out.strip(), None


def ask_ai(ai, prompt, resume=None, images=()):
    """resume: id de sesión de Claude para continuar una conversación (Claude guarda el historial y lo cachea).
    images: [{"media": "image/jpeg", "data": base64}] que la IA ve (👁); solo con Claude."""
    exe = shutil.which(ai)
    if ai not in AIS or not exe:
        raise RuntimeError(f"{AIS.get(ai, {}).get('nombre', ai)} no está instalado")
    if images and ai != "claude":
        raise RuntimeError(f"Desde DeskLens solo Claude puede ver imágenes: cambia a Claude o quita 👁 de la imagen")
    IA_DIR.mkdir(exist_ok=True)
    # Claude en modo mínimo: sin herramientas, sin MCP, sin ajustes/hooks/plugins de usuario y con prompt propio.
    # Medido 2026-11-01 con "Responde solo: OK": 41.091 tokens de entrada → 851. (--bare exige clave API, no sirve.)
    args = {"claude": [exe, "-p", "--output-format", "json", "--tools", "", "--strict-mcp-config",
                       "--disable-slash-commands", "--setting-sources", "",
                       "--system-prompt", "Sigue las instrucciones del usuario al pie de la letra."],
            "codex": [exe, "exec", "--skip-git-repo-check", "--sandbox", "read-only", "--json", "-"],
            "gemini": [exe, "--output-format", "json"]}[ai]
    if ai == "claude" and resume:
        args += ["--resume", resume]
    if images:  # mensaje en stream-json: texto + imágenes (probado 2026-11-02 con la suscripción)
        args[args.index("json")] = "stream-json"
        args += ["--input-format", "stream-json", "--verbose"]
        prompt = json.dumps({"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": prompt}] + [
            {"type": "image", "source": {"type": "base64", "media_type": i["media"], "data": i["data"]}} for i in images]}})
    r = subprocess.run(args, input=prompt, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=ajuste("ia_espera_seg"), cwd=IA_DIR, creationflags=NO_WINDOW)
    text, usage = parse_ai(ai, r.stdout)
    if r.returncode != 0 or not text:
        raise RuntimeError((r.stderr or r.stdout).strip()[-800:] or f"{AIS[ai]['nombre']} no respondió (código {r.returncode})")
    session = None
    if ai == "claude":
        try:
            session = claude_result(r.stdout).get("session_id")
        except (ValueError, AttributeError):
            pass
    return {"texto": text, "tokens": usage, "session": session}


# ---------- conversaciones con archivos adjuntos ----------

CONV_DIR = ROOT / "historial" / "conversaciones"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def docx_text(path):
    """Texto de un .docx (párrafos y tablas) leyendo su XML, sin librerías externas."""
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    lines = []
    for p in root.iter(W + "p"):
        parts = []
        for el in p.iter():
            if el.tag == W + "t":
                parts.append(el.text or "")
            elif el.tag == W + "tab":
                parts.append("\t")
            elif el.tag in (W + "br", W + "cr"):
                parts.append("\n")
        lines.append("".join(parts))
    return "\n".join(lines).strip()


def ooxml_text(src, ext):
    """Texto de un .xlsx (celdas por hoja, separadas por tabulador) o un .pptx (texto por diapositiva)."""
    A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
    S = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    num = lambda n: int(re.search(r"(\d+)\.xml$", n).group(1))
    with zipfile.ZipFile(src) as z:
        names = z.namelist()
        if ext == ".pptx":
            slides = sorted((n for n in names if re.match(r"ppt/slides/slide\d+\.xml$", n)), key=num)
            return "\n\n".join(f"[Diapositiva {num(n)}]\n" + "\n".join(
                "".join(t.text or "" for t in p.iter(A + "t")) for p in ET.fromstring(z.read(n)).iter(A + "p")).strip()
                for n in slides).strip()
        shared = [] if "xl/sharedStrings.xml" not in names else [
            "".join(t.text or "" for t in si.iter(S + "t")) for si in ET.fromstring(z.read("xl/sharedStrings.xml")).iter(S + "si")]
        out = []
        for n in sorted((n for n in names if re.match(r"xl/worksheets/sheet\d+\.xml$", n)), key=num):
            rows = []
            for row in ET.fromstring(z.read(n)).iter(S + "row"):
                cells = []
                for c in row.iter(S + "c"):
                    v, t = c.find(S + "v"), c.get("t")
                    if t == "inlineStr":
                        cells.append("".join(x.text or "" for x in c.iter(S + "t")))
                    elif v is not None:
                        cells.append(shared[int(v.text)] if t == "s" else v.text or "")
                rows.append("\t".join(cells))
            out.append(f"[Hoja {num(n)}]\n" + "\n".join(rows))
        return "\n\n".join(out).strip()


def image_size(b):
    """(ancho, alto) en píxeles de un PNG, GIF, BMP, WebP o JPEG leyendo su cabecera; None si no se reconoce."""
    if b[:8] == b"\x89PNG\r\n\x1a\n":
        return int.from_bytes(b[16:20], "big"), int.from_bytes(b[20:24], "big")
    if b[:6] in (b"GIF87a", b"GIF89a"):
        return int.from_bytes(b[6:8], "little"), int.from_bytes(b[8:10], "little")
    if b[:2] == b"BM":
        return int.from_bytes(b[18:22], "little"), abs(int.from_bytes(b[22:26], "little", signed=True))
    if b[:4] == b"RIFF" and b[8:12] == b"WEBP":
        if b[12:16] == b"VP8X":
            return int.from_bytes(b[24:27], "little") + 1, int.from_bytes(b[27:30], "little") + 1
        if b[12:16] == b"VP8 ":
            return int.from_bytes(b[26:28], "little") & 0x3FFF, int.from_bytes(b[28:30], "little") & 0x3FFF
        if b[12:16] == b"VP8L":
            v = int.from_bytes(b[21:25], "little")
            return (v & 0x3FFF) + 1, ((v >> 14) & 0x3FFF) + 1
    if b[:2] == b"\xff\xd8":  # JPEG: recorre los segmentos hasta el SOF
        i = 2
        while i + 9 < len(b):
            if b[i] != 0xFF:
                i += 1
                continue
            m, n = b[i + 1], int.from_bytes(b[i + 2:i + 4], "big")
            if 0xC0 <= m <= 0xCF and m not in (0xC4, 0xC8, 0xCC):
                return int.from_bytes(b[i + 7:i + 9], "big"), int.from_bytes(b[i + 5:i + 7], "big")
            i += 2 + n
    return None


def human_size(n):
    """Tamaño legible para la IA: «85 KB», «1.6 MB»."""
    return f"{n / 1_000_000:.1f} MB" if n >= 1_000_000 else f"{max(1, round(n / 1000))} KB"


def extract_text(path, data=None):
    """Lo que recibe la IA de un archivo: su texto o, si no lo tiene (imagen, audio, .zip…), una referencia
    con nombre, tamaño y ruta. data: contenido de un archivo soltado desde Windows (sin ruta)."""
    p = Path(path)
    ext = p.suffix.lower()
    src = io.BytesIO(data) if data is not None else p
    if ext == ".docx":
        return {"texto": docx_text(src)}
    if ext in (".xlsx", ".xlsm", ".pptx"):
        return {"texto": ooxml_text(src, ".pptx" if ext == ".pptx" else ".xlsx")}
    text = read_text(p)[0] if data is None else decode_bytes(data)[0]
    if text is not None:
        return {"texto": text}
    if ext == ".pdf":
        raise ValueError("Los PDF se leen por páginas en la ventana de DeskLens: di «página 40» o «páginas 27 a 35»")
    size = len(data) if data is not None else p.stat().st_size
    with (io.BytesIO(data) if data is not None else open(p, "rb")) as f:
        dims = image_size(f.read(65536))
    where = f"ruta: {p}" if data is None else "soltado desde Windows, sin ruta"
    if dims:
        return {"texto": f"[Imagen «{p.name}» · {dims[0]}×{dims[1]} px · {human_size(size)} · {where}. "
                         "No la ves: solo su nombre (el usuario puede enviártela con 👁).]",
                "ref": True, "imagen": True, "ancho": dims[0], "alto": dims[1]}
    return {"texto": f"[Archivo «{p.name}» · {human_size(size)} · {where}. No es de texto: solo recibes su nombre.]", "ref": True}


# Detección de archivos nombrados en el mensaje (sin IA): "lee montaña narrativa y preguntas y datos de contexto"
TEXT_EXT = {".md", ".markdown", ".txt", ".docx", ".pdf", ".csv", ".tsv", ".json", ".yaml", ".yml", ".xml", ".html", ".htm",
            ".py", ".php", ".js", ".ts", ".sql", ".ini", ".log", ".bat", ".cmd", ".ps1", ".rst", ".tex"}


def plain_words(text):
    """Palabras sin tildes ni mayúsculas, solo letras y números: «Preguntas y Datos» → ['preguntas', 'y', 'datos']."""
    text = unicodedata.normalize("NFD", text.lower())
    return re.findall(r"[a-z0-9]+", "".join(c for c in text if unicodedata.category(c) != "Mn"))


def longest_run(a, b):
    """Palabras seguidas en común más larga entre dos listas (p. ej. 'preguntas y datos de contexto')."""
    best, prev = 0, [0] * (len(b) + 1)
    for x in a:
        cur = [0] * (len(b) + 1)
        for j, y in enumerate(b):
            if x == y:
                cur[j + 1] = prev[j] + 1
                best = max(best, cur[j + 1])
        prev = cur
    return best


def project_files(base, depth=3, cap=3000):
    """Archivos de texto del proyecto que la IA puede recibir si se nombran en el mensaje.
    ponytail: hasta 3 niveles y 3000 archivos, sin node_modules, vendor… (HEAVY); más hondo no se encuentra."""
    out = []
    for root, dirs, files in os.walk(base):
        rel = Path(root).relative_to(base)
        dirs[:] = [] if len(rel.parts) >= depth else [d for d in dirs if d not in HIDDEN and d not in HEAVY]
        out += [Path(root) / f for f in files if Path(f).suffix.lower() in TEXT_EXT]
        if len(out) >= cap:
            break
    return out[:cap]


def find_mentioned(mensaje, ruta):
    """Archivos del proyecto (o de la carpeta del archivo abierto) que el mensaje nombra."""
    if not ruta or not allowed(ruta):
        return []
    p = Path(ruta)
    base = project_of(p) or (p if p.is_dir() else p.parent)
    files = [f for f in project_files(base) if not is_sensitive(f) and f.name.lower() != "reglas.md"]  # reglas: siempre
    rest = mensaje.lower()
    exact = [f for f in files if f.name.lower() in rest]
    for f in exact:  # un nombre escrito completo no debe arrastrar a sus "parecidos"
        rest = rest.replace(f.name.lower(), " ")
    found, msg_words = [(99, f) for f in exact], plain_words(rest)
    for f in files:
        if f in exact:
            continue
        stem = plain_words(f.stem)
        run = longest_run(stem, msg_words)
        if run >= 2 and run * 2 >= len([w for w in stem if len(w) > 2]):
            found.append((run, f))
    found.sort(key=lambda x: -x[0])
    return [{"ruta": str(f), "nombre": f.name} for _, f in found[:6]]


def conv_path(cid):
    """Ruta del JSON de una conversación; el id solo puede ser hexadecimal (nada de ../ desde la ventana)."""
    if not re.fullmatch(r"[0-9a-f]+", cid or ""):
        raise ValueError("conversación no válida")
    return CONV_DIR / f"{cid}.json"


def conv_load(cid):
    return json.loads(conv_path(cid).read_text(encoding="utf-8"))


def conv_save(conv):
    """Guarda la conversación entera (mensajes, adjuntos con su texto, sesión de Claude) en historial/conversaciones."""
    CONV_DIR.mkdir(parents=True, exist_ok=True)
    conv_path(conv["id"]).write_text(json.dumps(conv, ensure_ascii=False), encoding="utf-8")


def conv_public(conv):
    """Sin el texto de los adjuntos (puede ser grande): solo nombre, descripción y tokens."""
    script = Path(conv["proyecto"]) / "verificar_citas.py" if conv.get("proyecto") else None
    return {**conv, "adjuntos": [{k: a.get(k) for k in ("nombre", "desc", "tokens")} for a in conv["adjuntos"]],
            "verificador": str(script) if script and script.is_file() else ""}


def conv_list():
    """Conversaciones para el selector del chat, la más reciente primero (sin mensajes: solo título, fecha, IA y vínculo)."""
    out = []
    for f in sorted(CONV_DIR.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True) if CONV_DIR.exists() else []:
        try:
            c = json.loads(f.read_text(encoding="utf-8"))
            out.append({"id": c["id"], "titulo": c["titulo"], "fecha": c["fecha"], "ia": c["ia"], "n": len(c["mensajes"]),
                        "vinculo": c.get("vinculo", "")})
        except (ValueError, KeyError):
            pass
    return out


CONV_INTRO = """Conversación de trabajo. Responde en español y en Markdown.
- DeskLens (el programa del usuario) te adjunta los archivos que el usuario abre o nombra; las páginas de un PDF llegan marcadas [Página N]. Usa los ARCHIVOS ADJUNTOS como fuente; si algo no está en ellos, dilo en vez de inventarlo.
- No tienes herramientas (no lees archivos ni ejecutas comandos). Para verificar citas, el usuario usa su script y te pega el resultado.
- Si el usuario pide el resultado en un archivo (por ejemplo "muéstramelo en un .md" o "créalo en Word / PDF"), escribe el contenido completo así y DeskLens lo creará y abrirá:
<<<ARCHIVO nombre.ext
contenido
ARCHIVO>>>
  Para .docx y .pdf escribe el contenido en Markdown (títulos, negritas, listas, tablas): DeskLens lo convierte. Para .md, .txt, .csv, .html, .json, .py, etc., escribe el contenido final tal cual. DeskLens no puede crear .xlsx, .pptx ni imágenes: propone .csv o .docx.
- Para cambiar el ARCHIVO ABIERTO, usa bloques (BUSCAR debe ser texto exacto y único del archivo):
<<<<<<< BUSCAR
texto actual
=======
texto nuevo
>>>>>>> REEMPLAZAR"""


DOCX_HINT = """Es un documento de Word: no lo reescribas. Para cambiar su formato o su texto, responde con bloques así (DeskLens los aplica cuando el usuario pulsa Aplicar):
<<<DOCX {"buscar": "texto exacto del documento", "color": "rojo"} DOCX>>>
Claves: buscar (obligatoria, texto exacto), color (rojo/azul/verde/… o FF0000), negrita, cursiva, subrayado (true/false), tamano (puntos), resaltado (amarillo/verde/…/no), fuente, reemplazar (texto nuevo), todas (true = todas las apariciones). Uno o varios bloques.
Para insertar una imagen adjunta (en su propio párrafo, centrada): {"imagen": "ruta o nombre de la imagen adjunta", "buscar": "texto exacto del párrafo de referencia", "posicion": "antes" o "despues", "ancho_cm": 12 (opcional; por defecto su tamaño, máx. 16)}."""


def abierto_hint(abierto):
    """Cada turno: qué archivo tiene abierto el usuario (y, si es Word, cómo cambiarlo)."""
    if not abierto:
        return ""
    name = Path(abierto).name
    return f"ARCHIVO ABIERTO: {name}" + ("\n" + DOCX_HINT if name.lower().endswith(".docx") else "")


def conv_prompt(intro, reglas, adjuntos, historial, mensaje, abierto=""):
    """Texto que recibe la IA: instrucciones, reglas del proyecto, adjuntos, conversación previa, archivo abierto
    y el mensaje. Con la sesión de Claude ya abierta solo van los adjuntos nuevos y el mensaje."""
    parts = [intro] if intro else []
    if reglas.strip():
        parts.append("REGLAS DEL PROYECTO (respétalas):\n" + reglas.strip())
    for a in adjuntos:
        parts.append(f"=== ARCHIVO ADJUNTO: {a['nombre']}" + (f" ({a['desc']})" if a.get("desc") else "") + f" ===\n{a['texto']}")
    if historial:
        parts.append("CONVERSACIÓN PREVIA:\n" + "\n\n".join(
            ("Usuario: " if m["rol"] == "tu" else "Asistente: ") + m["texto"] for m in historial))
    if abierto_hint(abierto):
        parts.append(abierto_hint(abierto))
    parts.append("MENSAJE:\n" + mensaje.strip())
    return "\n\n".join(parts)


def conv_send(data):
    """Un turno de conversación. Claude continúa su sesión (--resume): los adjuntos se envían una sola vez.
    Las demás IAs no guardan sesión desde DeskLens: se les reenvía el contexto y la conversación cada turno."""
    ia, mensaje = data.get("ia"), data.get("mensaje", "")
    nuevos = [{"nombre": a["nombre"], "desc": a.get("desc", ""), "texto": a["texto"],
               "tokens": estimate_tokens(a["texto"])} for a in data.get("adjuntos", [])]
    if data.get("id"):
        conv = conv_load(data["id"])
    else:
        ruta = data.get("ruta") or ""
        proj = project_of(ruta) if ruta else None
        conv = {"id": f"{time.time_ns():x}", "titulo": mensaje.strip().splitlines()[0][:60] if mensaje.strip() else "Conversación",
                "fecha": time.strftime("%Y-%m-%d %H:%M"), "ia": ia, "session": None, "proyecto": str(proj) if proj else "",
                "mensajes": [], "adjuntos": [],
                "vinculo": data.get("vinculo") or ""}  # pestaña (archivo) a la que pertenece el chat; "" = general
    reglas = ""
    if conv["proyecto"] and (Path(conv["proyecto"]) / "reglas.md").is_file():
        reglas = read_text(Path(conv["proyecto"]) / "reglas.md")[0] or ""
    resume = conv["session"] if ia == "claude" and conv["ia"] == "claude" else None
    abierto = data.get("abierto") or ""
    if resume:  # Claude ya tiene reglas, adjuntos anteriores e historial en su sesión
        prompt = conv_prompt("", "", nuevos, [], mensaje, abierto)
    else:
        prompt = conv_prompt(CONV_INTRO, reglas, conv["adjuntos"] + nuevos, conv["mensajes"], mensaje, abierto)
    images = [a["imagen"] for a in data.get("adjuntos", []) if a.get("imagen")]  # 👁: no se guardan en el historial
    r = ask_ai(ia, prompt, resume, images)
    conv["adjuntos"] += nuevos
    conv["mensajes"] += [{"rol": "tu", "texto": mensaje, "adjuntos": [a["nombre"] + (f" · {a['desc']}" if a["desc"] else "")
                                                                       for a in nuevos],
                          "abierto": data.get("abierto") or "", "fecha": time.strftime("%Y-%m-%d %H:%M")},
                         {"rol": "ia", "ia": ia, "texto": r["texto"], "tokens": r["tokens"]}]
    conv["ia"], conv["session"] = ia, r["session"] if ia == "claude" else None
    conv["fecha"] = time.strftime("%Y-%m-%d %H:%M")
    conv_save(conv)
    return conv_public(conv)


def open_login(ai):
    """Abre una terminal con el login de la CLI (claude, codex, gemini) para que el usuario inicie sesión allí."""
    open_terminal(AIS[ai]["login"], Path.home(), f'DeskLens · {AIS[ai]["nombre"]}')


# ---------- reglas del proyecto y archivos nuevos ----------

def project_of(path):
    """El proyecto añadido que contiene `path`; si hay proyectos anidados, el más profundo. None si es un suelto."""
    p = Path(path).resolve()
    inside = [Path(r).resolve() for r in load_config()["proyectos"] if p.is_relative_to(Path(r).resolve())]
    return max(inside, key=lambda r: len(r.parts)) if inside else None


def file_info(p):
    """Lo que la ventana necesita para abrir un archivo: texto (si lo es), codificación, saltos de línea, mtime y si se ejecuta."""
    st = p.stat()
    texto, cod, trunc = read_text(p)
    return {"nombre": p.name, "ruta": str(p), "tam": st.st_size, "fecha": st.st_mtime, "mtime": str(st.st_mtime_ns),
            "texto": texto, "codificacion": cod, "truncado": trunc,
            "eol": "CRLF" if texto and "\r\n" in texto else "LF", "ejecutar": run_info(p)}


def rules_for(path):
    """reglas.md del proyecto de `path` para el panel de IA (None si el archivo no está en un proyecto o no hay reglas)."""
    proj = project_of(path)
    if not proj:
        return {"proyecto": None, "reglas": None}
    f = proj / "reglas.md"
    return {"proyecto": {"ruta": str(proj), "nombre": proj.name}, "reglas": file_info(f) if f.is_file() else None}


# ---------- crear .docx y .pdf desde el HTML del Markdown (la IA escribe Markdown; DeskLens convierte, sin IA) ----------

def _x(t):
    """Escapa texto para meterlo en XML/HTML (Word y la página que se imprime a PDF)."""
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


class _Docx(HTMLParser):
    """HTML sencillo (títulos, párrafos, negrita, cursiva, código, listas, citas, tablas) → cuerpo de document.xml."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.body, self.runs, self.ppr = [], None, ""
        self.b = self.i = self.code = self.quote = 0
        self.pre, self.href, self.lists, self.li_fresh = False, None, [], False
        self.table, self.cell = None, None

    def start_p(self, style="", indent=0, prefix=""):
        """Empieza un párrafo de Word con su estilo (Heading1, Quote…) y la sangría de lista o de cita."""
        self.end_p()
        self.runs = []
        ppr = f'<w:pStyle w:val="{style}"/>' if style else ""
        if indent:
            ppr += f'<w:ind w:left="{indent}" w:hanging="300"/>'
        elif self.quote:
            ppr += '<w:ind w:left="567"/>'
        self.ppr = f"<w:pPr>{ppr}</w:pPr>" if ppr else ""
        if prefix:
            self.add(prefix)

    def end_p(self):
        """Cierra el párrafo abierto y lo añade al cuerpo o a la celda de tabla en curso."""
        if self.runs is None:
            return
        (self.cell if self.cell is not None else self.body).append(f"<w:p>{self.ppr}{''.join(self.runs)}</w:p>")
        self.runs = None

    def add(self, text):
        """Texto suelto → un run de Word con el formato activo (negrita, cursiva, código, enlace); fuera de <pre> se juntan los espacios."""
        if not self.pre:
            text = re.sub(r"\s+", " ", text)
        if self.runs is None:
            if not text.strip():
                return
            self.start_p("Quote" if self.quote else "")
            text = text.lstrip()
        rpr = ("<w:b/>" if self.b else "") + ("<w:i/>" if self.i or self.quote else "") + \
              ('<w:rFonts w:ascii="Consolas" w:hAnsi="Consolas"/>' if self.code or self.pre else "")
        for k, part in enumerate(text.split("\n")):
            if k:
                self.runs.append("<w:r><w:br/></w:r>")
            if part:
                self.runs.append(f'<w:r>{"<w:rPr>" + rpr + "</w:rPr>" if rpr else ""}<w:t xml:space="preserve">{_x(part)}</w:t></w:r>')

    def handle_starttag(self, tag, attrs):
        """Etiquetas HTML de marked → estado del conversor: títulos, listas, tablas, citas, código, enlaces, saltos e imágenes."""
        a = dict(attrs)
        if tag in ("td", "th"):
            self.b += tag == "th"  # encabezados de tabla en negrita
            self.end_p()
            self.cell = []
            self.start_p()
            return
        if re.fullmatch(r"h[1-6]", tag):
            self.start_p(f"Heading{min(int(tag[1]), 3)}")
        elif tag == "p":
            if not self.li_fresh:
                self.start_p("Quote" if self.quote else "", 360 * len(self.lists))
            self.li_fresh = False
        elif tag in ("ul", "ol"):
            self.end_p()
            self.lists.append([tag, int(a.get("start") or 1) - 1])
        elif tag == "li":
            kind = self.lists[-1] if self.lists else ["ul", 0]
            kind[1] += 1
            self.start_p("", 360 * max(1, len(self.lists)), "• " if kind[0] == "ul" else f"{kind[1]}. ")
            self.li_fresh = True
        elif tag == "blockquote":
            self.end_p()
            self.quote += 1
        elif tag == "pre":
            self.start_p()
            self.pre = True
        elif tag in ("strong", "b"):
            self.b += 1
        elif tag in ("em", "i"):
            self.i += 1
        elif tag == "code":
            self.code += 1
        elif tag == "br" and self.runs is not None:
            self.runs.append("<w:r><w:br/></w:r>")
        elif tag == "hr":
            self.end_p()
            self.body.append('<w:p><w:pPr><w:pBdr><w:bottom w:val="single" w:sz="6" w:space="1" w:color="999999"/></w:pBdr></w:pPr></w:p>')
        elif tag == "a":
            self.href = a.get("href")
        elif tag == "img":
            self.add(f"[imagen: {a.get('alt') or a.get('src') or ''}]")
        elif tag == "table":
            self.end_p()
            self.table = []
        elif tag == "tr" and self.table is not None:
            self.table.append([])

    def handle_endtag(self, tag):
        """Cierra lo abierto en handle_starttag; al cerrar una tabla la escribe con bordes y ancho completo."""
        if re.fullmatch(r"h[1-6]", tag) or tag in ("p", "li", "pre"):
            self.end_p()
            self.pre = False if tag == "pre" else self.pre
            self.li_fresh = False
        elif tag in ("ul", "ol"):
            self.end_p()
            if self.lists:
                self.lists.pop()
        elif tag == "blockquote":
            self.end_p()
            self.quote = max(0, self.quote - 1)
        elif tag in ("strong", "b"):
            self.b = max(0, self.b - 1)
        elif tag in ("em", "i"):
            self.i = max(0, self.i - 1)
        elif tag == "code":
            self.code = max(0, self.code - 1)
        elif tag == "a":
            if self.href and self.href.startswith("http"):
                self.add(f" ({self.href})")
            self.href = None
        elif tag in ("td", "th"):
            self.end_p()
            if tag == "th":
                self.b = max(0, self.b - 1)
            if self.table is not None and self.table:
                self.table[-1].append(self.cell or ["<w:p/>"])
            self.cell = None
        elif tag == "table" and self.table is not None:
            cols = max((len(r) for r in self.table), default=1) or 1
            w = 9000 // cols
            rows = "".join("<w:tr>" + "".join(f'<w:tc><w:tcPr><w:tcW w:w="{w}" w:type="dxa"/></w:tcPr>{"".join(c)}</w:tc>'
                                              for c in r + [["<w:p/>"]] * (cols - len(r))) + "</w:tr>" for r in self.table if r)
            border = '<w:{0} w:val="single" w:sz="4" w:color="BBBBBB"/>'
            borders = "".join(border.format(s) for s in ("top", "left", "bottom", "right", "insideH", "insideV"))
            grid = f'<w:gridCol w:w="{w}"/>' * cols
            self.body.append(f'<w:tbl><w:tblPr><w:tblW w:w="0" w:type="auto"/><w:tblBorders>{borders}</w:tblBorders>'
                             f'</w:tblPr><w:tblGrid>{grid}</w:tblGrid>{rows}</w:tbl><w:p/>')
            self.table = None

    def handle_data(self, data):
        self.add(data)


DOCX_STYLES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Georgia" w:hAnsi="Georgia" w:cs="Georgia"/><w:sz w:val="23"/><w:lang w:val="es-ES"/></w:rPr></w:rPrDefault>
<w:pPrDefault><w:pPr><w:spacing w:after="140" w:line="300" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults>
<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:pPr><w:keepNext/><w:spacing w:before="360" w:after="160"/><w:outlineLvl w:val="0"/></w:pPr><w:rPr><w:rFonts w:ascii="Segoe UI" w:hAnsi="Segoe UI"/><w:b/><w:sz w:val="34"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:pPr><w:keepNext/><w:spacing w:before="280" w:after="120"/><w:outlineLvl w:val="1"/></w:pPr><w:rPr><w:rFonts w:ascii="Segoe UI" w:hAnsi="Segoe UI"/><w:b/><w:sz w:val="28"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading3"><w:name w:val="heading 3"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:pPr><w:keepNext/><w:spacing w:before="220" w:after="100"/><w:outlineLvl w:val="2"/></w:pPr><w:rPr><w:rFonts w:ascii="Segoe UI" w:hAnsi="Segoe UI"/><w:b/><w:sz w:val="24"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Quote"><w:name w:val="Quote"/><w:basedOn w:val="Normal"/><w:pPr><w:ind w:left="567"/><w:pBdr><w:left w:val="single" w:sz="12" w:space="8" w:color="7C5CDB"/></w:pBdr></w:pPr><w:rPr><w:i/><w:color w:val="555555"/></w:rPr></w:style>
</w:styles>"""


def html_to_docx(html):
    """Markdown ya convertido a HTML → .docx mínimo válido (document.xml, estilos, numeración de listas y
    relaciones), solo con zipfile. Word lo abre sin avisos; formatos más ricos se piden a la IA sobre el Word."""
    d = _Docx()
    d.feed(html)
    d.close()
    d.end_p()
    body = "".join(d.body) or "<w:p/>"
    doc = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document '
           'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
           f'{body}<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'  # A4
           '<w:pgMar w:top="1300" w:right="1200" w:bottom="1300" w:left="1200" w:header="708" w:footer="708"/></w:sectPr>'
           '</w:body></w:document>')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types '
                   'xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" '
                   'ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" '
                   'ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/'
                   'vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName='
                   '"/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.'
                   'styles+xml"/></Types>')
        z.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns='
                   '"http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type='
                   '"http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
                   'Target="word/document.xml"/></Relationships>')
        z.writestr("word/_rels/document.xml.rels", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship '
                   'Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
                   'Target="styles.xml"/></Relationships>')
        z.writestr("word/document.xml", doc)
        z.writestr("word/styles.xml", DOCX_STYLES)
    return buf.getvalue()


PDF_PAGE = """<!doctype html><html lang="es"><head><meta charset="utf-8"><title>{title}</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&display=swap">
<style>
@page {{ size: A4; margin: 22mm 20mm 22mm;
  @bottom-center {{ content: counter(page) " / " counter(pages); font: 9pt Georgia, serif; color: #777; }} }}
body {{ font: 12pt/1.6 "Source Serif 4", Georgia, serif; color: #1f1f1f; }}
h1, h2, h3, h4 {{ font-family: "Segoe UI", sans-serif; line-height: 1.25; break-after: avoid; }}
h1 {{ font-size: 20pt; }} h2 {{ font-size: 15pt; }} h3 {{ font-size: 12.5pt; }}
table {{ border-collapse: collapse; width: 100%; font-size: 10.5pt; }}
th, td {{ border: 1px solid #bbb; padding: 4px 8px; text-align: left; vertical-align: top; }}
tr {{ break-inside: avoid; }}
blockquote {{ border-left: 3px solid #7c5cdb; margin: 0; padding-left: 14px; color: #555; font-style: italic; }}
pre {{ background: #f4f4f4; padding: 10px; border-radius: 4px; white-space: pre-wrap; font-size: 9.5pt; }}
code {{ font-family: Consolas, monospace; font-size: .9em; }}
img {{ max-width: 100%; }}
</style></head><body>{body}</body></html>"""


# Navegadores Chromium (modo aplicación --app y PDF): id, nombre, ejecutable en Windows (App Paths y carpeta),
# app de macOS y órdenes de Linux. El orden es el de «Automático».
BROWSERS = [("edge", "Microsoft Edge", "msedge.exe", ("Microsoft", "Edge", "Application"), "Microsoft Edge",
             ("microsoft-edge", "microsoft-edge-stable")),
            ("chrome", "Google Chrome", "chrome.exe", ("Google", "Chrome", "Application"), "Google Chrome",
             ("google-chrome", "google-chrome-stable")),
            ("brave", "Brave", "brave.exe", ("BraveSoftware", "Brave-Browser", "Application"), "Brave Browser",
             ("brave-browser", "brave")),
            ("chromium", "Chromium", "chrome.exe", ("Chromium", "Application"), "Chromium", ("chromium", "chromium-browser"))]
_browsers = None


def browsers():
    """{id: ejecutable} de los navegadores Chromium instalados, en el orden de BROWSERS (se busca una vez)."""
    global _browsers
    if _browsers is not None:
        return _browsers
    found = {}
    for bid, _, exe, sub, app, names in BROWSERS:
        if MAC:
            p = Path("/Applications") / f"{app}.app" / "Contents" / "MacOS" / app
            cands = [str(p)] if p.exists() else []
        elif not WINDOWS:
            cands = [p for n in names if (p := shutil.which(n))]
        else:  # Windows: primero el registro (App Paths; Chromium no se registra), luego las carpetas habituales
            cands = []
            try:
                import winreg
                for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                    try:
                        if bid != "chromium":
                            with winreg.OpenKey(hive, rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{exe}") as k:
                                cands.append(winreg.QueryValue(k, None))
                    except OSError:
                        pass
            except ImportError:
                pass
            cands += [str(Path(b, *sub, exe)) for b in (os.environ.get("ProgramFiles(x86)", ""), os.environ.get("ProgramFiles", ""),
                                                         os.environ.get("LOCALAPPDATA", "")) if b]
            # Chrome y Chromium se llaman chrome.exe: cada uno solo cuenta en su propia carpeta
            cands = [c for c in cands if c and Path(c).is_file() and (bid != "chrome" or "Chromium" not in c)]
        if cands:
            found[bid] = cands[0]
    _browsers = found
    return found


def edge_path(choice=None):
    """El navegador Chromium elegido en ⚙ Ajustes (o el primero instalado) para la ventana y para crear PDF."""
    found = browsers()
    return found.get(choice) or next(iter(found.values()), None)


# ⚙ Ajustes › General: con qué se abre DeskLens. Solo se ofrecen los navegadores instalados (se miran al arrancar).
SETTINGS.insert(1, ("navegador", "General", "Navegador de la ventana de DeskLens (se aplica al reabrir DeskLens)", "auto",
                    [("auto", "Automático (" + " › ".join(n for b, n, *_ in BROWSERS if b in browsers()) + ")" if browsers()
                      else "Automático"),
                     *[(b, n) for b, n, *_ in BROWSERS if b in browsers()],
                     ("predeterminado", "Navegador predeterminado del sistema (pestaña normal)")], None))


def html_to_pdf(html, title=""):
    """Edge sin ventana imprime la página a PDF (A4, letra de lectura, números de página). Sin internet, Georgia."""
    edge = edge_path()
    if not edge:
        raise RuntimeError("Para crear el PDF hace falta Edge, Chrome, Chromium o Brave instalado")
    IA_DIR.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=IA_DIR) as d:
        page, out = Path(d) / "pagina.html", Path(d) / "salida.pdf"
        page.write_text(PDF_PAGE.format(title=_x(title), body=html), encoding="utf-8")
        subprocess.run([edge, "--headless=new", "--disable-gpu", "--no-first-run", f"--user-data-dir={Path(d) / 'perfil'}",
                        "--no-pdf-header-footer", "--virtual-time-budget=8000", f"--print-to-pdf={out}", page.as_uri()],
                       capture_output=True, timeout=120, creationflags=NO_WINDOW)
        if not out.exists() or out.stat().st_size == 0:
            raise RuntimeError("El navegador no pudo crear el PDF")
        return out.read_bytes()


# Formatos que DeskLens no sabe generar: mejor decirlo que crear un archivo roto
NOT_CREATABLE = {".xlsx", ".xls", ".xlsm", ".pptx", ".ppt", ".doc", ".odt", ".ods", ".odp", ".rtf", ".png", ".jpg",
                 ".jpeg", ".gif", ".webp", ".bmp", ".ico", ".zip", ".rar", ".7z", ".exe", ".dll", ".msi", ".mp3",
                 ".mp4", ".wav", ".epub"}


def create_file(folder, name, text, html=None):
    """Crea un archivo nuevo (nunca sobrescribe) dentro de una carpeta añadida a DeskLens.
    .docx y .pdf se generan desde el HTML del Markdown; el resto se guarda como texto UTF-8."""
    if not name or any(c in name for c in '\\/:*?"<>|') or name in (".", ".."):
        raise ValueError("Nombre de archivo no válido")
    p = Path(folder).resolve() / name
    ext = p.suffix.lower()
    if ext in NOT_CREATABLE:
        raise ValueError(f"DeskLens no puede crear archivos {ext}. Pide .docx, .pdf, .md, .txt, .csv o .html.")
    in_project = allowed(p)
    if not in_project and not any(Path(s).resolve().parent == p.parent for s in load_config()["sueltos"]):
        raise PermissionError("Carpeta no añadida a DeskLens")
    if p.exists():
        raise FileExistsError(str(p))
    html = html or f"<pre>{_x(text)}</pre>"
    if ext == ".docx":
        data = html_to_docx(html)
    elif ext == ".pdf":
        data = html_to_pdf(html, p.stem)
    else:
        data = text.encode("utf-8")
    with open(p, "xb") as f:  # "x": si apareció entre tanto, no se pisa
        f.write(data)
    if not in_project:  # junto a un archivo suelto: el nuevo también queda como suelto
        add_paths("sueltos", [p])
    idx_update(p)
    return str(p)


# ---------- cambiar formato y texto dentro de un .docx (la IA propone, el usuario pulsa Aplicar) ----------
# Solo se tocan los «runs» de texto afectados; el resto del XML (y las declaraciones de su raíz) se conserva tal cual.

RPR_ORDER = ["rStyle", "rFonts", "b", "bCs", "i", "iCs", "caps", "smallCaps", "strike", "dstrike", "outline", "shadow",
             "emboss", "imprint", "noProof", "snapToGrid", "vanish", "webHidden", "color", "spacing", "w", "kern",
             "position", "sz", "szCs", "highlight", "u", "effect", "bdr", "shd", "fitText", "vertAlign", "rtl", "cs",
             "em", "lang", "eastAsianLayout", "specVanish", "oMath"]
HIGHLIGHTS = {"amarillo": "yellow", "verde": "green", "azul": "cyan", "rosa": "magenta", "rojo": "red", "gris": "lightGray",
              "yellow": "yellow", "green": "green", "cyan": "cyan", "magenta": "magenta", "red": "red", "lightgray": "lightGray"}
COLORS = {"rojo": "FF0000", "azul": "0070C0", "verde": "00B050", "negro": "000000", "blanco": "FFFFFF", "naranja": "FFA500",
          "morado": "7030A0", "gris": "808080", "amarillo": "FFC000"}


def _set_rpr(run, op):
    """Aplica el formato pedido (color, negrita, cursiva, subrayado, tamaño, resaltado, fuente) al <w:rPr> de un run,
    creándolo si falta. Cada propiedad se inserta en el orden que exige el esquema de Word (RPR_ORDER)."""
    rpr = run.find(W + "rPr")
    if rpr is None:
        rpr = ET.Element(W + "rPr")
        run.insert(0, rpr)

    def put(tag, attrs):
        """Quita la propiedad si estaba y, si attrs no es None, la vuelve a poner con esos valores y en su sitio."""
        old = rpr.find(W + tag)
        if old is not None:
            rpr.remove(old)
        if attrs is None:
            return
        el = ET.Element(W + tag, {W + k: v for k, v in attrs.items()})
        pos = RPR_ORDER.index(tag)  # el orden del esquema de Word importa
        idx = next((i for i, c in enumerate(rpr) if c.tag.startswith(W) and c.tag[len(W):] in RPR_ORDER
                    and RPR_ORDER.index(c.tag[len(W):]) > pos), len(rpr))
        rpr.insert(idx, el)

    if "color" in op:
        c = str(op["color"]).strip().lstrip("#")
        put("color", {"val": COLORS.get(c.lower(), c.upper())})
    for key, tag in (("negrita", "b"), ("cursiva", "i")):
        if key in op:
            put(tag, {} if op[key] else {"val": "0"})
            put(tag + "Cs", {} if op[key] else {"val": "0"})
    if "subrayado" in op:
        put("u", {"val": "single" if op["subrayado"] else "none"})
    if "tamano" in op:
        half = str(int(round(float(op["tamano"]) * 2)))
        put("sz", {"val": half})
        put("szCs", {"val": half})
    if "resaltado" in op:
        v = str(op["resaltado"]).strip().lower()
        put("highlight", None if v in ("", "no", "ninguno", "none") else {"val": HIGHLIGHTS.get(v, "yellow")})
    if "fuente" in op:
        f = str(op["fuente"])
        put("rFonts", {"ascii": f, "hAnsi": f, "cs": f})


def _split_run(p, run, offset):
    """Parte un run de un solo w:t en dos (mismo formato) en la posición indicada. Devuelve el segundo."""
    t = run.find(W + "t")
    text = t.text or ""
    second = ET.fromstring(ET.tostring(run))
    t.text = text[:offset]
    t2 = second.find(W + "t")
    t2.text = text[offset:]
    for x in (t, t2):
        x.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    parent = next(e for e in p.iter() if run in list(e))
    parent.insert(list(parent).index(run) + 1, second)
    return second


def _runs(p):
    """Runs con texto del párrafo y su texto (los que tienen tabulaciones o imágenes cuentan como bloque)."""
    out = []
    for r in p.iter(W + "r"):
        txt = "".join((c.text or "") if c.tag == W + "t" else "\t" if c.tag == W + "tab" else "" for c in r)
        out.append((r, txt))
    return out


DOCX_IMG = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif", ".bmp": "image/bmp"}
PIC_XML = """<w:p xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
 xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
 xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
 xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><w:pPr><w:jc w:val="center"/></w:pPr>
<w:r><w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0"><wp:extent cx="{cx}" cy="{cy}"/><wp:docPr id="{id}" name="Imagen {id}"/>
<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:pic>
<pic:nvPicPr><pic:cNvPr id="0" name="{name}"/><pic:cNvPicPr/></pic:nvPicPr>
<pic:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>
<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>
</pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>"""


def _docx_image(root, pars, files, op, target, folder):
    """Inserta una imagen en un párrafo nuevo antes o después del que contiene «buscar»."""
    src = str(op["imagen"])
    name = Path(src).name
    ext = Path(name).suffix.lower()
    if ext not in DOCX_IMG:
        raise ValueError(f"Word no admite imágenes {ext or 'sin extensión'}: usa .png, .jpg, .gif o .bmp")
    if op.get("datos"):  # soltada desde Windows: llega su contenido
        data = base64.b64decode(op["datos"])
    else:
        f = Path(src) if Path(src).is_absolute() else folder / src
        if not f.is_file():
            raise ValueError(f"No se encontró la imagen «{src}»")
        data = f.read_bytes()
    dims = image_size(data)
    if not dims:
        raise ValueError(f"«{name}» no parece una imagen válida")
    norm = lambda s: unicodedata.normalize("NFC", s)
    par = next((q for q in pars if target in norm("".join(t.text or "" for t in q.iter(W + "t")))), None)
    if par is None:
        raise ValueError(f"No se encontró «{target}» en el documento (debe ser el texto exacto)")
    parent = next(e for e in root.iter() if par in list(e))
    # ancho: el pedido (cm) o el natural a 96 ppp, sin pasar de 16 cm (ancho útil de un A4)
    cm = float(op.get("ancho_cm") or min(16, dims[0] / 96 * 2.54))
    cx = int(cm * 360000)
    cy = int(cx * dims[1] / dims[0])
    n = 1 + sum(1 for k in files if k.startswith("word/media/desklens"))
    media = f"media/desklens{n}{ext}"
    rels_name = "word/_rels/document.xml.rels"
    rels = files[rels_name].decode("utf-8")
    rid = f"rIdDeskLens{n}"
    rels = rels.replace("</Relationships>", f'<Relationship Id="{rid}" Type="http://schemas.openxmlformats.org/officeDocument/'
                                            f'2006/relationships/image" Target="{media}"/></Relationships>')
    files[rels_name] = rels.encode("utf-8")
    ct = files["[Content_Types].xml"].decode("utf-8")
    if not re.search(rf'Extension="{ext[1:]}"', ct, re.I):
        ct = ct.replace("</Types>", f'<Default Extension="{ext[1:]}" ContentType="{DOCX_IMG[ext]}"/></Types>')
        files["[Content_Types].xml"] = ct.encode("utf-8")
    files["word/" + media] = data
    WP = "{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}"
    ids = [int(d.get("id")) for d in root.iter(WP + "docPr") if (d.get("id") or "").isdigit()]
    for prefix, uri in re.findall(r'xmlns:(\w+)="([^"]+)"', PIC_XML):
        ET.register_namespace(prefix, uri)
    safe = name.replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;")
    new = ET.fromstring(PIC_XML.format(cx=cx, cy=cy, id=max(ids, default=0) + 1, name=safe, rid=rid))
    i = list(parent).index(par)
    parent.insert(i if op.get("posicion") == "antes" else i + 1, new)


def docx_paragraphs(path):
    """Texto de cada párrafo (w:p) en orden, como lo ve docx_apply: la ventana lo empareja con lo que muestra el visor."""
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    return [unicodedata.normalize("NFC", "".join(t for _, t in _runs(par))) for par in root.iter(W + "p")]


def docx_apply(path, ops):
    """Aplica una lista de cambios {buscar, color, negrita, cursiva, subrayado, tamano, resaltado, fuente,
    reemplazar, todas}. Todo o nada: si un «buscar» no aparece, no se toca el archivo."""
    p = Path(path)
    data, total = docx_transform(p.read_bytes(), ops, p.parent)
    return {"cambios": total, **write_with_backup(p, data, "El documento está abierto en Word: ciérralo allí y vuelve a pulsar Aplicar")}


def docx_transform(data, ops, folder):
    """Los bytes de un .docx con los cambios aplicados, sin tocar el disco (también para el historial)."""
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        entries = [(i, z.read(i.filename)) for i in z.infolist()]
    raw = next(d for i, d in entries if i.filename == "word/document.xml").decode("utf-8")
    for prefix, uri in re.findall(r'xmlns:(\w+)="([^"]+)"', raw):
        ET.register_namespace(prefix, uri)  # conserva los prefijos originales (w:, w14:, mc:…)
    root = ET.fromstring(raw)
    total, files = 0, {i.filename: d for i, d in entries}  # files: lo que se escribe (las imágenes nuevas se añaden)
    for op in ops:
        target = unicodedata.normalize("NFC", str(op.get("buscar", "")))
        pars = list(root.iter(W + "p"))
        if "parrafo" in op:  # edición a mano: el párrafo N (orden de docx_paragraphs) y desde qué carácter buscar
            if not 0 <= int(op["parrafo"]) < len(pars):
                raise ValueError("El documento cambió mientras lo editabas: vuelve a abrirlo")
            pars = [pars[int(op["parrafo"])]]
            if "agregar" in op:  # párrafo vacío que ahora tiene texto
                r = ET.SubElement(pars[0], W + "r")
                ET.SubElement(r, W + "t", {"{http://www.w3.org/XML/1998/namespace}space": "preserve"}).text = str(op["agregar"])
                total += 1
                continue
        if not target and not ("imagen" in op and "parrafo" in op):  # imagen soltada en un párrafo (aunque esté vacío)
            raise ValueError("Falta el texto a buscar")
        if "imagen" in op:
            _docx_image(root, pars, files, op, target, folder)
            total += 1
            continue
        found = 0
        for par in pars:
            search_from = int(op.get("desde") or 0)
            while True:
                runs = _runs(par)
                full = unicodedata.normalize("NFC", "".join(t for _, t in runs))
                start = full.find(target, search_from)
                if start < 0:
                    break
                end = start + len(target)
                pos, covered = 0, []
                for r, t in runs:  # parte los runs en los bordes y se queda con los de dentro
                    a, b = pos, pos + len(t)
                    pos = b
                    if b <= start or a >= end or not t:
                        continue
                    simple = len([c for c in r if c.tag != W + "rPr"]) == 1 and r.find(W + "t") is not None
                    if simple and a < start:
                        r, a = _split_run(par, r, start - a), start
                    if simple and b > end:
                        _split_run(par, r, end - a)
                    covered.append(r)
                for r in covered:
                    _set_rpr(r, op)
                if "reemplazar" in op:  # el texto nuevo queda en el primer run, con su formato
                    first = covered[0].find(W + "t")
                    if first is None:
                        raise ValueError(f"«{target}» no se puede reemplazar (contiene imágenes o campos)")
                    first.text = str(op["reemplazar"])
                    first.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")  # conserva espacios al borde
                    for r in covered[1:]:
                        next(e for e in par.iter() if r in list(e)).remove(r)
                found += 1
                if not op.get("todas"):
                    break
                search_from = start + len(str(op.get("reemplazar", target)))  # sigue después de lo cambiado
            if found and not op.get("todas"):
                break
        if not found:
            raise ValueError(f"No se encontró «{target}» en el documento (debe ser el texto exacto)")
        total += found
    xml = ET.tostring(root, encoding="unicode")
    original_tag = re.search(r"<w:document\b[^>]*>", raw).group(0)
    new_tag = re.match(r"<w:document\b[^>]*>", xml).group(0)
    extra = [d for d in re.findall(r'xmlns:\w+="[^"]+"', new_tag) if d not in original_tag]
    if extra:  # por si ElementTree necesitó algún prefijo más
        original_tag = original_tag[:-1] + " " + " ".join(extra) + ">"
    xml = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\r\n' + original_tag + xml[len(new_tag):]
    files["word/document.xml"] = xml.encode("utf-8")
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        for info, _ in entries:
            z.writestr(info, files.pop(info.filename))
        for name, d in files.items():  # imágenes nuevas
            z.writestr(name, d, zipfile.ZIP_DEFLATED)
    return out.getvalue(), total


def write_with_backup(p, data, busy):
    """Escribe de golpe: .bak la primera vez (si no está en git) y copia exacta de antes para «Deshacer».
    busy: el aviso si otro programa lo tiene abierto (Windows no deja reemplazarlo)."""
    bak = backup_once(p)
    undo_id = undo_save(p)
    replace_atomic(p, data, busy)
    idx_update(p)
    return {"bak": str(bak) if bak else None, "mtime": str(p.stat().st_mtime_ns), "deshacer": undo_id}


# ---------- pestaña web: ¿la página se deja mostrar dentro de DeskLens? ----------

def web_check(url):
    """Descarga solo las cabeceras (GET, sigue redirecciones) y mira X-Frame-Options y CSP frame-ancestors.
    Límite: una página que lo permite puede enlazar a otras que no; esas fallan dentro del marco."""
    import urllib.request
    if not re.match(r"https?://", url, re.I):
        return {"permitido": False, "motivo": "La dirección debe empezar por http:// o https://", "url": url}
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (DeskLens)", "Accept": "text/html,*/*"})
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            final, h = r.geturl(), r.headers
    except urllib.error.HTTPError as e:  # 404, 403…: el marco mostrará la página de error de la web
        final, h = url, e.headers
    except (OSError, ValueError) as e:
        return {"permitido": False, "motivo": f"No se pudo conectar: {getattr(e, 'reason', e)}", "url": url}
    xfo = (h.get("X-Frame-Options") or "").strip().lower()
    fa = re.search(r"frame-ancestors([^;]*)", h.get("Content-Security-Policy") or "", re.I)
    sources = fa.group(1).split() if fa else []
    blocked = xfo in ("deny", "sameorigin") or (fa and "*" not in sources)
    host = urlparse(final).hostname or final
    return {"permitido": not blocked, "url": final,
            "motivo": f"{host} no permite mostrarse dentro de otra página (es una protección de la web)" if blocked else ""}


# ---------- historial de cambios (↶ ↷): cada paso queda en disco y sobrevive a guardar y cerrar ----------
# historial/versiones/<hash de la ruta>/: meta.json (árbol de pasos) + <id>.dat (el paso) + <id>.base (copia del archivo).
# Texto e imagen: cada paso guarda el estado completo. Word: los cambios del paso (se reconstruye desde la última copia).
# PDF: páginas y notas en JSON sobre la última copia. Nada se escribe hasta el primer cambio real.
HIST_DIR = ROOT / "historial" / "versiones"
_hist_lock = threading.Lock()
_hist_docx = {}  # (ruta, id) → bytes del Word ya reconstruido (el visor y los párrafos lo piden seguido)
_hist_last = 0  # último id dado (los ids son el reloj en ns, siempre crecientes)


def hist_dir(path):
    """Carpeta del historial de un archivo: hash de su ruta (en Windows sin distinguir mayúsculas), no su nombre."""
    return HIST_DIR / hashlib.sha1(os.path.normcase(str(Path(path).resolve())).encode()).hexdigest()[:16]


def hist_kind(path):
    """Cómo se guarda cada paso: texto (gzip), imagen (PNG), docx (cambios) o pdf (JSON de páginas y notas)."""
    ext = Path(path).suffix.lower()
    return "docx" if ext == ".docx" else "pdf" if ext == ".pdf" else "imagen" if ext in EDIT_IMG else "texto"


def hist_meta(path):
    """meta.json del historial (árbol de pasos y el actual); vacío si el archivo aún no tiene historial."""
    try:
        return json.loads((hist_dir(path) / "meta.json").read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return {"ruta": str(Path(path).resolve()), "nodos": [], "actual": None}


def _hist_write_meta(path, meta):
    """Guarda meta.json de golpe (archivo temporal + os.replace) y anota la última actividad, que usa la limpieza."""
    d = hist_dir(path)
    d.mkdir(parents=True, exist_ok=True)
    meta["ultimo"] = time.time()
    tmp = d / "meta.tmp"
    tmp.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, d / "meta.json")


def _hist_node(meta, nid):
    """El paso con ese id; ValueError si ya no está (p. ej. lo borró la limpieza)."""
    for n in meta["nodos"]:
        if n["id"] == nid:
            return n
    raise ValueError("Ese paso ya no está en el historial")


def hist_disk_node(path, meta):
    """El paso cuyo estado es el archivo tal como está en disco (el último guardado o abierto con ese mtime)."""
    m = str(Path(path).stat().st_mtime_ns)
    return next((n["id"] for n in reversed(meta["nodos"]) if n.get("mtime") == m), None)


def hist_public(path):
    """Árbol de pasos para la ventana, el actual y cuál corresponde al archivo tal como está en disco."""
    meta = hist_meta(path)
    return {"nodos": meta["nodos"], "actual": meta["actual"], "disco": hist_disk_node(path, meta) if Path(path).is_file() else None}


def _hist_add(meta, path, padre, desc, data, extra, base=None):
    """Crea un paso: <id>.dat con su contenido (texto comprimido) y, si es copia de partida, <id>.base.
    Los ids son el reloj en ns, siempre crecientes, así que ordenarlos como texto es ordenarlos en el tiempo."""
    global _hist_last
    d = hist_dir(path)
    d.mkdir(parents=True, exist_ok=True)
    _hist_last = max(time.time_ns(), _hist_last + 1)  # el reloj de Windows puede repetir: dos pasos seguidos, mismo id
    nid = f"{_hist_last:x}"
    if data is not None:
        (d / f"{nid}.dat").write_bytes(gzip.compress(data, 6) if hist_kind(path) == "texto" else data)
    if base is not None:
        (d / f"{nid}.base").write_bytes(base)
    meta["nodos"].append({"id": nid, "padre": padre, "fecha": time.strftime("%Y-%m-%d %H:%M:%S"), "desc": desc,
                          "base": base is not None, **(extra or {})})
    meta["actual"] = nid
    return nid


def hist_step(path, padre, desc, data, extra=None):
    """Un paso nuevo. padre None = parte del archivo en disco (si nadie lo tiene, se copia como «Abierto»)."""
    p = Path(path)
    with _hist_lock:
        meta = hist_meta(p)
        if padre is None:
            padre = hist_disk_node(p, meta)
        if padre is None:  # primera vez, o el archivo cambió fuera de DeskLens
            kind, raw = hist_kind(p), p.read_bytes()
            first = {"texto": ((read_text(p)[0] or "").replace("\r\n", "\n").encode("utf-8"), None),
                     "imagen": (raw, None)}.get(kind, (None, raw))
            padre = _hist_add(meta, p, meta["actual"], "📂 Abierto" if not meta["nodos"] else "📂 Cambiado fuera de DeskLens",
                              *first[:1], {"tipo": "abierto", "mtime": str(p.stat().st_mtime_ns)}, base=first[1])
        else:
            _hist_node(meta, padre)
        nid = _hist_add(meta, p, padre, desc, data, extra)
        _hist_write_meta(p, meta)
    return {"id": nid, **hist_public(p)}


def hist_go(path, nid):
    """Anota en meta.json en qué paso está el editor tras ↶ ↷ o «hasta aquí» (el estado lo carga la ventana)."""
    with _hist_lock:
        meta = hist_meta(path)
        _hist_node(meta, nid)
        meta["actual"] = nid
        _hist_write_meta(path, meta)


def hist_data(path, nid, part="dat"):
    """Lo guardado de un paso: el texto, la imagen, los cambios del Word o el JSON del PDF (dat), o la copia (base)."""
    meta = hist_meta(path)
    _hist_node(meta, nid)
    raw = (hist_dir(path) / f"{nid}.{'base' if part == 'base' else 'dat'}").read_bytes()
    return gzip.decompress(raw) if part != "base" and hist_kind(path) == "texto" else raw


def hist_docx(path, nid):
    """El Word tal como estaba en ese paso: la última copia anterior + los cambios de los pasos siguientes."""
    key = (os.path.normcase(str(Path(path).resolve())), nid)
    if key in _hist_docx:
        return _hist_docx[key]
    meta, chain = hist_meta(path), []
    n = _hist_node(meta, nid)
    while not n.get("base"):
        chain.append(n)
        if not n["padre"]:
            raise ValueError("Falta la copia de partida de este historial")
        n = _hist_node(meta, n["padre"])
    data = hist_data(path, n["id"], "base")
    for step in reversed(chain):
        data = docx_transform(data, json.loads(hist_data(path, step["id"])), Path(path).parent)[0]
    if len(_hist_docx) > 20:
        _hist_docx.clear()
    _hist_docx[key] = data
    return data


def hist_saved(path, nid):
    """El archivo ya tiene el estado de ese paso: se marca 💾 y, en Word y PDF, se copia como nueva base."""
    p = Path(path)
    with _hist_lock:
        meta = hist_meta(p)
        n = _hist_node(meta, nid)
        n.update(guardado=time.strftime("%Y-%m-%d %H:%M:%S"), mtime=str(p.stat().st_mtime_ns))
        if hist_kind(p) in ("docx", "pdf") and not n.get("base"):
            (hist_dir(p) / f"{nid}.base").write_bytes(p.read_bytes())
            n["base"] = True
        meta["actual"] = nid
        _hist_write_meta(p, meta)
    return hist_public(p)


def hist_diff(path, nid):
    """Qué cambió en ese paso respecto al anterior (texto y Word): líneas o párrafos quitados (-) y puestos (+)."""
    meta = hist_meta(path)
    n = _hist_node(meta, nid)
    if not n["padre"]:
        return []
    kind = hist_kind(path)
    if kind == "texto":
        a, b = (hist_data(path, x).decode("utf-8").split("\n") for x in (n["padre"], nid))
    elif kind == "docx":
        a, b = (docx_paragraphs(io.BytesIO(hist_docx(path, x))) for x in (n["padre"], nid))
    else:
        return []
    out = [line for line in difflib.unified_diff(a, b, lineterm="", n=1) if not line.startswith(("---", "+++"))]
    if not out and kind == "docx" and (hist_dir(path) / f"{nid}.dat").exists():  # solo formato: el párrafo tocado («=»)
        out = ["=" + b[op["parrafo"]] for op in json.loads(hist_data(path, nid)) if 0 <= op.get("parrafo", -1) < len(b)]
    return out[:200]


def hist_cleanup():
    """Borra el historial de los archivos sin actividad desde hace N días y, si todo pasa del tope, los más viejos.
    Corre en el hilo del índice (al arrancar y en cada repaso), no en cada paso: recorre todo el historial."""
    if not HIST_DIR.is_dir():
        return
    with _hist_lock:  # no borra una carpeta mientras hist_step escribe en ella
        limit, cap = time.time() - ajuste("historial_dias") * 86400, ajuste("historial_mb") * 1_000_000
        folders = []
        for d in HIST_DIR.iterdir():
            try:
                last = json.loads((d / "meta.json").read_text(encoding="utf-8")).get("ultimo", 0)
            except (OSError, ValueError):
                last = d.stat().st_mtime
            if last < limit:
                shutil.rmtree(d, ignore_errors=True)
            else:
                folders.append((last, d, sum(f.stat().st_size for f in d.iterdir())))
        total = sum(s for _, _, s in folders)
        for last, d, size in sorted(folders):  # ponytail: se borra el historial entero del archivo más viejo, no paso a paso
            if total <= cap:
                break
            shutil.rmtree(d, ignore_errors=True)
            total -= size


EDIT_IMG = {".png", ".jpg", ".jpeg", ".webp"}  # lo que el navegador sabe volver a guardar en su mismo formato


def binary_save(path, data):
    """Guarda una imagen o un PDF editados en DeskLens: .bak la primera vez, copia para Deshacer, de golpe."""
    p = Path(path)
    if p.suffix.lower() == ".pdf":
        if not data.startswith(b"%PDF-"):
            raise ValueError("Los datos recibidos no son un PDF")
    elif p.suffix.lower() not in EDIT_IMG:
        raise ValueError(f"DeskLens solo guarda PDF e imágenes {', '.join(sorted(EDIT_IMG))}")
    elif not image_size(data):
        raise ValueError("Los datos recibidos no son una imagen")
    return write_with_backup(p, data, f"«{p.name}» está abierto en otro programa: ciérralo allí y vuelve a guardar")


# ---------- deshacer cambios de la IA en un Word: copia exacta de antes de cada cambio ----------
UNDO_DIR = ROOT / "historial" / "deshacer"
UNDO_KEEP = 100  # copias que se conservan (las más antiguas se borran)


def undo_save(p):
    """Copia exacta del archivo antes de un cambio de la IA o de un guardado binario; se conservan las últimas UNDO_KEEP."""
    UNDO_DIR.mkdir(parents=True, exist_ok=True)
    uid = f"{time.time_ns():x}"
    shutil.copy2(p, UNDO_DIR / f"{uid}{p.suffix}")
    for old in sorted(UNDO_DIR.iterdir())[:-UNDO_KEEP]:
        old.unlink(missing_ok=True)
    return uid


def docx_undo(path, uid):
    """«↩ Deshacer»: vuelve a poner la copia guardada por undo_save (Word, imagen o PDF), de golpe.
    El id solo puede ser hexadecimal: no se puede pedir otro archivo desde la ventana."""
    if not re.fullmatch(r"[0-9a-f]+", uid or ""):
        raise ValueError("Copia para deshacer no válida")
    p, src = Path(path), UNDO_DIR / f"{uid}{Path(path).suffix}"
    if not src.is_file():
        raise ValueError("Ya no está la copia para deshacer este cambio")
    replace_atomic(p, src, "El archivo está abierto en otro programa (¿Word?): ciérralo allí y vuelve a pulsar Deshacer")
    idx_update(p)
    return {"mtime": str(p.stat().st_mtime_ns)}


def create_folder(folder, name):
    """Carpeta nueva dentro de un proyecto añadido; nombre válido en Windows y nunca reutiliza una que ya exista."""
    if not name or any(c in name for c in '\\/:*?"<>|') or name.strip(" .") == "":
        raise ValueError("Nombre de carpeta no válido")
    p = Path(folder).resolve() / name
    if not allowed(p):
        raise PermissionError("Las carpetas nuevas se crean dentro de un proyecto añadido a DeskLens")
    p.mkdir()  # FileExistsError si ya existe: nunca se reutiliza en silencio
    return str(p)


def to_trash(path):
    """«Eliminar»: a la papelera de reciclaje (Windows), la Papelera del Finder (macOS) o gio trash (Linux): se puede
    recuperar. Nunca la carpeta de un proyecto (para eso, «Quitar de DeskLens»). Un suelto eliminado sale de la lista.
    La ruta va por variable de entorno, no dentro del texto de la orden: un nombre con comillas no puede romperla."""
    p = Path(path).resolve()
    if not p.exists():
        raise FileNotFoundError(f"Ya no existe: {p}")
    if is_project(p):
        raise PermissionError("Es la carpeta de un proyecto: quítalo con «Quitar de DeskLens»")
    if WINDOWS:
        kind = "DeleteDirectory" if p.is_dir() else "DeleteFile"
        ps = ("Add-Type -AssemblyName Microsoft.VisualBasic; "
              f"[Microsoft.VisualBasic.FileIO.FileSystem]::{kind}($env:DESKLENS_RUTA, 'OnlyErrorDialogs', 'SendToRecycleBin')")
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], env={**os.environ, "DESKLENS_RUTA": str(p)},
                           capture_output=True, timeout=120, creationflags=NO_WINDOW)
    elif MAC:  # ponytail: sin probar en macOS
        r = subprocess.run(["osascript", "-e", "on run a", "-e", 'tell application "Finder" to delete (POSIX file (item 1 of a))',
                            "-e", "end run", str(p)], capture_output=True, timeout=120)
    else:
        r = subprocess.run(["gio", "trash", str(p)], capture_output=True, timeout=120)
    if p.exists():
        raise OSError((r.stderr.decode("utf-8", "replace").strip() or "No se pudo enviar a la papelera")[-300:])
    cfg = load_config()
    if str(p) in cfg["sueltos"]:
        cfg["sueltos"].remove(str(p))
        save_config(cfg)


# ---------- archivos soltados desde fuera: el navegador no da su ruta, se busca por nombre, tamaño y fecha ----------

PS_SELECTION = ("[Console]::OutputEncoding = [Text.Encoding]::UTF8; "
                "foreach ($w in (New-Object -ComObject Shell.Application).Windows()) { try { "
                "$w.Document.SelectedItems() | ForEach-Object { $_.Path }; '>' + $w.Document.Folder.Self.Path } catch {} }")
MAC_SELECTION = ['tell application "Finder"', 'set out to ""',
                 'repeat with i in (get selection)', 'set out to out & POSIX path of (i as alias) & linefeed', 'end repeat',
                 'try', 'repeat with w in Finder windows',
                 'set out to out & ">" & POSIX path of (target of w as alias) & linefeed', 'end repeat', 'end try',
                 'return out', 'end tell']


def shell_selection():
    """(seleccionados, carpetas abiertas) en las ventanas del Explorador de Windows o del Finder: de ahí suele venir
    lo que se arrastra. En Linux no hay forma común de preguntarlo: ([], [])."""
    try:
        if WINDOWS:
            r = subprocess.run(["powershell", "-NoProfile", "-Command", PS_SELECTION], capture_output=True, timeout=10,
                               creationflags=NO_WINDOW)
        elif MAC:  # ponytail: sin probar en macOS; si falla, quedan las carpetas habituales y los proyectos
            r = subprocess.run(["osascript", *[a for line in MAC_SELECTION for a in ("-e", line)]], capture_output=True, timeout=10)
        else:
            return [], []
    except (OSError, subprocess.TimeoutExpired):
        return [], []
    lines = [ln.strip() for ln in r.stdout.decode("utf-8", "replace").splitlines() if ln.strip()]
    return [ln for ln in lines if not ln.startswith(">")], [ln[1:] for ln in lines if ln.startswith(">")]


def locate_dropped(items):
    """Ruta real de cada archivo soltado ({nombre, tam, fecha en ms}): solo vale uno con el mismo nombre, tamaño
    y fecha (±2 s por FAT). Busca en lo seleccionado en el Explorador, sus carpetas abiertas, Escritorio, Descargas,
    Documentos y el índice de los proyectos. Lo hallado fuera de lo añadido pasa a «Sueltos»."""
    selected, folders = shell_selection()
    home = Path.home()
    places = folders + [str(b / n) for n in ("Desktop", "Downloads", "Documents") for b in (home, home / "OneDrive")]
    c = idx_conn()
    try:
        out = []
        for it in items:
            name, size, ms = Path(str(it.get("nombre", ""))).name, it.get("tam"), it.get("fecha") or 0

            def same(p):
                try:
                    st = p.stat()
                except OSError:
                    return False
                return p.name == name and p.is_file() and st.st_size == size and abs(st.st_mtime * 1000 - ms) < 2000

            indexed = [Path(r) for (r,) in c.execute("select path from files where name=? and size=?", (name, size))]
            hit = next((p for p in [*map(Path, selected), *(Path(f) / name for f in places), *indexed] if same(p)), None)
            out.append({"nombre": name, "ruta": str(hit.resolve()) if hit else None})
    finally:
        c.close()
    new = [o["ruta"] for o in out if o["ruta"] and not allowed(o["ruta"])]
    if new:
        add_paths("sueltos", new)
    return out


# ---------- recuperación (como Notepad++): copia de lo NO guardado; el archivo original no se toca ----------
# Sobrevive a cierres, cuelgues y reinicios. Va en historial/ (no en Temp: el liberador de Windows lo vacía).

RECOVERY_DIR = ROOT / "historial" / "recuperacion"


def recovery_path(key):
    """JSON de recuperación de una pestaña; la clave se limita a [a-z0-9-] para que no pueda salir de la carpeta."""
    if not re.fullmatch(r"[a-z0-9-]{1,64}", key or ""):
        raise ValueError("clave de recuperación no válida")
    return RECOVERY_DIR / f"{key}.json"


def recovery_save(data):
    """Copia de lo no guardado (como Notepad++) para reabrirlo tras un cierre o un apagón.
    Se escribe a un .tmp, se fuerza al disco y se renombra: nunca queda un JSON a medias."""
    RECOVERY_DIR.mkdir(parents=True, exist_ok=True)
    p = recovery_path(data.get("clave"))
    entry = {k: data.get(k) for k in ("clave", "ruta", "titulo", "texto", "mtime", "codificacion", "eol")}
    entry["fecha"] = time.time()
    tmp = p.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(entry, f, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, p)  # de golpe: un corte de luz nunca deja la copia a medias


def recovery_list():
    """Copias de recuperación pendientes, para ofrecer reabrirlas al arrancar."""
    out = []
    for f in sorted(RECOVERY_DIR.glob("*.json")) if RECOVERY_DIR.exists() else []:
        try:
            out.append(json.loads(f.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            pass
    return out


def recovery_delete(key):
    recovery_path(key).unlink(missing_ok=True)


# ---------- índice de búsqueda (SQLite FTS5) ----------
# Los archivos son la fuente; el índice se puede borrar y se regenera solo. Se indexa todo (son archivos locales),
# en segundo plano y por fecha/tamaño: al reabrir DeskLens sigue donde se quedó. Los PDF los lee la ventana (pdf.js).

INDEX_DB = ROOT / "historial" / "indice.db"
idx_state = {"fase": "esperando", "total": 0, "hechos": 0, "actual": "", "inicio": None, "fin": None}
idx_wake = threading.Event()


_idx_ready = set()  # bases ya preparadas (modo WAL y tablas): se hace una sola vez, no en cada conexión


def idx_conn():
    """Conexión al índice. El indexador escribe mientras la ventana consulta: en vez de fallar con
    «database is locked», cada conexión espera a que la base quede libre (busy_timeout)."""
    INDEX_DB.parent.mkdir(exist_ok=True)
    c = sqlite3.connect(INDEX_DB, timeout=30)
    c.execute("pragma busy_timeout=30000")
    if INDEX_DB not in _idx_ready:
        c.execute("pragma journal_mode=wal")  # lectores y un escritor a la vez
        c.executescript("""
            create table if not exists files(path text primary key, root text, name text, plain text, ext text,
                size int, mtime int, estado text, error text, paginas int, indexed real);
            create virtual table if not exists docs using fts5(path unindexed, page unindexed, body,
                tokenize='unicode61 remove_diacritics 2');""")
        _idx_ready.add(INDEX_DB)
    return c


def idx_file(c, p, root):
    """Indexa un archivo si cambió (tamaño o fecha). True si hizo algo."""
    try:
        st = p.stat()
    except OSError:
        return False
    row = c.execute("select size, mtime from files where path=?", (str(p),)).fetchone()
    if row and row[0] == st.st_size and row[1] == st.st_mtime_ns:
        return False
    estado, error, text = "ok", None, None
    try:
        if p.suffix.lower() == ".pdf":
            estado = "pdf_pendiente"  # lo lee la ventana con pdf.js
        elif p.suffix.lower() == ".docx":
            text = docx_text(p)
        else:
            with open(p, "rb") as f:
                text = decode_bytes(f.read(ajuste("indice_max_mb") * 1_000_000))[0]
            estado = "ok" if text is not None else "binario"
    except Exception as e:  # cualquier archivo raro no debe parar el índice
        estado, error = "error", str(e)[:300]
    c.execute("delete from docs where path=?", (str(p),))
    if text:
        c.execute("insert into docs values (?, 0, ?)", (str(p), text))
    c.execute("insert or replace into files values (?,?,?,?,?,?,?,?,?,?,?)",
              (str(p), str(root), p.name, " ".join(plain_words(p.name)), p.suffix.lower(), st.st_size,
               st.st_mtime_ns, estado, error, None, time.time()))
    return True


def idx_targets():
    """Todos los archivos a indexar: los de cada proyecto (sin .git) y los sueltos, cada uno con su proyecto."""
    cfg = load_config()
    for r in map(Path, cfg["proyectos"]):
        for d, dirs, files in os.walk(r):
            dirs[:] = [x for x in dirs if x != ".git"]  # la base interna de git no son archivos del usuario
            for f in files:
                yield Path(d) / f, r
    for s in map(Path, cfg["sueltos"]):
        if s.is_file():
            yield s, s.parent


def idx_pass():
    """Una pasada del indexador: añade o actualiza lo que cambió (por mtime y tamaño) y borra lo que ya no existe.
    Hace commit cada 100 archivos para que, si DeskLens se cierra, lo hecho no se repita."""
    targets = list(idx_targets())
    idx_state.update(fase="indexando", total=len(targets), hechos=0, inicio=time.time(), fin=None)
    c = idx_conn()
    try:
        for i, (p, root) in enumerate(targets, 1):
            idx_state.update(actual=str(p), hechos=i)
            if idx_file(c, p, root) and i % 100 == 0:
                c.commit()  # cada 100: si se cierra DeskLens, lo hecho queda guardado
        seen = {str(p) for p, _ in targets}
        for (path,) in c.execute("select path from files").fetchall():  # borrados o ya fuera de DeskLens
            if path not in seen:
                c.execute("delete from files where path=?", (path,))
                c.execute("delete from docs where path=?", (path,))
        c.commit()
    finally:
        c.close()
    idx_state.update(fase="al día", actual="", fin=time.time())


def indexer():
    """Hilo del índice: una pasada al arrancar y luego cada N minutos, o antes si se añade un proyecto (idx_wake).
    En cada vuelta también limpia el historial de cambios (días y tope de MB)."""
    while True:
        try:
            hist_cleanup()
        except OSError:
            pass
        try:
            idx_pass()
        except Exception as e:
            idx_state.update(fase="error", actual=str(e)[:300])
        idx_wake.wait(ajuste("indice_repaso_min") * 60)  # solo lo que cambió; antes si se añade un proyecto
        idx_wake.clear()


def idx_update(path):
    """Tras guardar o crear desde DeskLens: el índice queda al día al momento."""
    p = Path(path).resolve()
    try:
        c = idx_conn()
        idx_file(c, p, project_of(p) or p.parent)
        c.commit()
        c.close()
    except sqlite3.Error:
        pass


def idx_status():
    """Resumen del índice para su modal: archivos por estado y por tipo, páginas de PDF y los últimos errores."""
    c = idx_conn()
    try:
        por_estado = dict(c.execute("select estado, count(*) from files group by estado").fetchall())
        por_tipo = c.execute("select coalesce(nullif(ext,''),'(sin extensión)'), count(*) from files "
                             "group by ext order by 2 desc limit 12").fetchall()
        errores = c.execute("select path, error from files where estado='error' order by indexed desc limit 30").fetchall()
        pdf_pag = c.execute("select coalesce(sum(paginas),0) from files where ext='.pdf'").fetchone()[0]
    finally:
        c.close()
    size = sum(f.stat().st_size for f in INDEX_DB.parent.glob(INDEX_DB.name + "*") if f.exists())
    return {**idx_state, "por_estado": por_estado, "por_tipo": por_tipo, "errores": errores,
            "pdf_paginas": pdf_pag, "tam_db": size, "archivos": sum(por_estado.values())}


def idx_pdf_next():
    """El siguiente PDF pendiente (el más pequeño primero): su texto lo extrae la ventana con pdf.js."""
    c = idx_conn()
    try:
        row = c.execute("select path, mtime from files where estado='pdf_pendiente' order by size limit 1").fetchone()
        n = c.execute("select count(*) from files where estado='pdf_pendiente'").fetchone()[0]
    finally:
        c.close()
    return {"ruta": row[0], "mtime": str(row[1]), "pendientes": n} if row else {"ruta": None, "pendientes": 0}


def idx_pdf_save(ruta, mtime, paginas, error=None):
    """Guarda el texto por páginas que la ventana extrajo de un PDF.
    Si el PDF cambió mientras se leía (otro mtime), no se guarda: se repetirá en la próxima pasada."""
    c = idx_conn()
    try:
        row = c.execute("select mtime from files where path=?", (ruta,)).fetchone()
        if not row or str(row[0]) != str(mtime):
            return  # cambió mientras se leía: se repetirá en la próxima vuelta
        c.execute("delete from docs where path=?", (ruta,))
        pages = [(ruta, int(pg["n"]), pg["texto"]) for pg in paginas if (pg.get("texto") or "").strip()]
        c.executemany("insert into docs values (?,?,?)", pages)
        estado = "error" if error else ("ok" if pages else "pdf_sin_texto")
        c.execute("update files set estado=?, error=?, paginas=?, indexed=? where path=?",
                  (estado, error, len(paginas), time.time(), ruta))
        c.commit()
    finally:
        c.close()


def search_scope(raices):
    """Filtro SQL (texto, argumentos) para buscar solo en esos proyectos; «sueltos» = los archivos sueltos.
    None = en todo lo añadido."""
    if raices is None:
        return "1", []
    roots = [str(Path(r).resolve()) for r in raices if r != "sueltos"]
    loose = [str(Path(s).resolve()) for s in load_config()["sueltos"]] if "sueltos" in raices else []
    conds = ([f"files.root in ({','.join('?' * len(roots))})"] if roots else []) + \
            ([f"files.path in ({','.join('?' * len(loose))})"] if loose else [])
    return "(" + " or ".join(conds) + ")" if conds else "0", roots + loose


def search(q, limit=60, nombre=True, contenido=True, exacto=False, raices=None):
    """Por nombre (todas las palabras) y/o por contenido (FTS5; "frases" entre comillas).
    Sin «exacto», da igual mayúsculas y tildes; con «exacto» (Aa) cada palabra debe aparecer tal cual se escribió.
    raices: proyectos donde buscar (y «sueltos»); None = en todos."""
    phrases = [p for p in re.findall(r'"([^"]+)"', q) if plain_words(p)]
    rest = re.sub(r'"[^"]*"', " ", q)
    words = plain_words(rest)
    literal = phrases + rest.split()  # para «exacto»: las palabras tal cual se escribieron
    scope, scope_args = search_scope(raices)
    c = idx_conn()
    try:
        names = []
        name_words = words + [w for p in phrases for w in plain_words(p)]
        if nombre and name_words:
            where = " and ".join("plain like ?" for _ in name_words)
            names = c.execute(f"select path, name, root from files where {where} and {scope} order by length(name) limit ?",
                              [f"%{w}%" for w in name_words] + scope_args + [limit * 4]).fetchall()
            if exacto:  # mayúsculas y tildes tal cual (el filtro de arriba es amplio a propósito)
                names = [n for n in names if all(w.lstrip(".") in n[1] for w in literal)]
            names = names[:limit]
        content = []
        terms = [f'"{" ".join(plain_words(p))}"' for p in phrases] + [f"{w}*" for w in words if len(w) > 1]
        if contenido and terms:
            exact = " and ".join("instr(docs.body, ?) > 0" for _ in literal) if exacto else ""
            try:
                content = c.execute(
                    "select docs.path, docs.page, snippet(docs, 2, '[[', ']]', '…', 14), files.name, files.root "
                    f"from docs join files on files.path = docs.path where docs match ? and {scope} "
                    + (f"and {exact} " if exact else "") + "order by rank limit ?",
                    [" ".join(terms), *scope_args, *(literal if exacto else []), limit]).fetchall()
            except sqlite3.OperationalError:
                content = []
    finally:
        c.close()
    return {"nombres": [{"ruta": p, "nombre": n, "raiz": r} for p, n, r in names],
            "contenido": [{"ruta": p, "pagina": pg, "fragmento": s, "nombre": n, "raiz": r} for p, pg, s, n, r in content]}


# ---------- git: estado por archivo (un "git status" por repositorio, en caché 10 s) ----------

git_cache = {}


def git_root(d):
    """La carpeta del repositorio git que contiene `d` (la que tiene .git), o None."""
    for x in [d, *d.parents]:
        if (x / ".git").exists():
            return x
    return None


def git_run(repo, *args):
    """Ejecuta una orden de git en el repositorio y devuelve su salida, o «» si falla."""
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, timeout=20,
                       creationflags=NO_WINDOW)
    return r.stdout.decode("utf-8", "replace").strip() if r.returncode == 0 else ""


def git_log(path):
    """Commits que tocaron el archivo (sigue renombres): hash, fecha, autor, mensaje y su ruta en ese commit."""
    p = Path(path).resolve()
    repo = git_root(p.parent)
    if not repo:
        return {"repositorio": None, "commits": []}
    rel = str(p.relative_to(repo)).replace("\\", "/")
    out = git_run(repo, "-c", "core.quotePath=false", "log", "--follow", "-n", "1000", "--name-only", "--date=format:%d/%m/%Y %H:%M",
                  "--format=\x1e%H\x1f%h\x1f%ad\x1f%an\x1f%s\x1f%at", "--", rel)
    commits = []
    for rec in filter(None, out.split("\x1e")):  # git_run hace strip(), que también quita el primer \x1e
        head, _, names = rec.partition("\n")
        h, short, date, author, msg, ts = (head.split("\x1f") + [""] * 6)[:6]
        name = next((n for n in names.splitlines() if n.strip()), rel)
        commits.append({"hash": h, "corto": short, "fecha": date, "autor": author, "mensaje": msg, "ruta": name,
                        "ts": int(ts or 0), "n": None})
    # cuántos archivos cambió cada commit en total: con la ruta en el log, --shortstat contaría solo este archivo, así que
    # va en una 2.ª llamada sin ruta (una sola para todos). ponytail: 1000 hashes ≈ 41 KB de línea de órdenes, bajo el
    # límite de Windows (32 K caracteres) solo hasta ~780; más allá se queda sin número (n = None)
    if commits and len(commits) <= 700:
        cnt = git_run(repo, "log", "--no-walk=unsorted", "--diff-merges=first-parent", "--format=\x1e%H", "--shortstat", *(c["hash"] for c in commits))
        by = {c["hash"]: c for c in commits}
        for rec in filter(None, cnt.split("\x1e")):
            h, _, st = rec.partition("\n")
            if h.strip() in by:
                m = re.search(r"(\d+) files? changed", st)
                by[h.strip()]["n"] = int(m.group(1)) if m else 0  # merge: lo que trajo (contra su 1.er padre, como git_files)
    return {"repositorio": str(repo), "rel": rel, "commits": commits}


def git_files(path, commit):
    """Archivos que tocó un commit: [{estado: M/A/D/R…, ruta (absoluta), rel, antes, mas, menos}]; en un merge, frente
    al 1.er padre. path: un archivo del repositorio o la carpeta del repositorio. mas/menos: líneas (None si es binario)."""
    p = Path(path).resolve()
    repo = git_root(p if p.is_dir() else p.parent)
    if not repo or not re.fullmatch(r"[0-9a-f]{4,40}", commit):
        raise ValueError("commit no válido")
    q = ("-c", "core.quotePath=false")  # rutas con tildes tal cual, sin "\303\255"
    out = git_run(repo, *q, "show", "--format=", "--name-status", "-M", "--diff-merges=first-parent", commit) \
        or git_run(repo, *q, "show", "--format=", "--name-status", "-M", commit)  # git viejo: sin --diff-merges
    files = []
    for ln in out.splitlines():
        parts = ln.split("\t")
        if len(parts) < 2:
            continue
        rel = parts[-1]
        files.append({"estado": parts[0][:1], "rel": rel, "antes": parts[1] if len(parts) > 2 else None,
                      "ruta": str(repo / Path(rel)), "mas": None, "menos": None})
    stat = git_run(repo, *q, "show", "--format=", "--numstat", "-M", "--diff-merges=first-parent", commit)
    nums = {}
    for ln in stat.splitlines():  # «12\t3\truta» («-\t-» si es binario; renombrado: «viejo => nuevo»)
        a, d, *rest = ln.split("\t") + ["", ""]
        rel = rest[0]
        rel = re.sub(r"\{[^{}]* => ([^{}]*)\}", r"\1", rel).replace("//", "/") if "=>" in rel else rel
        rel = rel.split(" => ")[-1]
        nums[rel] = (int(a) if a.isdigit() else None, int(d) if d.isdigit() else None)
    for f in files:
        f["mas"], f["menos"] = nums.get(f["rel"], (None, None))
    return {"repositorio": str(repo), "archivos": files}


def git_commit_info(path, commit):
    """Todo lo de un commit para su detalle: mensaje completo, autor con email, fecha (epoch, la ventana la muestra
    absoluta y relativa), quien lo aplicó si es otro, padres completos, ramas y etiquetas que lo contienen y el
    tamaño de cada archivo en ese commit ({ruta relativa: bytes})."""
    repo = repo_of(path)
    if not re.fullmatch(r"[0-9a-f]{4,40}", commit or ""):
        raise ValueError("commit no válido")
    out = git_do(repo, "show", "-s", "--format=%H%x1f%P%x1f%an%x1f%ae%x1f%at%x1f%cn%x1f%ce%x1f%B", commit)
    h, parents, an, ae, at, cn, ce, body = (out.split("\x1f") + [""] * 8)[:8]
    ramas = git_run(repo, "branch", "-a", "--contains", h, "--format=%(refname:short)").splitlines()
    etiquetas = git_run(repo, "tag", "--contains", h).splitlines()
    changed = [ln.split("\t")[-1] for ln in git_run(repo, "-c", "core.quotePath=false", "show", "--format=", "--name-only",
                                                       "--diff-merges=first-parent", h).splitlines() if ln]
    sizes = {}
    if changed and len(changed) <= 400:  # ponytail: con más archivos no se piden tamaños (línea de órdenes de Windows ~32 KB)
        for ln in git_run(repo, "-c", "core.quotePath=false", "ls-tree", "-l", h, "--", *changed).splitlines():
            meta, _, rel = ln.partition("\t")  # «100644 blob <hash>     1234\truta»
            size = meta.split()[-1]
            if size.isdigit():
                sizes[rel] = int(size)
    return {"hash": h, "padres": parents.split(), "autor": an, "email": ae, "fecha": int(at or 0),
            "aplico": cn if (cn, ce) != (an, ae) else None, "mensaje": body.strip(),
            "ramas": [r for r in ramas if not r.endswith("/HEAD") and r != "origin"], "etiquetas": etiquetas, "tamanos": sizes}


def git_blob(path, commit, rel):
    """Bytes de un archivo tal como estaba en un commit (para ver imágenes antes/después). Hasta 30 MB."""
    repo = repo_of(path)
    if not re.fullmatch(r"[0-9a-f]{4,40}", commit or "") or not rel or rel.startswith(("-", ":")):
        raise ValueError("versión no válida")
    r = subprocess.run(["git", "-C", str(repo), "show", f"{commit}:{rel}"], capture_output=True, timeout=30, creationflags=NO_WINDOW)
    if r.returncode:
        raise ValueError(r.stderr.decode("utf-8", "replace").strip() or "no existe en esa versión")
    if len(r.stdout) > 30_000_000:
        raise ValueError("demasiado grande para mostrarlo")
    return r.stdout


def git_graph(path, todas=False, limit=300):
    """Historial para la pantalla completa de Git: la rama actual y su remota (o todas las ramas), del más nuevo al más
    viejo, con padres (para dibujar el grafo), etiquetas de ramas y si cada commit es entrante (está en el remoto y aún
    no se ha traído) o saliente (es tuyo y aún no se ha subido), como el grafo de VS Code."""
    repo = repo_of(path)
    if not git_run(repo, "rev-parse", "-q", "--verify", "HEAD"):
        return {"commits": [], "remota": None, "mas": False}
    up = git_run(repo, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    refs = ["--branches", "--remotes", "--tags", "HEAD"] if todas else ["HEAD", *([up] if up else [])]
    out = git_do(repo, "-c", "core.quotePath=false", "log", "--date-order", f"-n{limit}", "--date=format:%d/%m/%Y %H:%M",
                 "--format=%x1e%H%x1f%P%x1f%h%x1f%an%x1f%ad%x1f%s%x1f%D%x1f%at", *refs, "--")
    incoming = set(git_run(repo, "rev-list", f"HEAD..{up}").split()) if up else set()
    outgoing = set(git_run(repo, "rev-list", f"{up}..HEAD").split()) if up else set()
    commits = []
    for rec in out.split("\x1e"):
        if not rec.strip():
            continue
        h, parents, short, author, date, subject, deco, ts = (rec.strip("\n").split("\x1f") + [""] * 8)[:8]
        commits.append({"hash": h, "padres": parents.split(), "corto": short, "autor": author, "fecha": date, "ts": int(ts or 0),
                        "mensaje": subject, "refs": [r.strip() for r in deco.split(",") if r.strip()],
                        "lado": "entrante" if h in incoming else "saliente" if h in outgoing else ""})
    return {"commits": commits, "remota": up or None, "mas": len(commits) >= limit}


def git_version(path, commit, rel):
    """Texto del archivo en un commit (rel: su ruta en ese commit, puede haber cambiado de nombre)."""
    repo = git_root(Path(path).resolve().parent)
    if not repo or not re.fullmatch(r"[0-9a-f]{4,40}", commit) or rel.startswith(("-", ":")):
        raise ValueError("commit no válido")
    r = subprocess.run(["git", "-C", str(repo), "show", f"{commit}:{rel}"], capture_output=True, timeout=20,
                       creationflags=NO_WINDOW)
    if r.returncode:
        raise ValueError(r.stderr.decode("utf-8", "replace").strip() or "no se pudo leer esa versión")
    if len(r.stdout) > ajuste("vista_max_mb") * 1_000_000:
        raise ValueError("esa versión es demasiado grande para compararla")
    text, _ = decode_bytes(r.stdout)
    if text is None:
        raise ValueError("es un archivo binario: no se puede comparar como texto")
    return text


def git_blame(path, commit="", rel="", text=None):
    """Autor de cada línea: en un commit, en el disco (commit vacío) o en el texto del editor (text).
    Devuelve {"commits": [...], "lineas": [índice en commits por línea]}; lo no confirmado lleva local=True."""
    p = Path(path).resolve()
    repo = git_root(p.parent)
    if not repo:
        raise ValueError("no está en git")
    rel = rel or str(p.relative_to(repo)).replace("\\", "/")
    if commit and not re.fullmatch(r"[0-9a-f]{4,40}", commit) or rel.startswith(("-", ":")):
        raise ValueError("commit no válido")
    args = ["git", "-C", str(repo), "blame", "--porcelain"] + (["--contents", "-"] if text is not None else []) \
        + ([commit] if commit else []) + ["--", rel]
    r = subprocess.run(args, input=text.encode("utf-8") if text is not None else None, capture_output=True,
                       timeout=30, creationflags=NO_WINDOW)
    if r.returncode:
        raise ValueError(r.stderr.decode("utf-8", "replace").strip() or "git blame falló")
    info, order, lines, h = {}, {}, [], None
    for ln in r.stdout.decode("utf-8", "replace").split("\n"):
        if ln.startswith("\t"):
            lines.append(order.setdefault(h, len(order)))
        elif re.match(r"[0-9a-f]{40} \d+ \d+", ln):
            h = ln[:40]
            info.setdefault(h, {})
        elif h and " " in ln:
            k, v = ln.split(" ", 1)
            info[h].setdefault(k, v)
    commits = [None] * len(order)
    for h, i in order.items():
        d, local = info[h], set(h) == {"0"}
        when = time.strftime("%d/%m/%Y %H:%M", time.localtime(int(d.get("author-time", 0))))
        commits[i] = {"hash": h, "corto": h[:7], "autor": "Sin commit" if local else d.get("author", ""),
                      "fecha": when, "ts": int(d.get("author-time", 0)),
                      "mensaje": "cambio local" if local else d.get("summary", ""), "local": local}
    return {"commits": commits, "lineas": lines}


def git_status_map(repo):
    """Estado de git de todo el repositorio de una vez (git status --porcelain -z, con ignorados), en caché
    unos segundos: el árbol pregunta por muchos archivos seguidos. Devuelve archivos y carpetas enteras."""
    t, files, dirs = git_cache.get(repo, (0, None, None))
    if files is not None and time.time() - t < ajuste("git_cache_seg"):
        return files, dirs
    r = subprocess.run(["git", "-C", str(repo), "status", "--porcelain=v1", "-z", "--ignored", "--untracked-files=all"],
                       capture_output=True, timeout=30, creationflags=NO_WINDOW)
    files, dirs, entries, i = {}, {}, r.stdout.decode("utf-8", "replace").split("\0"), 0
    while i < len(entries):
        e = entries[i]
        i += 1
        if len(e) < 4:
            continue
        xy, rel = e[:2], e[3:]
        if xy[0] in "RC":
            i += 1  # renombrado/copiado: viene también la ruta original
        full = os.path.normcase(str(repo / rel.rstrip("/")))
        (dirs if rel.endswith("/") else files)[full] = xy
    git_cache[repo] = (time.time(), files, dirs)
    return files, dirs


# ---------- vista Git: cambios, preparar, commit, ramas, pull/push/merge (como el control de código de VS Code) ----------
# Las órdenes rápidas se ejecutan aquí y devuelven el estado nuevo; pull, push, fetch y merge van a la consola de DeskLens
# (pueden tardar y su salida interesa). Las credenciales son las de git del usuario (Git Credential Manager): DeskLens no
# las ve. GIT_TERMINAL_PROMPT=0: git nunca se queda esperando una contraseña por la terminal (no hay ninguna).

GIT_ENV = {"GIT_TERMINAL_PROMPT": "0"}
GIT_CONFLICT = {"DD", "AU", "UD", "UA", "DU", "AA", "UU"}


def repo_of(path):
    """Raíz del repositorio git de un proyecto o archivo añadido; ValueError si no está en git."""
    p = Path(path).resolve()
    repo = git_root(p if p.is_dir() else p.parent)
    if not repo:
        raise ValueError("No está en un repositorio git")
    return repo


def git_do(repo, *args, timeout=60, stdin=None):
    """Ejecuta git en el repositorio; ValueError con lo que dijo git si falla (para mostrarlo tal cual)."""
    r = subprocess.run(["git", "-C", str(repo), *args], input=stdin, capture_output=True, timeout=timeout,
                       creationflags=NO_WINDOW, env={**os.environ, **GIT_ENV})
    if r.returncode:
        raise ValueError((r.stderr or r.stdout).decode("utf-8", "replace").strip()[-800:] or "git falló")
    return r.stdout.decode("utf-8", "replace")


def git_overview(path):
    """Estado del repositorio para la vista Git: rama, remota, commits por subir/bajar, ramas locales y los archivos
    preparados, con cambios y en conflicto (estado de una letra como VS Code: M, A, D, R, U = sin seguimiento)."""
    repo = repo_of(path)
    # en Windows cada proceso de git cuesta ~40 ms: las consultas sueltas van en paralelo mientras corre el status
    with ThreadPoolExecutor(8) as ex:
        q = {k: ex.submit(git_run, repo, *a) for k, a in {
            "ramas": ("branch", "--format=%(refname:short)"),
            "remotas": ("branch", "-r", "--format=%(refname:short)"),
            "head": ("rev-parse", "-q", "--verify", "HEAD"),
            "up": ("rev-parse", "-q", "--verify", "@{u}"),
            "remotos": ("remote",),
            "stash": ("-c", "core.quotePath=false", "stash", "list", "--format=%gd\x1f%s\x1f%cr"),
            "merge": ("rev-parse", "-q", "--verify", "MERGE_HEAD"),
            "revert": ("rev-parse", "-q", "--verify", "REVERT_HEAD"),
            # cada rama local con la remota que sigue y cuánto va por delante/detrás: «[ahead 3, behind 2]», «[gone]»
            "track": ("for-each-ref", "--format=%(refname:short)\x1f%(upstream:short)\x1f%(upstream:track)", "refs/heads"),
            "urls": ("config", "--get-regexp", r"^remote\..*\.url$")}.items()}
        fetched = ex.submit(git_fetch_time, repo)
        out = git_do(repo, "-c", "core.quotePath=false", "status", "--porcelain=v1", "-z", "--branch", "--untracked-files=all")
        q = {k: f.result() for k, f in q.items()}
    entries = out.split("\0")
    head = entries[0][3:] if entries and entries[0].startswith("## ") else ""
    # «main...origin/main [ahead 1, behind 2]» · «No commits yet on main» · «HEAD (no branch)»
    m = re.match(r"(?:No commits yet on |Initial commit on )?(.+?)(?:\.\.\.(\S+))?(?: \[(.*)\])?$", head)
    branch, upstream, info = m.groups() if m else (head, None, "")
    num = lambda k: int(x.group(1)) if (x := re.search(k + r" (\d+)", info or "")) else 0
    staged, changes, conflicts, i = [], [], [], 1
    while i < len(entries):
        e = entries[i]
        i += 1
        if len(e) < 4:
            continue
        xy, rel = e[:2], e[3:]
        if xy[0] in "RC":
            i += 1  # renombrado/copiado: después viene la ruta original
        item = lambda st: {"estado": st, "rel": rel, "ruta": str(repo / rel)}
        if xy in GIT_CONFLICT:
            conflicts.append(item("!"))
        elif xy == "??":
            changes.append(item("U"))
        else:
            if xy[0] not in " ?!":
                staged.append(item(xy[0]))
            if xy[1] not in " ?!":
                changes.append(item(xy[1]))
    git_cache.pop(repo, None)  # el punto de color del árbol se pone al día con lo que se acaba de ver
    return {"repositorio": str(repo), "nombre": repo.name, "rama": branch, "remota": upstream,
            "adelante": num("ahead"), "atras": num("behind"),
            "ramas": q["ramas"].splitlines(),
            "ramas_remotas": [b for b in q["remotas"].splitlines() if not b.endswith("/HEAD") and "/" in b],
            "punta": q["head"] + ":" + q["up"],
            "remotos": q["remotos"].splitlines(),
            # cambios guardados aparte (stash): [{id: stash@{N}, mensaje, fecha}], el más reciente primero
            "stashes": [dict(zip(("id", "mensaje", "fecha"), ln.split("\x1f"))) for ln in q["stash"].splitlines() if ln],
            "fusionando": bool(q["merge"] or q["revert"]),  # merge o revert a medias
            "ramas_info": [git_track(ln) for ln in q["track"].splitlines() if ln],
            "servicio": git_service(q["urls"]),
            "comprobado": fetched.result(),
            "preparados": staged, "cambios": changes, "conflictos": conflicts}


def git_ignored(path):
    """Lo que git ignora en el repositorio (una carpeta ignorada entera va como una sola entrada «dir/») y lo que está en
    un .gitignore pero git ya seguía (ahí el .gitignore no hace nada), cada uno con la regla que lo ignora. Las carpetas
    van sin tamaño: la ventana lo pide aparte (folder_size) para no esperar a recorrer node_modules y similares."""
    repo = repo_of(path)
    out = git_do(repo, "-c", "core.quotePath=false", "status", "--ignored", "--porcelain=v1", "-z", "--untracked-files=normal")
    rels = [e[3:] for e in out.split("\0") if e.startswith("!! ")]
    tracked = [r for r in git_do(repo, "-c", "core.quotePath=false", "ls-files", "-ci", "--exclude-standard", "-z").split("\0") if r]
    rules = {}
    if rels or tracked:
        r = subprocess.run(["git", "-C", str(repo), "-c", "core.quotePath=false", "check-ignore", "-v", "-z", "--no-index", "--stdin"],
                           input="\0".join(rels + tracked).encode("utf-8"), capture_output=True, timeout=60, creationflags=NO_WINDOW)
        f = r.stdout.decode("utf-8", "replace").split("\0")  # origen, línea, patrón, ruta (y así sucesivamente)
        for i in range(0, len(f) - 3, 4):
            if f[i]:
                rules[f[i + 3]] = {"archivo": f[i], "linea": int(f[i + 1] or 0), "patron": f[i + 2]}

    def item(rel):
        p = repo / rel.rstrip("/")
        d = rel.endswith("/")
        try:
            size = None if d else p.lstat().st_size
        except OSError:
            size = None
        return {"rel": rel.rstrip("/"), "ruta": str(p), "dir": d, "tam": size, "regla": rules.get(rel)}
    return {"repositorio": str(repo), "ignorados": [item(r) for r in rels], "seguidos": [item(r) for r in tracked]}


def folder_size(path):
    """Archivos y bytes de una carpeta, recursivo y sin seguir enlaces."""
    n = size = 0
    for d, _, files in os.walk(path):
        for f in files:
            try:
                size += os.lstat(os.path.join(d, f)).st_size
                n += 1
            except OSError:
                pass
    return {"archivos": n, "tam": size}


def folder_items(path):
    """Contenido de una carpeta con el tamaño de cada archivo (las subcarpetas, sin tamaño: se pide con folder_size)."""
    items = []
    for e in os.scandir(path):
        try:
            d = e.is_dir(follow_symlinks=False)
            items.append({"nombre": e.name, "ruta": e.path, "dir": d, "tam": None if d else e.stat(follow_symlinks=False).st_size})
        except OSError:
            pass
    return items


def git_track(line):
    """Una línea de for-each-ref («rama␟origin/rama␟[ahead 1, behind 2]») → {rama, remota, adelante, atras, borrada}."""
    name, up, track = (line.split("\x1f") + ["", ""])[:3]
    num = lambda k: int(m.group(1)) if (m := re.search(k + r" (\d+)", track)) else 0
    return {"rama": name, "remota": up or None, "adelante": num("ahead"), "atras": num("behind"), "borrada": track == "[gone]"}


def git_service(urls):
    """Nombre del servicio del primer remoto para la interfaz («GitHub», «GitLab»…); «el remoto» si no se reconoce."""
    url = urls.split(" ", 1)[1] if " " in urls.split("\n", 1)[0] else ""
    for host, name in (("github", "GitHub"), ("gitlab", "GitLab"), ("bitbucket", "Bitbucket"), ("dev.azure", "Azure DevOps")):
        if host in url.lower():
            return name
    return "el remoto" if url else None


def git_fetch_time(repo):
    """Cuándo se miró el remoto por última vez (fecha de FETCH_HEAD: fetch, pull o el fetch automático); None si nunca."""
    f = git_run(repo, "rev-parse", "--git-path", "FETCH_HEAD")
    f = Path(f) if Path(f).is_absolute() else Path(repo) / f
    return f.stat().st_mtime if f.is_file() else None


def git_summary():
    """Estado de git de cada proyecto para el selector de la vista Git: rama, ↓↑ y número de cambios (None si no es git)."""
    def one(r):
        try:
            ov = git_overview(r)
            return {"ruta": r, "rama": ov["rama"], "remota": ov["remota"], "adelante": ov["adelante"],
                    "atras": ov["atras"], "cambios": len(ov["cambios"]) + len(ov["preparados"]) + len(ov["conflictos"])}
        except (ValueError, OSError, subprocess.TimeoutExpired):
            return {"ruta": r, "rama": None}
    with ThreadPoolExecutor(4) as ex:  # los proyectos a la vez, no uno tras otro
        return list(ex.map(one, load_config()["proyectos"]))


def git_autofetch():
    """Hilo: cada N minutos (⚙ Ajustes, 0 = nunca) hace fetch de los proyectos con remoto, para que ↓ diga si hay
    novedades sin pulsar nada. Sin ventanas: GCM_INTERACTIVE=never evita que salga a pedir credenciales; si las
    pide, ese repositorio simplemente no se pone al día hasta el siguiente pull o fetch a mano."""
    time.sleep(20)  # que arranque primero lo demás
    while True:
        mins = ajuste("git_fetch_min")
        if mins:
            seen = set()
            for r in load_config()["proyectos"]:
                repo = git_root(Path(r))
                if not repo or repo in seen or not git_run(repo, "remote"):
                    continue
                seen.add(repo)
                try:
                    subprocess.run(["git", "-C", str(repo), "fetch", "--prune", "--quiet"], capture_output=True, timeout=120,
                                   creationflags=NO_WINDOW, env={**os.environ, **GIT_ENV, "GCM_INTERACTIVE": "never"})
                except (OSError, subprocess.TimeoutExpired):
                    pass
        time.sleep((mins or 5) * 60)


def git_rel(repo, rels):
    """Rutas relativas pedidas por la ventana, comprobando que no salen del repositorio."""
    out = []
    for r in rels:
        p = (repo / str(r)).resolve()
        if not p.is_relative_to(repo):
            raise ValueError(f"Ruta fuera del repositorio: {r}")
        out.append(str(p.relative_to(repo)).replace("\\", "/"))
    return out


def git_branch_name(repo, name):
    """Nombre de rama válido para git (git check-ref-format), o ValueError."""
    name = str(name or "").strip()
    if not name or name.startswith("-"):
        raise ValueError("Nombre de rama no válido")
    git_do(repo, "check-ref-format", "--branch", name)
    return name


class GitLocalChanges(ValueError):
    """git no cambia de rama porque perdería cambios sin commit: lleva los archivos afectados para que la ventana
    ofrezca llevarlos a la otra rama o guardarlos a un lado (stash)."""

    def __init__(self, archivos, destino):
        self.archivos, self.destino = archivos, destino
        n = len(archivos)
        super().__init__(f"Tienes cambios sin commit en {n} archivo{'s' if n != 1 else ''} que también "
                         f"{'son distintos' if n != 1 else 'es distinto'} en «{destino}». Git no cambia de rama para no perderlos.")


def git_switch(repo, name, modo=""):
    """Cambia a la rama `name`. Si git se niega por cambios sin commit, GitLocalChanges con los archivos.
    modo «llevar»: guarda los cambios (stash), cambia y los vuelve a poner en la rama nueva (como «Migrate changes»
    de VS Code); si chocan con ella, quedan en conflicto para resolverlos y el stash se conserva.
    modo «apartar»: los guarda en el stash con un nombre claro y cambia (se recuperan con git stash pop)."""
    guardado = False
    if modo in ("llevar", "apartar"):
        actual = git_run(repo, "rev-parse", "--abbrev-ref", "HEAD")
        antes = git_run(repo, "rev-parse", "-q", "--verify", "refs/stash")
        git_do(repo, "stash", "push", "-u", "-m", f"DeskLens: cambios de «{actual}» al pasar a «{name}»")
        # sin nada que guardar no se crea stash: entonces no hay que sacar ninguno (sería uno viejo, ajeno)
        guardado = git_run(repo, "rev-parse", "-q", "--verify", "refs/stash") != antes
    try:
        git_do(repo, "switch", name)
    except ValueError as e:
        if guardado:
            git_run(repo, "stash", "pop")  # no se pudo cambiar: los cambios vuelven a donde estaban
        if modo:
            raise
        files = re.findall(r"^\t(.+)$", str(e), re.M)  # git los lista con un tabulador delante
        if "would be overwritten" in str(e) and files:
            raise GitLocalChanges(files, name)
        raise
    if modo == "llevar" and guardado:
        try:
            git_do(repo, "stash", "pop")
        except ValueError:
            raise ValueError(f"Ya estás en «{name}», pero algunos de tus cambios chocan con esta rama: aparecen en "
                             "«Conflictos» para resolverlos. Una copia sigue guardada en el stash por si acaso.")


def git_action(path, accion, archivos=(), mensaje="", rama="", todo=False, modo=""):
    """Una acción de la vista Git. Las rápidas devuelven el estado nuevo; pull, push, fetch y merge arrancan en la
    consola y devuelven {"id"} para seguir su salida. «descartar» envía a la papelera lo que no tiene seguimiento."""
    repo = repo_of(path)
    files = git_rel(repo, archivos)
    no_head = not git_run(repo, "rev-parse", "-q", "--verify", "HEAD")
    if accion == "preparar":
        git_do(repo, "add", "-A", "--", *(files or ["."]))
    elif accion == "quitar":  # sacar de preparados (sin commits todavía no hay HEAD al que volver)
        if no_head:
            git_do(repo, "rm", "-r", "--cached", "-q", "--", *(files or ["."]))
        else:
            git_do(repo, "restore", "--staged", "--", *(files or ["."]))
    elif accion == "descartar":
        untracked = set(git_do(repo, "ls-files", "--others", "--exclude-standard", "-z", "--", *files).split("\0")) - {""}
        tracked = [f for f in files if f not in untracked]
        if tracked:
            git_do(repo, "restore", "--", *tracked)
        for f in untracked:
            if not allowed(repo / f):  # repo más grande que el proyecto añadido: fuera de él no se borra nada
                raise PermissionError(f"«{f}» está fuera de lo añadido a DeskLens")
            to_trash(repo / f)
    elif accion == "commit":
        if not mensaje.strip():
            raise ValueError("Escribe el mensaje del commit")
        if todo:
            git_do(repo, "add", "-A")
        git_do(repo, "commit", "-F", "-", stdin=mensaje.strip().encode("utf-8"))
    elif accion == "cambiar_rama":
        git_switch(repo, git_branch_name(repo, rama), modo)
    elif accion == "nueva_rama":
        git_do(repo, "switch", "-c", git_branch_name(repo, rama))
    elif accion == "recuperar_stash":  # vuelve a poner los cambios guardados aparte; si chocan, quedan en conflicto
        if not re.fullmatch(r"stash@\{\d+\}", rama):
            raise ValueError("Cambios guardados no válidos")
        try:
            git_do(repo, "stash", "pop", rama)
        except ValueError:
            raise ValueError("Algunos de los cambios guardados chocan con lo que hay ahora: aparecen en «Conflictos». "
                             "Siguen guardados en el stash por si acaso.")
    elif accion == "rama_desde":  # crear una rama en un commit del historial (sin cambiar a ella)
        if not re.fullmatch(r"[0-9a-f]{4,40}", mensaje):
            raise ValueError("commit no válido")
        git_do(repo, "branch", git_branch_name(repo, rama), mensaje)
    elif accion == "revertir":  # commit nuevo que deshace ese commit (en un merge, respecto a su 1.er padre)
        if not re.fullmatch(r"[0-9a-f]{4,40}", mensaje):
            raise ValueError("commit no válido")
        merge = len(git_run(repo, "rev-list", "--parents", "-n1", mensaje).split()) > 2
        try:
            git_do(repo, "revert", "--no-edit", *(["-m", "1"] if merge else []), mensaje)
        except ValueError as e:
            if "conflict" in str(e).lower():
                raise ValueError("Deshacer ese commit choca con cambios posteriores: los archivos aparecen en «Conflictos». "
                                 "Resuélvelos, márcalos con + y haz commit (o «git revert --abort» para cancelar).")
            raise
    elif accion == "deshacer_commit":  # solo un commit que aún no se ha subido (sigue en la rama, en preparados)
        ov = git_overview(repo)
        if ov["remota"] and not ov["adelante"]:
            raise ValueError("El último commit ya está subido: deshacerlo aquí no lo quita del remoto")
        if not git_run(repo, "rev-parse", "-q", "--verify", "HEAD~1"):
            raise ValueError("Es el primer commit del repositorio: no hay uno anterior al que volver")
        git_do(repo, "reset", "--soft", "HEAD~1")
    elif accion in ("pull", "push", "fetch", "fusionar", "sincronizar"):
        ov = git_overview(repo)
        if accion == "sincronizar" and ov["remota"]:  # como VS Code: primero trae y luego sube (si hay algo tuyo)
            cmd = "git pull --no-rebase" + (" && git push" if ov["adelante"] else "")
            return {"id": start_run(f"cmd /c {cmd}" if WINDOWS else ["sh", "-c", cmd], str(repo), "utf-8",
                                    f"git sincronizar · {repo.name}", GIT_ENV), "orden": cmd}
        if accion == "pull":
            args = ["pull", "--no-rebase"]
        elif accion == "fetch":
            args = ["fetch", "--prune"]
        elif accion == "fusionar":
            args = ["merge", "--no-edit", git_branch_name(repo, rama)]
        elif ov["remota"]:
            args = ["push"]  # (sincronizar sin rama remota también llega aquí: se publica la rama)
        elif ov["remotos"]:  # rama sin seguimiento: se sube al primer remoto (origin) y queda enlazada
            args = ["push", "-u", "origin" if "origin" in ov["remotos"] else ov["remotos"][0], ov["rama"]]
        else:
            raise ValueError("Este repositorio no tiene remoto: añade uno (git remote add origin <url>)")
        return {"id": start_run(["git", *args], str(repo), "utf-8", f"git {accion} · {repo.name}", GIT_ENV),
                "orden": "git " + " ".join(args)}
    else:
        raise ValueError(f"Acción de git desconocida: {accion}")
    return git_overview(repo)


GIT_TEXT = {"limpio": "Git: sin cambios", "modificado": "Git: modificado", "nuevo": "Git: nuevo (sin commit)",
            "conflicto": "Git: conflicto", "ignorado": "Git: ignorado (.gitignore)", "sin_git": "No está en git"}


def git_state(p):
    """Estado de git de un archivo para el punto del árbol: limpio, modificado, nuevo, conflicto, ignorado o sin_git."""
    p = Path(p)
    repo = git_root(p.parent)
    if not repo:
        return "sin_git"
    try:
        files, dirs = git_status_map(repo)
    except (OSError, subprocess.TimeoutExpired):
        return "sin_git"
    key = os.path.normcase(str(p))
    xy = files.get(key) or next((v for d, v in dirs.items() if key.startswith(d + os.sep)), None)
    if xy is None:
        return "limpio"
    if xy == "??":
        return "nuevo"
    if xy == "!!":
        return "ignorado"
    if "U" in xy or xy in ("AA", "DD"):
        return "conflicto"
    if xy[0] == "A":
        return "nuevo"
    return "modificado"


# ---------- información de un archivo (modal ⓘ) ----------

def _pdf_str(raw, key):
    """Un campo del diccionario de información de un PDF (/Title, /Author…), en texto (paréntesis) o hexadecimal, en UTF-16 o Latin-1."""
    m = re.search(rb"/" + key + rb"\s*\(((?:\\.|[^\\)])*)\)", raw) or re.search(rb"/" + key + rb"\s*<([0-9A-Fa-f]+)>", raw)
    if not m:
        return ""
    v = m.group(1)
    if m.re.pattern.endswith(b">"):
        v = bytes.fromhex(v.decode())
    else:
        v = re.sub(rb"\\([()\\])", rb"\1", v)
    if v.startswith(b"\xfe\xff"):
        return v[2:].decode("utf-16-be", "replace")
    s = v.decode("latin-1")
    d = re.match(r"D:(\d{4})(\d{2})(\d{2})(\d{2})?(\d{2})?", s)  # fechas PDF: D:20260730123000
    return f"{d[3]}/{d[2]}/{d[1]}" + (f" {d[4]}:{d[5]}" if d[4] and d[5] else "") if d else s


def file_meta(path):
    """Datos del modal ⓘ Información: tamaño, fechas, atributos, codificación y saltos de línea si es texto,
    y las propiedades del documento (autor, título, revisión) en Word, Excel, PowerPoint, PDF e imágenes.
    st_file_attributes y st_birthtime solo existen en Windows y macOS: en Linux salen «normal» y la fecha de cambio."""
    p = Path(path)
    st, ext = p.stat(), p.suffix.lower()
    attrs = getattr(st, "st_file_attributes", 0)
    info = {"nombre": p.name, "ruta": str(p), "tam": st.st_size, "extension": ext,
            "creado": getattr(st, "st_birthtime", st.st_ctime), "modificado": st.st_mtime, "accedido": st.st_atime,
            "atributos": [n for bit, n in ((1, "solo lectura"), (2, "oculto"), (4, "sistema")) if attrs & bit] or ["normal"]}
    text, enc, trunc = read_text(p)
    if text is not None:
        info.update(codificacion=enc, eol="CRLF" if "\r\n" in text else "LF", lineas=text.count("\n") + 1,
                    palabras=len(text.split()), truncado=trunc)
    doc = {}
    try:
        if ext in (".docx", ".xlsx", ".pptx"):
            with zipfile.ZipFile(p) as z:
                core = ET.fromstring(z.read("docProps/core.xml"))
            for el in core:
                tag = el.tag.split("}")[1]
                if el.text and tag in ("creator", "lastModifiedBy", "title", "subject", "created", "modified", "revision"):
                    doc[tag] = el.text
        elif ext == ".pdf":
            raw = p.read_bytes() if st.st_size < 60_000_000 else b""
            doc = {k: _pdf_str(raw, k.encode()) for k in ("Title", "Author", "Creator", "Producer", "CreationDate", "ModDate")}
            doc = {k: v for k, v in doc.items() if v}
            doc["Páginas"] = len(re.findall(rb"/Type\s*/Page(?![sA-Za-z])", raw)) or None
        elif ext in (".png", ".gif", ".jpg", ".jpeg", ".bmp", ".webp"):
            with open(p, "rb") as f:
                size = image_size(f.read(512_000))
            if size:
                doc["Dimensiones"] = f"{size[0]} × {size[1]} px"
    except (OSError, KeyError, zipfile.BadZipFile, ET.ParseError, ValueError):
        pass
    info["documento"] = {k: v for k, v in doc.items() if v}
    repo = git_root(p.parent)
    if repo:
        rel = str(p.relative_to(repo)).replace("\\", "/")
        last = git_run(repo, "log", "-1", "--format=%h\x1f%an\x1f%ad\x1f%s", "--date=format:%d/%m/%Y %H:%M", "--", rel)
        first = git_run(repo, "log", "--diff-filter=A", "--format=%an\x1f%ad", "--date=format:%d/%m/%Y", "--", rel)
        info["git"] = {"estado": git_state(p), "texto": GIT_TEXT[git_state(p)], "repositorio": str(repo),
                       "rama": git_run(repo, "rev-parse", "--abbrev-ref", "HEAD"),
                       "ultimo": dict(zip(("hash", "autor", "fecha", "mensaje"), last.split("\x1f"))) if last else None,
                       "commits": git_run(repo, "rev-list", "--count", "HEAD", "--", rel) or "0",
                       "creado_por": dict(zip(("autor", "fecha"), first.splitlines()[-1].split("\x1f"))) if first else None}
    else:
        info["git"] = {"estado": "sin_git", "texto": GIT_TEXT["sin_git"]}
    c = idx_conn()
    try:
        row = c.execute("select estado, paginas, indexed from files where path=?", (str(p),)).fetchone()
    finally:
        c.close()
    info["indice"] = dict(zip(("estado", "paginas", "fecha"), row)) if row else {"estado": "pendiente"}
    return info


# ---------- apagado automático al cerrar la ventana ----------

last_ping = time.time()
bye_at = None


def watchdog(server):
    """Apaga el servidor cuando se cierra la ventana (aviso «adiós» y 5 s sin pings, por si era una recarga)
    o si lleva 5 minutos sin pings (la ventana se cerró sin avisar)."""
    while True:
        time.sleep(2)
        now = time.time()
        closed = bye_at and last_ping < bye_at and now - bye_at > 5  # 5 s de margen por si fue una recarga
        if closed or now - last_ping > 300:
            server.shutdown()
            return


# ---------- HTTP ----------

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        """Sin registro de cada petición en la consola: con pythonw no hay consola y solo sería ruido."""
        pass

    def send_json(self, code, data):
        """Respuesta JSON con su código HTTP (los errores llevan {"error": mensaje} para que la ventana lo muestre)."""
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def guard(self, need_header=True):
        """Bloquea webs externas: Host local y cabecera propia (no se puede enviar sin CORS)."""
        host_ok = self.headers.get("Host", "").split(":")[0] in ("127.0.0.1", "localhost")
        if not host_ok or (need_header and self.headers.get("X-DeskLens") != "1"):
            self.send_json(403, {"error": "prohibido"})
            return False
        return True

    def denied(self, ruta):
        """403 si la ruta no está dentro de lo añadido a DeskLens. True si ya respondió."""
        if allowed(ruta):
            return False
        self.send_json(403, {"error": "ruta no añadida a DeskLens"})
        return True

    def stale(self, ruta, mtime, msg):
        """409 si el archivo cambió en disco desde que la ventana lo leyó (mtime). True si ya respondió."""
        if not mtime or mtime == str(Path(ruta).stat().st_mtime_ns):
            return False
        self.send_json(409, {"error": msg})
        return True

    def do_GET(self):
        """Peticiones GET: la página (index.html), /raw/ (archivos de los proyectos, para visores e iframes) y /api/…
        Todo exige Host local; la API además la cabecera X-DeskLens (una web externa no puede enviarla sin CORS).
        Solo se sirven rutas dentro de proyectos o sueltos añadidos (allowed)."""
        url = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(url.query, keep_blank_values=True).items()}
        try:
            if url.path in ("/", "/index.html"):
                if not self.guard(need_header=False):
                    return
                return self.send_file(ROOT / "index.html", sandbox=False)
            if url.path.startswith("/raw/"):
                if not self.guard(need_header=False):
                    return
                p = Path(unquote(url.path[5:])).resolve()
                if not allowed(p) or not p.is_file():
                    return self.send_json(404, {"error": "no permitido o no existe"})
                return self.send_file(p, sandbox=p.suffix.lower() != ".pdf")
            if url.path == "/api/git/blob":  # imagen de una versión (para <img>, que no envía la cabecera X-DeskLens)
                if not self.guard(need_header=False) or self.denied(q.get("ruta", "")):
                    return
                try:
                    data = git_blob(q.get("ruta", ""), q.get("hash", ""), q.get("rel", ""))
                except (ValueError, subprocess.TimeoutExpired) as e:
                    return self.send_json(404, {"error": str(e)})
                self.send_response(200)
                self.send_header("Content-Type", mimetypes.guess_type(q.get("rel", ""))[0] or "application/octet-stream")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Content-Security-Policy", "sandbox")  # un SVG del repositorio no ejecuta nada
                self.end_headers()
                return self.wfile.write(data)
            if url.path in ("/api/hist/dato", "/api/hist/docx"):  # sin cabecera propia: también para <img src>
                if not self.guard(need_header=False):
                    return
                ruta = q.get("ruta", "")
                if self.denied(ruta):
                    return
                try:
                    data = hist_docx(ruta, q.get("id", "")) if url.path == "/api/hist/docx" else hist_data(ruta, q.get("id", ""), q.get("parte", "dat"))
                except (ValueError, OSError, KeyError, zipfile.BadZipFile, ET.ParseError) as e:
                    return self.send_json(404, {"error": str(e)})
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "max-age=86400")  # un paso nunca cambia
                self.end_headers()
                return self.wfile.write(data)
            if not self.guard():
                return
            if url.path == "/api/estado":
                return self.send_json(200, estado())
            if url.path == "/api/git/resumen":
                return self.send_json(200, git_summary())
            if url.path == "/api/explorar":  # sin parámetro: la última ubicación usada
                return self.send_json(200, explore(q.get("ruta", load_config().get("ultima", ""))))
            if url.path == "/api/ia":
                return self.send_json(200, ia_status(refresh=q.get("refrescar") == "1"))
            if url.path == "/api/ajustes":
                return self.send_json(200, {"valores": ajustes(), "lista": [
                    {"clave": k, "grupo": g, "etiqueta": e, "defecto": d, "min": lo, "max": hi} for k, g, e, d, lo, hi in SETTINGS]})
            if url.path == "/api/recup":
                return self.send_json(200, recovery_list())
            if url.path == "/api/buscar":
                raices = [r for r in q["raices"].split("|") if r] if "raices" in q else None  # | no cabe en una ruta
                return self.send_json(200, search(q.get("q", ""), nombre=q.get("nombre") != "0",
                                                  contenido=q.get("contenido") != "0", exacto=q.get("exacto") == "1",
                                                  raices=raices))
            if url.path == "/api/indice":
                return self.send_json(200, idx_status())
            if url.path == "/api/indice/pdf":
                return self.send_json(200, idx_pdf_next())
            if url.path == "/api/conv":
                return self.send_json(200, conv_public(conv_load(q["id"])) if q.get("id") else conv_list())
            if url.path == "/api/salida":
                r = runs.get(q.get("id", ""))
                return self.send_json(200, r.output(int(q.get("desde", 0)))) if r else self.send_json(404, {"error": "no existe"})
            ruta = q.get("ruta", "")
            if url.path == "/api/web/permite":  # no es una ruta de archivo: va antes de la comprobación de permisos
                return self.send_json(200, web_check(q.get("url", "")))
            if url.path == "/api/pruebas":
                if not is_project(ruta):
                    return self.send_json(403, {"error": "no es un proyecto añadido"})
                saved = load_config().get("pruebas", {}).get(str(Path(ruta).resolve()))
                return self.send_json(200, {"comando": saved or detect_tests(ruta), "guardado": bool(saved)})
            if url.path in ("/api/plantilla", "/api/archivar"):
                if not is_project(ruta):
                    return self.send_json(403, {"error": "no es un proyecto añadido"})
                if url.path == "/api/plantilla":
                    return self.send_json(200, template_info(ruta))
                text, _, keep, by_year = plan_archive(ruta)
                return self.send_json(200, {"lineas": text.count("\n"), "quedan": len(keep),
                                            "mover": {y: len(m) for y, m in by_year.items()}})
            if self.denied(ruta):
                return
            if url.path == "/api/dir":
                return self.send_json(200, list_dir(ruta))
            if url.path == "/api/abrir":
                return self.send_json(200, file_info(Path(ruta)))
            if url.path == "/api/reglas":
                return self.send_json(200, rules_for(ruta))
            if url.path == "/api/hist":
                return self.send_json(200, hist_public(ruta))
            if url.path in ("/api/hist/parrafos", "/api/hist/cambio"):
                try:
                    return self.send_json(200, docx_paragraphs(io.BytesIO(hist_docx(ruta, q.get("id", ""))))
                                          if url.path == "/api/hist/parrafos" else hist_diff(ruta, q.get("id", "")))
                except (ValueError, OSError, KeyError, zipfile.BadZipFile, ET.ParseError) as e:
                    return self.send_json(400, {"error": str(e)})
            if url.path == "/api/docx/parrafos":
                try:
                    return self.send_json(200, {"parrafos": docx_paragraphs(ruta), "mtime": str(Path(ruta).stat().st_mtime_ns)})
                except (OSError, KeyError, zipfile.BadZipFile, ET.ParseError) as e:
                    return self.send_json(400, {"error": str(e)})
            if url.path == "/api/info":
                return self.send_json(200, file_meta(ruta))
            if url.path == "/api/mtime":  # barato: la ventana pregunta cada pocos segundos si el archivo abierto cambió
                p = Path(ruta)
                return self.send_json(200, {"mtime": str(p.stat().st_mtime_ns)} if p.is_file() else {"mtime": None})
            if url.path == "/api/git/log":
                return self.send_json(200, git_log(ruta))
            if url.path == "/api/git/estado":
                try:
                    return self.send_json(200, git_overview(ruta))
                except (ValueError, subprocess.TimeoutExpired) as e:
                    return self.send_json(400, {"error": str(e)})
            if url.path == "/api/git/commit":
                try:
                    return self.send_json(200, git_commit_info(ruta, q.get("hash", "")))
                except (ValueError, subprocess.TimeoutExpired) as e:
                    return self.send_json(400, {"error": str(e)})
            if url.path == "/api/git/ignorados":
                try:
                    return self.send_json(200, git_ignored(ruta))
                except (ValueError, subprocess.TimeoutExpired) as e:
                    return self.send_json(400, {"error": str(e)})
            if url.path in ("/api/carpeta/tam", "/api/carpeta/lista"):  # ruta ya comprobada: dentro de lo añadido
                try:
                    return self.send_json(200, folder_size(ruta) if url.path == "/api/carpeta/tam" else {"items": folder_items(ruta)})
                except OSError as e:
                    return self.send_json(400, {"error": str(e)})
            if url.path == "/api/git/grafo":
                try:
                    return self.send_json(200, git_graph(ruta, q.get("todas") == "1"))
                except (ValueError, subprocess.TimeoutExpired) as e:
                    return self.send_json(400, {"error": str(e)})
            if url.path == "/api/git/archivos":
                try:
                    return self.send_json(200, git_files(ruta, q.get("hash", "")))
                except (ValueError, OSError, subprocess.TimeoutExpired) as e:
                    return self.send_json(400, {"error": str(e)})
            if url.path == "/api/git/version":
                try:
                    return self.send_json(200, {"texto": git_version(ruta, q.get("hash", ""), q.get("rel", ""))})
                except (ValueError, OSError, subprocess.TimeoutExpired) as e:
                    return self.send_json(400, {"error": str(e)})
            if url.path == "/api/extraer":
                if blocked_for_ai(ruta):
                    return self.send_json(403, {"error": "🔒 Archivo sensible: el envío a la IA está desactivado en ⚙ Ajustes."})
                try:
                    r = extract_text(ruta)
                except FileNotFoundError:
                    return self.send_json(404, {"error": "El archivo ya no existe"})
                except (ValueError, KeyError, IndexError, OSError, zipfile.BadZipFile, ET.ParseError) as e:
                    return self.send_json(400, {"error": str(e)})
                return self.send_json(200, {"nombre": Path(ruta).name, **r, "tokens": estimate_tokens(r["texto"])})
            self.send_json(404, {"error": "no existe"})
        except (ConnectionError, TimeoutError):
            pass
        except (OSError, ValueError, KeyError, sqlite3.Error) as e:  # sin esto la petición se cortaba sin respuesta
            self.send_json(500, {"error": str(e)})

    def do_POST(self):
        """Peticiones POST (todas en post()): un error inesperado vuelve a la ventana como JSON en vez de cortar la conexión."""
        try:
            self.post()
        except (ConnectionError, TimeoutError):
            pass
        except PermissionError as e:  # otro programa (Word…) tiene el archivo abierto
            self.send_json(423, {"error": str(e)})
        except (OSError, ValueError, KeyError, sqlite3.Error) as e:
            self.send_json(500, {"error": str(e)})

    def post(self):
        """Todas las acciones que cambian algo: guardar, crear, ejecutar, IA, historial, Word, imágenes, PDF, ajustes…
        ping/adiós llegan con sendBeacon, que no puede llevar cabeceras; el resto exige la cabecera X-DeskLens.
        Cada acción vuelve a comprobar que la ruta está dentro de lo añadido a DeskLens."""
        global last_ping, bye_at
        url = urlparse(self.path).path
        if url in ("/api/ping", "/api/adios"):  # sendBeacon no puede enviar cabeceras
            if not self.guard(need_header=False):
                return
            if url == "/api/ping":
                last_ping = time.time()
            else:
                bye_at = time.time()
            return self.send_json(200, {})
        if not self.guard():
            return
        data = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        if url == "/api/agregar" and data.get("tipo") in ("proyectos", "sueltos"):
            check = Path.is_dir if data["tipo"] == "proyectos" else Path.is_file
            rutas = [r for r in data.get("rutas", []) if check(Path(r))]
            add_paths(data["tipo"], rutas)
            if data.get("ultima") is not None:
                cfg = load_config()
                cfg["ultima"] = data["ultima"]
                save_config(cfg)
            return self.send_json(200, estado())
        if url == "/api/git/accion":
            if self.denied(data.get("ruta", "")):
                return
            try:
                return self.send_json(200, git_action(data["ruta"], str(data.get("accion", "")),
                                                      [str(a) for a in data.get("archivos") or []], str(data.get("mensaje", "")),
                                                      str(data.get("rama", "")), bool(data.get("todo")), str(data.get("modo", ""))))
            except GitLocalChanges as e:  # la ventana ofrece llevar los cambios o guardarlos a un lado
                return self.send_json(409, {"error": str(e), "codigo": "cambios_locales", "archivos": e.archivos, "rama": e.destino})
            except (ValueError, subprocess.TimeoutExpired) as e:
                return self.send_json(400, {"error": str(e)})
        if url == "/api/git/blame":
            if self.denied(data.get("ruta", "")):
                return
            try:
                return self.send_json(200, git_blame(data["ruta"], data.get("hash", ""), data.get("rel", ""), data.get("texto")))
            except (ValueError, OSError, subprocess.TimeoutExpired) as e:
                return self.send_json(400, {"error": str(e)})
        if url == "/api/guardar":
            if self.denied(data.get("ruta", "")):
                return
            return self.send_json(*save_text(data["ruta"], data.get("texto", ""), data.get("codificacion"),
                                             data.get("eol"), data.get("mtime"), bool(data.get("forzar"))))
        if url in ("/api/plantilla", "/api/archivar"):
            if not is_project(data.get("ruta", "")):
                return self.send_json(403, {"error": "no es un proyecto añadido"})
            if url == "/api/plantilla":
                creados = create_from_templates(data["ruta"], data.get("archivos", []),
                                                data.get("descripcion", ""), data.get("tecnologia", ""))
                return self.send_json(200, {"creados": creados, **estado()})
            return self.send_json(200, {"movidas": archive_log(data["ruta"]), **estado()})
        if url == "/api/ejecutar":
            if self.denied(data.get("ruta", "")):
                return
            p = Path(data["ruta"]).resolve()
            args, enc = command_for(p)
            if args is None:
                return self.send_json(400, {"error": enc or "Este tipo de archivo no se ejecuta"})
            extra = [str(a) for a in data.get("args", []) if isinstance(a, str)]  # p. ej. citas para verificar_citas.py
            return self.send_json(200, {"id": start_run(args + extra, str(p.parent), enc, p.name)})
        if url == "/api/pruebas":
            if not is_project(data.get("ruta", "")) or not data.get("comando", "").strip():
                return self.send_json(400, {"error": "proyecto o comando no válido"})
            p = str(Path(data["ruta"]).resolve())
            cfg = load_config()
            cfg.setdefault("pruebas", {})[p] = data["comando"].strip()
            save_config(cfg)
            cmd = data["comando"].strip()
            rid = start_run(f"cmd /c {cmd}" if WINDOWS else ["bash", "-lc", cmd], p, "utf-8", "Pruebas · " + Path(p).name)
            return self.send_json(200, {"id": rid})
        if url in ("/api/entrada", "/api/detener", "/api/consola"):
            r = runs.get(str(data.get("id")))
            if not r:
                return self.send_json(404, {"error": "no existe"})
            if url == "/api/entrada":
                r.send(data.get("texto", ""))
            elif url == "/api/detener":
                r.kill()
            else:
                try:
                    open_console(str(data["id"]))
                except (RuntimeError, OSError) as e:
                    return self.send_json(500, {"error": str(e)})
            return self.send_json(200, {})
        if url == "/api/ajustes":
            return self.send_json(200, {"valores": set_ajustes(data)})
        if url == "/api/recup/guardar":
            if data.get("ruta") and self.denied(data["ruta"]):
                return
            recovery_save(data)
            return self.send_json(200, {})
        if url == "/api/recup/borrar":
            recovery_delete(data.get("clave"))
            return self.send_json(200, {})
        if url == "/api/docx":  # cambios de formato/texto propuestos por la IA en un Word
            if not allowed(data.get("ruta", "")) or not data.get("ruta", "").lower().endswith(".docx"):
                return self.send_json(403, {"error": "Solo se pueden cambiar .docx de los proyectos añadidos"})
            if self.stale(data["ruta"], data.get("mtime"), "El Word cambió en disco mientras lo editabas (¿la IA o Word?): "
                                                     "descarta tus cambios y vuelve a editar"):
                return
            try:
                return self.send_json(200, docx_apply(data["ruta"], data.get("ops") or []))
            except (ValueError, KeyError, zipfile.BadZipFile, ET.ParseError) as e:
                return self.send_json(400, {"error": str(e)})
        if url.startswith("/api/hist/"):  # ↶ ↷: pasos del historial de un archivo en edición
            ruta = data.get("ruta", "")
            if self.denied(ruta):
                return
            try:
                if url == "/api/hist/paso":  # texto: llega tal cual; lo demás en base64
                    d = data.get("datos")
                    d = d.encode("utf-8") if hist_kind(ruta) == "texto" else base64.b64decode(d or "")
                    return self.send_json(200, hist_step(ruta, data.get("padre"), str(data.get("desc", ""))[:200], d, data.get("extra")))
                if url == "/api/hist/ir":
                    hist_go(ruta, str(data.get("id", "")))
                    return self.send_json(200, {})
                if url == "/api/hist/guardado":
                    return self.send_json(200, hist_saved(ruta, str(data.get("id", ""))))
                if url == "/api/hist/escribir":  # Word: el estado de ese paso se escribe en el archivo
                    if self.stale(ruta, data.get("mtime"), "El Word cambió en disco mientras lo editabas (¿la IA o Word?): "
                                                             "lo que ves sigue en el historial; vuelve a editar y recupéralo desde ↶"):
                        return
                    nid = str(data.get("id", ""))
                    r = write_with_backup(Path(ruta), hist_docx(ruta, nid), "El documento está abierto en Word: ciérralo allí y vuelve a guardar")
                    return self.send_json(200, {**r, **hist_saved(ruta, nid)})
            except PermissionError as e:
                return self.send_json(423, {"error": str(e)})
            except (ValueError, OSError, KeyError, zipfile.BadZipFile, ET.ParseError) as e:
                return self.send_json(400, {"error": str(e)})
        if url == "/api/binario":  # imagen o PDF editados en DeskLens (llegan en base64)
            if self.denied(data.get("ruta", "")):
                return
            if self.stale(data["ruta"], data.get("mtime"), "El archivo cambió en disco mientras lo editabas: descarta y vuelve a editar"):
                return
            try:
                return self.send_json(200, binary_save(data["ruta"], base64.b64decode(data.get("datos", ""))))
            except (ValueError, KeyError) as e:
                return self.send_json(400, {"error": str(e)})
        if url == "/api/docx/deshacer":  # sirve para cualquier archivo con copia en historial\deshacer (Word, imágenes)
            if self.denied(data.get("ruta", "")):
                return
            try:
                return self.send_json(200, docx_undo(data["ruta"], str(data.get("id", ""))))
            except ValueError as e:
                return self.send_json(400, {"error": str(e)})
        if url == "/api/carpeta":
            try:
                return self.send_json(200, {"ruta": create_folder(data.get("carpeta", ""), data.get("nombre", "").strip())})
            except FileExistsError:
                return self.send_json(409, {"error": "Ya existe una carpeta con ese nombre"})
            except PermissionError as e:
                return self.send_json(403, {"error": str(e)})
        if url == "/api/indice/pdf":  # texto de un PDF extraído por la ventana (pdf.js)
            idx_pdf_save(data.get("ruta", ""), data.get("mtime"), data.get("paginas", []), data.get("error"))
            return self.send_json(200, {})
        if url == "/api/extraer":  # archivo soltado desde Windows: llega su contenido en base64
            nombre = Path(str(data.get("nombre", ""))).name
            if blocked_for_ai(nombre):
                return self.send_json(403, {"error": "🔒 Archivo sensible: el envío a la IA está desactivado en ⚙ Ajustes."})
            try:
                r = extract_text(nombre, base64.b64decode(data.get("datos", "")))
            except (ValueError, KeyError, IndexError, zipfile.BadZipFile, ET.ParseError) as e:
                return self.send_json(400, {"error": str(e)})
            return self.send_json(200, {"nombre": nombre, **r, "tokens": estimate_tokens(r["texto"])})
        if url == "/api/papelera":
            if self.denied(data.get("ruta", "")):
                return
            try:
                to_trash(data["ruta"])
            except PermissionError as e:
                return self.send_json(403, {"error": str(e)})
            return self.send_json(200, estado())
        if url == "/api/soltados":  # archivos soltados desde el Explorador: su ruta real (y quedan como sueltos)
            return self.send_json(200, locate_dropped([a for a in data.get("archivos", []) if isinstance(a, dict)]))
        if url == "/api/contexto":
            return self.send_json(200, find_mentioned(data.get("mensaje", ""), data.get("ruta", "")))
        if url == "/api/conv/enviar":
            if any(blocked_for_ai(a.get("nombre", "")) for a in data.get("adjuntos", [])):  # defensa también en el servidor
                return self.send_json(403, {"error": "🔒 Archivo sensible: el envío a la IA está desactivado en ⚙ Ajustes."})
            try:
                return self.send_json(200, conv_send(data))
            except (RuntimeError, subprocess.TimeoutExpired) as e:
                return self.send_json(502, {"error": str(e)})
        if url == "/api/conv/borrar":
            conv_path(str(data.get("id", ""))).unlink(missing_ok=True)
            return self.send_json(200, {})
        if url == "/api/conv/limpiar":  # 🧹: mismo chat (y vínculo), vacío; Claude empieza sesión nueva
            conv = conv_load(str(data.get("id", "")))
            conv.update(mensajes=[], adjuntos=[], session=None, titulo="Conversación", fecha=time.strftime("%Y-%m-%d %H:%M"))
            conv_save(conv)
            return self.send_json(200, conv_public(conv))
        if url == "/api/conv/revincular":  # "nuevo 1" guardado con nombre: su chat pasa al archivo
            de, a = str(data.get("de", "")), str(data.get("a", ""))
            for item in conv_list():
                if item["vinculo"] == de:
                    conv = conv_load(item["id"])
                    conv["vinculo"] = a
                    conv_save(conv)
            return self.send_json(200, {})
        if url == "/api/ia/probar":
            try:
                r = ask_ai(data.get("ia"), "Responde solo: OK")
            except (RuntimeError, subprocess.TimeoutExpired) as e:
                return self.send_json(502, {"error": str(e)})
            cfg = load_config()
            ia = cfg.setdefault("ia", {})
            if r["tokens"]:
                ia.setdefault("carga", {})[data["ia"]] = {"tokens": r["tokens"]["entrada"], "v": CARGA_V}
                save_config(cfg)
            return self.send_json(200, r)
        if url == "/api/ia/pref":
            cfg = load_config()
            ia = cfg.setdefault("ia", {})
            if data.get("predeterminada") in AIS:
                ia["predeterminada"] = data["predeterminada"]
            save_config(cfg)
            if str(data.get("limite", "")).isdigit():
                set_ajustes({"ia_limite_tokens": int(data["limite"])})  # mismo valor que en ⚙ Ajustes
            return self.send_json(200, ia_prefs())
        if url == "/api/ia/login" and data.get("ia") in AIS:
            try:
                open_login(data["ia"])
            except (RuntimeError, OSError) as e:
                return self.send_json(500, {"error": str(e) + f'. Ábrela tú y escribe: {AIS[data["ia"]]["login"]}'})
            return self.send_json(200, {})
        if url == "/api/crear":
            try:
                return self.send_json(200, {"ruta": create_file(data.get("carpeta", ""), data.get("nombre", "").strip(),
                                                                 data.get("texto", ""), data.get("html"))})
            except FileExistsError:
                return self.send_json(409, {"error": "Ya existe un archivo con ese nombre"})
            except PermissionError as e:
                return self.send_json(403, {"error": str(e)})
            except (ValueError, RuntimeError, subprocess.TimeoutExpired) as e:  # formato no viable o Edge falló
                return self.send_json(400, {"error": str(e)})
        if url == "/api/quitar":
            cfg = load_config()
            for k in ("proyectos", "sueltos"):
                cfg[k] = [r for r in cfg[k] if r != data.get("ruta")]
            save_config(cfg)
            return self.send_json(200, estado())
        if url == "/api/ventana":
            cfg = load_config()
            cfg["ventana"] = {k: int(data[k]) for k in ("x", "y", "w", "h")}
            save_config(cfg)
            return self.send_json(200, {})
        if url == "/api/mostrar" and allowed(data.get("ruta", "")):
            p = Path(data["ruta"]).resolve()
            try:
                subprocess.Popen(["explorer", "/select,", str(p)] if WINDOWS else ["open", "-R", str(p)] if MAC
                                 else ["xdg-open", str(p if p.is_dir() else p.parent)])
            except OSError as e:
                return self.send_json(500, {"error": f"No se pudo abrir la carpeta: {e}"})
            return self.send_json(200, {})
        self.send_json(404, {"error": "no existe"})

    def send_file(self, p, sandbox):
        """Envía un archivo con soporte de Range (para poder adelantar audio y video)."""
        size = p.stat().st_size
        start, end = 0, size - 1
        rng = self.headers.get("Range", "")
        if rng.startswith("bytes=") and size:
            a, _, b = rng[6:].split(",")[0].partition("-")
            start = int(a) if a else max(0, size - int(b))
            end = min(int(b), size - 1) if a and b else size - 1
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        else:
            self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(p.name)[0] or "application/octet-stream")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(max(0, end - start + 1)))
        self.send_header("Cache-Control", "no-store")
        if sandbox:  # un HTML del usuario abierto aquí no puede usar la API de DeskLens
            self.send_header("Content-Security-Policy", "sandbox allow-scripts allow-forms allow-modals allow-popups")
        self.end_headers()
        with p.open("rb") as f:
            f.seek(start)
            left = end - start + 1
            while left > 0:
                chunk = f.read(min(65536, left))
                if not chunk:
                    break
                self.wfile.write(chunk)
                left -= len(chunk)


def window_flags(cfg):
    """Posición y tamaño de la última vez (los guarda la ventana mientras se usa)."""
    v = cfg.get("ventana") or {}
    try:
        x, y, w, h = (int(v[k]) for k in ("x", "y", "w", "h"))
    except (KeyError, TypeError, ValueError):
        return []
    if w < 400 or h < 300:  # tamaño absurdo: mejor el de Edge por defecto
        return []
    return [f"--window-position={x},{y}", f"--window-size={w},{h}"]


def open_window(url):
    """Ventana propia en modo aplicación con el navegador de ⚙ Ajustes (o el primero instalado); con «predeterminado»
    o sin ninguno Chromium, una pestaña del navegador de siempre."""
    choice = ajuste("navegador")
    try:
        exe = None if choice == "predeterminado" else edge_path(choice)
        if exe:  # start_new_session solo actúa en macOS y Linux: la ventana no muere con el servidor
            return subprocess.Popen([exe, f"--app={url}", *window_flags(load_config())], start_new_session=True,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=NO_WINDOW)
    except OSError:
        pass
    webbrowser.open(url)


def main():
    """Arranque: los archivos pasados como argumento (arrastrados sobre el icono) se añaden como sueltos; si DeskLens
    ya está abierto en ese puerto, solo se abre otra ventana; si no, servidor, indexador, limpieza y ventana."""
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    files = [str(Path(a).resolve()) for a in args if Path(a).is_file()]
    if files:
        add_paths("sueltos", files)
    port = ajuste("puerto")
    url = f"http://127.0.0.1:{port}/" + ("?abrir=" + quote("|".join(files)) if files else "")
    try:
        server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    except OSError:
        server = None  # ya hay un DeskLens abierto: solo se abre otra ventana
    if "--sin-ventana" not in sys.argv:
        open_window(url)
    if server:
        threading.Thread(target=watchdog, args=(server,), daemon=True).start()
        threading.Thread(target=indexer, daemon=True).start()  # también limpia el historial de cambios
        threading.Thread(target=git_autofetch, daemon=True).start()  # ↓ al día sin pulsar Fetch
        server.serve_forever()
        for r in runs.values():  # al cerrar la ventana no quedan programas corriendo
            r.kill()


if __name__ == "__main__":
    main()
