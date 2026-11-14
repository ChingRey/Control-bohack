param([Parameter(Mandatory=$true)][string]$LanHost,[int]$Port=8784)
$ErrorActionPreference='Stop'
$projectRoot=Split-Path -Parent $PSScriptRoot
Write-Host "两台电脑打开 http://${LanHost}:$Port 。仅供可信局域网演示，不是真实登录服务。"
Write-Host '请先退出占用此端口的旧服务；数据保留在本目录 data/workbench。'
Set-Location -LiteralPath $projectRoot
python backend.py --port $Port --lan-host $LanHost
