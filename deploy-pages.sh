#!/usr/bin/env bash
# deploy-pages.sh — Web UI (PWA) 发布门禁与推送
# 用法:
#   bash deploy-pages.sh                          跑门禁,列出待推送提交并交互确认后推送
#   bash deploy-pages.sh check                    只跑门禁([1/5]-[3/5]),不提交不推送,无副作用(脏工作树也可跑)
#   bash deploy-pages.sh publish [both|gitee|github]   跑门禁后直接推送(免交互,供 CI 使用)
#   bash deploy-pages.sh gitee|github|both         等价于 publish <target>(向后兼容)
# 本脚本不会替你提交:发布前工作树必须干净,提交信息请自己按 Conventional Commits 写好。
# 这样才不会出现一个把真实变更抹平的 "chore(deploy): update Web UI / PWA assets" 大提交。
set -euo pipefail
cd "$(dirname "$0")"

MODE=interactive
TARGET=both
USAGE="用法: bash deploy-pages.sh [check|publish [both|gitee|github]|gitee|github|both]"
case "${1:-}" in
  "" ) MODE=interactive ;;
  check|--check|-c ) MODE=check ;;
  publish|push ) MODE=publish; TARGET="${2:-both}" ;;
  both|gitee|github ) MODE=publish; TARGET="$1" ;;
  * ) echo "$USAGE"; exit 2 ;;
esac
case "$TARGET" in
  both|gitee|github ) ;;
  * ) echo "$USAGE"; exit 2 ;;
esac
OK=1

echo "==============================================="
case "$MODE" in
  check ) echo " 工资计算器（中国） — 发布门禁校验（check：不提交、不推送）" ;;
  publish ) echo " 工资计算器（中国） — 发布门禁 + 推送（publish：免交互，目标 $TARGET）" ;;
  * ) echo " 工资计算器（中国） — 发布门禁 + 推送（确认制，目标 $TARGET）" ;;
esac
echo "==============================================="

# 0) 发布前先做最便宜、也最常踩的检查:工作树必须已提交。放在重型门禁之前,省掉几十秒无效测试。
if [ "$MODE" != "check" ] && git rev-parse --is-inside-work-tree >/dev/null 2>&1 && [ -n "$(git status --porcelain)" ]; then
  echo "  ✗ 失败: 工作树有未提交的改动,本脚本不会代为提交:"
  git status --porcelain | sed 's/^/      /'
  echo ""
  echo "  请先自行提交(建议 Conventional Commits),例如:"
  echo '      git commit -am "feat(scope): 简述本次变更"'
  echo "  然后再运行本脚本;只想校验而不发布可用: bash deploy-pages.sh check"
  exit 1
fi

# 1) 校验 PWA 必需文件
echo "[1/5] 校验 Web UI / PWA 文件..."
for f in web/index.html web/manifest.webmanifest web/sw.js \
         web/icons/icon-192.png web/icons/icon-512.png web/icons/maskable-512.png \
         web/icons/apple-touch-icon.png; do
  if [ -f "$f" ]; then echo "  ✓ $f"; else echo "  ✗ 缺失: $f"; OK=0; fi
done
[ "$OK" = 1 ] || { echo "文件不完整,请先运行: powershell -File web/gen-icons.ps1"; exit 1; }

# 1b) 校验内嵌副本、引擎断言与 Excel 引擎（index.html 内联了 config、引擎与两个 xlsx 模块）
echo "[2/5] 校验内嵌副本、引擎断言与 Excel 测试..."
if command -v node >/dev/null 2>&1; then
  # 内联脚本会重写 index.html。若它本来与已提交版本一致、跑完却变脏了，
  # 说明仓里交付的是旧内嵌副本（源文件改了但忘跑内联）——这正是必须拦住的漂移。
  HTML_WAS_CLEAN=0
  if git diff --quiet -- web/index.html >/dev/null 2>&1; then HTML_WAS_CLEAN=1; fi
  node web/inline-config.mjs >/dev/null || { echo "  ✗ config.json 与 index.html 内嵌副本不一致"; exit 1; }
  node web/inline-compute.mjs >/dev/null || { echo "  ✗ compute.js 与 index.html 内嵌引擎不一致"; exit 1; }
  node web/inline-xlsx.mjs  >/dev/null || { echo "  ✗ xlsx 引擎与 index.html 内嵌副本不一致"; exit 1; }
  if [ "$HTML_WAS_CLEAN" = 1 ] && ! git diff --quiet -- web/index.html >/dev/null 2>&1; then
    echo "  ✗ 内嵌副本漂移: index.html 里交付的是旧副本,脚本已重新生成"
    echo "     请将 web/index.html 一并提交后再发布"
    exit 1
  fi
  echo "  ✓ 内嵌副本已与源文件同步"
  node web/test-compute.js >/dev/null || { echo "  ✗ 计算引擎断言未通过（详情: node web/test-compute.js）"; exit 1; }
  echo "  ✓ 计算引擎断言全部通过"
else
  echo "  ! 未检测到 node,跳过内联一致性校验。改过 config.json 或 web/*.js 后必须手动重跑内联脚本。"
fi
if command -v python3 >/dev/null 2>&1; then
  python3 src/test_xlsx_writer.py >/dev/null || { echo "  ✗ xlsx 契约测试未通过"; exit 1; }
  echo "  ✓ xlsx 契约测试通过（CLI 与网页 Excel 逐字节一致）"
  python3 src/test_cli_smoke.py >/dev/null || { echo "  ✗ CLI 端到端冒烟测试未通过（详情: python3 src/test_cli_smoke.py）"; exit 1; }
  echo "  ✓ CLI 端到端冒烟测试通过（覆盖申报基数、医疗定额、逐月薪资与反推）"
else
  echo "  ! 未检测到 python3,跳过 xlsx 契约测试与 CLI 冒烟测试"
fi

# 2) 校验 git 仓库与远程
echo "[3/5] 检查 git 远程..."
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "  ✗ 当前目录不是 git 仓库"; exit 1
fi
REMOTES=$(git remote -v | awk '{print $1}' | sort -u || true)
if [ -z "$REMOTES" ]; then
  echo "  ! 尚未配置任何远程。请先添加,例如:"
  echo "      git remote add origin https://github.com/<你的用户名>/<仓库名>.git"
  echo "    或 Gitee: git remote add gitee https://gitee.com/<你的用户名>/<仓库名>.git"
else
  echo "  已配置远程: $REMOTES"
fi
BRANCH=$(git rev-parse --abbrev-ref HEAD)
echo "  当前分支: $BRANCH"
AHEAD=""
if git rev-parse --verify --quiet "origin/$BRANCH" >/dev/null 2>&1; then
  AHEAD=$(git rev-list --count "origin/$BRANCH..HEAD" 2>/dev/null || echo "")
fi

# 3) check 模式到此结束：不推送、不打印发布步骤
if [ "$MODE" = "check" ]; then
  echo "[4/5] check 模式：不推送"
  echo "[5/5] check 模式：未发布,故不打印 Pages 控制台启用步骤"
  echo ""
  echo "门禁全部通过 ✅（需要发布请直接运行: bash deploy-pages.sh）"
  exit 0
fi

if [ -n "$AHEAD" ]; then
  echo "  待推送提交: $AHEAD 个"
  if [ "$AHEAD" != "0" ]; then git log --oneline "origin/$BRANCH..HEAD" | sed 's/^/    /'; fi
fi
if [ "$AHEAD" = "0" ]; then
  echo ""
  echo "本地与 origin/$BRANCH 已同步,无需推送。"
  exit 0
fi

# 4) 推送（本脚本不代为提交）
echo "[4/5] 推送到远程..."
echo "  本脚本不代为提交;请确认上面的待推送提交就是你想发布的内容。"
if [ "$MODE" != "publish" ]; then
  printf '  确认推送到 %s (输入 y 确认,其他任意键取消): ' "$BRANCH"
  read -r REPLY || REPLY=""
  if [ "${REPLY:-n}" != "y" ] && [ "${REPLY:-n}" != "Y" ]; then
    echo "  已取消推送,本地提交保持不变。"
    exit 0
  fi
fi
push() {
  if git remote get-url "$1" >/dev/null 2>&1; then
    echo "  推送到 $1 ($BRANCH)..."
    git push -u "$1" "$BRANCH" || { echo "  ✗ 推送到 $1 未成功"; return 1; }
  else
    echo "  跳过: 未配置远程 '$1'"
  fi
}
case "$TARGET" in
  github) push origin; push github ;;
  gitee)  push gitee; push origin ;;
  *)      push origin; push github; push gitee ;;
esac

# 5) 打印启用步骤
echo "[5/5] 推送完成。到网页控制台启用 Pages(首次一次性操作):"
cat <<'EOF'

  ── GitHub Pages ──────────────────────────────
  1) 仓库已内置 .github/workflows/deploy-pages.yml
  2) Settings → Pages → Build and deployment → Source 选 "GitHub Actions"
  3) push 后到 Actions 页看部署进度,成功后访问:
        https://<用户名>.github.io/<仓库名>/
  (若仓库根即站点,URL 带 /<仓库名>/ 子路径;PWA 用相对路径已适配)

  ── Gitee Pages ───────────────────────────────
  1) 需实名认证: 登录 Gitee → 右上角 → 个人设置 → 实名信息
  2) 仓库页 → Services → Gitee Pages → 点 "启用"
  3) 部署分支: master/main;  目录: web  ; 点 "启动"
  4) 访问控制台给出的:
        https://<用户名>.gitee.io/<仓库名>/
  注意: 更新内容后需在 Gitee Pages 页手动点 "更新" 才会重新发布。

  ── 手机安装为 App (PWA) ──────────────────────
  浏览器打开上述网址 → 菜单 "安装/添加到主屏幕" → 得到独立图标、离线可用。

EOF
echo "完成 ✅"
