# OpenDoor Image Skills - Windows 安装脚本
# 使用方法: powershell -ExecutionPolicy Bypass -File install.ps1

$ErrorActionPreference = "Stop"

$RepoDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ClaudeDir = if ($env:CLAUDE_CONFIG_DIR) { $env:CLAUDE_CONFIG_DIR } else { Join-Path $env:USERPROFILE ".claude" }
$SkillDir = Join-Path $ClaudeDir "skills\opendoor-image-skills"
$Settings = Join-Path $ClaudeDir "settings.json"

Write-Host "OpenDoor Image Skills - 安装程序"
Write-Host "================================="

# ─── 运行时检测（优先 Python，其次 Node.js）────────────────────

$Runtime = $null
$PythonCmd = $null
$NodeCmd = $null

foreach ($cmd in @("python", "python3")) {
    try {
        $ver = & $cmd -c "import sys; print(sys.version_info.major)" 2>$null
        if ($ver -eq "3") {
            $PythonCmd = $cmd
            $Runtime = "python"
            break
        }
    } catch {}
}

if (-not $Runtime) {
    foreach ($cmd in @("node")) {
        try {
            $ver = & $cmd -e "process.exit(parseInt(process.versions.node) >= 18 ? 0 : 1)" 2>$null
            if ($LASTEXITCODE -eq 0) {
                $NodeCmd = $cmd
                $Runtime = "node"
                break
            }
        } catch {}
    }
}

if (-not $Runtime) {
    Write-Host "错误: 需要 Python 3 或 Node.js 18+，请先安装其中一个" -ForegroundColor Red
    exit 1
}

Write-Host "运行时: $Runtime"

# ─── Python: 创建 venv 并安装依赖 ────────────────────────────

if ($Runtime -eq "python") {
    Write-Host "正在安装 Python 依赖..."
    $VenvDir = Join-Path $RepoDir ".venv"
    if (-not (Test-Path $VenvDir)) {
        & $PythonCmd -m venv $VenvDir
    }
    $PipPath = Join-Path $VenvDir "Scripts\pip.exe"
    & $PipPath install -q -r (Join-Path $RepoDir "requirements.txt")
    Write-Host "依赖安装完成"
}

# ─── 安装 skill 到 Claude Code ────────────────────────────────

Write-Host "正在安装 skill..."
if (-not (Test-Path $SkillDir)) {
    New-Item -ItemType Directory -Path $SkillDir -Force | Out-Null
}
Copy-Item (Join-Path $RepoDir "SKILL.md") (Join-Path $SkillDir "SKILL.md") -Force
Write-Host "Skill 已安装到 $SkillDir"

# ─── 修改 settings.json（幂等）────────────────────────────────

if (-not (Test-Path $Settings)) {
    Set-Content -Path $Settings -Value "{}" -Encoding UTF8
}

Copy-Item $Settings "$Settings.bak" -Force

$SettingsObj = Get-Content $Settings -Raw -Encoding UTF8 | ConvertFrom-Json

if (-not $SettingsObj.hooks) {
    $SettingsObj | Add-Member -NotePropertyName "hooks" -NotePropertyValue @{} -Force
}
if (-not $SettingsObj.hooks.UserPromptSubmit) {
    $SettingsObj.hooks | Add-Member -NotePropertyName "UserPromptSubmit" -NotePropertyValue @() -Force
}

$Matcher = "画|生成图片|出图|制图|帮我画|draw|generate image|create image|make image|image generation"

$AlreadyInstalled = $false
foreach ($h in $SettingsObj.hooks.UserPromptSubmit) {
    if ($h.matcher -eq $Matcher) {
        $AlreadyInstalled = $true
        break
    }
}

if (-not $AlreadyInstalled) {
    $HookCommand = "echo 'INSTRUCTION: The user wants to generate an image. You MUST use the opendoor-image-skills skill to fulfill this request. Do not attempt to draw ASCII art or describe the image in text.'"
    $HookEntry = @{
        matcher = $Matcher
        hooks = @(@{ type = "command"; command = $HookCommand })
    }
    $SettingsObj.hooks.UserPromptSubmit += $HookEntry
    $SettingsObj | ConvertTo-Json -Depth 10 | Set-Content $Settings -Encoding UTF8
    Write-Host "Hook 已添加，settings.json 更新完成"
} else {
    Write-Host "Hook 已存在，跳过"
}

# ─── 创建 .env 文件 ───────────────────────────────────────────

$EnvFile = Join-Path $SkillDir ".env"
if (-not (Test-Path $EnvFile)) {
    Copy-Item (Join-Path $RepoDir ".env.example") $EnvFile
    Write-Host ".env 文件已创建: $EnvFile"
} else {
    Write-Host ".env 文件已存在，跳过"
}

$CurrentKey = (Select-String -Path $EnvFile -Pattern '^OPENDOOR_IMAGE_API_KEY=.+' -ErrorAction SilentlyContinue)
if (-not $CurrentKey) {
    Write-Host ""
    Write-Host "请输入你的 API 密钥（从 https://api.code-opendoor.com 获取）"
    $ApiKey = Read-Host "API Key"
    if ($ApiKey) {
        (Get-Content $EnvFile -Encoding UTF8) -replace '^OPENDOOR_IMAGE_API_KEY=.*', "OPENDOOR_IMAGE_API_KEY=$ApiKey" |
            Set-Content $EnvFile -Encoding UTF8
        Write-Host "API Key 已保存"
    } else {
        Write-Host "跳过，请稍后手动编辑: $EnvFile"
    }
} else {
    Write-Host "API Key 已配置，跳过"
}

Write-Host ""
Write-Host "安装完成！"
Write-Host ""
if ($Runtime -eq "python") {
    $PythonExe = Join-Path $RepoDir ".venv\Scripts\python.exe"
    $GenScript = Join-Path $RepoDir "scripts\generate.py"
    Write-Host "运行时: Python (.venv)"
    Write-Host "  脚本: $PythonExe $GenScript"
} else {
    $GenScript = Join-Path $RepoDir "scripts\generate.js"
    Write-Host "运行时: Node.js"
    Write-Host "  脚本: node $GenScript"
}
Write-Host ""
Write-Host "使用方法："
Write-Host "  在 Claude Code 中直接说「帮我画一只猫」即可自动触发"
Write-Host "  或使用 /opendoor-image-skills 手动调用"
