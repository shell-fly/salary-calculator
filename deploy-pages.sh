#!/usr/bin/env bash
# deploy-pages.sh — 一键校验并部署 Web UI (PWA) 到 GitHub / Gitee Pages
# 用法: bash deploy-pages.sh   (可加参数: gitee|github|both 指定要推送的远程, 默认 both)
set -euo pipefail
cd "$(dirname "$0")"

TARGET="${1:-both}"
OK=1

echo "==============================================="
echo " China Salary Calculator — Pages 部署检查"
echo "==============================================="

# 1) 校验 PWA 必需文件
echo "[1/4] 校验 Web UI / PWA 文件..."
for f in web/index.html web/manifest.webmanifest web/sw.js \
         web/icons/icon-192.png web/icons/icon-512.png web/icons/maskable-512.png \
         web/icons/apple-touch-icon.png; do
  if [ -f "$f" ]; then echo "  ✓ $f"; else echo "  ✗ 缺失: $f"; OK=0; fi
done
[ "$OK" = 1 ] || { echo "文件不完整,请先运行: powershell -File web/gen-icons.ps1"; exit 1; }

# 2) 校验 git 仓库与远程
echo "[2/4] 检查 git 远程..."
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

# 3) 提交并推送
echo "[3/4] 提交本地改动并推送..."
git add -A
if ! git diff --cached --quiet; then
  git commit -m "chore(deploy): update Web UI / PWA assets" || true
else
  echo "  无待提交改动"
fi
BRANCH=$(git rev-parse --abbrev-ref HEAD)
push() { [ -n "$(git remote -v | awk -v r="$1" '$1==r{print}')" ] && { echo "  推送到 $1 ($BRANCH)..."; git push -u "$1" "$BRANCH"; } || echo "  跳过: 未配置远程 '$1'"; }
case "$TARGET" in
  github) push origin; push github ;;
  gitee)  push gitee; push origin ;;
  *)      push origin; push github; push gitee ;;
esac

# 4) 打印启用步骤
echo "[4/4] 推送完成。到网页控制台启用 Pages(首次一次性操作):"
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
