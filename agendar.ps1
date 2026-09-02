<#
.SYNOPSIS
    Cria (ou atualiza) uma tarefa no Agendador do Windows para rodar a consulta
    em lote sozinha, todo dia, e avisar so o que mudou.

.EXAMPLE
    .\agendar.ps1 -Arquivo "C:\ListasCNPJ\minha-carteira.txt" -Hora 08:00

.EXAMPLE
    .\agendar.ps1 -Arquivo "\\servidor\contabil\clientes.xlsx" -Hora 07:30 -Nome "SN - carteira toda"

.NOTES
    A tarefa roda no seu usuario e SO com voce logado - o portal exige um
    navegador visivel por causa do captcha. Se o portal pedir verificacao
    durante a rodada agendada, a janela fica esperando voce resolver.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Arquivo,

    [string]$Hora = "08:00",

    [string]$Nome = "Consulta Simples Nacional",

    [ValidateSet("Diaria", "SemanalSegunda", "Mensal")]
    [string]$Frequencia = "Diaria",

    [switch]$TodasAsOcorrencias,

    [string]$PastaSaida
)

$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path

if (-not (Test-Path $Arquivo)) {
    throw "Arquivo de CNPJs nao encontrado: $Arquivo"
}

# Prefere o executavel instalado; cai para o python do projeto.
$exe = Join-Path $raiz "consultar.exe"
if (Test-Path $exe) {
    $programa = $exe
    $argumentos = @()
}
else {
    $python = Join-Path $raiz ".venv\Scripts\pythonw.exe"
    if (-not (Test-Path $python)) { $python = "pythonw.exe" }
    $programa = $python
    $argumentos = @("`"$(Join-Path $raiz 'consultar.py')`"")
}

$argumentos += @("--arquivo", "`"$Arquivo`"", "--formato", "xlsx", "--silencioso")
if (-not $TodasAsOcorrencias) { $argumentos += "--somente-mudancas" }
if ($PastaSaida) { $argumentos += @("--saida", "`"$PastaSaida`"") }

$acao = New-ScheduledTaskAction -Execute $programa -Argument ($argumentos -join " ") -WorkingDirectory $raiz

switch ($Frequencia) {
    "Diaria"          { $gatilho = New-ScheduledTaskTrigger -Daily -At $Hora }
    "SemanalSegunda"  { $gatilho = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At $Hora }
    "Mensal"          { $gatilho = New-ScheduledTaskTrigger -Once -At $Hora `
                            -RepetitionInterval (New-TimeSpan -Days 30) }
}

$config = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -DontStopIfGoingOnBatteries `
    -AllowStartIfOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Hours 4)

Register-ScheduledTask -TaskName $Nome -Action $acao -Trigger $gatilho -Settings $config `
    -Description "Consulta os CNPJs do arquivo no portal do Simples Nacional e gera relatorio das mudancas." `
    -Force | Out-Null

Write-Host ""
Write-Host "Tarefa '$Nome' criada." -ForegroundColor Green
Write-Host "  Programa : $programa"
Write-Host "  Argumentos: $($argumentos -join ' ')"
Write-Host "  Quando   : $Frequencia as $Hora"
Write-Host ""
Write-Host "Testar agora:  Start-ScheduledTask -TaskName '$Nome'"
Write-Host "Remover:       Unregister-ScheduledTask -TaskName '$Nome' -Confirm:`$false"
