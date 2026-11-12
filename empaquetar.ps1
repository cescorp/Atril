<#
==============================================================================================
 DeskLens · empaquetar para llevar a otro equipo
 Uso:  doble clic en empaquetar.bat     o en PowerShell:  .\empaquetar.ps1

 Crea, en esta carpeta, DeskLens-AAAA-MM-DD.zip con una carpeta «DeskLens» dentro que lleva SOLO lo necesario
 para que funcione. En el otro equipo: descomprimir donde se quiera y doble clic en instalar.bat.

 Lo que NO lleva (tus datos, se quedan en este equipo):
   - config.json   → tus proyectos, archivos sueltos y ajustes (las rutas son de este equipo)
   - historial\    → conversaciones con la IA, índice de búsqueda, recuperación y versiones
   - .git, capturas del README, notas de desarrollo (bitácora, implementación…) y zips anteriores
==============================================================================================
#>
param([switch]$SinAbrir)                          # -SinAbrir: no abre el Explorador al terminar
$ErrorActionPreference = 'Stop'
$Carpeta = $PSScriptRoot

# ---------- 1. Qué se lleva ----------
# El programa (servidor y ventana), las plantillas de reglas/bitácora que ofrece a los proyectos, el instalador
# y las pruebas que este ejecuta al final, los lanzadores de macOS/Linux y la documentación básica y licencias.
$Archivos = @(
    'desklens.pyw', 'index.html',                 # el programa
    'instalar.bat', 'instalar.ps1',               # instalador del otro equipo
    'test_desklens.py',                           # la prueba final del instalador
    'desklens.sh', 'desklens.command',            # abrir en Linux y macOS
    'README.md', 'LICENSE', 'TERCEROS.md',        # qué es, licencia y licencias de terceros
    'novedades.md'                                # versión de la copia (ⓘ de la cinta) y qué trae cada una
)
$Carpetas = @('plantillas')                       # AGENTS.md, CLAUDE.md, reglas.md… para «Sin reglas / Sin bitácora»

# Si falta algo, mejor avisar que crear un zip que luego no funcione
$faltan = @($Archivos + $Carpetas | Where-Object { -not (Test-Path (Join-Path $Carpeta $_)) })
if ($faltan.Count) { Write-Host "Faltan archivos: $($faltan -join ', '). No se crea el zip." -ForegroundColor Red; exit 1 }

# ---------- 2. Se copian a una carpeta temporal «DeskLens» ----------
# Así el zip tiene una carpeta dentro (al descomprimir no quedan los archivos sueltos por el escritorio).
$tmp = Join-Path $env:TEMP "desklens-paquete-$PID"
$destino = Join-Path $tmp 'DeskLens'
New-Item -ItemType Directory -Force $destino | Out-Null
foreach ($a in $Archivos) { Copy-Item (Join-Path $Carpeta $a) $destino }
foreach ($c in $Carpetas) { Copy-Item (Join-Path $Carpeta $c) $destino -Recurse }

# ---------- 3. Se comprime ----------
# Nombre con la fecha; si ya existe uno de hoy, se reemplaza.
$zip = Join-Path $Carpeta ("DeskLens-{0}.zip" -f (Get-Date -Format 'yyyy-MM-dd'))
if (Test-Path $zip) { Remove-Item $zip }
Compress-Archive -Path $destino -DestinationPath $zip
Remove-Item -Recurse -Force $tmp

# ---------- 4. Resumen y abrir la carpeta con el zip marcado ----------
Write-Host ""
Write-Host "Listo: $zip" -ForegroundColor Green
Write-Host ("Tamaño: {0:N0} KB · lleva: {1}, {2}\" -f ((Get-Item $zip).Length / 1KB), ($Archivos -join ', '), ($Carpetas -join '\, '))
Write-Host "No lleva tus datos: config.json ni historial\."
Write-Host ""
Write-Host "En el otro equipo: descomprime el zip y haz doble clic en DeskLens\instalar.bat." -ForegroundColor Cyan
if (-not $SinAbrir) { Start-Process explorer.exe "/select,`"$zip`"" }
