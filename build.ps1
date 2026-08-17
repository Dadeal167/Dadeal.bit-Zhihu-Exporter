# -*- coding: utf-8 -*-
# 一键构建脚本: 语法检查 -> PyInstaller 打包 -> 瘦身+便携版 -> Inno Setup 生成安装包
# 用法: powershell -ExecutionPolicy Bypass -File build.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

Write-Host "== 1/4 语法检查 ==" -ForegroundColor Cyan
python -m py_compile main.py (Get-ChildItem core -Filter *.py).FullName
if ($LASTEXITCODE -ne 0) { Write-Error "语法检查失败"; exit 1 }

Write-Host "== 2/4 PyInstaller 打包 ==" -ForegroundColor Cyan
python -m PyInstaller --noconfirm --clean main.spec
if ($LASTEXITCODE -ne 0) { Write-Error "PyInstaller 打包失败"; exit 1 }

Write-Host "== 3/4 体积瘦身(仅保留中文翻译) + 生成便携版 zip ==" -ForegroundColor Cyan
$trans = Join-Path $root "dist\main\_internal\PySide6\translations"
if (Test-Path $trans) {
    Get-ChildItem $trans -Filter "*.qm" | Where-Object { $_.Name -notmatch "zh_CN" } | Remove-Item -Force
}
$ver = (Select-String -Path "core\version.py" -Pattern '__version__ = "([^"]+)"').Matches[0].Groups[1].Value
Compress-Archive -Path (Join-Path $root "dist\main\*") -DestinationPath (Join-Path $root "Output\Dadealbit_ZhihuExporter_v${ver}_便携版.zip") -Force

Write-Host "== 4/4 Inno Setup 生成安装包 ==" -ForegroundColor Cyan
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" Dadeal.iss
if ($LASTEXITCODE -ne 0) { Write-Error "Inno Setup 编译失败"; exit 1 }

Write-Host ""
Write-Host "构建完成! 安装包位于 Output\ 目录" -ForegroundColor Green
Get-ChildItem Output -Filter "*.exe" | Select-Object Name, Length, LastWriteTime
Get-ChildItem Output -Filter "*.zip" | Select-Object Name, Length, LastWriteTime
