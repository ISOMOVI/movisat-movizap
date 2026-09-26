# Ligações do MicroSIP — como os dados entram e onde ficam

Planos 5 e 5.1 (25/09/2026). 🔵 *"inicialmente o backup das ligações na VPS
de uma forma bem inteligente -- depois ter uma rotina com histórico de chamadas
na ficha da pessoa do chat"* e *"talvez diretório documentado de como os dados
entram e ordenamos ele para consulta rápida"*.

O procedimento para instalar em cada operador está no kit `Desktop\MoviZap-Ligacoes-Kit\MANUAL.md`
do PC do Iago (ferramentas Preparar, Assinar e Conferir, sobre `scripts/agentes_ligacao.py`).

## O caminho

```
PC do operador
  MicroSIP ─ grava MP3 em recordingPath (MicroSIP.ini) + histórico em call_log.db
  Tarefa "MoviZap Ligacoes" (12:00, 17:30, ao entrar +5 min, usuário da pessoa)
  └─ movizap-ligacoes.ps1 (v0.3)
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

A rota antiga (`movizap.movisat.com.br/api/ligacoes/agente/*`, no processo do
painel) vale só até cada PC concluir o passo 2. Ela sai junto do reinício do
Plano 4.

## Garantias

- **Idempotente pelo banco:** reenviar não duplica nada (`UNIQUE (ramal, call_id)`
  e hash único). A resposta devolve o hash **do que está no disco**, e o agente
  só marca como salvo quando o hash bate.
- **Nada é apagado do PC** nesta fase ("7 dias já pode apagar" fica para depois,
  com a palavra dele).
- **Queda e atraso:** até 3 tentativas (30 s, 2 min, 5 min); o 429 espera o
  `Retry-After`; arquivo recusado é pulado sem travar os outros; o tempo
  limite é de 60 s + 10 s por MB; uma execução por vez (`agente.lock`).
- **Alerta:** o gancho `SessionStart` do Claude Code roda
  `scripts/agentes_mudos.py`. Ele fica mudo quando está tudo em dia e acusa:
  PC sem contato há mais de 24 h, PC vivo com erro ou aviso, e certificado
  vencendo em menos de 30 dias.

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

## Consulta rápida (hoje)

- Por contato: `ligacao (telefone_e164, inicio DESC)`, o índice da 059.
- Os índices por operador e por dia e a visão `ligacao_resumo` **nascem com a
  Fase 2**, junto da tela que os usa (índice sem consulta é palpite).

## Achados do ensaio de 25/09 (antes de produção)

- `certreq -accept` recusa a CA própria (CERT_E_CHAINING). O `-Concluir` usa
  o cofre `My` + `certutil -repairstore`, sem tornar a CA raiz confiável do PC.
- `WebRequestHandler` não carrega no PowerShell 5.1: o agente usa
  `HttpClientHandler` com `ClientCertificateOptions = Manual`.
