# Novedades de DeskLens
Cada cambio es una versión nueva, la más reciente arriba. El número de la primera es el que sale en ⓘ (arriba en la cinta).

## v1.122 · 2026-11-13 · Sombrear lo que seleccionas y ver los cambios al editar a mano
- Al seleccionar una palabra o trozo de una línea, todas sus apariciones se sombrean en amarillo: en el editor, en la lectura y en las comparaciones al fusionar (en el editor también se marcan en la barra de scroll).
- «Editar manualmente» colorea en verde las líneas distintas de lo que tienes ahora y pone una raya roja donde se quitó algo; la barra de la derecha lo resume y lleva a cada cambio.
- La barra de marcas de cambios es más ancha y se ve mejor.

## v1.121 · 2026-11-13 · Comparar en dos columnas al elegir versión
- Cada pestaña enseña dos columnas que se mueven juntas: a la izquierda lo que tienes ahora y a la derecha cómo quedará. En rojo lo que se quita y en verde lo que se añade.
- «Dejar mi cambio» también enseña los dos archivos, con el aviso «✓ Tu archivo no cambia».

## v1.120 · 2026-11-13 · Elegir versión en pestañas
- «👁 Ver y elegir» es ahora una ventana más pequeña con una pestaña por opción (Unificar cambios, Dejar mi cambio, Dejar cambio que llega, Editar manualmente): la que ves es la que eliges.
- Cada pestaña compara con lo que tienes ahora: en rojo lo que se quitaría de tu archivo y en verde lo que se añadiría («✓ Tu archivo no cambia» si nada cambia). Barra a la derecha con marcas de los cambios.
- «Editar manualmente» siempre disponible en los archivos de texto. Azul marino para lo elegido, más sobrio.

## v1.119 · 2026-11-13 · Elegir con un clic y editar manualmente al fusionar
- En «👁 Ver las dos», cada columna se resalta al pasar el ratón y se elige con un clic. Los cambios van en negrita, el resto más tenue, y cada columna se abre centrada en su primer cambio.
- Nombres más claros: «Dejar mi cambio», «Dejar cambio que llega», «Dejar los dos cambios» y «Editar manualmente».
- «Editar manualmente» se hace ahí mismo: empieza con los dos cambios juntos, «Guardar y volver a la lista» y se escribe al fusionar. Cada archivo de la lista muestra lo elegido («✓ Dejar mi cambio», «✎ Editado manualmente»).

## v1.118 · 2026-11-13 · Fusionar y traer cambios en una sola pantalla
- ⤵ Fusionar, Pull y «Pull desde» abren una sola pantalla que lo comprueba todo antes de tocar nada: los commits que llegan, los conflictos, tus cambios sin commit en archivos que también llegan, archivos nuevos tuyos con el mismo nombre y archivos abiertos en otro programa.
- Cada archivo con algo que elegir dice qué pasa y qué hará cada opción («Juntar las dos», «Quedarme con la mía», «Quedarme con la que llega», «Mezclar a mano», «Borrarlo»…). Las vistas previas se abren en otra ventana encima.
- «Fusionar» lo hace todo de una vez; solo «Mezclar a mano» abre el editor para terminar.

## v1.117 · 2026-11-13 · Vista previa de la fusión más clara
- Arriba, la respuesta en grande: «✅ Se puede fusionar sin problemas», «⚠️ Hay N archivos que tendrás que elegir» o «✅ Ya tienes todo».
- Se ven los commits que llegan (fecha, autor y mensaje) y cada archivo con lo que le pasará, en letra normal y con «👁 Ver cambios».

## v1.116 · 2026-11-13 · Fusionar con vista previa y conflictos explicados
- Antes de fusionar, una vista previa dice qué pasará con cada archivo (se une solo, llega nuevo, se borra o tendrás que elegir), sin tocar nada.
- Durante una fusión, la vista Git dice qué se fusiona y si hay conflictos, con «⚔ Ver y elegir», «✓ Confirmar la fusión» o «✕ Cancelar la fusión».
- Cada conflicto se resuelve con dos botones que dicen el resultado («Quedarme con MI versión», «Borrar el archivo»…); «👁 Ver diferencias» enseña las dos versiones y cómo quedará. Al final, un resumen antes de hacer el commit.

## v1.115 · 2026-11-13 · Historial de cada línea
- Al editar, a la derecha de la línea sale `[💾N ⎇N]`: cuántas veces cambió en disco y en commits de git. Al pulsarlo, el historial de esa línea en dos pestañas (💾 Ediciones en disco en azul, ⎇ Commits de git en morado) con el antes y después pintado.
- «⤢ Ver en su contexto»: el archivo entero en esa versión, con la línea resaltada y lo demás atenuado, ◀ ▶ entre versiones y ← Volver.
- «↩ Volver a esta versión» cambia solo esa línea en el editor; «⇆ Ver el commit entero» muestra sus archivos.

## v1.114 · 2026-11-13 · Línea sombreada, Guardar vuelve a lectura y Ctrl+A en casi todo
- Al pasar el ratón se sombrea la fila con su número, al leer y al editar; al editar, la línea del cursor queda marcada. En Markdown, tablas y cuadernos se sombrea el párrafo, la fila o la celda.
- El botón Guardar guarda y vuelve a lectura en la misma línea; Ctrl+S guarda sin salir de la edición.
- Ctrl+A también en la consola (su salida) y en el panel de IA (la conversación), nunca toda la ventana.

## v1.113 · 2026-11-13 · Ctrl+A selecciona solo el documento
- En lectura, Ctrl+A selecciona solo el texto del archivo abierto (sin árbol, pestañas ni números de línea); con la vista dividida, solo el lado activo.
- En cuadros de texto, el editor y la consola sigue como siempre.

## v1.112 · 2026-11-13 · Descartar un cambio desde el aviso de fusionar
- En la tabla de «No se puede fusionar», cada archivo tiene «↶ Descartar» (pide confirmación). Cuando ya no queda ninguno, se fusiona sola.

## v1.111 · 2026-11-13 · Fusionar con cambios sin commit: se explica y se resuelve
- Antes, merge o pull fallaban con «Your local changes… would be overwritten» y no decían qué hacer.
- Ahora sale una tabla con esos archivos (tus cambios, fecha, tamaño y qué hizo la otra rama), ordenable por columnas, y dos salidas que no pierden nada: «Commit y fusionar» o «Guardar aparte y fusionar».

## v1.110 · 2026-11-12 · Detalle del commit más compacto
- La cabecera ocupa dos líneas: título, autor, fecha, rama y archivos. El resto (mensaje completo, email, padres, ramas) se abre con «▸ Ver detalle» y se recuerda.
- Ver y Abrir pasan a la primera columna de la tabla de archivos.

## v1.109 · 2026-11-12 · «✅ En orden» también solo si lo pides
- Va con el mismo ajuste que «Sin reglas» y «Sin bitácora» (⚙ Ajustes › Bitácora).

## v1.108 · 2026-11-12 · Avisos «Sin reglas» y «Sin bitácora» solo si los pides
- Ya no salen por defecto. Se activan en ⚙ Ajustes › Bitácora.
- Sirven para trabajar con IA: `reglas.md` guarda las normas del proyecto y `bitacora.md` todo lo realizado, así un chat nuevo retoma el trabajo sin volver a explicarlo.

## v1.107 · 2026-11-12 · Novedades y número de versión
- Icono ⓘ arriba en la cinta con la versión de esta copia; al pulsarlo, la lista de versiones y qué trae cada una.
- Sirve para saber si una copia en otro equipo está al día: si el número no coincide, una de las dos es más vieja.

## v1.106 · 2026-11-11 · «Ver» de un commit ya no sale vacío
- Si el archivo no cambió después de ese commit, se compara el antes y el después del commit.

## v1.105 · 2026-11-07 · Máximo de pestañas de consola en Ajustes
- ⚙ Ajustes › Consola: cuántas pestañas se guardan (5 por defecto). Las que siguen en marcha nunca se quitan.

## v1.104 · 2026-11-07 · El servidor ya no se apaga con la ventana abierta
- Tras suspender el PC salía «Failed to fetch». Ahora solo se apaga al cerrar la ventana.

## v1.103 · 2026-11-05 · «Abrir con…» funciona con rutas con espacios

## v1.102 · 2026-11-05 · Vista previa en vivo del .md/.html en el otro lado
- Con la misma pestaña en los dos lados, lo que escribes en uno se ve al momento en el otro.

## v1.101 · 2026-11-05 · Duplicar pestaña a la derecha o abajo

## v1.100 · 2026-11-05 · 🐞 Depurar paso a paso: Batch (.bat/.cmd)

## v1.99 · 2026-11-05 · 🐞 Depurar paso a paso: JavaScript

## v1.98 · 2026-11-05 · 🐞 Depurar paso a paso: Python
- Puntos de parada con clic en el margen; Continuar (F5), Paso (F10), Entrar (F11) y Salir (Mayús+F11).

## v1.97 · 2026-11-05 · Migas del código: archivo › clase › función

## v1.96 · 2026-11-05 · Tema claro/oscuro en Ajustes y plegar bloques de código

## v1.95 · 2026-11-05 · Colores de código como VS Code, al leer y al editar

## v1.94 · 2026-11-05 · La marca azul del cursor salía en otro sitio

## v1.93 · 2026-11-05 · Proyecto sin git: empezar a usar git y conectar con un servidor

## v1.92 · 2026-11-05 · Rama abierta en otra carpeta (worktree)

## v1.91 · 2026-11-05 · Volver a Git a pantalla completa al cerrar el archivo

## v1.90 · 2026-11-05 · Instalador: arreglado el error con winget

## v1.89 · 2026-11-05 · Empaquetar para otro equipo
- `empaquetar.bat` crea un .zip con solo lo necesario, sin tus datos.

## v1.88 · 2026-11-05 · Una ventana o varias

## v1.87 · 2026-11-05 · «Reiniciar ahora» y nunca dos servidores en el mismo puerto

## v1.86 · 2026-11-04 · «Ver» del detalle del commit: Disco (actual) a la izquierda

## v1.85 · 2026-11-04 · Día/Semana/Mes en el título del gráfico

## v1.84 · 2026-11-04 · «Unir autores»: ancho según los proyectos

## v1.83 · 2026-11-04 · «Unir autores» rehecho: filas por persona, columnas por proyecto

## v1.82 · 2026-11-04 · Estadística de varios proyectos juntos y «Unir autores»

## v1.81 · 2026-11-04 · Estadística: bloques que se arrastran y se pliegan

## v1.80 · 2026-11-04 · Estadística: los números no se salen de su tarjeta

## v1.79 · 2026-11-04 · 📊 Estadística (parte 2): palabras y horas por cambios

## v1.78 · 2026-11-04 · 📊 Estadística de Git (parte 1)

## v1.77 · 2026-11-04 · Nº de archivos en cada fila del historial de Git

## v1.76 · 2026-11-04 · Proyectos con el mismo nombre

## v1.75 · 2026-11-04 · Terminal para escribir órdenes

## v1.74 · 2026-11-04 · Consola: como mucho 7 pestañas

## v1.73 · 2026-11-04 · Abrir con… y DeskLens en Windows

## v1.72 · 2026-11-04 · La consola de git se oculta sola al terminar bien

## v1.71 · 2026-11-04 · Menú de ramas: Pull desde, Push a, clic derecho y Fusionar

## v1.70 · 2026-11-04 · Pestaña 🙈 Ignorados en Git

## v1.69 · 2026-11-04 · Panel de proyecto y ramas más claro

## v1.68 · 2026-11-04 · Comparador al instante y ⋮ más fácil de pulsar

## v1.67 · 2026-11-04 · Lista de versiones compacta

## v1.66 · 2026-11-04 · Pantalla de Git ajustable y recordada

## v1.65 · 2026-11-04 · Listas de commits más fáciles de leer

## v1.64 · 2026-11-04 · Historial de Git más sencillo

## v1.63 · 2026-11-04 · Todo clic responde al instante y Git más rápido

## v1.62 · 2026-11-04 · Dos sesiones en la misma carpeta

## v1.61 · 2026-11-04 · Detalle del commit: tabla ordenable y datos completos

## v1.60 · 2026-11-04 · Instalador: comandos visibles y sin winget

## v1.59 · 2026-11-04 · Cambiar de rama con cambios sin commit

## v1.58 · 2026-11-04 · Instalador para Windows

## v1.57 · 2026-11-04 · Git a pantalla completa con grafo

## v1.56 · 2026-11-04 · Git: Sincronizar y comprobar cambios solo

## v1.55 · 2026-11-04 · Atril pasa a llamarse DeskLens

## v1.54 · 2026-11-04 · Elegir el navegador de la ventana

## v1.53 · 2026-11-04 · Vista Git: commit, ramas, pull, push y merge

## v1.52 · 2026-11-04 · Ctrl+J para la IA, Ctrl+G ir a la línea

## v1.51 · 2026-11-04 · Revisión técnica y mejoras de uso

## v1.50 · 2026-11-03 · Código comentado

## v1.49 · 2026-11-03 · El documento se pintaba encima del panel de IA

## v1.48 · 2026-11-03 · Atajo para el panel de IA

## v1.47 · 2026-11-03 · Pestaña web: no se recarga al cambiar de pestaña

## v1.46 · 2026-11-03 · La ventana entera se desplazaba hacia un lado

## v1.45 · 2026-11-03 · Capturas para el README

## v1.44 · 2026-11-03 · Vista dividida, comparar archivos y pestaña web

## v1.43 · 2026-11-03 · Funciona en Windows, macOS y Linux

## v1.42 · 2026-11-03 · Avisos propios en lugar de los del navegador

## v1.41 · 2026-11-03 · Panel de IA sin 🧹 Limpiar

## v1.40 · 2026-11-03 · La IA recibe la página del PDF que se ve

## v1.39 · 2026-11-03 · Pestañas: Ctrl+W, Ctrl+Tab y arrastrar

## v1.38 · 2026-11-03 · PDF: hueco a la izquierda

## v1.37 · 2026-11-03 · PDF en blanco

## v1.36 · 2026-11-03 · Vista «Buscar» aparte

## v1.35 · 2026-11-03 · Clic derecho en pestañas

## v1.34 · 2026-11-03 · Imprimir

## v1.33 · 2026-11-03 · Clic derecho propio

## v1.32 · 2026-11-03 · Árbol y archivo abierto se actualizan solos

## v1.31 · 2026-11-03 · Orden del árbol por proyecto

## v1.30 · 2026-11-03 · Comparador: pestaña «Archivos»

## v1.29 · 2026-11-03 · Comparador: archivos de cada commit

## v1.28 · 2026-11-03 · Comparador: lista de cambios y mapa

## v1.27 · 2026-11-03 · Quién escribió cada línea en el comparador

## v1.26 · 2026-11-03 · Comparar versiones (git)

## v1.25 · 2026-11-03 · Buscar y reemplazar como VS Code

## v1.24 · 2026-11-03 · «Añadir proyecto o archivo suelto» rehecho

## v1.23 · 2026-11-03 · Atajos de edición de VS Code en el editor

## v1.22 · 2026-11-03 · ⚙ Ajustes rehecho a lo ancho, con filtro

## v1.21 · 2026-11-02 · Aviso «Cambios sin guardar»

## v1.20 · 2026-11-02 · Historial de cambios (↶ ↷) en disco

## v1.19 · 2026-11-02 · Visor de PDF propio

## v1.18 · 2026-11-02 · Editar PDF

## v1.17 · 2026-11-02 · Editar imágenes

## v1.16 · 2026-11-02 · Editar un Word a mano

## v1.15 · 2026-11-02 · Imágenes y cualquier archivo en el chat

## v1.14 · 2026-11-02 · Arrastrar al chat

## v1.13 · 2026-11-02 · Envío inmediato y cambios de la IA sin doble paso

## v1.12 · 2026-11-02 · Chat vinculado a la pestaña

## v1.11 · 2026-11-02 · Cambiar formato de un Word desde el chat

## v1.10 · 2026-11-02 · Buscador con Aa / nombre / contenido

## v1.9 · 2026-11-02 · Nuevo archivo/carpeta, «nuevo 1», recuperación y ⚙ Ajustes

## v1.8 · 2026-11-02 · Índice de búsqueda, git por archivo e (i) información

## v1.7 · 2026-11-02 · Crear .docx y .pdf desde el chat

## v1.6 · 2026-11-02 · Posición y tamaño de la ventana recordados

## v1.5 · 2026-11-02 · Panel de IA rehecho como un solo chat

## v1.4 · 2026-11-02 · Claude gasta muchos menos tokens fijos

## v1.3 · 2026-11-02 · Retoques de interfaz

## v1.2 · 2026-11-01 · Explorador, edición, plantillas, consola e IA

## v1.1 · 2026-10-31 · Primera versión
