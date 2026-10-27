<#
  MoviZap - Ligacoes | desinstalar o agente deste PC (versao 0.4, 15/10/2026)

  Remove: a tarefa agendada (o nome novo e o antigo), o atalho do Menu
  Iniciar, a entrada em Aplicativos instalados, o certificado deste PC no
  cofre do usuario, e a pasta %LOCALAPPDATA%\MoviZapLigacoes (config,
  controle e log).

  AS GRAVACOES DO MICROSIP NAO SAO TOCADAS. Elas sao do MicroSIP, nao nossas.

  O que isto NAO faz: revogar a chave na VPS. Quem sai da empresa pede ao
  Iago: "revoga o agente do ramal XXXX" (uma linha no banco). Enquanto nao
  revogar, o historico que ja subiu continua lah -- e e isso que se quer.
#>
$ErrorActionPreference = 'Stop'
$TAREFA = 'MoviZap - Backup de Ligacoes'
$TAREFA_ANTIGA = 'MoviZap Ligacoes'
$DADOS = Join-Path $env:LOCALAPPDATA 'MoviZapLigacoes'
$CONFIG = Join-Path $DADOS 'config.json'
$CHAVE_REGISTRO = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\MoviZapLigacoes'
$ATALHO = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\MoviZap - Backup de Ligacoes (ver situacao).lnk'

function Diga([string]$t) { Write-Host $t -ForegroundColor Cyan }

foreach ($nome in @($TAREFA, $TAREFA_ANTIGA)) {
    if (Get-ScheduledTask -TaskName $nome -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $nome -Confirm:$false
        Diga "Tarefa '$nome' removida."
    }
}

# O certificado deste PC nao serve a mais nada depois disto.
if (Test-Path -LiteralPath $CONFIG) {
    try {
        $cfg = Get-Content -LiteralPath $CONFIG -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($cfg.cert) {
            Get-ChildItem Cert:\CurrentUser\My -ErrorAction SilentlyContinue |
                Where-Object { $_.Thumbprint -eq $cfg.cert } |
                ForEach-Object {
                    Remove-Item -LiteralPath $_.PSPath -DeleteKey -Force -ErrorAction SilentlyContinue
                    Diga ("Certificado {0}... removido do cofre do usuario." -f $cfg.cert.Substring(0, 8))
                }
        }
    } catch { Write-Host "Nao deu para ler o config.json (segue)." -ForegroundColor Yellow }
}

if (Test-Path -LiteralPath $ATALHO) {
    Remove-Item -LiteralPath $ATALHO -Force
    Diga 'Atalho do Menu Iniciar removido.'
}
if (Test-Path -LiteralPath $CHAVE_REGISTRO) {
    Remove-Item -LiteralPath $CHAVE_REGISTRO -Recurse -Force
    Diga 'Entrada em Aplicativos instalados removida.'
}
if (Test-Path -LiteralPath $DADOS) {
    # O proprio desinstalador pode estar rodando de dentro desta pasta.
    $eu = $MyInvocation.MyCommand.Path
    if ($eu -and $eu.StartsWith($DADOS, [StringComparison]::OrdinalIgnoreCase)) {
        Start-Process -WindowStyle Hidden -FilePath 'cmd.exe' `
            -ArgumentList ('/c ping -n 4 127.0.0.1 >nul & rmdir /s /q "' + $DADOS + '"') | Out-Null
        Diga "Pasta $DADOS sai em alguns segundos."
    } else {
        Remove-Item -LiteralPath $DADOS -Recurse -Force
        Diga "Pasta $DADOS removida."
    }
}
Write-Host ''
Diga 'Pronto. As gravacoes do MicroSIP continuam onde estavam.'
