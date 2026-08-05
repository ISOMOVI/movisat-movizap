# 03 — Registro de telas e barra de status

Toda tela do MoviZap tem um **código imutável**. O código é ao mesmo tempo **endereço**, **chave de permissão** e **âncora de auditoria**.

---

## Por que existe

Quando alguém diz "deu erro na tela de cadastro", começa uma investigação. Quando diz **"deu erro na `CAD_1.2`, requisição `a3f9`"**, a investigação já acabou.

```
Objetivo:     achar em segundos o código por trás de qualquer erro relatado
Hoje:         = o objetivo, desde a primeira tela
Por quê:      pedido do usuário em 2026-08-04, no modelo de bloco de notas/Excel
Reavaliar se: — fechado
```

## Formato

```
MOD_a.b[.c]
```

| Parte | Significado |
|---|---|
| `MOD` | módulo — `ATD` atendimento · `CAD` cadastro · `CFG` configuração · `REL` relatório |
| `a` | submódulo |
| `b` | tela |
| `c` | aba dentro da tela (opcional) |

🚨 **O código nunca muda.** Título muda, rota muda, arquivo muda — código não. Se uma tela for aposentada, o código é **aposentado junto**, nunca reaproveitado. Reaproveitar código faz o log antigo mentir.

---

## Registro — Fase 1

| Código | Tela | Rota | Permissão | Fase |
|---|---|---|---|---|
| `ATD_1.1` | Caixa de entrada | `/atendimento` | `atendimento` | 1 |
| `ATD_1.2` | Conversa | `/atendimento/{id}` | `atendimento` | 1 |
| `ATD_1.3` | Fila | `/atendimento/fila` | `atendimento` | 1 |
| `ATD_2.1` | Ficha do contato (painel lateral) | componente | `atendimento` | 1 |
| `CAD_1.1` | Clientes | `/cadastro/clientes` | `cadastro` | 1 |
| `CAD_1.2` | Contatos | `/cadastro/contatos` | `cadastro` | 1 |
| `CAD_1.2.1` | Contato — dados | aba | `cadastro` | 1 |
| `CAD_1.2.2` | Contato — telefones | aba | `cadastro` | 1 |
| `CAD_1.2.3` | Contato — papéis | aba | `cadastro` | 1 |
| `CAD_2.1` | Atendentes | `/cadastro/atendentes` | `admin` | 1 |
| `CAD_2.2` | Times | `/cadastro/times` | `admin` | 1 |
| `CFG_1.1` | Canais | `/config/canais` | `admin` | 1 |
| `CFG_2.1` | IA — prompt | `/config/ia/prompt` | `admin` | 1 |
| `CFG_3.1` | Sincronização Harmonit | `/config/sync` | `admin` | 1 |
| `CFG_4.1` | Classificações | `/config/classificacoes` | `admin` | 1 |
| `CFG_9.1` | Registro de telas | `/config/telas` | `owner` | 1 |

**Reservados, não implementar na Fase 1:**
`ATD_3.1` Informativos · `ATD_4.1` E-mail · `CFG_2.2` IA — analytics · `REL_1.1` Relatórios

---

## Fonte única

Espelha o `abas.py` do MoviServer, sem desvio:

```
telas.py  →  código · título · rota · arquivo · permissão · fase · ativo
```

- **Tela que não está no registro não existe.** Rota sem código registrado não sobe.
- A **navegação** é gerada do registro — menu não se escreve à mão.
- A **permissão** vem do registro: `requer_tela("CAD_1.2")` como dependency da rota. A permissão vive no backend, nunca no `localStorage`.
- O **log de auditoria** grava o código, não a URL. URL muda; código não.
- Conta nova nasce **sem nenhuma tela**: falha fechado.

---

## 🚨 Mexeu na tela? Atualiza o registro NO MESMO COMMIT

Regra pedida pelo usuário em 2026-08-05, e a mais fácil de esquecer.

Mudou **rota, título, ícone, permissão ou fase** de uma tela, o
`movizap/telas.py` muda junto — não no dia seguinte, não "depois que
estabilizar". No mesmo commit.

**Por que isto não é burocracia:**

| Se o registro desatualizar | O que quebra |
|---|---|
| rota mudou, registro não | o menu leva ao **lugar errado** — e o frontend desenha o que vem, então ele obedece o registro errado sem reclamar |
| permissão mudou, registro não | alguém enxerga o que não devia, ou perde acesso sem motivo aparente |
| título mudou, registro não | o log de auditoria descreve uma tela que **já não é aquela** |
| tela saiu, código reaproveitado | 🚨 **o log antigo passa a mentir** — aponta para uma tela que nunca visitou |

**Código aposentado nunca volta.** Tela removida deixa o código queimado para
sempre; a próxima usa número novo. É barato: são três dígitos.

**Como conferir:** `CFG_9.1` mostra o registro inteiro, e
`tests/teste_telas.py` reprova código duplicado, rota duplicada e permissão
vazando. Se o teste passar e a tela estiver errada, é porque o registro
mentiu junto — por isso a atualização é no mesmo commit, não depois.

---

## Barra de status

Fixa no rodapé de **toda** tela principal. Modelo mental: barra do Excel / bloco de notas.

```
┌──────────────────────────────────────────────────────────────────────┐
│ Iago Santos · sessão 01:47 · 04/08/2026 14:52 · CAD_1.2 · req a3f9  │
└──────────────────────────────────────────────────────────────────────┘
```

| Campo | Fonte |
|---|---|
| Usuário logado | sessão |
| Duração da sessão | relógio do cliente, desde o login |
| Data e hora | fuso do usuário |
| **Código da tela** | registro |
| **Id da requisição** | gerado no backend a cada requisição, ecoado no header e no log |

**Por que o id da requisição:** no erro, o que se procura no log não é a tela — é *aquela* requisição. Com o código você acha o arquivo; com o id você acha a linha.

⚠️ A barra faz parte do sistema de design desde a primeira tela. Pregada por cima depois, fica com cara de remendo.

---

## Perfis — Fase 1

| Perfil | Telas |
|---|---|
| `owner` | todas, e não pode ser alterado nem por ele mesmo |
| `admin` | tudo menos `CFG_9.1` |
| `atendimento` | `ATD_*` |
| `cadastro` | `CAD_1.*` |

Perfil é conjunto de telas, montado do registro. **Não existe permissão escrita fora dele.**
