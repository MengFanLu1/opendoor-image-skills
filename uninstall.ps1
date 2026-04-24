# OpenDoor Image Skills - Windows 卸载脚本
# 使用方法: powershell -ExecutionPolicy Bypass -File uninstall.ps1

$ErrorActionPreference = "Stop"

$ClaudeDir = if ($env:CLAUDE_CONFIG_DIR) { $env:CLAUDE_CONFIG_DIR } else { Join-Path $env:USERPROFILE ".claude" }
$SkillDir = Join-Path $ClaudeDir "skills\opendoor-image-skills"
$Settings = Join-Path $ClaudeDir "settings.json"

Write-Host "OpenDoor Image Skills - 卸载程序"
Write-Host "================================="

# 1. 删除 skill 目录
if (Test-Path $SkillDir) {
    Remove-Item -Recurse -Force $SkillDir
    Write-Host "已删除: $SkillDir"
} else {
    Write-Host "Skill 目录不存在，跳过"
}

# 2. 从 settings.json 移除 hook
if (Test-Path $Settings) {
    $SettingsObj = Get-Content $Settings -Raw -Encoding UTF8 | ConvertFrom-Json
    $Matcher = "画|生成图片|出图|制图|帮我画|draw|generate image|create image|make image|image generation"

    if ($SettingsObj.hooks -and $SettingsObj.hooks.UserPromptSubmit) {
        $Original = $SettingsObj.hooks.UserPromptSubmit
        $Filtered = @($Original | Where-Object { $_.matcher -ne $Matcher })

        if ($Filtered.Count -lt $Original.Count) {
            if ($Filtered.Count -eq 0) {
                $SettingsObj.hooks.PSObject.Properties.Remove("UserPromptSubmit")
            } else {
                $SettingsObj.hooks.UserPromptSubmit = $Filtered
            }
            Write-Host "Hook 已移除"
        } else {
            Write-Host "未找到对应 Hook，跳过"
        }
    }

    # 清理旧版 env 变量
    if ($SettingsObj.env -and $SettingsObj.env.OPENDOOR_IMAGE_API_KEY) {
        $SettingsObj.env.PSObject.Properties.Remove("OPENDOOR_IMAGE_API_KEY")
        Write-Host "已从 settings.json 清理旧版 API Key"
    }

    $SettingsObj | ConvertTo-Json -Depth 10 | Set-Content $Settings -Encoding UTF8
    Write-Host "settings.json 更新完成"
} else {
    Write-Host "settings.json 不存在，跳过"
}

Write-Host ""
Write-Host "卸载完成！"
Write-Host "注意: 已生成的图片保留在 ~/generated_images/ 目录中"
