"""Prueba de Atril: python test_atril.py  (no abre ventanas ni toca config.json real)."""
import importlib.machinery
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

# «import atril» solo encuentra atril.pyw en Windows: se carga el archivo directamente (macOS y Linux igual)
_loader = importlib.machinery.SourceFileLoader("atril", str(Path(__file__).with_name("atril.pyw")))
atril = importlib.util.module_from_spec(importlib.util.spec_from_loader("atril", _loader))
sys.modules["atril"] = atril
_loader.exec_module(atril)


def get(port, path, header=True, rng=None):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}")
    if header:
        req.add_header("X-Atril", "1")
    if rng:
        req.add_header("Range", rng)
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    atril.CONFIG = tmp / "config.json"
    # nada de la prueba va al historial\ real de Atril (copias para deshacer, versiones, archivos de la IA)
    atril.UNDO_DIR, atril.HIST_DIR, atril.IA_DIR = tmp / "deshacer", tmp / "versiones", tmp / "ia"
    proj, fuera = tmp / "proyecto", tmp / "fuera"
    proj.mkdir(), fuera.mkdir()
    (proj / "utf8.md").write_bytes("# Hola ñ\n".encode())
    (proj / "bom.ps1").write_bytes(b"\xef\xbb\xbfWrite-Host 'a'")
    (proj / "ansi.bat").write_bytes("echo café\r\n".encode("cp1252"))
    (proj / "utf16.txt").write_bytes("hola".encode("utf-16"))
    (proj / "img.png").write_bytes(b"\x89PNG\r\n\x1a\n\0\0\0datos")
    (fuera / "secreto.txt").write_text("no")
    suelto = fuera / "suelto.txt"
    suelto.write_text("ok")
    atril.add_paths("proyectos", [proj])
    atril.add_paths("sueltos", [suelto])

    # permisos: proyecto y suelto sí; lo demás no, ni con ../
    assert atril.allowed(proj / "utf8.md") and atril.allowed(suelto)
    assert not atril.allowed(fuera / "secreto.txt")
    assert not atril.allowed(proj / ".." / "fuera" / "secreto.txt")

    # codificaciones y binarios
    assert atril.read_text(proj / "utf8.md")[:2] == ("# Hola ñ\n", "utf-8")
    assert atril.read_text(proj / "bom.ps1")[1] == "utf-8-bom"
    assert atril.read_text(proj / "ansi.bat")[:2] == ("echo café\r\n", "cp1252")
    assert atril.read_text(proj / "utf16.txt")[:2] == ("hola", "utf-16")
    assert atril.read_text(proj / "img.png")[0] is None

    # guardar: conserva codificación y CRLF, crea .bak una vez, detecta conflictos
    bat = proj / "ansi.bat"
    mt = str(bat.stat().st_mtime_ns)
    code, d = atril.save_text(bat, "echo café\necho ñ\n", "cp1252", "CRLF", mt)
    assert code == 200 and bat.read_bytes() == "echo café\r\necho ñ\r\n".encode("cp1252")
    assert Path(d["bak"]).read_bytes() == "echo café\r\n".encode("cp1252")
    code, d2 = atril.save_text(bat, "echo 2\n", "cp1252", "CRLF", d["mtime"])
    assert code == 200 and d2["bak"] is None  # un solo .bak por sesión
    assert atril.save_text(bat, "x", "cp1252", "CRLF", mt)[0] == 409  # cambió desde que se abrió
    assert atril.save_text(bat, "x", "cp1252", "CRLF", mt, force=True)[0] == 200
    code, d = atril.save_text(bat, "echo 😀", "cp1252", "CRLF", str(bat.stat().st_mtime_ns))
    assert code == 422 and "línea 1" in d["error"] and bat.read_bytes() == b"x"  # no rompe el .bat
    ps1 = proj / "bom.ps1"
    atril.save_text(ps1, "Write-Host 'ñ'", "utf-8-bom", "LF", str(ps1.stat().st_mtime_ns))
    assert ps1.read_bytes() == b"\xef\xbb\xbf" + "Write-Host 'ñ'".encode()
    assert atril.save_text(proj / "img.png", "x", "utf-8", "LF", "0")[0] == 400  # binario: solo lectura
    (proj / "conGit" / ".git").mkdir(parents=True)
    g = proj / "conGit" / "a.py"
    g.write_text("1")
    assert atril.save_text(g, "2", "utf-8", "LF", str(g.stat().st_mtime_ns))[1]["bak"] is None  # git es el respaldo

    # plantillas: crea solo lo que falta y nunca sobrescribe
    nuevo = tmp / "nuevo"
    nuevo.mkdir()
    (nuevo / "CLAUDE.md").write_text("mío")
    info = atril.template_info(nuevo)
    assert [a["existe"] for a in info["archivos"]] == [False, True, False, False, False]
    creados = atril.create_from_templates(nuevo, atril.TEMPLATES, "Bot de pedidos.", "Node")
    assert creados == ["AGENTS.md", "GEMINI.md", "reglas.md", "bitacora.md"]
    assert (nuevo / "CLAUDE.md").read_text() == "mío"
    agents = (nuevo / "AGENTS.md").read_text(encoding="utf-8")
    assert "# Proyecto: nuevo" in agents and "Bot de pedidos. Tecnología: Node." in agents and "{{" not in agents
    assert "{{" not in (nuevo / "bitacora.md").read_text(encoding="utf-8")
    assert atril.status(nuevo) == []

    # archivar: quedan las 20 más recientes, el resto va a bitacora/AAAA.md sin perder nada
    entradas = [f"## 2026-{m:02d}-01 · e{m}\nTexto {m}\n\n" for m in range(12, 0, -1)]
    entradas += [f"## 2025-{m:02d}-01 · v{m}\nTexto viejo {m}\n\n" for m in range(12, 0, -1)]
    (nuevo / "bitacora.md").write_text("# Bitácora\n\n" + "".join(entradas), encoding="utf-8")
    (nuevo / "bitacora").mkdir()
    (nuevo / "bitacora" / "2025.md").write_text("# Bitácora 2025\n\n## 2025-00-01 · más vieja\nx\n", encoding="utf-8")
    assert atril.archive_log(nuevo) == {"2025": 4}
    queda = (nuevo / "bitacora.md").read_text(encoding="utf-8")
    assert queda.startswith("# Bitácora\n\n## 2026-12-01") and queda.count("\n## ") == 20
    archivo = (nuevo / "bitacora" / "2025.md").read_text(encoding="utf-8")
    assert archivo.startswith("# Bitácora 2025\n\n## 2025-04-01") and archivo.count("## 2025-") == 5
    assert archivo.rstrip().endswith("más vieja\nx")

    # consola: salida normal y de error, entrada, código de salida, tildes en .bat, detener
    def wait_run(rid, t=20):
        end = time.time() + t
        while time.time() < end:
            o = atril.runs[rid].output(0)
            if o["fin"]:
                return o
            time.sleep(0.1)
        raise AssertionError("el proceso no terminó")

    def text(o, kind):
        return "".join(t for k, t in o["trozos"] if k == kind)

    (proj / "hola.py").write_text('import sys\nprint("hola ñ")\nprint("mal", file=sys.stderr)\n'
                                  'print("leí", input())\nsys.exit(3)\n', encoding="utf-8")
    args, enc = atril.command_for(proj / "hola.py")
    rid = atril.start_run(args, str(proj), enc, "hola.py")
    atril.runs[rid].send("sí")
    o = wait_run(rid)
    assert text(o, "out") == "hola ñ\nleí sí\n" and text(o, "err") == "mal\n" and o["codigo"] == 3
    def run_file(p):
        a, e = atril.command_for(p)
        return atril.start_run(a, str(p.parent), e, p.name)

    if atril.WINDOWS:
        (proj / "acento.bat").write_bytes("@echo off\r\necho café\r\n".encode(atril.oem_encoding()))
        o = wait_run(run_file(proj / "acento.bat"))
        (proj / "largo.bat").write_text("@ping -n 30 127.0.0.1 > nul\r\n")
        rid = run_file(proj / "largo.bat")
    else:  # macOS y Linux: lo mismo con bash; un .bat dice que es solo de Windows
        assert atril.command_for(proj / "ansi.bat") == (None, "Solo se ejecuta en Windows")
        (proj / "acento.sh").write_text("echo café\n", encoding="utf-8")
        o = wait_run(run_file(proj / "acento.sh"))
        (proj / "largo.sh").write_text("sleep 30 & sleep 30\n")  # con un hijo: detener también lo para
        rid = run_file(proj / "largo.sh")
    assert text(o, "out") == "café\n" and o["codigo"] == 0
    time.sleep(0.5)
    atril.runs[rid].kill()
    assert wait_run(rid, 10)["codigo"] != 0
    assert atril.command_for(proj / "utf8.md") == (None, None) and atril.run_info(proj / "utf8.md") is None
    assert atril.run_info(proj / "hola.py")["texto"].endswith("hola.py")

    # comando de pruebas detectado por los archivos del proyecto
    lara = tmp / "lara"
    lara.mkdir()
    assert atril.detect_tests(lara) == ""
    (lara / "package.json").write_text('{"scripts": {"test": "jest"}}')
    assert atril.detect_tests(lara) == "npm test"
    (lara / "artisan").write_text("")
    assert atril.detect_tests(lara) == "php artisan test"

    # IA: archivos sensibles, prompt, lectura de la salida de cada CLI
    assert atril.is_sensitive(proj / ".env.local") and atril.is_sensitive(proj / "clave.PEM")
    assert atril.is_sensitive(proj / "wp-config.php") and atril.is_sensitive(proj / "id_rsa") and atril.is_sensitive(proj / "x.kdbx")
    assert not atril.is_sensitive(proj / "web.php")
    p = atril.conv_prompt(atril.CONV_INTRO, "- Usar usted", [{"nombre": "a.pdf", "desc": "pág. 4", "texto": "hola tío"}], [], "Más formal")
    assert p.index("<<<ARCHIVO") < p.index("REGLAS") < p.index("ADJUNTO: a.pdf (pág. 4)") < p.index("MENSAJE:\nMás formal")
    assert "REGLAS" not in atril.conv_prompt("", "", [], [], "¿qué es?")
    assert atril.parse_ai("claude", json.dumps({"result": "OK", "usage": {"input_tokens": 5, "cache_read_input_tokens": 100,
                                                                          "output_tokens": 2}})) == ("OK", {"entrada": 105, "salida": 2})
    assert atril.parse_ai("gemini", json.dumps({"response": "OK", "stats": {"models": {"g": {"tokens": {"prompt": 7, "candidates": 1}}}}})) \
        == ("OK", {"entrada": 7, "salida": 1})
    codex_out = "\n".join(json.dumps(e) for e in [{"type": "thread.started"},
                                                   {"type": "item.completed", "item": {"type": "agent_message", "text": "OK"}},
                                                   {"type": "turn.completed", "usage": {"input_tokens": 9, "output_tokens": 1}}])
    assert atril.parse_ai("codex", codex_out) == ("OK", {"entrada": 9, "salida": 1})
    assert atril.parse_ai("claude", "texto plano") == ("texto plano", None)  # formato desconocido: no se pierde la respuesta

    # conversaciones: docx a texto, prompt, sesión de Claude, adjuntos enviados una sola vez
    import zipfile
    W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
    with zipfile.ZipFile(proj / "doc.docx", "w") as z:
        z.writestr("word/document.xml", f'<w:document {W}><w:body><w:p><w:r><w:t>Hola</w:t></w:r><w:r><w:tab/><w:t>ñandú</w:t></w:r></w:p>'
                                        '<w:p><w:r><w:t xml:space="preserve">Línea 2 </w:t></w:r></w:p></w:body></w:document>')
    assert atril.docx_text(proj / "doc.docx") == "Hola\tñandú\nLínea 2"
    atril.CONV_DIR = tmp / "historial" / "conversaciones"
    calls = []
    real_ask = atril.ask_ai
    atril.ask_ai = lambda ia, prompt, resume=None, images=(): (calls.append((ia, prompt, resume)) or
                                                     {"texto": f"resp {len(calls)}", "tokens": {"entrada": 1, "salida": 1},
                                                      "session": "s1" if ia == "claude" else None})
    (proj / "reglas.md").write_bytes(b"- Usar RVR60\n")
    (proj / "verificar_citas.py").write_text("print('ok')")
    c = atril.conv_send({"ia": "claude", "mensaje": "Pregunta 1", "ruta": str(proj / "utf8.md"),
                         "adjuntos": [{"nombre": "libro.pdf", "desc": "págs. 27–30", "texto": "TEXTO DEL LIBRO"}]})
    assert "REGLAS" in calls[0][1] and "TEXTO DEL LIBRO" in calls[0][1] and calls[0][2] is None
    assert c["session"] == "s1" and c["verificador"].endswith("verificar_citas.py") and "texto" not in c["adjuntos"][0]
    c = atril.conv_send({"id": c["id"], "ia": "claude", "mensaje": "OK, la B", "adjuntos": []})
    assert calls[1][2] == "s1" and "TEXTO DEL LIBRO" not in calls[1][1] and "REGLAS" not in calls[1][1]  # ya están en la sesión
    c = atril.conv_send({"id": c["id"], "ia": "gemini", "mensaje": "Sigue", "adjuntos": []})
    assert "TEXTO DEL LIBRO" in calls[2][1] and "Usuario: OK, la B" in calls[2][1] and c["session"] is None  # sin sesión: todo
    assert [x["n"] for x in atril.conv_list()] == [6]
    atril.ask_ai = real_ask
    (proj / "reglas.md").unlink()
    atril.conv_path(c["id"]).unlink()
    assert atril.conv_list() == []
    for bad in ("../x", "abc/def", ""):
        try:
            atril.conv_path(bad)
            raise AssertionError("id inválido aceptado")
        except ValueError:
            pass

    # reglas del proyecto y archivos nuevos
    assert atril.project_of(proj / "conGit" / "a.py") == proj.resolve() and atril.project_of(fuera / "suelto.txt") is None
    assert atril.rules_for(proj / "utf8.md")["reglas"] is None
    (proj / "reglas.md").write_bytes(b"- Usar usted\n")
    assert atril.rules_for(proj / "utf8.md")["reglas"]["texto"] == "- Usar usted\n"
    assert atril.rules_for(fuera / "suelto.txt") == {"proyecto": None, "reglas": None}
    nuevo_f = atril.create_file(proj, "nuevo.md", "# Hola\n")
    assert Path(nuevo_f).read_text(encoding="utf-8") == "# Hola\n"
    try:
        atril.create_file(proj, "nuevo.md", "otro")
        raise AssertionError("debió negarse a sobrescribir")
    except FileExistsError:
        pass
    assert Path(atril.create_file(fuera, "junto.md", "x")).name == "junto.md"  # junto a un suelto: queda como suelto
    assert any(s.endswith("junto.md") for s in atril.load_config()["sueltos"])
    # cambios de formato/texto en un Word: todo o nada, conserva el resto, .bak, el visor y Word lo leen
    wd = atril.create_file(proj, "tema.docx", "", "<h1>Título del tema</h1><p>El <strong>arca</strong> y el arca otra vez.</p>")
    r = atril.docx_apply(wd, [{"buscar": "Título del tema", "color": "rojo", "tamano": 20},
                              {"buscar": "arca", "cursiva": True, "todas": True},
                              {"buscar": "otra vez", "reemplazar": "de nuevo"}])
    xml = zipfile.ZipFile(wd).read("word/document.xml").decode()
    assert r["cambios"] == 4 and r["bak"].endswith("tema.docx.bak") and 'w:val="FF0000"' in xml and 'w:val="40"' in xml
    assert atril.docx_text(wd).split("\n") == ["Título del tema", "El arca y el arca de nuevo."]
    assert xml.count("<w:i />") + xml.count("<w:i/>") == 2
    # «Deshacer»: vuelve exactamente al archivo de antes del cambio
    atril.UNDO_DIR = tmp / "deshacer"
    prev = Path(wd).read_bytes()
    r2 = atril.docx_apply(wd, [{"buscar": "Título del tema", "color": "verde"}])
    assert Path(wd).read_bytes() != prev and r2["deshacer"]
    atril.docx_undo(wd, r2["deshacer"])
    assert Path(wd).read_bytes() == prev
    for bad in ("../x", "zz"):
        try:
            atril.docx_undo(wd, bad)
            raise AssertionError("debió fallar")
        except ValueError:
            pass
    assert atril.ajuste("ia_confirmar_aplicar") is False  # predeterminado: se aplica sin preguntar
    before = Path(wd).read_bytes()
    try:
        atril.docx_apply(wd, [{"buscar": "arca", "negrita": True}, {"buscar": "no existe"}])
        raise AssertionError("debió fallar")
    except ValueError as e:
        assert "no existe" in str(e)
    assert Path(wd).read_bytes() == before  # todo o nada: nada se tocó
    assert "DOCX" in atril.abierto_hint(wd) and "DOCX" not in atril.abierto_hint(proj / "utf8.md")
    # edición a mano: cambios en el párrafo N desde el carácter indicado (no en la primera aparición del documento)
    assert atril.docx_paragraphs(wd) == ["Título del tema", "El arca y el arca de nuevo."]
    prev = Path(wd).read_bytes()
    r3 = atril.docx_apply(wd, [{"parrafo": 1, "desde": 12, "buscar": "arca", "reemplazar": "Arca santa"},
                               {"parrafo": 1, "desde": 0, "buscar": "El", "negrita": True},
                               {"parrafo": 0, "agregar": " (2)"}])
    assert atril.docx_paragraphs(wd) == ["Título del tema (2)", "El arca y el Arca santa de nuevo."]
    try:
        atril.docx_apply(wd, [{"parrafo": 9, "buscar": "x", "negrita": True}])
        raise AssertionError("debió fallar")
    except ValueError:
        pass
    atril.docx_undo(wd, r3["deshacer"])
    assert Path(wd).read_bytes() == prev
    # imagen en un Word: párrafo nuevo después del indicado, con su relación, tipo y proporción
    import base64 as b64, io, struct, zlib
    chunk = lambda t, d: struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d))
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 40, 20, 8, 2, 0, 0, 0)) + \
        chunk(b"IDAT", zlib.compress(b"\x00" + b"\xff\x00\x00" * 40 * 20)) + chunk(b"IEND", b"")
    (proj / "portada.png").write_bytes(png)
    assert atril.image_size(png) == (40, 20)
    ref = atril.extract_text(proj / "portada.png")
    assert ref["imagen"] and "40×20" in ref["texto"] and str(proj / "portada.png") in ref["texto"]
    assert atril.extract_text("x.png", png)["imagen"] and atril.extract_text("x.zip", b"PK\0\0")["ref"]
    atril.docx_apply(wd, [{"imagen": str(proj / "portada.png"), "buscar": "Título del tema", "ancho_cm": 10},
                          {"imagen": "otra.png", "datos": b64.b64encode(png).decode(), "buscar": "arca", "posicion": "antes"}])
    with zipfile.ZipFile(wd) as z:
        xml = z.read("word/document.xml").decode()
        assert z.read("word/media/atril1.png") == png and "word/media/atril2.png" in z.namelist()
        assert 'Extension="png"' in z.read("[Content_Types].xml").decode() and "rIdAtril2" in z.read("word/_rels/document.xml.rels").decode()
    assert 'cx="3600000" cy="1800000"' in xml  # 10 cm de ancho, mitad de alto
    assert xml.index("Título del tema") < xml.index("rIdAtril1") < xml.index("rIdAtril2") < xml.index(">El <")
    # soltada a mano sobre un párrafo: va a ese párrafo (por índice), aunque «buscar» esté vacío
    atril.docx_apply(wd, [{"imagen": str(proj / "portada.png"), "parrafo": 0, "buscar": "", "posicion": "antes"}])
    with zipfile.ZipFile(wd) as z:
        xml = z.read("word/document.xml").decode()
    assert xml.index("rIdAtril3") < xml.index("Título del tema")
    for bad in ({"imagen": "foto.webp", "buscar": "arca"}, {"imagen": "no.png", "buscar": "arca"}):
        try:
            atril.docx_apply(wd, [bad])
            raise AssertionError("debió fallar")
        except ValueError:
            pass
    # imagen editada en Atril: .bak la primera vez, copia para deshacer; no acepta datos que no son imagen
    png2 = png.replace(struct.pack(">II", 40, 20), struct.pack(">II", 20, 40))
    r = atril.binary_save(proj / "portada.png", png2)
    assert (proj / "portada.png").read_bytes() == png2 and Path(r["bak"]).read_bytes() == png and r["deshacer"]
    atril.docx_undo(proj / "portada.png", r["deshacer"])
    assert (proj / "portada.png").read_bytes() == png
    (tmp / "doc.pdf").write_bytes(b"%PDF-1.4 a")
    assert atril.binary_save(tmp / "doc.pdf", b"%PDF-1.4 b")["deshacer"] and (tmp / "doc.pdf").read_bytes() == b"%PDF-1.4 b"
    for bad in ((proj / "portada.png", b"no"), (proj / "utf8.md", png), (tmp / "doc.pdf", png)):
        try:
            atril.binary_save(*bad)
            raise AssertionError("debió fallar")
        except ValueError:
            pass
    # historial de cambios: nada hasta el primer paso; árbol de pasos; Word reconstruido; guardado; limpieza
    atril.HIST_DIR = tmp / "versiones"
    txt = proj / "hist.md"
    txt.write_bytes(b"uno\r\n")
    assert atril.hist_public(txt)["nodos"] == [] and not atril.HIST_DIR.exists()
    h = atril.hist_step(txt, None, "Texto", b"uno\ndos\n")
    raiz, p1 = h["nodos"][0], h["id"]
    assert raiz["tipo"] == "abierto" and atril.hist_data(txt, raiz["id"]) == b"uno\n" and h["disco"] == raiz["id"]
    p2 = atril.hist_step(txt, p1, "Texto", b"uno\ndos\ntres\n")["id"]
    assert "+tres" in atril.hist_diff(txt, p2)
    rama = atril.hist_step(txt, p1, "Texto", b"otra rama\n")  # deshacer y editar: el paso 2 no se pierde
    assert {n["id"] for n in rama["nodos"]} >= {p1, p2} and rama["actual"] == rama["id"]
    atril.hist_go(txt, p2)
    assert atril.hist_public(txt)["actual"] == p2
    txt.write_bytes(b"uno\ndos\ntres\n")
    assert atril.hist_saved(txt, p2)["disco"] == p2  # el siguiente paso parte de aquí sin copiar nada
    assert atril.hist_step(txt, None, "Texto", b"x")["nodos"][-1]["padre"] == p2
    hw = proj / "hist.docx"
    hw.write_bytes(Path(wd).read_bytes())
    w1 = atril.hist_step(hw, None, "Negrita", json.dumps([{"buscar": "Título del tema", "negrita": True}]).encode())["id"]
    i = atril.docx_paragraphs(hw).index("Título del tema")
    w2 = atril.hist_step(hw, w1, "Texto", json.dumps([{"parrafo": i, "agregar": " (2)"}]).encode())["id"]
    assert atril.docx_paragraphs(io.BytesIO(atril.hist_docx(hw, w2)))[i] == "Título del tema (2)"
    assert "+Título del tema (2)" in atril.hist_diff(hw, w2) and Path(wd).read_bytes() == hw.read_bytes()  # el archivo no se tocó
    assert atril.hist_docx(hw, w1) != atril.hist_docx(hw, w2)
    atril.set_ajustes({"historial_dias": 1})
    old = atril.hist_dir(txt) / "meta.json"
    m = json.loads(old.read_text(encoding="utf-8"))
    m["ultimo"] = time.time() - 2 * 86400
    old.write_text(json.dumps(m), encoding="utf-8")
    atril.hist_cleanup()
    assert not atril.hist_dir(txt).exists() and atril.hist_dir(hw).exists()
    # pestaña web: X-Frame-Options y frame-ancestors deciden si la página se deja mostrar en un iframe
    import email.message
    import urllib.request

    class Resp:
        def __init__(self, headers):
            self.headers = email.message.Message()
            for k, v in headers.items():
                self.headers[k] = v
        def geturl(self):
            return "https://ejemplo.org/final"
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False

    real_open = urllib.request.urlopen
    for headers, ok in (({}, True), ({"X-Frame-Options": "DENY"}, False), ({"X-Frame-Options": "SAMEORIGIN"}, False),
                        ({"Content-Security-Policy": "default-src 'self'; frame-ancestors 'none'"}, False),
                        ({"Content-Security-Policy": "frame-ancestors *"}, True), ({"Content-Security-Policy": "script-src 'self'"}, True)):
        urllib.request.urlopen = lambda req, timeout=0, h=headers: Resp(h)
        r = atril.web_check("https://ejemplo.org")
        assert r["permitido"] is ok and r["url"] == "https://ejemplo.org/final", (headers, r)
    urllib.request.urlopen = real_open
    assert not atril.web_check("file:///C:/x")["permitido"]
    assert atril.ajuste("web_buscador") == "google"  # ajuste de lista: solo valores previstos
    atril.set_ajustes({"web_buscador": "bing"})
    atril.set_ajustes({"web_buscador": "inventado"})
    assert atril.ajuste("web_buscador") == "bing"
    atril.set_ajustes({"web_buscador": "google"})
    # .xlsx y .pptx: su texto para la IA
    xl = io.BytesIO()
    with zipfile.ZipFile(xl, "w") as z:
        z.writestr("xl/sharedStrings.xml", '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><si><t>Nombre</t></si></sst>')
        z.writestr("xl/worksheets/sheet1.xml", '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
                   '<row><c t="s"><v>0</v></c><c><v>42</v></c></row></sheetData></worksheet>')
    assert atril.extract_text("a.xlsx", xl.getvalue())["texto"] == "[Hoja 1]\nNombre\t42"
    pp = io.BytesIO()
    with zipfile.ZipFile(pp, "w") as z:
        z.writestr("ppt/slides/slide1.xml", '<p:sld xmlns:p="p" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
                   '<a:p><a:r><a:t>Hola</a:t></a:r></a:p></p:sld>')
    assert atril.extract_text("a.pptx", pp.getvalue())["texto"] == "[Diapositiva 1]\nHola"

    # .docx y .pdf generados por Atril desde el HTML del Markdown; formatos no viables se rechazan con aviso
    html = "<h1>Título ñ</h1><p><strong>Negrita</strong> y <em>cursiva</em></p><ul><li>uno</li></ul>" \
           "<table><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>2</td></tr></table>"
    docx = atril.create_file(proj, "resumen.docx", "", html)
    assert atril.docx_text(docx).split("\n") == ["Título ñ", "Negrita y cursiva", "• uno", "A", "B", "1", "2"]
    if atril.edge_path():
        assert Path(atril.create_file(proj, "resumen.pdf", "", html)).read_bytes()[:5] == b"%PDF-"
    try:
        atril.create_file(proj, "tabla.xlsx", "a,b")
        raise AssertionError("debió rechazar .xlsx")
    except ValueError as e:
        assert ".csv" in str(e)
    for bad in ("../x.md", "a/b.md", ""):
        try:
            atril.create_file(proj, bad, "x")
            raise AssertionError("nombre inválido aceptado: " + bad)
        except ValueError:
            pass

    # detección de archivos nombrados en el mensaje (sin IA)
    (proj / "montaña_narrativa.md").write_text("x", encoding="utf-8")
    (proj / "1 y 2 Samuel – Preguntas y Datos de Contexto.docx").write_bytes(b"x")
    (proj / "Datos_Contexto_1y2_Samuel.docx").write_bytes(b"x")
    names = lambda m: [f["nombre"] for f in atril.find_mentioned(m, str(proj / "utf8.md"))]
    assert names("lee la página 40 y usa la Montaña Narrativa") == ["montaña_narrativa.md"]
    assert names("revisa las preguntas y datos de contexto") == ["1 y 2 Samuel – Preguntas y Datos de Contexto.docx"]
    assert names("compara con Datos_Contexto_1y2_Samuel.docx") == ["Datos_Contexto_1y2_Samuel.docx"]
    assert names("hola, ¿qué tal?") == [] and atril.find_mentioned("montaña narrativa", str(fuera / "secreto.txt")) == []

    # lógica del chat en index.html (páginas, archivos y bloques en la respuesta, citas, añadir regla)
    if shutil.which("node"):
        html = (Path(atril.ROOT) / "index.html").read_text(encoding="utf-8")
        grab = lambda a, b: html[html.index(a):html.index(b)]
        js = ("const AJ = {};\nconst norm = t => t.replace(/\\r\\n/g, '\\n');\n" + grab("const plainTxt", "const srcText")
              + grab("function parsePages", "const rkey") + grab("const FILE_RE", "function iaMsg")
              + grab("function parseBlocks", "async function saveAsNew")
              + grab("function findRefs", "function verifyCites") + grab("function addRule", "function rulesDialog") + """
const assert = require('assert');
const b = parseBlocks('<<<<<<< BUSCAR\\nhola tío\\n=======\\nbuenos días\\n>>>>>>> REEMPLAZAR');
assert.deepStrictEqual(b, [['hola tío', 'buenos días']]);
assert.strictEqual(applyBlocks('x hola tío y', b), 'x buenos días y');
assert.strictEqual(applyBlocks('hola tío hola tío', b), null);  // ambiguo: no se aplica
assert.strictEqual(applyBlocks('nada', b), null);
assert.deepStrictEqual(parsePages('lee la página 40 y dime'), [40, 40]);
assert.deepStrictEqual(parsePages('Páginas 27 a 35'), [27, 35]);
assert.deepStrictEqual(parsePages('pág. 27-30'), [27, 30]);
assert.deepStrictEqual(parsePages('lee pagina 27 en adelante'), [27, 36]);
assert.strictEqual(parsePages('sin números'), null);
const reply = 'Aquí está:\\n<<<ARCHIVO preguntas.md\\n# Preguntas\\n1. ¿Quién?\\nARCHIVO>>>\\nListo.';
assert.deepStrictEqual(replyFiles(reply), [{ nombre: 'preguntas.md', texto: '# Preguntas\\n1. ¿Quién?' }]);
assert.ok(replyClean(reply).includes('📄 **preguntas.md**') && !replyClean(reply).includes('ARCHIVO>>>'));
assert.strictEqual(addRule('# R\\n\\n## Código\\n- a\\n\\n## Estilo\\n- b\\n', 'c', 'Código'), '# R\\n\\n## Código\\n- a\\n- c\\n\\n## Estilo\\n- b\\n');
assert.strictEqual(addRule('# R\\n- a', 'z', ''), '# R\\n- a\\n- z\\n');
assert.deepStrictEqual(findRefs('Ver 1 Samuel 4:4 y 1 Samuel 8:5, 20; Deuteronomio 17:14–15. Luego (7:10).'),
  ['1 Samuel 4:4', '1 Samuel 8:5', '1 Samuel 8:20', 'Deuteronomio 17:14-15']);
""")
        r = subprocess.run(["node", "-e", js], capture_output=True, text=True, encoding="utf-8")
        assert r.returncode == 0, r.stderr

    # avisos
    assert atril.status(proj) == ["Sin bitácora"]  # reglas.md ya existe (prueba de IA); AGENTS.md no se exige
    (proj / "reglas.md").unlink()
    assert atril.status(proj) == ["Sin reglas", "Sin bitácora"]
    for f in ("AGENTS.md", "reglas.md"):
        (proj / f).write_text("x")
    (proj / "bitacora.md").write_text("x\n" * 201)
    assert atril.status(proj) == ["Bitácora grande"]
    assert atril.status(tmp / "no-existe") == ["No encontrado"]

    # índice: todo se indexa (también 🔒), búsqueda por nombre y contenido sin tildes, PDF por la ventana, se reanuda
    atril.INDEX_DB = tmp / "idx" / "indice.db"
    (proj / "notas arca.md").write_text("El arca de Jehová volvió de los filisteos.", encoding="utf-8")
    (proj / "libro.pdf").write_bytes(b"%PDF-1.4 falso")
    (proj / ".env").write_text("CLAVE=secreta")
    atril.idx_pass()
    st = atril.idx_status()
    assert st["fase"] == "al día" and st["por_estado"]["pdf_pendiente"] >= 1 and st["archivos"] > 5
    r = atril.search("jehova filisteos")  # sin tildes y con prefijo
    assert [x["nombre"] for x in r["contenido"]] == ["notas arca.md"] and "[[Jehová]]" in r["contenido"][0]["fragmento"]
    assert [x["nombre"] for x in atril.search("arca .md")["nombres"]] == ["notas arca.md"]
    assert atril.search('"de los filisteos"')["contenido"] and not atril.search('"filisteos de los"')["contenido"]
    assert any(x["nombre"] == ".env" for x in atril.search("CLAVE")["contenido"])  # local: también lo sensible
    # 📄 solo nombre · ≡ solo contenido · Aa exacto (mayúsculas y tildes tal cual)
    assert not atril.search("arca", contenido=False)["contenido"] and atril.search("arca", contenido=False)["nombres"]
    assert not atril.search("arca", nombre=False)["nombres"] and atril.search("arca", nombre=False)["contenido"]
    assert atril.search("Jehová", exacto=True)["contenido"] and not atril.search("jehova", exacto=True)["contenido"]
    assert atril.search("jehova")["contenido"]  # sin Aa: da igual
    assert not atril.search("ARCA", exacto=True)["nombres"] and atril.search("arca", exacto=True)["nombres"]
    # «En:» solo en los proyectos elegidos (raíz tal como está en config.json); lista vacía: nada
    assert atril.search("arca", raices=[str(proj)])["nombres"] and atril.search("jehova", raices=[str(proj)])["contenido"]
    assert not atril.search("arca", raices=[str(tmp / "otro")])["nombres"] and not atril.search("arca", raices=[])["contenido"]
    nxt = atril.idx_pdf_next()
    assert nxt["ruta"].endswith("libro.pdf")  # el más pequeño primero
    atril.idx_pdf_save(nxt["ruta"], nxt["mtime"], [{"n": 3, "texto": "Samuel ungió a David"}])
    hit = atril.search("ungio")["contenido"][0]
    assert hit["nombre"] == "libro.pdf" and hit["pagina"] == 3 and not (atril.idx_pdf_next()["ruta"] or "").endswith("libro.pdf")
    atril.idx_pdf_save(nxt["ruta"], "otro-mtime", [])  # el PDF cambió mientras se leía: no se guarda
    assert atril.search("ungio")["contenido"]
    t0 = time.time(); atril.idx_pass(); assert time.time() - t0 < 5  # 2.ª pasada: solo lo que cambió
    (proj / "notas arca.md").unlink(); atril.idx_pass()
    assert not atril.search("filisteos")["contenido"] or all(x["nombre"] != "notas arca.md" for x in atril.search("filisteos")["contenido"])

    # git: estado por archivo con un repositorio real y metadatos del modal (i)
    if shutil.which("git"):
        repo = tmp / "repo"
        repo.mkdir()
        g = lambda *a: subprocess.run(["git", "-C", str(repo), *a], capture_output=True, check=True)
        g("init", "-q"); g("config", "user.email", "t@t"); g("config", "user.name", "Tester")
        (repo / ".gitignore").write_text("ignorado.txt\nbuild/\n")
        for n in ("limpio.txt", "cambia.txt"):
            (repo / n).write_text("a")
        g("add", "."); g("commit", "-q", "-m", "inicio")
        (repo / "cambia.txt").write_text("b"); (repo / "nuevo.txt").write_text("c"); (repo / "ignorado.txt").write_text("d")
        (repo / "build").mkdir(); (repo / "build" / "x.js").write_text("e")
        atril.git_cache.clear()
        estados = {n: atril.git_state(repo / n) for n in ("limpio.txt", "cambia.txt", "nuevo.txt", "ignorado.txt", "build/x.js")}
        assert estados == {"limpio.txt": "limpio", "cambia.txt": "modificado", "nuevo.txt": "nuevo",
                           "ignorado.txt": "ignorado", "build/x.js": "ignorado"}, estados
        meta = atril.file_meta(repo / "limpio.txt")
        assert meta["git"]["ultimo"]["mensaje"] == "inicio" and meta["git"]["commits"] == "1" and meta["git"]["creado_por"]["autor"] == "Tester"
    assert atril.git_state(proj / "utf8.md") == "sin_git"
    meta = atril.file_meta(proj / "utf8.md")
    assert meta["lineas"] == 2 and meta["git"]["estado"] == "sin_git" and meta["indice"]["estado"] == "ok"
    (proj / "img.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\0\0\0\rIHDR" + (640).to_bytes(4, "big") + (480).to_bytes(4, "big"))
    assert atril.file_meta(proj / "img.png")["documento"]["Dimensiones"] == "640 × 480 px"

    # ajustes: por defecto, validación de tipo y rango, y efecto real (tamaño máximo de vista)
    assert atril.ajuste("bitacora_conservar") == 20 and atril.ajuste("pestanas_vista_previa") is True
    v = atril.set_ajustes({"bitacora_conservar": "5", "puerto": 80, "letra_codigo": "abc", "revelar_en_arbol": 0})
    assert v["bitacora_conservar"] == 5 and v["puerto"] == 8765 and v["letra_codigo"] == 13 and v["revelar_en_arbol"] is False
    (proj / "grande.txt").write_bytes(b"linea\n" * 400_000)  # 2,4 MB
    assert atril.read_text(proj / "grande.txt")[2] is True
    atril.set_ajustes({"vista_max_mb": 3})
    assert atril.read_text(proj / "grande.txt")[2] is False
    atril.set_ajustes({"ia_limite_tokens": 5000})
    assert atril.ia_prefs()["limite"] == 5000  # un solo valor para ⚙ Ajustes y «Conectar IA»
    atril.set_ajustes({k: d for k, _, _, d, _, _ in atril.SETTINGS})  # vuelve a los valores por defecto

    # nueva carpeta: dentro de un proyecto, nunca reutiliza una existente
    assert Path(atril.create_folder(proj, "Sesión 4")).is_dir()
    for bad, exc in (("Sesión 4", FileExistsError), ("a/b", ValueError), ("..", ValueError)):
        try:
            atril.create_folder(proj, bad)
            raise AssertionError("debió fallar: " + bad)
        except exc:
            pass
    try:
        atril.create_folder(fuera, "x")
        raise AssertionError("fuera de un proyecto")
    except PermissionError:
        pass

    # recuperación: copia atómica de lo no guardado, se lista y se borra
    atril.RECOVERY_DIR = tmp / "recuperacion"
    atril.recovery_save({"clave": "nuevo-1", "ruta": None, "titulo": "nuevo 1", "texto": "hola ñ"})
    atril.recovery_save({"clave": "f-1a2b", "ruta": str(proj / "utf8.md"), "texto": "cambio", "mtime": "123"})
    atril.recovery_save({"clave": "nuevo-1", "ruta": None, "titulo": "nuevo 1", "texto": "hola ñ otra vez"})  # reemplaza
    items = {e["clave"]: e for e in atril.recovery_list()}
    assert items["nuevo-1"]["texto"] == "hola ñ otra vez" and items["f-1a2b"]["mtime"] == "123"
    assert not list(atril.RECOVERY_DIR.glob("*.tmp"))  # sin restos a medias
    atril.recovery_delete("nuevo-1")
    assert [e["clave"] for e in atril.recovery_list()] == ["f-1a2b"]
    for bad in ("../x", "A B", ""):
        try:
            atril.recovery_path(bad)
            raise AssertionError("clave inválida aceptada")
        except ValueError:
            pass

    # ventana: se abre con la última posición y tamaño (incluido un segundo monitor a la izquierda)
    assert atril.window_flags({}) == []
    assert atril.window_flags({"ventana": {"x": -1600, "y": 20, "w": 1400, "h": 900}}) == \
        ["--window-position=-1600,20", "--window-size=1400,900"]
    assert atril.window_flags({"ventana": {"x": 0, "y": 0, "w": 120, "h": 80}}) == []  # tamaño absurdo: se ignora

    # HTTP
    srv = ThreadingHTTPServer(("127.0.0.1", 0), atril.Handler)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    assert get(port, "/api/estado", header=False)[0] == 403  # una web externa no puede llamar a la API
    code, body = get(port, "/api/estado")
    assert code == 200 and json.loads(body)["proyectos"][0]["avisos"] == ["Bitácora grande"]
    code, body = get(port, "/api/abrir?ruta=" + urllib.request.quote(str(proj / "utf8.md")))
    assert code == 200 and json.loads(body)["texto"] == "# Hola ñ\n"
    assert get(port, "/api/abrir?ruta=" + urllib.request.quote(str(fuera / "secreto.txt")))[0] == 403
    raw = "/raw/" + "/".join(urllib.request.quote(p) for p in str(proj / "img.png").replace("\\", "/").split("/"))
    assert get(port, raw, header=False, rng="bytes=0-3") == (206, b"\x89PNG")
    assert get(port, "/raw/" + urllib.request.quote(str(fuera / "secreto.txt").replace("\\", "/")), header=False)[0] == 404

    # explorador: lista nombres fuera de lo añadido, pero el contenido sigue bloqueado
    (fuera / "app").mkdir()
    (fuera / "app" / "artisan").write_text("")
    (fuera / "app" / ".git").mkdir()
    code, body = get(port, "/api/explorar?ruta=" + urllib.request.quote(str(fuera)))
    items = {i["nombre"]: i for i in json.loads(body)["items"]}
    assert code == 200 and items["app"]["tipo"] == ["Laravel", "git"] and items["app"]["avisos"] == ["Sin reglas", "Sin bitácora"]
    assert items["suelto.txt"]["estado"] == "añadido" and items["secreto.txt"]["estado"] is None
    assert get(port, "/api/abrir?ruta=" + urllib.request.quote(str(fuera / "secreto.txt")))[0] == 403
    code, body = get(port, "/api/explorar?ruta=" + urllib.request.quote(str(tmp)))
    assert {i["nombre"]: i["estado"] for i in json.loads(body)["items"]}["proyecto"] == "añadido"
    assert json.loads(get(port, "/api/explorar?ruta=")[1])["unidades"]  # "Este equipo" lista unidades
    assert get(port, "/api/explorar", header=False)[0] == 403
    assert get(port, "/api/plantilla?ruta=" + urllib.request.quote(str(fuera)))[0] == 403  # solo proyectos añadidos
    req = urllib.request.Request(f"http://127.0.0.1:{port}/api/ejecutar", method="POST",
                                 headers={"X-Atril": "1", "Content-Type": "application/json"},
                                 data=json.dumps({"ruta": str(fuera / "secreto.txt")}).encode())
    try:
        urllib.request.urlopen(req)
        raise AssertionError("debió rechazar")
    except urllib.error.HTTPError as e:
        assert e.code == 403  # no ejecuta nada fuera de lo añadido
    code, body = get(port, "/api/abrir?ruta=" + urllib.request.quote(str(proj / "hola.py")))
    assert json.loads(body)["ejecutar"]["carpeta"] == str(proj)
    def post(path, data):
        req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", method="POST", data=json.dumps(data).encode(),
                                     headers={"X-Atril": "1", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    # 🔗 chat vinculado a una pestaña: 🧹 limpiar lo vacía sin perder el vínculo; un "nuevo 1" guardado se lleva su chat
    atril.save_config({**atril.load_config()})  # (sin cambios: asegura config escrita)
    atril.conv_save({"id": "abc1", "titulo": "t", "fecha": "f", "ia": "claude", "session": "s9", "proyecto": "",
                     "mensajes": [{"rol": "tu", "texto": "hola"}], "adjuntos": [{"nombre": "x", "texto": "y"}], "vinculo": "nuevo:1"})
    assert [c["vinculo"] for c in atril.conv_list() if c["id"] == "abc1"] == ["nuevo:1"]
    code, d = post("/api/conv/limpiar", {"id": "abc1"})
    assert code == 200 and d["mensajes"] == [] and d["adjuntos"] == [] and d["session"] is None and d["vinculo"] == "nuevo:1"
    post("/api/conv/revincular", {"de": "nuevo:1", "a": str(proj / "guardado.md")})
    assert atril.conv_load("abc1")["vinculo"] == str(proj / "guardado.md")
    atril.conv_path("abc1").unlink()

    (proj / ".env").write_text("CLAVE=secreta")
    # 🔒 por defecto se permite (son archivos locales del usuario); si se desactiva en Ajustes, el servidor lo bloquea
    code, d = get(port, "/api/extraer?ruta=" + urllib.request.quote(str(proj / ".env")))
    assert code == 200 and "CLAVE=secreta" in json.loads(d)["texto"]
    atril.set_ajustes({"ia_permitir_sensibles": False})
    code, d = post("/api/conv/enviar", {"ia": "gemini", "mensaje": "x", "adjuntos": [{"nombre": ".env", "texto": "CLAVE=secreta"}]})
    assert code == 403 and "sensible" in d["error"]  # ni aunque la interfaz fallara
    assert get(port, "/api/extraer?ruta=" + urllib.request.quote(str(proj / ".env")))[0] == 403
    atril.set_ajustes({"ia_permitir_sensibles": True})
    assert post("/api/conv/enviar", {"ia": "no-existe", "mensaje": "x", "adjuntos": []})[0] == 502
    code, body = get(port, "/api/plantilla?ruta=" + urllib.request.quote(str(proj)))
    assert code == 200 and "{{proyecto}}" in json.loads(body)["plantillas"]["AGENTS.md"]

    # añadir desde el explorador y recordar la última ubicación
    req = urllib.request.Request(f"http://127.0.0.1:{port}/api/agregar", method="POST",
                                 headers={"X-Atril": "1", "Content-Type": "application/json"},
                                 data=json.dumps({"tipo": "proyectos", "rutas": [str(fuera / "app"), str(tmp / "no-existe")],
                                                  "ultima": str(fuera)}).encode())
    st = json.loads(urllib.request.urlopen(req).read())
    assert [p["nombre"] for p in st["proyectos"]] == ["proyecto", "app"]  # la ruta inexistente se ignora
    assert json.loads(get(port, "/api/explorar")[1])["ruta"] == str(fuera.resolve())
    srv.shutdown()

print("OK: todas las pruebas pasan")
