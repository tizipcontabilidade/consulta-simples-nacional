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

# A versao mora no codigo (simplesnacionalersao.py) e desce dele para o
# instalador e para o manifesto - assim nao ha dois numeros para desencontrar.
if (-not $Versao) {
    $Versao = (python -c "import sys; sys.path.insert(0,'.'); from simplesnacional.versao import VERSAO; print(VERSAO)").Trim()
    if (-not $Versao) { throw "nao consegui ler a versao de simplesnacionalersao.py" }
}
Write-Host "Versao $Versao" -ForegroundColor Cyan

Write-Host "1/5  Conferindo dependencias..." -ForegroundColor Cyan
python -m pip install --disable-pip-version-check -q -r requirements.txt
python -m pip install --disable-pip-version-check -q pyinstaller

Write-Host "2/5  Gerando o executavel (PyInstaller)..." -ForegroundColor Cyan
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

Write-Host "3/5  Localizando o compilador do Inno Setup..." -ForegroundColor Cyan
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

Write-Host "4/5  Compilando o instalador..." -ForegroundColor Cyan
$parametros = @("instalador.iss")
if ($Versao) { $parametros = @("/DVersao=$Versao") + $parametros }
& $iscc @parametros | Select-Object -Last 3
if ($LASTEXITCODE -ne 0) { throw "Inno Setup falhou" }

Write-Host "5/5  Preparando a publicacao..." -ForegroundColor Cyan
$setup = Join-Path $raiz "instalador\ConsultaSimplesNacional-$Versao-setup.exe"
if (-not (Test-Path $setup)) { throw "instalador nao encontrado: $setup" }
$hash = (Get-FileHash $setup -Algorithm SHA256).Hash.ToLower()

# A faixa da tela mostra apenas o primeiro paragrafo destas notas, em texto
# simples. Entao a primeira linha e uma frase curta, para a equipe - que nao
# precisa entender o detalhe. O resto fica para quem abrir as notas.
$notas = Join-Path $raiz "instalador\notas-v$Versao.md"
@"
Atualizacao do Consulta Simples Nacional para a versao $Versao.

Baixe o instalador abaixo e execute; ou, se ja tem o sistema instalado, use o
botao **Atualizar agora** que aparece na propria tela.

O Windows avisa que o programa e de origem desconhecida enquanto o instalador
nao tiver certificado de assinatura: **Mais informacoes** > **Executar assim
mesmo**.

``````
SHA-256: $hash
``````

O que mudou nesta versao esta no
[CHANGELOG](https://github.com/tizipcontabilidade/consulta-simples-nacional/blob/main/CHANGELOG.md).
"@ | Out-File $notas -Encoding utf8

Write-Host ""
Write-Host "Pronto." -ForegroundColor Green
"{0}  ({1:N0} MB)" -f $setup, ((Get-Item $setup).Length / 1MB)
Write-Host "SHA-256: $hash"
Write-Host ""
Write-Host "Para publicar o release (e com isso avisar a equipe):" -ForegroundColor Yellow
Write-Host "    gh release create v$Versao `"$setup`" --title `"v$Versao`" --notes-file `"$notas`""
