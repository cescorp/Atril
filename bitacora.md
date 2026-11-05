# Bitácora de DeskLens
Entradas nuevas arriba. Formato: `## AAAA-MM-DD · título` + 2–4 líneas (qué, por qué, pendiente).

## Cómo continuar (para la próxima IA)
- **Qué es DeskLens:** visor local con pestañas para leer, editar, ejecutar y buscar archivos de varios proyectos, con un chat de IA (Claude/Codex/Gemini por sus CLIs) que gasta pocos tokens. Diseño completo y decisiones en `implementacion_desklens.md`; formatos en `formatos_desklens.md`.
- **Archivos:** `desklens.pyw` (servidor Python, solo biblioteca estándar), `index.html` (toda la interfaz), `test_desklens.py` (prueba: `python test_desklens.py` → «OK: todas las pruebas pasan»), `plantillas/`. `config.json` e `historial/` (conversaciones, índice, recuperación) están fuera de git.
- **Arrancar:** doble clic en `desklens.pyw` (abre Edge en modo aplicación). Tras cambiar `desklens.pyw` hay que cerrar y reabrir DeskLens; tras cambiar solo `index.html`, basta Ctrl+R.
- **Cómo trabaja el usuario:** escribe en español. **Antes de construir algo nuevo, dibujarlo en texto y esperar su «ok».** No instalar nada sin acuerdo. Ahorrar tokens. Prefiere lo simple: rechazó un panel de IA con modos (ver 2026-11-02).
- **Para verificar sin tocar su DeskLens:** levantar `desklens.Handler` en el puerto 8799 con `CONFIG`, `CONV_DIR`, `RECOVERY_DIR` e `INDEX_DB` en una carpeta temporal y hacer captura con Edge sin ventana (`--headless=new --screenshot`). Así se probó cada paso. Ojo: en Windows dos servidores pueden escuchar el mismo puerto sin error; si hay otra sesión probando, usa otro puerto.

## 2026-11-04 · Proyectos con el mismo nombre
Captura del usuario: dos «hesis» en carpetas distintas se confundían. (A) Si dos proyectos se ven con el mismo nombre, a su lado va en gris lo justo de la carpeta que los contiene para distinguirlos, desde el final («…\Trabajo» / «…\2025»; la ruta entera si solo cambia la unidad): `project_label`. (B) «✎ Nombre en DeskLens…» en el ⋮ del proyecto: un nombre propio (`config.json` › `nombres`; la carpeta no cambia; vacío = el de la carpeta), y entonces ya no hace falta el lugar. Se ve en el árbol, el selector y el título de Git y «En:» del buscador. «Bitácora grande» usaba 🟡, que en algún Windows sale como un cuadrado vacío: ahora ⚠️ como los demás avisos.

## 2026-11-04 · ＞ Terminal para escribir órdenes
El usuario quería escribir sus propias órdenes (p. ej. `git fetch origin && git log --oneline -1 origin/calidad`). «＋ Terminal» al final de las pestañas de la consola (y «＞ Terminal aquí» en el ⋮ del proyecto): `cmd.exe /d /k` en la carpeta del proyecto con la entrada por la consola (`/api/terminal`, ruta comprobada). `cd` se mantiene; varias líneas pegadas se ejecutan en orden (el cuadro es un textarea: Enter envía, Mayús+Enter salta de línea); ↑↓ historial por terminal; no se oculta sola ni cuenta para el límite de 7 mientras corre. Codificación: `chcp` a la página ANSI (cp1252) y la entrada en ella (si no, `cd año` falla); la salida con `MixedDecoder` (UTF-8 de git/npm/php y, si no lo es, cp1252 de dir/echo). No sirve para programas de pantalla completa (vim, top): para eso, «Abrir en una terminal».
Ojo al probar: el servidor de prueba lanzado desde Git Bash hereda su PATH y `find` es el de Linux (recorrió C:\ hasta detenerlo); DeskLens abierto desde su acceso directo tiene el PATH de Windows.

## 2026-11-04 · Consola: como mucho 7 pestañas
Captura del usuario: las ejecuciones (sobre todo de git) se acumulaban en la consola. Al lanzar una nueva, si hay más de 7 se quitan las terminadas más antiguas; las que siguen corriendo no se quitan nunca.

## 2026-11-04 · Abrir con… y DeskLens en Windows
Menús de archivo (explorador y ⋮ de la pestaña): «↗ Abrir con el programa de Windows» (`os.startfile`; se niega con ejecutables como .bat/.exe/.ps1: eso sería ejecutarlos) y «↗ Abrir con…» (ventana de Windows `OpenAs_RunDLL`). ⚙ Ajustes › «🪟 Abrir desde Windows…»: registra DeskLens en «Abrir con» de las extensiones elegidas y, opcional, «Abrir con DeskLens» en el clic derecho del Explorador; todo en HKCU (sin administrador, `WIN_BASE`), con «Quitar de Windows». «Hacer predeterminado…» abre la ventana «Abrir con» sobre un archivo de ejemplo: Windows 10 exige que el usuario lo confirme. Doble clic con DeskLens ya abierto: la 2.ª instancia pasa los archivos por `/api/abrir_fuera`, la ventana los recoge cada 1,5 s (`/api/pendientes`) como pestañas y se trae al frente (`SetForegroundWindow`); si el DeskLens que corre es antiguo o no tiene ventana, se abre otra como antes. Las pruebas registran en una clave de prueba (`Software\DeskLensPrueba`) y la borran.
Pendiente: probar de verdad en el Explorador (registrar, doble clic en un .txt con DeskLens abierto y cerrado). Ojo: esta sesión encontró `G:\Atril` en la rama `main` (5f1b39a, versión «Atril»); se volvió a `publico` con el ok del usuario.

## 2026-11-04 · La consola de git se oculta sola al terminar bien
Fetch, Pull, Push, Sincronizar, Fusionar…: la consola se ve mientras corre y, si terminó bien, se oculta 1,5 s después (la ejecución queda en su pestaña ✓ y un aviso lo dice). Si falla, o si la consola ya estaba abierta antes, se queda como está.

## 2026-11-04 · Menú de ramas: Pull desde, Push a, clic derecho y ⤵ Fusionar visible
Al ocultar el selector de rama de la derecha en pantalla completa, el menú de la rama (fusionar, pull, push…) quedó inaccesible ahí. Ahora: ⋯ junto a «Ramas de X» y clic derecho en cada rama. Rama actual: Pull, Pull desde…, Push, Push a… (también a una rama nueva), Fetch, Fusionar otra rama…, Nueva rama aquí…, Recuperar guardados…, Deshacer último commit, Archivos ignorados. Otra rama: Cambiar, Fusionar en «actual», Pull y Push sin cambiarse a ella. Nombres de 2–3 palabras; lo que hace cada uno, en el title (el usuario pidió menús cortos). Panel derecho: botón «⤵ Fusionar…» junto a Sincronizar; con una fusión a medias pasa a «⤵ Fusión en curso» con Terminar / Cancelar fusión. Servidor: acciones `pull_desde` (`pull --no-rebase origin x`), `push_a` (`push origin HEAD:x`), `pull_rama` (`fetch origin x:x`, solo avanza), `push_rama` y `cancelar_fusion` (`merge --abort` o `revert --abort`), con pruebas.

## 2026-11-04 · Pestaña 🙈 Ignorados en Git
Junto a «Historial» (y en el menú de la rama): árbol de lo que git ignora, ordenado por peso, con nº de archivos y tamaño por carpeta, total en la pestaña y «Ignorado por» (`.gitignore:línea patrón`, clic: abre ese .gitignore). Aviso ⚠ para lo que está en .gitignore pero git ya seguía. Servidor: `git_ignored` (`status --ignored` con carpetas enteras como una entrada + `check-ignore -v --no-index` en una sola llamada), `folder_size` y `folder_items` (`/api/carpeta/tam` y `/lista`, rutas comprobadas por `denied`). La lista llega enseguida y los tamaños de carpeta se piden 3 a la vez y rellenan la tabla. Una carpeta ignorada porque todo su contenido lo está no tiene regla propia: dice «todo lo que contiene está ignorado».

## 2026-11-04 · Panel de proyecto y ramas más claro
El usuario encontraba confuso el panel izquierdo de Git (Proyectos, Ramas y Remotas iguales y cada rama dos veces). Ahora: el proyecto en un desplegable (el mismo menú de la vista Git, con los sin git al final), su estado en palabras («⎇ pruebas · ↑ 3 commits por subir · 7 archivos sin commit» o «✓ Todo al día con GitHub») y «Ramas de X» con una fila por rama (local y remota juntas): ✓ al día, ↑/↓ N, 💻 solo en tu PC, 💻 sin enlazar, 💻 ya no está en GitHub, ☁ solo en GitHub. Servidor: `ramas_info` (`for-each-ref` con `upstream:track`, en la tanda paralela) y `servicio` (GitHub/GitLab/… por la URL del remoto). En pantalla completa se ocultan los selectores de proyecto y rama de la derecha (están a la izquierda).

## 2026-11-04 · Comparador al instante y ⋮ más fácil de pulsar
«Ver» (y todo lo que abre el comparador) esperaba al historial del archivo y a la librería antes de mostrar nada: ahora el modal se abre ya con «Cargando…» (7 ms) y se rellena al llegar (≈ 260 ms en la prueba); si se cierra mientras carga, no se reabre. El ⋮ de los proyectos y el ✕ de los sueltos tienen zona de clic de 26×22 px con fondo al pasar el ratón (antes solo el carácter).

## 2026-11-04 · Lista de versiones compacta y selectores que no se pegan
Capturas del usuario: con muchos commits la lista llenaba la pantalla (3 líneas por commit y el botón de archivos suelto) y «Hoy» salía como «· ·»; en otro equipo los selectores del comparador se montaban sobre el código. Ahora cada commit son 2 líneas (~39 px): «título · detalle … hora» y «autor … 📄 N archivos ▸» como enlace. Menús: como mucho el 70 % del alto y `.menu>*{flex-shrink:0}` (en una columna flex con scroll las filas con overflow:hidden se aplastaban: eso borraba «Hoy»). `syncHeads` da a la barra de selectores el alto del más alto + 6 px arriba y abajo (antes 40 px fijos; con letra mayor el selector medía 46). Probado simulando letra grande: margen de 6 px.

## 2026-11-04 · Pantalla de Git ajustable y recordada
En pantallas pequeñas todo se amontonaba. Ahora ◧ ⬓ ◨ en la barra ocultan proyectos/ramas, el detalle y commit/cambios; los bordes se arrastran (doble clic: tamaño original); ⤢ amplía el historial o el detalle (Esc o ⤡ vuelve); ✕ oculta el detalle y elegir un commit lo vuelve a mostrar. Todo se recuerda en `desklens.git.disposicion` (anchos, alto, ocultos, ampliado y, por repositorio, commit elegido y scroll del historial). Ventana principal: ahora también se recuerdan el alto de la consola (`desklens.conH`) y la zona ampliada documento/IA (`desklens.max`). Probado a 900×600: al recargar vuelve todo igual. Ojo al probar: con el panel del navegador oculto no hay eventos de scroll; hace falta la rueda real o lanzar el evento.

## 2026-11-04 · Listas de commits para personas
El usuario no sacaba nada de «9d4a3bb · 04/11/2026 18:37 · Cesar · mensaje largo» ni veía la ▸ de archivos. Lista de versiones del comparador: agrupada por día (Hoy, Ayer, Lunes 2 nov), título en negrita (lo que va antes de «: ») con la hora o «hace N min», el resto del mensaje debajo, autor, y un botón «📄 N archivos» que despliega los archivos con +/−; la elegida lleva barra de color. Sin hash a la vista (va oculto en la fila: el filtro lo encuentra). Lo mismo, en corto, en la cabecera de cada columna, en «Autores» y en el historial de Git (sin hash, fecha legible). Servidor: `ts` (author time) en `git_log`, `git_graph` y blame, y `n` en `git_log` con una 2.ª llamada `log --no-walk --shortstat` (con la ruta, --shortstat contaría solo ese archivo).
Ojo: `git stash pop` dejó `index.html` en CRLF (no tiene `eol=lf` en .gitattributes); los scripts de parcheo deben normalizar `
` antes de buscar.

## 2026-11-04 · Historial de Git más sencillo
El usuario no entendía los carriles del grafo (colores por carril, sin nombres, cruces). Ahora, sin «Todas las ramas»: una sola línea (1.er padre desde HEAD y su remota) y cada merge es una fila «Fusionó «jeanr» · 3 commits» que se despliega (`gitMainLine`: cada commit lo reclama el merge más viejo que lo alcanza, igual que `git log p1..p2`, sin llamar a git). Con «Todas las ramas»: una columna por rama con su nombre en vertical y color fijo (`gitColumns`: main/master primero, luego la actual; las ramas ya borradas toman el nombre del mensaje del merge). Todo en la ventana; el servidor no cambia. Corregido de paso: abrir la pantalla completa estando ya abierta perdía la vista Git («null» a la derecha y un error cada 5 s).

## 2026-11-04 · Clic al instante (regla nueva) y Git más rápido
El usuario notaba demora en casi todos los clics: no eran animaciones, la ventana esperaba al servidor sin dar señal. Nueva regla en `reglas.md`: marcar lo elegido (⏳ si tarda) antes de esperar y paralelizar lo independiente. Aplicada primero a las ramas de Git (`gitPending`: rama marcada y grafo atenuado al instante; al cancelar vuelve atrás). Servidor: `git_overview` lanza sus 8 consultas de git en paralelo con el status (0,33 → 0,11 s en Atril) y `git_summary` mira los proyectos a la vez (1,08 → 0,25 s). Pendiente: aplicar la regla al resto de opciones cuando se toquen.

## 2026-11-04 · Dos sesiones en la misma carpeta
Mientras se hacía el detalle del commit, otra sesión de Claude hizo `315fd7e` en `G:\Atril` (Buscador «En:»: `search_scope` compara rutas resueltas; fallaba con carpetas en formato corto 8.3). Solo llevó sus 2 líneas y no chocó con los cambios sin commit de esta sesión, pero cambió `desklens.pyw` a mitad de una prueba: el servidor de prueba mostró «Hay que reiniciar DeskLens» (CODE_MTIME). Antes de editar o hacer commit, mirar `git status` y `git log -3`; si hay otra sesión trabajando aquí, no tocar los mismos archivos a la vez. Ojo también: en Windows, un servidor de prueba anterior puede seguir vivo en el mismo puerto; cerrar los `serve_tmp.py` que queden.

## 2026-11-04 · Detalle del commit: tabla ordenable y datos completos
El detalle de la pantalla completa de Git pasa a tabla (Estado, Archivo, Carpeta, Tipo, +, −, Tamaño en el commit) ordenable por columnas (se recuerda en `desklens.git.orden`) y con filtro. Cabecera: mensaje completo, hash con copiar, autor y email, fecha absoluta y relativa, padres que llevan a su fila del grafo, ramas/etiquetas que lo contienen y totales. «Ver» en imágenes: antes/después lado a lado (`/api/git/blob`, sin cabecera X-DeskLens porque lo pide un `<img>`, como `/api/hist/dato`; CSP sandbox para SVG). Menú ⋯: copiar hash, crear rama aquí, revertir. Servidor: `git_commit_info`, `git_blob`, acciones `rama_desde` y `revertir`; el estado también avisa de un revert a medias (REVERT_HEAD).

## 2026-11-04 · Instalador: comandos visibles y sin winget
En un Windows Server sin winget el instalador solo decía «falta». Ahora cada paso muestra el comando exacto (`> …`) y pregunta «¿Ejecutar? (s/n)», también para actualizar lo ya instalado (winget upgrade) y para las pruebas. Sin winget descarga los instaladores oficiales (python.org 3.12.10, la última versión de Git para Windows desde su GitHub y el .msi LTS de nodejs.org) y exige firma Authenticode válida de Python Software Foundation / Johannes Schindelin / OpenJS Foundation antes de ejecutarlos (comprobado descargando los tres). TLS 1.2 forzado para Server antiguos; sin administrador, Python y Git se instalan para el usuario. Marcas [OK]/[FALTA]/[--] porque ✓/✗ salían como «V»/«?». Ojo PS 5.1: `Invoke-RestMethod` pasa un array JSON como un solo objeto; hay que guardarlo en una variable antes de filtrarlo.

## 2026-11-04 · Cambiar de rama con cambios sin commit
Captura del usuario: al cambiar de rama salía el error de git en inglés («would be overwritten by checkout»). Es la protección normal de git; ahora `git_switch` lo convierte en `GitLocalChanges` (409 con los archivos) y la ventana ofrece, como VS Code: «Guardarlos aparte y cambiar» (stash con nombre claro; primero, lo más seguro) o «Llevarlos» (stash → cambiar → pop; si chocan, quedan en Conflictos y el stash se conserva). Nuevo «📦 Recuperar cambios guardados» en el menú de la rama y aviso en la vista. Solo se saca un stash si se acaba de crear (si no, sería uno ajeno). Probado con una copia de homeshape y sus cambios reales: pruebas → main guardando aparte → vuelta → recuperar dejó los archivos idénticos al original.

## 2026-11-04 · Instalador para Windows y modo de Git recordado
`instalar.bat` (lanza `instalar.ps1` con ExecutionPolicy Bypass solo para esa ejecución) revisa e instala con winget Python 3.12 y Git, comprueba Edge/Chrome, ofrece Node.js y las CLI de IA por npm, crea el acceso directo y ejecuta las pruebas; `-SoloRevisar` no instala nada. Comentado por secciones a petición del usuario. Detalles: .ps1 con BOM (PowerShell 5.1 lee UTF-8 solo así), .bat con CRLF (.gitattributes), se ignora el «python» de WindowsApps (atajo a la Store) y se recarga el PATH tras cada instalación. Probado en modo revisión en el equipo del usuario; las instalaciones reales no (todo estaba ya instalado).
Git recuerda si se dejó a pantalla completa o en el panel (`desklens.git.full`; predeterminado: panel).

## 2026-11-04 · Git fase 2: pantalla completa con grafo
⤢ en la vista Git: proyectos y ramas a la izquierda, grafo con entrantes/salientes y detalle del commit en el centro, y la vista Git (#gitv, movida) a la derecha. Ocupa la fila de las pestañas (`body.gitfull`), así la consola de pull/push sigue a la vista. Grafo por carriles en `gitLanes` (simple: con muchas ramas vivas se ensancha). Fallos vistos en la captura: la columna central se ensanchaba (faltaba `grid-template-columns:minmax(0,1fr)`, el mismo caso que la vista dividida) y la fecha usaba la clase `.gd`, que ya era el punto de git del árbol. Comprobado con capturas de Edge sin ventana (CDP) sobre un repo de prueba con rama, merge, entrante y saliente.

## 2026-11-04 · Git fase 1: Sincronizar y fetch automático
Pedido del usuario con captura de VS Code («Sync Changes 13↑»): en la vista Git no se veía si había algo pendiente. Plan en 4 fases tras revisar VS Code, GitLens, Git Graph, GitHub Desktop, Fork, Sublime Merge y GitKraken; esta es la 1: botón Sincronizar con ↓↑ (pull --no-rebase && push en la consola), «Comprobado hace N min», fetch automático configurable y estado de todos los proyectos en el selector. Pull/Push pasan al menú de la rama. Siguientes: 2 pantalla completa con grafo y detalle de commits; 3 stash, mensaje con IA, commit y sincronizar; 4 preparar por trozos y editor de conflictos.

## 2026-11-04 · Atril pasa a llamarse DeskLens
«Atril» chocaba en GitHub (≈195 repositorios y el visor de documentos Atril de MATE). Se descartaron DocGit (60), Facistol, Hojea y otros; DeskLens tenía 4 repositorios, ninguno parecido. Cambio completo, a petición del usuario: archivos (`desklens.pyw`, `.sh`, `.command`, `test_desklens.py`, docs), textos, cabecera `X-DeskLens`, claves de localStorage `desklens.*` y carpeta temporal `desklens-ia` (las pestañas y preferencias del navegador empiezan de cero; `config.json` e `historial/` siguen igual). Las entradas antiguas de esta bitácora también dicen DeskLens. Pendiente: renombrar el repositorio en GitHub y la carpeta local, y rehacer las capturas de `docs/capturas` (aún muestran «Atril»).

## 2026-11-04 · Elegir el navegador de la ventana
⚙ Ajustes › General › «Navegador de la ventana de DeskLens»: Automático (Edge › Chrome › Brave › Chromium), cada uno de los instalados o el navegador predeterminado (pestaña normal, sin modo aplicación). `browsers()` los detecta una vez al arrancar (registro App Paths y carpetas en Windows, /Applications en macOS, PATH en Linux); `edge_path(elegido)` cae al primero instalado si el elegido ya no está. Los PDF siempre usan un Chromium. Se aplica al reabrir DeskLens.

## 2026-11-04 · Vista Git (commit, ramas, pull, push y merge)
Tercera vista de la barra lateral, como el control de código de VS Code (diseño dibujado y aprobado antes). Las acciones rápidas (preparar, quitar, descartar, commit, ramas, deshacer commit) devuelven el estado; pull/push/fetch/merge van a la consola con `launch` y al terminar refrescan vista y árbol. Push sin seguimiento hace `push -u origin <rama>`. Sin editor de fusión de 3 paneles, rebase, stash ni etiquetas (pendiente si hacen falta). Probado con un repo y remoto temporales (test_desklens.py) y en la ventana con un conflicto real resuelto.
## 2026-11-04 · Ctrl+J para la IA, Ctrl+G ir a la línea
Ctrl+J abre/cierra el panel de IA (antes Ctrl+G; sigue Ctrl+Alt+B). Ctrl+G va a la línea: en el editor, el cuadro de CodeMirror (`jumpToLine`, admite «línea:columna»); en la vista de código numerada, pide el número con `ask()` y la marca un momento. Ambos en captura, para ganar a las descargas (Ctrl+J) y al «buscar siguiente» (Ctrl+G) del navegador.

## 2026-11-04 · Revisión técnica y mejoras de uso
- Revisión: do_GET ya responde a ValueError/KeyError; la ventana usa `edge_path()` también en Windows; fuera `_image_size` duplicada; `backup_once`/`replace_atomic`, `denied`/`stale` y el 423 en `do_POST` quitan código repetido; la limpieza del historial pasa al hilo del índice.
- Vista dividida: `.pane` con `grid-template-columns:minmax(0,1fr)` (un Word ancho tapaba el otro lado y ocultaba «Juntar»). Un solo botón para la barra lateral (el de las pestañas).
- Buscador: «En:» elige proyectos (casillas, «solo», o el del archivo abierto); `search(raices=…)` filtra en SQL. Título de proyecto en banda.
- Árbol: Plegar/Desplegar todo (un nivel), carpetas abiertas recordadas (`desklens.arbol`), «nuevo» sin extensión en la carpeta del archivo elegido, «Eliminar (a la papelera)» (PowerShell/VisualBasic, ruta por variable de entorno).
- Soltar desde el Explorador abre en pestañas: el navegador no da la ruta y `locate_dropped` la busca por nombre+tamaño+fecha (selección del Explorador por COM, carpetas abiertas, Escritorio/Descargas/Documentos, índice). Sobre un Word solo se inserta en edición.
- Ojo al probar: una pestaña del navegador en el 8765 del usuario envía pings y mantiene vivo su servidor viejo. Ahora la ventana avisa si el servidor no conoce una ruta o si `desklens.pyw` cambió desde el arranque.

## 2026-11-03 · Código comentado
Barrido completo con la regla de reglas.md (técnico, para quien mantenga): 83 docstrings en desklens.pyw (138 de 145 funciones comentadas; las 7 restantes son de una línea y evidentes) y 100 comentarios en index.html sobre las funciones de 5+ líneas que no tenían (las que quedan son de una línea o evidentes). Solo comentarios: se comprobó que el código sin ellos es idéntico al de antes, y las pruebas pasan en Windows y Linux.

## 2026-11-03 · El documento se pintaba encima del panel de IA
Captura del usuario: un Word ancho se veía a través del panel de IA (parecía transparente). Un elemento con posición absoluta dentro de `#view` (que no está posicionado) no lo recorta su scroll y puede salir sobre `#ia`. Arreglo: `main{overflow:clip}` (nada se pinta fuera del área central) y `#ia{z-index:3}`. No se reprodujo con su documento, pero sí el mecanismo: con el CSS anterior un elemento así tapa la IA; con el nuevo, no. El «Failed to fetch» de esa captura fue el servidor reiniciándose.

## 2026-11-03 · Ctrl+G: panel de IA
Abre y cierra el panel de IA (sigue también Ctrl+Alt+B). Escuchado en captura para que funcione con el cursor en el editor y no lo coja el «buscar siguiente» del navegador; no actúa con un modal abierto ni a pantalla completa. Para buscar dentro de una web se quedó la opción C (Ctrl+F del navegador); la A (lista de coincidencias sin resaltar) se descartó.

## 2026-11-03 · Pestaña web: no se recarga al cambiar de pestaña; Ctrl+F del navegador
Cada pestaña web vive en una `.webbox` hija de su `.pane`, encima de `#view` en la misma celda de la rejilla. Al cambiar de pestaña se oculta (no se borra) y la barra (`box._bar`) se vuelve a poner al volver: misma página, scroll y lo escrito, sin recargar. Se quita al cerrar la pestaña, al sustituir la de vista previa y al moverla de lado (ahí sí se recarga: un iframe que se mueve en el DOM se recarga). `setUrl` cambia la ruta de la pestaña aunque esté oculta o en el otro lado.
Ctrl+F en una pestaña web: `findOpen` devuelve false y la tecla llega al buscador del navegador, que sí entra en webs de otro origen; el de DeskLens no puede leerlas.

## 2026-11-03 · La ventana entera se desplazaba hacia un lado
Con muchas pestañas (o una ruta larga en la barra de estado) la columna central `1fr` crecía más que la ventana, y como `body` tenía `overflow:hidden` (oculta la barra pero deja desplazar por código), el primer `scrollIntoView()` (saltar de página en el PDF, marcar el archivo en el árbol) corría todo DeskLens: la columna de iconos y parte del árbol quedaban fuera. Arreglo: columnas `minmax(0,1fr)` y `html,body{overflow:clip}` (no se puede desplazar ni por código). Reproducido con el CSS anterior (columna de iconos a −3142 px) y comprobado con el nuevo (0).

## 2026-11-03 · Capturas para el README
10 capturas en `docs/capturas/` (1440×900) con un proyecto inventado, «Taller de escritura» (sin datos del usuario). Se sacan con Edge sin ventana manejado por CDP desde Node (WebSocket nativo de Node 24, nada instalado). El proyecto se crea en `_demo/` (en .gitignore) con una ruta neutra, porque la consola muestra la ruta completa. Al repetirlas, crear la demo, levantar un servidor aparte (otro puerto, historial aparte) y lanzar el guion de escenas.
Encontrado de paso: en la vista dividida, PDF y Word quedaban cortados por los dos bordes (centrados y más anchos que el lado) → `align-items: safe center` y el visor de PDF recalcula el ancho con ResizeObserver. «Abrir en consola de Windows» → «Abrir en una terminal».

## 2026-11-03 · Vista dividida, comparar archivos, pestaña web
- **Vista dividida** (◫ en la barra de pestañas o Ctrl+\): `#panes` con una o dos `.pane`, cada una con sus `#tabs`, `#bar` y `#view`. `$()` busca primero en la `.pane` activa, así el código existente no cambia. `activatePane()` guarda y carga `tabs`/`cur`/`previewTab`/`editorCM`/`curFile`/`pdfCtl`/`findP` sin volver a dibujar. Cada render tiene un número único y cada lado guarda el suyo (`live(s)`): el del otro lado no lo cancela. Arrastrar una pestaña a la barra del otro lado la mueve. Se recuerda (`desklens.split`, ancho `desklens.splitL`).
  Al dividir, lo que se ve se queda (una web no se recarga: un iframe que se mueve o se recrea vuelve a su dirección inicial) y al lado nuevo va la pestaña vista justo antes. `moveTab` espera a que el lado de origen termine de dibujarse antes de cambiar de lado (si no, quedaba en blanco hasta hacer clic).
- **Comparar dos archivos** (clic derecho → «⇆ Comparar con otro archivo…» o «con el otro lado»): `compareFiles()` con MergeView aparte del comparador de git. Texto editable a la derecha con ➜ y Guardar; Word/Excel/PowerPoint por su texto; PDF por el texto de sus páginas.
- **Pestaña web** (🌐 junto a +): ruta `web:<dirección>`. `/api/web/permite` mira X-Frame-Options y `frame-ancestors` antes de cargar; si la web no se deja mostrar, aviso y «↗ Abrir en el navegador». iframe con sandbox sin `allow-top-navigation`. ← → con el historial de la ventana contando las cargas del iframe. Búsquedas: ⚙ Ajustes → Web → buscador (`web_buscador`, primer ajuste de tipo lista: valor de texto y opciones en el hueco «mínimo»). Google (con `igu=1`), Bing, Yahoo y Wikipedia se ven dentro; DuckDuckGo, Ecosia y Brave dan el aviso con «Abrir en el navegador». ☆ favoritos en `desklens.favoritos`. Límite: la dirección no sigue a los enlaces de dentro de la web (iframe de otro origen: el navegador no deja leerla ni recargarla). La barra lo dice: `nav.urls[pos]` guarda la dirección de cada carga que pidió DeskLens (null si vino de un enlace de dentro); si es null, la barra muestra en gris «↪ Navegaste dentro de la web · empezó en …», ⟳ pasa a ⌂ «Volver al inicio» y ↗/☆ usan la última conocida. ← → recuperan el estado de cada posición. El usuario eligió esta opción frente a un proxy (rompe muchas webs) o una ventana aparte.

## 2026-11-03 · Multiplataforma y preparado para publicar
`desklens.pyw` funciona en Windows, macOS y Linux: `WINDOWS`/`MAC`, `NO_WINDOW`, `edge_path()` busca Edge/Chrome/Chromium/Brave en cada sistema (ventana `--app` y PDF), `open_terminal()` (cmd, Terminal de macOS, x-terminal-emulator…), «Mostrar en carpeta» (`explorer`/`open -R`/`xdg-open`), `.sh` con bash, `.bat`/`.vbs` «solo en Windows», `.ps1` con `pwsh`, detener mata el grupo de procesos. Ventana: `sepOf`/`pjoin`/`under`/`rawPath` para rutas `C:\…` y `/home/…`. Lanzadores `desklens.command` (macOS) y `desklens.sh` (Linux).
Probado en Linux con Docker (Python 3.10 y 3.12): pruebas completas + interfaz (Word, PDF, imagen, consola .sh). macOS sin probar. Corregido de paso: la prueba escribía copias para deshacer en el `historial\` real (ahora usa carpetas temporales desde el principio).
README, LICENSE (MIT), TERCEROS.md, `.gitattributes` (LF en lanzadores). Nombres de proyectos del usuario cambiados por ejemplos en la documentación.
Pendiente: decidir nombre en LICENSE, historial de git limpio para el repositorio público, y subirlo (lo hace el usuario o lo confirma).

## 2026-11-03 · Adiós a alert/confirm/prompt
Se cambiaron los 10 avisos y preguntas del navegador por `ask()`. Ahora `ask()` va en su propio `<dialog id="ask">`, centrado y encima de cualquier otro modal. Antes pisaba `#dlg`: un aviso dentro de Reglas o de Conectar IA borraba ese modal.
- Los botones nombran la acción: Quitar/Cancelar, Borrar/Cancelar, Descartar/Seguir editando, Guardar/Cancelar, Entendido.
- `{ danger: true }` pone en rojo lo que borra; el foco queda en Cancelar, así que un Enter nunca borra.
- `{ input: 'valor' }` pide un texto (sustituye a `prompt`) y devuelve ese texto o null.
- Las comprobaciones de «hay un modal abierto» usan `modalOpen()`.
- Hay una regla nueva en reglas.md.

## 2026-11-03 · Panel de IA sin 🧹 Limpiar
Se quitó el botón 🧹 porque se solapaba con «Nueva»: los dos dejan el chat en blanco. Quedan **Nueva** (la anterior sigue en el desplegable) y **🗑 Borrar**. El servidor conserva `/api/conv/limpiar` porque las pruebas lo usan; se puede borrar junto con su prueba si nadie lo vuelve a necesitar.

## 2026-11-03 · La IA recibe la página del PDF que se ve
Antes, con un PDF abierto y sin páginas nombradas en el mensaje, no se mandaba texto. Ahora se adjunta la página en pantalla (`pdfAt`), y la etiqueta «Se enviará» cambia al pasar de hoja (`pdfAt` llama a `iaRefresh`). Si el mensaje nombra páginas, mandan esas.

## 2026-11-03 · Pestañas: Ctrl+W, Ctrl+Tab y arrastrar
- **Ctrl+W** cierra la pestaña activa (si tiene cambios sin guardar, pregunta).
- **Ctrl+Tab** y **Ctrl+Shift+Tab** van a la siguiente y a la anterior en el orden de la barra, con vuelta al principio.
- **Arrastrar una pestaña** sobre otra la reordena: una raya del acento marca dónde cae. Al chat sigue adjuntándose, y soltarla fuera de la barra no hace nada.
- Los atajos se escuchan en fase de captura, antes que CodeMirror.
- **Pendiente:** comprobar en la ventana real de Edge (`--app`) que Edge no se queda con Ctrl+W ni con Ctrl+Tab.

## 2026-11-03 · PDF: hueco a la izquierda
La columna de miniaturas (◧) tiene `display:flex`, y eso pasaba por encima del atributo `hidden`. Apagada, dejaba un hueco vacío de 150 px. Se añadió `.pthumbs[hidden]{display:none}`.

## 2026-11-03 · PDF en blanco (choque de clases CSS)
Las páginas del PDF salían en blanco porque el modal de Imprimir reutilizó la clase `.pbody`, que ya usaban las páginas de los PDF. Con `flex:1` y `display:grid`, cada página quedaba con altura 0. Se renombró a `.prbody`. De paso: las filas de cambios del comparador (`.crow`) ahora son `.chg`, porque `.crow` ya era de «Conectar IA». La pista del buscador es `.sempty`. **Antes de crear una clase, buscarla con grep.**

## 2026-11-03 · Vista «Buscar» aparte
La barra lateral tiene dos vistas, como VS Code: 📁 Explorador y 🔍 Buscar (Ctrl+Shift+F; otro clic en la vista activa oculta la barra; se recuerda en `desklens.vista`). Buscar ya no oculta el árbol, y cada vista conserva lo suyo. Los resultados van agrupados por proyecto › archivo › fragmentos, con contador, etiqueta «nombre», la extensión siempre visible (`setName`), chips por tipo y teclado (↑↓ Enter ←→). Un clic en un fragmento abre el archivo con el buscador de la pestaña en esa palabra (en un PDF, desde esa página). Ojo: `.srow` ya era de Ajustes, así que las filas del buscador usan `.sr`.

## 2026-11-03 · Clic derecho en pestañas
Abre el menú del archivo (el mismo del árbol: Información, Comparar versiones, Abrir, Editar, Adjuntar, Copiar…, Mostrar en carpeta) con «Cerrar pestaña» y «Cerrar las demás» arriba; «nuevo N» solo las de cerrar. `nodeMenu(…, git=null, extra)`: sin estado de git conocido lo busca en el árbol y no apaga «Comparar».

## 2026-11-03 · Imprimir
🖨 Imprimir… en ⋮ de la pestaña, clic derecho (árbol y pestaña) y Ctrl+P. Modal con vista previa de la hoja a escala: tamaño (A4, Carta, Oficio 216×330, Legal, A3, A5), vertical/horizontal, márgenes (0/6/15/25 mm); imágenes: ajustar, llenar (recorta), tamaño real o ancho en mm, centrar; código: números de línea y partir líneas largas (tabla de líneas con colores de hljs, spans cerrados y reabiertos por línea); Markdown/HTML (sin scripts)/CSV/notebook como en lectura; Word con el visor (márgenes del propio Word). Se recuerda lo elegido (`desklens.print`). Se imprime con `window.print()` sobre un `#printArea` y `@page` con la hoja; en papel siempre colores claros (hljs claro en `print`). PDF: el original con el diálogo de Edge (iframe oculto; si falla, abre el visor de Edge). Audio, vídeo y fuentes: en gris.
Probado: imagen (A4 horizontal, llenar → `@page{size:297mm 210mm;margin:15mm}`, 267×179,5 mm), código y Markdown. Sin probar: el diálogo real de Windows, el PDF y el Word impresos.

## 2026-11-03 · Clic derecho propio (sin el menú del navegador)
Menú de DeskLens según dónde: siempre Copiar (gris sin selección), Seleccionar todo y, en el documento, 🔍 Buscar en el archivo; donde se escribe (editor, cuadros de texto, Word en edición) además Deshacer, Rehacer, Cortar y Pegar. Atajo a la derecha de cada opción (`openMenu` acepta `{key}`). El árbol mantiene su menú; Mayús + clic derecho = menú del navegador. `copyText` con plan B (execCommand) si el portapapeles no da permiso; Pegar usa `clipboard.readText` (Edge puede pedir permiso la 1.ª vez; si no, avisa «usa Ctrl+V»).

## 2026-11-03 · Árbol y archivo abierto se actualizan solos
Árbol: cada 4 s revisa las carpetas desplegadas (`/api/dir`, firma nombres+git) y redibuja solo la que cambió, armada aparte (sin parpadeo, subcarpetas abiertas siguen abiertas); pausa con DeskLens oculto, un menú abierto o escribiendo en la barra. Ponytail: sondeo; con cientos de carpetas abiertas, vigilar el disco en el servidor.
Archivo abierto: cada 3 s `/api/mtime`; si cambió fuera de DeskLens se recarga solo (lectura, edición sin cambios —sigue en edición, mismo cursor y scroll—, PDF en su página, Word/imagen/PDF en edición sin cambios vuelven a la vista). Con cambios sin guardar siempre pregunta («Mantener mis cambios» / «Recargar (perder mis cambios)»), y no vuelve a preguntar por ese mismo cambio. ⚙ Ajustes «Preguntar antes de recargar…» (predeterminado: no). Guardar desde DeskLens no cuenta como cambio externo.

## 2026-11-03 · Orden del árbol por proyecto
⋮ del proyecto → Ordenar: «Alfabético ↑ ↓» y «Fecha modificación ↑ ↓» (flechas con título: ascendente A→Z / lo más antiguo primero, descendente Z→A / lo más reciente primero; clic en el nombre = A→Z o lo más reciente). Carpetas siempre primero; ✓ en el tipo y la flecha activa en morado. Se recuerda por proyecto (`desklens.orden`: alfa-asc|alfa-desc|fecha-asc|fecha-desc). `/api/dir` envía `fecha` (mtime).

## 2026-11-03 · Comparador: pestaña «Archivos» en el panel izquierdo
El ▸ del combo pasaba desapercibido. Panel izquierdo con pestañas «Cambios N | Archivos N»: archivos del commit de cada columna (un grupo por commit; Disco/Editor no cuentan), con insignia de tipo (.php, blade, .md…), estado M/A/D/R, filtro y resumen por tipo («4 .php · 2 .md · 2 .blade»); el actual marcado. Clic = comparar ese archivo con las mismas versiones, sin salir de la pestaña. Clases `.cfrow` (`.frow` ya la usan el buscador y Reglas).
Corregido: al pulsar un archivo, el panel desaparecía mientras cargaba («Cargando versiones…» en todo el ancho) y parecía cambiar de pestaña; ahora la lista se queda (el archivo pulsado ya marcado), solo el centro dice «Cargando…» y los combos se reparten mientras tanto.
Más suave: al cambiar de archivo o de versión, las columnas actuales quedan atenuadas con «Cargando…» encima y las nuevas entran con un fundido de 0,18 s (sin animación si el sistema pide menos movimiento); el hueco de la raya de autores va reservado desde el principio (no empuja el texto); los archivos de cada commit se guardan para toda la sesión (`gitFilesCache`) y la lista ya no parpadea con «Cargando archivos…».
Corregido: «←» fallaba desde el segundo salto (la vuelta guardada no tenía ruta: error en `.split`). Ahora «← archivo» lleva siempre al archivo con el que se abrió el comparador, con las versiones y la pestaña de entonces (`carry.origin`).
Corregido: el scroll con la rueda se paraba (hacia la línea 300–400) hasta mover el ratón: la etiqueta de autor quedaba bajo el puntero y, al estar fuera de la zona con scroll, se tragaba la rueda. Ahora la rueda sobre la etiqueta la oculta y desplaza la columna.
Corregido: al pulsar un archivo la lista se encogía a 250 px mientras cargaba y luego volvía sola al ancho guardado; el ancho guardado se aplica desde el primer instante.

## 2026-11-03 · Comparador: archivos de cada commit
En el combo de versiones, ▸ junto a cada commit despliega sus archivos (M/A/D/R de color, «● este» el actual; GET `/api/git/archivos`, `git show --name-status -M --diff-merges=first-parent`, rutas con tildes sin escapar). Clic en un archivo = comparar ese archivo con las mismas versiones por columna (un commit que no lo tocó se lee igual); «← archivo» vuelve. Si no existe en una versión, la columna lo dice («no existe en esta versión»). El filtro del combo encuentra también los archivos ya desplegados. La lista de cambios abre siempre visible (◧ la oculta solo mientras el modal está abierto).
Corregido: el filtro de la lista no ocultaba nada (`.crow{display:grid}` ganaba a `[hidden]`). Ahora busca en todas las líneas del cambio, de las dos versiones, varias palabras, sin tildes ni mayúsculas, y avisa si nada coincide.
Lista: el cambio actual se ve con ▶ en lugar del número, fondo del acento, borde grueso y texto en negrita; cada fila lleva una insignia de tipo (+ verde, − rojo, ~ ámbar).

## 2026-11-03 · Comparador: lista de cambios y mapa
Lista a la izquierda (◧, se recuerda): una fila por cambio con nº, línea, tipo (+ añadido / − quitado / ~ cambiado, borde verde/rojo/ámbar), primer texto y, en 3 columnas, entre cuáles; filtro; ▶ el actual. Mapa a la derecha: todo el archivo en la franja, marcas por cambio y recuadro de lo que se ve; clic o arrastrar = ir. Clic en la lista o ↑↓ / Alt+↑↓ baja al cambio, lo centra y lo resalta en las dos columnas; «Cambio n de N». Datos: `leftChunks()`/`rightChunks()` del merge.
Corregido: al ocultar la lista todo quedaba gris (la columna oculta salía de la cuadrícula y el merge caía en una de 0 px; el mapa ocupaba todo). El botón ◧ pasó arriba a la izquierda, sobre la lista junto al filtro, con el icono de la barra lateral. Probado con routes/web.php de un proyecto Laravel (95 commits).
Anchos: borde derecho de la lista (160–600 px) y el hueco entre columnas (reparte entre esas dos, mín. 150 px); doble clic = original; se recuerdan (`desklens.cmplw`, `desklens.cmpw2/3`). Los combos se colocan encima de su columna (`syncHeads`, ResizeObserver).

## 2026-11-03 · Autoría por línea en el comparador (git blame)
Cada columna: raya del color del autor junto al número y, al pasar el ratón, «● autor · fecha hora · hash · mensaje» al final de la línea (recuadro con hash y mensaje completos). Color fijo por autor (8 tonos); lo no confirmado en gris «Sin commit · cambio local». Casilla «Autores» (se recuerda). POST `/api/git/blame` {ruta, hash, rel, texto}: por commit, disco o texto del editor (`--contents -`).
Pendiente: llevarlo también al editor normal (autor de la línea del cursor), si el usuario lo quiere.
Corregido: la autoría iba al final de la línea (en líneas largas no se veía y movía el texto); ahora es una etiqueta flotante pegada al borde derecho, a la altura de la línea, sin tocar el texto.
Corregido: el comparador no tenía scroll (las columnas crecían con el texto y el modal las cortaba); ahora cada columna mide lo que el modal, con scroll sincronizado, y ↑↓ deja la diferencia al centro. Probado con 300 líneas.
Ajuste de línea con Alt+Z (como VS Code) en el editor y en el comparador (casilla «Ajuste de línea»); se recuerda (`desklens.wrap`).

## 2026-11-03 · Menú de acciones en (i) y comparar versiones (git)
(i) y clic derecho en el árbol abren un menú: Información, ⇆ Comparar versiones (gris sin git), Abrir, Editar, Adjuntar al chat, Copiar nombre/ruta/ruta relativa (el título dice qué se copia), Mostrar en carpeta; carpetas: Nuevo archivo/carpeta aquí. El modal Información queda solo para leer. `openMenu` admite '-', {head}, {title, disabled}, ↑↓ y `{search}`.
Comparar: 2 o 3 columnas con el merge de CodeMirror (diff_match_patch, cdnjs, se carga al abrir); cada columna elige versión en un combo con filtro (editor sin guardar, disco, commits con `--follow`); rojo = quitado, verde = añadido; ↑↓ diferencias, ocultar líneas iguales, ↩ copia una versión al editor sin guardar. `/api/git/log`, `/api/git/version`. Solo texto (Word/PDF no).

## 2026-11-03 · Buscar y reemplazar como VS Code (por pestaña) y barra del PDF
Cuadro flotante arriba a la derecha: Aa / ab / .* / á (sin tildes), «n de N», ↑↓ (Enter, F3), ≡ en la selección, › reemplazar con AB (conservar mayúsculas), ⇄ y ⇄⇄ (un solo Ctrl+Z); Alt+C/W/R/L, Ctrl+Mayús+1, Ctrl+Alt+Enter, Esc. Cada pestaña recuerda búsqueda y opciones. Proveedores: editor (marcas + rayas en el scroll, addon annotatescrollbar), lectura (CSS Highlight API sobre el texto de la vista; Ctrl+H pasa a edición) y PDF (cuenta en todas las páginas, marca en las dibujadas).
PDF: ◧ miniaturas, ‹ pág ›, − zoom▾ + (Ctrl+rueda, Ctrl + / − / 0), ↔ Ancho, ▯ Página, ⟲ girar vista, 🔍; AvPág/RePág/Inicio/Fin por páginas. Probado en servidor aparte con un PDF de 3 páginas; falta probar con «1 & 2 Samuel» (82 págs.).
🔍 en la cabecera de todas las pestañas (junto a ✎ y ⋮): buscar sin editar; reemplazar (Ctrl+H) sí pasa a edición.
Ponytail: tope de 20000 coincidencias (3000 marcadas en el editor); la vista en lectura engancha el buscador a los 300 ms.

## 2026-11-03 · Modal «Añadir proyecto o archivo suelto» rehecho
Antes, en una carpeta que ya era proyecto todo salía «dentro de un proyecto» y los botones apagados, sin salida. Ahora tres columnas (hasta 1100 px): Lugares (Inicio, Escritorio, Documentos, Descargas —también en OneDrive—, unidades, proyectos de DeskLens) | lista con Tipo y Estado (● proyecto / en proyecto / suelto), filtro sin tildes | panel «Como proyecto» (avisos, o «Mostrar en el árbol» si ya está) y «Archivos sueltos» (marcados con ✕; los que ya están en DeskLens se abren en vez de añadirse). Teclado: ↑↓, Enter, Espacio, Retroceso, escribir = filtrar, Esc. `/api/explorar` envía `lugares` y `proyectos`.

## 2026-11-03 · Atajos de edición de VS Code en el editor
Con `keymap/sublime.min.js` (cdnjs) y `CodeMirror.defaults.extraKeys`: Alt+↑/↓ mover línea, Shift+Alt+↑/↓ duplicar (arriba deja el cursor en la copia de arriba), Ctrl+Alt+↑/↓ cursor extra, Ctrl+D siguiente coincidencia, Ctrl+Shift+L todas, Ctrl+Shift+K borrar línea; Esc vuelve a un cursor. Vale para el editor y para Reglas. Probado con teclas reales.
Ojo: con gráficos Intel, Ctrl+Alt+↑/↓ puede girar la pantalla antes de llegar a DeskLens.

## 2026-11-03 · ⚙ Ajustes rehecho a lo ancho, con filtro
Modal de hasta 1100 px: grupos a la izquierda (clic = ir, nº visibles, ● si hay cambiados), filas «nombre | valor | rango | ↺ defecto». Filtro sin tildes ni mayúsculas (Esc lo borra), «Solo cambiados», contador y aviso si nada coincide. Solo `settingsDialog()` y CSS `.sets`.
Nuevo `reglas.md` del proyecto: aprovechar el ancho de escritorio y usar la skill de diseño en las mejoras de interfaz.

## 2026-11-02 · Modal «Cambios sin guardar»
Los `confirm()` del navegador se cambiaron por un modal de DeskLens: **Guardar | No guardar | Cancelar** (`askUnsaved`), al cerrar una pestaña, al salir de edición (📖) y al pasar a otra pestaña mientras se edita un Word, imagen o PDF (la vista no se toca hasta decidir; «Guardar» incluye lo último escrito).

## 2026-11-02 · Historial de cambios (↶ ↷) en disco
Texto, Word, imagen y PDF en edición: [↶|▾] [↷|▾], Ctrl+Z / Ctrl+Y (en código manda CodeMirror) y modal tipo papelera (fecha y cambio · vista previa: líneas/párrafos +/−, palabra marcada en cambios de formato, imágenes antes/después, miniatura del PDF con notas). «Deshacer/Rehacer hasta aquí», separadores 📂 Abierto y 💾 Guardado, filtro.
`historial\versiones\<hash>\`: árbol de pasos (deshacer y seguir editando no borra: queda en «Otras versiones»). Texto: texto entero gzip; imagen: PNG + brillo/contraste; Word: los cambios del paso sobre la última copia (`docx_transform` sin tocar el disco; Guardar escribe el estado del paso); PDF: páginas y notas sobre la última copia. Nada se escribe hasta el primer cambio. ⚙ Ajustes «Historial de cambios»: días (7), tope (1000 MB: se borra el historial más viejo entero), pausa al escribir (2 s).

## 2026-11-02 · Visor de PDF propio
El visor de Edge no dice en qué página estás (su dirección no cambia), así que el editor empezaba en la 1. Ahora los PDF se leen con pdf.js: páginas perezosas (se sueltan las lejanas), texto seleccionable (capa de texto), pág. [n] / N, − % + ↔, buscar dentro (Ctrl+F, Enter / Mayús+Enter, sin tildes ni mayúsculas, resalta y centra). La página se recuerda por archivo (`desklens.pdfpag`); ✎ abre el editor en ella y al salir se vuelve a ella. ⋮ «Abrir con el visor de Edge» para imprimir; sin internet se usa Edge solo.
Probado con «1 & 2 Samuel» (82 págs., 16 MB).
Corregido: la barra del visor no respondía al bajar por el documento (la capa de texto de las páginas, mismo z-index, quedaba encima de la barra fija). Barra z-index 10 y cada página `isolation:isolate`.

## 2026-11-02 · Editar PDF
✎ en un .pdf: vista propia con pdf.js (páginas dibujadas al llegar a ellas). T Texto (clic → texto; color y tamaño), ▭ Resaltar (arrastrar; amarillo 35 %), ✕ quita una nota, por página ⟲ ⟳ ↑ ↓ 🗑, ↶ deshace pasos. Las notas se guardan en coordenadas del PDF; al guardar, pdf-lib 1.17.1 (cdnjs) las dibuja (Helvetica: español sí, emojis no → aviso), reordena/gira/quita páginas en el mismo documento y `/api/binario` escribe con .bak y copia para deshacer. PDF cifrado → aviso. Probado: orden, giro, borrado, «¿ñandú?» y texto derecho sobre página girada.
No se puede cambiar el texto que ya trae el PDF (solo añadir encima).

## 2026-11-02 · Editar imágenes
✎ en .png/.jpg/.jpeg/.webp: ⟲ ⟳ ↔ ↕, ✂ Recortar (arrastrar y ✓), Ancho en px (alto proporcional), ☀ brillo y ◐ contraste (doble clic = 100 %), ↶ deshace pasos. Cada paso es un lienzo nuevo en memoria; al guardar se escribe en el mismo formato (JPEG con fondo blanco, calidad 0,92) por `/api/imagen`: .bak la primera vez, copia en `historial\deshacer` («↩ Deshacer el último guardado» en ⋮) y rechazo si cambió en disco. GIF/BMP/SVG no (el navegador no los vuelve a guardar igual).

## 2026-11-02 · Editar un Word a mano
✎ en un .docx: se escribe sobre la vista y hay B, I, U y color A▾ (también Ctrl+B/I/U); Guardar o Ctrl+S. Cada `<p>` del visor se empareja con su `w:p` por texto y orden (`/api/docx/parrafos`); los que no casan (encabezados, tabulaciones) quedan atenuados y de solo lectura. Al guardar se envían cambios por párrafo `{parrafo, desde, buscar, reemplazar | negrita… | agregar}` al mismo `docx_apply` que usa la IA: .bak, «↩ Deshacer el último guardado» en ⋮, y se rechaza si el Word cambió en disco (mtime).
El botón dice su estado: «Guardar» (gris, sin cambios) → «Guardar ●» → «✓ Guardado»; los avisos de abajo destellan (el usuario creyó que Guardar no iba: guardaba, pero no se notaba).
Soltar una imagen (árbol, pestaña, visor o Windows) sobre un párrafo del Word la inserta antes o después según la mitad (línea azul), en lectura o en edición (en edición va junto con lo pendiente). Soltar fuera de un sitio válido explica dónde soltar.
Sin Enter (párrafos nuevos → IA); pegar solo texto. La IA no aplica cambios en un Word con ediciones a mano sin guardar. Probado con una copia de «Exposición – 2 Samuel»: 80/80 párrafos editables y Word lo abrió bien.

## 2026-11-02 · Imágenes y cualquier archivo en el chat, imagen en Word, .bak y extensión visible
Se adjunta todo: texto, .docx, .xlsx/.pptx (texto con Python estándar), PDF por páginas. Imágenes y binarios van como referencia (nombre, tamaño, ruta); 👁 hace que Claude vea la imagen (JPEG ≤ 1568 px ≈ 1.600 tok, `--input-format stream-json`). Los avisos llevan siempre el nombre y nada se descarta en silencio.
Word: `<<<DOCX {"imagen": ruta, "buscar": …, "posicion": "antes|despues", "ancho_cm"} DOCX>>>` mete la imagen en un párrafo nuevo y centrado (probado: Word lo abre, 16 cm). Explorador: botón «.bak» (ocultos por defecto) y el nombre se recorta conservando la extensión (también en pestañas).
La edición a mano de Word, imágenes y PDF está en las entradas de arriba.

## 2026-11-02 · Arrastrar al chat, archivos sensibles permitidos, índice sin bloqueos
Arrastrar un archivo del árbol o una pestaña al panel de IA lo adjunta (con ruta: la IA puede proponer cambios); desde el Explorador de Windows se adjunta su contenido (solo lectura). PDF soltado sin «página N» en el mensaje → cuadro «de … a …». Carpetas no.
Nuevo ajuste «Permitir adjuntar y enviar a la IA archivos sensibles» (predeterminado: SÍ, por decisión del usuario: son archivos locales); lista ampliada (.npmrc, .netrc, id_rsa, credentials.json, wp-config.php, .ppk, .kdbx…). Desactivado, el servidor vuelve a bloquearlos.
Corregido: «database is locked» cuando el indexador escribe y la ventana consulta a la vez (WAL una sola vez + busy_timeout; los errores de SQLite ya no cortan la petición).

## 2026-11-02 · Envío inmediato y cambios de la IA sin doble paso
El mensaje sale del cuadro al pulsar Ctrl+Enter (antes esperaba a preparar adjuntos y a la respuesta); si algo falla, vuelve al cuadro. Nuevo ajuste «Pedir confirmación antes de aplicar los cambios que propone la IA» (predeterminado: no): los cambios de Word y de texto se aplican al llegar la respuesta; en Word queda «↩ Deshacer» (copia exacta previa en `historial/deshacer`, últimas 100), en texto Ctrl+Z.

## 2026-11-02 · Chat vinculado a la pestaña
🔗 (encendido por defecto): cada pestaña tiene su conversación y la recupera al volver (la recordada o la más reciente con ese `vinculo`); una pestaña sin chat empieza vacía. Borrador por pestaña. 🧹 limpia (con confirmación) sin perder el vínculo; 🗑 borra. «nuevo N» guardado se lleva su chat.
Pendiente: las conversaciones anteriores a este cambio no tienen vínculo (se ven con 🔗 apagado).

## 2026-11-02 · Cambiar formato de un Word desde el chat
Visor fiel con `docx-preview` (colores, fuentes, páginas); mammoth queda de reserva sin internet. La IA recibe «ARCHIVO ABIERTO» y, si es .docx, propone `<<<DOCX {"buscar": "…", "color": "rojo"} DOCX>>>`; «Aplicar al Word» cambia solo los fragmentos afectados (todo o nada, .bak, avisa si Word lo tiene abierto).
Probado con una copia real: Microsoft Word la abrió sin errores y con el título en rojo.

## 2026-11-02 · Buscador con Aa / nombre / contenido y límite de tokens en Ajustes
Iconos dentro del cuadro como VS Code: Aa (mayúsculas y tildes exactas), 📄 nombre, ≡ contenido (nunca los dos apagados; se recuerda). El límite de tokens por mensaje está en ⚙ Ajustes y en «Conectar IA» (mismo valor).

## 2026-11-02 · Nuevo archivo/carpeta, «nuevo 1», recuperación, ⚙ Ajustes
Iconos en el árbol (en la carpeta elegida). Ctrl+N abre «nuevo 1» sin guardar. Lo no guardado se copia a `historial\recuperacion` (2 s / máx. 10 s, escritura atómica) y se reabre tras cierres o reinicios. ⚙ Ajustes: los valores antes fijos en el código (grupos General, Índice, Bitácora, Git, IA, Recuperación, Editor). Modal (i) con copiar nombre/ruta/ruta relativa.

## 2026-11-02 · Índice de búsqueda, git por archivo, (i) información
SQLite FTS5 en `historial/indice.db` (sin tildes ni mayúsculas, frases, prefijos). Se indexa todo en segundo plano (también 🔒; solo se salta `.git`); se reanuda tras cerrar; PDFs los lee la ventana con pdf.js página a página. Árbol: negrita = pestaña abierta, fondo = la activa, se despliega hasta ella. Punto de git (blanco con borde = sin git) que se cambia por (i) al pasar el ratón.
Medido: 917 archivos en 39 s la 1.ª vez; ≈ 230 MB por la Biblia en JSON.

## 2026-11-02 · Crear .docx y .pdf desde el chat
La IA escribe Markdown en `<<<ARCHIVO nombre.ext … ARCHIVO>>>`; DeskLens crea texto tal cual, .docx con Python estándar y .pdf con Edge sin ventana (A4, números de página). Se abre solo en una pestaña. .xlsx/.pptx/imágenes se rechazan con aviso.
Pendiente: comprobar a ojo los números de página del PDF.

## 2026-11-02 · Ventana: posición y tamaño recordados
Se guardan en `config.json` y DeskLens abre con `--window-position/--window-size`; la página corrige si Edge las ignora.

## 2026-11-02 · Panel de IA rehecho como un solo chat
El primer diseño (modos Rápido/Conversación, Alcance, Destino, adjuntar a mano) fue **rechazado por complicado**. Ahora DeskLens adjunta solo: archivo abierto, archivos nombrados en el mensaje (coincidencia por palabras seguidas), páginas de PDF («página 40», «páginas 27 a 35»), selección; se ve en «Se enviará». Conversación con memoria (Claude `--resume`), ✓ Verificar citas con `verificar_citas.py` del proyecto, 🤖 Explicar error desde la consola.

## 2026-11-02 · Claude CLI en modo mínimo: 41.091 → 851 tokens fijos
`claude -p --output-format json --tools "" --strict-mcp-config --disable-slash-commands --setting-sources "" --system-prompt …`, en una carpeta neutra. `--bare` no sirve con suscripción. La carga fija medida antes de este cambio se ignora (`CARGA_V`).
Pendiente: medir Gemini (clave API: Google ya no acepta «Sign in with Google» en su CLI) y Codex (no instalado).

## 2026-11-02 · Retoques de interfaz
Columnas redimensionables (doble clic: ancho original), ⤢ pantalla completa en documento/IA/consola, ◧ ◨ y Ctrl+B / Ctrl+Alt+B para paneles, menús que no se salen de la ventana, cabecera sin duplicar (un render nuevo anula los anteriores), menú ⋮ que se cierra al pulsar en un PDF.

## 2026-11-01 · Pasos 1 a 5 del diseño original
1 Explorador y vistas (niveles 1, 2, 5 de formatos, regla universal, 🔒) · 2 Edición con CodeMirror (mismo encoding y CRLF, .bak, conflictos) · 3 Plantillas y avisos (Sin reglas / Sin bitácora / Archivar bitácora) · 4 Consola (.py .bat .ps1 …, Detener, entrada, pruebas del proyecto) · 5 IA (Conectar, reglas.md siempre enviado, cambios en rojo/verde). Estilo inspirado en Obsidian (letra de libro en documentos) y pestañas de vista previa como VS Code.

## 2026-10-31 · Origen y decisiones de base
Problema: el chat es difícil de leer y se pierde el hilo entre proyectos y chats. Decisiones: Python estándar + HTML/JS, sin instalar nada; memoria del proyecto en `.md` (`reglas.md`, `bitacora.md`; AGENTS/CLAUDE/GEMINI.md opcionales); base de datos solo como índice regenerable; editar el archivo original con respaldo; nada se ejecuta ni se envía a una IA sin que el usuario lo pulse.

## Pendientes
- [ ] Probar en la ventana real: lectura de PDF en el chat, números de página del PDF creado, panel 🔗 en uso diario.
- [ ] Medir la carga fija de Gemini y Codex cuando estén conectados.
- [ ] Probar en la ventana real la edición a mano de Word, imágenes y PDF (hecha el 2026-11-02).
- [ ] Decidir: aviso «⏳ Sin actividad», nivel 4 de formatos (LibreOffice/ffmpeg).
- [ ] Probar en el Explorador real «🪟 Abrir desde Windows» (hecho el 2026-11-04, probado solo en una clave de prueba).
- [ ] Nota de Obsidian sobre el modo mínimo de Claude: propuesta, pendiente de aprobación del usuario.
