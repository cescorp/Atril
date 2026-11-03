# Formatos de Atril
Los ~380 formatos de la lista se pueden abrir todos, pero no todos igual: unos se ven y editan, otros solo se ven y otros solo muestran una ficha con botón para abrirlos en Windows.

## Regla universal (cubre cualquier extensión, incluso las que no están en la lista)
1. Si la extensión es conocida → se usa su vista.
2. Si no: se miran los primeros 8 KB. Sin bytes nulos = **es texto** → se muestra y edita como texto.
3. Si es binario desconocido → **ficha**: nombre, tamaño, fecha, tipo + botón "Mostrar en carpeta" o "Abrir con el programa de Windows".
   - Ejecutables e instaladores **nunca** se abren con doble clic desde Atril: solo "Mostrar en carpeta".

## Resumen

| Nivel | Qué hace Atril | ¿Instalar algo? | Formatos aprox. |
|---|---|---|---|
| 1. Texto | Ver con colores + **editar** + ejecutar (scripts) | No | ~170 |
| 2. Nativo del navegador | Ver / reproducir | No | ~35 |
| 3. Con librería web | Ver (solo lectura) | No (librerías JS desde CDN) | ~60 |
| 4. Programa externo | Ver tras convertir | Sí (LibreOffice, ffmpeg…) | ~60 |
| 5. Sin vista útil | Ficha + mostrar en carpeta | — | ~55 |

## Nivel 1 — Texto: ver, editar, resaltar (0 instalaciones)
| Grupo | Extensiones |
|---|---|
| Documentos de texto | txt, text, md, markdown, mdx, rst, tex, bib, rmd, log, diff, patch |
| PHP / web | php, phtml, php3, php4, php5, html, htm, xhtml, css, scss, sass, less, js, mjs, cjs, jsx, ts, tsx, vue, svelte, astro, svg |
| Python y ciencia | py, pyw, pyx, r, jl, m, ipynb (se ve como cuaderno: celdas y resultados) |
| Otros lenguajes | java, kt, kts, scala, sc, groovy, gradle, c, h, cc, cpp, cxx, hpp, hh, cs, csx, vb, vbs, bas, cls, frm, vba, rs, go, rb, rake, pl, pm, lua, swift, mm, dart, ex, exs, erl, hrl, hs, lhs, elm, clj, cljs, fs, fsx, fsi, asm, s, ino |
| Scripts | ps1, psm1, psd1, bat, cmd, sh, bash, zsh, fish, awk, sed |
| Build / infra | Makefile, mk, cmake, Dockerfile, tf, hcl, proto, graphql, gql, gitignore, gitattributes, editorconfig |
| Datos y config | json, jsonc, json5, xml, xsd, xsl, xslt, yaml, yml, toml, ini, cfg, conf, properties, sql, psql, pgsql |
| Tablas | csv, tsv, psv → se ven como **tabla** y se editan como texto |
| Otros de texto | srt, ass, ssa, vtt, m3u, m3u8, pls, ics, vcf, eml, mbox, geojson, kml, gpx, prj, ovf, unity, ma, obj, dxf, step, stp, iges, igs |

Ejecutables desde la consola: py, pyw, bat, cmd, ps1, sh/bash (con Git Bash), vbs, js (Node), php (si PHP está instalado).

## Nivel 2 — El navegador lo muestra solo (0 instalaciones)
| Grupo | Extensiones |
|---|---|
| Documentos | pdf, html (renderizado) |
| Imágenes | jpg, jpeg, jpe, png, gif, bmp, dib, webp, avif, ico, svg |
| Audio | mp3, wav, flac, aac, m4a, ogg, oga, opus |
| Video | mp4, m4v, webm, ogv, mov (si es H.264) |
| Fuentes | ttf, otf, woff, woff2 → muestra del alfabeto con esa letra |

## Nivel 3 — Con librería web (solo lectura, 0 instalaciones en el PC)
| Grupo | Extensiones | Cómo |
|---|---|---|
| Word | docx | mammoth.js |
| Excel / hojas | xlsx, xlsm, xls, xlsb, xltx, xltm, ods | SheetJS (tablas por hoja; macros no se ejecutan) |
| Libros | epub, fb2, mobi/azw3 sin DRM | epub.js / lectores JS (mobi parcial) |
| Texto enriquecido | rtf | rtf.js (formato básico) |
| Imágenes especiales | tif, tiff, heic, heif, psd, kra, ora, exr, hdr | UTIF, heic2any, ag-psd; kra/ora traen un PNG dentro |
| Vista previa interna | pages, numbers, key, sketch | son ZIP con una miniatura dentro: se ve la miniatura |
| Illustrator | ai | si se guardó "compatible con PDF" se ve como PDF |
| 3D | stl, obj, gltf, glb, fbx, 3ds | three.js (girar y hacer zoom) |
| Planos | dxf | dxf-viewer |
| Mapas | geojson, kml, kmz, gpx, shp | Leaflet (el mapa de fondo necesita internet) |
| Bases de datos | db, sqlite, sqlite3 | sql.js: ver tablas y consultar, solo lectura |
| Comprimidos | zip, jar, apk, aab, ipa, tar, gz, tgz | listar contenido y abrir un archivo de dentro |
| Correo | eml, msg | ver remitente, asunto, cuerpo y adjuntos |
| Música | mid, midi | reproductor MIDI |
| RAW de cámara | raw, dng, cr2, cr3, nef, nrw, arw, srf, sr2, raf, orf, rw2, pef, 3fr, fff, iiq | se muestra el JPEG de vista previa que traen dentro (no es revelado completo) |
| Otros | djvu, dbf | djvu.js; dbf como tabla |

## Nivel 4 — Necesita un programa instalado (decidir más adelante)
| Programa | Formatos que desbloquea |
|---|---|
| LibreOffice (gratis) | doc, wps, wpd, odt, odp, ppt, pps, pptx, pptm, ppsx, potx, xps, oxps → convertidos a PDF para verlos fieles |
| ffmpeg (gratis) | avi, mkv, wmv, flv, f4v, mpeg, mpg, m2v, 3gp, 3g2, mts, m2ts, vob, asf, rm, rmvb, wma, aiff, aif, amr, ape, dsf, dff |
| Ghostscript (gratis) | eps, ps |
| Driver de Access | mdb, accdb |
| Sin opción gratuita fiable | dwg, dgn, cdr, cmx, indd, idml, xd, fig, afdesign, afphoto, xcf, blend, max, mb, fits → nivel 5 hasta que haga falta |

## Nivel 5 — Sin vista útil: ficha + "Mostrar en carpeta"
exe, msi, msp, msix, appx, dll, sys, drv, so, dylib, bin, dat, wasm, class, phar, iso, img, dmg, vhd, vhdx, vmdk, vdi, ova, deb, rpm, appimage, 7z, rar, cab, xz, zst, lz, lzma, bz2, tbz, txz, pst, ost, unitypackage, uasset, umap, fon, eot, cur, ani, icns, shx, pbf, idx, frx, xla, xlam

## 🔒 Archivos sensibles: se ven, pero NUNCA se envían a la IA
env, pem, key (si es clave), p12, pfx, gpg, pgp, asc, crt, cer, der, p7b, p7c, csr
- Se marcan con 🔒 en el explorador.
- El chat con IA bloquea cualquier envío de estos archivos o de fragmentos suyos.
- Los binarios (p12, pfx, der, gpg) muestran solo la ficha.

## Correcciones a la lista original
| Entrada | Observación |
|---|---|
| .ipynb_checkpoints | Es una **carpeta** de Jupyter, no una extensión → Atril la oculta |
| .dockerfile | El nombre habitual es `Dockerfile`, sin extensión → se reconocen ambos |
| .alac | No existe como extensión: el audio ALAC va dentro de `.m4a` |
| .key | Ambiguo: Keynote (ZIP) o clave privada (texto) → se detecta por contenido |
| .m | Objective-C o MATLAB: los dos son texto, se ven bien igual |
| .cls | Clase VBA o clase LaTeX: los dos son texto |
| .fig | Figma o figura MATLAB: ninguno tiene vista libre → ficha |
| .sub | Puede ser texto (MicroDVD) o binario (DVD con `.idx`) → detección automática |
| .ovf, .unity, .ma, .prj, .mbox, .dxf, .obj, .step | En la lista parecen binarios, pero son texto → nivel 1 |

## Recomendación de orden
1. **Niveles 1, 2 y 5 + regla universal + 🔒**: cubren lo que se usa a diario (Laravel, Python, .bat, PowerShell, Markdown, PDF, imágenes) sin instalar nada.
2. **Nivel 3 por demanda**: primero docx, xlsx/csv, ipynb y zip; el resto cuando aparezca un archivo real que lo necesite.
3. **Nivel 4**: solo si se decide instalar LibreOffice o ffmpeg.

Origen: Atril · 2026-10-31
