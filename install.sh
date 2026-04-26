#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
SKILL_DIR="$CLAUDE_DIR/skills/opendoor-image-skills"
SETTINGS="$CLAUDE_DIR/settings.json"
# venv 放到用户目录，避免 /opt 等只读场景权限问题
VENV_DIR="${OPENDOOR_VENV_DIR:-$SKILL_DIR/.venv}"

echo "OpenDoor Image Skills - 安装程序"
echo "================================="

# ─── 运行时检测（优先 Python，其次 Node.js）────────────────────

RUNTIME=""
PYTHON_CMD=""
NODE_CMD=""

for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        VER=$("$cmd" -c "import sys; print(sys.version_info.major)" 2>/dev/null || echo "0")
        if [ "$VER" = "3" ]; then
            PYTHON_CMD="$cmd"
            RUNTIME="python"
            break
        fi
    fi
done

if [ -z "$RUNTIME" ]; then
    for cmd in node nodejs; do
        if command -v "$cmd" &>/dev/null; then
            VER=$("$cmd" -e "process.exit(parseInt(process.versions.node) >= 18 ? 0 : 1)" 2>/dev/null && echo "ok" || echo "")
            if [ "$VER" = "ok" ]; then
                NODE_CMD="$cmd"
                RUNTIME="node"
                break
            fi
        fi
    done
fi

if [ -z "$RUNTIME" ]; then
    echo "错误: 需要 Python 3 或 Node.js 18+，请先安装其中一个"
    exit 1
fi

echo "运行时: $RUNTIME"

# ─── 安装 skill 到 Claude Code ────────────────────────────────

echo "正在安装 skill..."
mkdir -p "$SKILL_DIR"
cp "$REPO_DIR/SKILL.md" "$SKILL_DIR/SKILL.md"
echo "$REPO_DIR" > "$SKILL_DIR/.repo_path"
echo "Skill 已安装到 $SKILL_DIR"

# ─── Python: 创建 venv 并安装依赖 ────────────────────────────

if [ "$RUNTIME" = "python" ]; then
    echo "正在安装 Python 依赖..."
    if ! "$PYTHON_CMD" -m venv "$VENV_DIR"; then
        echo "错误: 无法创建虚拟环境，请检查以上错误信息"
        if command -v apt-get &>/dev/null; then
            echo "  Debian/Ubuntu 可尝试: sudo apt install python3-venv python3-full"
        fi
        exit 1
    fi
    "$VENV_DIR/bin/pip" install -q -r "$REPO_DIR/requirements.txt"
    echo "依赖安装完成"
fi

# ─── 修改 settings.json（幂等）────────────────────────────────

if [ ! -f "$SETTINGS" ]; then
    echo "{}" > "$SETTINGS"
fi

cp "$SETTINGS" "$SETTINGS.bak"

"${PYTHON_CMD:-python3}" - <<PYEOF 2>&1
import json, sys, os

settings_path = "$SETTINGS"

with open(settings_path, "r", encoding="utf-8") as f:
    settings = json.load(f)

hook_command = (
    "echo 'INSTRUCTION: The user wants to generate an image. "
    "You MUST use the opendoor-image-skills skill to fulfill this request. "
    "Do not attempt to draw ASCII art or describe the image in text.'"
)
hook_entry = {
    "matcher": "画|生成图片|出图|制图|帮我画|draw|generate image|create image|make image|image generation",
    "hooks": [{"type": "command", "command": hook_command}]
}

hooks = settings.setdefault("hooks", {})
prompt_hooks = hooks.setdefault("UserPromptSubmit", [])

already_installed = any(
    h.get("matcher") == hook_entry["matcher"]
    for h in prompt_hooks
)
if not already_installed:
    prompt_hooks.append(hook_entry)
    with open(settings_path, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("Hook 已添加，settings.json 更新完成")
else:
    print("Hook 已存在，跳过")
PYEOF

# ─── 创建 .env 文件 ───────────────────────────────────────────

ENV_FILE="$SKILL_DIR/.env"
if [ ! -f "$ENV_FILE" ]; then
    cp "$REPO_DIR/.env.example" "$ENV_FILE"
    echo ".env 文件已创建: $ENV_FILE"
else
    echo ".env 文件已存在，跳过"
fi

CURRENT_KEY=$(grep -E '^OPENDOOR_IMAGE_API_KEY=.+' "$ENV_FILE" 2>/dev/null | head -1 | cut -d= -f2- || true)
if [ -z "$CURRENT_KEY" ]; then
    echo ""
    echo "请输入你的 API 密钥（从 https://api.code-opendoor.com 获取）"
    printf "API Key: "
    read -r API_KEY </dev/tty || API_KEY=""
    if [ -n "$API_KEY" ]; then
        if [[ "$OSTYPE" == "darwin"* ]]; then
            sed -i '' "s|^OPENDOOR_IMAGE_API_KEY=.*|OPENDOOR_IMAGE_API_KEY=$API_KEY|" "$ENV_FILE"
        else
            sed -i "s|^OPENDOOR_IMAGE_API_KEY=.*|OPENDOOR_IMAGE_API_KEY=$API_KEY|" "$ENV_FILE"
        fi
        echo "API Key 已保存"
    else
        echo "跳过，请稍后手动编辑: $ENV_FILE"
    fi
else
    echo "API Key 已配置，跳过"
fi

echo ""
echo "安装完成！"
echo ""
if [ "$RUNTIME" = "python" ]; then
    echo "运行时: Python (.venv)"
    echo "  脚本: $VENV_DIR/bin/python3 $REPO_DIR/scripts/generate.py"
else
    echo "运行时: Node.js"
    echo "  脚本: node $REPO_DIR/scripts/generate.js"
fi
echo ""
echo "使用方法："
echo "  在 Claude Code 中直接说「帮我画一只猫」即可自动触发"
echo "  或使用 /opendoor-image-skills 手动调用"
