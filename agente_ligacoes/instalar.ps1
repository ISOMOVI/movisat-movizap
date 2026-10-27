<#
  MoviZap - Ligacoes | instalar o agente neste PC (usuario atual, sem administrador)
  versao 0.4 (15/10/2026)

  UM PASSO SO, com a senha que o Iago dita na hora:
    - le o ramal do proprio MicroSIP deste PC;
    - gera o PEDIDO de certificado (a chave privada nasce aqui e NAO e
      exportavel: nunca sai deste PC);
    - manda ramal + senha + pedido para a VPS, que devolve a chave do ramal e
      o certificado deste PC;
    - guarda a chave CIFRADA (DPAPI, amarrada a este usuario) e instala o
      certificado no cofre do usuario;
    - cria a tarefa "MoviZap - Backup de Ligacoes" (12:00, 17:30 e ao entrar);
    - registra o programa em Aplicativos instalados e um atalho de "ver
      situacao" no Menu Iniciar;
    - roda uma vez, para provar que falou com a VPS;
    - apaga o instalador, se tudo deu certo.

  A senha vale 10 minutos e serve UMA vez. Se vencer, pedir outra.

  NADA SECRETO FICA NESTA PASTA. A chave do ramal nasce na VPS, vem nesta
  unica resposta e e gravada cifrada em %LOCALAPPDATA%\MoviZapLigacoes.

  O que ESTE instalador nunca faz: apagar gravacao, apagar o agente ja
  instalado, pedir administrador, ou mexer em outro usuario do Windows.
#>
[CmdletBinding()]
param(
    [string]$Senha = '',        # se vier por parametro, nao pergunta
    [switch]$NaoApagar,         # mantem o instalador na pasta (para teste)
    [switch]$NaoRodarAgora      # nao dispara a primeira passada
)

$ErrorActionPreference = 'Stop'
$VERSAO = '0.7'
$AQUI = Split-Path -Parent $MyInvocation.MyCommand.Path
$DADOS = Join-Path $env:LOCALAPPDATA 'MoviZapLigacoes'
$CONFIG = Join-Path $DADOS 'config.json'
$AGENTE = Join-Path $DADOS 'movizap-ligacoes.ps1'
$LANCADOR = Join-Path $DADOS 'MoviZap-Backup-de-Ligacoes.exe'
$TAREFA = 'MoviZap - Backup de Ligacoes'
$TAREFA_ANTIGA = 'MoviZap Ligacoes'
$CHAVE_REGISTRO = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\MoviZapLigacoes'
# O alistamento entra pelo PAINEL: a porta propria exige certificado de
# cliente, e um PC que esta se alistando ainda nao tem certificado.
$URL_PAINEL = 'https://movizap.movisat.com.br'
$URL_MTLS = 'https://ligacoesmicrosip.movisat.com.br'

[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

function Diga([string]$t, [string]$cor = 'Cyan') { Write-Host $t -ForegroundColor $cor }

function Ramal-Do-MicroSIP {
    $ini = Join-Path $env:APPDATA 'MicroSIP\MicroSIP.ini'
    if (-not (Test-Path -LiteralPath $ini)) {
        throw "MicroSIP nao encontrado neste usuario do Windows ($ini). Instale e configure o MicroSIP antes."
    }
    $l = Select-String -LiteralPath $ini -Pattern '^username=(\d+)' | Select-Object -First 1
    if (-not $l) { throw "O MicroSIP deste PC nao tem ramal configurado (username no MicroSIP.ini)." }
    return $l.Matches[0].Groups[1].Value
}

# Arquivo que veio por pendrive ou download ganha a "marca da internet", e o
# Windows pode barrar o script.
Get-ChildItem -LiteralPath $AQUI -File | Unblock-File -ErrorAction SilentlyContinue

Diga "MoviZap - Backup de Ligacoes | instalador $VERSAO"
Diga ''

# ------------------------------------------------------------------ 1. o PC
$ramal = Ramal-Do-MicroSIP
Diga "Ramal deste PC .... $ramal"
Diga "Usuario ........... $env:USERNAME em $env:COMPUTERNAME"

if (-not (Test-Path -LiteralPath (Join-Path $AQUI 'movizap-ligacoes.ps1'))) {
    throw "Falta o arquivo movizap-ligacoes.ps1 nesta pasta."
}
New-Item -ItemType Directory -Force -Path $DADOS | Out-Null
Copy-Item -LiteralPath (Join-Path $AQUI 'movizap-ligacoes.ps1') -Destination $DADOS -Force
$lancadorNaPasta = Join-Path $AQUI 'MoviZap-Backup-de-Ligacoes.exe'
if (Test-Path -LiteralPath $lancadorNaPasta) {
    Copy-Item -LiteralPath $lancadorNaPasta -Destination $DADOS -Force
}
Diga "Agente copiado .... $DADOS"

# ---------------------------------------------------------------- 2. a senha
if (-not $Senha) {
    Diga ''
    Diga 'Peca a senha de uso ao Iago (ela vale 10 minutos e serve uma vez).' 'Yellow'
    # A senha NAO vai escondida de proposito: ela e ditada em voz alta, dura
    # 10 minutos e morre no uso. Esconder o que a pessoa esta digitando so
    # produziria erro de digitacao e uma senha queimada por engano.
    $Senha = Read-Host 'Senha de uso'
}
if (-not $Senha.Trim()) { throw 'Sem senha nao da para alistar este PC.' }

# -------------------------------------------------- 3. o pedido de certificado
$pedidoArq = Join-Path $env:TEMP ("movizap-pedido-{0}.req" -f $ramal)
$inf = Join-Path $env:TEMP ("movizap-pedido-{0}.inf" -f ([guid]::NewGuid().ToString('N')))
Remove-Item -LiteralPath $pedidoArq -ErrorAction SilentlyContinue
@"
[Version]
Signature="`$Windows NT`$"

[NewRequest]
Subject = "CN=mzl-$ramal-$($env:COMPUTERNAME)"
KeyAlgorithm = RSA
KeyLength = 2048
Exportable = FALSE
MachineKeySet = FALSE
ProviderName = "Microsoft Software Key Storage Provider"
KeyUsage = 0xa0
RequestType = PKCS10
HashAlgorithm = SHA256

[EnhancedKeyUsageExtension]
OID = 1.3.6.1.5.5.7.3.2
"@ | Set-Content -LiteralPath $inf -Encoding ASCII
try {
    $saida = & certreq.exe -new -user -q $inf $pedidoArq 2>&1 | Out-String
    if (-not (Test-Path -LiteralPath $pedidoArq)) { throw "O certreq nao gerou o pedido:`n$saida" }
} finally { Remove-Item -LiteralPath $inf -ErrorAction SilentlyContinue }
Diga 'Pedido gerado ..... chave privada deste PC, nao exportavel'

# ------------------------------------------------------------- 4. o alistamento
#     ARMADILHA MEDIDA (15/10): `Get-Content -Raw` devolve a string DECORADA
#     com PSPath, PSProvider e companhia. O ConvertTo-Json serializa o objeto
#     inteiro, o `pedido` chega como OBJETO e a VPS devolve 422 -- aconteceu no
#     primeiro teste. ReadAllText devolve texto puro.
$corpo = @{
    ramal  = $ramal
    senha  = $Senha.Trim()
    pedido = [IO.File]::ReadAllText($pedidoArq)
    pc     = $env:COMPUTERNAME
} | ConvertTo-Json

Diga 'Alistando ......... falando com a VPS...'
try {
    $r = Invoke-RestMethod -Method Post -Uri "$URL_PAINEL/api/ligacoes/agente/alistar" `
        -ContentType 'application/json; charset=utf-8' -Body $corpo -TimeoutSec 60
} catch {
    # ARMADILHA MEDIDA (15/10): no PowerShell 5.1 o corpo da resposta de erro
    # JA FOI CONSUMIDO pelo Invoke-RestMethod -- ler o GetResponseStream()
    # devolve vazio, e a pessoa via "Nao consegui falar com a VPS (401)" em vez
    # de "Senha invalida ou vencida". O corpo vive em $_.ErrorDetails.Message.
    $detalhe = ''
    try {
        if ($_.ErrorDetails -and $_.ErrorDetails.Message) {
            $detalhe = "$(($_.ErrorDetails.Message | ConvertFrom-Json).detail)"
        }
    } catch { $detalhe = '' }
    if (-not $detalhe -and $_.Exception.Response) {
        try {
            $leitor = New-Object IO.StreamReader($_.Exception.Response.GetResponseStream())
            $texto = $leitor.ReadToEnd()
            $leitor.Close()
            if ($texto) { $detalhe = "$(($texto | ConvertFrom-Json).detail)" }
        } catch { $detalhe = '' }
    }
    Remove-Item -LiteralPath $pedidoArq -ErrorAction SilentlyContinue
    if ($detalhe) { throw "A VPS recusou: $detalhe" }
    throw "Nao consegui falar com a VPS ($($_.Exception.Message))."
}
Remove-Item -LiteralPath $pedidoArq -ErrorAction SilentlyContinue
if (-not $r.chave -or -not $r.cert_pem) { throw 'A VPS respondeu sem chave ou sem certificado.' }
Diga ("Alistado .......... ramal {0}, {1}" -f $r.ramal, $r.atendente) 'Green'
if ($r.pc_anterior) {
    Diga ("  ATENCAO: o ramal {0} estava no PC {1}, que PAROU de enviar agora." -f $r.ramal, $r.pc_anterior) 'Yellow'
}

# ------------------------------------------- 4.5 a pasta das gravacoes (0.7)
#
# 🔵 *"pedindo permissão ao instalar"*.
#
# 🚨 CONSENTIMENTO, NAO FORMALIDADE: a partir do 0.7 o agente procura pastas
# dentro do perfil deste usuario e SOBE o audio para a VPS. Quem usa o PC tem
# de ver isso escrito e concordar -- nao descobrir depois. Ate o 0.6 a pasta
# era deduzida em silencio, e quando a deducao errava (OneDrive move a Area de
# Trabalho) ninguem sabia dizer onde ele tinha procurado.
Diga ''
Diga 'Pasta das gravacoes' 'Cyan'

$pastaSugerida = $null
$comoAchou = $null
try {
    $ini = $null
    foreach ($c in @((Join-Path $env:APPDATA 'MicroSIP\MicroSIP.ini'),
                     (Join-Path $env:LOCALAPPDATA 'MicroSIP\MicroSIP.ini'))) {
        if (Test-Path -LiteralPath $c) { $ini = $c; break }
    }
    if ($ini) {
        foreach ($linha in Get-Content -LiteralPath $ini) {
            if ($linha -match '^\s*recordingPath\s*=\s*(.+)$') {
                $bruto = $Matches[1].Trim()
                if ($bruto) {
                    $pastaSugerida = [Environment]::ExpandEnvironmentVariables($bruto)
                    $comoAchou = 'esta no MicroSIP.ini'
                }
                break
            }
        }
    }
    # 🚨 Nao achou no .ini: PROCURA pelo nome, em vez de chutar a Area de
    # Trabalho -- que era o palpite do 0.6 e o que quebrava com OneDrive.
    if (-not $pastaSugerida) {
        $raizes = @($env:USERPROFILE)
        foreach ($v in @('OneDrive', 'OneDriveCommercial', 'OneDriveConsumer')) {
            $valor = [Environment]::GetEnvironmentVariable($v)
            if ($valor) { $raizes += $valor }
        }
        foreach ($raiz in $raizes) {
            if (-not $raiz -or -not (Test-Path -LiteralPath $raiz)) { continue }
            $achada = Get-ChildItem -LiteralPath $raiz -Directory -Filter 'Recordings' `
                -Recurse -Depth 4 -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($achada) {
                $pastaSugerida = $achada.FullName
                $comoAchou = 'encontrada procurando pelo nome'
                break
            }
        }
    }
} catch { }

if ($pastaSugerida) {
    Diga ("  Achei: {0}" -f $pastaSugerida) 'Green'
    Diga ("  ({0})" -f $comoAchou) 'DarkGray'
} else {
    Diga '  Nao achei a pasta de gravacoes deste MicroSIP.' 'Yellow'
}
Diga '  O agente vai LER os audios desta pasta e envia-los para a VPS da Movisat.' 'Yellow'
Diga '  Ele nao le mais nada do computador.' 'DarkGray'

$pastaEscolhida = $null
try {
    if ($pastaSugerida) {
        $resp = Read-Host '  E essa a pasta? (ENTER = sim; ou cole outro caminho)'
    } else {
        $resp = Read-Host '  Cole o caminho da pasta (ENTER = deixar o agente procurar)'
    }
    if ($resp -and $resp.Trim()) {
        $pastaEscolhida = $resp.Trim().Trim('"')
    } elseif ($pastaSugerida) {
        $pastaEscolhida = $pastaSugerida
    }
} catch {
    # ⚠️ Instalacao sem ninguem na frente (sem console): NAO INVENTA escolha.
    # Segue sem ela, o agente cai no .ini ou na busca, e o painel passa a
    # dizer qual foi -- que e melhor que uma escolha que ninguem fez.
    $pastaEscolhida = $null
}

if ($pastaEscolhida) {
    if (Test-Path -LiteralPath $pastaEscolhida) {
        Diga ("  Pasta confirmada: {0}" -f $pastaEscolhida) 'Green'
    } else {
        # Nao barra: MicroSIP novo ainda nao criou a pasta, e isso e normal.
        Diga ("  Anotado: {0} (ainda nao existe -- sera criada na 1a gravacao)" -f $pastaEscolhida) 'Yellow'
    }
} else {
    Diga '  Sem escolha: o agente procura, e o painel mostra onde achou.' 'DarkGray'
}

# ------------------------------------------------------- 5. instalar o certificado
$cerArq = Join-Path $env:TEMP ("movizap-cert-{0}.cer" -f $ramal)
Set-Content -LiteralPath $cerArq -Value $r.cert_pem -Encoding ASCII
try {
    $novo = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2($cerArq)
    # NAO usar `certreq -accept`: exige que a CA seja raiz confiavel do Windows
    # (CERT_E_CHAINING, medido em 25/09), e isso faria o PC confiar nela para
    # TUDO. O caminho e o cofre do usuario + certutil -repairstore.
    $cofre = New-Object System.Security.Cryptography.X509Certificates.X509Store('My', 'CurrentUser')
    $cofre.Open('ReadWrite'); $cofre.Add($novo); $cofre.Close()
    $saida = & certutil.exe -user -repairstore My $novo.Thumbprint 2>&1 | Out-String
    $noCofre = Get-ChildItem Cert:\CurrentUser\My |
        Where-Object { $_.Thumbprint -eq $novo.Thumbprint } | Select-Object -First 1
    if (-not $noCofre -or -not $noCofre.HasPrivateKey) {
        throw "O certificado nao ficou ligado a chave deste PC. Saida do certutil:`n$saida"
    }
    # O rascunho sai do cofre de pedidos. SEM -DeleteKey: a chave e a mesma
    # que acabou de ser ligada ao certificado.
    Get-ChildItem Cert:\CurrentUser\REQUEST -ErrorAction SilentlyContinue |
        Where-Object { $_.Subject -like 'CN=mzl-*' } |
        ForEach-Object { Remove-Item -LiteralPath $_.PSPath -ErrorAction SilentlyContinue }
    # O certificado ANTERIOR deste ramal foi revogado na VPS no alistamento de
    # agora: deixa-lo no cofre so acumula certificado morto a cada troca de PC
    # (medido em 15/10, depois do primeiro alistamento real).
    Get-ChildItem Cert:\CurrentUser\My -ErrorAction SilentlyContinue |
        Where-Object { $_.Subject -like "CN=mzl-$ramal-*" -and $_.Thumbprint -ne $novo.Thumbprint } |
        ForEach-Object {
            Remove-Item -LiteralPath $_.PSPath -DeleteKey -Force -ErrorAction SilentlyContinue
            Diga ("Certificado antigo .. {0}... removido do cofre (ja revogado na VPS)" -f $_.Thumbprint.Substring(0, 8)) 'DarkGray'
        }
} finally { Remove-Item -LiteralPath $cerArq -ErrorAction SilentlyContinue }
Diga ("Certificado ....... {0}... vale ate {1:dd/MM/yyyy}" -f $novo.Thumbprint.Substring(0, 8), $novo.NotAfter)

# ------------------------------------------------------------ 6. guardar a chave
# DPAPI do usuario: o config.json copiado para outro PC ou outro usuario nao
# se abre. Decisao dele, 15/10.
$protegida = ConvertFrom-SecureString -SecureString (ConvertTo-SecureString -String $r.chave -AsPlainText -Force)
$Senha = $null
$aGravar = @{ url = $URL_MTLS; ramal = $ramal; cert = $novo.Thumbprint
              chave_protegida = $protegida }
# 🆕 0.7: a pasta que a pessoa confirmou no passo 4.5. ⚠️ Entra NESTE mesmo
# Set-Content de proposito: dois momentos de escrita do config.json seriam dois
# jeitos de perder a chave do ramal, que so se recupera com senha nova.
if ($pastaEscolhida) { $aGravar['pasta_gravacoes'] = $pastaEscolhida }
$aGravar | ConvertTo-Json | Set-Content -LiteralPath $CONFIG -Encoding UTF8
Diga 'Chave guardada .... cifrada neste usuario do Windows (DPAPI)'

# ---------------------------------------------------------------- 7. a tarefa
if (Get-ScheduledTask -TaskName $TAREFA_ANTIGA -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TAREFA_ANTIGA -Confirm:$false
    Diga "Tarefa antiga ..... '$TAREFA_ANTIGA' removida (virou '$TAREFA')"
}
if (Test-Path -LiteralPath $LANCADOR) {
    # Com o lancador, o Gerenciador de Tarefas mostra "MoviZap - Backup de
    # Ligacoes" em vez de powershell.exe -- e ninguem encerra por engano.
    $acao = New-ScheduledTaskAction -Execute $LANCADOR -Argument '-Enviar'
} else {
    $acao = New-ScheduledTaskAction -Execute 'powershell.exe' `
        -Argument ('-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "{0}" -Enviar' -f $AGENTE)
}
$quemId = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$gatilhos = @(
    (New-ScheduledTaskTrigger -Daily -At '12:00'),
    (New-ScheduledTaskTrigger -Daily -At '17:30'),
    # PC desligado nos horarios: o que ficou para tras sobe ao entrar.
    (New-ScheduledTaskTrigger -AtLogOn -User $quemId)
)
$gatilhos[2].Delay = 'PT5M'   # espera a rede e o MicroSIP subirem
$ajustes = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
    -MultipleInstances IgnoreNew -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 10)
$quem = New-ScheduledTaskPrincipal -UserId $quemId -LogonType Interactive
$descricao = @'
Backup das ligacoes do MicroSIP no MoviZap (12:00, 17:30 e ao entrar no Windows).

NAO apague esta tarefa: ela e o que guarda o historico de ligacoes da empresa.
O que ela NAO faz: nao apaga nada do PC, nao grava ligacao nova, nao escuta
nada ao vivo e nao manda nada fora destes horarios. Duvidas: Iago (Movisat).
'@
Register-ScheduledTask -TaskName $TAREFA -Action $acao -Trigger $gatilhos -Settings $ajustes `
    -Principal $quem -Description $descricao -Force | Out-Null
Diga "Tarefa criada ..... '$TAREFA' (12:00, 17:30 e 5 min depois de entrar)"

# --------------------------------------------- 8. aparecer para o Windows e para a pessoa
# Aplicativos instalados: da cara de programa instalado (em vez de script
# solto) e um jeito certo de remover, no lugar do Gerenciador de Tarefas.
New-Item -Path $CHAVE_REGISTRO -Force | Out-Null
$desinstalar = ('powershell.exe -NoProfile -ExecutionPolicy Bypass -File "{0}"' -f (Join-Path $DADOS 'desinstalar.ps1'))
Set-ItemProperty -Path $CHAVE_REGISTRO -Name 'DisplayName' -Value 'MoviZap - Backup de Ligacoes'
Set-ItemProperty -Path $CHAVE_REGISTRO -Name 'DisplayVersion' -Value $VERSAO
Set-ItemProperty -Path $CHAVE_REGISTRO -Name 'Publisher' -Value 'Movisat'
Set-ItemProperty -Path $CHAVE_REGISTRO -Name 'InstallLocation' -Value $DADOS
Set-ItemProperty -Path $CHAVE_REGISTRO -Name 'UninstallString' -Value $desinstalar
Set-ItemProperty -Path $CHAVE_REGISTRO -Name 'NoModify' -Value 1 -Type DWord
Set-ItemProperty -Path $CHAVE_REGISTRO -Name 'NoRepair' -Value 1 -Type DWord
if (Test-Path -LiteralPath (Join-Path $AQUI 'desinstalar.ps1')) {
    Copy-Item -LiteralPath (Join-Path $AQUI 'desinstalar.ps1') -Destination $DADOS -Force
}
if (Test-Path -LiteralPath (Join-Path $AQUI 'LEIA-ME.txt')) {
    Copy-Item -LiteralPath (Join-Path $AQUI 'LEIA-ME.txt') -Destination $DADOS -Force
}

# Atalho de "ver situacao": quem desconfia confere, em vez de encerrar.
$menu = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs'
$atalho = Join-Path $menu 'MoviZap - Backup de Ligacoes (ver situacao).lnk'
try {
    $shell = New-Object -ComObject WScript.Shell
    $l = $shell.CreateShortcut($atalho)
    if (Test-Path -LiteralPath $LANCADOR) {
        $l.TargetPath = $LANCADOR
        $l.Arguments = '-Simular'
    } else {
        $l.TargetPath = 'powershell.exe'
        $l.Arguments = ('-NoProfile -ExecutionPolicy Bypass -NoExit -File "{0}" -Simular' -f $AGENTE)
    }
    $l.WorkingDirectory = $DADOS
    $l.Description = 'Mostra ramal, pasta das gravacoes e o ultimo envio. Nao envia nada.'
    $l.Save()
    Diga 'Atalho criado ..... Menu Iniciar > MoviZap - Backup de Ligacoes (ver situacao)'
} catch {
    Diga ("Atalho nao criado (nao impede nada): {0}" -f $_.Exception.Message) 'Yellow'
}

# ------------------------------------------------------------ 9. a primeira passada
if (-not $NaoRodarAgora) {
    Diga ''
    Diga 'Rodando uma vez agora, para provar que falou com a VPS...'
    if (Test-Path -LiteralPath $LANCADOR) { & $LANCADOR -Enviar }
    else { & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $AGENTE -Enviar }
}

Diga ''
Diga 'PRONTO. Este PC passa a mandar o historico de ligacoes as 12:00, as 17:30' 'Green'
Diga 'e 5 minutos depois de entrar no Windows. Nada e apagado deste PC.' 'Green'

# ----------------------------------------------------- 10. apagar o instalador
# Decisao dele (15/10): o instalador sai do PC. SO EM CASO DE SUCESSO -- se
# algo falhar, o script morre antes daqui e a pessoa ainda tem com que tentar
# de novo. O que sai e o INSTALADOR; a pasta do agente e as gravacoes ficam.
if (-not $NaoApagar) {
    $meExe = $env:MZL_INSTALADOR     # o .exe passa o proprio caminho
    $apagar = @()
    if ($meExe -and (Test-Path -LiteralPath $meExe)) { $apagar += $meExe }
    foreach ($n in @('instalar.ps1', 'movizap-ligacoes.ps1', '1 - Instalar.cmd',
                     '2 - Concluir.cmd', '0 - Testar (simular).cmd')) {
        $p = Join-Path $AQUI $n
        if (Test-Path -LiteralPath $p) { $apagar += $p }
    }
    if ($apagar.Count) {
        # Um arquivo em uso nao se apaga sozinho. O .exe sai de cena logo
        # depois de nos chamar, mas o antivirus pode estar com ele aberto por
        # alguns segundos -- dai a tentativa repetida (30 x 2 s) em vez de uma.
        $lista = ($apagar | ForEach-Object { '"' + $_ + '"' }) -join ' '
        $laco = 'for /l %i in (1,1,30) do (ping -n 3 127.0.0.1 >nul & del /f /q ' +
                $lista + ' 2>nul & if not exist ' + ($apagar[0] | ForEach-Object { '"' + $_ + '"' }) +
                ' exit)'
        Start-Process -WindowStyle Hidden -FilePath 'cmd.exe' -ArgumentList ('/c ' + $laco) | Out-Null
        Diga ''
        Diga 'O instalador se apaga desta pasta em alguns segundos.' 'DarkGray'
    }
}
