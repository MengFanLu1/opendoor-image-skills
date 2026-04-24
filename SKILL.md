---
name: opendoor-image-skills
description: AI image generation via OpenDoor Hub — supports NanoBanana (Gemini format) and gpt-image-2 (OpenAI format), auto-archives locally. Use when the user wants to generate images, draw pictures, or create AI art.
origin: ECC
---

# OpenDoor Image - AI 图片生成与归档

通过 code-opendoor 中转站调用图片生成模型，自动按日期+序号归档保存。

## When to Activate

- User wants to generate an image from a text prompt
- User says "画", "生成图片", "出图", "制图", "帮我画", "draw", "generate image", "create image", or similar
- Any text-to-image generation task

## 支持模型

- `gemini-3.1-flash-image`（Nano Banana 2，默认，速度快）
- `gemini-3-pro-image-preview`（Nano Banana Pro，质量高）
- `gpt-image-2`（GPT Image 2，OpenAI 格式）

NanoBanana 系列均走 Gemini 格式接口，gpt-image-2 走 OpenAI Images 格式接口。

## 完整流程（两步，必须按顺序执行）

### 第一步：确定运行时和脚本路径

安装时自动检测运行时（优先 Python，其次 Node.js 18+）。根据安装结果选择对应命令：

**Python 运行时**（已安装 Python 3）：
- macOS/Linux: `~/.claude/skills/opendoor-image-skills/.venv/bin/python3 <repo_dir>/scripts/generate.py`
- Windows: `~\.claude\skills\opendoor-image-skills\.venv\Scripts\python.exe <repo_dir>\scripts\generate.py`

**Node.js 运行时**（仅有 Node.js 18+）：
- macOS/Linux/Windows: `node <repo_dir>/scripts/generate.js`

其中 `<repo_dir>` 是项目克隆目录（通常为 `~/code/opendoor-image-skills`）。

### 第二步：生成图片

```bash
# Python - macOS / Linux
~/.claude/skills/opendoor-image-skills/.venv/bin/python3 ~/code/opendoor-image-skills/scripts/generate.py "提示词"

# Python - Windows (PowerShell)
~\.claude\skills\opendoor-image-skills\.venv\Scripts\python.exe ~\code\opendoor-image-skills\scripts\generate.py "提示词"

# Node.js - 所有平台
node ~/code/opendoor-image-skills/scripts/generate.js "提示词"
```

指定模型：
```bash
# Python
~/.claude/skills/opendoor-image-skills/.venv/bin/python3 ~/code/opendoor-image-skills/scripts/generate.py "提示词" --model gpt-image-2

# Node.js
node ~/code/opendoor-image-skills/scripts/generate.js "提示词" --model gpt-image-2
```

脚本成功后输出图片路径，例如：
```
图片已保存: ~/generated_images/20260409_001_一只可爱的猫_abc123.png
```

注意：实际输出的是绝对路径，不同操作系统路径格式不同：
- macOS: `/Users/<username>/generated_images/...`
- Linux: `/home/<username>/generated_images/...`
- Windows: `C:\Users\<username>\generated_images\...`

### 第三步：展示图片

用 `Read` 工具读取上一步输出的图片绝对路径，直接展示给用户。

## 参数说明

| 参数 | 说明 |
|------|------|
| prompt（必填） | 图片提示词 |
| --model / -m | 模型名称，默认 gemini-3.1-flash-image |
| --output / -o | 输出目录，默认 ~/generated_images |
| --size / -s | 图片尺寸，仅 gpt-image-2 有效（如 1024x1024） |
| --quality / -q | 图片质量，仅 gpt-image-2 有效（low/medium/high） |
| --list / -l | 列出已生成的图片 |

## 环境变量

| 变量 | 必填 | 说明 |
|------|------|------|
| OPENDOOR_IMAGE_API_KEY | 是 | API 密钥 |
| OPENDOOR_IMAGE_API_BASE | 否 | API 基础地址（默认 https://api.code-opendoor.com） |
| OPENDOOR_IMAGE_MODEL | 否 | 模型名称（默认 gemini-3.1-flash-image） |
| OPENDOOR_IMAGE_OUTPUT_DIR | 否 | 输出目录（默认 ~/generated_images） |
| OPENDOOR_IMAGE_SIZE | 否 | 图片尺寸，仅 gpt-image-2 有效（默认 1024x1024） |
| OPENDOOR_IMAGE_QUALITY | 否 | 图片质量，仅 gpt-image-2 有效（默认 low） |
