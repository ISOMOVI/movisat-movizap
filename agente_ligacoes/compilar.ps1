<#
  MoviZap - Ligacoes | recompilar os dois executaveis (v0.7, 26/10/2026)

  Nao precisa instalar nada: usa o csc.exe que ja vem no Windows
  (Microsoft.NET\Framework64\v4.0.30319). Sem ps2exe, sem admin.

  Uso:  powershell -NoProfile -ExecutionPolicy Bypass -File compilar.ps1

  Sai daqui:
    1-PC-DO-OPERADOR\MoviZap-Instalar-Ligacoes.exe   o unico arquivo que vai
        para a pessoa; carrega dentro de si o agente, o instalador, o
        desinstalador, o LEIA-ME e o lancador.
    (dentro dele) MoviZap-Backup-de-Ligacoes.exe     o lancador que a tarefa
        executa -- e o que faz o Gerenciador de Tarefas mostrar o nome certo.

  Rode isto sempre que mexer em movizap-ligacoes.ps1, instalar.ps1,
  desinstalar.ps1 ou LEIA-ME.txt: o .exe guarda uma COPIA deles.
#>
$ErrorActionPreference = 'Stop'
$AQUI = Split-Path -Parent $MyInvocation.MyCommand.Path
$KIT = Split-Path -Parent $AQUI
$DESTINO = Join-Path $KIT '1-PC-DO-OPERADOR'
$CSC = 'C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe'

function Diga([string]$t, [string]$c = 'Cyan') { Write-Host $t -ForegroundColor $c }
if (-not (Test-Path -LiteralPath $CSC)) { throw "Nao achei o csc.exe em $CSC." }

# A sintaxe dos .ps1 e conferida ANTES de entrar no .exe: script quebrado
# dentro do executavel so apareceria no PC da pessoa.
foreach ($n in @('instalar.ps1', 'desinstalar.ps1', 'movizap-ligacoes.ps1')) {
    $erros = $null; $tokens = $null
    [void][System.Management.Automation.Language.Parser]::ParseFile(
        (Join-Path $AQUI $n), [ref]$tokens, [ref]$erros)
    if ($erros -and $erros.Count) {
        $erros | ForEach-Object { Write-Host ("  {0}: linha {1}: {2}" -f $n, $_.Extent.StartLineNumber, $_.Message) -ForegroundColor Red }
        throw "$n nao compila."
    }
    Diga "$n : sintaxe ok"
}

$tmp = Join-Path $env:TEMP ('mzl-build-' + [guid]::NewGuid().ToString('N').Substring(0, 8))
New-Item -ItemType Directory -Force -Path $tmp | Out-Null
try {
    foreach ($n in @('instalar.ps1', 'desinstalar.ps1', 'movizap-ligacoes.ps1', 'LEIA-ME.txt')) {
        Copy-Item -LiteralPath (Join-Path $AQUI $n) -Destination $tmp -Force
    }
    Push-Location $tmp
    try {
        & $CSC /nologo /target:winexe /optimize+ /out:'MoviZap-Backup-de-Ligacoes.exe' (Join-Path $AQUI 'lancador.cs')
        if ($LASTEXITCODE -ne 0) { throw 'falhou o lancador.' }
        Diga 'lancador compilado'
        & $CSC /nologo /target:winexe /optimize+ /out:'MoviZap-Instalar-Ligacoes.exe' `
            /resource:instalar.ps1,instalar.ps1 `
            /resource:movizap-ligacoes.ps1,movizap-ligacoes.ps1 `
            /resource:desinstalar.ps1,desinstalar.ps1 `
            /resource:LEIA-ME.txt,LEIA-ME.txt `
            /resource:MoviZap-Backup-de-Ligacoes.exe,MoviZap-Backup-de-Ligacoes.exe `
            (Join-Path $AQUI 'instalador.cs')
        if ($LASTEXITCODE -ne 0) { throw 'falhou o instalador.' }
        Diga 'instalador compilado'
        Copy-Item -LiteralPath 'MoviZap-Instalar-Ligacoes.exe' -Destination $DESTINO -Force
    } finally { Pop-Location }
} finally { Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue }

$exe = Get-Item (Join-Path $DESTINO 'MoviZap-Instalar-Ligacoes.exe')
Write-Host ''
Diga ("Pronto: {0} ({1:N0} bytes)" -f $exe.FullName, $exe.Length) 'Green'
Diga ("  Windows mostra: '{0}' de '{1}', v{2}" -f $exe.VersionInfo.FileDescription,
    $exe.VersionInfo.CompanyName, $exe.VersionInfo.FileVersion) 'Green'
