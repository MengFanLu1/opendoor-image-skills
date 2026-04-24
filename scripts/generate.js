#!/usr/bin/env node
/**
 * OpenDoor Image - AI 图片生成与归档 (Node.js)
 *
 * 支持两种协议：
 * - Gemini 格式（NanoBanana 系列）
 * - OpenAI Images 格式（gpt-image-2）
 *
 * 配置优先级：环境变量 > .env 文件 > 默认值
 */

import fs from "fs";
import path from "path";
import { randomUUID } from "crypto";
import { parseArgs } from "util";

// Node.js 18+ 原生 fetch，无需额外依赖

// ─── 配置加载 ────────────────────────────────────────────────

function findEnvFile() {
  const candidates = [
    path.join(process.env.HOME || process.env.USERPROFILE, ".claude", "skills", "opendoor-image-skills", ".env"),
    path.join(path.dirname(new URL(import.meta.url).pathname), "..", ".env"),
  ];
  return candidates.find((p) => fs.existsSync(p)) ?? null;
}

function parseEnvFile(envPath) {
  const vars = {};
  const lines = fs.readFileSync(envPath, "utf-8").split("\n");
  for (const raw of lines) {
    const line = raw.trim();
    if (!line || line.startsWith("#") || !line.includes("=")) continue;
    const idx = line.indexOf("=");
    const key = line.slice(0, idx).trim();
    const value = line.slice(idx + 1).trim().replace(/^["']|["']$/g, "");
    if (key && value) vars[key] = value;
  }
  return vars;
}

function loadConfig(overrides = {}) {
  const envPath = findEnvFile();
  const fileVars = envPath ? parseEnvFile(envPath) : {};

  const get = (key, def = "") =>
    overrides[key] || process.env[key] || fileVars[key] || def;

  const apiKey = get("OPENDOOR_IMAGE_API_KEY");
  if (!apiKey) {
    const hint = [
      "请在以下任一位置配置:",
      `  1. ${path.join(process.env.HOME || process.env.USERPROFILE, ".claude", "skills", "opendoor-image-skills", ".env")}`,
      "  2. 环境变量 OPENDOOR_IMAGE_API_KEY",
      "  获取密钥: https://api.code-opendoor.com",
    ].join("\n");
    throw new Error(`未找到 OPENDOOR_IMAGE_API_KEY\n${hint}`);
  }

  return {
    apiKey,
    apiBase: get("OPENDOOR_IMAGE_API_BASE", "https://api.code-opendoor.com").replace(/\/$/, ""),
    model: get("OPENDOOR_IMAGE_MODEL", "gemini-3.1-flash-image"),
    size: get("OPENDOOR_IMAGE_SIZE", "1024x1024"),
    quality: get("OPENDOOR_IMAGE_QUALITY", "low"),
  };
}

// ─── 工具函数 ────────────────────────────────────────────────

function isOpenAIModel(model) {
  return model.startsWith("gpt-image") || model.startsWith("dall-e");
}

function sanitizeFilename(text, maxLen = 20) {
  const result = text.replace(/[^a-zA-Z0-9\u4e00-\u9fff\u3400-\u4dbf_]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, maxLen)
    .replace(/^_+|_+$/g, "");
  return result || "untitled";
}

function mimeToExt(mime) {
  const known = { "image/png": "png", "image/jpeg": "jpg", "image/webp": "webp" };
  if (!known[mime]) console.warn(`警告: 未知 MIME 类型 ${mime}，默认使用 png`);
  return known[mime] ?? "png";
}

async function raiseForStatus(resp) {
  if (!resp.ok) {
    let msg;
    try {
      const body = await resp.json();
      msg = JSON.stringify(body).slice(0, 300);
    } catch {
      msg = (await resp.text()).slice(0, 300);
    }
    throw new Error(`API 返回 ${resp.status}: ${msg}`);
  }
}

// ─── 文件锁（跨平台，基于 .lock 文件 + 重试） ───────────────

function acquireLock(lockPath, timeout = 10000) {
  const start = Date.now();
  while (true) {
    try {
      fs.writeFileSync(lockPath, String(process.pid), { flag: "wx" });
      return;
    } catch (e) {
      if (e.code !== "EEXIST") throw e;
      if (Date.now() - start > timeout) throw new Error("获取文件锁超时");
      // 简单自旋等待
      const end = Date.now() + 50;
      while (Date.now() < end) {}
    }
  }
}

function releaseLock(lockPath) {
  try { fs.unlinkSync(lockPath); } catch {}
}

// ─── 索引管理 ────────────────────────────────────────────────

function loadIndex(outDir) {
  const indexPath = path.join(outDir, ".index.json");
  if (!fs.existsSync(indexPath)) return {};
  try {
    return JSON.parse(fs.readFileSync(indexPath, "utf-8"));
  } catch {
    return {};
  }
}

function saveIndex(outDir, index) {
  const indexPath = path.join(outDir, ".index.json");
  const tmpPath = indexPath + ".tmp";
  fs.writeFileSync(tmpPath, JSON.stringify(index, null, 2), "utf-8");
  fs.renameSync(tmpPath, indexPath);
}

function calcNextSequence(index, dateStr) {
  let max = 0;
  for (const entry of Object.values(index)) {
    const m = entry.filename?.match(/^\d{8}_(\d{3})_/);
    if (m && entry.filename.startsWith(dateStr)) {
      max = Math.max(max, parseInt(m[1], 10));
    }
  }
  return max + 1;
}

// ─── API 调用 ────────────────────────────────────────────────

async function callGemini(prompt, config) {
  const url = `${config.apiBase}/v1beta/models/${config.model}:generateContent`;
  const resp = await fetch(url, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${config.apiKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      contents: [{ parts: [{ text: prompt }] }],
      generationConfig: { responseModalities: ["TEXT", "IMAGE"] },
    }),
    signal: AbortSignal.timeout(120_000),
  });
  await raiseForStatus(resp);
  const data = await resp.json();

  const parts = data?.candidates?.[0]?.content?.parts ?? [];
  for (const part of parts) {
    if (part.inlineData) {
      return {
        bytes: Buffer.from(part.inlineData.data, "base64"),
        mime: part.inlineData.mimeType ?? "image/png",
      };
    }
  }
  throw new Error(`Gemini 响应中未找到图片数据\n${JSON.stringify(data).slice(0, 500)}`);
}

async function callOpenAIImages(prompt, config) {
  const url = `${config.apiBase}/v1/images/generations`;
  const resp = await fetch(url, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${config.apiKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model: config.model,
      prompt,
      size: config.size,
      quality: config.quality,
    }),
    signal: AbortSignal.timeout(120_000),
  });
  await raiseForStatus(resp);
  const data = await resp.json();

  const b64 = data?.data?.[0]?.b64_json;
  if (!b64) throw new Error(`解析 OpenAI Images 响应失败\n${JSON.stringify(data).slice(0, 500)}`);
  return { bytes: Buffer.from(b64, "base64"), mime: "image/png" };
}

// ─── 主功能 ──────────────────────────────────────────────────

async function generateImage(prompt, opts = {}) {
  const config = loadConfig({
    OPENDOOR_IMAGE_MODEL: opts.model,
    OPENDOOR_IMAGE_SIZE: opts.size,
    OPENDOOR_IMAGE_QUALITY: opts.quality,
  });

  const outDir = path.resolve(
    (opts.outputDir || process.env.OPENDOOR_IMAGE_OUTPUT_DIR || path.join(process.env.HOME || process.env.USERPROFILE, "generated_images"))
      .replace(/^~/, process.env.HOME || process.env.USERPROFILE)
  );
  fs.mkdirSync(outDir, { recursive: true });

  console.log(`正在生成: ${prompt}`);
  console.log(`模型: ${config.model}`);

  let result;
  try {
    result = isOpenAIModel(config.model)
      ? await callOpenAIImages(prompt, config)
      : await callGemini(prompt, config);
  } catch (e) {
    throw new Error(`生成失败: ${e.message}`);
  }

  const { bytes, mime } = result;
  const ext = mimeToExt(mime);
  const now = new Date();
  const dateStr = now.toISOString().slice(0, 10).replace(/-/g, "");
  const contentHash = randomUUID().replace(/-/g, "");
  const lockPath = path.join(outDir, ".index.lock");

  acquireLock(lockPath);
  let filename, targetPath, createdAt;
  try {
    const index = loadIndex(outDir);
    const seq = calcNextSequence(index, dateStr);
    const desc = sanitizeFilename(prompt);
    filename = `${dateStr}_${String(seq).padStart(3, "0")}_${desc}_${contentHash.slice(0, 6)}.${ext}`;
    targetPath = path.join(outDir, filename);

    fs.writeFileSync(targetPath, bytes);

    createdAt = now.toISOString();
    index[contentHash] = { filename, prompt, model: config.model, created_at: createdAt, path: targetPath };
    saveIndex(outDir, index);
  } finally {
    releaseLock(lockPath);
  }

  const sizeKb = (bytes.length / 1024).toFixed(1);
  console.log(`图片已保存: ${targetPath}`);
  console.log(`大小: ${sizeKb} KB`);

  return { path: targetPath, filename, prompt, created_at: createdAt, size_kb: parseFloat(sizeKb) };
}

function listImages(opts = {}) {
  const outDir = path.resolve(
    (opts.outputDir || process.env.OPENDOOR_IMAGE_OUTPUT_DIR || path.join(process.env.HOME || process.env.USERPROFILE, "generated_images"))
      .replace(/^~/, process.env.HOME || process.env.USERPROFILE)
  );

  if (!fs.existsSync(outDir)) {
    console.log(`目录不存在: ${outDir}`);
    return;
  }

  const limit = Math.min(opts.limit ?? 20, 200);
  const index = loadIndex(outDir);

  if (Object.keys(index).length > 0) {
    const entries = Object.values(index).sort((a, b) =>
      (b.created_at ?? "").localeCompare(a.created_at ?? "")
    );
    console.log(`\n生成的图片 (共 ${entries.length} 张):\n`);
    for (const entry of entries.slice(0, limit)) {
      let sizeKb = 0;
      try { sizeKb = (fs.statSync(entry.path).size / 1024).toFixed(1); } catch {}
      const created = (entry.created_at ?? "").slice(0, 16).replace("T", " ");
      console.log(`  ${entry.filename}`);
      console.log(`    提示词: ${(entry.prompt ?? "").slice(0, 30)}  模型: ${entry.model}  大小: ${sizeKb} KB  时间: ${created}`);
    }
    if (entries.length > limit) console.log(`\n... 还有 ${entries.length - limit} 张`);
    return;
  }

  // fallback：遍历文件系统
  const files = fs.readdirSync(outDir)
    .filter((f) => /\.(png|jpg|webp)$/.test(f))
    .map((f) => ({ name: f, stat: fs.statSync(path.join(outDir, f)) }))
    .sort((a, b) => b.name.localeCompare(a.name));

  console.log(`\n生成的图片 (共 ${files.length} 张):\n`);
  for (const { name, stat } of files.slice(0, limit)) {
    const sizeKb = (stat.size / 1024).toFixed(1);
    const created = new Date(stat.mtimeMs).toISOString().slice(0, 16).replace("T", " ");
    console.log(`  ${name}  (${sizeKb} KB | ${created})`);
  }
  if (files.length > limit) console.log(`\n... 还有 ${files.length - limit} 张`);
}

// ─── CLI 入口 ────────────────────────────────────────────────

const { values, positionals } = parseArgs({
  args: process.argv.slice(2),
  options: {
    model: { type: "string", short: "m" },
    output: { type: "string", short: "o" },
    list: { type: "boolean", short: "l", default: false },
    size: { type: "string", short: "s" },
    quality: { type: "string", short: "q" },
  },
  allowPositionals: true,
});

try {
  if (values.list) {
    listImages({ outputDir: values.output });
  } else if (positionals.length > 0) {
    await generateImage(positionals[0], {
      model: values.model,
      outputDir: values.output,
      size: values.size,
      quality: values.quality,
    });
  } else {
    console.log("用法: node generate.js <提示词> [--model <模型>] [--output <目录>]");
    console.log("      node generate.js --list");
    process.exit(1);
  }
} catch (e) {
  console.error(`错误: ${e.message}`);
  process.exit(1);
}
