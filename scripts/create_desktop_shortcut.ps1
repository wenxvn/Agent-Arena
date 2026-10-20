#requires -Version 5.1
<#
.SYNOPSIS
  在桌面创建 Agent Arena 启动快捷方式（Windows）。
.DESCRIPTION
  快捷方式指向 scripts/launch_web.ps1，不写入密钥。
#>
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$desktop = [Environment]::GetFolderPath("Desktop")
$link = Join-Path $desktop "Agent Arena.lnk"
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($link)
$shortcut.TargetPath = "powershell.exe"
$shortcut.Arguments = "-ExecutionPolicy Bypass -File `"$repo\scripts\launch_web.ps1`""
$shortcut.WorkingDirectory = $repo
$shortcut.IconLocation = "powershell.exe,0"
$shortcut.Description = "启动 Agent Arena 本地网页"
$shortcut.Save()
Write-Host "已创建：$link"
