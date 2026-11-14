param([int]$Port = 8772)
$ErrorActionPreference = 'Stop'
$controlRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $controlRoot
if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) { throw "端口 $Port 已占用，请先关闭旧工作台；不要同时启动两个进程写入同一数据库。" }
if (-not $env:CONTROL_V021_ACCESS_TOKEN) {
 $controlSecureToken = Read-Host '设置本次V0.2.1联调访问令牌（不是模型API Key，重启需重新设置）' -AsSecureString
 $controlTokenPtr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($controlSecureToken)
 try { $env:CONTROL_V021_ACCESS_TOKEN = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($controlTokenPtr) }
 finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($controlTokenPtr) }
}
if ($env:CONTROL_V021_ACCESS_TOKEN.Length -lt 16) { throw '请设置至少16个字符的随机访问令牌' }
try { python -X utf8 backend.py --port $Port }
finally { Remove-Item Env:CONTROL_V021_ACCESS_TOKEN -ErrorAction SilentlyContinue }
