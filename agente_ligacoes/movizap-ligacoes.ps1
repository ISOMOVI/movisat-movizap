<#
  MoviZap - Ligacoes  |  agente do MicroSIP  |  versao 0.6 (19/10/2026)
  --------------------------------------------------------------------------
  Le as gravacoes e o historico do MicroSIP deste PC e sobe para a VPS o que
  ainda nao subiu, conferindo cada arquivo por hash.

  0.6 (19/10):
    - LIMPEZA LOCAL: gravacao com mais de 7 dias que a VPS JA CONFIRMOU sai
      deste PC (decisao dele: "7 dias ja pode apagar"). Confirmada quer dizer
      que o hash esta no enviados.json, e ele so entra la quando a VPS devolveu
      o MESMO sha256 -- nao basta ter dado 200;
    - nunca encosta no call_log.db do MicroSIP: o historico fica;
    - sem enviados.json, ou com ele vazio, NAO APAGA NADA (sem confirmacao,
      nao ha o que apagar com seguranca);
    - -Dias muda o prazo, -NaoApagar desliga a limpeza nesta passada, e a
      simulacao so conta o que apagaria.

  0.5 (15/10, Bloco 9):
    - -Exportar grava um PACOTE (.zip) com o historico e as gravacoes deste PC,
      para importar na VPS depois. Nao precisa de chave nem de config e nao
      fala com a VPS: serve justamente no PC que ainda NAO foi alistado;
    - o pacote tem a MESMA forma do envio, para o import entrar pelo mesmo
      caminho de gravacao e com a mesma idempotencia.

  0.4 (15/10):
    - a chave do ramal fica CIFRADA no config.json, amarrada a este usuario
      deste PC (DPAPI): o arquivo copiado para outra maquina nao se abre;
    - config.json da v0.3 (chave em texto puro) e migrado na primeira passada,
      sem reinstalar nada;
    - o alistamento passou a ser do instalador (uma senha de uso unico), e o
      agente nao conhece senha nenhuma: ele so usa chave + certificado.

  0.3 (Plano 5.1):
    - acha o MicroSIP pelo proprio MicroSIP.ini (instalado ou portatil) e a
      pasta pelo recordingPath dele -- nunca procurando pasta pelo nome;
    - avisa quando a gravacao automatica esta desligada, a pasta nao existe
      ou o disco esta quase cheio;
    - ate 3 tentativas por envio (30 s, 2 min, 5 min); 429 espera e segue;
      um arquivo com erro nao trava os outros;
    - tempo limite pelo tamanho do arquivo;
    - uma execucao por vez (trava .lock);
    - porta propria com certificado do PC (mTLS), quando o config.json tem
      "cert" -- sem ele, usa a rota antiga do painel.

  Uso:
    ... -File movizap-ligacoes.ps1 -Simular            mostra o que faria
    ... -File movizap-ligacoes.ps1 -Enviar             envia (a tarefa usa este)
    ... -File movizap-ligacoes.ps1 -Simular -Ini <arq> testa com outro MicroSIP.ini
    ... -File movizap-ligacoes.ps1 -Exportar            grava o pacote .zip
#>
[CmdletBinding()]
param(
    [switch]$Simular,
    [switch]$Enviar,
    [int]$Limite = 0,          # 0 = sem limite; 1 = "validar 1 antes do lote"
    [string]$Ini = '',         # so para teste: outro MicroSIP.ini
    [int[]]$Esperas = @(30, 120, 300),
    [string]$PastaDados = '',  # so para teste: outra pasta de config/controle/log
    [switch]$Exportar,         # grava um pacote .zip para importar na VPS
    [string]$Destino = '',     # onde gravar o pacote (padrao: Area de Trabalho)
    [int]$Dias = 7,            # 0.6: apagar gravacao local confirmada com mais de N dias
    [switch]$NaoApagar         # 0.6: nao apaga nada nesta passada
)

$ErrorActionPreference = 'Stop'
$VERSAO = '0.7'
$AQUI = Split-Path -Parent $MyInvocation.MyCommand.Path
$RELATORIO = Join-Path $AQUI 'relatorio-simulacao.txt'
$DADOS = if ($PastaDados) { $PastaDados } else { Join-Path $env:LOCALAPPDATA 'MoviZapLigacoes' }
$CONFIG = Join-Path $DADOS 'config.json'
$ENVIADOS = Join-Path $DADOS 'enviados.json'
$LOG = Join-Path $DADOS 'agente.log'
$TRAVA = Join-Path $DADOS 'agente.lock'

# --------------------------------------------------------------- SQLite do Windows
# winsqlite3.dll vem no Windows 10/11 (System32). Abrimos SOMENTE LEITURA e sobre
# uma COPIA do banco: o MicroSIP pode estar com ele aberto.
if (-not ('WinSqlite' -as [type])) {
    Add-Type -Language CSharp -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using System.Collections.Generic;
public static class WinSqlite {
    [DllImport("winsqlite3.dll", EntryPoint="sqlite3_open_v2", CallingConvention=CallingConvention.StdCall, CharSet=CharSet.Ansi)]
    static extern int open_v2(byte[] nome, out IntPtr db, int flags, IntPtr vfs);
    [DllImport("winsqlite3.dll", EntryPoint="sqlite3_prepare_v2", CallingConvention=CallingConvention.StdCall)]
    static extern int prepare_v2(IntPtr db, byte[] sql, int n, out IntPtr stmt, IntPtr resto);
    [DllImport("winsqlite3.dll", EntryPoint="sqlite3_step", CallingConvention=CallingConvention.StdCall)]
    static extern int step(IntPtr stmt);
    [DllImport("winsqlite3.dll", EntryPoint="sqlite3_column_count", CallingConvention=CallingConvention.StdCall)]
    static extern int column_count(IntPtr stmt);
    [DllImport("winsqlite3.dll", EntryPoint="sqlite3_column_name", CallingConvention=CallingConvention.StdCall)]
    static extern IntPtr column_name(IntPtr stmt, int i);
    [DllImport("winsqlite3.dll", EntryPoint="sqlite3_column_text", CallingConvention=CallingConvention.StdCall)]
    static extern IntPtr column_text(IntPtr stmt, int i);
    [DllImport("winsqlite3.dll", EntryPoint="sqlite3_column_bytes", CallingConvention=CallingConvention.StdCall)]
    static extern int column_bytes(IntPtr stmt, int i);
    [DllImport("winsqlite3.dll", EntryPoint="sqlite3_finalize", CallingConvention=CallingConvention.StdCall)]
    static extern int finalize(IntPtr stmt);
    [DllImport("winsqlite3.dll", EntryPoint="sqlite3_close", CallingConvention=CallingConvention.StdCall)]
    static extern int close(IntPtr db);

    static byte[] Utf8(string s) { return System.Text.Encoding.UTF8.GetBytes(s + "\0"); }
    static string Texto(IntPtr p, int n) {
        if (p == IntPtr.Zero) return null;
        byte[] b = new byte[n]; Marshal.Copy(p, b, 0, n);
        return System.Text.Encoding.UTF8.GetString(b);
    }

    public static List<Dictionary<string,string>> Consultar(string arquivo, string sql) {
        IntPtr db; IntPtr st;
        int rc = open_v2(Utf8(arquivo), out db, 1 /* SQLITE_OPEN_READONLY */, IntPtr.Zero);
        if (rc != 0) throw new Exception("SQLite nao abriu o historico (codigo " + rc + ")");
        try {
            rc = prepare_v2(db, Utf8(sql), -1, out st, IntPtr.Zero);
            if (rc != 0) throw new Exception("SQLite recusou a consulta (codigo " + rc + ")");
            var linhas = new List<Dictionary<string,string>>();
            int cols = column_count(st);
            while (step(st) == 100 /* SQLITE_ROW */) {
                var l = new Dictionary<string,string>();
                for (int i = 0; i < cols; i++) {
                    string nome = Marshal.PtrToStringAnsi(column_name(st, i));
                    l[nome] = Texto(column_text(st, i), column_bytes(st, i));
                }
                linhas.Add(l);
            }
            finalize(st);
            return linhas;
        } finally { close(db); }
    }
}
'@
}

# --------------------------------------------------------------- achar o MicroSIP
# REGRAS 1-5 (Plano 5.1): o MicroSIP diz onde grava. Nunca procurar pasta pelo
# nome -- outro programa pode ter uma "Recordings" (gravador de tela, OBS).
function Achar-Ini {
    if ($Ini) { if (Test-Path -LiteralPath $Ini) { return $Ini } else { return $null } }
    # 1. Instalacao normal: %APPDATA%\MicroSIP\MicroSIP.ini
    $normal = Join-Path $env:APPDATA 'MicroSIP\MicroSIP.ini'
    if (Test-Path -LiteralPath $normal) { return $normal }
    # 2. Portatil: o ini mora ao lado do MicroSIP.exe.
    $exes = New-Object System.Collections.Generic.List[string]
    try { Get-Process -Name MicroSIP -ErrorAction Stop | ForEach-Object { if ($_.Path) { $exes.Add($_.Path) } } } catch { }
    foreach ($base in @($env:LOCALAPPDATA, $env:ProgramFiles, ${env:ProgramFiles(x86)})) {
        if ($base) { $exes.Add((Join-Path $base 'MicroSIP\MicroSIP.exe')) }
    }
    foreach ($exe in $exes) {
        $ao_lado = Join-Path (Split-Path -Parent $exe) 'MicroSIP.ini'
        if (Test-Path -LiteralPath $ao_lado) { return $ao_lado }
    }
    return $null
}

# ============================================================================
# A PASTA DE GRAVACAO -- travas, busca e as duas fontes de fora (v0.7, 26/10)
# ----------------------------------------------------------------------------
# 🚨 AS TRAVAS MORAM AQUI, NAO NA VPS. A VPS pode MANDAR um caminho; quem diz
# se ele e aceitavel e este programa, no PC. Um agente que confia na VPS para
# isso e um agente que obedece a VPS invadida -- e este programa le disco e
# SOBE arquivo.
# ============================================================================

# As raizes de onde a coleta pode sair: o perfil da pessoa e as pastas de
# OneDrive. Nada de C:\Windows, nada de outro usuario, nada de unidade de rede.
function Raizes-Permitidas {
    $r = New-Object System.Collections.Generic.List[string]
    if ($env:USERPROFILE) { $r.Add($env:USERPROFILE) }
    foreach ($v in @('OneDrive', 'OneDriveCommercial', 'OneDriveConsumer')) {
        $valor = [Environment]::GetEnvironmentVariable($v)
        if ($valor) { $r.Add($valor) }
    }
    return $r
}

function Caminho-Permitido([string]$caminho) {
    if (-not $caminho) { return $null }
    try {
        $cheio = [IO.Path]::GetFullPath([Environment]::ExpandEnvironmentVariables($caminho))
    } catch { return $null }
    # Unidade de rede fora: backup de pasta compartilhada e outra decisao, e
    # nao se toma por caminho digitado num painel.
    if ($cheio.StartsWith('\\')) { return $null }
    foreach ($raiz in @(Raizes-Permitidas)) {
        $r = [IO.Path]::GetFullPath($raiz).TrimEnd('\')
        if ($cheio -eq $r -or $cheio.StartsWith($r + '\', 'OrdinalIgnoreCase')) {
            return $cheio
        }
    }
    return $null
}

# ⚠️ `Ler-Config`/`Gravar-Config` NAO EXISTIAM: a config era lida inline em
# dois pontos do arquivo (`Executar-Envio` e o alistamento), cada um com o seu
# `Get-Content | ConvertFrom-Json`. Eu ia chamar uma funcao que nao existe --
# o `grep` pegou antes. Elas nascem aqui porque agora ha um terceiro leitor, e
# tres copias da mesma leitura e uma delas divergindo.
function Ler-Config {
    if (-not (Test-Path -LiteralPath $CONFIG)) { return $null }
    try { return Get-Content -LiteralPath $CONFIG -Raw -Encoding UTF8 | ConvertFrom-Json }
    catch { return $null }
}

# 🚨 Grava preservando o que ja estava: a chave do ramal vive neste arquivo, e
# reescrever o json inteiro a partir de um objeto parcial apagaria o
# alistamento deste PC -- que so se recupera com senha nova.
function Gravar-Config($pares) {
    $cfg = Ler-Config
    if (-not $cfg) { return }
    foreach ($k in $pares.Keys) {
        $cfg | Add-Member -NotePropertyName $k -NotePropertyValue $pares[$k] -Force
    }
    $cfg | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $CONFIG -Encoding UTF8
}

# A escolha que a pessoa confirmou na instalacao, no config.json local.
function Pasta-Escolhida {
    try {
        $cfg = Ler-Config
        if ($cfg -and $cfg.pasta_gravacoes) { return [string]$cfg.pasta_gravacoes }
    } catch { }
    return $null
}

# O que a VPS mandou na ultima resposta de batimento. 🚨 Guardado no
# config.json porque o agente roda e sai: sem guardar, a passada seguinte
# comecaria sem saber.
function Pastas-Da-Vps {
    try {
        $cfg = Ler-Config
        if ($cfg -and $cfg.pastas_da_vps) { return @($cfg.pastas_da_vps) }
    } catch { }
    return @()
}

# Procura uma pasta de gravacao pelo NOME, dentro das raizes permitidas.
# ⚠️ PROFUNDIDADE E TEMPO LIMITADOS: varredura de disco inteiro num PC de
# trabalho e o tipo de coisa que a pessoa sente, e nao poderia ser causada por
# um programa de backup silencioso.
function Procurar-Pasta-De-Gravacao {
    $nomes = @('Recordings', 'Gravacoes', 'Gravacoes MicroSIP')
    $relogio = [Diagnostics.Stopwatch]::StartNew()
    foreach ($raiz in @(Raizes-Permitidas)) {
        if (-not (Test-Path -LiteralPath $raiz)) { continue }
        foreach ($nome in $nomes) {
            try {
                $achadas = Get-ChildItem -LiteralPath $raiz -Directory -Filter $nome `
                    -Recurse -Depth 4 -ErrorAction SilentlyContinue |
                    Select-Object -First 1
            } catch { $achadas = $null }
            if ($achadas) { return $achadas.FullName }
            if ($relogio.Elapsed.TotalSeconds -gt 20) { return $null }
        }
    }
    return $null
}

function Ler-MicroSIP {
    $arq = Achar-Ini
    # 5. Nada achado: nao sobe nada, e o batimento leva o erro (vira alerta).
    if (-not $arq) { throw 'MicroSIP nao encontrado neste PC (sem MicroSIP.ini).' }
    $secao = ''; $cfg = @{}
    foreach ($linha in Get-Content -LiteralPath $arq) {
        $l = $linha.Trim()
        if ($l -match '^\[(.+)\]$') { $secao = $Matches[1]; continue }
        if ($l -match '^([^=]+)=(.*)$') { $cfg["$secao.$($Matches[1])"] = $Matches[2] }
    }
    # SENHA NAO E LIDA: so os campos abaixo.
    $pastaIni = Split-Path -Parent $arq
    # ========================================================================
    # ONDE PROCURAR AS GRAVACOES -- a ordem de precedencia (v0.7, 26/10)
    # ------------------------------------------------------------------------
    # 1. pastas que a VPS mandou   -> 'vps'
    # 2. a escolha da instalacao    -> 'escolhida'
    # 3. recordingPath do .ini      -> 'ini' / 'relativa'
    # 4. busca pelo NOME da pasta   -> 'busca'
    #
    # 🚨 O PALPITE DA AREA DE TRABALHO SAIU. Ate a v0.6, recordingPath vazio
    # caia em `GetFolderPath('Desktop')\Recordings` -- e o proprio comentario
    # dizia que era HIPOTESE. Com OneDrive a Area de Trabalho muda de lugar, e
    # era exatamente o caso que motivou esta versao. Chutar e pior que
    # procurar: o chute nao avisa que chutou.
    # ========================================================================
    $pasta = $null
    $origem = $null

    # 1. O que a VPS mandou, na ordem. Vence tudo: e o pedido dele de poder
    #    "atualizar do lado de ca".
    foreach ($candidata in @(Pastas-Da-Vps)) {
        $c = Caminho-Permitido $candidata
        if ($c -and (Test-Path -LiteralPath $c)) { $pasta = $c; $origem = 'vps'; break }
    }

    # 2. A escolha confirmada na instalacao.
    if (-not $pasta) {
        $escolhida = Caminho-Permitido (Pasta-Escolhida)
        if ($escolhida -and (Test-Path -LiteralPath $escolhida)) {
            $pasta = $escolhida; $origem = 'escolhida'
        }
    }

    # 3. O .ini, que era o unico caminho ate a v0.6.
    if (-not $pasta) {
        $doIni = $cfg['Settings.recordingPath']
        if ($doIni) {
            $doIni = [Environment]::ExpandEnvironmentVariables($doIni)
            if ([IO.Path]::IsPathRooted($doIni)) {
                $pasta = $doIni; $origem = 'ini'
            } else {
                $pasta = Join-Path $pastaIni $doIni; $origem = 'relativa'
            }
        }
    }

    # 4. Procurar pelo NOME. 🔵 *"ou buscar pelo nome da pasta"*.
    if (-not $pasta) {
        $achada = Procurar-Pasta-De-Gravacao
        if ($achada) { $pasta = $achada; $origem = 'busca' }
    }

    # 5. Nada: a pasta fica nula e o aviso DIZ que nao achou onde procurar --
    #    em vez de apontar para um lugar inventado e dizer "pasta nao existe".
    if (-not $pasta) { $origem = $null }
    $historico = Join-Path $pastaIni 'call_log.db'
    $auto = $cfg['Settings.autoRecording']
    $versaoSip = $null
    try {
        $exe = Join-Path (Split-Path -Parent $arq) 'MicroSIP.exe'
        if (-not (Test-Path -LiteralPath $exe)) { $exe = Join-Path $env:LOCALAPPDATA 'MicroSIP\MicroSIP.exe' }
        if (Test-Path -LiteralPath $exe) { $versaoSip = (Get-Item -LiteralPath $exe).VersionInfo.ProductVersion }
    } catch { }
    [pscustomobject]@{
        Ini          = $arq
        Pasta        = $pasta
        Origem       = $origem
        Ramal        = $cfg['Account1.username']
        Rotulo       = $cfg['Account1.label']
        Exibicao     = $cfg['Account1.displayName']
        Servidor     = $cfg['Account1.server']
        Historico    = $historico
        AutoGravacao = ($auto -eq '1')
        VersaoSip    = $versaoSip
    }
}

# Avisos que nao impedem o envio mas pedem olho (vao no batimento e no alerta).
function Avisos($ms) {
    $a = New-Object System.Collections.Generic.List[string]
    # 6. Gravacao automatica desligada: ligacao sem gravacao e backup perdido calado.
    if (-not $ms.AutoGravacao) { $a.Add('gravacao automatica desligada no MicroSIP') }
    # 7. Pasta inexistente: nao e erro (MicroSIP novo, ainda sem ligacao gravada).
    # 🚨 v0.7: O AVISO PASSOU A DIZER ONDE PROCUROU. Ate a v0.6 ele dizia
    # "pasta de gravacoes ainda nao existe" sem dizer QUAL pasta -- e foi por
    # isso que ninguem viu, pelo painel, que o caminho calculado estava errado
    # no PC com OneDrive. Aviso que nao diz onde procurou nao e diagnostico.
    if (-not $ms.Pasta) {
        $a.Add('nao achei onde o MicroSIP grava (recordingPath vazio e nenhuma pasta encontrada)')
    } elseif (-not (Test-Path -LiteralPath $ms.Pasta)) {
        $a.Add(('pasta de gravacoes ainda nao existe: {0} (origem: {1})' -f $ms.Pasta, $ms.Origem))
    }
    try {
        $raiz = [IO.Path]::GetPathRoot($ms.Pasta)
        $livre = (New-Object IO.DriveInfo($raiz)).AvailableFreeSpace
        if ($livre -lt 1GB) { $a.Add(('disco {0} com {1:N1} GB livres' -f $raiz, ($livre / 1GB))) }
    } catch { }
    return $a
}

function Ler-Historico($arquivo) {
    if (-not (Test-Path -LiteralPath $arquivo)) { return @() }
    $copia = Join-Path $env:TEMP ("movizap-call_log-{0}.db" -f ([guid]::NewGuid().ToString('N')))
    Copy-Item -LiteralPath $arquivo -Destination $copia
    try {
        $linhas = [WinSqlite]::Consultar($copia,
            'SELECT id, callId, number, name, type, time, duration, info FROM call_log ORDER BY time')
    } finally { Remove-Item -LiteralPath $copia -ErrorAction SilentlyContinue }
    foreach ($l in $linhas) {
        $quando = [DateTimeOffset]::FromUnixTimeSeconds([int64]$l['time']).LocalDateTime
        # Tipos do MicroSIP: 0 = feita, 1 = recebida, 2 = perdida.
        $sentido = switch ($l['type']) { '0' { 'feita' } '1' { 'recebida' } '2' { 'perdida' } default { "tipo $($l['type'])" } }
        [pscustomobject]@{
            CallId   = $l['callId']
            Numero   = $l['number']
            Nome     = $l['name']
            Sentido  = $sentido
            Inicio   = $quando
            Duracao  = [int]$l['duration']
            Situacao = $l['info']
            Gravacao = $null
        }
    }
}

# 8. So sobe arquivo com o nome no padrao do MicroSIP:
#    AAAAMMDD-HHMMSS-<numero>-<outgoing|incoming>-<ramal>_-_<nome>.mp3
$PADRAO = '^(?<data>\d{8})-(?<hora>\d{6})-(?<numero>.+?)-(?<sentido>outgoing|incoming)-(?<ramal>\d+)_-_(?<nome>.*)\.mp3$'

function Ler-Gravacoes($pasta) {
    if (-not (Test-Path -LiteralPath $pasta)) { return @() }
    foreach ($f in Get-ChildItem -LiteralPath $pasta -Filter *.mp3 -File) {
        $m = [regex]::Match($f.Name, $PADRAO)
        $inicio = $null
        if ($m.Success) {
            $inicio = [datetime]::ParseExact($m.Groups['data'].Value + $m.Groups['hora'].Value,
                                             'yyyyMMddHHmmss', $null)
        }
        [pscustomobject]@{
            Arquivo  = $f
            Entende  = $m.Success
            Inicio   = $inicio
            Numero   = if ($m.Success) { $m.Groups['numero'].Value } else { $null }
            Sentido  = if ($m.Success) { @{ outgoing = 'feita'; incoming = 'recebida' }[$m.Groups['sentido'].Value] } else { $null }
            # 9/10. O ramal e o do NOME do arquivo (troca de ramal, varias contas).
            Ramal    = if ($m.Success) { $m.Groups['ramal'].Value } else { $null }
            # Mexido ha menos de 60 s: pode ser uma ligacao em andamento.
            Pronto   = ((Get-Date) - $f.LastWriteTime).TotalSeconds -ge 60
            Casada   = $false
        }
    }
}

function So-Digitos($s) { if ($s) { ($s -replace '\D', '') } else { '' } }

function Mesmo-Numero($a, $b) {
    $x = So-Digitos $a; $y = So-Digitos $b
    if (-not $x -or -not $y) { return $false }
    $n = [Math]::Min(8, [Math]::Min($x.Length, $y.Length))
    return $x.Substring($x.Length - $n) -eq $y.Substring($y.Length - $n)
}

# Casa gravacao <-> ligacao. UMA LIGACAO PODE TER VARIAS GRAVACOES (a gravacao
# recomeca no meio e o MicroSIP abre outro arquivo). Vale todo arquivo do mesmo
# numero que comece de inicio - 2 s ate inicio + duracao + 60 s. A GRAVACAO
# NUNCA COMECA ANTES DA LIGACAO: os 2 s so arredondam o relogio.
function Casar($ligacoes, $gravacoes) {
    foreach ($l in $ligacoes) { $l.Gravacao = New-Object System.Collections.ArrayList }
    foreach ($g in ($gravacoes | Where-Object Entende)) {
        $melhor = $null; $dif = [double]::MaxValue
        foreach ($l in $ligacoes) {
            if (-not (Mesmo-Numero $l.Numero $g.Numero)) { continue }
            $desde = ($g.Inicio - $l.Inicio).TotalSeconds
            if ($desde -lt -2 -or $desde -gt ($l.Duracao + 60)) { continue }
            if ([Math]::Abs($desde) -lt $dif) { $melhor = $l; $dif = [Math]::Abs($desde) }
        }
        if ($melhor) { [void]$melhor.Gravacao.Add($g); $g.Casada = $true }
    }
}

function Tamanho($bytes) { '{0:N1} MB' -f ($bytes / 1MB) }
function Duracao($s) { '{0}:{1:D2}' -f [int][Math]::Floor($s / 60), ($s % 60) }

# --------------------------------------------------------------- controle local
function Registrar-Log([string]$texto) {
    New-Item -ItemType Directory -Force -Path $DADOS | Out-Null
    Add-Content -LiteralPath $LOG -Value ('{0:yyyy-MM-dd HH:mm:ss}  {1}' -f (Get-Date), $texto) -Encoding UTF8
}

function Ler-Enviados {
    if (Test-Path -LiteralPath $ENVIADOS) {
        $j = Get-Content -LiteralPath $ENVIADOS -Raw -Encoding UTF8 | ConvertFrom-Json
        $g = @{}; $l = @{}
        if ($j.gravacoes) { $j.gravacoes.PSObject.Properties | ForEach-Object { $g[$_.Name] = $_.Value } }
        if ($j.ligacoes) { $j.ligacoes.PSObject.Properties | ForEach-Object { $l[$_.Name] = $_.Value } }
        return @{ gravacoes = $g; ligacoes = $l }
    }
    return @{ gravacoes = @{}; ligacoes = @{} }
}

function Gravar-Enviados($e) {
    # Escreve num temporario e troca: queda no meio nao corrompe o controle.
    $tmp = "$ENVIADOS.tmp"
    ([pscustomobject]@{ gravacoes = $e.gravacoes; ligacoes = $e.ligacoes } | ConvertTo-Json -Depth 5) |
        Set-Content -LiteralPath $tmp -Encoding UTF8
    Move-Item -LiteralPath $tmp -Destination $ENVIADOS -Force
}

# 14. Uma execucao por vez, tambem quando alguem roda a mao. Trava com o PID;
# trava de processo morto, ou com mais de 1 h, e ignorada.
function Pegar-Trava {
    New-Item -ItemType Directory -Force -Path $DADOS | Out-Null
    if (Test-Path -LiteralPath $TRAVA) {
        $idade = ((Get-Date) - (Get-Item -LiteralPath $TRAVA).LastWriteTime).TotalMinutes
        $dono = 0; [void][int]::TryParse((Get-Content -LiteralPath $TRAVA -Raw -ErrorAction SilentlyContinue), [ref]$dono)
        $vivo = $dono -and (Get-Process -Id $dono -ErrorAction SilentlyContinue)
        if ($vivo -and $idade -lt 60) { return $false }
    }
    Set-Content -LiteralPath $TRAVA -Value $PID -Encoding ASCII
    return $true
}
function Soltar-Trava { Remove-Item -LiteralPath $TRAVA -ErrorAction SilentlyContinue }

# --------------------------------------------------------------- rede
Add-Type -AssemblyName System.Net.Http
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

class ErroDefinitivo : System.Exception {   # 400/413: o arquivo, nao a rede
    ErroDefinitivo([string]$m) : base($m) { }
}
class ErroDeAcesso : System.Exception {      # 401/403: chave ou certificado
    ErroDeAcesso([string]$m) : base($m) { }
}
class ErroDeCalma : System.Exception {       # 429: a VPS diz quanto esperar
    [int]$Espera
    ErroDeCalma([string]$m, [int]$s) : base($m) { $this.Espera = $s }
}

# ------------------------------------------------------------- a chave (DPAPI)
# A chave do ramal e o unico segredo que sobra neste PC. Cifrada pelo DPAPI do
# usuario, ela continua servindo ao agente (que roda como a propria pessoa) e
# deixa de servir a quem copie o arquivo para outro lugar.
#
# NAO protege contra quem esta logado como a pessoa -- nada no PC protegeria.
# Protege contra copia do arquivo, que e o caso real: pendrive, backup, pasta
# compartilhada.
function Proteger-Chave([string]$texto) {
    $s = ConvertTo-SecureString -String $texto -AsPlainText -Force
    return (ConvertFrom-SecureString -SecureString $s)
}

function Chave-Em-Claro($cfg) {
    if ($cfg.chave_protegida) {
        try { $s = ConvertTo-SecureString -String $cfg.chave_protegida }
        catch {
            throw [ErroDeAcesso]::new(
                'a chave guardada neste PC nao abre com o usuario atual (config.json de outro PC ou de outro usuario do Windows?)')
        }
        return [Runtime.InteropServices.Marshal]::PtrToStringAuto(
            [Runtime.InteropServices.Marshal]::SecureStringToBSTR($s))
    }
    if ($cfg.chave) { return $cfg.chave }   # v0.3, antes da migracao
    throw [ErroDeAcesso]::new("sem chave do ramal em $CONFIG")
}

function Migrar-Chave-Para-DPAPI($cfg) {
    # So faz algo uma vez: depois disso nao existe mais `chave` em texto puro.
    if (-not $cfg.chave) { return $cfg }
    $cfg | Add-Member -NotePropertyName chave_protegida `
                      -NotePropertyValue (Proteger-Chave $cfg.chave) -Force
    $cfg.PSObject.Properties.Remove('chave')
    ($cfg | ConvertTo-Json) | Set-Content -LiteralPath $CONFIG -Encoding UTF8
    Registrar-Log 'v0.4 a chave do ramal passou a ficar cifrada neste PC (DPAPI)'
    return $cfg
}

function Certificado-Do-PC($cfg) {
    if (-not $cfg.cert) { return $null }
    $c = Get-ChildItem -Path Cert:\CurrentUser\My |
        Where-Object { $_.Thumbprint -eq $cfg.cert -and $_.HasPrivateKey } | Select-Object -First 1
    if (-not $c) { throw [ErroDeAcesso]::new("certificado do PC ($($cfg.cert.Substring(0,8))...) nao esta no cofre do usuario") }
    return $c
}

function Novo-Cliente($cfg) {
    # HttpClientHandler (.NET 4.7.1+). O WebRequestHandler fica num assembly que
    # o PowerShell nao carrega sozinho -- o ensaio de 25/09 pegou isso.
    $h = New-Object System.Net.Http.HttpClientHandler
    $cert = Certificado-Do-PC $cfg
    if ($cert) {
        $h.ClientCertificateOptions = [System.Net.Http.ClientCertificateOption]::Manual
        [void]$h.ClientCertificates.Add($cert)
    }
    $c = New-Object System.Net.Http.HttpClient($h)
    # O limite e por pedido (CancellationToken), pelo tamanho do arquivo.
    $c.Timeout = [System.Threading.Timeout]::InfiniteTimeSpan
    $c.DefaultRequestHeaders.Add('X-Agente-Chave', (Chave-Em-Claro $cfg))
    return $c
}

# Porta propria (com certificado) ou rota antiga do painel (sem).
function Endereco($cfg, [string]$acao) {
    $base = $cfg.url.TrimEnd('/')
    if ($cfg.cert) { return "$base/agente/$acao" }
    return "$base/api/ligacoes/agente/$acao"
}

function Post($cliente, [string]$url, $conteudo, [int]$segundos) {
    $cts = New-Object System.Threading.CancellationTokenSource([TimeSpan]::FromSeconds($segundos))
    try {
        $r = $cliente.PostAsync($url, $conteudo, $cts.Token).GetAwaiter().GetResult()
    } catch {
        # O PowerShell embrulha a excecao do .NET: desembrulha antes de olhar o tipo.
        $ex = $_.Exception
        while ($ex -is [System.Management.Automation.MethodInvocationException] -and $ex.InnerException) { $ex = $ex.InnerException }
        if ($ex -is [System.OperationCanceledException]) { throw "tempo esgotado ($segundos s)" }
        throw $ex
    }
    $corpo = $r.Content.ReadAsStringAsync().Result
    $cod = [int]$r.StatusCode
    if ($r.IsSuccessStatusCode) { return $corpo | ConvertFrom-Json }
    $det = $corpo
    try { $det = ($corpo | ConvertFrom-Json).detail } catch { }
    if ($det -and $det.Length -gt 200) { $det = $det.Substring(0, 200) }
    if ($cod -eq 401 -or $cod -eq 403 -or ($cod -eq 400 -and "$det" -match 'SSL certificate')) {
        throw [ErroDeAcesso]::new("VPS recusou o acesso ($cod): $det")
    }
    if ($cod -eq 429) {
        # Retry-After em segundos; sem ele (ou ilegivel), 60 s.
        $espera = 60
        $valores = $null
        if ($r.Headers.TryGetValues('Retry-After', [ref]$valores)) {
            $s = 0
            if ([int]::TryParse(@($valores)[0], [ref]$s) -and $s -gt 0) { $espera = [Math]::Min($s, 600) }
        }
        throw [ErroDeCalma]::new("VPS pediu calma (429)", $espera)
    }
    if ($cod -ge 400 -and $cod -lt 500) { throw [ErroDefinitivo]::new("VPS recusou ($cod): $det") }
    throw "VPS respondeu $cod"
}

# 11. Ate 3 tentativas (30 s, 2 min, 5 min). Erro de acesso ou do proprio
# arquivo nao se repete: repetir nao muda a resposta.
function Com-Tentativas([scriptblock]$acao, [string]$nome) {
    for ($i = 0; ; $i++) {
        try { return & $acao }
        catch {
            $ex = $_.Exception
            while ($ex -is [System.Management.Automation.MethodInvocationException] -and $ex.InnerException) { $ex = $ex.InnerException }
            if ($ex -is [ErroDeAcesso] -or $ex -is [ErroDefinitivo]) { throw $ex }
            if ($i -ge $Esperas.Count) { throw $ex }
            # No 429 vale o que a VPS pediu (nao a escada de 30 s / 2 min / 5 min).
            $espera = if ($ex -is [ErroDeCalma]) { $ex.Espera } else { $Esperas[$i] }
            $msg = $ex.Message; if ($ex.InnerException) { $msg = $ex.InnerException.Message }
            Write-Host ('  {0}: {1} -- nova tentativa em {2} s' -f $nome, $msg, $espera) -ForegroundColor Yellow
            Start-Sleep -Seconds $espera
        }
    }
}

function Enviar-Ligacao($cliente, $cfg, $dados, $gravacao) {
    $json = $dados | ConvertTo-Json -Compress
    $segundos = 60
    if ($gravacao) { $segundos = 60 + [int][Math]::Ceiling($gravacao.Arquivo.Length / 1MB) * 10 }  # 13.
    return Com-Tentativas {
        $form = New-Object System.Net.Http.MultipartFormDataContent
        $form.Add((New-Object System.Net.Http.StringContent($json, [Text.Encoding]::UTF8)), 'dados')
        if ($gravacao) {
            $bytes = [IO.File]::ReadAllBytes($gravacao.Arquivo.FullName)
            $arq = New-Object System.Net.Http.ByteArrayContent(, $bytes)
            $arq.Headers.ContentType = [System.Net.Http.Headers.MediaTypeHeaderValue]::Parse('audio/mpeg')
            $form.Add($arq, 'arquivo', $gravacao.Arquivo.Name)
        }
        Post $cliente (Endereco $cfg 'enviar') $form $segundos
    } $(if ($gravacao) { $gravacao.Arquivo.Name } else { "ligacao $($dados.call_id)" })
}

function Batimento($cliente, $cfg, [int]$pendentes, [string]$erro, [string]$aviso, $ms) {
    # 🚨 v0.7: O BATIMENTO DEIXOU DE SER SO DE IDA.
    # Ida: passou a contar ONDE procura e COMO decidiu -- ate a v0.6 o aviso
    #      dizia "pasta nao existe" sem dizer qual pasta, e por isso ninguem
    #      via pelo painel que o caminho calculado estava errado.
    # Volta: a resposta traz `config.pastas`, e esta funcao GUARDA isso. Ate a
    #      v0.6 a resposta era descartada (`[void](Batimento ...)`) -- era o
    #      que tornava impossivel "atualizar do lado de ca o local de coleta".
    $corpo = @{ pc = $env:COMPUTERNAME; versao = $VERSAO; pendentes = $pendentes
                erro = $(if ($erro) { $erro.Substring(0, [Math]::Min(500, $erro.Length)) } else { $null })
                aviso = $(if ($aviso) { $aviso.Substring(0, [Math]::Min(500, $aviso.Length)) } else { $null })
                pasta = $(if ($ms -and $ms.Pasta) { $ms.Pasta } else { $null })
                pasta_origem = $(if ($ms -and $ms.Origem) { $ms.Origem } else { $null })
                auto_gravacao = $(if ($ms) { [bool]$ms.AutoGravacao } else { $null }) } | ConvertTo-Json -Compress
    $resposta = Com-Tentativas {
        $c = New-Object System.Net.Http.StringContent($corpo, [Text.Encoding]::UTF8, 'application/json')
        Post $cliente (Endereco $cfg 'batimento') $c 60
    } 'batimento'
    # ⚠️ A config so e gravada quando a VPS DIZ algo sobre pastas. Resposta de
    # servidor antigo (sem `config`) nao pode apagar o que ja estava.
    try {
        if ($resposta -and $resposta.config -and
                $null -ne $resposta.config.pastas) {
            Gravar-Config @{ pastas_da_vps = @($resposta.config.pastas) }
        }
    } catch { }
    return $resposta
}

function Dados-Da($l, $g) {
    $d = [ordered]@{
        call_id   = $l.CallId
        sentido   = $l.Sentido
        numero    = $l.Numero
        inicio    = ([DateTimeOffset]$l.Inicio).ToString('o')
        duracao_s = $l.Duracao
        situacao  = $l.Situacao
        pc        = $env:COMPUTERNAME
    }
    if ($g) { $d.gravacao_inicio = ([DateTimeOffset]$g.Inicio).ToString('o') }
    return $d
}

function Msg($ex) {
    while ($ex -is [System.Management.Automation.MethodInvocationException] -and $ex.InnerException) { $ex = $ex.InnerException }
    $m = $ex.Message
    if ($ex.InnerException) { $m = "$m ($($ex.InnerException.Message))" }
    return $m
}

function Executar-Envio {
    if (-not (Test-Path -LiteralPath $CONFIG)) { throw "Sem configuracao em $CONFIG (falta a chave do ramal)." }
    $cfg = Get-Content -LiteralPath $CONFIG -Raw -Encoding UTF8 | ConvertFrom-Json
    $cfg = Migrar-Chave-Para-DPAPI $cfg
    $cliente = $null
    $enviadas = 0; $ja = 0; $pulados = New-Object System.Collections.Generic.List[string]
    $erro = $null; $avisos = @(); $pendentes = 0
    # '?' e nao 0: se a leitura falhar antes de contar, zero seria mentira.
    $noHistorico = '?'; $naPasta = '?'
    try {
        $cliente = Novo-Cliente $cfg
        $ms = Ler-MicroSIP
        $avisos = @(Avisos $ms)
        $ligacoes = @(Ler-Historico $ms.Historico)
        $gravacoes = @(Ler-Gravacoes $ms.Pasta)
        # Contado AQUI: depois disto o laco acrescenta gravacao orfa a lista,
        # e "historico" passaria a significar outra coisa.
        $noHistorico = $ligacoes.Count
        $naPasta = $gravacoes.Count
        Casar $ligacoes $gravacoes
        $env_ = Ler-Enviados

        # ZERO AMBIGUO (15/10, pedido dele): "0 novas" dizia a mesma coisa
        # quando nao havia nada novo e quando a PASTA SUMIU. Se este PC ja
        # enviou gravacao antes e agora a pasta nao tem nenhuma, isso nao e
        # silencio: e pasta movida, renomeada no MicroSIP ou apagada.
        if ($naPasta -eq 0 -and $env_.gravacoes.Count -gt 0) {
            $avisos += ('pasta de gravacoes SEM ARQUIVOS mas este PC ja enviou {0}: movida ou apagada? ({1})' -f $env_.gravacoes.Count, $ms.Pasta)
        }

        # Gravacao sem ligacao no historico: sobe com os dados do nome do arquivo.
        foreach ($g in ($gravacoes | Where-Object { $_.Entende -and -not $_.Casada })) {
            $ligacoes += [pscustomobject]@{
                CallId = 'arquivo:' + $g.Arquivo.BaseName; Numero = $g.Numero; Nome = ''
                Sentido = $g.Sentido; Inicio = $g.Inicio; Duracao = 0; Situacao = 'sem registro no historico'
                Gravacao = [System.Collections.ArrayList]@($g)
            }
        }

        foreach ($l in $ligacoes) {
            if ($Limite -gt 0 -and $enviadas -ge $Limite) { break }
            $pendGrav = @($l.Gravacao | Where-Object { $_.Pronto })
            try {
                if ($pendGrav.Count -eq 0) {
                    if ($env_.ligacoes.ContainsKey($l.CallId)) { continue }
                    $r = Enviar-Ligacao $cliente $cfg (Dados-Da $l $null) $null
                    $env_.ligacoes[$l.CallId] = (Get-Date).ToString('o'); Gravar-Enviados $env_
                    if ($r.ligacao_nova) { $enviadas++ } else { $ja++ }
                    continue
                }
                foreach ($g in $pendGrav) {
                    if ($Limite -gt 0 -and $enviadas -ge $Limite) { break }
                    $hash = (Get-FileHash -LiteralPath $g.Arquivo.FullName -Algorithm SHA256).Hash.ToLower()
                    if ($env_.gravacoes.ContainsKey($hash)) { continue }
                    try {
                        $r = Enviar-Ligacao $cliente $cfg (Dados-Da $l $g) $g
                        # A PROVA E O HASH DEVOLVIDO, NAO O 200: so marca se bater.
                        if ($r.arquivo_sha256 -ne $hash) { throw [ErroDefinitivo]::new('hash diferente na VPS') }
                        $env_.gravacoes[$hash] = [pscustomobject]@{ arquivo = $g.Arquivo.Name; call_id = $l.CallId; em = (Get-Date).ToString('o') }
                        $env_.ligacoes[$l.CallId] = (Get-Date).ToString('o')
                        Gravar-Enviados $env_
                        if ($r.gravacao_nova) { $enviadas++ } else { $ja++ }
                        Write-Host ('  subiu {0}  (sha256 {1}... conferido)' -f $g.Arquivo.Name, $hash.Substring(0, 12)) -ForegroundColor Green
                    } catch {
                        $ex = $_.Exception
                        while ($ex -is [System.Management.Automation.MethodInvocationException] -and $ex.InnerException) { $ex = $ex.InnerException }
                        if ($ex -is [ErroDeAcesso]) { throw $ex }
                        # 12. Um arquivo com erro nao trava os outros.
                        $pulados.Add(('{0}: {1}' -f $g.Arquivo.Name, (Msg $ex)))
                        Write-Host "  pulou $($g.Arquivo.Name): $(Msg $ex)" -ForegroundColor Yellow
                    }
                }
            } catch {
                $ex = $_.Exception
                while ($ex -is [System.Management.Automation.MethodInvocationException] -and $ex.InnerException) { $ex = $ex.InnerException }
                if ($ex -is [ErroDeAcesso]) { throw $ex }
                $pulados.Add(('ligacao {0}: {1}' -f $l.CallId, (Msg $ex)))
            }
        }
        $pendentes = @($gravacoes | Where-Object {
            -not $env_.gravacoes.ContainsKey((Get-FileHash -LiteralPath $_.Arquivo.FullName -Algorithm SHA256).Hash.ToLower())
        }).Count
    } catch {
        $erro = Msg $_.Exception
        Write-Host "  erro: $erro" -ForegroundColor Red
    }

    if ($pulados.Count) {
        $resumo = "{0} pulado(s): {1}" -f $pulados.Count, $pulados[0]
        $erro = if ($erro) { "$erro | $resumo" } else { $resumo }
    }
    $aviso = ($avisos -join '; ')
    $bat = 'sem batimento (sem conexao configurada)'
    if ($cliente) {
        try { [void](Batimento $cliente $cfg $pendentes $erro $aviso $ms); $bat = 'batimento ok' }
        catch { $bat = 'batimento FALHOU: ' + (Msg $_.Exception) }
    }
    # 0.6: a limpeza vem DEPOIS do envio e do batimento, nesta ordem de
    # proposito -- o que acabou de subir nesta passada ja esta confirmado, e o
    # que falhou nao entrou no enviados.json e por isso nao sera apagado.
    $limpeza = ''
    if (-not $NaoApagar) {
        try {
            $lp = Limpar-Antigas $ms.Pasta $Dias
            if ($lp.Motivo) { $limpeza = ' | limpeza: ' + $lp.Motivo }
            elseif ($lp.Apagadas) { $limpeza = ' | limpeza: {0} apagada(s) de mais de {1} dias ({2})' -f $lp.Apagadas, $Dias, (Tamanho $lp.Bytes) }
        } catch {
            $limpeza = ' | limpeza FALHOU: ' + (Msg $_.Exception)
        }
    }
    # O QUE HAVIA entra no log junto com o que subiu: sem isso, "0 novas"
    # servia tanto para "nada novo" quanto para "pasta vazia", e so dava para
    # distinguir rodando a simulacao a mao.
    $msg = 'v{0} envio: {1} novas, {2} ja estavam na VPS, {3} gravacoes pendentes | historico {4}, pasta {5} | {6}{7}{8}{9}' -f $VERSAO, $enviadas, $ja, $pendentes, $noHistorico, $naPasta, $bat,
        $(if ($erro) { " | erro: $erro" } else { '' }), $(if ($aviso) { " | aviso: $aviso" } else { '' }), $limpeza
    Registrar-Log $msg
    Write-Host $msg -ForegroundColor $(if ($erro) { 'Yellow' } else { 'Cyan' })
    if ($erro -or $bat -ne 'batimento ok') { return 1 }
    return 0
}

# --------------------------------------------------------------- limpeza local
# 0.6 (19/10). Decisao dele: "7 dias ja pode apagar" -- a gravacao vive na VPS
# (com backup noturno) e nao precisa ocupar o disco de quem atende.
#
# SO APAGA O QUE A VPS CONFIRMOU. A confirmacao nao e o 200 do envio: e o
# sha256 que a VPS DEVOLVEU batendo com o do arquivo, que e o unico momento em
# que o hash entra no enviados.json (ver Executar-Envio). Arquivo que nunca
# subiu, ou que subiu com hash diferente, NAO esta la e por isso fica.
#
# NAO ENCOSTA NO HISTORICO (call_log.db): o que se apaga aqui e audio, e o
# MicroSIP continua mostrando a ligacao na tela dele.
#
# Sem enviados.json -- PC reinstalado, config perdido --, a funcao sai sem
# apagar: "nao sei o que subiu" nao pode virar "apago tudo".
function Limpar-Antigas($pasta, $dias, [switch]$SoContar) {
    $resultado = [pscustomobject]@{ Apagadas = 0; Bytes = 0; Candidatas = 0; Motivo = '' }
    if ($dias -le 0) { $resultado.Motivo = 'desligada'; return $resultado }
    if (-not (Test-Path -LiteralPath $pasta)) { $resultado.Motivo = 'pasta nao existe'; return $resultado }
    $env_ = Ler-Enviados
    if (-not $env_.gravacoes -or $env_.gravacoes.Count -eq 0) {
        $resultado.Motivo = 'sem confirmacao da VPS (enviados.json vazio): nada apagado'
        return $resultado
    }
    $limite = (Get-Date).AddDays(-$dias)
    foreach ($f in Get-ChildItem -LiteralPath $pasta -Filter *.mp3 -File) {
        if ($f.LastWriteTime -gt $limite) { continue }
        $hash = (Get-FileHash -LiteralPath $f.FullName -Algorithm SHA256).Hash.ToLower()
        if (-not $env_.gravacoes.ContainsKey($hash)) { continue }
        $resultado.Candidatas++
        $resultado.Bytes += $f.Length
        if ($SoContar) { continue }
        try {
            Remove-Item -LiteralPath $f.FullName -Force
            $resultado.Apagadas++
            # Cada arquivo apagado deixa rastro com o hash: e por ele que se
            # prova, depois, que a copia da VPS e a mesma que saiu daqui.
            Registrar-Log ('v{0} apagou local {1} ({2} bytes, sha256 {3})' -f $VERSAO, $f.Name, $f.Length, $hash)
        } catch {
            Registrar-Log ('v{0} NAO conseguiu apagar {1}: {2}' -f $VERSAO, $f.Name, (Msg $_.Exception))
        }
    }
    return $resultado
}

# --------------------------------------------------------------- exportacao
# BLOCO 9 (15/10): o PC que ainda NAO tem agente tambem tem historico, e esse
# historico e trabalho perdido se so quem esta alistado consegue mandar.
# -Exportar le o MicroSIP exatamente como o envio leria, e grava um PACOTE
# (um .zip) para a pessoa mandar para ele por qualquer caminho.
#
# NAO PRECISA DE CHAVE, NAO PRECISA DE CONFIG, NAO FALA COM A VPS. E so leitura
# -- por isso roda em PC sem alistamento, que e o caso todo deste bloco.
#
# O PACOTE TEM A MESMA FORMA DO ENVIO, de proposito: as mesmas chaves
# (call_id, sentido, numero, inicio, duracao_s, situacao) e o mesmo truque de
# 'arquivo:<nome>' para gravacao sem registro no historico. Assim o import na
# VPS entra pelo MESMO caminho de gravacao, com a MESMA idempotencia, e nao
# existe um segundo jeito de uma ligacao nascer no banco.
function Executar-Exportacao {
    $ms = Ler-MicroSIP
    $ligacoes = @(Ler-Historico $ms.Historico)
    $gravacoes = @(Ler-Gravacoes $ms.Pasta)
    Casar $ligacoes $gravacoes

    # Gravacao sem par no historico sobe pelos dados do nome do arquivo --
    # igualzinho ao envio. Nome fora do padrao fica de fora e e CONTADO: o
    # pacote diz o que deixou para tras, nunca silencia.
    foreach ($g in ($gravacoes | Where-Object { $_.Entende -and -not $_.Casada })) {
        $ligacoes += [pscustomobject]@{
            CallId = 'arquivo:' + $g.Arquivo.BaseName; Numero = $g.Numero; Nome = ''
            Sentido = $g.Sentido; Inicio = $g.Inicio; Duracao = 0
            Situacao = 'sem registro no historico'
            Gravacao = [System.Collections.ArrayList]@($g)
        }
    }
    $foraDoPadrao = @($gravacoes | Where-Object { -not $_.Entende })

    $pasta = Join-Path ([IO.Path]::GetTempPath()) ("movizap-export-{0}" -f ([guid]::NewGuid().ToString('N')))
    $pastaGrav = Join-Path $pasta 'gravacoes'
    [void](New-Item -ItemType Directory -Path $pastaGrav -Force)
    try {
        $itens = New-Object System.Collections.Generic.List[object]
        $usados = @{}
        $bytes = 0
        foreach ($l in $ligacoes) {
            $gs = New-Object System.Collections.Generic.List[object]
            foreach ($g in $l.Gravacao) {
                # EM USO NAO VAI: arquivo que o MicroSIP ainda escreve entraria
                # cortado, e o hash dele mudaria depois -- a idempotencia da VPS
                # e por hash, entao o pedaco cortado viraria uma gravacao extra
                # para sempre.
                if (-not $g.Pronto) { continue }
                $hash = (Get-FileHash -LiteralPath $g.Arquivo.FullName -Algorithm SHA256).Hash.ToLower()
                $nome = $g.Arquivo.Name
                if ($usados.ContainsKey($nome)) { $nome = $hash.Substring(0, 8) + '-' + $nome }
                $usados[$nome] = $true
                Copy-Item -LiteralPath $g.Arquivo.FullName -Destination (Join-Path $pastaGrav $nome)
                $bytes += $g.Arquivo.Length
                $gs.Add([ordered]@{
                    arquivo       = $nome
                    nome_original = $g.Arquivo.Name
                    sha256        = $hash
                    bytes         = $g.Arquivo.Length
                    inicio        = ([DateTimeOffset]$g.Inicio).ToString('o')
                })
            }
            $itens.Add([ordered]@{
                call_id   = $l.CallId
                sentido   = $l.Sentido
                numero    = $l.Numero
                inicio    = ([DateTimeOffset]$l.Inicio).ToString('o')
                duracao_s = $l.Duracao
                situacao  = $l.Situacao
                gravacoes = $gs.ToArray()
            })
        }

        $pacote = [ordered]@{
            pacote      = 'movizap-ligacoes'
            versao      = 1
            agente      = $VERSAO
            pc          = $env:COMPUTERNAME
            usuario     = $env:USERNAME
            ramal       = $ms.Ramal
            gerado_em   = (Get-Date).ToString('o')
            microsip    = [ordered]@{ ini = $ms.Ini; pasta = $ms.Pasta; versao = $ms.VersaoSip }
            # O que ficou de fora, por escrito dentro do proprio pacote: quem
            # importa tem de poder conferir a conta sem voltar neste PC.
            fora_do_padrao = @($foraDoPadrao | ForEach-Object { $_.Arquivo.Name })
            em_uso_agora   = @($gravacoes | Where-Object { $_.Entende -and -not $_.Pronto } | ForEach-Object { $_.Arquivo.Name })
            ligacoes    = $itens.ToArray()
        }
        $json = $pacote | ConvertTo-Json -Depth 8
        [IO.File]::WriteAllText((Join-Path $pasta 'pacote.json'), $json, (New-Object Text.UTF8Encoding($false)))

        $destino = if ($Destino) { $Destino } else { [Environment]::GetFolderPath('Desktop') }
        if (-not (Test-Path -LiteralPath $destino)) { [void](New-Item -ItemType Directory -Path $destino -Force) }
        $zip = Join-Path $destino ('MoviZap-Ligacoes-{0}-ramal{1}-{2:yyyyMMdd-HHmmss}.zip' -f $env:COMPUTERNAME, $ms.Ramal, (Get-Date))
        if (Test-Path -LiteralPath $zip) { Remove-Item -LiteralPath $zip -Force }
        Compress-Archive -Path (Join-Path $pasta '*') -DestinationPath $zip
        $tam = (Get-Item -LiteralPath $zip).Length

        Write-Host ''
        Write-Host 'MoviZap - Ligacoes  |  PACOTE PARA IMPORTAR' -ForegroundColor Cyan
        Write-Host 'Nada foi enviado, nada foi apagado. So leitura.' -ForegroundColor Cyan
        Write-Host ''
        Write-Host ("PC ............ {0}" -f $env:COMPUTERNAME)
        Write-Host ("Ramal ......... {0}" -f $ms.Ramal)
        Write-Host ("Ligacoes ...... {0}" -f $itens.Count)
        Write-Host ("Gravacoes ..... {0}  ({1})" -f $usados.Count, (Tamanho $bytes))
        if ($foraDoPadrao.Count) {
            Write-Host ("Fora do padrao  {0} arquivo(s) NAO entraram (nome fora do padrao do MicroSIP)" -f $foraDoPadrao.Count) -ForegroundColor Yellow
        }
        $emUso = @($gravacoes | Where-Object { $_.Entende -and -not $_.Pronto })
        if ($emUso.Count) {
            Write-Host ("Em uso agora .. {0} arquivo(s) ficaram de fora (ligacao em andamento)" -f $emUso.Count) -ForegroundColor Yellow
        }
        Write-Host ''
        Write-Host ("Pacote: {0}  ({1})" -f $zip, (Tamanho $tam)) -ForegroundColor Green
        Write-Host 'Mande este arquivo para o Iago. Ele importa na VPS.' -ForegroundColor Green
        Registrar-Log ('v{0} exportacao: {1} ligacoes, {2} gravacoes, {3} -> {4}' -f $VERSAO, $itens.Count, $usados.Count, (Tamanho $bytes), $zip)
        return 0
    } finally {
        Remove-Item -LiteralPath $pasta -Recurse -Force -ErrorAction SilentlyContinue
    }
}

# --------------------------------------------------------------- execucao
if ($Exportar) {
    try { $codigo = Executar-Exportacao | Select-Object -Last 1 }
    catch {
        Write-Host ("ERRO ao exportar: {0}" -f (Msg $_.Exception)) -ForegroundColor Red
        exit 1
    }
    exit $codigo
}
if (-not $Simular -and -not $Enviar) { $Simular = $true }
if ($Enviar) {
    if (-not (Pegar-Trava)) {
        Registrar-Log "v$VERSAO outra execucao em andamento: esta saiu sem fazer nada"
        Write-Host 'Outra execucao do agente esta em andamento. Saindo.' -ForegroundColor Yellow
        exit 0
    }
    try { $codigo = Executar-Envio | Select-Object -Last 1 } finally { Soltar-Trava }
    exit $codigo
}

$saida = New-Object System.Collections.Generic.List[string]
function Diga([string]$texto, [string]$cor = 'Gray') { Write-Host $texto -ForegroundColor $cor; $saida.Add($texto) }

Diga ("MoviZap - Ligacoes  |  SIMULACAO  |  agente {0}  |  {1:dd/MM/yyyy HH:mm}" -f $VERSAO, (Get-Date)) 'Cyan'
Diga 'Nada e enviado, nada e apagado. So leitura -- a limpeza aqui so conta.' 'Cyan'
Diga ''

try { $ms = Ler-MicroSIP } catch {
    Diga ("ERRO: {0}" -f $_.Exception.Message) 'Red'
    Diga 'Nada subiria. O batimento levaria este erro, e ele vira alerta.' 'Red'
    $saida | Set-Content -LiteralPath $RELATORIO -Encoding UTF8
    exit 1
}
Diga ("PC ............ {0}" -f $env:COMPUTERNAME)
Diga ("MicroSIP ...... {0}  (ini: {1})" -f $(if ($ms.VersaoSip) { $ms.VersaoSip } else { '?' }), $ms.Ini)
Diga ("Ramal ......... {0}  (rotulo: {1})" -f $ms.Ramal, $ms.Rotulo)
if ($ms.Exibicao -and $ms.Rotulo -and ($ms.Exibicao -ne $ms.Rotulo)) {
    Diga ("  aviso: o nome que o outro lado ve e '{0}', diferente do rotulo '{1}'" -f $ms.Exibicao, $ms.Rotulo) 'Yellow'
}
Diga ("Central ....... {0}" -f $ms.Servidor)
Diga ("Gravacoes em .. {0}" -f $ms.Pasta)
Diga ("  de onde ..... {0}" -f $ms.Origem)
Diga ("Gravacao auto . {0}" -f $(if ($ms.AutoGravacao) { 'ligada' } else { 'DESLIGADA' }))
foreach ($a in (Avisos $ms)) { Diga ("  AVISO: {0}" -f $a) 'Yellow' }
if (Test-Path -LiteralPath $CONFIG) {
    $cfg = Get-Content -LiteralPath $CONFIG -Raw -Encoding UTF8 | ConvertFrom-Json
    Diga ("Destino ....... {0}" -f (Endereco $cfg '...'))
    if ($cfg.cert) {
        try { $c = Certificado-Do-PC $cfg; Diga ("Certificado ... {0}... vale ate {1:dd/MM/yyyy}" -f $c.Thumbprint.Substring(0, 8), $c.NotAfter) }
        catch { Diga ("Certificado ... ERRO: {0}" -f $_.Exception.Message) 'Red' }
    } else { Diga 'Certificado ... nenhum (usa a rota antiga do painel)' }
}
Diga ''

$ligacoes = @(Ler-Historico $ms.Historico)
$gravacoes = @(Ler-Gravacoes $ms.Pasta)
Casar $ligacoes $gravacoes

Diga ("Historico do MicroSIP: {0} ligacoes | Gravacoes na pasta: {1}" -f $ligacoes.Count, $gravacoes.Count) 'White'

# 0.6: a simulacao DIZ o que a limpeza faria, e nao apaga nada (o `-SoContar`
# e a garantia). Sem esta linha, a limpeza seria uma surpresa na primeira
# passada real do dia seguinte.
$lpSim = Limpar-Antigas $ms.Pasta $Dias -SoContar
if ($lpSim.Motivo) {
    Diga ("Limpeza local: {0}" -f $lpSim.Motivo)
} else {
    Diga ("Limpeza local: {0} gravacao(oes) com mais de {1} dias JA confirmada(s) na VPS -- o envio apagaria ({2})" -f $lpSim.Candidatas, $Dias, (Tamanho $lpSim.Bytes))
}
Diga ''
Diga 'Quando              Sentido   Numero            Duracao  Gravacao'
Diga '------------------  --------  ----------------  -------  -----------------------------------'
$totalBytes = 0; $comGravacao = 0
$arquivosCasados = 0
foreach ($l in $ligacoes) {
    $linhas = @()
    foreach ($g in $l.Gravacao) {
        $f = $g.Arquivo
        $hash = (Get-FileHash -LiteralPath $f.FullName -Algorithm SHA256).Hash.ToLower()
        $linhas += '{0}  {1}  sha256 {2}...' -f (Tamanho $f.Length), ($(if ($g.Pronto) { 'pronta' } else { 'EM USO' })), $hash.Substring(0, 12)
        $totalBytes += $f.Length; $arquivosCasados++
    }
    if ($l.Gravacao.Count) { $comGravacao++ }
    $primeira = if ($linhas.Count) { $linhas[0] } else { '(sem gravacao)' }
    Diga ('{0:dd/MM/yyyy HH:mm:ss}  {1,-8}  {2,-16}  {3,7}  {4}' -f $l.Inicio, $l.Sentido, $l.Numero, (Duracao $l.Duracao), $primeira)
    foreach ($extra in ($linhas | Select-Object -Skip 1)) {
        Diga ('{0,57}  + {1}  (a gravacao recomecou nesta ligacao)' -f '', $extra)
    }
}

$soltas = @($gravacoes | Where-Object { -not $_.Casada })
if ($soltas.Count) {
    Diga ''
    Diga ("Gravacoes SEM ligacao no historico: {0} (subiriam assim mesmo, pelos dados do nome do arquivo)" -f $soltas.Count) 'Yellow'
    foreach ($g in $soltas) {
        $motivo = if ($g.Entende) { 'nome entendido, sem par no historico' } else { 'nome fora do padrao: NAO sobe' }
        Diga ('  {0}  ({1}, {2})' -f $g.Arquivo.Name, (Tamanho $g.Arquivo.Length), $motivo) 'Yellow'
        if ($g.Entende) { $totalBytes += $g.Arquivo.Length }
    }
}

Diga ''
Diga 'RESUMO' 'White'
Diga ("  Ligacoes que subiriam ......... {0}  (das quais {1} com gravacao)" -f $ligacoes.Count, $comGravacao)
Diga ("  Gravacoes que subiriam ........ {0}" -f ($arquivosCasados + @($soltas | Where-Object Entende).Count))
Diga ("  Volume ........................ {0}" -f (Tamanho $totalBytes))
Diga ("  Por sentido ................... " + (($ligacoes | Group-Object Sentido | ForEach-Object { "$($_.Name): $($_.Count)" }) -join ' | '))
$emUso = @($gravacoes | Where-Object { -not $_.Pronto }).Count
if ($emUso) { Diga ("  Em uso agora (ficariam para a proxima passada): {0}" -f $emUso) 'Yellow' }
Diga ''
Diga ("Relatorio salvo em: {0}" -f $RELATORIO) 'Cyan'

$saida | Set-Content -LiteralPath $RELATORIO -Encoding UTF8
