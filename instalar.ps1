<#
==============================================================================================
 DeskLens · instalador para Windows
 Se abre con doble clic en instalar.bat (o: powershell -ExecutionPolicy Bypass -File instalar.ps1)

 Qué hace, en orden (cada paso está explicado en su sección):
   1. Comprueba que existe winget, el instalador oficial de Windows 10 y 11.
   2. Python 3.10 o más nuevo      → obligatorio (el servidor de DeskLens).
   3. Git                          → recomendado (vista Git, estado en el árbol, comparar versiones).
   4. Navegador Edge o Chrome      → solo se comprueba (Edge viene con Windows).
   5. IA, opcional                 → Node.js y las CLI que elijas: Claude Code, Codex, Gemini CLI.
   6. Acceso directo «DeskLens» en el Escritorio y en el menú Inicio.
   7. Prueba final y resumen ✓ / ✗.

 Garantías:
   - No reinstala lo que ya tienes: solo informa de la versión encontrada.
   - Pregunta antes de instalar cada cosa (S/N). Lo opcional viene con «N» por defecto.
   - Todo sale de winget (repositorio oficial de Microsoft) y de npm (paquetes oficiales de cada IA).
   - No toca tus proyectos, tu config.json ni tu historial.
 Opción: -SoloRevisar  → muestra qué hay y qué falta, sin instalar ni crear nada.
==============================================================================================
#>
param([switch]$SoloRevisar)

# 'Continue': si un programa escribe avisos en su salida de error (winget, npm, git), no se corta el script;
# cada paso comprueba por sí mismo si salió bien.
$ErrorActionPreference = 'Continue'
$Carpeta = $PSScriptRoot                      # carpeta de DeskLens (donde está este script)
$Resumen = [System.Collections.Generic.List[object]]::new()   # filas del resumen final


# ---------- utilidades: mensajes, preguntas y PATH ----------

# Una línea de título para cada paso
function Titulo([string]$t) { Write-Host ""; Write-Host "── $t " -ForegroundColor Cyan }

# Anota el resultado de un paso para el resumen final (Estado: ok, falta u opcional)
function Anotar([string]$pieza, [string]$estado, [string]$detalle) {
    $Resumen.Add([pscustomobject]@{ Pieza = $pieza; Estado = $estado; Detalle = $detalle })
}

# Pregunta S/N. $porDefecto: lo que vale si solo se pulsa Enter. Con -SoloRevisar nunca instala.
function Preguntar([string]$texto, [bool]$porDefecto) {
    if ($SoloRevisar) { return $false }
    $op = if ($porDefecto) { '[S/n]' } else { '[s/N]' }
    $r = Read-Host "$texto $op"
    if ([string]::IsNullOrWhiteSpace($r)) { return $porDefecto }
    return $r.Trim().ToLower().StartsWith('s')
}

# Tras instalar algo, Windows no actualiza el PATH de esta ventana: se vuelve a leer del registro
# (el del sistema y el del usuario) para que los programas recién instalados se encuentren ya.
function Recargar-Path {
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' +
                [Environment]::GetEnvironmentVariable('Path', 'User')
}

# Instala un paquete con winget, aceptando sus licencias (las mismas que al instalarlo a mano).
# Puede aparecer la ventana de Windows que pide permiso de administrador: hay que aceptarla.
function Instalar-Winget([string]$id, [string]$nombre) {
    Write-Host "   Instalando $nombre con winget ($id)…" -ForegroundColor Yellow
    winget install --id $id -e --accept-package-agreements --accept-source-agreements
    Recargar-Path
}


# ---------- bienvenida ----------
Write-Host "DeskLens · instalador" -ForegroundColor Cyan
Write-Host "Carpeta: $Carpeta"
if ($SoloRevisar) { Write-Host "Modo -SoloRevisar: no se instalará ni se creará nada." -ForegroundColor Yellow }
elseif (-not (Preguntar "Se revisará lo necesario y se preguntará antes de instalar cada cosa. ¿Empezar?" $true)) { exit }


# ---------- 1. winget: el instalador oficial de Windows ----------
# Viene con Windows 10 (1809+) y 11 como «Instalador de aplicación» (App Installer) de Microsoft Store.
# Sin él no se puede instalar nada automáticamente, pero sí revisar.
Titulo "1. winget (instalador de Windows)"
$hayWinget = [bool](Get-Command winget -ErrorAction SilentlyContinue)
if ($hayWinget) { Write-Host "   ✓ winget disponible"; Anotar 'winget' 'ok' 'disponible' }
else {
    Write-Host "   ✗ No está winget. Instálalo desde Microsoft Store: «Instalador de aplicación» (App Installer)." -ForegroundColor Red
    Write-Host "     Mientras tanto, este script solo puede revisar; lo que falte se instala a mano."
    Anotar 'winget' 'falta' 'Microsoft Store › «Instalador de aplicación»'
}


# ---------- 2. Python 3.10 o más nuevo (obligatorio) ----------
# DeskLens solo usa la biblioteca estándar de Python: no hace falta instalar paquetes con pip.
# Se busca primero el lanzador «py» y luego «python». Se ignora el «python» falso de Windows
# (un atajo en WindowsApps que solo abre Microsoft Store y no es un Python de verdad).
Titulo "2. Python 3.10 o más nuevo"
function Buscar-Python {
    foreach ($cmd in @(@('py', '-3'), @('python'))) {
        $exe = Get-Command $cmd[0] -ErrorAction SilentlyContinue
        if (-not $exe -or $exe.Source -like '*WindowsApps*') { continue }
        try {
            # Python dice su versión y la ruta del ejecutable (para el acceso directo del paso 6)
            $extra = @($cmd | Select-Object -Skip 1)   # «-3» para el lanzador py; nada para python
            $info = & $cmd[0] @extra -c "import sys; print(sys.version_info[0], sys.version_info[1], sys.executable)" 2>$null
            if ($LASTEXITCODE -eq 0 -and $info) {
                $p = "$info".Trim() -split ' ', 3
                return [pscustomobject]@{ Mayor = [int]$p[0]; Menor = [int]$p[1]; Exe = $p[2] }
            }
        } catch { }
    }
    return $null
}
$py = Buscar-Python
$pyOk = $py -and ($py.Mayor -gt 3 -or ($py.Mayor -eq 3 -and $py.Menor -ge 10))
if (-not $pyOk -and $hayWinget) {
    $motivo = if ($py) { "Hay Python $($py.Mayor).$($py.Menor), pero DeskLens necesita 3.10 o más nuevo." } else { "No se encontró Python." }
    Write-Host "   $motivo" -ForegroundColor Yellow
    if (Preguntar "   ¿Instalar Python 3.12?" $true) { Instalar-Winget 'Python.Python.3.12' 'Python 3.12'; $py = Buscar-Python }
    $pyOk = $py -and ($py.Mayor -gt 3 -or ($py.Mayor -eq 3 -and $py.Menor -ge 10))
}
if ($pyOk) { Write-Host "   ✓ Python $($py.Mayor).$($py.Menor) · $($py.Exe)"; Anotar 'Python' 'ok' "$($py.Mayor).$($py.Menor)" }
else { Write-Host "   ✗ Falta Python 3.10+: https://www.python.org/downloads/ (marca «Add python.exe to PATH»)" -ForegroundColor Red; Anotar 'Python' 'falta' 'obligatorio' }


# ---------- 3. Git (recomendado) ----------
# DeskLens funciona sin git, pero entonces no hay vista Git, ni estado de los archivos en el árbol,
# ni comparar versiones, ni «quién escribió cada línea». Git para Windows trae también Git Bash
# (DeskLens lo usa para ejecutar archivos .sh) y el administrador de credenciales para pull/push.
Titulo "3. Git"
$git = Get-Command git -ErrorAction SilentlyContinue
if (-not $git -and $hayWinget -and (Preguntar "   No se encontró Git. ¿Instalarlo? (recomendado)" $true)) {
    Instalar-Winget 'Git.Git' 'Git'; $git = Get-Command git -ErrorAction SilentlyContinue
}
if ($git) { $v = (git --version) -replace 'git version ', ''; Write-Host "   ✓ Git $v"; Anotar 'Git' 'ok' $v }
else { Write-Host "   ✗ Sin Git: no habrá vista Git. Se puede instalar luego: https://git-scm.com" -ForegroundColor Yellow; Anotar 'Git' 'falta' 'recomendado' }


# ---------- 4. Navegador de la ventana (solo se comprueba) ----------
# La ventana de DeskLens es un navegador Chromium en «modo aplicación» (Edge, Chrome, Brave o Chromium),
# que también se usa para crear PDF. Edge viene con Windows, así que normalmente no hay que hacer nada.
# Cuál usar se elige luego en ⚙ Ajustes › General.
Titulo "4. Navegador de la ventana"
$navegadores = @(
    @{ n = 'Microsoft Edge'; r = @("${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe", "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe") },
    @{ n = 'Google Chrome';  r = @("$env:ProgramFiles\Google\Chrome\Application\chrome.exe", "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe", "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe") },
    @{ n = 'Brave';          r = @("$env:ProgramFiles\BraveSoftware\Brave-Browser\Application\brave.exe", "$env:LOCALAPPDATA\BraveSoftware\Brave-Browser\Application\brave.exe") }
)
$hay = @($navegadores | Where-Object { $_.r | Where-Object { $_ -and (Test-Path $_) } } | ForEach-Object { $_.n })
if ($hay.Count) { Write-Host "   ✓ $($hay -join ', ')"; Anotar 'Navegador' 'ok' ($hay -join ', ') }
else { Write-Host "   ✗ Ni Edge ni Chrome: DeskLens se abrirá en tu navegador de siempre, en una pestaña normal." -ForegroundColor Yellow; Anotar 'Navegador' 'falta' 'Edge o Chrome' }


# ---------- 5. IA (opcional): Node.js y las CLI de cada IA ----------
# El chat de IA de DeskLens usa las herramientas de línea de órdenes de cada empresa, con TU propia
# suscripción o cuenta: DeskLens no guarda claves. Se instalan con npm, que viene con Node.js.
# Después de instalar una, hay que iniciar sesión una vez (DeskLens tiene «Conectar IA» para eso).
Titulo "5. IA (opcional)"
# nombre, orden que deja instalada, paquete oficial de npm
$ias = @(@('Claude Code', 'claude', '@anthropic-ai/claude-code'),
         @('Codex', 'codex', '@openai/codex'),
         @('Gemini CLI', 'gemini', '@google/gemini-cli'))
$faltan = @()
foreach ($ia in $ias) {   # primero se informa de las que ya están
    if (Get-Command $ia[1] -ErrorAction SilentlyContinue) { Write-Host "   ✓ $($ia[0])"; Anotar $ia[0] 'ok' 'instalada' }
    else { $faltan += , $ia }
}
if (-not $faltan.Count) { Write-Host "   Todas instaladas." }
elseif (Preguntar "   Faltan: $(($faltan | ForEach-Object { $_[0] }) -join ', '). ¿Instalar alguna?" $false) {
    if (-not (Get-Command npm -ErrorAction SilentlyContinue) -and $hayWinget) { Instalar-Winget 'OpenJS.NodeJS.LTS' 'Node.js LTS' }
    if (Get-Command npm -ErrorAction SilentlyContinue) {
        foreach ($ia in $faltan) {
            if (-not (Preguntar "   ¿Instalar $($ia[0])?" $false)) { Anotar $ia[0] 'opcional' 'no se instaló'; continue }
            npm install -g $ia[2]
            Recargar-Path
            if (Get-Command $ia[1] -ErrorAction SilentlyContinue) { Anotar $ia[0] 'ok' "instalada · inicia sesión con: $($ia[1])" }
            else { Anotar $ia[0] 'falta' "npm install -g $($ia[2])" }
        }
    } else { Write-Host "   ✗ No hay Node.js/npm: instálalo desde https://nodejs.org y vuelve a ejecutar." -ForegroundColor Yellow; Anotar 'IA' 'falta' 'Node.js' }
} else { foreach ($ia in $faltan) { Anotar $ia[0] 'opcional' 'no instalada' } }


# ---------- 6. Acceso directo «DeskLens» (Escritorio y menú Inicio) ----------
# Abre desklens.pyw con pythonw.exe (el Python sin ventana negra). La carpeta de trabajo es la de
# DeskLens, para que encuentre su config.json e historial/.
Titulo "6. Acceso directo"
$pyw = if ($py) { Join-Path (Split-Path $py.Exe) 'pythonw.exe' } else { $null }
$yaHay = Test-Path (Join-Path ([Environment]::GetFolderPath('Desktop')) 'DeskLens.lnk')
if ($yaHay) { Write-Host "   ✓ Ya hay un acceso directo «DeskLens» en el Escritorio" }
if (-not $pyOk -or -not $pyw -or -not (Test-Path $pyw)) { Write-Host "   (sin Python no se puede crear)"; Anotar 'Acceso directo' 'falta' 'necesita Python' }
elseif ($SoloRevisar) { Anotar 'Acceso directo' $(if ($yaHay) { 'ok' } else { 'opcional' }) $(if ($yaHay) { 'en el Escritorio' } else { 'no creado' }) }
elseif (Preguntar "   ¿Crear el acceso directo «DeskLens» en el Escritorio y en el menú Inicio?" $true) {
    $shell = New-Object -ComObject WScript.Shell
    foreach ($dir in @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs'))) {
        $lnk = $shell.CreateShortcut((Join-Path $dir 'DeskLens.lnk'))
        $lnk.TargetPath = $pyw
        $lnk.Arguments = '"' + (Join-Path $Carpeta 'desklens.pyw') + '"'
        $lnk.WorkingDirectory = $Carpeta
        $lnk.Description = 'DeskLens: visor y editor local de proyectos, con git e IA'
        $lnk.Save()
    }
    Write-Host "   ✓ Creado en el Escritorio y en el menú Inicio"; Anotar 'Acceso directo' 'ok' 'Escritorio y menú Inicio'
} else { Anotar 'Acceso directo' 'opcional' 'no se creó' }


# ---------- 7. Prueba final y resumen ----------
# Las pruebas de DeskLens (test_desklens.py) no abren ventanas ni tocan tus datos: usan una carpeta
# temporal. Necesitan Git (prueban la vista Git con un repositorio de juguete).
Titulo "7. Prueba final"
if ($pyOk -and $git -and -not $SoloRevisar) {
    Push-Location $Carpeta
    try {
        $salida = & $py.Exe test_desklens.py 2>&1 | Select-Object -Last 3
        if ($LASTEXITCODE -eq 0) { Write-Host "   ✓ $($salida | Select-Object -Last 1)"; Anotar 'Pruebas' 'ok' 'todas pasan' }
        else { Write-Host ($salida -join "`n") -ForegroundColor Red; Anotar 'Pruebas' 'falta' 'ver el error de arriba' }
    } finally { Pop-Location }
} else { Write-Host "   (se omite: hace falta Python y Git, o es -SoloRevisar)" }

Titulo "Resumen"
foreach ($f in $Resumen) {
    $marca, $color = switch ($f.Estado) { 'ok' { '✓', 'Green' } 'falta' { '✗', 'Red' } default { '·', 'DarkGray' } }
    Write-Host ("   {0} {1,-16} {2}" -f $marca, $f.Pieza, $f.Detalle) -ForegroundColor $color
}
Write-Host ""
if ($pyOk) { Write-Host "Listo. Abre DeskLens con el acceso directo o con doble clic en desklens.pyw." -ForegroundColor Cyan }
else { Write-Host "Falta Python: instálalo y vuelve a ejecutar instalar.bat." -ForegroundColor Red }
