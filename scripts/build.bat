@echo off
setlocal
chcp 65001 >nul

set "APP_NAME=DocuFlowLarkAI"
set "VERSION=2.0.0"
set "PACKAGE_NAME=%APP_NAME%_v%VERSION%_windows_x64"
set "ROOT_DIR=%~dp0.."
set "RELEASE_DIR=%ROOT_DIR%\release"
set "TARGET_DIR=%RELEASE_DIR%\%PACKAGE_NAME%"
set "ZIP_PATH=%RELEASE_DIR%\%PACKAGE_NAME%.zip"

echo ==========================================
echo    %APP_NAME% v%VERSION% build script
echo ==========================================
echo.

cd /d "%ROOT_DIR%" || (
    echo [ERROR] cannot enter project root
    exit /b 1
)

echo [1/6] Ensure build dependencies...
python -m pip install pyinstaller email-validator==2.3.0 dnspython==2.8.0
if errorlevel 1 (
    echo [ERROR] dependency install failed
    exit /b 1
)

echo [2/6] Archive old build outputs to tmp...
if not exist "%ROOT_DIR%\tmp" mkdir "%ROOT_DIR%\tmp"
for /f "delims=" %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "BUILD_STAMP=%%I"
set "ARCHIVE_DIR=%ROOT_DIR%\tmp\build_archive_%BUILD_STAMP%"
if not exist "%ARCHIVE_DIR%" mkdir "%ARCHIVE_DIR%"
if exist "%ROOT_DIR%\build" (
    move /Y "%ROOT_DIR%\build" "%ARCHIVE_DIR%\" >nul
    if errorlevel 1 (
        echo [ERROR] archive build folder failed
        exit /b 1
    )
)
if exist "%ROOT_DIR%\dist" (
    move /Y "%ROOT_DIR%\dist" "%ARCHIVE_DIR%\" >nul
    if errorlevel 1 (
        echo [ERROR] archive dist folder failed
        exit /b 1
    )
)
if exist "%TARGET_DIR%" (
    move /Y "%TARGET_DIR%" "%ARCHIVE_DIR%\" >nul
    if errorlevel 1 (
        echo [ERROR] archive release folder failed
        exit /b 1
    )
)
if exist "%ZIP_PATH%" (
    move /Y "%ZIP_PATH%" "%ARCHIVE_DIR%\" >nul
    if errorlevel 1 (
        echo [ERROR] archive release zip failed
        exit /b 1
    )
)
if not exist "%RELEASE_DIR%" mkdir "%RELEASE_DIR%"

echo [3/6] Run PyInstaller...
python -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --windowed ^
  --onedir ^
  --name "%APP_NAME%" ^
  --add-data "frontend;frontend" ^
  --add-data "templates;templates" ^
  --add-data "config;config" ^
  --copy-metadata email-validator ^
  --hidden-import uvicorn ^
  --hidden-import fastapi ^
  --hidden-import main ^
  --hidden-import email_validator ^
  --collect-submodules email_validator ^
  --hidden-import sqlalchemy ^
  --hidden-import aiosqlite ^
  --hidden-import httpx ^
  --hidden-import pandas ^
  --hidden-import openpyxl ^
  --hidden-import docx ^
  --hidden-import webview ^
  backend\desktop_app.py
if errorlevel 1 (
    echo [ERROR] PyInstaller build failed
    exit /b 1
)

echo [4/6] Prepare release folder...
mkdir "%TARGET_DIR%"
xcopy /E /I /Y "%ROOT_DIR%\dist\%APP_NAME%\*" "%TARGET_DIR%\" >nul

(
echo @echo off
echo setlocal
echo cd /d "%%~dp0"
echo start "" "%%~dp0%APP_NAME%.exe"
) > "%TARGET_DIR%\start.bat"

echo [5/6] Create ZIP package...
powershell -NoProfile -Command "Compress-Archive -Path '%TARGET_DIR%\*' -DestinationPath '%ZIP_PATH%' -Force"
if errorlevel 1 (
    echo [ERROR] ZIP package failed
    exit /b 1
)

echo [6/6] Done
echo.
echo ==========================================
echo  Folder: %TARGET_DIR%
echo  Zip:    %ZIP_PATH%
echo ==========================================
echo.
if not "%NO_PAUSE%"=="1" pause
exit /b 0
