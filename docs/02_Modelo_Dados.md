# 02 — Modelo de dados

Banco `movizap`, no **Postgres 16 do host** (não no container — aquele é do Evolution).

Banco próprio, não schema dentro de outro: backup e restauração independentes.

> **Este é o documento que fica caro de mudar depois.** É o que mais merece revisão antes de existir código.

---

## Princípios

1. **Evento referencia, nunca copia.** A mensagem aponta para o contato; não guarda o nome dele. Foi copiar que quebrou o `HBG 8442` no Harmonit — uma instalação de 2024 fotografou um cadastro vazio e nunca mais foi corrigível.
2. **Estado derivado, não escrito à mão.** "Conversa aberta" é consulta, não flag mantida por gatilho.
3. **Duas origens no mesmo lugar, com fronteira dura.** `origem` diz quem manda em cada linha.
4. **Telefone é identidade no WhatsApp**, e por isso é tabela, não coluna.
5. **Nada se apaga.** Inativa-se.

---

## Cadastro

### `cliente`
| Campo | Tipo | Nota |
|---|---|---|
| `id` | bigserial PK | |
| `nome` | text | razão social ou nome |
| `documento` | text | CNPJ/CPF, só dígitos. **Aceita alfanumérico** (o novo CNPJ já existe na base) |
| `origem` | enum(`harmonit`,`movizap`) | fronteira do sync |
| `harmonit_id` | text NULL | UNIQUE quando não nulo |
| `ativo` | bool | |
| `criado_em` / `atualizado_em` / `sincronizado_em` | timestamptz | |

### `contato`
| Campo | Tipo | Nota |
|---|---|---|
| `id` | bigserial PK | |
| `cliente_id` | FK NULL | lead e fornecedor podem não ter cliente |
| `nome` | text | |
| `relacao` | enum(`cliente`,`fornecedor`,`tecnico`,`lead`) | **o que a pessoa é para a Movisat** |
| `origem` / `harmonit_id` / `ativo` | | igual acima |

### `contato_papel`
Papel **dentro do cliente** — eixo diferente de `relacao`.

| Campo | Nota |
|---|---|
| `contato_id` | FK |
| `papel` | enum(`assinar`,`central_24h`,`financeiro`) |

⚠️ **`relacao` e `papel` não são a mesma coisa.** Um técnico não é "papel de contato de cliente". Colapsar os dois num campo só custa faxina depois.
⚠️ Na Fase 1 o papel **é gravado e não aciona nada**.

### `contato_telefone`
| Campo | Tipo | Nota |
|---|---|---|
| `id` | bigserial PK | |
| `contato_id` | FK | |
| `e164` | text | **normalizado — é por aqui que se busca.** INDEX |
| `bruto` | text | como veio. Nunca se perde |
| `tem_whatsapp` | bool NULL | `NULL` = não verificado ≠ `false` = verificado e não tem |
| `verificado_em` | timestamptz NULL | |
| `principal` | bool | |

🚨 A busca **nunca** usa `bruto`. O nono dígito faz `+551899811xxxx` e `+55189811xxxx` serem a mesma pessoa — o normalizador resolve nos dois sentidos.

---

## Canal e conversa

### `canal`
| Campo | Nota |
|---|---|
| `id` / `nome` | |
| `tipo` | enum(`atendimento`,`informativo`) |
| `gateway` | `evolution` |
| `instancia` | nome da instância no Evolution |
| `modo` | enum(`baileys`,`cloud_api`) — a porta para a API oficial já fica aberta |
| `ativo` | |

### `conversa`
| Campo | Nota |
|---|---|
| `id` | |
| `canal_id` | FK |
| `contato_id` | FK **NULL** — desconhecido até identificar |
| `telefone_e164` | sempre presente: é o que chega, mesmo sem cadastro |
| `estado` | enum(`nova`,`bot`,`fila`,`humano`,`resolvida`,`adiada`) |
| `atendente_id` / `time_id` | FK NULL |
| `prompt_versao_id` | FK NULL — **qual versão da IA atendeu esta conversa** |
| `classificacao_id` | FK NULL — preenchida no fechamento |
| `aberta_em` / `ultima_mensagem_em` / `encerrada_em` | |
| `adiada_ate` | timestamptz NULL |

**Constraint que evita conversa duplicada:**
```
UNIQUE (canal_id, telefone_e164) WHERE estado <> 'resolvida'
```
Uma conversa aberta por telefone, por canal. É isso que faz o cliente que volta **reabrir** em vez de criar outra.

### `mensagem`
| Campo | Nota |
|---|---|
| `id` | |
| `conversa_id` | FK |
| `id_externo` | text **UNIQUE** — 🚨 é a idempotência do webhook. Sem isso, reentrega duplica |
| `direcao` | enum(`entrada`,`saida`) |
| `autor` | enum(`cliente`,`ia`,`atendente`,`sistema`) |
| `tipo` | enum(`texto`,`imagem`,`audio`,`video`,`documento`,`figurinha`,`localizacao`,`contato`,`sistema`) |
| `conteudo` | text |
| `midia_id` | FK NULL |
| `citada_id` | FK NULL — resposta citando outra mensagem |
| `atendente_id` | FK NULL |
| `entrega` | enum(`pendente`,`enviada`,`entregue`,`lida`,`falhou`) |
| `criada_em` | timestamptz — **do provedor**, é por ela que a tela ordena |
| `recebida_em` | timestamptz — nossa. Webhook chega fora de ordem |

**`tipo = 'sistema'` é o que põe "Karla assumiu" e "transferido para Financeiro" na mesma linha do tempo dos balões.** Sem isso o histórico fica ilegível — é o `activity` do Chatwoot, e vale a cópia.

### `midia`
`id · conversa_id · mime · tamanho · caminho · nome_original · hash · baixada_em`

Arquivo em disco, não no banco. `hash` evita guardar duas vezes o mesmo áudio.

---

## Operação

### `atendente`
`id · nome · email · senha_hash NULL · google_sub NULL · ativo · convite_token NULL · convite_expira_em NULL`

Login local na Fase 1; as colunas do Google já nascem para a Fase 2 não exigir migração.

### `time` · `atendente_time`
n:n. O time rege a transferência.

### `classificacao`
`id · nome · ativo` — motivo de fechamento. Obrigatória ao resolver.

### `prompt_versao`
`id · versao · conteudo · autor_id · criado_em · ativo`

**Prompt não é editado por cima.** Cada alteração é uma versão nova, e a conversa grava qual atendeu. É o que permite responder "por que a IA disse isso" três semanas depois.

### `sync_execucao`
`id · iniciado_em · terminado_em · origem(cron|manual) · atendente_id NULL · lidos · criados · atualizados · inativados · erros · mensagem_erro`

Sem isso não se sabe se o botão funcionou.

---

## 🚨 A regra dura do sync

```
O sync SÓ toca linhas com origem = 'harmonit'.
Linha com origem = 'movizap' é intocável — nem update, nem delete, nunca.
```

- Upsert por `harmonit_id`. **Jamais "apaga tudo e reinsere"** — seria perder na primeira madrugada todo contato cadastrado à mão.
- Sumiu do Harmonit → `ativo = false`. Não se apaga cadastro.
- O Harmonit responde **`list` quando acha** e **`dict` quando não acha**, e o `dict` é *truthy*. O sync checa o **tipo**, não a veracidade.

---

## Índices que não são opcionais

| Índice | Por quê |
|---|---|
| `mensagem.id_externo` UNIQUE | idempotência do webhook |
| `contato_telefone.e164` | é o lookup de toda mensagem que chega |
| `conversa (canal_id, telefone_e164)` parcial | uma conversa aberta por telefone |
| `conversa (estado, time_id)` | a fila é a tela mais aberta do dia |
| `mensagem (conversa_id, criada_em)` | rolagem do histórico |

---

## O que este modelo deliberadamente não tem ainda

`contrato` · `veiculo` · `os` · `fatura` — **na Fase 1 esses dados são consultados no FPSL, não copiados para cá.**

Quando o ERP existir, eles nascem aqui como entidades próprias e a ficha deixa de ser consulta externa. O modelo acima já está desenhado para isso: `cliente` e `contato` são as mesmas tabelas que o ERP vai usar.
