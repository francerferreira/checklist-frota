param(
    [string]$ApiUrl = "https://checklist-api.onrender.com",
    [string]$Login = "admin",
    [string]$Senha = "123456",
    [string]$Destino = "$env:USERPROFILE\OneDrive - Chibatao Navegacao e Comercio Ltda\BACKUPS_CHECKLIST",
    [switch]$LimparAntigos,
    [int]$ManterDias = 14
)

$ErrorActionPreference = "Stop"
$ApiUrl = $ApiUrl.TrimEnd("/")
New-Item -ItemType Directory -Force -Path $Destino | Out-Null

Write-Host "Entrando na API..."
$loginBody = @{ login = $Login; senha = $Senha } | ConvertTo-Json
$loginResponse = Invoke-RestMethod -Uri "$ApiUrl/login" -Method Post -ContentType "application/json" -Body $loginBody
$headers = @{ Authorization = "Bearer $($loginResponse.token)" }

Write-Host "Consultando armazenamento..."
$status = Invoke-RestMethod -Uri "$ApiUrl/admin/storage/status" -Headers $headers -Method Get
Write-Host ("Banco: {0}% ({1} MB de {2} MB)" -f $status.database.percent, $status.database.used_mb, $status.database.limit_mb)
Write-Host ("Fotos: {0}% ({1} MB de {2} MB)" -f $status.storage.percent, $status.storage.used_mb, $status.storage.limit_mb)

Write-Host "Gerando backup completo..."
$backup = Invoke-RestMethod -Uri "$ApiUrl/admin/backups/create" -Headers $headers -Method Post
$saida = Join-Path $Destino $backup.filename

Write-Host "Baixando backup em $saida ..."
Invoke-WebRequest -Uri "$ApiUrl$($backup.download_url)" -Headers $headers -OutFile $saida
Write-Host "Backup salvo: $saida"

if ($LimparAntigos) {
    Write-Host "Limpando dados antigos na nuvem, mantendo os ultimos $ManterDias dias..."
    $cleanupBody = @{
        keep_days = $ManterDias
        dry_run = $false
        backup_filename = $backup.filename
        confirmation = "LIMPAR_DADOS_ANTIGOS"
    } | ConvertTo-Json
    $cleanup = Invoke-RestMethod -Uri "$ApiUrl/admin/cleanup/old-records" -Headers $headers -Method Post -ContentType "application/json" -Body $cleanupBody
    $cleanup | ConvertTo-Json -Depth 5
} else {
    Write-Host "Limpeza nao executada. Para limpar antigos, rode com -LimparAntigos."
}
