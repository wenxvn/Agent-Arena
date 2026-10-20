#requires -Version 5.1
<#
.SYNOPSIS
  启动 Agent Arena 本地网页（Windows PowerShell）。
.DESCRIPTION
  只监听 127.0.0.1；首次运行会由 uv 临时提供 streamlit。
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts/launch_web.ps1
#>
param(
    [int]$Port = 8501,
    [switch]$Check
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

if ($Check) {
    uv run python scripts/verify_v11.py
    exit $LASTEXITCODE
}

uv run --with streamlit agent-arena web --port $Port
