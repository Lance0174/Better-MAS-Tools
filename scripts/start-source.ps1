param(
    [switch]$SkipInstall,
    [switch]$NoRun,
    [switch]$SmokeTest
)

$ErrorActionPreference = 'Stop'
$projectDirectory = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$yarnCommand = (Get-Command yarn.cmd -ErrorAction Stop).Source
$sourcePreviousDataDirectory = $env:COMMUNITY_DATA_DIR
if ($SmokeTest) {
    $sourceSmokeDirectory = Join-Path $projectDirectory ('local/source-smoke-' + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $sourceSmokeDirectory -Force | Out-Null
    $env:COMMUNITY_DATA_DIR = $sourceSmokeDirectory
}

# 源码入口只使用本项目依赖；不要求已有 exe，也不调用 MAS 的运行环境。
Push-Location $projectDirectory
try {
    if (-not $SkipInstall) {
        & uv sync --locked --extra captcha --link-mode=copy
        if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }
    }
    if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe' -PathType Leaf)) {
        throw 'Project Python is missing. Run uv sync --locked --link-mode=copy.'
    }
    Push-Location (Join-Path $projectDirectory 'frontend')
    try {
        if (-not $SkipInstall) {
            & $yarnCommand install --immutable
            if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
        }
        & $yarnCommand typecheck
        if ($LASTEXITCODE -ne 0) { throw 'Source typecheck failed.' }
        & $yarnCommand build
        if ($LASTEXITCODE -ne 0) { throw 'Source build failed.' }
        if (-not $NoRun) {
            if ($SmokeTest) { & $yarnCommand desktop --smoke-test }
            else { & $yarnCommand desktop }
            if ($LASTEXITCODE -ne 0) { throw 'Source application exited with an error.' }
        }
    }
    finally { Pop-Location }
}
finally {
    Pop-Location
    if ($SmokeTest) {
        $env:COMMUNITY_DATA_DIR = $sourcePreviousDataDirectory
        Write-Output "Smoke-test data and logs: $sourceSmokeDirectory"
    }
}
