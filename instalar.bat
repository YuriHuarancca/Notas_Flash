@echo off
setlocal enabledelayedexpansion
title Instalador - Widget Notas Windows 11

echo ========================================================
echo   Instalador Profesional - Widget Notas Windows 11
echo ========================================================
echo.

rem 1. Verificar y solicitar elevacion de Administrador para C:\Program Files
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [SOLICITANDO PERMISOS] Se requieren privilegios de Administrador para
    echo instalar la aplicacion en C:\Program Files y registrar el menu anticlick.
    echo.
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process cmd -ArgumentList '/c \"\"%~f0\"\"' -Verb runAs"
    exit /b
)

set "SOURCE_DIR=%~dp0"
set "SOURCE_EXE=%SOURCE_DIR%Widget-Notas-Win11.exe"
if not exist "%SOURCE_EXE%" (
    set "SOURCE_EXE=%SOURCE_DIR%dist\Widget-Notas-Win11\Widget-Notas-Win11.exe"
)

if not exist "%SOURCE_EXE%" (
    echo [ERROR] No se encontro el archivo ejecutable Widget-Notas-Win11.exe.
    pause
    exit /b 1
)

echo [1/4] Preparando carpeta de instalacion en C:\Program Files...
set "INSTALL_DIR=%ProgramFiles%\WidgetNotasWin11"
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"

echo [2/4] Copiando archivos de la aplicacion...
taskkill /F /IM Widget-Notas-Win11.exe >nul 2>&1
copy /Y "%SOURCE_EXE%" "%INSTALL_DIR%\Widget-Notas-Win11.exe" >nul
if exist "%SOURCE_DIR%_internal" xcopy /E /I /Y "%SOURCE_DIR%_internal" "%INSTALL_DIR%\_internal" >nul
if exist "%SOURCE_DIR%dist\Widget-Notas-Win11\_internal" xcopy /E /I /Y "%SOURCE_DIR%dist\Widget-Notas-Win11\_internal" "%INSTALL_DIR%\_internal" >nul
if exist "%SOURCE_DIR%icon.ico" copy /Y "%SOURCE_DIR%icon.ico" "%INSTALL_DIR%\icon.ico" >nul
if exist "%SOURCE_DIR%desinstalar.bat" copy /Y "%SOURCE_DIR%desinstalar.bat" "%INSTALL_DIR%\desinstalar.bat" >nul

echo [3/4] Creando accesos directos en Escritorio y Menu Inicio...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$ws = New-Object -ComObject WScript.Shell; " ^
    "$desk = [System.Environment]::GetFolderPath('Desktop'); " ^
    "$pubDesk = [System.Environment]::GetFolderPath('CommonDesktopDirectory'); " ^
    "$start = [System.Environment]::GetFolderPath('CommonPrograms'); " ^
    "$target = \"$env:ProgramFiles\WidgetNotasWin11\Widget-Notas-Win11.exe\"; " ^
    "$s1 = $ws.CreateShortcut(\"$pubDesk\Widget Notas Win11.lnk\"); " ^
    "$s1.TargetPath = $target; " ^
    "$s1.IconLocation = \"$target,0\"; " ^
    "$s1.Save(); " ^
    "$s2 = $ws.CreateShortcut(\"$desk\Widget Notas Win11.lnk\"); " ^
    "$s2.TargetPath = $target; " ^
    "$s2.IconLocation = \"$target,0\"; " ^
    "$s2.Save(); " ^
    "$s3 = $ws.CreateShortcut(\"$start\Widget Notas Win11.lnk\"); " ^
    "$s3.TargetPath = $target; " ^
    "$s3.IconLocation = \"$target,0\"; " ^
    "$s3.Save(); " ^
    "$startup = [System.Environment]::GetFolderPath('Startup'); " ^
    "$s4 = $ws.CreateShortcut(\"$startup\Widget Notas Win11.lnk\"); " ^
    "$s4.TargetPath = $target; " ^
    "$s4.IconLocation = \"$target,0\"; " ^
    "$s4.Save();"

echo [4/4] Configurando menu contextual anticlick para .txt, .html y .htm...
set "EXE_PATH=%INSTALL_DIR%\Widget-Notas-Win11.exe"

for %%E in (.txt .html .htm .w11note) do (
    reg add "HKCR\SystemFileAssociations\%%E\shell\WidgetNotas" /ve /d "Abrir con Widget de Notas" /f >nul
    reg add "HKCR\SystemFileAssociations\%%E\shell\WidgetNotas" /v "Icon" /d "\"%EXE_PATH%\",0" /f >nul
    reg add "HKCR\SystemFileAssociations\%%E\shell\WidgetNotas\command" /ve /d "\"%EXE_PATH%\" \"%%1\"" /f >nul
)

rem Registrar en aplicaciones compatibles (Abrir con...)
reg add "HKCR\Applications\Widget-Notas-Win11.exe\shell\open\command" /ve /d "\"%EXE_PATH%\" \"%%1\"" /f >nul
reg add "HKCR\Applications\Widget-Notas-Win11.exe\SupportedTypes" /v ".txt" /t REG_SZ /d "" /f >nul
reg add "HKCR\Applications\Widget-Notas-Win11.exe\SupportedTypes" /v ".html" /t REG_SZ /d "" /f >nul
reg add "HKCR\Applications\Widget-Notas-Win11.exe\SupportedTypes" /v ".htm" /t REG_SZ /d "" /f >nul
reg add "HKCR\Applications\Widget-Notas-Win11.exe\SupportedTypes" /v ".w11note" /t REG_SZ /d "" /f >nul

rem Registrar en Agregar o Quitar Programas de Windows
set "REG_UNINST=HKLM\Software\Microsoft\Windows\CurrentVersion\Uninstall\WidgetNotasWin11"
reg add "%REG_UNINST%" /v "DisplayName" /d "Widget Notas Windows 11" /f >nul
reg add "%REG_UNINST%" /v "DisplayVersion" /d "1.1.0" /f >nul
reg add "%REG_UNINST%" /v "Publisher" /d "Widget Notas" /f >nul
reg add "%REG_UNINST%" /v "DisplayIcon" /d "%INSTALL_DIR%\Widget-Notas-Win11.exe,0" /f >nul
reg add "%REG_UNINST%" /v "InstallLocation" /d "%INSTALL_DIR%" /f >nul
reg add "%REG_UNINST%" /v "UninstallString" /d "\"%INSTALL_DIR%\desinstalar.bat\"" /f >nul
reg add "%REG_UNINST%" /v "EstimatedSize" /t REG_DWORD /d 15000 /f >nul

echo.
echo ========================================================
echo    INSTALACION COMPLETADA CON EXITO!
echo ========================================================
echo - Carpeta de instalacion: %INSTALL_DIR%
echo - Accesos directos: Escritorio y Menu Inicio
echo - Menu anticlick: "Abrir con Widget de Notas" listo en .txt y .html
echo.
pause
