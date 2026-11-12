# Reglas de DeskLens
Normas estables del proyecto, una por línea.

- Aprovechar el ancho de escritorio: modales y paneles anchos, en columnas o rejilla; nada de columnas estrechas con scroll largo.
- Usar la skill de diseño (frontend-design) en todas las mejoras de interfaz, manteniendo los colores y la letra de DeskLens.
- Nunca usar alert, confirm ni prompt del navegador. Usar siempre `ask()`, el modal centrado de DeskLens. Sus botones nombran la acción (Quitar/Cancelar, Guardar/Cancelar, Entendido…), y lo que borra o descarta va en rojo con `{ danger: true }`.
- Comentarios del código en tono técnico, para quien lo mantenga: qué hace, por qué y qué límite tiene. Sin narrar ni contar lo que se hizo.
- Cada cambio es una versión nueva: al terminar, añadir arriba en `novedades.md` `## vX.N+1 · AAAA-MM-DD · título` y 1–3 líneas en lenguaje sencillo (qué gana el usuario, no cómo se hizo).
- Todo clic responde al instante: la ventana marca lo elegido (y ⏳ si tarda) antes de esperar al servidor; si falla, vuelve a como estaba y avisa. Las llamadas que no dependen entre sí van en paralelo (en el servidor y en la ventana).
