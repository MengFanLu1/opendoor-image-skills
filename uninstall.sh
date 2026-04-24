#!/usr/bin/env bash
set -euo pipefail

CLAUDE_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
SKILL_DIR="$CLAUDE_DIR/skills/opendoor-image-skills"
SETTINGS="$CLAUDE_DIR/settings.json"

echo "OpenDoor Image Skills - 卸载程序"
echo "================================="

# 1. 删除 skill 目录
if [ -d "$SKILL_DIR" ]; then
    rm -rf "$SKILL_DIR"
    echo "已删除: $SKILL_DIR"
else
    echo "Skill 目录不存在，跳过"
fi

# 2. 从 settings.json 移除 hook
if [ -f "$SETTINGS" ] && command -v python3 &>/dev/null; then
    python3 - <<PYEOF
import json

settings_path = "$SETTINGS"
matcher = "画|生成图片|出图|制图|帮我画|draw|generate image|create image|make image|image generation"

try:
    with open(settings_path, "r", encoding="utf-8") as f:
        settings = json.load(f)
except (json.JSONDecodeError, FileNotFoundError):
    print("settings.json 读取失败，跳过")
    exit(0)

hooks = settings.get("hooks", {})
prompt_hooks = hooks.get("UserPromptSubmit", [])
original_len = len(prompt_hooks)
prompt_hooks = [h for h in prompt_hooks if h.get("matcher") != matcher]

if len(prompt_hooks) < original_len:
    hooks["UserPromptSubmit"] = prompt_hooks
    if not prompt_hooks:
        del hooks["UserPromptSubmit"]
    if not hooks:
        del settings["hooks"]
    with open(settings_path, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("Hook 已移除")
else:
    print("未找到对应 Hook，跳过")

# 清理 env 变量（如果存在旧版安装）
env = settings.get("env", {})
if "OPENDOOR_IMAGE_API_KEY" in env:
    del env["OPENDOOR_IMAGE_API_KEY"]
    if not env:
        del settings["env"]
    with open(settings_path, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("已从 settings.json 清理旧版 API Key")
PYEOF
else
    echo "无法清理 settings.json（需要 python3），请手动编辑"
fi

echo ""
echo "卸载完成！"
echo "注意: 已生成的图片保留在 ~/generated_images/ 目录中"
