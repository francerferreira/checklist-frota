param(
    [switch]$Clean
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$desktopRoot = Join-Path $projectRoot "desktop"
$specPath = Join-Path $desktopRoot "ChecklistFrotaPortable.spec"
$distRoot = Join-Path $projectRoot "dist"
$buildRoot = Join-Path $projectRoot "build"
$portableRoot = Join-Path $distRoot "ChecklistFrotaPortable"

if (-not (Test-Path $specPath)) {
    throw "Spec portable não encontrado: $specPath"
}

if ($Clean) {
    if (Test-Path $portableRoot) {
        Remove-Item -LiteralPath $portableRoot -Recurse -Force
    }
    $portableBuildRoot = Join-Path $buildRoot "ChecklistFrotaPortable"
    if (Test-Path $portableBuildRoot) {
        Remove-Item -LiteralPath $portableBuildRoot -Recurse -Force
    }
}

Push-Location $projectRoot
try {
    python -m PyInstaller --noconfirm $specPath
    if (-not (Test-Path (Join-Path $portableRoot "ChecklistFrotaPortable.exe"))) {
        throw "Portable gerado sem executável final."
    }
    Write-Host ""
    Write-Host "Portable pronto em:" -ForegroundColor Green
    Write-Host $portableRoot -ForegroundColor Cyan
} finally {
    Pop-Location
}
