@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
python src\release.py %*
set "RC=%ERRORLEVEL%"
exit /b %RC%
