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
| `MOD` | módulo — `INI` início · `ATD` atendimento · `EML` e-mail · `CAD` cadastro · `CFG` configuração · `REL` relatório |
| `a` | submódulo |
| `b` | tela |
| `c` | aba dentro da tela (opcional) |

🚨 **O código nunca muda.** Título muda, rota muda, arquivo muda — código não. Se uma tela for aposentada, o código é **aposentado junto**, nunca reaproveitado. Reaproveitar código faz o log antigo mentir.

---

## Telas — espelho de `movizap/telas.py`

> 🚨 **ESTA TABELA É A ÚNICA.** Até 12/08 este arquivo tinha **duas** tabelas
> de telas — "Registro — Fase 1" e "Telas de hoje" — e elas divergiram em
> silêncio: a primeira dava `admin` a seis telas que o código trata como
> `owner`, e não tinha `EML_1.1`, `INI_1.1` nem `CFG_2.2`. Só a segunda tinha
> teste. Duas tabelas do mesmo fato é uma que vai mentir; o conserto não foi
> corrigir células, foi apagar a cópia.
>
> ⚠️ `teste_telas.py` reprova se um código existir no `telas.py` e não
> aparecer aqui. Foi assim que `INI_1.1` e `EML_1.1` ficaram de fora até 10/08.

| Código | Tela | Rota | Permissão | Fase |
|---|---|---|---|---|
| `INI_1.1` | Início | `/inicio` | `atendimento` | 1 |
| `ATD_1.1` | Caixa de entrada | `/atendimento` | `atendimento` | 1 |
| `ATD_1.2` | Conversa | `/atendimento/{id}` | `atendimento` | 1 |
| `ATD_1.3` | Fila | `/atendimento/fila` | `atendimento` | 1 |
| `ATD_3.1` | Informativos | `/informativos` | `informativos` | 1 |
| `ATD_5.1` | Histórico | `/atendimento/historico` | `atendimento` | 1 |
| `ATD_6.1` | Chat interno | `/chat` | `atendimento` | 1 |
| `EML_1.1` | E-mail | `/email` | `atendimento` | 1 |
| `CAD_1.1` | Clientes | `/cadastro/clientes` | `cadastro` | 1 |
| `CAD_1.2` | Contatos | `/cadastro/contatos` | `cadastro` | 1 |
| `CAD_2.1` | Atendentes | `/cadastro/atendentes` | `owner` | 1 |
| `CAD_2.2` | Times | `/cadastro/times` | `owner` | 1 |
| `CFG_1.1` | Canais | `/config/canais` | `owner` | 1 |
| `CFG_2.1` | IA — prompt | `/config/ia/prompt` | `owner` | 1 |
| `CFG_3.1` | Sincronização | `/config/sync` | `owner` | 1 |
| `CFG_4.1` | Classificações | `/config/classificacoes` | `owner` | 1 |
| `CFG_9.1` | Registro de telas | `/config/telas` | `owner` | 1 |
| `CFG_2.2` | IA — analytics | `/config/ia/analytics` | `owner` | 2 |
| `REL_1.1` | Relatórios | `/relatorios` | `owner` | 3 |

🚨 **TODA CONFIGURAÇÃO É `owner`, E ISSO É DECISÃO, NÃO DESCUIDO.** A tabela
antiga dizia `admin` em seis dessas linhas. Quem lesse criaria um perfil
`admin` esperando que ele configurasse Canais ou Sincronização, e levaria 403
sem entender: `pode_acessar` devolve **False** para tela `owner` a menos que a
pessoa seja o owner. Em 12/08 o perfil `admin` saiu do vocabulário — ver
"Perfis" abaixo.

## Abas e componentes

Não entram no `telas.py`: **não têm rota nem permissão próprias**, e o
`telas.py` é o registro das rotas — é ele que gera menu e resolve permissão.
Herdam a permissão da tela que os hospeda. **Não é drift.**

Continuam valendo como âncora de auditoria: o log grava `CAD_1.2.2` quando o
erro foi na aba de telefones, e é isso que se procura.

| Código | O quê | Dentro de |
|---|---|---|
| `CAD_1.2.1` | Contato — dados | `CAD_1.2` |
| `CAD_1.2.2` | Contato — telefones | `CAD_1.2` |
| `CAD_1.2.3` | Contato — papéis | `CAD_1.2` |
| — | Gaveta do contato (painel lateral) | `ATD_1.2` — **sem código próprio** |

⚠️ **A gaveta que existe hoje NÃO é a `ATD_2.1`.** Ela abre por botão dentro da
conversa e mostra o que o Harmonit e o Bitrix sabem do número. A `ATD_2.1` é
outra coisa, ainda não construída: a ficha do cliente **consultando o FPSL** —
é o que o próprio texto da tela vazia promete. Até 12/08 a `ATD_2.1` aparecia
nesta tabela como se fosse a gaveta, contradizendo o `docs/10`, que dizia que a
gaveta está "fora do registro". Eram duas coisas com um nome só.

**Reservados, não implementar agora:**
`ATD_2.1` Ficha do cliente com FPSL · `CFG_2.2` IA — analytics · `REL_1.1` Relatórios

🚨 **`ATD_3.1` SAIU DA RESERVA EM 2026-08-07** e subiu para a Fase 1.
Decisão do usuário: *"o informativo é o que vai enviar, sem resposta de
cliente"*. O chip foi pareado no mesmo dia e o canal já entrega (TESTE
BOT com `DELIVERY_ACK` em 2 s).

⚠️ **É a única tela do sistema que alcança cliente de verdade EM LOTE**, e
o canal é irreversível. Por isso a permissão dela é `informativos`, que
**não está em nenhum perfil** além do owner: disparo em massa não é coisa
que se libera por padrão. Para dar a alguém, é acrescentar `informativos`
ao perfil em `telas.PERFIS` — decisão consciente, não efeito colateral.

⚠️ **Por que o chat é `ATD_6.1` e não cabe dentro de `ATD_1`.** Acrescentado
em 12/08. O submódulo `ATD_1` é atendimento a **cliente** — caixa, conversa,
fila. O chat interno é outro assunto: conversa entre atendentes, que nunca sai
para o WhatsApp. Pendurá-lo em `ATD_1` faria o log de auditoria misturar
"falou com cliente" e "falou com colega", que é justamente o que se quer poder
distinguir. Submódulo próprio custa três dígitos.

⚠️ **Por que o Histórico é `ATD_5.1` e não `ATD_2.2`.** Acrescentado em
2026-08-06. O submódulo `ATD_2` é a ficha do contato, e `ATD_3`/`ATD_4` já
estão reservados acima. Poderia ter virado `ATD_2.2`, mas ficaria pendurado no
submódulo da ficha, com quem não tem parentesco nenhum. Histórico é assunto
próprio, então ganha submódulo próprio. **Custo: nenhum — são três dígitos.**

⚠️ **Contagem de linhas não serve como reconciliação.** Até 12/08 este trecho
dizia "a tabela tem 17 linhas e o `telas.py` tem 13 de Fase 1 — a diferença são
`ATD_2.1` e as três abas". A conta estava errada e ninguém percebeu, porque
número em prosa não tem teste. A separação agora é estrutural: **tela** e
**aba/componente** são duas tabelas diferentes, e só a primeira é espelho do
`telas.py`. Quem quiser conferir roda `teste_telas.py`, não conta linha.

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

## Perfis

| Perfil | Permissões | Telas na prática |
|---|---|---|
| `owner` | todas | tudo, inclusive o que é exclusivo do owner |
| `atendimento` | `atendimento` | `INI_1.1` `ATD_1.*` `ATD_5.1` `EML_1.1` |
| `cadastro` | `cadastro` | `CAD_1.1` `CAD_1.2` |

Perfil é conjunto de **permissões**, e a permissão de cada tela vem do registro.
**Não existe permissão escrita fora dele.**

🚨 **`admin` SAIU DO VOCABULÁRIO EM 12/08.** Ele existia como perfil e como
permissão, e destravava exatamente duas telas — `CFG_2.2` (Fase 2) e `REL_1.1`
(Fase 3) —, **nenhuma das quais existe**. Na prática, um `admin` tinha o mesmo
alcance de quem tem `atendimento` + `cadastro`, e a doc prometia que ele
configuraria Canais e Sincronização, o que o código nunca permitiu. Ninguém
usava: a base tinha 1 `owner` e 3 `atendimento`.

Decisão do usuário no mesmo dia: **owner é o único administrador, e não nascem
mais owners.** As duas telas futuras passaram a `owner`, o perfil saiu de
`telas.PERFIS` e o `CHECK` da coluna `atendente.perfil` perdeu o valor
(migração 024).

⚠️ **`informativos` não está em nenhum perfil**, de propósito — só o owner
alcança a `ATD_3.1`. Disparo em massa não se libera por padrão; para dar a
alguém, acrescenta-se `informativos` ao perfil em `telas.PERFIS`, como decisão
consciente.

---

## Códigos aposentados

🚨 **Nunca reaproveitados** — reusar faria o log antigo mentir.

- `ATD_4.1` — era o e-mail dentro do módulo de atendimento. Aposentado em 10/08: o usuário decidiu que e-mail **jamais** se mistura com WhatsApp, e ele virou `EML_1.1`, módulo próprio. A tela nunca existiu, então nada foi logado com ele.
