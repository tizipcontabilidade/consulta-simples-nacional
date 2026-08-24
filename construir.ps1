<#
.SYNOPSIS
    Gera o executavel e o instalador do Consulta Simples Nacional.

.DESCRIPTION
    Roda em quem MANTEM o sistema, nao em quem usa. Produz:

      dist\ConsultaSimplesNacional\      pasta portatil (pode ser copiada em rede)
      instalador\...-setup.exe           instalador para a equipe

.EXAMPLE
    .\construir.ps1

.EXAMPLE
    .\construir.ps1 -Versao 1.1.0 -SomenteExecutavel
#>
[CmdletBinding()]
param(
    [string]$Versao,
    [switch]$SomenteExecutavel,
    [switch]$GerarZip
)

$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $raiz

Write-Host "1/4  Conferindo dependencias..." -ForegroundColor Cyan
python -m pip install --disable-pip-version-check -q -r requirements.txt
python -m pip install --disable-pip-version-check -q pyinstaller

Write-Host "2/4  Gerando o executavel (PyInstaller)..." -ForegroundColor Cyan
python -m PyInstaller empacotar.spec --noconfirm --distpath dist --workpath build
if ($LASTEXITCODE -ne 0) { throw "PyInstaller falhou" }

if ($GerarZip) {
    Write-Host "     Compactando versao portatil..." -ForegroundColor Cyan
    $zip = Join-Path $raiz "instalador\ConsultaSimplesNacional-portatil.zip"
    New-Item -ItemType Directory -Force (Split-Path $zip) | Out-Null
    if (Test-Path $zip) { Remove-Item $zip -Force }
    Compress-Archive -Path "dist\ConsultaSimplesNacional\*" -DestinationPath $zip
    Write-Host "     $zip"
}

if ($SomenteExecutavel) {
    Write-Host "Pronto (sem instalador)." -ForegroundColor Green
    exit 0
}

Write-Host "3/4  Localizando o compilador do Inno Setup..." -ForegroundColor Cyan
$candidatos = @(
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
)
$iscc = $candidatos | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) {
    Write-Host "Inno Setup nao encontrado. Instale com:" -ForegroundColor Yellow
    Write-Host "    winget install --id JRSoftware.InnoSetup -e"
    throw "ISCC.exe ausente"
}

Write-Host "4/4  Compilando o instalador..." -ForegroundColor Cyan
$parametros = @("instalador.iss")
if ($Versao) { $parametros = @("/DVersao=$Versao") + $parametros }
& $iscc @parametros | Select-Object -Last 3
if ($LASTEXITCODE -ne 0) { throw "Inno Setup falhou" }

Write-Host ""
Write-Host "Pronto." -ForegroundColor Green
Get-ChildItem instalador\*.exe | ForEach-Object {
    "{0}  ({1:N0} MB)" -f $_.FullName, ($_.Length / 1MB)
}
