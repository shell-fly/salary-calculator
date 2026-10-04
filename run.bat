@echo off
chcp 65001 >nul
title 工资计算器（中国）
cd /d "%~dp0"
echo ===============================
echo  工资计算器（中国）
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
