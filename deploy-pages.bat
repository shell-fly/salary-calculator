@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
rem deploy-pages.bat — 一键校验并部署 Web UI (PWA) 到 GitHub / Gitee Pages
rem 用法: deploy-pages.bat [check^|gitee^|github^|both]
rem   check  只跑门禁([1/5]-[3/5]),不提交、不推送,无任何副作用
rem   其余值只控制往哪些远程推送,默认 both(会提交并推送)
rem
rem 重要(cmd 陷阱): 写在括号块内部的 `exit /b 1` 会丢掉退出码,进程仍返回 0,
rem   导致门禁"打印失败但不阻断"。因此本脚本的每条检查都用
rem   `set "ERR=%%ERRORLEVEL%%"` 记下错误码,失败一律用顶层单行 `exit /b 1` 退出。
rem   该回归由 src/test_deploy_gate.py 守住(无 PWA 文件时必须 exit 1)。
cd /d "%~dp0"

set "TARGET=%~1"
if "%TARGET%"=="" set "TARGET=both"
set "CHECK_ONLY="
if /i "%TARGET%"=="check" set "CHECK_ONLY=1"
if /i "%TARGET%"=="--check" set "CHECK_ONLY=1"
if /i "%TARGET%"=="-c" set "CHECK_ONLY=1"

echo ===============================================
if defined CHECK_ONLY (
  echo  工资计算器（中国） — Pages 门禁校验（check 模式：不提交、不推送）
) else (
  echo  工资计算器（中国） — Pages 部署检查与发布
)
echo ===============================================

echo [1/5] 校验 Web UI / PWA 文件...
set "OK=1"
for %%f in (web\index.html web\manifest.webmanifest web\sw.js ^
            web\icons\icon-192.png web\icons\icon-512.png web\icons\maskable-512.png ^
            web\icons\apple-touch-icon.png) do (
  if exist "%%f" (echo   OK  %%f) else (echo   缺失:  %%f & set "OK=0")
)
if "%OK%"=="0" echo 文件不完整,请先运行: powershell -ExecutionPolicy Bypass -File web\gen-icons.ps1
if "%OK%"=="0" exit /b 1

echo [2/5] 校验内嵌副本、引擎断言与 Excel 测试...
call :check_node_suite
if errorlevel 1 exit /b 1
call :check_python_suite
if errorlevel 1 exit /b 1

echo [3/5] 检查 git 远程...
git rev-parse --is-inside-work-tree >nul 2>&1
set "ERR=%ERRORLEVEL%"
if not "%ERR%"=="0" echo   当前目录不是 git 仓库
if not "%ERR%"=="0" exit /b 1
set "HAS_REMOTE="
for /f "tokens=1" %%r in ('git remote') do set "HAS_REMOTE=1"
if not defined HAS_REMOTE (
  echo   尚未配置任何远程。请先添加,例如:
  echo       git remote add origin https://github.com/用户名/仓库名.git
  echo     或 Gitee: git remote add gitee https://gitee.com/用户名/仓库名.git
) else (
  echo   已配置远程:
  for /f "tokens=1" %%r in ('git remote') do echo     - %%r
)

if defined CHECK_ONLY goto :check_only

echo [4/5] 提交本地改动并推送...
git add -A
git commit -m "chore(deploy): update Web UI / PWA assets" 2>nul || echo   无待提交改动
for /f "tokens=*" %%b in ('git rev-parse --abbrev-ref HEAD') do set "BRANCH=%%b"

call :push origin
if not "%TARGET%"=="gitee" call :push github
if not "%TARGET%"=="github" call :push gitee
goto :after_push

:check_only
echo [4/5] check 模式: 跳过提交与推送
echo [5/5] check 模式: 未发布, 不打印 Pages 控制台启用步骤
echo.
echo 门禁全部通过。需要发布请直接运行: deploy-pages.bat
exit /b 0

:after_push
echo [5/5] 推送完成。到网页控制台启用 Pages ^(首次一次性操作^):
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
exit /b 0

rem ---------------------------------------------------------------- 子例程
rem 每个失败分支都在子例程顶层 exit /b 1(不在括号块内),错误码才会真实传出。

:check_node_suite
where node >nul 2>&1
if not errorlevel 1 goto :run_node_checks
echo   未检测到 node,跳过内联一致性校验。改过 config.json 或 web\*.js 后必须手动重跑内联脚本。
exit /b 0

:run_node_checks
rem 内联脚本会重写 index.html。若它本来与已提交版本一致、跑完却变脏了,
rem 说明仓里交付的是旧内嵌副本(源文件改了但忘跑内联)——必须拦住。
set "HTML_WAS_CLEAN="
git diff --quiet -- web\index.html >nul 2>&1
if not errorlevel 1 set "HTML_WAS_CLEAN=1"

node web\inline-config.mjs >nul 2>&1
set "ERR=%ERRORLEVEL%"
if not "%ERR%"=="0" echo   失败: config.json 与 index.html 内嵌副本不一致
if not "%ERR%"=="0" exit /b 1

node web\inline-compute.mjs >nul 2>&1
set "ERR=%ERRORLEVEL%"
if not "%ERR%"=="0" echo   失败: compute.js 与 index.html 内嵌引擎不一致
if not "%ERR%"=="0" exit /b 1

node web\inline-xlsx.mjs >nul 2>&1
set "ERR=%ERRORLEVEL%"
if not "%ERR%"=="0" echo   失败: xlsx 引擎与 index.html 内嵌副本不一致
if not "%ERR%"=="0" exit /b 1

set "DRIFT="
if defined HTML_WAS_CLEAN call :check_drift
if defined DRIFT echo   失败: 内嵌副本漂移,index.html 里交付的是旧副本(脚本已重新生成)
if defined DRIFT echo         请把 web\index.html 一并提交后再发布
if defined DRIFT exit /b 1
echo   OK  内嵌副本已与源文件同步

node web\test-compute.js >nul 2>&1
set "ERR=%ERRORLEVEL%"
if not "%ERR%"=="0" echo   失败: 计算引擎断言未通过(详情: node web\test-compute.js)
if not "%ERR%"=="0" exit /b 1
echo   OK  计算引擎断言全部通过
exit /b 0

:check_drift
git diff --quiet -- web\index.html >nul 2>&1
if errorlevel 1 set "DRIFT=1"
exit /b 0

:check_python_suite
where python >nul 2>&1
if not errorlevel 1 goto :run_python_checks
echo   未检测到 python,跳过 xlsx 契约测试与 CLI 冒烟测试
exit /b 0

:run_python_checks
set "PYTHONIOENCODING=utf-8"
python src\test_xlsx_writer.py >nul 2>&1
set "ERR=%ERRORLEVEL%"
if not "%ERR%"=="0" echo   失败: xlsx 契约测试未通过
if not "%ERR%"=="0" exit /b 1
echo   OK  xlsx 契约测试通过(CLI 与网页 Excel 逐字节一致)

python src\test_cli_smoke.py >nul 2>&1
set "ERR=%ERRORLEVEL%"
if not "%ERR%"=="0" echo   失败: CLI 端到端冒烟测试未通过(详情: python src\test_cli_smoke.py)
if not "%ERR%"=="0" exit /b 1
echo   OK  CLI 端到端冒烟测试通过(覆盖申报基数、医疗定额、逐月薪资与反推)
exit /b 0

:push
git remote get-url %1 >nul 2>&1
if errorlevel 1 (echo   跳过: 未配置远程 '%1' & goto :eof)
echo   推送到 %1 ^(!BRANCH!^)...
git push -u %1 !BRANCH!
set "ERR=%ERRORLEVEL%"
if not "%ERR%"=="0" echo   失败: 推送到 %1 未成功 ^(exit %ERR%^)
if not "%ERR%"=="0" exit /b 1
goto :eof
