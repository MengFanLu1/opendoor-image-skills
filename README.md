# opendoor-image-skills

基于 [OpenDoor Hub](https://api.code-opendoor.com) 的 Claude Code AI 图片生成 Skill。

支持 NanoBanana（Gemini 格式）和 gpt-image-2（OpenAI 格式），图片自动按日期+序号归档到本地。

## 快速开始

```bash
git clone https://github.com/menglulu/opendoor-image-skills.git
cd opendoor-image-skills
```

### macOS / Linux

```bash
bash install.sh
```

### Windows (PowerShell)

```powershell
powershell -ExecutionPolicy Bypass -File install.ps1
```

### 跨平台（推荐）

```bash
python3 install.py
```

安装过程会自动检测运行时（优先 Python 3，其次 Node.js 18+），并提示输入 API Key。

也可以稍后手动编辑配置文件：

```
~/.claude/skills/opendoor-image-skills/.env
```

在 [api.code-opendoor.com](https://api.code-opendoor.com) 获取 API 密钥。

## 使用方法

在 Claude Code 中直接说你想要的内容：

```
帮我画一只猫
生成一张夕阳下的海边图片
draw a futuristic city at night
```

Skill 会自动触发。也可以用 `/opendoor-image-skills` 手动调用。

## 支持的模型

| 模型 | 说明 | 接口格式 |
|------|------|----------|
| `gemini-3.1-flash-image` | Nano Banana 2，速度快（默认） | Gemini |
| `gemini-3-pro-image-preview` | Nano Banana Pro，质量高 | Gemini |
| `gpt-image-2` | GPT Image 2 | OpenAI |

指定模型：在请求中说明，或在 `.env` 文件中设置：

```
OPENDOOR_IMAGE_MODEL=gpt-image-2
```

## 运行时

安装脚本自动检测可用运行时，**优先使用 Python 3，其次 Node.js 18+**。

| 运行时 | 脚本 | 依赖 |
|--------|------|------|
| Python 3 | `scripts/generate.py` | `requests`（自动安装到 `.venv`） |
| Node.js 18+ | `scripts/generate.js` | 无（使用 Node.js 内置 API） |

两种运行时功能完全一致，均支持 Gemini 和 OpenAI 格式接口。

## 配置

配置优先级：环境变量 > `.env` 文件 > 默认值

`.env` 文件位置：`~/.claude/skills/opendoor-image-skills/.env`

| 变量 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `OPENDOOR_IMAGE_API_KEY` | 是 | -- | API 密钥 |
| `OPENDOOR_IMAGE_API_BASE` | 否 | `https://api.code-opendoor.com` | API 基础地址 |
| `OPENDOOR_IMAGE_MODEL` | 否 | `gemini-3.1-flash-image` | 默认模型 |
| `OPENDOOR_IMAGE_OUTPUT_DIR` | 否 | `~/generated_images` | 图片保存目录 |
| `OPENDOOR_IMAGE_SIZE` | 否 | `1024x1024` | 图片尺寸（仅 gpt-image-2） |
| `OPENDOOR_IMAGE_QUALITY` | 否 | `low` | 图片质量：low/medium/high（仅 gpt-image-2） |

## 环境要求

- Python 3.8+ **或** Node.js 18+
- Claude Code
- 支持 macOS / Linux / Windows

## 卸载

### macOS / Linux

```bash
bash uninstall.sh
```

### Windows (PowerShell)

```powershell
powershell -ExecutionPolicy Bypass -File uninstall.ps1
```

### 手动卸载

```bash
rm -rf ~/.claude/skills/opendoor-image-skills
```

然后从 `~/.claude/settings.json` 中删除对应的 `UserPromptSubmit` hook。
