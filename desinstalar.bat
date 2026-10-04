@echo off
setlocal enabledelayedexpansion
title Desinstalador - Widget Notas Windows 11

echo ========================================================
echo   Desinstalador - Widget Notas Windows 11
echo ========================================================
echo.

rem 1. Verificar y solicitar elevacion de Administrador
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [SOLICITANDO PERMISOS] Se requieren privilegios de Administrador para
    echo desinstalar completamente la aplicacion de C:\Program Files.
    echo.
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process cmd -ArgumentList '/c \"\"%~f0\"\"' -Verb runAs"
    exit /b
)

echo [1/4] Cerrando procesos activos...
taskkill /F /IM Widget-Notas-Win11.exe >nul 2>&1

echo [2/4] Eliminando accesos directos...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$desk = [System.Environment]::GetFolderPath('Desktop'); " ^
    "$pubDesk = [System.Environment]::GetFolderPath('CommonDesktopDirectory'); " ^
    "$start = [System.Environment]::GetFolderPath('CommonPrograms'); " ^
    "$uStart = [System.Environment]::GetFolderPath('Programs'); " ^
    "Remove-Item -Path \"$desk\Widget Notas Win11.lnk\" -Force -ErrorAction SilentlyContinue; " ^
    "Remove-Item -Path \"$pubDesk\Widget Notas Win11.lnk\" -Force -ErrorAction SilentlyContinue; " ^
    "Remove-Item -Path \"$start\Widget Notas Win11.lnk\" -Force -ErrorAction SilentlyContinue; " ^
    "Remove-Item -Path \"$uStart\Widget Notas Win11.lnk\" -Force -ErrorAction SilentlyContinue;"

echo [3/4] Eliminando asociaciones de menu anticlick y registros...
for %%E in (.txt .html .htm .w11note) do (
    reg delete "HKCR\SystemFileAssociations\%%E\shell\WidgetNotas" /f >nul 2>&1
)
reg delete "HKCR\Applications\Widget-Notas-Win11.exe" /f >nul 2>&1
reg delete "HKLM\Software\Microsoft\Windows\CurrentVersion\Uninstall\WidgetNotasWin11" /f >nul 2>&1
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\WidgetNotasWin11" /f >nul 2>&1

echo [4/4] Eliminando archivos de instalacion en C:\Program Files...
set "INSTALL_DIR=%ProgramFiles%\WidgetNotasWin11"
cd /d "%TEMP%"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "Start-Sleep -Milliseconds 500; Remove-Item -Path \"$env:ProgramFiles\WidgetNotasWin11\" -Recurse -Force -ErrorAction SilentlyContinue; Remove-Item -Path \"$env:LOCALAPPDATA\WidgetNotasWin11\" -Recurse -Force -ErrorAction SilentlyContinue"

echo.
echo ========================================================
echo   DESINSTALACION COMPLETADA LIMPIAMENTE!
echo ========================================================
echo Los archivos de C:\Program Files, accesos directos y entradas de
echo menu anticlick han sido eliminados por completo de Windows.
echo.
pause
