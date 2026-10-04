#!/usr/bin/env bash
cd "$(dirname "$0")"
echo "==============================="
echo " 工资计算器（中国）"
echo "==============================="
echo "[1] CLI 命令行版"
echo "[2] Web UI（浏览器打开）"
echo ""
read -p "请选择 (1/2，默认2): " choice
if [ "$choice" = "1" ]; then
    python3 src/salary_calculator.py
else
    if command -v open &>/dev/null; then
        open web/index.html
    elif command -v xdg-open &>/dev/null; then
        xdg-open web/index.html
    elif command -v termux-open &>/dev/null; then
        termux-open web/index.html
    else
        echo "请手动用浏览器打开 web/index.html"
    fi
fi