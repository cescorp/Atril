@echo off
rem ==========================================================================================
rem  DeskLens · empaquetar para llevar a otro equipo (doble clic aquí)
rem
rem  Crea DeskLens-AAAA-MM-DD.zip con SOLO lo necesario para funcionar: sin tus datos
rem  (config.json, historial\). En el otro equipo: descomprimir y doble clic en instalar.bat.
rem  Este archivo solo lanza empaquetar.ps1, que es el que hace el trabajo (comentado paso a paso).
rem  «-ExecutionPolicy Bypass» quita el bloqueo de scripts SOLO para esta ejecución.
rem ==========================================================================================
chcp 65001 >nul
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0empaquetar.ps1" %*
pause
