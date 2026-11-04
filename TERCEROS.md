# Software de terceros

DeskLens no incluye copias de estas bibliotecas: la ventana las carga desde una CDN (cdnjs.cloudflare.com, cdn.jsdelivr.net) la primera vez que hacen falta. El servidor (`desklens.pyw`) solo usa la biblioteca estándar de Python.

| Biblioteca | Versión | Para qué | Licencia |
|---|---|---|---|
| [pdf.js](https://github.com/mozilla/pdf.js) | 3.11.174 | Ver PDF, leer su texto, buscar | Apache 2.0 |
| [pdf-lib](https://github.com/Hopding/pdf-lib) | 1.17.1 | Editar PDF (texto, resaltado, páginas) | MIT |
| [docx-preview](https://github.com/VolodymyrBaydalka/docxjs) | 0.3.2 | Ver y editar Word | Apache 2.0 |
| [JSZip](https://github.com/Stuk/jszip) | 3.10.1 | Lo usa docx-preview | MIT o GPLv3 (a elegir) |
| [mammoth.js](https://github.com/mwilliamson/mammoth.js) | 1.8.0 | Word sin docx-preview; texto de un Word soltado | BSD 2-Clause |
| [CodeMirror 5](https://github.com/codemirror/codemirror5) | 5.65.16 | Editor de código, comparador | MIT |
| [diff-match-patch](https://github.com/google/diff-match-patch) | 20121119 | Lo usa el comparador de CodeMirror | Apache 2.0 |
| [highlight.js](https://github.com/highlightjs/highlight.js) | 11.9.0 | Colores del código en lectura | BSD 3-Clause |
| [marked](https://github.com/markedjs/marked) | 12.0.2 | Markdown | MIT |
| [DOMPurify](https://github.com/cure53/DOMPurify) | 3.1.6 | Limpiar el HTML que se muestra | Apache 2.0 o MPL 2.0 |
| [Source Serif 4](https://fonts.google.com/specimen/Source+Serif+4), [Inter](https://fonts.google.com/specimen/Inter) | Google Fonts | Letra de lectura e interfaz | SIL Open Font License 1.1 |

Las IA (Claude Code, Codex, Gemini CLI) no forman parte de DeskLens: son programas aparte que cada usuario instala y conecta con su propia cuenta.
