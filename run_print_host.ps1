# Launch the host app with a resilient Python/runtime fallback.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Add-PathFront {
    param([string]$Value)
    if (-not $Value) { return }
    if (-not (Test-Path $Value)) { return }
    if ($env:PATH -notlike "*$Value*") {
        $env:PATH = "$Value;$env:PATH"
    }
}

function Add-PythonPathFront {
    param([string]$Value)
    if (-not $Value) { return }
    if (-not (Test-Path $Value)) { return }
    if ([string]::IsNullOrWhiteSpace($env:PYTHONPATH)) {
        $env:PYTHONPATH = $Value
        return
    }
    if ($env:PYTHONPATH -notlike "*$Value*") {
        $env:PYTHONPATH = "$Value;$env:PYTHONPATH"
    }
}

$preferredVenvs = @(
    (Join-Path $PSScriptRoot ".venv312\Scripts\python.exe"),
    (Join-Path $PSScriptRoot ".venv\Scripts\python.exe")
)
$pythonExe = $null
$brokenVenvFound = $false

foreach ($candidate in $preferredVenvs) {
    if (-not (Test-Path $candidate)) { continue }
    try {
        & $candidate -c "import sys; print(sys.executable)" *> $null
        $pythonExe = $candidate
        break
    } catch {
        $brokenVenvFound = $true
    }
}

if (-not $pythonExe) {
    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonCmd) {
        throw "No usable Python interpreter was found."
    }
    $pythonExe = $pythonCmd.Source
    if ($brokenVenvFound) {
        Write-Host "Local virtual environment is unavailable, falling back to system Python."
    }
    Write-Host "Using system Python: $pythonExe"

    Add-PythonPathFront (Join-Path $PSScriptRoot "app\vendor_site")

    $pythonPrefix = (& $pythonExe -c "import sys; print(sys.prefix)").Trim()
    Add-PathFront (Join-Path $pythonPrefix "Library\bin")
    Add-PathFront (Join-Path $pythonPrefix "Lib\site-packages\PySide6")
}

& $pythonExe -m print_host

