$ErrorActionPreference = 'Stop'
$projectDirectory = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$application = Join-Path $projectDirectory 'frontend/out/win-unpacked/BetterMASTools.exe'
if (-not (Test-Path -LiteralPath $application -PathType Leaf)) {
    throw 'Desktop build not found. Run scripts/build-desktop.ps1 first.'
}
Start-Process -FilePath $application -WorkingDirectory (Split-Path $application) -WindowStyle Hidden
