@echo off
chcp 65001 >nul
title 上海工资计算器 (Shanghai Salary Calculator)
cd /d "%~dp0"
python salary_calculator.py
if %errorlevel% neq 0 (
    echo.
    echo [Error] 未检测到 python，请先安装 Python 3 并加入 PATH。
    pause
)
pause
