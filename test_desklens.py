"""Prueba de DeskLens: python test_desklens.py  (no abre ventanas ni toca config.json real)."""
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

# «import desklens» solo encuentra desklens.pyw en Windows: se carga el archivo directamente (macOS y Linux igual)
_loader = importlib.machinery.SourceFileLoader("desklens", str(Path(__file__).with_name("desklens.pyw")))
desklens = importlib.util.module_from_spec(importlib.util.spec_from_loader("desklens", _loader))
sys.modules["desklens"] = desklens
_loader.exec_module(desklens)


def get(port, path, header=True, rng=None):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}")
    if header:
        req.add_header("X-DeskLens", "1")
    if rng:
        req.add_header("Range", rng)
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    desklens.CONFIG = tmp / "config.json"
    # nada de la prueba va al historial\ real de DeskLens (copias para deshacer, versiones, archivos de la IA)
    desklens.UNDO_DIR, desklens.HIST_DIR, desklens.IA_DIR = tmp / "deshacer", tmp / "versiones", tmp / "ia"
    # ni al índice, conversaciones o recuperación reales: con DeskLens abierto, su índice está en uso y la prueba esperaba
    desklens.INDEX_DB, desklens.CONV_DIR, desklens.RECOVERY_DIR = tmp / "idx" / "indice.db", tmp / "conv", tmp / "recuperacion"
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
    desklens.add_paths("proyectos", [proj])
    desklens.add_paths("sueltos", [suelto])

    # permisos: proyecto y suelto sí; lo demás no, ni con ../
    assert desklens.allowed(proj / "utf8.md") and desklens.allowed(suelto)
    assert not desklens.allowed(fuera / "secreto.txt")
    assert not desklens.allowed(proj / ".." / "fuera" / "secreto.txt")

    # codificaciones y binarios
    assert desklens.read_text(proj / "utf8.md")[:2] == ("# Hola ñ\n", "utf-8")
    assert desklens.read_text(proj / "bom.ps1")[1] == "utf-8-bom"
    assert desklens.read_text(proj / "ansi.bat")[:2] == ("echo café\r\n", "cp1252")
    assert desklens.read_text(proj / "utf16.txt")[:2] == ("hola", "utf-16")
    assert desklens.read_text(proj / "img.png")[0] is None

    # guardar: conserva codificación y CRLF, crea .bak una vez, detecta conflictos
    bat = proj / "ansi.bat"
    mt = str(bat.stat().st_mtime_ns)
    code, d = desklens.save_text(bat, "echo café\necho ñ\n", "cp1252", "CRLF", mt)
    assert code == 200 and bat.read_bytes() == "echo café\r\necho ñ\r\n".encode("cp1252")
    assert Path(d["bak"]).read_bytes() == "echo café\r\n".encode("cp1252")
    code, d2 = desklens.save_text(bat, "echo 2\n", "cp1252", "CRLF", d["mtime"])
    assert code == 200 and d2["bak"] is None  # un solo .bak por sesión
    assert desklens.save_text(bat, "x", "cp1252", "CRLF", mt)[0] == 409  # cambió desde que se abrió
    assert desklens.save_text(bat, "x", "cp1252", "CRLF", mt, force=True)[0] == 200
    code, d = desklens.save_text(bat, "echo 😀", "cp1252", "CRLF", str(bat.stat().st_mtime_ns))
    assert code == 422 and "línea 1" in d["error"] and bat.read_bytes() == b"x"  # no rompe el .bat
    ps1 = proj / "bom.ps1"
    desklens.save_text(ps1, "Write-Host 'ñ'", "utf-8-bom", "LF", str(ps1.stat().st_mtime_ns))
    assert ps1.read_bytes() == b"\xef\xbb\xbf" + "Write-Host 'ñ'".encode()
    assert desklens.save_text(proj / "img.png", "x", "utf-8", "LF", "0")[0] == 400  # binario: solo lectura
    (proj / "conGit" / ".git").mkdir(parents=True)
    g = proj / "conGit" / "a.py"
    g.write_text("1")
    assert desklens.save_text(g, "2", "utf-8", "LF", str(g.stat().st_mtime_ns))[1]["bak"] is None  # git es el respaldo

    # plantillas: crea solo lo que falta y nunca sobrescribe
    nuevo = tmp / "nuevo"
    nuevo.mkdir()
    (nuevo / "CLAUDE.md").write_text("mío")
    info = desklens.template_info(nuevo)
    assert [a["existe"] for a in info["archivos"]] == [False, True, False, False, False]
    creados = desklens.create_from_templates(nuevo, desklens.TEMPLATES, "Bot de pedidos.", "Node")
    assert creados == ["AGENTS.md", "GEMINI.md", "reglas.md", "bitacora.md"]
    assert (nuevo / "CLAUDE.md").read_text() == "mío"
    agents = (nuevo / "AGENTS.md").read_text(encoding="utf-8")
    assert "# Proyecto: nuevo" in agents and "Bot de pedidos. Tecnología: Node." in agents and "{{" not in agents
    assert "{{" not in (nuevo / "bitacora.md").read_text(encoding="utf-8")
    assert desklens.status(nuevo) == []

    # archivar: quedan las 20 más recientes, el resto va a bitacora/AAAA.md sin perder nada
    entradas = [f"## 2026-{m:02d}-01 · e{m}\nTexto {m}\n\n" for m in range(12, 0, -1)]
    entradas += [f"## 2025-{m:02d}-01 · v{m}\nTexto viejo {m}\n\n" for m in range(12, 0, -1)]
    (nuevo / "bitacora.md").write_text("# Bitácora\n\n" + "".join(entradas), encoding="utf-8")
    (nuevo / "bitacora").mkdir()
    (nuevo / "bitacora" / "2025.md").write_text("# Bitácora 2025\n\n## 2025-00-01 · más vieja\nx\n", encoding="utf-8")
    assert desklens.archive_log(nuevo) == {"2025": 4}
    queda = (nuevo / "bitacora.md").read_text(encoding="utf-8")
    assert queda.startswith("# Bitácora\n\n## 2026-12-01") and queda.count("\n## ") == 20
    archivo = (nuevo / "bitacora" / "2025.md").read_text(encoding="utf-8")
    assert archivo.startswith("# Bitácora 2025\n\n## 2025-04-01") and archivo.count("## 2025-") == 5
    assert archivo.rstrip().endswith("más vieja\nx")

    # consola: salida normal y de error, entrada, código de salida, tildes en .bat, detener
    def wait_run(rid, t=20):
        end = time.time() + t
        while time.time() < end:
            o = desklens.runs[rid].output(0)
            if o["fin"]:
                return o
            time.sleep(0.1)
        raise AssertionError("el proceso no terminó")

    def text(o, kind):
        return "".join(t for k, t in o["trozos"] if k == kind)

    (proj / "hola.py").write_text('import sys\nprint("hola ñ")\nprint("mal", file=sys.stderr)\n'
                                  'print("leí", input())\nsys.exit(3)\n', encoding="utf-8")
    args, enc = desklens.command_for(proj / "hola.py")
    rid = desklens.start_run(args, str(proj), enc, "hola.py")
    desklens.runs[rid].send("sí")
    o = wait_run(rid)
    assert text(o, "out") == "hola ñ\nleí sí\n" and text(o, "err") == "mal\n" and o["codigo"] == 3
    def run_file(p):
        a, e = desklens.command_for(p)
        return desklens.start_run(a, str(p.parent), e, p.name)

    if desklens.WINDOWS:
        (proj / "acento.bat").write_bytes("@echo off\r\necho café\r\n".encode(desklens.oem_encoding()))
        o = wait_run(run_file(proj / "acento.bat"))
        (proj / "largo.bat").write_text("@ping -n 30 127.0.0.1 > nul\r\n")
        rid = run_file(proj / "largo.bat")
    else:  # macOS y Linux: lo mismo con bash; un .bat dice que es solo de Windows
        assert desklens.command_for(proj / "ansi.bat") == (None, "Solo se ejecuta en Windows")
        (proj / "acento.sh").write_text("echo café\n", encoding="utf-8")
        o = wait_run(run_file(proj / "acento.sh"))
        (proj / "largo.sh").write_text("sleep 30 & sleep 30\n")  # con un hijo: detener también lo para
        rid = run_file(proj / "largo.sh")
    assert text(o, "out") == "café\n" and o["codigo"] == 0
    time.sleep(0.5)
    desklens.runs[rid].kill()
    assert wait_run(rid, 10)["codigo"] != 0
    assert desklens.command_for(proj / "utf8.md") == (None, None) and desklens.run_info(proj / "utf8.md") is None
    assert desklens.run_info(proj / "hola.py")["texto"].endswith("hola.py")

    # comando de pruebas detectado por los archivos del proyecto
    lara = tmp / "lara"
    lara.mkdir()
    assert desklens.detect_tests(lara) == ""
    (lara / "package.json").write_text('{"scripts": {"test": "jest"}}')
    assert desklens.detect_tests(lara) == "npm test"
    (lara / "artisan").write_text("")
    assert desklens.detect_tests(lara) == "php artisan test"

    # IA: archivos sensibles, prompt, lectura de la salida de cada CLI
    assert desklens.is_sensitive(proj / ".env.local") and desklens.is_sensitive(proj / "clave.PEM")
    assert desklens.is_sensitive(proj / "wp-config.php") and desklens.is_sensitive(proj / "id_rsa") and desklens.is_sensitive(proj / "x.kdbx")
    assert not desklens.is_sensitive(proj / "web.php")
    p = desklens.conv_prompt(desklens.CONV_INTRO, "- Usar usted", [{"nombre": "a.pdf", "desc": "pág. 4", "texto": "hola tío"}], [], "Más formal")
    assert p.index("<<<ARCHIVO") < p.index("REGLAS") < p.index("ADJUNTO: a.pdf (pág. 4)") < p.index("MENSAJE:\nMás formal")
    assert "REGLAS" not in desklens.conv_prompt("", "", [], [], "¿qué es?")
    assert desklens.parse_ai("claude", json.dumps({"result": "OK", "usage": {"input_tokens": 5, "cache_read_input_tokens": 100,
                                                                          "output_tokens": 2}})) == ("OK", {"entrada": 105, "salida": 2})
    assert desklens.parse_ai("gemini", json.dumps({"response": "OK", "stats": {"models": {"g": {"tokens": {"prompt": 7, "candidates": 1}}}}})) \
        == ("OK", {"entrada": 7, "salida": 1})
    codex_out = "\n".join(json.dumps(e) for e in [{"type": "thread.started"},
                                                   {"type": "item.completed", "item": {"type": "agent_message", "text": "OK"}},
                                                   {"type": "turn.completed", "usage": {"input_tokens": 9, "output_tokens": 1}}])
    assert desklens.parse_ai("codex", codex_out) == ("OK", {"entrada": 9, "salida": 1})
    assert desklens.parse_ai("claude", "texto plano") == ("texto plano", None)  # formato desconocido: no se pierde la respuesta

    # conversaciones: docx a texto, prompt, sesión de Claude, adjuntos enviados una sola vez
    import zipfile
    W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
    with zipfile.ZipFile(proj / "doc.docx", "w") as z:
        z.writestr("word/document.xml", f'<w:document {W}><w:body><w:p><w:r><w:t>Hola</w:t></w:r><w:r><w:tab/><w:t>ñandú</w:t></w:r></w:p>'
                                        '<w:p><w:r><w:t xml:space="preserve">Línea 2 </w:t></w:r></w:p></w:body></w:document>')
    assert desklens.docx_text(proj / "doc.docx") == "Hola\tñandú\nLínea 2"
    desklens.CONV_DIR = tmp / "historial" / "conversaciones"
    calls = []
    real_ask = desklens.ask_ai
    desklens.ask_ai = lambda ia, prompt, resume=None, images=(): (calls.append((ia, prompt, resume)) or
                                                     {"texto": f"resp {len(calls)}", "tokens": {"entrada": 1, "salida": 1},
                                                      "session": "s1" if ia == "claude" else None})
    (proj / "reglas.md").write_bytes(b"- Usar RVR60\n")
    (proj / "verificar_citas.py").write_text("print('ok')")
    c = desklens.conv_send({"ia": "claude", "mensaje": "Pregunta 1", "ruta": str(proj / "utf8.md"),
                         "adjuntos": [{"nombre": "libro.pdf", "desc": "págs. 27–30", "texto": "TEXTO DEL LIBRO"}]})
    assert "REGLAS" in calls[0][1] and "TEXTO DEL LIBRO" in calls[0][1] and calls[0][2] is None
    assert c["session"] == "s1" and c["verificador"].endswith("verificar_citas.py") and "texto" not in c["adjuntos"][0]
    c = desklens.conv_send({"id": c["id"], "ia": "claude", "mensaje": "OK, la B", "adjuntos": []})
    assert calls[1][2] == "s1" and "TEXTO DEL LIBRO" not in calls[1][1] and "REGLAS" not in calls[1][1]  # ya están en la sesión
    c = desklens.conv_send({"id": c["id"], "ia": "gemini", "mensaje": "Sigue", "adjuntos": []})
    assert "TEXTO DEL LIBRO" in calls[2][1] and "Usuario: OK, la B" in calls[2][1] and c["session"] is None  # sin sesión: todo
    assert [x["n"] for x in desklens.conv_list()] == [6]
    desklens.ask_ai = real_ask
    (proj / "reglas.md").unlink()
    desklens.conv_path(c["id"]).unlink()
    assert desklens.conv_list() == []
    for bad in ("../x", "abc/def", ""):
        try:
            desklens.conv_path(bad)
            raise AssertionError("id inválido aceptado")
        except ValueError:
            pass

    # reglas del proyecto y archivos nuevos
    assert desklens.project_of(proj / "conGit" / "a.py") == proj.resolve() and desklens.project_of(fuera / "suelto.txt") is None
    assert desklens.rules_for(proj / "utf8.md")["reglas"] is None
    (proj / "reglas.md").write_bytes(b"- Usar usted\n")
    assert desklens.rules_for(proj / "utf8.md")["reglas"]["texto"] == "- Usar usted\n"
    assert desklens.rules_for(fuera / "suelto.txt") == {"proyecto": None, "reglas": None}
    nuevo_f = desklens.create_file(proj, "nuevo.md", "# Hola\n")
    assert Path(nuevo_f).read_text(encoding="utf-8") == "# Hola\n"
    try:
        desklens.create_file(proj, "nuevo.md", "otro")
        raise AssertionError("debió negarse a sobrescribir")
    except FileExistsError:
        pass
    assert Path(desklens.create_file(fuera, "junto.md", "x")).name == "junto.md"  # junto a un suelto: queda como suelto
    assert any(s.endswith("junto.md") for s in desklens.load_config()["sueltos"])
    # cambios de formato/texto en un Word: todo o nada, conserva el resto, .bak, el visor y Word lo leen
    wd = desklens.create_file(proj, "tema.docx", "", "<h1>Título del tema</h1><p>El <strong>arca</strong> y el arca otra vez.</p>")
    r = desklens.docx_apply(wd, [{"buscar": "Título del tema", "color": "rojo", "tamano": 20},
                              {"buscar": "arca", "cursiva": True, "todas": True},
                              {"buscar": "otra vez", "reemplazar": "de nuevo"}])
    xml = zipfile.ZipFile(wd).read("word/document.xml").decode()
    assert r["cambios"] == 4 and r["bak"].endswith("tema.docx.bak") and 'w:val="FF0000"' in xml and 'w:val="40"' in xml
    assert desklens.docx_text(wd).split("\n") == ["Título del tema", "El arca y el arca de nuevo."]
    assert xml.count("<w:i />") + xml.count("<w:i/>") == 2
    # «Deshacer»: vuelve exactamente al archivo de antes del cambio
    desklens.UNDO_DIR = tmp / "deshacer"
    prev = Path(wd).read_bytes()
    r2 = desklens.docx_apply(wd, [{"buscar": "Título del tema", "color": "verde"}])
    assert Path(wd).read_bytes() != prev and r2["deshacer"]
    desklens.docx_undo(wd, r2["deshacer"])
    assert Path(wd).read_bytes() == prev
    for bad in ("../x", "zz"):
        try:
            desklens.docx_undo(wd, bad)
            raise AssertionError("debió fallar")
        except ValueError:
            pass
    assert desklens.ajuste("ia_confirmar_aplicar") is False  # predeterminado: se aplica sin preguntar
    before = Path(wd).read_bytes()
    try:
        desklens.docx_apply(wd, [{"buscar": "arca", "negrita": True}, {"buscar": "no existe"}])
        raise AssertionError("debió fallar")
    except ValueError as e:
        assert "no existe" in str(e)
    assert Path(wd).read_bytes() == before  # todo o nada: nada se tocó
    assert "DOCX" in desklens.abierto_hint(wd) and "DOCX" not in desklens.abierto_hint(proj / "utf8.md")
    # edición a mano: cambios en el párrafo N desde el carácter indicado (no en la primera aparición del documento)
    assert desklens.docx_paragraphs(wd) == ["Título del tema", "El arca y el arca de nuevo."]
    prev = Path(wd).read_bytes()
    r3 = desklens.docx_apply(wd, [{"parrafo": 1, "desde": 12, "buscar": "arca", "reemplazar": "Arca santa"},
                               {"parrafo": 1, "desde": 0, "buscar": "El", "negrita": True},
                               {"parrafo": 0, "agregar": " (2)"}])
    assert desklens.docx_paragraphs(wd) == ["Título del tema (2)", "El arca y el Arca santa de nuevo."]
    try:
        desklens.docx_apply(wd, [{"parrafo": 9, "buscar": "x", "negrita": True}])
        raise AssertionError("debió fallar")
    except ValueError:
        pass
    desklens.docx_undo(wd, r3["deshacer"])
    assert Path(wd).read_bytes() == prev
    # imagen en un Word: párrafo nuevo después del indicado, con su relación, tipo y proporción
    import base64 as b64, io, struct, zlib
    chunk = lambda t, d: struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d))
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 40, 20, 8, 2, 0, 0, 0)) + \
        chunk(b"IDAT", zlib.compress(b"\x00" + b"\xff\x00\x00" * 40 * 20)) + chunk(b"IEND", b"")
    (proj / "portada.png").write_bytes(png)
    assert desklens.image_size(png) == (40, 20)
    ref = desklens.extract_text(proj / "portada.png")
    assert ref["imagen"] and "40×20" in ref["texto"] and str(proj / "portada.png") in ref["texto"]
    assert desklens.extract_text("x.png", png)["imagen"] and desklens.extract_text("x.zip", b"PK\0\0")["ref"]
    desklens.docx_apply(wd, [{"imagen": str(proj / "portada.png"), "buscar": "Título del tema", "ancho_cm": 10},
                          {"imagen": "otra.png", "datos": b64.b64encode(png).decode(), "buscar": "arca", "posicion": "antes"}])
    with zipfile.ZipFile(wd) as z:
        xml = z.read("word/document.xml").decode()
        assert z.read("word/media/desklens1.png") == png and "word/media/desklens2.png" in z.namelist()
        assert 'Extension="png"' in z.read("[Content_Types].xml").decode() and "rIdDeskLens2" in z.read("word/_rels/document.xml.rels").decode()
    assert 'cx="3600000" cy="1800000"' in xml  # 10 cm de ancho, mitad de alto
    assert xml.index("Título del tema") < xml.index("rIdDeskLens1") < xml.index("rIdDeskLens2") < xml.index(">El <")
    # soltada a mano sobre un párrafo: va a ese párrafo (por índice), aunque «buscar» esté vacío
    desklens.docx_apply(wd, [{"imagen": str(proj / "portada.png"), "parrafo": 0, "buscar": "", "posicion": "antes"}])
    with zipfile.ZipFile(wd) as z:
        xml = z.read("word/document.xml").decode()
    assert xml.index("rIdDeskLens3") < xml.index("Título del tema")
    for bad in ({"imagen": "foto.webp", "buscar": "arca"}, {"imagen": "no.png", "buscar": "arca"}):
        try:
            desklens.docx_apply(wd, [bad])
            raise AssertionError("debió fallar")
        except ValueError:
            pass
    # imagen editada en DeskLens: .bak la primera vez, copia para deshacer; no acepta datos que no son imagen
    png2 = png.replace(struct.pack(">II", 40, 20), struct.pack(">II", 20, 40))
    r = desklens.binary_save(proj / "portada.png", png2)
    assert (proj / "portada.png").read_bytes() == png2 and Path(r["bak"]).read_bytes() == png and r["deshacer"]
    desklens.docx_undo(proj / "portada.png", r["deshacer"])
    assert (proj / "portada.png").read_bytes() == png
    (tmp / "doc.pdf").write_bytes(b"%PDF-1.4 a")
    assert desklens.binary_save(tmp / "doc.pdf", b"%PDF-1.4 b")["deshacer"] and (tmp / "doc.pdf").read_bytes() == b"%PDF-1.4 b"
    for bad in ((proj / "portada.png", b"no"), (proj / "utf8.md", png), (tmp / "doc.pdf", png)):
        try:
            desklens.binary_save(*bad)
            raise AssertionError("debió fallar")
        except ValueError:
            pass
    # historial de cambios: nada hasta el primer paso; árbol de pasos; Word reconstruido; guardado; limpieza
    desklens.HIST_DIR = tmp / "versiones"
    txt = proj / "hist.md"
    txt.write_bytes(b"uno\r\n")
    assert desklens.hist_public(txt)["nodos"] == [] and not desklens.HIST_DIR.exists()
    h = desklens.hist_step(txt, None, "Texto", b"uno\ndos\n")
    raiz, p1 = h["nodos"][0], h["id"]
    assert raiz["tipo"] == "abierto" and desklens.hist_data(txt, raiz["id"]) == b"uno\n" and h["disco"] == raiz["id"]
    p2 = desklens.hist_step(txt, p1, "Texto", b"uno\ndos\ntres\n")["id"]
    assert "+tres" in desklens.hist_diff(txt, p2)
    rama = desklens.hist_step(txt, p1, "Texto", b"otra rama\n")  # deshacer y editar: el paso 2 no se pierde
    assert {n["id"] for n in rama["nodos"]} >= {p1, p2} and rama["actual"] == rama["id"]
    desklens.hist_go(txt, p2)
    assert desklens.hist_public(txt)["actual"] == p2
    txt.write_bytes(b"uno\ndos\ntres\n")
    assert desklens.hist_saved(txt, p2)["disco"] == p2  # el siguiente paso parte de aquí sin copiar nada
    assert desklens.hist_step(txt, None, "Texto", b"x")["nodos"][-1]["padre"] == p2
    hw = proj / "hist.docx"
    hw.write_bytes(Path(wd).read_bytes())
    w1 = desklens.hist_step(hw, None, "Negrita", json.dumps([{"buscar": "Título del tema", "negrita": True}]).encode())["id"]
    i = desklens.docx_paragraphs(hw).index("Título del tema")
    w2 = desklens.hist_step(hw, w1, "Texto", json.dumps([{"parrafo": i, "agregar": " (2)"}]).encode())["id"]
    assert desklens.docx_paragraphs(io.BytesIO(desklens.hist_docx(hw, w2)))[i] == "Título del tema (2)"
    assert "+Título del tema (2)" in desklens.hist_diff(hw, w2) and Path(wd).read_bytes() == hw.read_bytes()  # el archivo no se tocó
    assert desklens.hist_docx(hw, w1) != desklens.hist_docx(hw, w2)
    desklens.set_ajustes({"historial_dias": 1})
    old = desklens.hist_dir(txt) / "meta.json"
    m = json.loads(old.read_text(encoding="utf-8"))
    m["ultimo"] = time.time() - 2 * 86400
    old.write_text(json.dumps(m), encoding="utf-8")
    desklens.hist_cleanup()
    assert not desklens.hist_dir(txt).exists() and desklens.hist_dir(hw).exists()
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
        r = desklens.web_check("https://ejemplo.org")
        assert r["permitido"] is ok and r["url"] == "https://ejemplo.org/final", (headers, r)
    urllib.request.urlopen = real_open
    assert not desklens.web_check("file:///C:/x")["permitido"]
    assert desklens.ajuste("web_buscador") == "google"  # ajuste de lista: solo valores previstos
    desklens.set_ajustes({"web_buscador": "bing"})
    desklens.set_ajustes({"web_buscador": "inventado"})
    assert desklens.ajuste("web_buscador") == "bing"
    desklens.set_ajustes({"web_buscador": "google"})
    # .xlsx y .pptx: su texto para la IA
    xl = io.BytesIO()
    with zipfile.ZipFile(xl, "w") as z:
        z.writestr("xl/sharedStrings.xml", '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><si><t>Nombre</t></si></sst>')
        z.writestr("xl/worksheets/sheet1.xml", '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
                   '<row><c t="s"><v>0</v></c><c><v>42</v></c></row></sheetData></worksheet>')
    assert desklens.extract_text("a.xlsx", xl.getvalue())["texto"] == "[Hoja 1]\nNombre\t42"
    pp = io.BytesIO()
    with zipfile.ZipFile(pp, "w") as z:
        z.writestr("ppt/slides/slide1.xml", '<p:sld xmlns:p="p" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
                   '<a:p><a:r><a:t>Hola</a:t></a:r></a:p></p:sld>')
    assert desklens.extract_text("a.pptx", pp.getvalue())["texto"] == "[Diapositiva 1]\nHola"

    # .docx y .pdf generados por DeskLens desde el HTML del Markdown; formatos no viables se rechazan con aviso
    html = "<h1>Título ñ</h1><p><strong>Negrita</strong> y <em>cursiva</em></p><ul><li>uno</li></ul>" \
           "<table><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>2</td></tr></table>"
    docx = desklens.create_file(proj, "resumen.docx", "", html)
    assert desklens.docx_text(docx).split("\n") == ["Título ñ", "Negrita y cursiva", "• uno", "A", "B", "1", "2"]
    if desklens.edge_path():
        assert Path(desklens.create_file(proj, "resumen.pdf", "", html)).read_bytes()[:5] == b"%PDF-"
    try:
        desklens.create_file(proj, "tabla.xlsx", "a,b")
        raise AssertionError("debió rechazar .xlsx")
    except ValueError as e:
        assert ".csv" in str(e)
    for bad in ("../x.md", "a/b.md", ""):
        try:
            desklens.create_file(proj, bad, "x")
            raise AssertionError("nombre inválido aceptado: " + bad)
        except ValueError:
            pass

    # detección de archivos nombrados en el mensaje (sin IA)
    (proj / "montaña_narrativa.md").write_text("x", encoding="utf-8")
    (proj / "1 y 2 Samuel – Preguntas y Datos de Contexto.docx").write_bytes(b"x")
    (proj / "Datos_Contexto_1y2_Samuel.docx").write_bytes(b"x")
    names = lambda m: [f["nombre"] for f in desklens.find_mentioned(m, str(proj / "utf8.md"))]
    assert names("lee la página 40 y usa la Montaña Narrativa") == ["montaña_narrativa.md"]
    assert names("revisa las preguntas y datos de contexto") == ["1 y 2 Samuel – Preguntas y Datos de Contexto.docx"]
    assert names("compara con Datos_Contexto_1y2_Samuel.docx") == ["Datos_Contexto_1y2_Samuel.docx"]
    assert names("hola, ¿qué tal?") == [] and desklens.find_mentioned("montaña narrativa", str(fuera / "secreto.txt")) == []

    # lógica del chat en index.html (páginas, archivos y bloques en la respuesta, citas, añadir regla)
    if shutil.which("node"):
        html = (Path(desklens.ROOT) / "index.html").read_text(encoding="utf-8")
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
    assert desklens.status(proj) == ["Sin bitácora"]  # reglas.md ya existe (prueba de IA); AGENTS.md no se exige
    (proj / "reglas.md").unlink()
    assert desklens.status(proj) == ["Sin reglas", "Sin bitácora"]
    for f in ("AGENTS.md", "reglas.md"):
        (proj / f).write_text("x")
    (proj / "bitacora.md").write_text("x\n" * 201)
    assert desklens.status(proj) == ["Bitácora grande"]
    assert desklens.status(tmp / "no-existe") == ["No encontrado"]

    # índice: todo se indexa (también 🔒), búsqueda por nombre y contenido sin tildes, PDF por la ventana, se reanuda
    desklens.INDEX_DB = tmp / "idx" / "indice.db"
    (proj / "notas arca.md").write_text("El arca de Jehová volvió de los filisteos.", encoding="utf-8")
    (proj / "libro.pdf").write_bytes(b"%PDF-1.4 falso")
    (proj / ".env").write_text("CLAVE=secreta")
    desklens.idx_pass()
    st = desklens.idx_status()
    assert st["fase"] == "al día" and st["por_estado"]["pdf_pendiente"] >= 1 and st["archivos"] > 5
    r = desklens.search("jehova filisteos")  # sin tildes y con prefijo
    assert [x["nombre"] for x in r["contenido"]] == ["notas arca.md"] and "[[Jehová]]" in r["contenido"][0]["fragmento"]
    assert [x["nombre"] for x in desklens.search("arca .md")["nombres"]] == ["notas arca.md"]
    assert desklens.search('"de los filisteos"')["contenido"] and not desklens.search('"filisteos de los"')["contenido"]
    assert any(x["nombre"] == ".env" for x in desklens.search("CLAVE")["contenido"])  # local: también lo sensible
    # 📄 solo nombre · ≡ solo contenido · Aa exacto (mayúsculas y tildes tal cual)
    assert not desklens.search("arca", contenido=False)["contenido"] and desklens.search("arca", contenido=False)["nombres"]
    assert not desklens.search("arca", nombre=False)["nombres"] and desklens.search("arca", nombre=False)["contenido"]
    assert desklens.search("Jehová", exacto=True)["contenido"] and not desklens.search("jehova", exacto=True)["contenido"]
    assert desklens.search("jehova")["contenido"]  # sin Aa: da igual
    assert not desklens.search("ARCA", exacto=True)["nombres"] and desklens.search("arca", exacto=True)["nombres"]
    # «En:» solo en los proyectos elegidos (raíz tal como está en config.json); lista vacía: nada
    assert desklens.search("arca", raices=[str(proj)])["nombres"] and desklens.search("jehova", raices=[str(proj)])["contenido"]
    assert not desklens.search("arca", raices=[str(tmp / "otro")])["nombres"] and not desklens.search("arca", raices=[])["contenido"]
    nxt = desklens.idx_pdf_next()
    assert nxt["ruta"].endswith("libro.pdf")  # el más pequeño primero
    desklens.idx_pdf_save(nxt["ruta"], nxt["mtime"], [{"n": 3, "texto": "Samuel ungió a David"}])
    hit = desklens.search("ungio")["contenido"][0]
    assert hit["nombre"] == "libro.pdf" and hit["pagina"] == 3 and not (desklens.idx_pdf_next()["ruta"] or "").endswith("libro.pdf")
    desklens.idx_pdf_save(nxt["ruta"], "otro-mtime", [])  # el PDF cambió mientras se leía: no se guarda
    assert desklens.search("ungio")["contenido"]
    t0 = time.time(); desklens.idx_pass(); assert time.time() - t0 < 5  # 2.ª pasada: solo lo que cambió
    (proj / "notas arca.md").unlink(); desklens.idx_pass()
    assert not desklens.search("filisteos")["contenido"] or all(x["nombre"] != "notas arca.md" for x in desklens.search("filisteos")["contenido"])

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
        desklens.git_cache.clear()
        estados = {n: desklens.git_state(repo / n) for n in ("limpio.txt", "cambia.txt", "nuevo.txt", "ignorado.txt", "build/x.js")}
        assert estados == {"limpio.txt": "limpio", "cambia.txt": "modificado", "nuevo.txt": "nuevo",
                           "ignorado.txt": "ignorado", "build/x.js": "ignorado"}, estados
        meta = desklens.file_meta(repo / "limpio.txt")
        assert meta["git"]["ultimo"]["mensaje"] == "inicio" and meta["git"]["commits"] == "1" and meta["git"]["creado_por"]["autor"] == "Tester"
    assert desklens.git_state(proj / "utf8.md") == "sin_git"
    meta = desklens.file_meta(proj / "utf8.md")
    assert meta["lineas"] == 2 and meta["git"]["estado"] == "sin_git" and meta["indice"]["estado"] == "ok"
    (proj / "img.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\0\0\0\rIHDR" + (640).to_bytes(4, "big") + (480).to_bytes(4, "big"))
    assert desklens.file_meta(proj / "img.png")["documento"]["Dimensiones"] == "640 × 480 px"

    # ajustes: por defecto, validación de tipo y rango, y efecto real (tamaño máximo de vista)
    assert desklens.ajuste("bitacora_conservar") == 20 and desklens.ajuste("pestanas_vista_previa") is True
    v = desklens.set_ajustes({"bitacora_conservar": "5", "puerto": 80, "letra_codigo": "abc", "revelar_en_arbol": 0})
    assert v["bitacora_conservar"] == 5 and v["puerto"] == 8765 and v["letra_codigo"] == 13 and v["revelar_en_arbol"] is False
    (proj / "grande.txt").write_bytes(b"linea\n" * 400_000)  # 2,4 MB
    assert desklens.read_text(proj / "grande.txt")[2] is True
    desklens.set_ajustes({"vista_max_mb": 3})
    assert desklens.read_text(proj / "grande.txt")[2] is False
    desklens.set_ajustes({"ia_limite_tokens": 5000})
    assert desklens.ia_prefs()["limite"] == 5000  # un solo valor para ⚙ Ajustes y «Conectar IA»
    # navegador de la ventana: solo valores ofrecidos (los instalados, «auto» o «predeterminado»)
    assert desklens.set_ajustes({"navegador": "inventado"})["navegador"] == "auto"
    assert desklens.set_ajustes({"navegador": "predeterminado"})["navegador"] == "predeterminado"
    assert desklens.edge_path("no-instalado") == desklens.edge_path()  # elegido que ya no está: el primero que haya
    desklens.set_ajustes({k: d for k, _, _, d, _, _ in desklens.SETTINGS})  # vuelve a los valores por defecto

    # nueva carpeta: dentro de un proyecto, nunca reutiliza una existente
    assert Path(desklens.create_folder(proj, "Sesión 4")).is_dir()
    for bad, exc in (("Sesión 4", FileExistsError), ("a/b", ValueError), ("..", ValueError)):
        try:
            desklens.create_folder(proj, bad)
            raise AssertionError("debió fallar: " + bad)
        except exc:
            pass
    try:
        desklens.create_folder(fuera, "x")
        raise AssertionError("fuera de un proyecto")
    except PermissionError:
        pass

    # soltado desde el Explorador: se halla por nombre + tamaño + fecha y queda como suelto; otro tamaño no vale
    suelto = fuera / "soltado.txt"
    suelto.write_text("hola")
    st, real_sel = suelto.stat(), desklens.shell_selection
    desklens.shell_selection = lambda: ([], [str(fuera)])  # la carpeta abierta en el Explorador
    try:
        r = desklens.locate_dropped([{"nombre": "soltado.txt", "tam": st.st_size, "fecha": st.st_mtime * 1000},
                                  {"nombre": "soltado.txt", "tam": 99, "fecha": st.st_mtime * 1000}])
    finally:
        desklens.shell_selection = real_sel
    assert r[0]["ruta"] == str(suelto.resolve()) and r[1]["ruta"] is None and desklens.allowed(suelto)
    # «Eliminar»: nunca la carpeta de un proyecto ni algo que ya no existe (el envío real a la papelera no se prueba
    # aquí: llenaría la papelera del usuario en cada pasada)
    for bad, exc in ((proj, PermissionError), (proj / "no-existe.txt", FileNotFoundError)):
        try:
            desklens.to_trash(bad)
            raise AssertionError("debió fallar: " + str(bad))
        except exc:
            pass

    # recuperación: copia atómica de lo no guardado, se lista y se borra
    desklens.RECOVERY_DIR = tmp / "recuperacion"
    desklens.recovery_save({"clave": "nuevo-1", "ruta": None, "titulo": "nuevo 1", "texto": "hola ñ"})
    desklens.recovery_save({"clave": "f-1a2b", "ruta": str(proj / "utf8.md"), "texto": "cambio", "mtime": "123"})
    desklens.recovery_save({"clave": "nuevo-1", "ruta": None, "titulo": "nuevo 1", "texto": "hola ñ otra vez"})  # reemplaza
    items = {e["clave"]: e for e in desklens.recovery_list()}
    assert items["nuevo-1"]["texto"] == "hola ñ otra vez" and items["f-1a2b"]["mtime"] == "123"
    assert not list(desklens.RECOVERY_DIR.glob("*.tmp"))  # sin restos a medias
    desklens.recovery_delete("nuevo-1")
    assert [e["clave"] for e in desklens.recovery_list()] == ["f-1a2b"]
    for bad in ("../x", "A B", ""):
        try:
            desklens.recovery_path(bad)
            raise AssertionError("clave inválida aceptada")
        except ValueError:
            pass

    # ventana: se abre con la última posición y tamaño (incluido un segundo monitor a la izquierda)
    assert desklens.window_flags({}) == []
    assert desklens.window_flags({"ventana": {"x": -1600, "y": 20, "w": 1400, "h": 900}}) == \
        ["--window-position=-1600,20", "--window-size=1400,900"]
    assert desklens.window_flags({"ventana": {"x": 0, "y": 0, "w": 120, "h": 80}}) == []  # tamaño absurdo: se ignora

    # HTTP
    srv = ThreadingHTTPServer(("127.0.0.1", 0), desklens.Handler)
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
                                 headers={"X-DeskLens": "1", "Content-Type": "application/json"},
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
                                     headers={"X-DeskLens": "1", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    # 🔗 chat vinculado a una pestaña: 🧹 limpiar lo vacía sin perder el vínculo; un "nuevo 1" guardado se lleva su chat
    desklens.save_config({**desklens.load_config()})  # (sin cambios: asegura config escrita)
    desklens.conv_save({"id": "abc1", "titulo": "t", "fecha": "f", "ia": "claude", "session": "s9", "proyecto": "",
                     "mensajes": [{"rol": "tu", "texto": "hola"}], "adjuntos": [{"nombre": "x", "texto": "y"}], "vinculo": "nuevo:1"})
    assert [c["vinculo"] for c in desklens.conv_list() if c["id"] == "abc1"] == ["nuevo:1"]
    code, d = post("/api/conv/limpiar", {"id": "abc1"})
    assert code == 200 and d["mensajes"] == [] and d["adjuntos"] == [] and d["session"] is None and d["vinculo"] == "nuevo:1"
    post("/api/conv/revincular", {"de": "nuevo:1", "a": str(proj / "guardado.md")})
    assert desklens.conv_load("abc1")["vinculo"] == str(proj / "guardado.md")
    desklens.conv_path("abc1").unlink()

    (proj / ".env").write_text("CLAVE=secreta")
    # 🔒 por defecto se permite (son archivos locales del usuario); si se desactiva en Ajustes, el servidor lo bloquea
    code, d = get(port, "/api/extraer?ruta=" + urllib.request.quote(str(proj / ".env")))
    assert code == 200 and "CLAVE=secreta" in json.loads(d)["texto"]
    desklens.set_ajustes({"ia_permitir_sensibles": False})
    code, d = post("/api/conv/enviar", {"ia": "gemini", "mensaje": "x", "adjuntos": [{"nombre": ".env", "texto": "CLAVE=secreta"}]})
    assert code == 403 and "sensible" in d["error"]  # ni aunque la interfaz fallara
    assert get(port, "/api/extraer?ruta=" + urllib.request.quote(str(proj / ".env")))[0] == 403
    desklens.set_ajustes({"ia_permitir_sensibles": True})
    assert post("/api/conv/enviar", {"ia": "no-existe", "mensaje": "x", "adjuntos": []})[0] == 502
    code, body = get(port, "/api/plantilla?ruta=" + urllib.request.quote(str(proj)))
    assert code == 200 and "{{proyecto}}" in json.loads(body)["plantillas"]["AGENTS.md"]

    # añadir desde el explorador y recordar la última ubicación
    req = urllib.request.Request(f"http://127.0.0.1:{port}/api/agregar", method="POST",
                                 headers={"X-DeskLens": "1", "Content-Type": "application/json"},
                                 data=json.dumps({"tipo": "proyectos", "rutas": [str(fuera / "app"), str(tmp / "no-existe")],
                                                  "ultima": str(fuera)}).encode())
    st = json.loads(urllib.request.urlopen(req).read())
    assert [p["nombre"] for p in st["proyectos"]] == ["proyecto", "app"]  # la ruta inexistente se ignora
    assert json.loads(get(port, "/api/explorar")[1])["ruta"] == str(fuera.resolve())

    # vista Git: preparar, commit, quitar, descartar, ramas, deshacer commit, merge y push (estos dos en la consola)
    def git(cwd, *a):
        subprocess.run(["git", "-C", str(cwd), *a], check=True, capture_output=True)

    def wait_run(rid):
        for _ in range(200):
            o = desklens.runs[rid].output(0)
            if o["fin"]:
                return o
            time.sleep(0.05)
        raise AssertionError("la orden de git no terminó")

    rep, remoto = proj / "repo", fuera / "remoto.git"
    rep.mkdir()
    git(rep, "init", "-q", "-b", "main")
    git(rep, "config", "user.name", "Prueba"); git(rep, "config", "user.email", "prueba@example.com")
    git(fuera, "init", "-q", "--bare", "-b", "main", str(remoto))
    git(rep, "remote", "add", "origin", str(remoto))
    (rep / "a.md").write_text("uno\n")
    code, ov = post("/api/git/accion", {"ruta": str(rep), "accion": "commit", "mensaje": "inicio", "todo": True})
    assert code == 200 and ov["rama"] == "main" and not ov["cambios"] and not ov["preparados"], ov
    (rep / "a.md").write_text("dos\n"); (rep / "b.md").write_text("nuevo\n")
    ov = json.loads(get(port, "/api/git/estado?ruta=" + urllib.request.quote(str(rep)))[1])
    assert {(c["estado"], c["rel"]) for c in ov["cambios"]} == {("M", "a.md"), ("U", "b.md")}
    code, ov = post("/api/git/accion", {"ruta": str(rep), "accion": "preparar", "archivos": ["b.md"]})
    assert [(c["estado"], c["rel"]) for c in ov["preparados"]] == [("A", "b.md")]
    code, ov = post("/api/git/accion", {"ruta": str(rep), "accion": "quitar", "archivos": ["b.md"]})
    assert not ov["preparados"] and ("U", "b.md") in {(c["estado"], c["rel"]) for c in ov["cambios"]}
    code, ov = post("/api/git/accion", {"ruta": str(rep), "accion": "descartar", "archivos": ["a.md"]})
    assert (rep / "a.md").read_text() == "uno\n" and [c["rel"] for c in ov["cambios"]] == ["b.md"]
    assert post("/api/git/accion", {"ruta": str(rep), "accion": "preparar", "archivos": ["../fuera.txt"]})[0] == 400
    assert post("/api/git/accion", {"ruta": str(rep), "accion": "nueva_rama", "rama": "-x"})[0] == 400
    code, ov = post("/api/git/accion", {"ruta": str(rep), "accion": "nueva_rama", "rama": "tema"})
    assert ov["rama"] == "tema" and set(ov["ramas"]) == {"main", "tema"}
    post("/api/git/accion", {"ruta": str(rep), "accion": "commit", "mensaje": "b en tema", "todo": True})
    code, ov = post("/api/git/accion", {"ruta": str(rep), "accion": "deshacer_commit"})
    assert ov["preparados"] and ov["preparados"][0]["rel"] == "b.md"  # sin subir: vuelve a preparados
    post("/api/git/accion", {"ruta": str(rep), "accion": "commit", "mensaje": "b en tema"})
    post("/api/git/accion", {"ruta": str(rep), "accion": "cambiar_rama", "rama": "main"})
    assert not (rep / "b.md").exists()
    code, r = post("/api/git/accion", {"ruta": str(rep), "accion": "fusionar", "rama": "tema"})
    assert wait_run(r["id"])["codigo"] == 0 and (rep / "b.md").exists()
    code, r = post("/api/git/accion", {"ruta": str(rep), "accion": "push"})  # sin seguimiento: push -u origin main
    assert "-u origin main" in r["orden"] and wait_run(r["id"])["codigo"] == 0
    ov = json.loads(get(port, "/api/git/estado?ruta=" + urllib.request.quote(str(rep)))[1])
    assert ov["remota"] == "origin/main" and ov["adelante"] == 0
    assert post("/api/git/accion", {"ruta": str(rep), "accion": "deshacer_commit"})[0] == 400  # ya subido
    # Sincronizar: otro clon sube un commit (↓1) y aquí hay uno sin subir (↑1); pull y push dejan los dos en 0
    otro = fuera / "otro"
    git(fuera, "clone", "-q", str(remoto), str(otro))
    git(otro, "config", "user.name", "Otra"); git(otro, "config", "user.email", "otra@example.com")
    (otro / "c.md").write_text("de otra persona\n"); git(otro, "add", "-A"); git(otro, "commit", "-q", "-m", "c"); git(otro, "push", "-q")
    (rep / "d.md").write_text("mío\n")
    post("/api/git/accion", {"ruta": str(rep), "accion": "commit", "mensaje": "d", "todo": True})
    code, r = post("/api/git/accion", {"ruta": str(rep), "accion": "fetch"})
    wait_run(r["id"])
    ov = json.loads(get(port, "/api/git/estado?ruta=" + urllib.request.quote(str(rep)))[1])
    assert (ov["atras"], ov["adelante"]) == (1, 1) and ov["comprobado"] and time.time() - ov["comprobado"] < 60
    code, r = post("/api/git/accion", {"ruta": str(rep), "accion": "sincronizar"})
    assert r["orden"] == "git pull --no-rebase && git push" and wait_run(r["id"])["codigo"] == 0
    ov = json.loads(get(port, "/api/git/estado?ruta=" + urllib.request.quote(str(rep)))[1])
    assert (ov["atras"], ov["adelante"]) == (0, 0) and (rep / "c.md").exists()
    # estado de cada rama (panel de ramas) y nombre del servicio del remoto
    assert desklens.git_track("a\x1forigin/a\x1f[ahead 1, behind 2]") == {"rama": "a", "remota": "origin/a", "adelante": 1, "atras": 2, "borrada": False}
    assert desklens.git_track("b\x1forigin/b\x1f[gone]")["borrada"] and desklens.git_track("c\x1f\x1f")["remota"] is None
    assert desklens.git_service("remote.origin.url https://github.com/x/y.git") == "GitHub" and desklens.git_service("") is None
    assert desklens.git_service("remote.origin.url //servidor/repo.git") == "el remoto"
    # menú de ramas: Push a / Pull desde otra rama remota, Pull / Push de otra rama sin cambiarse, Cancelar fusión
    act = lambda accion, rama: post("/api/git/accion", {"ruta": str(rep), "accion": accion, "rama": rama})
    code, r = act("push_a", "origin/copia")
    assert r["orden"] == "git push origin HEAD:copia" and wait_run(r["id"])["codigo"] == 0
    git(otro, "fetch", "-q"); git(otro, "checkout", "-q", "-b", "copia", "origin/copia")
    (otro / "g.md").write_text("g\n"); git(otro, "add", "-A"); git(otro, "commit", "-q", "-m", "g"); git(otro, "push", "-q")
    code, r = act("pull_desde", "origin/copia")
    assert r["orden"] == "git pull --no-rebase origin copia" and wait_run(r["id"])["codigo"] == 0 and (rep / "g.md").exists()
    git(rep, "branch", "lado")
    code, r = act("push_rama", "lado")  # sin remota: se publica y queda enlazada
    assert r["orden"] == "git push -u origin lado" and wait_run(r["id"])["codigo"] == 0
    git(otro, "fetch", "-q"); git(otro, "checkout", "-q", "-b", "lado", "origin/lado")
    (otro / "h.md").write_text("h\n"); git(otro, "add", "-A"); git(otro, "commit", "-q", "-m", "h"); git(otro, "push", "-q")
    code, r = act("pull_rama", "lado")  # actualiza «lado» sin dejar «main»
    assert r["orden"] == "git fetch origin lado:lado" and wait_run(r["id"])["codigo"] == 0
    out = lambda cwd, *a: subprocess.check_output(["git", "-C", str(cwd), *a], text=True).strip()
    assert out(rep, "rev-parse", "lado") == out(otro, "rev-parse", "HEAD") and out(rep, "rev-parse", "--abbrev-ref", "HEAD") == "main"
    assert act("pull_rama", "main")[0] == 400 and act("push_a", "nada/x")[0] == 400 and act("push_a", "origin/-x")[0] == 400
    assert act("cancelar_fusion", "")[0] == 400  # no hay fusión en curso
    git(otro, "checkout", "-q", "main")
    # pestaña Ignorados: carpeta entera como una entrada, regla que lo ignora, y lo que git ya seguía aunque esté en .gitignore
    ign = fuera / "ign"; ign.mkdir(); git(ign, "init", "-q")
    git(ign, "config", "user.name", "T"); git(ign, "config", "user.email", "t@example.com")
    (ign / "db.php").write_text("x"); git(ign, "add", "-A"); git(ign, "commit", "-q", "-m", "db")
    (ign / ".gitignore").write_text("# dependencias\nnode_modules/\n.env\ndb.php\n")
    (ign / "node_modules" / "lib").mkdir(parents=True); (ign / "node_modules" / "lib" / "a.js").write_text("12345")
    (ign / "node_modules" / "b.js").write_text("123"); (ign / ".env").write_text("CLAVE=1")
    r = desklens.git_ignored(str(ign))
    got = {x["rel"]: x for x in r["ignorados"]}
    assert set(got) == {"node_modules", ".env"} and got["node_modules"]["dir"] and got[".env"]["tam"] == 7
    assert got["node_modules"]["regla"] == {"archivo": ".gitignore", "linea": 2, "patron": "node_modules/"}
    assert [(x["rel"], x["regla"]["linea"]) for x in r["seguidos"]] == [("db.php", 4)]
    assert desklens.folder_size(str(ign / "node_modules")) == {"archivos": 2, "tam": 8}
    assert sorted((x["nombre"], x["dir"], x["tam"]) for x in desklens.folder_items(str(ign / "node_modules"))) == [("b.js", False, 3), ("lib", True, None)]
    # grafo de la pantalla completa: entrantes y salientes, padres de un merge y +/− líneas por archivo
    (rep / "e.md").write_text("uno\ndos\n"); post("/api/git/accion", {"ruta": str(rep), "accion": "commit", "mensaje": "e", "todo": True})
    git(otro, "pull", "-q", "--no-rebase")  # el otro clon se pone al día con lo sincronizado arriba
    (otro / "f.md").write_text("f\n"); git(otro, "add", "-A"); git(otro, "commit", "-q", "-m", "f"); git(otro, "push", "-q")
    wait_run(post("/api/git/accion", {"ruta": str(rep), "accion": "fetch"})[1]["id"])
    g = json.loads(get(port, "/api/git/grafo?ruta=" + urllib.request.quote(str(rep)))[1])
    lados = {c["mensaje"]: c["lado"] for c in g["commits"]}
    assert lados["e"] == "saliente" and lados["f"] == "entrante" and lados["d"] == "" and g["remota"] == "origin/main"
    assert any(len(c["padres"]) == 2 for c in g["commits"])  # el merge de sincronizar
    e = next(c for c in g["commits"] if c["mensaje"] == "e")
    code, d = get(port, f"/api/git/archivos?ruta={urllib.request.quote(str(rep))}&hash={e['hash']}")
    assert [(f["rel"], f["mas"], f["menos"]) for f in json.loads(d)["archivos"]] == [("e.md", 2, 0)]
    # cambiar de rama con cambios sin commit: 409 con los archivos; «apartar» los guarda en el stash y
    # «llevar» los vuelve a poner en la rama nueva (aquí sin chocar: tocan líneas distintas)
    wait_run(post("/api/git/accion", {"ruta": str(rep), "accion": "sincronizar"})[1]["id"])
    (rep / "h.md").write_text("1\n2\n3\n"); post("/api/git/accion", {"ruta": str(rep), "accion": "commit", "mensaje": "h", "todo": True})
    post("/api/git/accion", {"ruta": str(rep), "accion": "nueva_rama", "rama": "otra"})
    (rep / "h.md").write_text("uno\n2\n3\n"); post("/api/git/accion", {"ruta": str(rep), "accion": "commit", "mensaje": "h otra", "todo": True})
    post("/api/git/accion", {"ruta": str(rep), "accion": "cambiar_rama", "rama": "main"})
    (rep / "h.md").write_text("1\n2\ntres\n")
    code, d = post("/api/git/accion", {"ruta": str(rep), "accion": "cambiar_rama", "rama": "otra"})
    assert code == 409 and d["codigo"] == "cambios_locales" and d["archivos"] == ["h.md"] and "«otra»" in d["error"]
    code, ov = post("/api/git/accion", {"ruta": str(rep), "accion": "cambiar_rama", "rama": "otra", "modo": "llevar"})
    assert code == 200 and ov["rama"] == "otra" and (rep / "h.md").read_text() == "uno\n2\ntres\n"  # los dos cambios
    git(rep, "checkout", "--", "h.md")
    post("/api/git/accion", {"ruta": str(rep), "accion": "cambiar_rama", "rama": "main"})
    (rep / "h.md").write_text("1\n2\ntres\n")
    code, ov = post("/api/git/accion", {"ruta": str(rep), "accion": "cambiar_rama", "rama": "otra", "modo": "apartar"})
    assert code == 200 and ov["rama"] == "otra" and (rep / "h.md").read_text() == "uno\n2\n3\n" and not ov["cambios"]
    assert "DeskLens: cambios de «main» al pasar a «otra»" in subprocess.run(["git", "-C", str(rep), "stash", "list"], capture_output=True, text=True, encoding="utf-8").stdout
    code, ov = post("/api/git/accion", {"ruta": str(rep), "accion": "cambiar_rama", "rama": "main"})
    assert [s["mensaje"].split(": ", 1)[-1] for s in ov["stashes"]] == ["DeskLens: cambios de «main» al pasar a «otra»"]
    code, ov = post("/api/git/accion", {"ruta": str(rep), "accion": "recuperar_stash", "rama": ov["stashes"][0]["id"]})
    assert code == 200 and (rep / "h.md").read_text() == "1\n2\ntres\n" and not ov["stashes"]
    assert post("/api/git/accion", {"ruta": str(rep), "accion": "recuperar_stash", "rama": "HEAD; rm"})[0] == 400
    git(rep, "checkout", "--", "h.md")
    # detalle del commit: mensaje completo, email, ramas, tamaños; versión binaria; crear rama aquí; revertir
    (rep / "i.md").write_text("cuatro\n"); (rep / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\0" * 20)
    post("/api/git/accion", {"ruta": str(rep), "accion": "commit", "mensaje": "Título\n\nCuerpo largo\nen dos líneas", "todo": True})
    h = subprocess.run(["git", "-C", str(rep), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    code, d = get(port, f"/api/git/commit?ruta={urllib.request.quote(str(rep))}&hash={h}")
    i = json.loads(d)
    assert i["mensaje"] == "Título\n\nCuerpo largo\nen dos líneas" and i["email"] == "prueba@example.com" and "main" in i["ramas"]
    assert i["tamanos"] == {"i.md": 7, "logo.png": 28} and len(i["padres"]) == 1  # tamaño en el commit (git guarda LF)
    code, png = get(port, f"/api/git/blob?ruta={urllib.request.quote(str(rep))}&hash={h}&rel=logo.png")
    assert code == 200 and png.startswith(b"\x89PNG")
    assert get(port, f"/api/git/blob?ruta={urllib.request.quote(str(rep))}&hash={h}&rel=-x")[0] == 404
    code, ov = post("/api/git/accion", {"ruta": str(rep), "accion": "rama_desde", "rama": "desde-aqui", "mensaje": h})
    assert "desde-aqui" in ov["ramas"] and ov["rama"] == "main"  # creada, sin cambiar a ella
    code, ov = post("/api/git/accion", {"ruta": str(rep), "accion": "revertir", "mensaje": h})
    assert code == 200 and not (rep / "i.md").exists() and not ov["cambios"]
    assert "Revert" in subprocess.run(["git", "-C", str(rep), "log", "-1", "--format=%s"], capture_output=True, text=True).stdout
    resumen = json.loads(get(port, "/api/git/resumen")[1])
    assert any(x["ruta"] == str(proj) for x in resumen)  # un proyecto por fila (sin git: rama None)
    srv.shutdown()

print("OK: todas las pruebas pasan")
