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
$mainWindowPath = Join-Path $desktopRoot "ui\\main_window.py"

function Get-SystemVersion {
    param(
        [string]$SourceFile
    )

    if (-not (Test-Path $SourceFile)) {
        return "0_0_0_0"
    }

    $content = Get-Content $SourceFile -Raw
    $match = [regex]::Match($content, "REV\s+(\d+(?:\.\d+){1,3})")
    if (-not $match.Success) {
        return "0_0_0_0"
    }

    return $match.Groups[1].Value -replace "\.", "_"
}

if (-not (Test-Path $specPath)) {
    throw "Spec portable não encontrado: $specPath"
}

$versionLabel = Get-SystemVersion -SourceFile $mainWindowPath
$zipPath = Join-Path $distRoot ("ChecklistFrotaPortable_v{0}.zip" -f $versionLabel)

if ($Clean) {
    if (Test-Path $portableRoot) {
        Remove-Item -LiteralPath $portableRoot -Recurse -Force
    }
    $portableBuildRoot = Join-Path $buildRoot "ChecklistFrotaPortable"
    if (Test-Path $portableBuildRoot) {
        Remove-Item -LiteralPath $portableBuildRoot -Recurse -Force
    }
    if (Test-Path $zipPath) {
        Remove-Item -LiteralPath $zipPath -Force
    }
}

Push-Location $projectRoot
try {
    python -m PyInstaller --noconfirm $specPath
    if (-not (Test-Path (Join-Path $portableRoot "ChecklistFrotaPortable.exe"))) {
        throw "Portable gerado sem executável final."
    }

    if (Test-Path $zipPath) {
        Remove-Item -LiteralPath $zipPath -Force
    }
    Compress-Archive -Path (Join-Path $portableRoot "*") -DestinationPath $zipPath -CompressionLevel Optimal

    Write-Host ""
    Write-Host "Portable pronto em:" -ForegroundColor Green
    Write-Host $portableRoot -ForegroundColor Cyan
    Write-Host ""
    Write-Host "ZIP de distribuição pronto em:" -ForegroundColor Green
    Write-Host $zipPath -ForegroundColor Cyan
} finally {
    Pop-Location
}
