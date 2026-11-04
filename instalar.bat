@echo off
rem ==========================================================================================
rem  DeskLens · instalador para Windows (doble clic aquí)
rem
rem  Este archivo solo lanza instalar.ps1, que es el que revisa e instala lo necesario.
rem  Por qué un .bat: Windows bloquea por defecto los scripts de PowerShell que se abren con
rem  doble clic. «-ExecutionPolicy Bypass» quita ese bloqueo SOLO para esta ejecución; no cambia
rem  la configuración del equipo.
rem  Opciones: instalar.bat -SoloRevisar   (muestra qué falta, sin instalar nada)
rem ==========================================================================================

rem Consola en UTF-8 para que se vean bien las tildes y la ñ
chcp 65001 >nul

rem %~dp0 es la carpeta donde está este .bat (funciona aunque se abra desde otro sitio)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0instalar.ps1" %*

rem Deja la ventana abierta para poder leer el resumen
pause
