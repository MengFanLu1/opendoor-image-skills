#!/usr/bin/env python3
"""跨平台安装入口 - 适用于 Linux / macOS / Windows"""

import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent


def get_claude_dir() -> Path:
    custom = os.getenv("CLAUDE_CONFIG_DIR")
    if custom:
        return Path(custom)
    return Path.home() / ".claude"


def detect_runtime() -> tuple[str, str]:
    """返回 (runtime, cmd)，优先 Python 3，其次 Node.js 18+"""
    for cmd in ["python3", "python"]:
        if shutil.which(cmd):
            try:
                ver = subprocess.check_output(
                    [cmd, "-c", "import sys; print(sys.version_info.major)"],
                    text=True, stderr=subprocess.DEVNULL
                ).strip()
                if ver == "3":
                    return "python", cmd
            except Exception:
                pass

    for cmd in ["node", "nodejs"]:
        if shutil.which(cmd):
            try:
                ret = subprocess.call(
                    [cmd, "-e", "process.exit(parseInt(process.versions.node) >= 18 ? 0 : 1)"],
                    stderr=subprocess.DEVNULL
                )
                if ret == 0:
                    return "node", cmd
            except Exception:
                pass

    print("错误: 需要 Python 3 或 Node.js 18+，请先安装其中一个")
    sys.exit(1)


def setup_venv(venv_dir: Path):
    print("正在安装 Python 依赖...")
    if not venv_dir.exists():
        subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)

    if platform.system() == "Windows":
        pip_path = venv_dir / "Scripts" / "pip.exe"
    else:
        pip_path = venv_dir / "bin" / "pip"

    subprocess.run(
        [str(pip_path), "install", "-q", "-r", str(REPO_DIR / "requirements.txt")],
        check=True,
    )
    print("依赖安装完成")


def install_skill(claude_dir: Path) -> Path:
    print("正在安装 skill...")
    skill_dir = claude_dir / "skills" / "opendoor-image-skills"
    skill_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(REPO_DIR / "SKILL.md", skill_dir / "SKILL.md")
    print(f"Skill 已安装到 {skill_dir}")
    return skill_dir


def update_settings(claude_dir: Path):
    settings_path = claude_dir / "settings.json"
    if not settings_path.exists():
        settings_path.write_text("{}", encoding="utf-8")

    backup = settings_path.with_suffix(".json.bak")
    shutil.copy2(settings_path, backup)

    with open(settings_path, "r", encoding="utf-8") as f:
        settings = json.load(f)

    hook_command = (
        "echo 'INSTRUCTION: The user wants to generate an image. "
        "You MUST use the opendoor-image-skills skill to fulfill this request. "
        "Do not attempt to draw ASCII art or describe the image in text.'"
    )
    matcher = "画|生成图片|出图|制图|帮我画|draw|generate image|create image|make image|image generation"
    hook_entry = {
        "matcher": matcher,
        "hooks": [{"type": "command", "command": hook_command}],
    }

    hooks = settings.setdefault("hooks", {})
    prompt_hooks = hooks.setdefault("UserPromptSubmit", [])

    already_installed = any(h.get("matcher") == matcher for h in prompt_hooks)
    if not already_installed:
        prompt_hooks.append(hook_entry)
        with open(settings_path, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print("Hook 已添加，settings.json 更新完成")
    else:
        print("Hook 已存在，跳过")


def setup_env_file(skill_dir: Path):
    env_file = skill_dir / ".env"
    if not env_file.exists():
        shutil.copy2(REPO_DIR / ".env.example", env_file)
        print(f".env 文件已创建: {env_file}")
    else:
        print(".env 文件已存在，跳过")

    with open(env_file, "r", encoding="utf-8") as f:
        content = f.read()

    has_key = any(
        line.strip().startswith("OPENDOOR_IMAGE_API_KEY=") and line.strip().split("=", 1)[1].strip()
        for line in content.splitlines()
    )

    if not has_key:
        print("")
        print("请输入你的 API 密钥（从 https://api.code-opendoor.com 获取）")
        try:
            api_key = input("API Key: ").strip()
        except (EOFError, KeyboardInterrupt):
            api_key = ""
            print("")

        if api_key:
            new_lines = [
                f"OPENDOOR_IMAGE_API_KEY={api_key}" if line.startswith("OPENDOOR_IMAGE_API_KEY=") else line
                for line in content.splitlines()
            ]
            with open(env_file, "w", encoding="utf-8") as f:
                f.write("\n".join(new_lines) + "\n")
            print("API Key 已保存")
        else:
            print(f"跳过，请稍后手动编辑: {env_file}")
    else:
        print("API Key 已配置，跳过")

    return env_file


def main():
    print("OpenDoor Image Skills - 安装程序")
    print("=================================")
    print(f"操作系统: {platform.system()} {platform.release()}")
    print("")

    runtime, runtime_cmd = detect_runtime()
    print(f"运行时: {runtime} ({runtime_cmd})")
    print("")

    claude_dir = get_claude_dir()
    skill_dir = install_skill(claude_dir)

    if runtime == "python":
        venv_dir = skill_dir / ".venv"
        setup_venv(venv_dir)
    else:
        venv_dir = None

    update_settings(claude_dir)
    setup_env_file(skill_dir)

    print("")
    print("安装完成！")
    print("")
    if runtime == "python":
        if platform.system() == "Windows":
            py_exe = venv_dir / "Scripts" / "python.exe"
        else:
            py_exe = venv_dir / "bin" / "python3"
        print(f"运行时: Python (.venv)")
        print(f"  脚本: {py_exe} {REPO_DIR / 'scripts' / 'generate.py'}")
    else:
        print(f"运行时: Node.js")
        print(f"  脚本: node {REPO_DIR / 'scripts' / 'generate.js'}")
    print("")
    print("使用方法：")
    print('  在 Claude Code 中直接说「帮我画一只猫」即可自动触发')
    print("  或使用 /opendoor-image-skills 手动调用")


if __name__ == "__main__":
    main()
