# TruthSeeker API 启动脚本
# 固定使用项目虚拟环境 venv_new 启动，避免误用系统 Python
# 导致 langchain/openai 包版本与测试环境不一致。
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$Python = Join-Path $PSScriptRoot "venv_new\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    Write-Error "未找到 venv_new\Scripts\python.exe，请先创建虚拟环境并安装依赖：python -m venv venv_new && venv_new\Scripts\python -m pip install -r requirements.txt"
    exit 1
}

Write-Host "使用解释器: $Python"
& $Python -m uvicorn app.main:app --reload --port 8000
