<#
==============================================================================================
 DeskLens · instalador para Windows (también Windows Server)
 Uso:  doble clic en instalar.bat          o en PowerShell:  .\instalar.ps1
       .\instalar.ps1 -SoloRevisar         → solo informa: no pregunta ni ejecuta nada

 Cómo trabaja: en cada paso dice qué encontró, MUESTRA EL COMANDO exacto que ejecutaría
 (línea que empieza por «>») y pregunta «¿Ejecutar? (s/n)». Enter = la opción en mayúscula.

 Pasos:
   1. Python 3.10 o más nuevo   → obligatorio (el servidor de DeskLens; solo biblioteca estándar).
   2. Git                       → recomendado (vista Git, estado en el árbol, comparar versiones).
   3. Navegador Edge/Chrome     → solo se comprueba (la ventana de DeskLens y los PDF).
   4. IA (opcional)             → Node.js y las CLI de Claude, Codex o Gemini, con npm.
   5. Acceso directo «DeskLens» en el Escritorio y en el menú Inicio.
   6. Prueba final (python test_desklens.py) y resumen.

 De dónde se instala:
   - Con winget (Windows 10/11): del repositorio oficial de Microsoft.
   - Sin winget (p. ej. Windows Server): se descarga el instalador oficial de python.org, del GitHub de
     Git para Windows o de nodejs.org, y ANTES de ejecutarlo se comprueba su firma digital (que lo firmó
     quien debe y que no se modificó). Si la firma no es válida, no se ejecuta.
 No toca tus proyectos, tu config.json ni tu historial.
==============================================================================================
#>
param([switch]$SoloRevisar)

# 'Continue': si un programa escribe avisos en su salida de error (winget, npm, git), no se corta el
# script; cada paso comprueba por sí mismo si salió bien.
$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'      # la barra de progreso de las descargas las hace muy lentas en PS 5.1
# Windows Server antiguos usan TLS 1.0 por defecto y python.org/GitHub/nodejs.org exigen TLS 1.2
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12

$Carpeta = $PSScriptRoot                      # carpeta de DeskLens (donde está este script)
$Resumen = [System.Collections.Generic.List[object]]::new()
$EsAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
$HayWinget = [bool](Get-Command winget -ErrorAction SilentlyContinue)


# =========================== utilidades ===========================

# Título de cada paso
function Titulo([string]$t) { Write-Host ""; Write-Host "== $t" -ForegroundColor Cyan }

# Marcas que se ven bien en cualquier consola (los símbolos ✓/✗ salen como «V» y «?» en algunas)
function Ok([string]$t)    { Write-Host "   [OK]    $t" -ForegroundColor Green }
function Falta([string]$t) { Write-Host "   [FALTA] $t" -ForegroundColor Red }
function Info([string]$t)  { Write-Host "   $t" }

# Resultado de un paso para el resumen final. Estado: ok, falta u opcional.
function Anotar([string]$pieza, [string]$estado, [string]$detalle) {
    $Resumen.Add([pscustomobject]@{ Pieza = $pieza; Estado = $estado; Detalle = $detalle })
}

# Muestra el comando y pregunta si se ejecuta. $si: lo que vale con solo Enter. -SoloRevisar: nunca.
function Confirmar([string[]]$comandos, [bool]$si) {
    foreach ($c in $comandos) { Write-Host "   > $c" -ForegroundColor Yellow }
    if ($SoloRevisar) { Write-Host "   (no se ejecuta: -SoloRevisar)" -ForegroundColor DarkGray; return $false }
    $op = if ($si) { '(S/n)' } else { '(s/N)' }
    $r = Read-Host "   ¿Ejecutar? $op"
    if ([string]::IsNullOrWhiteSpace($r)) { return $si }
    return $r.Trim().ToLower().StartsWith('s')
}

# Tras instalar algo, el PATH de esta ventana no se actualiza solo: se vuelve a leer del registro
# (el del sistema y el del usuario) para encontrar ya los programas recién instalados.
function Recargar-Path {
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')
}

# winget: instala o actualiza un paquete aceptando sus licencias (las mismas que al instalarlo a mano).
# Puede salir la ventana de Windows que pide permiso de administrador: hay que aceptarla.
function Winget-Texto([string]$verbo, [string]$id) { "winget $verbo --id $id -e --accept-package-agreements --accept-source-agreements" }
function Winget([string]$verbo, [string]$id) {
    winget $verbo --id $id -e --accept-package-agreements --accept-source-agreements
    Recargar-Path
}

# Sin winget: descarga el instalador oficial a la carpeta temporal y comprueba su firma digital.
# $firma: texto que debe aparecer en el nombre de quien lo firmó. Devuelve la ruta, o $null si algo falla.
function Descargar-Firmado([string]$url, [string]$firma) {
    $archivo = Join-Path $env:TEMP ([IO.Path]::GetFileName(([Uri]$url).AbsolutePath))
    Info "Descargando $url …"
    try { Invoke-WebRequest -Uri $url -OutFile $archivo -UseBasicParsing }
    catch { Falta "No se pudo descargar: $($_.Exception.Message)"; return $null }
    $s = Get-AuthenticodeSignature $archivo
    if ($s.Status -ne 'Valid' -or $s.SignerCertificate.Subject -notlike "*$firma*") {
        Falta "La firma del instalador no es válida ($($s.Status), $($s.SignerCertificate.Subject)): no se ejecuta."
        Remove-Item $archivo -ErrorAction SilentlyContinue
        return $null
    }
    Info "Firma válida: $($s.SignerCertificate.Subject.Split(',')[0])"
    return $archivo
}

# Ejecuta un instalador y espera a que termine; recarga el PATH. True si terminó bien.
function Ejecutar-Instalador([string]$archivo, [string[]]$argumentos) {
    $p = Start-Process -FilePath $archivo -ArgumentList $argumentos -Wait -PassThru
    Recargar-Path
    return $p.ExitCode -eq 0
}


# =========================== bienvenida ===========================
Write-Host "DeskLens · instalador" -ForegroundColor Cyan
Write-Host "Carpeta: $Carpeta"
Write-Host ("winget: " + $(if ($HayWinget) { 'sí' } else { 'no (se usarán los instaladores oficiales, comprobando su firma)' }) +
            " · administrador: " + $(if ($EsAdmin) { 'sí' } else { 'no (lo que lo necesite se instala solo para tu usuario o se avisa)' }))
if ($SoloRevisar) { Write-Host "Modo -SoloRevisar: solo se informa; no se pregunta ni se ejecuta nada." -ForegroundColor Yellow }
else { Write-Host "Cada paso muestra el comando y pregunta antes. Enter = la opción en mayúscula." }


# =========================== 1. Python 3.10 o más nuevo (obligatorio) ===========================
# Se busca el lanzador «py» y luego «python». Se ignora el «python» falso de Windows (un atajo en
# WindowsApps que solo abre Microsoft Store). Sin winget se instala el oficial de python.org:
# /quiet = sin ventanas · PrependPath=1 = añade python al PATH · Include_launcher=1 = instala «py».
Titulo "1. Python 3.10 o más nuevo"
$PY_VERSION = '3.12.10'                       # versión del instalador de python.org (sin winget)
function Buscar-Python {
    foreach ($cmd in @(@('py', '-3'), @('python'))) {
        $exe = Get-Command $cmd[0] -ErrorAction SilentlyContinue
        if (-not $exe -or $exe.Source -like '*WindowsApps*') { continue }
        $extra = @($cmd | Select-Object -Skip 1)   # «-3» para el lanzador py; nada para python
        $info = & $cmd[0] @extra -c "import sys; print(sys.version_info[0], sys.version_info[1], sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $info) {
            $p = "$info".Trim() -split ' ', 3
            return [pscustomobject]@{ Mayor = [int]$p[0]; Menor = [int]$p[1]; Exe = $p[2] }
        }
    }
    return $null
}
function Python-Valido($py) { [bool]($py -and ($py.Mayor -gt 3 -or ($py.Mayor -eq 3 -and $py.Menor -ge 10))) }

$py = Buscar-Python
if (Python-Valido $py) {
    Ok "Python $($py.Mayor).$($py.Menor) · $($py.Exe)"
    if ($HayWinget) { Info "¿Buscar una versión más nueva?"; if (Confirmar @(Winget-Texto 'upgrade' 'Python.Python.3.12') $false) { Winget 'upgrade' 'Python.Python.3.12' } }
} else {
    Falta $(if ($py) { "Hay Python $($py.Mayor).$($py.Menor); DeskLens necesita 3.10 o más nuevo." } else { "No se encontró Python." })
    if ($HayWinget) {
        if (Confirmar @(Winget-Texto 'install' 'Python.Python.3.12') $true) { Winget 'install' 'Python.Python.3.12' }
    } else {
        $url = "https://www.python.org/ftp/python/$PY_VERSION/python-$PY_VERSION-amd64.exe"
        $todos = if ($EsAdmin) { 1 } else { 0 }   # para todos los usuarios solo si es administrador
        if (Confirmar @("Invoke-WebRequest $url  (y comprobar su firma: Python Software Foundation)",
                        "python-$PY_VERSION-amd64.exe /quiet InstallAllUsers=$todos PrependPath=1 Include_launcher=1") $true) {
            $f = Descargar-Firmado $url 'Python Software Foundation'
            if ($f) {
                if (-not (Ejecutar-Instalador $f @('/quiet', "InstallAllUsers=$todos", 'PrependPath=1', 'Include_launcher=1'))) { Falta "El instalador de Python terminó con error." }
                Remove-Item $f -ErrorAction SilentlyContinue
            }
        }
    }
    $py = Buscar-Python
}
$pyOk = Python-Valido $py
if ($pyOk) { Anotar 'Python' 'ok' "$($py.Mayor).$($py.Menor)" }
else { Anotar 'Python' 'falta' 'obligatorio · https://www.python.org/downloads/' }


# =========================== 2. Git (recomendado) ===========================
# Sin git DeskLens funciona, pero sin vista Git, sin estado de los archivos y sin comparar versiones.
# Git para Windows trae también Git Bash (para ejecutar .sh) y el administrador de credenciales
# (pull/push sin escribir contraseñas). Sin winget se toma la última versión publicada en su GitHub:
# /VERYSILENT = sin ventanas · /NORESTART = no reinicia · /CURRENTUSER = solo tu usuario (sin admin).
Titulo "2. Git"
$git = Get-Command git -ErrorAction SilentlyContinue
if ($git) {
    Ok ((git --version) -replace 'git version ', 'Git ')
    if ($HayWinget) { Info "¿Buscar una versión más nueva?"; if (Confirmar @(Winget-Texto 'upgrade' 'Git.Git') $false) { Winget 'upgrade' 'Git.Git' } }
} else {
    Falta "No se encontró Git (recomendado)."
    if ($HayWinget) {
        if (Confirmar @(Winget-Texto 'install' 'Git.Git') $true) { Winget 'install' 'Git.Git' }
    } else {
        $api = 'https://api.github.com/repos/git-for-windows/git/releases/latest'
        $alcance = if ($EsAdmin) { @() } else { @('/CURRENTUSER') }
        if (Confirmar @("Invoke-RestMethod $api  (la última versión de Git para Windows)",
                        "Invoke-WebRequest <Git-…-64-bit.exe>  (y comprobar su firma: Johannes Schindelin)",
                        "Git-…-64-bit.exe /VERYSILENT /NORESTART /NOCANCEL /SP- $($alcance -join ' ')") $true) {
            try {
                $rel = Invoke-RestMethod -Uri $api -UseBasicParsing -Headers @{ 'User-Agent' = 'DeskLens-instalador' }
                $asset = $rel.assets | Where-Object { $_.name -match '^Git-[\d.]+-64-bit\.exe$' } | Select-Object -First 1
                if (-not $asset) { throw "no se encontró el instalador de 64 bits en $($rel.tag_name)" }
                $f = Descargar-Firmado $asset.browser_download_url 'Johannes Schindelin'
                if ($f) {
                    if (-not (Ejecutar-Instalador $f (@('/VERYSILENT', '/NORESTART', '/NOCANCEL', '/SP-') + $alcance))) { Falta "El instalador de Git terminó con error." }
                    Remove-Item $f -ErrorAction SilentlyContinue
                }
            } catch { Falta "No se pudo obtener Git: $($_.Exception.Message)" }
        }
    }
    $git = Get-Command git -ErrorAction SilentlyContinue
}
if ($git) { Anotar 'Git' 'ok' ((git --version) -replace 'git version ', '') }
else { Anotar 'Git' 'falta' 'recomendado · https://git-scm.com/download/win' }


# =========================== 3. Navegador de la ventana (solo se comprueba) ===========================
# La ventana de DeskLens es un navegador Chromium en «modo aplicación» (Edge, Chrome o Brave), que también
# crea los PDF. Edge viene con Windows 10/11; en Windows Server puede no estar. No se instala nada aquí:
# sin ninguno, DeskLens se abre en el navegador predeterminado, en una pestaña normal.
Titulo "3. Navegador de la ventana"
$navegadores = @(
    @{ n = 'Microsoft Edge'; r = @("${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe", "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe") },
    @{ n = 'Google Chrome';  r = @("$env:ProgramFiles\Google\Chrome\Application\chrome.exe", "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe", "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe") },
    @{ n = 'Brave';          r = @("$env:ProgramFiles\BraveSoftware\Brave-Browser\Application\brave.exe", "$env:LOCALAPPDATA\BraveSoftware\Brave-Browser\Application\brave.exe") }
)
$hay = @($navegadores | Where-Object { $_.r | Where-Object { $_ -and (Test-Path $_) } } | ForEach-Object { $_.n })
if ($hay.Count) { Ok ($hay -join ', '); Anotar 'Navegador' 'ok' ($hay -join ', ') }
else { Falta "Ni Edge ni Chrome: DeskLens se abrirá en una pestaña de tu navegador. Para la ventana propia, instala Edge o Chrome."; Anotar 'Navegador' 'falta' 'Edge o Chrome (recomendado)' }


# =========================== 4. IA (opcional): Node.js y las CLI de cada IA ===========================
# El chat de IA usa las herramientas de línea de órdenes de cada empresa con TU propia cuenta: DeskLens no
# guarda claves. Se instalan con npm (viene con Node.js). Después hay que iniciar sesión una vez en cada una.
# Node.js sin winget: el .msi LTS oficial de nodejs.org (msiexec /qn = sin ventanas; necesita administrador).
Titulo "4. IA (opcional)"
$ias = @(@('Claude Code', 'claude', '@anthropic-ai/claude-code'),   # nombre, orden, paquete oficial de npm
         @('Codex', 'codex', '@openai/codex'),
         @('Gemini CLI', 'gemini', '@google/gemini-cli'))
$faltan = @()
foreach ($ia in $ias) {
    if (Get-Command $ia[1] -ErrorAction SilentlyContinue) { Ok $ia[0]; Anotar $ia[0] 'ok' 'instalada' } else { $faltan += , $ia }
}
if ($faltan.Count -and -not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Info "Para instalar las que faltan hace falta Node.js (incluye npm)."
    if ($HayWinget) {
        if (Confirmar @(Winget-Texto 'install' 'OpenJS.NodeJS.LTS') $false) { Winget 'install' 'OpenJS.NodeJS.LTS' }
    } elseif (-not $EsAdmin) {
        Info "Node.js sin winget necesita administrador: ejecuta instalar.bat con «Ejecutar como administrador»."
    } elseif (Confirmar @("Invoke-RestMethod https://nodejs.org/dist/index.json  (la última versión LTS)",
                          "Invoke-WebRequest <node-v…-x64.msi>  (y comprobar su firma: OpenJS Foundation)",
                          "msiexec /i node-v…-x64.msi /qn") $false) {
        try {
            # se guarda primero en una variable: en PS 5.1 Invoke-RestMethod pasa la lista entera como un solo objeto
            $versiones = Invoke-RestMethod -Uri 'https://nodejs.org/dist/index.json' -UseBasicParsing
            $lts = ($versiones | Where-Object { $_.lts } | Select-Object -First 1).version
            $f = Descargar-Firmado "https://nodejs.org/dist/$lts/node-$lts-x64.msi" 'OpenJS Foundation'
            if ($f) {
                if (-not (Ejecutar-Instalador 'msiexec.exe' @('/i', "`"$f`"", '/qn'))) { Falta "El instalador de Node.js terminó con error." }
                Remove-Item $f -ErrorAction SilentlyContinue
            }
        } catch { Falta "No se pudo obtener Node.js: $($_.Exception.Message)" }
    }
}
foreach ($ia in $faltan) {
    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { Anotar $ia[0] 'opcional' 'no instalada (falta Node.js)'; continue }
    Info "$($ia[0]) no está instalada."
    if (Confirmar @("npm install -g $($ia[2])") $false) {
        npm install -g $ia[2]
        Recargar-Path
        if (Get-Command $ia[1] -ErrorAction SilentlyContinue) { Ok "$($ia[0]) · inicia sesión una vez con: $($ia[1])"; Anotar $ia[0] 'ok' "instalada · inicia sesión con: $($ia[1])" }
        else { Falta "$($ia[0]) no quedó instalada"; Anotar $ia[0] 'falta' "npm install -g $($ia[2])" }
    } else { Anotar $ia[0] 'opcional' 'no instalada' }
}


# =========================== 5. Acceso directo «DeskLens» ===========================
# Abre desklens.pyw con pythonw.exe (Python sin ventana negra), con la carpeta de DeskLens como carpeta de
# trabajo para que encuentre su config.json e historial/. Se crea en el Escritorio y en el menú Inicio.
Titulo "5. Acceso directo"
$pyw = if ($py) { Join-Path (Split-Path $py.Exe) 'pythonw.exe' } else { $null }
$destinos = @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs')) | ForEach-Object { Join-Path $_ 'DeskLens.lnk' }
$yaHay = Test-Path $destinos[0]
if ($yaHay) { Ok "Ya hay un acceso directo «DeskLens» en el Escritorio (se puede volver a crear)" }
if (-not $pyOk -or -not $pyw -or -not (Test-Path $pyw)) { Falta "Sin Python no se puede crear."; Anotar 'Acceso directo' 'falta' 'necesita Python' }
elseif (Confirmar @($destinos | ForEach-Object { "Crear $_  ->  `"$pyw`" `"$Carpeta\desklens.pyw`"" }) (-not $yaHay)) {
    $shell = New-Object -ComObject WScript.Shell
    foreach ($d in $destinos) {
        $lnk = $shell.CreateShortcut($d)
        $lnk.TargetPath = $pyw
        $lnk.Arguments = '"' + (Join-Path $Carpeta 'desklens.pyw') + '"'
        $lnk.WorkingDirectory = $Carpeta
        $lnk.Description = 'DeskLens: visor y editor local de proyectos, con git e IA'
        $lnk.Save()
    }
    Ok "Creado en el Escritorio y en el menú Inicio"; Anotar 'Acceso directo' 'ok' 'Escritorio y menú Inicio'
} else { Anotar 'Acceso directo' $(if ($yaHay) { 'ok' } else { 'opcional' }) $(if ($yaHay) { 'ya existía' } else { 'no creado' }) }


# =========================== 6. Prueba final ===========================
# test_desklens.py no abre ventanas ni toca tus datos (usa una carpeta temporal). Necesita Git porque
# prueba la vista Git con un repositorio de juguete.
Titulo "6. Prueba final"
if ($pyOk -and $git) {
    if (Confirmar @("cd `"$Carpeta`"", "`"$($py.Exe)`" test_desklens.py") $true) {
        Push-Location $Carpeta
        try {
            $salida = & $py.Exe test_desklens.py 2>&1 | Select-Object -Last 4
            if ($LASTEXITCODE -eq 0) { Ok ($salida | Select-Object -Last 1); Anotar 'Pruebas' 'ok' 'todas pasan' }
            else { Write-Host ($salida -join "`n") -ForegroundColor Red; Anotar 'Pruebas' 'falta' 'ver el error de arriba' }
        } finally { Pop-Location }
    }
} else { Info "(se omite: hace falta Python y Git)" }


# =========================== resumen ===========================
Titulo "Resumen"
foreach ($f in $Resumen) {
    $marca, $color = switch ($f.Estado) { 'ok' { '[OK]   ', 'Green' } 'falta' { '[FALTA]', 'Red' } default { '[--]   ', 'DarkGray' } }
    Write-Host ("   {0} {1,-16} {2}" -f $marca, $f.Pieza, $f.Detalle) -ForegroundColor $color
}
Write-Host ""
if ($pyOk) { Write-Host "Listo. Abre DeskLens con el acceso directo o con doble clic en desklens.pyw." -ForegroundColor Cyan }
else { Write-Host "Falta Python: vuelve a ejecutar el instalador y acepta instalarlo, o instálalo desde python.org." -ForegroundColor Red }
