@echo off
chcp 65001 >nul
title China Salary Calculator
cd /d "%~dp0"
echo ===============================
echo  China Salary Calculator
echo ===============================
echo [1] CLI 命令行版
echo [2] Web UI（浏览器打开）
echo.
set /p choice=请选择 (1/2，默认2): 
if "%choice%"=="1" (
    python src\salary_calculator.py
) else (
    start "" "web\index.html"
)
