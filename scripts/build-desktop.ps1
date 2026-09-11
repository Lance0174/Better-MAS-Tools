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
    Invoke-Checked $pythonExecutable @(
        '-m', 'PyInstaller', '--noconfirm', '--clean', '--onedir', '--console',
        '--name', 'community-backend', '--distpath', 'build/backend',
        '--workpath', 'build/pyinstaller', '--specpath', 'build',
        '--collect-submodules', 'uvicorn', '--hidden-import', 'app.main',
        '--hidden-import', 'win32timezone', 'main.py'
    )
    Push-Location (Join-Path $projectDirectory 'frontend')
    try {
        if ($Zip) { Invoke-Checked 'yarn' @('package:desktop') }
        else { Invoke-Checked 'yarn' @('package:desktop', '--dir') }
    } finally { Pop-Location }
    Write-Output (Join-Path $projectDirectory 'frontend/out/win-unpacked/BetterMASCommunity.exe')
} finally { Pop-Location }
