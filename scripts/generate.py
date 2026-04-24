#!/usr/bin/env python3
"""
OpenDoor Image - AI 图片生成与归档

支持两种协议：
- Gemini 格式（NanoBanana 系列）: POST /v1beta/models/{model}:generateContent
- OpenAI Images 格式（gpt-image-2）: POST /v1/images/generations

从环境变量读取配置:
- OPENDOOR_IMAGE_API_KEY: API 密钥 (必需)
- OPENDOOR_IMAGE_API_BASE: API 基础地址 (默认: https://api.code-opendoor.com)
- OPENDOOR_IMAGE_MODEL: 模型名称 (默认: gemini-3.1-flash-image)
- OPENDOOR_IMAGE_OUTPUT_DIR: 输出目录 (默认: ~/generated_images)
- OPENDOOR_IMAGE_SIZE: 图片尺寸，仅 gpt-image-2 有效 (默认: 1024x1024)
- OPENDOOR_IMAGE_QUALITY: 图片质量，仅 gpt-image-2 有效 (默认: low)

使用方法:
    python3 generate.py "一只可爱的猫"
    python3 generate.py "夕阳下的海边" --model gpt-image-2
    python3 generate.py --list
"""

import os
import sys
import json
import base64
import uuid
import re
import argparse
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    import requests
except ImportError:
    print("需要安装 requests: pip install requests")
    sys.exit(1)


def _find_env_file() -> Optional[Path]:
    """按优先级查找 .env 文件：skill 安装目录 > 项目目录"""
    candidates = [
        Path.home() / ".claude" / "skills" / "opendoor-image-skills" / ".env",
        Path(__file__).resolve().parent.parent / ".env",
    ]
    for p in candidates:
        if p.is_file():
            return p
    return None


def _parse_env_file(env_path: Path) -> dict[str, str]:
    """解析 .env 文件，忽略注释和空行"""
    result = {}
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and value:
                result[key] = value
    return result


def load_config() -> dict:
    env_file = _find_env_file()
    file_vars = _parse_env_file(env_file) if env_file else {}

    def _get(key: str, default: str = "") -> str:
        """环境变量优先，.env 文件次之，最后用默认值"""
        return os.getenv(key) or file_vars.get(key) or default

    config = {
        "api_key": _get("OPENDOOR_IMAGE_API_KEY"),
        "api_base": _get("OPENDOOR_IMAGE_API_BASE", "https://api.code-opendoor.com").rstrip("/"),
        "model": _get("OPENDOOR_IMAGE_MODEL", "gemini-3.1-flash-image"),
        "size": _get("OPENDOOR_IMAGE_SIZE", "1024x1024"),
        "quality": _get("OPENDOOR_IMAGE_QUALITY", "low"),
    }
    if not config["api_key"]:
        hint = "请在以下任一位置配置:\n"
        hint += f"  1. {Path.home() / '.claude' / 'skills' / 'opendoor-image-skills' / '.env'}\n"
        hint += f"  2. 环境变量 OPENDOOR_IMAGE_API_KEY\n"
        hint += "  获取密钥: https://api.code-opendoor.com"
        raise ValueError(f"未找到 OPENDOOR_IMAGE_API_KEY\n{hint}")
    return config


def is_openai_image_model(model: str) -> bool:
    return model.startswith("gpt-image") or model.startswith("dall-e")


def sanitize_filename(text: str, max_len: int = 20) -> str:
    text = re.sub(r'[^a-zA-Z0-9一-鿿㐀-䶿_]+', '_', text)
    result = text.strip('_')[:max_len].strip('_')
    return result or "untitled"


def _calc_next_sequence(index: dict, date_str: str) -> int:
    max_seq = 0
    for entry in index.values():
        fname = entry.get("filename", "")
        m = re.match(r'^\d{8}_(\d{3})_', fname)
        if m and fname.startswith(date_str):
            try:
                max_seq = max(max_seq, int(m.group(1)))
            except ValueError:
                pass
    return max_seq + 1


def load_index(output_dir: Path) -> dict:
    index_file = output_dir / ".index.json"
    if index_file.exists():
        try:
            with open(index_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save_index(output_dir: Path, index: dict) -> None:
    index_file = output_dir / ".index.json"
    tmp_file = index_file.with_suffix('.tmp')
    try:
        with open(tmp_file, 'w', encoding='utf-8') as f:
            json.dump(index, f, ensure_ascii=False, indent=2)
        tmp_file.replace(index_file)
    except OSError as e:
        print(f"保存索引失败: {e}")
        tmp_file.unlink(missing_ok=True)


def _lock_index(output_dir: Path):
    """返回 .index.lock 文件对象（已加锁），调用方负责解锁关闭"""
    import platform
    lock_path = output_dir / ".index.lock"
    f = open(lock_path, 'w', encoding='utf-8')
    if platform.system() == "Windows":
        import msvcrt
        msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
    else:
        import fcntl
        fcntl.flock(f, fcntl.LOCK_EX)
    return f


def _unlock_index(lock_file) -> None:
    import platform
    if platform.system() == "Windows":
        import msvcrt
        lock_file.seek(0)
        msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl
        fcntl.flock(lock_file, fcntl.LOCK_UN)
    lock_file.close()


def _raise_for_status(resp) -> None:
    if not resp.ok:
        try:
            body = resp.json()
            msg = json.dumps(body, ensure_ascii=False)[:300]
        except Exception:
            msg = resp.text[:300]
        raise ValueError(f"API 返回 {resp.status_code}: {msg}")


def call_gemini(prompt: str, config: dict) -> tuple[bytes, str]:
    """调用 Gemini 格式接口（NanoBanana 系列）"""
    model = config["model"]
    url = f"{config['api_base']}/v1beta/models/{model}:generateContent"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]}
    }
    resp = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {config['api_key']}",
            "Content-Type": "application/json"
        },
        json=payload,
        timeout=120
    )
    _raise_for_status(resp)
    data = resp.json()

    try:
        parts = data["candidates"][0]["content"]["parts"]
        for part in parts:
            if "inlineData" in part:
                return base64.b64decode(part["inlineData"]["data"]), part["inlineData"].get("mimeType", "image/png")
    except (KeyError, IndexError) as e:
        raise ValueError(f"解析 Gemini 响应失败: {e}\n响应: {json.dumps(data, ensure_ascii=False)[:500]}")

    raise ValueError(f"Gemini 响应中未找到图片数据\n响应: {json.dumps(data, ensure_ascii=False)[:500]}")


def call_openai_images(prompt: str, config: dict) -> tuple[bytes, str]:
    """调用 OpenAI Images 格式接口（gpt-image-2）"""
    url = f"{config['api_base']}/v1/images/generations"
    payload = {
        "model": config["model"],
        "prompt": prompt,
        "size": config["size"],
        "quality": config["quality"],
    }
    resp = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {config['api_key']}",
            "Content-Type": "application/json"
        },
        json=payload,
        timeout=120
    )
    _raise_for_status(resp)
    data = resp.json()

    try:
        b64 = data["data"][0]["b64_json"]
        return base64.b64decode(b64), "image/png"
    except (KeyError, IndexError) as e:
        raise ValueError(f"解析 OpenAI Images 响应失败: {e}\n响应: {json.dumps(data, ensure_ascii=False)[:500]}")


def mime_to_ext(mime: str) -> str:
    known = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}
    if mime not in known:
        print(f"警告: 未知 MIME 类型 {mime!r}，默认使用 png")
    return known.get(mime, "png")


def generate_image(
    prompt: str,
    output_dir: Optional[str] = None,
    model: Optional[str] = None,
    size: Optional[str] = None,
    quality: Optional[str] = None,
) -> dict:
    config = load_config()
    if model:
        config["model"] = model
    if size:
        config["size"] = size
    if quality:
        config["quality"] = quality

    if output_dir is None:
        out_path = Path(os.getenv("OPENDOOR_IMAGE_OUTPUT_DIR", str(Path.home() / "generated_images"))).expanduser()
    else:
        out_path = Path(output_dir).expanduser()
    out_path.mkdir(parents=True, exist_ok=True)

    print(f"正在生成: {prompt}")
    print(f"模型: {config['model']}")

    try:
        if is_openai_image_model(config["model"]):
            image_bytes, mime = call_openai_images(prompt, config)
        else:
            image_bytes, mime = call_gemini(prompt, config)
    except (requests.exceptions.RequestException, ValueError) as e:
        raise RuntimeError(f"生成失败: {e}") from e

    ext = mime_to_ext(mime)
    now = datetime.now()
    date_str = now.strftime("%Y%m%d")
    content_hash = uuid.uuid4().hex[:12]

    lock_file = _lock_index(out_path)
    try:
        index = load_index(out_path)
        seq = _calc_next_sequence(index, date_str)
        desc = sanitize_filename(prompt)
        filename = f"{date_str}_{seq:03d}_{desc}_{content_hash[:6]}.{ext}"
        target_path = out_path / filename

        with open(target_path, "wb") as f:
            f.write(image_bytes)

        created_at = now.isoformat()
        index[content_hash] = {
            "filename": filename,
            "prompt": prompt,
            "model": config["model"],
            "created_at": created_at,
            "path": str(target_path)
        }
        save_index(out_path, index)
    finally:
        _unlock_index(lock_file)

    size_kb = len(image_bytes) / 1024
    print(f"图片已保存: {target_path}")
    print(f"大小: {size_kb:.1f} KB")

    return {
        "path": str(target_path),
        "filename": filename,
        "prompt": prompt,
        "created_at": created_at,
        "size_kb": size_kb
    }


def list_images(output_dir: Optional[str] = None, limit: int = 20) -> None:
    if output_dir is None:
        out_path = Path(os.getenv("OPENDOOR_IMAGE_OUTPUT_DIR", str(Path.home() / "generated_images"))).expanduser()
    else:
        out_path = Path(output_dir).expanduser()

    if not out_path.exists():
        print(f"目录不存在: {out_path}")
        return

    limit = min(limit, 200)

    # 优先从 .index.json 读取（含 prompt/model 元数据）
    index = load_index(out_path)
    if index:
        entries = sorted(index.values(), key=lambda x: x.get("created_at", ""), reverse=True)
        print(f"\n生成的图片 (共 {len(entries)} 张):\n")
        for entry in entries[:limit]:
            path = Path(entry.get("path", ""))
            size_kb = path.stat().st_size / 1024 if path.exists() else 0
            created = entry.get("created_at", "")[:16].replace("T", " ")
            prompt_short = entry.get("prompt", "")[:30]
            model = entry.get("model", "")
            print(f"  {entry.get('filename', path.name)}")
            print(f"    提示词: {prompt_short}  模型: {model}  大小: {size_kb:.1f} KB  时间: {created}")
        if len(entries) > limit:
            print(f"\n... 还有 {len(entries) - limit} 张")
        return

    # fallback：直接遍历文件系统
    entries_fs = []
    for p in out_path.iterdir():
        if p.suffix in ('.jpg', '.png', '.webp'):
            try:
                entries_fs.append((p, p.stat()))
            except OSError:
                pass
    entries_fs.sort(key=lambda x: x[0].name, reverse=True)

    print(f"\n生成的图片 (共 {len(entries_fs)} 张):\n")
    for img, stat in entries_fs[:limit]:
        size_kb = stat.st_size / 1024
        created = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
        print(f"  {img.name}  ({size_kb:.1f} KB | {created})")

    if len(entries_fs) > limit:
        print(f"\n... 还有 {len(entries_fs) - limit} 张")


def main() -> None:
    parser = argparse.ArgumentParser(description="OpenDoor Image - AI 图片生成与归档")
    parser.add_argument("prompt", nargs="?", help="图片生成提示词")
    parser.add_argument("--output", "-o", dest="output_dir", help="输出目录")
    parser.add_argument("--list", "-l", action="store_true", help="列出已生成的图片")
    parser.add_argument("--model", "-m", help="模型名称")
    parser.add_argument("--size", "-s", help="图片尺寸，仅 gpt-image-2 有效（如 1024x1024）")
    parser.add_argument("--quality", "-q", help="图片质量，仅 gpt-image-2 有效（low/medium/high）")
    args = parser.parse_args()

    try:
        if args.list:
            list_images(args.output_dir)
        elif args.prompt:
            generate_image(args.prompt, args.output_dir, args.model, args.size, args.quality)
        else:
            parser.print_help()
            sys.exit(1)
    except (ValueError, RuntimeError) as e:
        print(f"错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
