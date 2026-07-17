param(
    [string]$ApiUrl = "https://checklist-frota-qngw.onrender.com",
    [string]$Login = "admin",
    [Security.SecureString]$SenhaSegura,
    [string]$Destino = "$env:USERPROFILE\BACKUPS_CHECKLIST",
    [switch]$LimparAntigos,
    [int]$ManterDias = 14
)

$ErrorActionPreference = "Stop"
$ApiUrl = $ApiUrl.TrimEnd("/")
New-Item -ItemType Directory -Force -Path $Destino | Out-Null

if (-not $SenhaSegura) {
    $SenhaSegura = Read-Host "Senha do usuario $Login" -AsSecureString
}

Write-Host "Verificando saude da API..."
try {
    $health = Invoke-RestMethod -Uri "$ApiUrl/health" -Method Get -TimeoutSec 120
    if ($health.database -ne "ok") {
        throw "Banco informado como indisponivel pela API."
    }
} catch {
    throw "A API nao respondeu com banco saudavel em $ApiUrl. Detalhe: $($_.Exception.Message)"
}

Write-Host "Entrando na API..."
$pointer = [IntPtr]::Zero
$pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SenhaSegura)
try {
    $senhaTexto = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    $loginBody = @{ login = $Login; senha = $senhaTexto } | ConvertTo-Json
    $loginResponse = Invoke-RestMethod -Uri "$ApiUrl/login" -Method Post -ContentType "application/json" -Body $loginBody -TimeoutSec 120
} finally {
    $senhaTexto = $null
    if ($pointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
    }
}
if (-not $loginResponse.data.token) {
    throw "A API respondeu ao login sem fornecer o token esperado."
}
$headers = @{ Authorization = "Bearer $($loginResponse.data.token)" }

Write-Host "Consultando armazenamento..."
$statusResponse = Invoke-RestMethod -Uri "$ApiUrl/admin/storage/status" -Headers $headers -Method Get -TimeoutSec 120
$status = $statusResponse.data
if (-not $status.database -or -not $status.storage) {
    throw "A API respondeu sem os dados de armazenamento esperados."
}
Write-Host ("Banco: {0}% ({1} MB de {2} MB)" -f $status.database.percent, $status.database.used_mb, $status.database.limit_mb)
Write-Host ("Fotos: {0}% ({1} MB de {2} MB)" -f $status.storage.percent, $status.storage.used_mb, $status.storage.limit_mb)

Write-Host "Gerando backup completo..."
$backupResponse = Invoke-RestMethod -Uri "$ApiUrl/admin/backups/create" -Headers $headers -Method Post -TimeoutSec 120
$backup = $backupResponse.data
if (-not $backup.filename -or -not $backup.download_url) {
    throw "A API respondeu sem os dados do backup esperado."
}
$saida = Join-Path $Destino $backup.filename

Write-Host "Baixando backup em $saida ..."
Invoke-WebRequest -Uri "$ApiUrl$($backup.download_url)" -Headers $headers -OutFile $saida -TimeoutSec 120
Write-Host "Backup salvo: $saida"

$restoreTool = Join-Path $PSScriptRoot "tools\restore_backup_archive.py"
$python = Get-Command python -ErrorAction SilentlyContinue
if ($python -and (Test-Path $restoreTool)) {
    Write-Host "Validando integridade e manifesto do backup..."
    & $python.Source $restoreTool $saida --validate-only
    if ($LASTEXITCODE -ne 0) {
        throw "O arquivo foi baixado, mas falhou na validacao. Nao use este backup para limpeza."
    }
} else {
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip = [System.IO.Compression.ZipFile]::OpenRead($saida)
    try {
        if (-not ($zip.Entries | Where-Object { $_.FullName -eq "backup_manifesto.json" })) {
            throw "Manifesto ausente no backup."
        }
    } finally {
        $zip.Dispose()
    }
}

if ($LimparAntigos) {
    Write-Host "Limpando dados antigos na nuvem, mantendo os ultimos $ManterDias dias..."
    $cleanupBody = @{
        keep_days = $ManterDias
        dry_run = $false
        backup_filename = $backup.filename
        confirmation = "LIMPAR_DADOS_ANTIGOS"
    } | ConvertTo-Json
    $cleanupResponse = Invoke-RestMethod -Uri "$ApiUrl/admin/cleanup/old-records" -Headers $headers -Method Post -ContentType "application/json" -Body $cleanupBody -TimeoutSec 120
    $cleanupResponse.data | ConvertTo-Json -Depth 5
} else {
    Write-Host "Limpeza nao executada. Para limpar antigos, rode com -LimparAntigos."
}

