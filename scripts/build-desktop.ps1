[CmdletBinding()]
param([switch]$Zip)

$ErrorActionPreference = 'Stop'
$projectDirectory = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))

function Invoke-Checked {
    param([string]$Executable, [string[]]$Arguments)
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Executable failed with exit code $LASTEXITCODE" }
}

Push-Location $projectDirectory
try {
    Invoke-Checked 'uv' @('sync', '--locked', '--dev', '--extra', 'captcha', '--link-mode=copy')
    Push-Location (Join-Path $projectDirectory 'frontend')
    try {
        Invoke-Checked 'yarn' @('install', '--immutable')
        Invoke-Checked 'yarn' @('typecheck')
        Invoke-Checked 'yarn' @('build')
    } finally { Pop-Location }

    $pythonExecutable = Join-Path $projectDirectory '.venv/Scripts/python.exe'
    # app 下的非 Python 数据文件不会被 PyInstaller 自动收集（它只跟 import 走），
    # 必须显式 --add-data；否则打包后 endfield_lookup 读不到昵称表，
    # 检索会静默退化成"只能用索引里的名字"，昵称/简称/同音字全部失效。
    # 目标路径用 app/tools/data，与源码里 Path(__file__).parent / "data" 对齐。
    $toolData = Join-Path $projectDirectory 'app/tools/data'
    if (-not (Test-Path $toolData)) { throw "缺少数据目录：$toolData" }
    Invoke-Checked $pythonExecutable @(
        '-m', 'PyInstaller', '--noconfirm', '--clean', '--onedir', '--console',
        '--name', 'community-backend', '--distpath', 'build/backend',
        '--workpath', 'build/pyinstaller', '--specpath', 'build',
        '--collect-submodules', 'uvicorn', '--hidden-import', 'app.main',
        '--hidden-import', 'win32timezone',
        '--add-data', "$toolData;app/tools/data", 'main.py'
    )
    Push-Location (Join-Path $projectDirectory 'frontend')
    try {
        if ($Zip) { Invoke-Checked 'yarn' @('package:desktop') }
        else { Invoke-Checked 'yarn' @('package:desktop', '--dir') }
    } finally { Pop-Location }
    Write-Output (Join-Path $projectDirectory 'frontend/out/win-unpacked/BetterMASTools.exe')
} finally { Pop-Location }
