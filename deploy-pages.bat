@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
rem deploy-pages.bat — 一键校验并部署 Web UI (PWA) 到 GitHub / Gitee Pages
rem 用法: deploy-pages.bat   (可选参数 gitee|github|both 指定推送远程, 默认 both)
cd /d "%~dp0"

set "TARGET=%~1"
if "%TARGET%"=="" set "TARGET=both"

echo ===============================================
echo  China Salary Calculator — Pages 部署检查
echo ===============================================

echo [1/4] 校验 Web UI / PWA 文件...
set "OK=1"
for %%f in (web\index.html web\manifest.webmanifest web\sw.js ^
            web\icons\icon-192.png web\icons\icon-512.png web\icons\maskable-512.png ^
            web\icons\apple-touch-icon.png) do (
  if exist "%%f" (echo   OK  %%f) else (echo   缺失:  %%f & set "OK=0")
)
if "%OK%"=="0" (
  echo 文件不完整,请先运行: powershell -ExecutionPolicy Bypass -File web\gen-icons.ps1
  exit /b 1
)

echo [2/4] 检查 git 远程...
git rev-parse --is-inside-work-tree >nul 2>&1
if errorlevel 1 (echo   当前目录不是 git 仓库 & exit /b 1)
for /f "tokens=1" %%r in ('git remote') do set "HAS_REMOTE=1"
if not defined HAS_REMOTE (
  echo   尚未配置任何远程。请先添加,例如:
  echo       git remote add origin https://github.com/用户名/仓库名.git
  echo     或 Gitee: git remote add gitee https://gitee.com/用户名/仓库名.git
) else (
  echo   已配置远程:
  for /f "tokens=1" %%r in ('git remote') do echo     - %%r
)

echo [3/4] 提交本地改动并推送...
git add -A
git commit -m "chore(deploy): update Web UI / PWA assets" 2>nul || echo   无待提交改动
for /f "tokens=*" %%b in ('git rev-parse --abbrev-ref HEAD') do set "BRANCH=%%b"

call :push origin
if not "%TARGET%"=="gitee" call :push github
if not "%TARGET%"=="github" call :push gitee
goto :after_push

:push
git remote get-url %1 >nul 2>&1
if errorlevel 1 (echo   跳过: 未配置远程 '%1' & goto :eof)
echo   推送到 %1 ^(%BRANCH%^)...
git push -u %1 %BRANCH%
goto :eof

:after_push
echo [4/4] 推送完成。到网页控制台启用 Pages ^(首次一次性操作^):
echo.
echo   ── GitHub Pages ──────────────────────────────
echo   1^) 仓库已内置 .github\workflows\deploy-pages.yml
echo   2^) Settings -^> Pages -^> Build and deployment -^> Source 选 "GitHub Actions"
echo   3^) push 后到 Actions 页看部署进度,成功后访问:
echo         https://用户名.github.io/仓库名/
echo.
echo   ── Gitee Pages ───────────────────────────────
echo   1^) 需实名认证: 登录 Gitee -^> 个人设置 -^> 实名信息
echo   2^) 仓库页 -^> Services -^> Gitee Pages -^> 点 "启用"
echo   3^) 部署分支: master/main;  目录: web  ; 点 "启动"
echo   4^) 访问: https://用户名.gitee.io/仓库名/
echo   注意: 更新内容后需在 Gitee Pages 页手动点 "更新" 才会重新发布。
echo.
echo   ── 手机安装为 App (PWA) ──────────────────────
echo   浏览器打开上述网址 -^> 菜单 "安装/添加到主屏幕" -^> 独立图标、离线可用。
echo.
echo 完成.
endlocal
