# Ligações do MicroSIP — como os dados entram e onde ficam

Planos 5 e 5.1 (25/09/2026). 🔵 *"inicialmente o backup das ligações na VPS
de uma forma bem inteligente -- depois ter uma rotina com histórico de chamadas
na ficha da pessoa do chat"* e *"talvez diretório documentado de como os dados
entram e ordenamos ele para consulta rápida"*.

O procedimento para instalar em cada operador está no kit `Desktop\MoviZap-Ligacoes-Kit\MANUAL.md`
do PC do Iago. Desde **15/10 (v0.4) são 2 passos e um arquivo só**: a pessoa
abre `MoviZap-Instalar-Ligacoes.exe` e digita a senha de uso único que ele
dita (`Senha de alistamento.cmd` → `scripts/senha_alistamento.py`). A
conferência continua em `Conferir agentes.cmd` → `scripts/agentes_ligacao.py`.
As ferramentas `Preparar operador` e `Assinar pedido` foram aposentadas
(`fontes/aposentado-v03/` no kit): a chave e o certificado passaram a nascer no
PC da pessoa, no alistamento.

## O caminho

```
PC do operador
  MicroSIP ─ grava MP3 em recordingPath (MicroSIP.ini) + histórico em call_log.db
  Tarefa "MoviZap Ligacoes" (12:00, 17:30, ao entrar +5 min, usuário da pessoa)
  └─ MoviZap-Backup-de-Ligacoes.exe → movizap-ligacoes.ps1 (v0.4)
        lê o ini ─ lê o call_log.db (cópia, só leitura) ─ casa gravação × ligação
        HTTPS + CERTIFICADO DO PC + X-Agente-Chave
          │
nginx ligacoesmicrosip.movisat.com.br  (ssl_verify_client on; só /agente/;
          │                              cota lig_agente 120/min; 30 MB; log próprio)
          │  repassa o certificado em X-Cliente-Cert
127.0.0.1:8010  movizap.app_ligacoes   (serviço --user movizap-ligacoes)
          │  confere chave + certificado DO MESMO agente
          ├─ agente_ligacao   (batimento: último contato, IP, versão, erro, aviso)
          ├─ ligacao          (uma por (ramal, call_id); telefone_e164 padronizado)
          └─ ligacao_gravacao (uma por SHA-256) ─ disco:
                /home/claude/movizap_ligacoes/AAAA/MM/<sha256>.mp3  (0640, gravação atômica)
```

A rota antiga de ENVIO (`movizap.movisat.com.br/api/ligacoes/agente/{batimento,enviar}`,
no processo do painel) vale só até cada PC se alistar. Ela sai junto do
reinício do Plano 4 -- mas **`/api/ligacoes/agente/alistar` fica**, e fica no
painel de propósito (ver abaixo).

## Garantias

- **Idempotente pelo banco:** reenviar não duplica nada (`UNIQUE (ramal, call_id)`
  e hash único). A resposta devolve o hash **do que está no disco**, e o agente
  só marca como salvo quando o hash bate.
- **Nada é apagado do PC** nesta fase ("7 dias já pode apagar" fica para depois,
  com a palavra dele).
- **O log diz QUANTO HAVIA, não só quanto subiu** (15/10). 🔵 *"o resultado do
  script foi zero por ja não ter novos ou nenhum na pasta? importante deixar no
  log a diferença para evitar falso positivo ou pasta movida ou apagada"*. A
  linha virou `... 0 novas, 0 ja estavam na VPS, 0 gravacoes pendentes |
  historico 28, pasta 19 | batimento ok`:
  - `pasta 19` com `0 novas` é silêncio legítimo;
  - `pasta 0` **depois de o PC já ter enviado gravação** não é silêncio, e sai
    com aviso que nomeia o caminho onde ele procurou: *"pasta de gravacoes SEM
    ARQUIVOS mas este PC ja enviou 19: movida ou apagada?"*. O aviso vai no
    batimento, então o vigia da VPS avisa sozinho;
  - se a leitura falhar antes de contar, aparece `historico ?, pasta ?` --
    zero que não foi medido é mentira.
- **Queda e atraso:** até 3 tentativas (30 s, 2 min, 5 min); o 429 espera o
  `Retry-After`; arquivo recusado é pulado sem travar os outros; o tempo
  limite é de 60 s + 10 s por MB; uma execução por vez (`agente.lock`).
- **Alerta:** `scripts/agentes_mudos.py` fica mudo quando está tudo em dia e
  acusa: PC sem contato há mais de 24 h, PC vivo com erro ou aviso, e
  certificado vencendo em menos de 30 dias. **Dois gatilhos** (desde 15/10): o
  gancho `SessionStart` do Claude Code, que imprime na sessão, e o **cron da
  VPS às 08:10 e 18:10** com `--avisar-whatsapp`, que manda uma mensagem.
  Detalhe na seção "O vigia".

## Chaves e certificados

| O quê | Onde | Segredo? |
|---|---|---|
| chave do agente (`mzl_…`) | `config.json` no PC; no banco só o SHA-256 | sim |
| chave privada do PC | cofre do Windows do usuário, não exportável | sim, nunca sai do PC |
| pedido `.req` / certificado `.cer` | trafegam entre PC e VPS | não |
| chave da CA | `/home/claude/movizap_ligacoes_ca/ca.key` (0600, **fora do backup**) | sim |
| certificado público da CA | `ca.crt` e `/etc/nginx/movizap_ligacoes_ca.crt` | não |

- Emitir: `scripts/chave_agente_ligacao.py` (chave), depois
  `scripts/cert_agente_ligacao.py --ramal --pedido --saida` (certificado). O
  certificado novo substitui o anterior.
- **Revogar um PC:** `UPDATE agente_ligacao SET revogado_em = now() WHERE id = …`.
  Não precisa de root nem de recarregar o nginx.
- **CA perdida:** criar outra e emitir certificado novo para cada PC. Nenhuma
  ligação se perde.

## A camada de consulta (Bloco 3, 15/10/2026)

🔵 *"um grid simples que tenha as ligações do historico do MicroSip,
consultadas por cliente - ja da base Movizap, ou por Atendente, ou por data ou
por numero, etc"* e, na conversa, *"o modal só trará ultimos 7 dias"*.

Até 15/10 o módulo só escrevia: nenhuma rota de leitura, nenhuma tela, nenhum
player. Agora:

| Onde | O quê |
|---|---|
| `movizap/ligacoes_consulta.py` | `consultar` (o grid, com filtros e paginação), `para_csv`, `do_telefone` (o modal da ficha), `gravacao`, `agentes` (a cobertura) |
| `movizap/relatorio_csv.py` | o primeiro CSV do projeto: `;`, BOM e CRLF, com fórmula neutralizada |
| `GET /api/conversas/{id}/ligacoes?dias=7` | **`ATD_1.2`** — o que o modal do botão Ligações usa |

**Módulo separado de propósito:** `ligacoes.py` é o caminho de escrita do
agente, no ar desde 25/09, e não se mexe nele para acrescentar leitura — mesma
divisão de `ligacoes_ca.py` e `ligacoes_alistar.py`.

**Índices** (migração 063): `(inicio DESC)`, `(atendente_id, inicio DESC)`,
`(ramal, inicio DESC)` e a FK `(agente_id)`. O de `(telefone_e164, inicio DESC)`
já vinha da 059 e é o que serve o modal. Nasceram **junto** das consultas que
os usam — índice sem consulta é palpite. ⚠️ A visão `ligacao_resumo` que eu
havia previsto **não foi feita**: as subconsultas de gravações e de clientes
resolvem, e uma visão a mais seria lugar a mais para a verdade divergir.

### Três coisas que a consulta tem de acertar, e que viraram teste

1. **Uma ligação pode ter DUAS gravações** (o MicroSIP reinicia o arquivo no
   meio da chamada e o agente manda os dois pedaços). Com `JOIN` isso viraria
   duas linhas no grid; por isso as gravações vêm por **subconsulta
   agregada**, como lista.
2. **Um número pode cair em VÁRIAS empresas** — é o "empresas do mesmo
   responsável" que a ficha já mostra. `clientes` é lista, e uma ligação de
   duas gravações em duas empresas continua **uma** linha.
3. **A maioria das ligações não tem cadastro nenhum** (`08000028000`,
   `1925172200`, o ramal interno `3407` estão no histórico real). Lista vazia
   significa "sem cadastro", e a tela tem de distinguir isso de "não
   consultei".

Mais duas, que também viraram teste: os **totais são do filtro inteiro**, não
da página (rodapé que conta a página mente a cada virada), e a busca por
**pedaço** de número funciona (`"9811"`), comparando só dígitos dos dois lados.

**`cobertura` vai junto no modal** (quantos ramais têm agente, de quantos
atendentes ativos): sem isso a tela afirma "nenhuma ligação" onde a verdade é
"aquele PC não tem agente".

### Provado em 15/10

| O quê | Resultado |
|---|---|
| `tests/teste_ligacoes_consulta.py` | **22 verdes** (17 da consulta + 5 da rota, com `TestClient`) |
| Contra a base real | 28 ligações, 19 gravações, `{feita: 19, recebida: 4, perdida: 5}` — igual à simulação do agente no mesmo dia |
| Cobertura | 1 ramal com agente, 9 atendentes ativos |
| Rota da ficha, no ar | 401 sem token; 200 com token, 7 dias por padrão; grupo (sem número) responde vazio em vez de explodir; conversa inexistente dá 404 |
| Resíduo de teste | zero (atendente, cliente, contato, conversa e grupo de teste apagados) |

## Alistamento por senha (v0.4, 15/10/2026)

🔵 *"o .exe deve rodar livre assim, porém validar o atendente do MicroSip com
uma senha que será gerada sempre via algoritmo e é mutável para rodar"*,
*"se trocarem de PC é só executar novamente e me pedir a senha de uso"*,
*"o .exe se deleta automaticamente após ser concluído"* e *"eu apagaria do PC
para evitar engenharia reversa e senha do banco"*.

```
PC da pessoa                                        VPS
  MoviZap-Instalar-Ligacoes.exe
    extrai a carga num temporário
    lê o ramal do MicroSIP.ini
    certreq -new -user  (chave NÃO exportável, nasce aqui)
    POST /api/ligacoes/agente/alistar  ──────────►  ligacoes_alistar.alistar()
      { ramal, senha, pedido (CSR), pc }              confere a senha (HMAC)
                                                      queima a janela (UNIQUE)
                                                      revoga o agente anterior
                                                      gera a chave nova
                                                      assina o certificado
    ◄──────────────────────────  { chave, cert_pem, cert_validade, pc_anterior }
    certutil -repairstore  (liga o cert à chave)
    config.json: chave CIFRADA com DPAPI do usuário
    tarefa "MoviZap - Backup de Ligações"
    Aplicativos instalados + atalho "ver situação"
    apaga o instalador (só em caso de sucesso)
```

**Por que o alistamento entra pelo PAINEL e não pela porta 8010:** o nginx de
`ligacoesmicrosip` exige certificado de cliente, e um PC que está se alistando
ainda **não tem** certificado -- não conseguiria abrir a conexão. Pôr o
alistamento no painel também manteve a promessa do kit: nenhum passo precisa de
root nem toca o nginx.

**A senha** (`movizap/ligacoes_alistar.py`): HMAC-SHA256 de
`MOVIZAP_LIGACOES_SENHA_SEGREDO` (segredo PRÓPRIO, nunca o `jwt_secret`) sobre
`(ramal, janela de 10 min)`, 8 caracteres de um alfabeto sem `I`, `O`, `0` e
`1` -- ela é ditada em voz alta. Duas janelas são aceitas (tolerância de
relógio), então no pior caso vale 20 minutos.

- 🚨 **Não é guardada em lugar nenhum.** É derivada a cada chamada. O que o
  banco guarda é a janela GASTA, em `alistamento_queimado`, com
  `UNIQUE (ramal, janela)` -- é essa constraint que faz a senha servir uma vez.
- 🚨 **O algoritmo vive só na VPS.** O `.exe` manda o que foi digitado e a VPS
  responde sim ou não. Se a derivação rodasse no PC, quem abrisse o executável
  passaria a **fabricar** senhas; como está, decompilá-lo entrega a URL pública
  e nada mais.
- 🚨 **A senha só alista.** Batimento e envio seguem com chave + certificado.
  Se cada execução pedisse senha, a tarefa das 12:00 e 17:30 pararia de
  funcionar -- não há ninguém na frente do PC para digitar.
- Senha errada e ramal sem dono dão **a mesma** resposta: dizer qual é o caso
  entregaria a lista de ramais válidos a quem está adivinhando.
- Tentativa errada cai no `movizap/ratelimit.py`, o mesmo do login (5 falhas em
  5 min, contador em SQLite, chave `ip|alistar:<ramal>` para o erro de um PC
  não trancar o ramal de outro).

**Troca de PC** (decisão dele, 15/10): o alistamento novo **revoga o anterior**
automaticamente -- quem alista de novo está trocando de PC, e dois PCs no mesmo
ramal mandariam em dobro. Quem revoga é `ligacoes.gerar_chave`, que já era
assim. A resposta devolve `pc_anterior`, e o instalador avisa na tela que aquele
PC parou de enviar. Nada se perde: o que já subiu está na VPS, e o PC novo
reenvia o que vê sem duplicar (`UNIQUE (ramal, call_id)` + hash do arquivo).

**A chave no PC** fica cifrada pelo **DPAPI do usuário** (decisão dele, 15/10):
o `config.json` copiado para outra máquina ou outro usuário não se abre. Não
protege contra quem está logado como a pessoa -- nada no PC protegeria --, e
protege contra o caso real: cópia do arquivo. Config da v0.3 (chave em texto
puro) é migrado na primeira passada da v0.4, sem reinstalar nada.

**Os dois executáveis** são compilados pelo `csc.exe` que já vem no Windows
(`fontes/Compilar.cmd`): sem ps2exe, sem instalar nada, sem admin.
`MoviZap-Instalar-Ligacoes.exe` carrega dentro de si o agente, o instalador, o
desinstalador, o LEIA-ME e o lançador, e se apaga no fim.
`MoviZap-Backup-de-Ligacoes.exe` fica instalado e é o que a tarefa executa --
é ele que faz o Gerenciador de Tarefas mostrar **"MoviZap - Backup de
Ligações"** em vez de `powershell.exe`, que era o que as pessoas encerravam.

### Provado em 15/10, no PC dele

| O quê | Resultado |
|---|---|
| Senha derivada | determinística, muda por ramal e por janela, sem `I/O/0/1` |
| Alistamento pela rota HTTP | 200, chave + certificado conferem juntos |
| Mesma senha de novo | 401 "Essa senha já foi usada" |
| Senha errada / ramal sem dono | mesma mensagem, janela não queimada |
| 5 erros seguidos | trava só aquele IP; outro IP alista normalmente |
| Alistamento real do ramal 3404 | agente 17 revogado, agente 431 vivo, cert até 14/10/2028 |
| Tarefa renomeada | `MoviZap Ligacoes` saiu, `MoviZap - Backup de Ligações` roda (resultado 0) |
| DPAPI | `config.json` sem `chave`, só `chave_protegida`; batimento ok pela porta com mTLS |
| Base intacta | 28 ligações e 19 gravações antes e depois |

### Armadilhas do PowerShell medidas neste dia

- `Get-Content -Raw` devolve a string **decorada** (`PSPath`, `PSProvider`...);
  o `ConvertTo-Json` serializa o objeto inteiro e o CSR chega como objeto →
  **422**. Usar `[IO.File]::ReadAllText`.
- No PowerShell 5.1 o corpo da resposta de erro **já foi consumido** pelo
  `Invoke-RestMethod`: `GetResponseStream()` volta vazio e a pessoa veria
  "Nao consegui falar com a VPS (401)" em vez de "Senha inválida ou vencida".
  O corpo vive em `$_.ErrorDetails.Message`.
- Executável que **espera** o PowerShell não consegue se apagar (fica em uso):
  o instalador dispara o PowerShell e sai de cena, e o `del` tenta 30 vezes.

## O vigia (Bloco 2, 15/10/2026)

🔵 *"Rotina da VPS verifica se os envios estão sendo feito corretamente e mesmo
que não tenha arquivos novos para enviar, um ping no servidor valida o usuario
e a conexão"*.

O ping já existia e não mudou: é o `batimento`, que o agente dá a cada passada
mesmo sem nada para enviar. O que faltava era **alguém olhando** — até 15/10 o
único gatilho do `agentes_mudos.py` era o `SessionStart` da sessão do Claude,
ou seja: se eu não abrisse sessão, ninguém era avisado. Com um PC isso passava;
com oito, não.

```
cron da VPS (claude), 08:10 e 18:10
  └─ scripts/agentes_mudos.py --avisar-whatsapp
        PC sem contato há mais de 24 h  (agentes_mudos)
        PC vivo com erro ou aviso       (agentes_com_aviso)
        certificado vencendo em 30 dias (certs_vencendo)
        │
        ├─ imprime (vai para o log /home/claude/logs/movizap_ligacoes_vigia.log)
        └─ UMA mensagem para MOVIZAP_LIGACOES_AVISO_NUMERO, pelo Evolution
```

- **Horário:** 08:10 e 18:10, depois das passadas dos PCs (logon+5min de manhã
  e 17:30), para não acusar quem ainda ia falar.
- 🚨 **Fala direto com o Evolution**, não pela rota do painel: o vigia tem de
  funcionar inclusive com o painel fora do ar — que é justamente um dos motivos
  de um PC parecer mudo.
- 🚨 **Mudo quando está tudo em dia:** nenhuma linha impressa, nenhuma mensagem
  enviada, log vazio. Aviso que chega todo dia vira aviso que ninguém lê.
- **Se o envio falhar**, o alerta não se perde: ele já foi impresso (e vai para
  o log) antes da tentativa de mandar.
- `MOVIZAP_LIGACOES_AVISO_NUMERO` vazio no `.env` = só imprime. É o que mantém
  o gancho da sessão funcionando sem mandar mensagem para ninguém.
- ⚠️ **Por que não existe alerta de "ramal revogado sem substituto"** (eu havia
  proposto): a revogação acontece junto do alistamento do PC novo, na mesma
  transação, e fora disso só à mão — quando alguém sai da empresa. Avisar nesse
  caso seria cobrar a reinstalação de quem foi embora.

### Provado em 15/10

| O quê | Resultado |
|---|---|
| Tudo em dia, sem flag | silêncio total (é o gancho da sessão) |
| Tudo em dia, com `--avisar-whatsapp` | silêncio total, nada enviado |
| PC fingido mudo há 30 h | alerta impresso **e** mensagem entregue no número do `.env` |
| O estado forçado | devolvido ao valor exato (`finally`), conferido depois |
| A linha do cron, rodada literalmente | código 0, log vazio |

## Achados do ensaio de 25/09 (antes de produção)

- `certreq -accept` recusa a CA própria (CERT_E_CHAINING). O `-Concluir` usa
  o cofre `My` + `certutil -repairstore`, sem tornar a CA raiz confiável do PC.
- `WebRequestHandler` não carrega no PowerShell 5.1: o agente usa
  `HttpClientHandler` com `ClientCertificateOptions = Manual`.


## A ficha e o import retroativo (Blocos 5, 6 e 9, 15/10/2026)

### O modal de 7 dias na conversa (Bloco 5)

🔵 *"aqui na conversa, o modal só trará ultimos 7 dias, para mais dias um botão
vai levar para a aba Ligações"* e *"importante a separação basica entre, feitas,
recebidas, etc"*.

Botão **Ligações** na gaveta da conversa (a ficha), abrindo
`GET /api/conversas/{id}/ligacoes?dias=7` — rota que já existia desde o Bloco 3
e não tinha quem a chamasse. Dentro: os três grupos do `CHECK` da 059
(`Feitas`, `Recebidas`, `Perdidas`), cada um com a contagem, e em cada linha a
hora, a duração, quem atendeu e, havendo gravação, **ouvir** e **baixar** (um
player por vez; o `object URL` é revogado ao trocar e ao sair da tela).

🚨 **A permissão é `ATD_1.2`, a da conversa — não a da aba.** Quem atende vê as
ligações do número que está atendendo. A aba `LIG_1.1` é outra coisa: o
histórico de todos.

🚨 **A linha de cobertura é o que impede o modal de mentir.** Ele diz quantos
atendentes têm agente instalado, porque "nenhuma ligação com este número" e
"aquele PC não manda ligação nenhuma" são respostas diferentes e a tela não
pode devolver a mesma frase para as duas.

⚠️ **O rodapé "Ver todas na aba Ligações" só aparece para quem tem `LIG_1.1`**
(hoje: owner, admin e `atendimento`). Para quem não tem, seria um botão que
termina em 403.

### Outros contatos da empresa (Bloco 6)

`GET /api/conversas/{id}/contatos-da-empresa`, sob **`ATD_1.2`**.

🚨 **Rota irmã, e não `/api/clientes/{id}`.** A rota de cadastro é `CAD_1.1`,
que o perfil `atendimento` não tem desde 10/08: a gaveta tomaria 403 justamente
para quem atende. É o mesmo motivo de `/api/conversas/buscar-empresa` existir.

- **Cada telefone é uma linha**, não cada contato: contato com dois números dá
  duas linhas, e contato **sem** número aparece mesmo assim, com `e164` nulo.
  Esconder quem não tem número faria a lista afirmar "a empresa tem 3 contatos"
  onde ela tem 5.
- **`tem_whatsapp` tem três valores** e eles não se confundem: `true`
  conferido e tem, `false` conferido e não tem, `null` nunca conferido. O botão
  **Mensagem** não aparece no `false` (mandar ali só produz 409) e **continua
  aparecendo** no `null` — recusar por falta de conferência seria inventar o
  `false`.
- **Lista vazia vem com `motivo`**: `sem_cadastro` (o número não está no
  cadastro) e `contato_sem_empresa` (a pessoa não tem empresa) são casos
  diferentes, e a tela diz qual é.
- **Pular para outra conversa reusa a receita do `?numero=`**: busca o número,
  um acerto abre a conversa, nenhum abre "Nova mensagem" preenchida. Não
  existe rota que apenas localize ou crie conversa sem enviar, e inventar uma
  seria um segundo caminho de conversa nascer.
- A ficha passou a mostrar **o telefone do contato** no `dt>Contato`, que nunca
  teve número nenhum — os dois primeiros, com `+N` quando há mais.

### Import retroativo (Bloco 9)

Para o PC que passou meses **sem** agente. Dois lados:

1. **No PC:** `movizap-ligacoes.ps1 -Exportar` (agente **v0.5**) grava um
   `.zip` na Área de Trabalho com `pacote.json` + `gravacoes/`. **Não precisa
   de chave, não precisa de config e não fala com a VPS** — é só leitura, que é
   o que permite rodar antes do alistamento. O pacote tem a **mesma forma do
   envio**, inclusive o `call_id` sintético `arquivo:<nome>` para gravação sem
   registro no histórico, e declara por escrito o que ficou de fora
   (`fora_do_padrao`, `em_uso_agora`).
2. **Na VPS:** `scripts/importar_ligacoes.py <pacote.zip> [--conferir]
   [--atendente <login|id>]`.

🚨 **Entra pelo mesmo `ligacoes.registrar()` do agente.** A idempotência é a
mesma (`UNIQUE (ramal, call_id)` e `arquivo_sha256` único): importar duas vezes
o mesmo pacote grava **zero** na segunda. Um `INSERT` próprio seria uma segunda
verdade.

🚨 **Recusa, e diz o que recusou:** linha sem `call_id` (sem ela não há
idempotência, e a mesma ligação voltaria a cada import); áudio que nenhuma
ligação do pacote reivindica (ele viraria ligação inventada, com data tirada do
nome do arquivo); `sha256` diferente do declarado; pacote de outra origem; e
versão de pacote mais nova do que o script entende.

🚨 **`--conferir` pergunta ao BANCO, não ao pacote.** Sem isso ele dizia "11
entrariam" num pacote cujas 11 já estavam todas na base — relatório que promete
mais do que vai acontecer é a mesma doença de tela que mente.

🚨 **De quem é a ligação importada**, nesta ordem: o agente **vivo** do ramal; o
último **revogado** dele; e só então, com `--atendente`, um **agente de
importação** novo — que nasce **já revogado**, com chave aleatória que ninguém
vê. Ele serve para carimbar de quem é a ligação, nunca para enviar. **Nunca
revoga o agente vivo de um ramal:** o PC que manda hoje não pode cair porque
alguém importou um arquivo velho.

⚠️ **Outra origem fica fora** (PABX, Intelbras, planilha à mão): muda a chave
de idempotência e precisa de desenho aprovado por ele.

⚠️ **O `pc` da linha importada vira `importado:<PC>`** — é como o grid
distingue retroativo de envio ao vivo.

🚨 **Armadilha medida em 15/10:** o `Compress-Archive` do **Windows PowerShell
5.1** grava os nomes dentro do zip com **barra invertida**
(`gravacoes\x.mp3`). O importador aceita os dois separadores; procurar só por
`gravacoes/` fazia ele recusar 19 gravações boas dizendo que estavam "ausentes
do zip". O pacote vem do PC do operador, onde não se escolhe a versão do
PowerShell — quem tem de aceitar os dois é o lado da VPS.

**Provado em 15/10:** o pacote real deste PC (28 ligações, 19 gravações, 5,6 MB)
importado contra a base que já tinha tudo → **0 novas, 28 e 19 já estavam, 0
recusadas**, nos dois modos; e 12 testes em `tests/teste_importar_ligacoes.py`.

### A sessão do dia (Bloco 8)

🔵 Decisão dele: *"o login vale até a virada do dia; o rascunho morre com ele"*.

`auth.expira_na_virada()` devolve a meia-noite seguinte em
**`America/Sao_Paulo`** (em UTC a virada cairia às 21h de Brasília, em plena
tarde), com **piso de 2 horas**: quem entra às 23:30 vale até a virada do dia
**seguinte**. A resposta do login devolve `expira_em` (ISO) em vez de
`expira_em_horas`, e `/api/sessao/eu` devolve `sessao_expira_em` — é daí que a
barra funciona depois de um F5 e para quem entra pelo Google.

⚠️ **O que isso custa, por escrito:** quem entra às 08:00 passa a ter token de
**16 h** em vez de 10 h. Continuam valendo as travas que já existem:
`atendente.ativo = false` derruba na requisição seguinte, perda de permissão
vira 403 na hora, e rotação do `MOVIZAP_JWT_SECRET` invalida tudo.

**Dois defeitos existentes que isso obrigou a consertar:** o 401 limpava a
sessão e **não navegava** (a pessoa ficava olhando uma tela sem casca que não
respondia mais nada até tentar navegar) — agora a casca leva ao Login com a
frase *"Sua sessão do dia terminou. Entre de novo."*; e o texto digitado no
compositor **vazava** de uma conversa para a outra, o que o rascunho por
conversa resolve.


## A senha de alistamento passou a valer 1 dia (15/10/2026)

🔵 *"dos ramais, podemos prolongar as senhas para 1 dia por enquanto?"* —
autorizado por ele no mesmo dia (*"ok para ajuste das senhas"*).

🚨 **O `.exe` não muda, e nenhum PC precisa ser reinstalado.** A senha é
derivada inteiramente na VPS (`senha_da_janela`); o instalador apenas manda o
que a pessoa digitou e ouve sim ou não. O nginx também não foi tocado.

🚨 **QUEM MUDOU FOI A ACEITAÇÃO, NÃO A JANELA DE GERAÇÃO**, e a diferença é o
ponto todo. `JANELA_S = 86400` pareceria o caminho óbvio e seria defeito grave:
`UNIQUE (ramal, janela)` é o que faz a senha servir uma vez, então uma janela
de um dia viraria **um alistamento por ramal por dia** — e um alistamento que
falhasse depois de a janela queimar (erro de certificado, rede caindo no meio)
deixaria o ramal travado até amanhã, porque "peça outra senha" devolveria a
mesma senha já queimada.

O que está no ar:

| | Antes | Agora |
|---|---|---|
| A senha TROCA a cada | 10 min | **10 min** (igual) |
| A senha é ACEITA por | 20 min (2 janelas) | **24 h** (144 janelas) |
| Uma falha custa | 10 min | **10 min** (igual) |
| Uso | uma vez | **uma vez** (igual) |

⚠️ **O que isso custa, por escrito:** uma senha ditada e **não usada** continua
servindo por até um dia, em vez de 20 minutos. Ela continua de uso único (a
primeira utilização queima a janela), continua **só alistando** (o batimento e
o envio seguem com chave + certificado), e 5 erros seguidos continuam trancando
aquele IP. O risco que cresce é alguém que ouviu a senha alistar o PC errado
antes da pessoa certa — e isso aparece na hora, porque alistar revoga o PC
anterior e o vigia acusa o PC que parou de falar.

⚠️ **Para voltar a 20 minutos é uma linha:** `JANELAS_ACEITAS = 2`.

⚠️ **A ferramenta dele passou a dizer o prazo REAL** (`Vale por 23 h 53 min`).
Enquanto `segundos_restantes()` media só a janela de geração, ela dizia "vale
por 7 min" de uma senha que valia um dia — e ferramenta que mente sobre o
próprio prazo faz pedir senha nova sem precisar.

**Provado:** 15 testes em `tests/teste_ligacoes_alistar.py`, entre eles a senha
de 23 h atrás alistando, a de 25 h sendo recusada, o uso único dentro do dia, e
uma janela queimada **não** trancando a seguinte.


### A senha passou de 1 dia para 48 h (15/10, fim do dia)

🔵 *"essas senhas pode deixa-las com 48hrs a partir da geracao"*, junto do
pedido de deixar as senhas de todos os ramais prontas num arquivo.

`JANELAS_ACEITAS = 288` (288 × 10 min). Continua valendo o que já estava
escrito: quem muda é a **aceitação**, nunca a janela de geração — é o
`UNIQUE (ramal, janela)` que faz a senha servir uma vez, e janela grande
viraria "um alistamento por ramal a cada 48 h".

⚠️ O custo cresce junto: senha ditada e **não usada** serve por dois dias.
Continua de uso único e continua só alistando.

**`scripts/senhas_dos_ramais.py`** gera o arquivo com a senha de cada ramal
(`--gravar`). Ele **não dá senha a ramal que já está enviando** — usá-la
revogaria o PC que funciona — e lista, com o motivo, quem ficou de fora. O
arquivo diz, dentro dele, que é uma chave e que se apaga depois do mutirão.
