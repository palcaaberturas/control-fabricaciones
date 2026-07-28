@echo off
title Control de Fabricaciones - PALCA
echo ====================================================
echo      INICIANDO CONTROL DE FABRICACIONES
echo ====================================================
echo.

:: 0. Poner la consola en UTF-8 (evita problemas con los emojis)
chcp 65001 >nul

:: 1. Cambiar al directorio donde esta el script (repo git)
cd /d "C:\Users\NICO\repos\Control fabricaciones"

:: 2. Ejecutar el script usando el Python del entorno virtual
"C:\Users\NICO\Onedrive PALCA\OneDrive\PALCA\Scripts Python PALCA\.venv\Scripts\python.exe" "Control_fabricacionesV0.1.py"

echo.
echo ====================================================
echo      PROCESO FINALIZADO
echo ====================================================
echo.
pause