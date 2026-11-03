# Atril

Visor y editor local de proyectos y archivos, con pestañas, buscador y un chat de IA que gasta pocos tokens.
Todo corre en tu ordenador: un servidor pequeño en Python (solo biblioteca estándar, sin instalar nada) y una ventana web.

## Qué hace

- **Explorador** de proyectos y archivos sueltos, con estado de git y pestañas como en VS Code.
- **Leer** casi cualquier formato: Markdown, código, tablas (CSV, JSON…), HTML, Word, PDF, imágenes, audio, vídeo y letras.
- **Editar**:
  - texto y código (CodeMirror), conservando la codificación y los saltos de línea;
  - Word: texto, negrita, cursiva, subrayado, color e imágenes;
  - imágenes: girar, voltear, recortar, cambiar tamaño, brillo y contraste;
  - PDF: añadir texto, resaltar, girar, mover y borrar páginas.
- **Historial de cambios** (↶ ↷) en disco: sobrevive a guardar y cerrar, y se borra solo a los N días.
- **Buscador** en nombres y contenido (SQLite FTS5), también dentro de PDF y Word.
- **Consola** para ejecutar scripts y las pruebas del proyecto.
- **Chat de IA** con Claude Code, Codex o Gemini CLI usando tu propia suscripción. Atril adjunta solo lo necesario (el archivo abierto, las páginas pedidas de un PDF, una selección) y nada se envía sin que pulses Enviar.
- Copias de seguridad: `.bak` la primera vez que se guarda, recuperación de lo no guardado y «Deshacer» de los cambios de la IA.

## Requisitos

- **Python 3.10 o más nuevo**.
- **Un navegador Chromium** para la ventana y para crear PDF: Microsoft Edge (viene con Windows), Google Chrome, Chromium o Brave. Sin ninguno, Atril se abre en tu navegador de siempre.
- Internet la primera vez que se abre un PDF o un Word: sus visores se cargan de una CDN (ver [TERCEROS.md](TERCEROS.md)).
- Opcional, para el chat: [Claude Code](https://docs.anthropic.com/claude-code), [Codex](https://github.com/openai/codex) o [Gemini CLI](https://github.com/google-gemini/gemini-cli).

## Instalar y abrir

Descarga el repositorio (botón **Code → Download ZIP** o `git clone`) y:

| Sistema | Cómo abrirlo |
|---|---|
| **Windows** | Doble clic en `atril.pyw`. Arrastra archivos sobre él para abrirlos. |
| **macOS** | Doble clic en `atril.command` (la primera vez: clic derecho → Abrir). |
| **Linux** | `./atril.sh` (o `python3 atril.pyw`). |

Para usarlo como servidor sin ventana: `python3 atril.pyw --sin-ventana` y abre `http://127.0.0.1:8765/`.

Estado: probado en **Windows 10** y **Linux** (Debian, Python 3.12). En **macOS** está preparado pero aún sin probar: si lo usas en Mac, cuéntanos cómo va.

## Tus datos

- `config.json`: tus proyectos y ajustes.
- `historial/`: conversaciones, índice de búsqueda, recuperación y versiones.

Los dos se crean junto a `atril.pyw` y **no** se suben al repositorio (`.gitignore`). Atril solo sirve los archivos de las carpetas que añades y solo escucha en `127.0.0.1`.

## Para desarrollar

- `python3 test_atril.py` → «OK: todas las pruebas pasan».
- Diseño y decisiones: [implementacion_atril.md](implementacion_atril.md) · formatos: [formatos_atril.md](formatos_atril.md) · diario de cambios: [bitacora.md](bitacora.md).
- Normas del proyecto: [reglas.md](reglas.md).

## Licencia

[MIT](LICENSE). Las bibliotecas que usa la ventana tienen sus propias licencias: [TERCEROS.md](TERCEROS.md).
