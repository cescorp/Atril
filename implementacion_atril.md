# Implementación de Atril
Atril es un visor local con pestañas para leer, editar y ejecutar archivos de muchos proyectos, y pedir cambios a Claude, Codex o Gemini gastando los mínimos tokens.

## Problema que resuelve
- El chat de las IAs es difícil de leer con textos largos.
- Se trabaja en muchos proyectos (Laravel, Python, .bat, PowerShell, documentos) y archivos sueltos en distintas ubicaciones.
- Los chats se quedan sin contexto y hay que abrir otro y volver a explicar todo.

## Principios
1. **Mostrar nunca usa IA.** Markdown, Word, PDF, HTML y código se muestran en local: 0 tokens.
2. **La IA ve lo mínimo y devuelve solo el cambio.** Nunca el documento entero ida y vuelta.
3. **La memoria vive en archivos `.md` del proyecto, no en el chat.** Cualquier chat nuevo, con cualquier IA, retoma el trabajo.
4. **Nada se instala ni se ejecuta sin acuerdo explícito.**
5. **Se trabaja sobre los archivos originales**, sin copias para descargar.

## Interfaz

```
┌──────────────────┬──────────────────────────────────┬─────────────┐
│ PROYECTOS        │ [ESTADO] [web.php] [▶ Consola]   │ CHAT        │
│ ✅ mi-web     │                                  │ IA: Gemini  │
│ ⚠️ bot-whatsapp  │   vista previa / editor          │ Alcance:    │
│    Sin reglas    │                                  │  selección  │
│ 📌 SUELTOS       │                                  │ ≈ 320 tok   │
│   backup.bat     │                                  │             │
└──────────────────┴──────────────────────────────────┴─────────────┘
```

### Estilo (inspirado en Obsidian, 2026-11-01)

```
┌──┬────────────────────────┬────────────────────────────────────────────────────┐
│📁│ [+proy][+suelto][plegar]│ [web.php ✕] [bitacora.md ✕] [+]                    │
│🔍│ PROYECTOS              ├────────────────────────────────────────────────────┤
│>_│ › mi-web  ⚠️ 1      │ ←  →     mi-web / routes / web.php    [✎]  [⋮]  │
│✦ │   │ › routes           │                                                    │
│  │   │ │  web.php         │   documento (letra de libro, ancho de lectura)    │
│⚙ │ 📌 SUELTOS             │                                  utf-8 · CRLF · …  │ ← barra de estado
└──┴────────────────────────┴────────────────────────────────────────────────────┘
```

- **Cinta de iconos:** 📁 mostrar/ocultar explorador · 🔍 Buscar (futuro) · >_ Consola (paso 4) · ✦ IA (paso 5) · ⚙ Ajustes (futuro).
- **Árbol:** chevrons ›, líneas guía verticales, grises neutros, acento morado.
- **Cabecera:** ← → historial (también Alt+← / Alt+→), migas proyecto / carpeta / archivo, ✎ Editar o 📖 volver a lectura, ⋮ menú (ver fuente, vista previa, descartar, mostrar en carpeta, copiar ruta).
- **Columnas redimensionables** (2026-11-02): arrastrar el borde de la barra lateral o del panel de IA (180–600 px; el documento nunca baja de 300 px). Doble clic en el borde: ancho original. Los anchos se recuerdan. La consola cambia de altura desde su borde superior.
- **Mostrar/ocultar paneles laterales:** ◧ al inicio y ◨ al final de la barra de pestañas (siempre visibles), o **Ctrl+B** (barra lateral) y **Ctrl+J** o **Ctrl+Alt+B** (panel de IA). También ◨ en la cabecera de la IA y 📁 / ✦ en la cinta. **Ctrl+G**: ir a la línea (editor y vista de código).
- **Vista Git** (⎇ en la cinta o **Ctrl+Shift+G**): repositorio y rama, ↓↑ commits por traer/subir, mensaje y Commit (Ctrl+Enter; sin nada preparado, ofrece preparar todo), listas Conflictos · Preparados · Cambios con + (preparar), − (quitar) y ↶ (descartar; lo nuevo va a la papelera). Clic en un modificado: comparador «último commit ↔ disco». Menú de la rama: cambiar, crear, fusionar otra en esta, fetch y deshacer el último commit (solo si no está subido). Pull, push, fetch y merge salen en la consola; usan las credenciales de git del usuario (`GIT_TERMINAL_PROMPT=0`: nunca esperan una contraseña). Servidor: `git_overview` y `git_action` (`/api/git/estado`, `/api/git/accion`).
- **⤢ Pantalla completa** en documento, IA y consola: esa zona ocupa toda la ventana. **⤡ o Esc** vuelve exactamente a como estaba justo antes (no al diseño original), porque al ampliar solo se ocultan las demás zonas sin cambiar su estado. Con un diálogo o menú abierto, Esc solo cierra el diálogo.
- **Barra de estado** abajo: codificación, saltos de línea, tamaño, fecha y mensajes ("✓ Guardado").
- Se mantiene la **letra de libro** (Source Serif) en los documentos.

### Pestañas (lógica de VS Code)
- **Un clic** en un archivo lo abre en la **pestaña de vista previa** (título en cursiva). El siguiente clic en otro archivo **la reemplaza**, así no se acumulan.
- La pestaña se **fija** con **doble clic** (en el árbol o en la pestaña) o en cuanto **se modifica** el archivo.
- Solo hay una pestaña de vista previa a la vez. Lo que se abre desde "Añadir sueltos" o tras crear plantillas se abre ya fijo.

### Barra lateral
- **Proyectos:** carpetas reales, no copias.
- **📌 Sueltos:** archivos en cualquier ubicación; solo se guarda su ruta.

### Buscador, archivos abiertos y git en la barra lateral (2026-11-02)

```
🔍 [ arca filisteos            ]        ← busca en nombre y contenido de todos los proyectos
EN EL CONTENIDO · Mi curso
  Sesión 3 – 1 Samuel 4…docx
     …los [filisteos], que la capturan…
  1 & 2 Samuel…pdf · pág. 23            ← clic: abre el PDF en esa página
───────────────────────────────────────
  montaña_narrativa.md            •     ← punto: estado de git (al pasar el ratón: (i))
  **reglas.md**                   •     ← negrita: tiene pestaña abierta
  ▓ 1 & 2 Samuel…pdf ▓            •     ← fondo: la pestaña que estás viendo
✓ Índice al día · 917 archivos          ← abajo a la izquierda; clic: detalles
```

- **Índice (SQLite FTS5, viene con Python):** `historial/indice.db`, fuera de git. Los archivos siguen siendo la fuente: el índice se puede borrar y se regenera solo.
  - Se indexa **todo** lo de los proyectos y sueltos (también los 🔒: el índice es local). Solo se salta la carpeta interna `.git`. Binarios: solo el nombre. Texto: hasta 20 MB por archivo. `.docx`: su texto.
  - **PDF:** los lee la ventana con pdf.js en segundo plano, uno a uno (el más pequeño primero), página por página; el buscador indica la página.
  - En segundo plano al abrir Atril, repasa cada 5 min **solo lo que cambió** (tamaño/fecha) y al momento lo que se guarda o crea desde Atril. Guarda cada 100 archivos: **si se cierra Atril, sigue donde se quedó**.
  - Medido con los proyectos reales: 917 archivos en 39 s la 1.ª vez; la 2.ª pasada sin cambios, 0 s. La base ocupa ≈ 230 MB (sobre todo por la Biblia en JSON).
  - Búsqueda: sin tildes ni mayúsculas, prefijos (`filist` → filisteos), "frases entre comillas"; primero por nombre, luego por contenido con fragmento resaltado. Esc vuelve al árbol.
  - **Conmutadores dentro del cuadro (como VS Code), 2026-11-02:** `Aa` mayúsculas y tildes exactas (apagado por defecto) · 📄 buscar en el nombre · ≡ buscar en el contenido. 📄 y ≡ no se apagan los dos a la vez; se recuerdan al reabrir. Con `Aa`, cada palabra debe aparecer tal cual se escribió (en el contenido se comprueba sobre el texto completo, no solo el fragmento).
- **Límite de tokens por mensaje** también en ⚙ Ajustes (grupo IA): es el mismo valor que en «Conectar IA»; cambiarlo en uno lo cambia en el otro.
  - **Estado abajo a la izquierda** (⟳ indexando n / total · leyendo PDF · ✓ al día); clic → modal con fase, progreso, archivo actual, PDF pendientes y páginas leídas, recuento por estado y por tipo, errores y tamaño de la base.
- **Pestañas en el árbol:** negrita = abierta; cursiva = vista previa; fondo = la que se ve. Al cambiar de pestaña, el árbol **despliega sus carpetas y se desplaza** hasta el archivo.
- **Git por archivo:** un `git status` por repositorio (caché 10 s). Punto: 🟢 sin cambios · 🟠 modificado · 🔵 nuevo · 🔴 conflicto · ⚪ gris ignorado · **blanco con borde negro: no está en git**. El estado aparece al pasar el ratón.
- **(i) Información** (aparece al pasar el ratón, en lugar del punto): ruta, tamaño, líneas y palabras, tipo, codificación, fechas de creación, modificación y acceso, atributos; del documento: autor, título, fechas (Word/Excel/PowerPoint), páginas y programa (PDF), dimensiones (PNG/JPG/GIF); de git: estado, repositorio, rama, último commit, nº de commits del archivo y quién lo añadió; estado en el índice.
  - Windows no guarda el autor de un archivo de texto: solo sale de los documentos que lo llevan dentro y de git.

### Nuevo archivo, nueva carpeta y recuperación (2026-11-02)

```
[📄+][📁+][+][⇅][◧]                      ← nuevo archivo · nueva carpeta · añadir proyecto/sueltos · plegar · ocultar
▾ Mi curso           ← carpeta elegida (barra morada a la izquierda)
    [ nuevo.md            ] ↵            ← se escribe el nombre aquí mismo; Esc cancela
[nuevo 1 ●] [reglas.md ●]                ← Ctrl+N: pestaña sin guardar (como Notepad++)
```

- **Nuevo archivo / nueva carpeta:** en la carpeta elegida (clic en una carpeta), si no, en la del archivo abierto, si no, en el primer proyecto. También en el ⋮ de cada proyecto («… aquí»). El formato sale de la extensión; los de texto se abren ya en edición; `.docx` crea un Word vacío. Nunca sobrescribe.
- **Ctrl+N → «nuevo 1»:** pestaña sin nombre ni archivo; sobrevive a cierres y reinicios. Guardar (Ctrl+S) pide nombre y carpeta.
- **Recuperación como Notepad++:** lo no guardado se copia a `historial\recuperacion\` 2 s después de dejar de escribir (como máximo cada 10 s; ajustable). El archivo original no se toca hasta Ctrl+S. Escritura atómica (archivo aparte + reemplazo + fsync): un corte de luz no deja copias rotas. No va en Temp de Windows (el liberador lo vacía).
  - Al abrir Atril: reabre las pestañas con su texto y ● y avisa «Se recuperó…». Si el archivo cambió en disco después de la copia: «Usar mi versión recuperada / Usar la del disco / Ver las dos». Si el archivo ya no existe, el texto se abre como «nuevo N».
  - Guardar, descartar o cerrar la pestaña borra su copia. Al cerrar Atril se guarda lo pendiente al instante.
  - También se conserva lo que se estaba escribiendo en el chat.
  - Probado: con una copia de «nuevo 1», Atril la reabrió en el editor con su texto y el aviso.
- **🔍 de la cinta:** lleva al buscador de la barra lateral. **⚙ Ajustes:** los valores que antes estaban fijos en el código, por grupos (General, Índice, Bitácora, Git, IA, Recuperación, Editor y lectura), con rango y valor por defecto; se guardan en `config.json` («Restablecer valores» vuelve a los de fábrica; el puerto se aplica al reabrir).
- **Modal (i):** botones de copiar agrupados — Copiar nombre · Copiar ruta · Copiar ruta relativa (al proyecto) — y aparte Mostrar en carpeta / Cerrar.

### Explorador para añadir (botón + de Proyectos o de Sueltos)

```
┌ Añadir a Atril ─────────────────────────────────────┐
│ [↑] Este equipo › G: › proyectos        [C:][G:][H:] │
├─────────────────────────────────────────────────────┤
│ 📁 mi-web      Laravel · git   ✅ ya añadido      │
│ 📁 bot-whatsapp   Node · git                         │
│ 📁 node_modules   (atenuada)                         │
│ 📄 notas.md                                    [ ]   │
├─────────────────────────────────────────────────────┤
│ Seleccionada: G:\proyectos\bot-whatsapp              │
│ Quedará con avisos: ⚠️ Sin reglas · ⚠️ Sin bitácora  │
│ [Añadir como proyecto] [Añadir 1 suelto] [Cancelar]  │
└─────────────────────────────────────────────────────┘
```

- Abre en la última ubicación usada; la primera vez, en "Este equipo".
- Doble clic entra en una carpeta, un clic la selecciona; sin selección, se añade la carpeta actual.
- Tipo detectado por archivos: `artisan` → Laravel, `composer.json` → PHP, `package.json` → Node, `requirements.txt`/`pyproject.toml`/`setup.py` → Python, `.git` → git.
- Marca "✅ ya añadido" y "dentro de un proyecto" para evitar duplicados.
- **Seguridad:** el explorador lista **nombres** en cualquier unidad; **leer contenido** sigue limitado a lo añadido.
- Reemplaza al diálogo de Windows (tkinter), que a veces aparecía detrás de la ventana.

### Avisos por proyecto (0 tokens, solo comprueba si existen archivos)

| Aviso | Cuándo aparece |
|---|---|
| ⚠️ Sin reglas | Falta `reglas.md` |

`AGENTS.md`, `CLAUDE.md` y `GEMINI.md` son **opcionales** (2026-11-01): solo sirven si se trabaja con esa IA directamente dentro de la carpeta del proyecto. Atril no los exige ni avisa de ellos, y en la plantilla aparecen desmarcados.
| ⚠️ Sin bitácora | Falta `bitacora.md` |
| 🟡 Bitácora grande | Más de 200 líneas |
| ⏳ Sin actividad | Última entrada con más de 30 días (opcional, pendiente de decidir) |
| ✅ | Todo en orden |

Al hacer clic aparece el botón **"Crear desde plantilla"**. Solo se crean archivos si el usuario lo pulsa.

### Vistas previas

| Tipo | Cómo se ve |
|---|---|
| `.md`, `.txt` | Documento con formato, estilo Word |
| `.docx` | Documento con formato (solo lectura; botón "Abrir en Word") |
| `.html`, `.svg`, imágenes, `.pdf` | Renderizado real (`.pdf` solo lectura) |
| `.php`, `.blade.php`, `.py`, `.bat`, `.ps1`, `.js`, `.css`, `.sql`, `.json`, `.yaml` | Código con colores y números de línea |
| App en marcha (Laravel, Flask…) | Pestaña con la URL `localhost` |

Clasificación completa de ~380 formatos en 5 niveles, regla universal para extensiones desconocidas y archivos sensibles 🔒 (nunca se envían a la IA): ver [formatos_atril.md](formatos_atril.md). Lista de los 256 viables sin instalar nada: [formatos_viables.txt](formatos_viables.txt).

## Memoria por proyecto (archivos `.md`)

```
mi-proyecto/
├─ AGENTS.md      → punto de entrada corto (Codex lo lee por defecto)
├─ CLAUDE.md      → una línea: @AGENTS.md
├─ GEMINI.md      → una línea: @AGENTS.md
├─ reglas.md      → normas estables del proyecto
└─ bitacora.md    → qué se hizo, cuándo y por qué (nuevas arriba)
```

Plantilla de `AGENTS.md`:

```markdown
# Proyecto: <nombre>
<Una frase: qué es y con qué tecnología.>

## Al empezar
1. Lee `reglas.md` completo.
2. Lee solo las últimas 10 entradas de `bitacora.md`.
3. Si alguno no existe, créalo con la plantilla.

## Al terminar una tarea
- Añade una entrada al principio de `bitacora.md`:
  `## AAAA-MM-DD · título` + 2–4 líneas (qué, por qué, pendiente).
- Si se acordó una norma nueva, añádela a `reglas.md`.
- Si `bitacora.md` pasa de 200 líneas, mueve las antiguas a `bitacora/AAAA.md`.
```

Reglas:
- `AGENTS.md` debe ser corto: se carga en cada chat.
- La IA lee solo las últimas 10 entradas de la bitácora.
- Nunca guardar claves, IPs ni datos de clientes en estos archivos.

**Por qué `.md` y no base de datos:** las tres IAs leen `.md` sin código extra, viajan con el proyecto (git, GitHub) y se pueden leer en cualquier editor u Obsidian. Una base de datos (SQLite) solo como índice de búsqueda en el futuro, regenerable desde los `.md`.

## Edición de archivos
- Se guarda en la **ruta original**.
- **Respaldo:**
  - Proyecto con git → sin copia (git es el respaldo; se puede ver el diff).
  - Sin git → antes del primer guardado de la sesión se crea `nombre.ext.bak` en la misma carpeta.
  - Se usa `.bak` al final para que Laravel, Python o Windows nunca carguen ni ejecuten la copia.
- **Aviso de conflicto:** si el archivo cambió en disco desde que se abrió, se avisa antes de sobrescribir.
- **Formato original:** se conservan la codificación (ANSI, UTF-8, BOM) y los saltos de línea (CRLF).
- **Solo rutas permitidas:** el servidor solo lee y escribe en carpetas y archivos añadidos por el usuario.

## Ejecución de scripts y pruebas (0 tokens)

| Tipo | Cómo se ejecuta |
|---|---|
| `.py` | Python; usa el `.venv` del proyecto si existe |
| `.bat`, `.cmd` | `cmd`, leyendo la salida en la codificación de Windows |
| `.ps1` | PowerShell con permiso solo para esa ejecución, sin tocar la configuración del sistema |
| Pruebas del proyecto | Botón **Probar** (`php artisan test`, `pytest`…), comando leído de `AGENTS.md` o `config.json` |

- La salida aparece en vivo en una pestaña **Consola**, con el código de salida y la duración.
- **Siempre se confirma** el comando y la carpeta antes de ejecutar.
- Botón **Detener** y límite de tiempo.
- Línea de entrada para scripts con `pause` o preguntas S/N.
- Se ejecuta en la carpeta del propio script.
- **🤖 Explicar error:** envía a la IA solo las últimas ~40 líneas de salida y la parte del script relacionada (~500 tokens).

## Chat con IA
- **IAs:** Claude y Codex (de pago) y Gemini (gratis), mediante sus CLIs oficiales y con el login de cada uno, sin API keys.
- **Reparto sugerido:** Gemini para borradores, resúmenes y formato; Codex o Claude para código y lógica.
- **Destino de la respuesta:** modificar la pestaña actual, abrir una pestaña nueva o responder solo en el chat.

### Conectar IA (primera parte del paso 5)

```
┌──────────────────────────────────────────────────────────────────────────┐
│ Atril     IA:  [● Claude]  [⚠ Codex]  [○ Gemini]            [Conectar IA] │
├──────────────┬───────────────────────────────────────────────────────────┤

┌ Conectar IA ──────────────────────────────────────────────────────────┐
│ Claude   ● conectada     v2.1   carga fija medida: ≈ 4.200 tok  [Probar]│
│ Codex    ⚠ sin sesión    v0.4                         [Iniciar sesión] │
│ Gemini   ○ no instalada                                [Cómo instalar] │
├───────────────────────────────────────────────────────────────────────┤
│ IA predeterminada: [Gemini ▾]    Límite por petición: [2.000] tokens  │
└───────────────────────────────────────────────────────────────────────┘
```

- ● conectada · ⚠ instalada sin sesión · ○ no instalada. Se comprueba al abrir Atril, sin gastar tokens (versión del programa).
- **Cómo instalar:** muestra el comando para copiar; Atril no instala nada por su cuenta.
- **Iniciar sesión:** abre una consola con el login oficial (`codex login`, `claude`, `gemini`); después, **Comprobar**.
- **Probar:** envía "responde OK", tras confirmar, y mide la carga fija real de tokens de esa IA (si el CLI informa del consumo). Resuelve con datos la duda pendiente sobre los CLIs.
- Atril nunca guarda contraseñas ni claves: cada CLI guarda su propia sesión.

Decidido (2026-11-01):
- Solo CLIs (suscripciones); claves API solo si la carga fija medida resulta alta.
- Instalar: solo se muestra el comando para copiar.
- Sin barra superior: el estado está en el panel de IA y como punto de color en ✦ de la cinta.

### Panel de IA: un solo chat (rehecho el 2026-11-02)

El primer diseño (modos Rápido/Conversación, Alcance, Destino y adjuntar a mano) resultó **demasiado complicado** y se sustituyó por un único chat en el que Atril prepara el contexto solo.

```
│ ✦ IA   [● Claude ▾] [Conectar]                    │
│ 📜 Reglas: Mi curso · 9 reglas                 │ ← clic: modal de reglas
│ [conversaciones guardadas ▾] [Nueva] [Borrar]      │
│  …conversación (se recuerda)…                      │
│ Se enviará: 📄 1 & 2 Samuel.pdf · pág. 40 (abierto) ✕│ ← Atril lo detecta solo, sin IA
│             📄 montaña_narrativa.md   ≈ 4.500 tok ✕ │
│             + Otro archivo                          │
│ [ lee la página 40 y usa montaña narrativa… ]       │
│ ≈ 7.900 tokens                          [Enviar ↵]  │
```

- **Contexto automático (Python/JS, 0 tokens):**
  - El **archivo abierto** se incluye siempre (si es texto, su contenido; si es `.docx`, su texto).
  - **PDF:** si el mensaje dice «página 40», «páginas 27 a 35», «pág. 27-30» o «página 27 en adelante» (10 páginas), se extraen **solo esas páginas** con pdf.js (numeración del visor). Si no se indican, aparece el aviso «di qué páginas».
  - **Archivos nombrados** en el mensaje («montaña narrativa», «preguntas y datos de contexto», o el nombre completo) se buscan en la carpeta del proyecto y se añaden. Coincidencia por palabras seguidas en común, sin tildes ni mayúsculas; un nombre escrito completo no arrastra a sus parecidos.
  - **Texto seleccionado** en el documento.
  - Todo aparece en **«Se enviará»** con sus tokens; ✕ lo quita, ↺ lo devuelve. **+ Otro archivo** (con buscador) para lo que no se nombre.
- **Memoria:** conversación continua guardada en `historial/conversaciones/`. Con Claude continúa su sesión (`--resume`): reglas y archivos se envían **una sola vez** («ya en la conversación») y lo anterior va en caché. Un archivo de texto que cambió se vuelve a enviar. Con otras IAs se reenvía todo en cada turno.
- **Respuestas que Atril ejecuta de forma segura** (la IA no tiene herramientas):
  - `<<<ARCHIVO nombre.md … ARCHIVO>>>` → Atril **crea el archivo** en la carpeta del proyecto (nunca sobrescribe: añade « (2)») y **lo abre** en una pestaña. Probado con Claude: «lee la página 40… muéstramelo en un archivo .md» → `preguntas_pagina_40.md` (≈ 1.550 tokens).
  - Bloques `BUSCAR / REEMPLAZAR` → cambios al archivo que estaba abierto, en rojo/verde con **Aplicar** (solo si cada texto aparece una vez); se guardan con Ctrl+S.
  - **✓ Verificar citas** (si el proyecto tiene `verificar_citas.py`): extrae las referencias (editables), ejecuta el script en la consola y deja el resultado en el chat para enviarlo.
- **Crear cualquier formato y abrirlo solo** (2026-11-02): la IA escribe el contenido; Atril lo convierte sin IA y lo abre en una pestaña.

  | Pides | Cómo lo crea Atril |
  |---|---|
  | `.md`, `.txt`, `.csv`, `.html`, `.json`, `.svg`, `.py`, `.bat`, `.ps1`, `.sql`… | Texto UTF-8 tal cual |
  | `.docx` | Markdown → HTML (marked) → Word con Python estándar: títulos, negrita, cursiva, código, listas, citas, tablas; A4; sin imágenes |
  | `.pdf` | Markdown → HTML con la letra de lectura → **Edge sin ventana** lo imprime (A4, números de página «n / total»); ≈ 2,5 s |
  | `.xlsx`, `.pptx`, `.doc`, imágenes… | Se rechaza con aviso y se sugiere `.csv` o `.docx` |

  Probado con Claude: «crea un archivo Word con las preguntas en una tabla» → `preguntas_pagina_47.docx` con su tabla (≈ 1.680 tokens).
- **Cambiar formato y texto de un Word desde el chat** (2026-11-02):
  - **Visor fiel** con `docx-preview` (+ JSZip): colores, fuentes, tamaños, resaltado, bordes de tabla y páginas, como en Word. Antes (mammoth) se perdían los colores; mammoth queda de reserva si no hay internet.
  - Cada mensaje dice a la IA cuál es el **ARCHIVO ABIERTO**; si es `.docx`, también cómo proponer cambios: `<<<DOCX {"buscar": "texto exacto", "color": "rojo"} DOCX>>>` con `color`, `negrita`, `cursiva`, `subrayado`, `tamano` (pt), `resaltado`, `fuente`, `reemplazar` (conserva el formato) y `todas`.
  - Atril lo muestra como lista y **solo cambia el Word al pulsar «Aplicar al Word»**: toca únicamente los fragmentos de texto afectados (los parte si hace falta), conserva el resto del archivo y sus declaraciones; **todo o nada** (si un texto no aparece, no se toca nada); `.bak` la primera vez si no hay git; escritura de golpe; si el Word está abierto en Microsoft Word, avisa en lugar de escribir. Después el visor se recarga.
  - Probado con una **copia** de «Exposición – 2 Samuel 6:1 – 7:29.docx»: Claude propuso el bloque (≈ 4.800 tokens), Atril lo aplicó, **Microsoft Word abrió el archivo sin errores con el título en rojo**, y el visor de Atril lo muestra en rojo.
  - No hace: márgenes, columnas, encabezados/pies, insertar imágenes o tablas nuevas (para eso, generar un `.docx` nuevo).
- **Arrastrar al chat** (2026-11-02): soltar en el panel de IA un archivo del árbol o una pestaña lo adjunta con su ruta (vinculado); desde el Explorador de Windows, solo su contenido («desde Windows · solo lectura»: la IA lo lee pero no puede aplicarle cambios). Texto, `.docx` (texto con mammoth) y PDF (cuadro «de … a …» si el mensaje no dice qué páginas). Las carpetas no se adjuntan.
- **Archivos sensibles** (🔒 `.env`, claves, `.npmrc`, `.netrc`, `id_rsa`, `credentials.json`, `wp-config.php`, `.ppk`, `.kdbx`…): ajuste «Permitir adjuntar y enviar a la IA archivos sensibles», **activado por defecto** (decisión del usuario: son archivos locales). Copiar, buscar y editar siempre estuvieron permitidos. Desactivado, el servidor rechaza su envío aunque la interfaz fallara.
- **Sin doble paso** (2026-11-02): ajuste «Pedir confirmación antes de aplicar los cambios que propone la IA», **apagado por defecto**. Apagado, los cambios de Word y de texto se aplican solos al llegar la respuesta y la tarjeta muestra «✓ Aplicado» con **↩ Deshacer** (Word: vuelve a la copia exacta guardada en `historial/deshacer` antes de cada cambio, se conservan 100; texto: Ctrl+Z en el editor). Encendido, como antes: botón «Aplicar».
- **Envío inmediato:** al pulsar Ctrl+Enter el mensaje sale del cuadro y aparece en el chat al momento; la preparación de adjuntos sigue después. Si se cancela por el límite de tokens o falla, el texto vuelve al cuadro.
- **Carga fija de cada IA:** solo cuenta la medida con el modo mínimo actual; las medidas antiguas (≈ 27.000 tokens del modo completo) se ignoran. Conviene pulsar **Conectar → Probar** otra vez.
- **🔗 Chat vinculado a la pestaña** (2026-11-02, encendido por defecto; el estado se recuerda):
  ```
  [🔗 Exposición…docx] [conversaciones de esta pestaña ▾] [Nueva] [🧹] [🗑]
  ```
  - Cada pestaña tiene **su conversación**: al volver a ella **reaparece** (la recordada o, si no, la más reciente vinculada a ese archivo); una pestaña sin chat muestra uno **nuevo y vacío**. El desplegable muestra solo las de esa pestaña; «Nueva» deja la anterior en el desplegable.
  - El vínculo se guarda en la propia conversación (`vinculo` en `historial/conversaciones/`), así que sobrevive a cierres y reinicios. El borrador del cuadro también va por pestaña.
  - **🧹 Limpiar conversación** (con confirmación): vacía mensajes, adjuntos y la sesión de Claude, sin perder el vínculo. **🗑** la borra.
  - Una pestaña «nuevo N» guardada con nombre se lleva su chat al archivo.
  - **🔗 apagado:** chat general que no cambia con la pestaña; el desplegable muestra todas (las vinculadas con «🔗 nombre»).
  - Probado en Edge sin ventana: en A.md reaparece su conversación; en B.md, chat vacío.
- **🤖 Explicar error** (consola): envía al chat solo las últimas ~40 líneas, el comando y el código de salida.
- Los CLIs se ejecutan en una **carpeta neutra**; **reglas.md** del proyecto se envía siempre; 🔒 nunca se envía; contador y límite de tokens antes de enviar.
- **Modal de reglas:** Markdown a la izquierda, vista previa (letra de libro) a la derecha, «+ Nueva regla» con sección, contador de reglas y tokens (aviso si > 300). Se eligió **Markdown y no texto enriquecido**: la IA lee exactamente lo escrito, sin cambios fantasma en git ni librerías extra.

### Alcance (ahorro de tokens)

| Modo | Se envía | La IA devuelve | Coste aprox. (doc de 5.000 palabras) |
|---|---|---|---|
| **Selección** (por defecto) | Texto seleccionado + título de su sección | Solo ese fragmento | ~300–600 |
| Sección | Índice + sección actual | Solo esa sección | ~1.500 |
| Documento (con aviso) | Todo | Solo los cambios (buscar → reemplazar) | ~8.000 |

- Contador de tokens antes de enviar; por encima de un límite, pide confirmación.
- Sin historial infinito: cada petición es independiente.

## Configuración
- `config.json`: proyectos, archivos sueltos, pestañas abiertas, límites de tokens y ruta de Obsidian.
- **Obsidian opcional:** si se configura la ruta, aparece la opción "enviar nota a Obsidian". La ruta nunca va en el código que se sube a GitHub.

## Tecnología y arranque
- **Servidor:** Python, solo la biblioteca estándar (ya instalado, sin paquetes).
- **Interfaz:** HTML + JavaScript. El navegador muestra PDF, imágenes, audio y video; las librerías del nivel 3 son JS desde CDN.
- Descartados: Electron (pesado, Node), Tauri (compilar Rust), Laravel (excesivo para local), C# escritorio (sin Markdown/PDF nativos).
- **Arranque:** doble clic en `atril.pyw` (sin consola) → abre una ventana de **Edge en modo aplicación** (`msedge --app=…`), que parece un programa normal.
- Al cerrar la ventana, el servidor se apaga solo.
- **Posición y tamaño de la ventana** (2026-11-02): se guardan en `config.json` mientras se usa (cada 2 s si cambian) y Atril abre la siguiente vez con `--window-position` / `--window-size`. Si Edge ignorara esas opciones (pasa si ya había otra ventana de Edge abierta), la propia página corrige tamaño y posición al cargar.
- Abrir archivos: botón **+** de Sueltos (diálogo de Windows) o arrastrarlos sobre el icono de `atril.pyw`. Soltarlos dentro de la ventana no sirve: el navegador no entrega la ruta real, y sin ella no se puede editar el original.
- Seguridad local: solo escucha en `127.0.0.1`; las llamadas a la API exigen una cabecera propia para que ninguna web externa pueda usarla.

## Estructura del proyecto

```
Atril/
├─ atril.pyw          → servidor local (Python stdlib) y arranque de la ventana
├─ index.html         → interfaz: proyectos, pestañas, vistas (consola y chat en pasos 4 y 5)
├─ test_atril.py      → prueba automática
├─ plantillas/        → AGENTS.md, CLAUDE.md, GEMINI.md, reglas.md, bitacora.md
└─ implementacion_atril.md
```

`config.json` (proyectos y archivos sueltos) y `historial/` (respuestas de IA) se crean solos y van en `.gitignore`, porque contienen rutas y textos personales.

## Orden de construcción
1. ✅ **Explorador** (2026-11-01): proyectos, sueltos, pestañas, vistas de niveles 1, 2 y 5 (+ docx), regla universal, 🔒 y avisos. Sin IA. Prueba: `python test_atril.py`.
2. ✅ **Edición** (2026-11-01): editor CodeMirror (colores, números, Ctrl+F, Ctrl+S), guardar en el original, `.bak` una vez por sesión si no hay git, diálogo de conflicto (Recargar / Sobrescribir / Cancelar), misma codificación y saltos de línea, bloqueo si un carácter no cabe en ANSI, vista previa para Markdown y HTML, ● en pestañas con cambios y aviso al cerrar.
3. ✅ **Plantillas** (2026-11-01): los avisos son botones.
   - ⚠️ Sin reglas / Sin bitácora → "Crear desde plantilla": descripción + tecnología detectada, casillas por archivo, vista previa de AGENTS.md. Crea solo lo que falta (nunca sobrescribe; un CLAUDE.md o GEMINI.md propio solo recibe un aviso).
   - 🟡 Bitácora grande → "Archivar": quedan las 20 entradas más recientes; las antiguas van a `bitacora/AAAA.md` según la fecha de su título (las sin fecha se quedan). Nada se borra.
   - No encontrado → "Quitar de Atril".
   - Plantillas editables en `plantillas/`, con marcadores `{{proyecto}}`, `{{descripcion}}`, `{{tecnologia}}`, `{{fecha}}`.
4. ✅ **Consola** (2026-11-01):
   - ▶ en la cabecera de archivos ejecutables (`.py`, `.pyw`, `.bat`, `.cmd`, `.ps1`, `.vbs`, `.js`, `.php`, `.sh`). Desactivado con el motivo si falta el programa (Node, PHP, Git Bash).
   - Confirmación con comando y carpeta + casilla "No volver a preguntar (hasta cerrar Atril)". Con cambios sin guardar: "Guardar y ejecutar".
   - Panel abajo (como VS Code), redimensionable, con >_ en la cinta: una sub-pestaña por ejecución (● / ✓ / ✗), errores en rojo, línea de entrada para `pause`/S/N/`input()`, Detener (mata también los procesos hijos), Repetir, Limpiar, "Abrir en consola de Windows" para programas interactivos, "🤖 Explicar error" desactivado hasta el paso 5.
   - Codificación de salida: UTF-8 para Python/Node/PHP/bash; la de consola de Windows (OEM) para `.bat`, `.ps1`, `.vbs`. Python usa el `.venv` del proyecto si existe.
   - ⋮ de cada proyecto → **Ejecutar pruebas**: detecta `php artisan test` (artisan), `npm test` (package.json con script test) o `pytest` (pytest.ini o carpeta tests); la primera vez se puede corregir y se recuerda en `config.json`.
   - Al cerrar la ventana de Atril se detiene todo lo que esté en ejecución.
5. ✅ **IA** (2026-11-01): Conectar IA (estado, instalar, iniciar sesión, Probar con medición de carga fija, IA predeterminada y límite), panel de IA con reglas, alcance, destino, contador, cambios propuestos, Otra IA, Nuevo archivo, Explicar error y modal de reglas. **Pendiente de probar con los CLIs reales instalados** (la lectura de su salida está probada con ejemplos de su formato).

## Pendiente de decidir
- [ ] Aviso "⏳ Sin actividad" (30 días): ¿se incluye?
- [x] Carga fija de Claude medida (2026-11-01, "Responde solo: OK"):

  | Modo de Claude CLI | Tokens de entrada |
  |---|---|
  | `claude -p` normal (herramientas, MCP, CLAUDE.md global, hooks y plugins) | 41.091 |
  | + `--tools "" --strict-mcp-config --disable-slash-commands --system-prompt …` | 3.321 |
  | **+ `--setting-sources ""`** (sin ajustes, hooks ni plugins de usuario) — **el que usa Atril** | **851** |
  | `--bare` | no sirve con suscripción (pide clave API) |

  Prueba real de "Modificar" con Claude: 1.167 de entrada + 44 de salida, bloque BUSCAR/REEMPLAZAR correcto.
- [ ] Medir Gemini (con clave API) y Codex cuando estén conectados; buscar sus equivalentes de modo mínimo si la carga es alta.
- Gemini CLI ya no admite "Sign in with Google" para cuentas personales (2026-11): usar clave API (`GEMINI_API_KEY`).
- [ ] Nivel 4 de formatos: ¿instalar LibreOffice y/o ffmpeg más adelante?
- [ ] "Abrir con Atril" en el menú contextual del Explorador (requiere entrada en el registro del usuario).

## Prototipo
El prototipo inicial (`server.py` con chat que enviaba el documento entero) se reemplazó por `atril.pyw` en el paso 1. El chat se rehará en el paso 5 con las reglas de ahorro.

Origen: Atril · 2026-10-31
