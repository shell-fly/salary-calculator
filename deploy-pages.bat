@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
rem deploy-pages.bat — Web UI (PWA) 发布门禁与推送
rem
rem 用法:
rem   deploy-pages.bat                    跑门禁,然后列出待推送提交并交互确认后推送
rem   deploy-pages.bat check              只跑门禁([1/5]-[3/5]),不提交不推送,无副作用(脏工作树也可跑)
rem   deploy-pages.bat publish [target]   跑门禁后直接推送(免交互,供 CI 使用);target = both^|gitee^|github
rem   deploy-pages.bat gitee / github / both   等价于 publish <target>(向后兼容)
rem
rem 本脚本不会替你提交:发布前工作树必须干净,提交信息请自己按 Conventional Commits 写好。
rem 这样才不会出现一个把真实变更抹平的 "chore(deploy): update Web UI / PWA assets" 大提交。
rem
rem 重要(cmd 陷阱): 写在括号块内部的 `exit /b N` 会丢掉退出码,进程仍返回 0,导致门禁"打印失败却不阻断"。
rem   因此本脚本失败一律走子例程 + 顶层单行 exit,错误码先存入 ERR。由 src/test_deploy_gate.py 守住。
cd /d "%~dp0"

set "MODE=interactive"
set "TARGET=both"
set "ARG1=%~1"
set "ARG2=%~2"
rem 第一个参数只表示模式或向后兼容的远程名;不能用它直接当 TARGET(否则 check 会被当成远程名而误报用法错误)。
if /i "%ARG1%"=="check" set "MODE=check"
if /i "%ARG1%"=="--check" set "MODE=check"
if /i "%ARG1%"=="-c" set "MODE=check"
if /i "%ARG1%"=="publish" set "MODE=publish"
if /i "%ARG1%"=="push" set "MODE=publish"
if /i "%ARG1%"=="both" set "MODE=publish"
if /i "%ARG1%"=="gitee" set "MODE=publish"
if /i "%ARG1%"=="github" set "MODE=publish"
if /i "%ARG1%"=="both" set "TARGET=both"
if /i "%ARG1%"=="gitee" set "TARGET=gitee"
if /i "%ARG1%"=="github" set "TARGET=github"
if /i "%ARG1%"=="publish" set "TARGET=%ARG2%"
if /i "%ARG1%"=="push" set "TARGET=%ARG2%"
if "%TARGET%"=="" set "TARGET=both"
set "VALID_TARGET="
if /i "%TARGET%"=="both" set "VALID_TARGET=1"
if /i "%TARGET%"=="gitee" set "VALID_TARGET=1"
if /i "%TARGET%"=="github" set "VALID_TARGET=1"
if defined VALID_TARGET goto :target_ok
echo 用法: deploy-pages.bat [check^|publish [both^|gitee^|github]^|gitee^|github^|both]
exit /b 2
:target_ok

echo ===============================================
if "%MODE%"=="check" echo  工资计算器（中国） — 发布门禁校验（check：不提交、不推送）
if "%MODE%"=="publish" echo  工资计算器（中国） — 发布门禁 + 推送（publish：免交互，目标 %TARGET%）
if "%MODE%"=="interactive" echo  工资计算器（中国） — 发布门禁 + 推送（确认制，目标 %TARGET%）
echo ===============================================

rem 发布前先做最便宜、也最容易踩的检查:工作树必须已提交。放在重型门禁之前,省掉几十秒无效测试。
if "%MODE%"=="check" goto :skip_precheck
call :check_worktree_committed
if errorlevel 1 exit /b 1
:skip_precheck

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

echo [3/5] 检查 git 远程与待推送提交...
git rev-parse --is-inside-work-tree >nul 2>&1
set "ERR=%ERRORLEVEL%"
if not "%ERR%"=="0" echo   当前目录不是 git 仓库
if not "%ERR%"=="0" exit /b 1
set "HAS_REMOTE="
for /f "tokens=1" %%r in ('git remote') do set "HAS_REMOTE=1"
if defined HAS_REMOTE (
  echo   已配置远程:
  for /f "tokens=1" %%r in ('git remote') do echo     - %%r
) else (
  echo   尚未配置任何远程。请先添加,例如:
  echo       git remote add origin https://github.com/用户名/仓库名.git
  echo     或 Gitee: git remote add gitee https://gitee.com/用户名/仓库名.git
)
for /f "tokens=*" %%b in ('git rev-parse --abbrev-ref HEAD') do set "BRANCH=%%b"
echo   当前分支: !BRANCH!
if "%MODE%"=="check" goto :check_only

call :count_ahead
if "!AHEAD!"=="" goto :check_only
echo   待推送提交: !AHEAD! 个
if not "!AHEAD!"=="0" git log --oneline origin/!BRANCH!..HEAD

:check_only
if not "%MODE%"=="check" goto :publish_gate
if "!AHEAD!"=="0" goto :already_in_sync
echo [4/5] check 模式: 不推送
echo [5/5] check 模式: 未发布, 不打印 Pages 控制台启用步骤
echo.
echo 门禁全部通过。需要发布请直接运行: deploy-pages.bat
exit /b 0

:already_in_sync
echo.
echo 本地与 origin/!BRANCH! 已同步,无需推送。
exit /b 0

:publish_gate
echo [4/5] 推送到远程...
if not "!AHEAD!"=="" echo   本脚本不代为提交;请确认上面的待推送提交就是你想发布的内容。
if "%MODE%"=="publish" goto :do_push
echo.
set "CONFIRM="
set /p "CONFIRM=  确认推送到 !BRANCH! (输入 y 确认,其他任意键取消): "
if /i "!CONFIRM!"=="y" goto :do_push
echo   已取消推送,本地提交保持不变。
exit /b 0

:do_push
call :push origin
if errorlevel 1 exit /b 1
if "%TARGET%"=="gitee" goto :push_gitee_done
call :push github
if errorlevel 1 exit /b 1
:push_gitee_done
if "%TARGET%"=="github" goto :push_done
call :push gitee
if errorlevel 1 exit /b 1
:push_done

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

rem 工作树必须已提交:脚本不替你 commit,所以要先把这件事说清楚。
:check_worktree_committed
set "DIRTY="
for /f "usebackq delims=" %%i in (`git status --porcelain`) do set "DIRTY=1"
if not defined DIRTY exit /b 0
echo   失败: 工作树有未提交的改动,本脚本不会代为提交。
for /f "usebackq delims=" %%i in (`git status --porcelain`) do echo     !  %%i
echo.
echo   请先自行提交(建议 Conventional Commits),例如:
echo       git add -A
echo       git commit -m "feat(scope): 简述本次变更"
echo   然后再运行本脚本;只想校验而不发布可用: deploy-pages.bat check
exit /b 1

:count_ahead
set "AHEAD="
git rev-list --count origin/!BRANCH!..HEAD >"%TEMP%\csgate_ahead.txt" 2>nul
set "ERR=%ERRORLEVEL%"
if not "%ERR%"=="0" exit /b 0
set /p "AHEAD="<"%TEMP%\csgate_ahead.txt"
del "%TEMP%\csgate_ahead.txt" >nul 2>&1
exit /b 0

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
echo   未检测到 python,跳过 xlsx 契约测试、CLI 冒烟测试与门禁守卫测试
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
rem 未配置该远程时必须返回 0:用 `goto :eof` 直接退出子例程会把上一步的 errorlevel 1 带给调用方,
rem 导致 target=both 在 origin 已推成之后仍然误报失败退出。
git remote get-url %1 >nul 2>&1
if not errorlevel 1 goto :push_run
echo   跳过: 未配置远程 '%1'
exit /b 0

:push_run
echo   推送到 %1 ^(!BRANCH!^)...
git push -u %1 !BRANCH!
set "ERR=%ERRORLEVEL%"
if not "%ERR%"=="0" echo   失败: 推送到 %1 未成功 ^(exit %ERR%^)
if not "%ERR%"=="0" exit /b 1
exit /b 0
