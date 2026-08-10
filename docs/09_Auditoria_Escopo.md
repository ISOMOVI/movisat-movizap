# 09 — Auditoria de escopo: o que existe sem ninguém ter pedido

> Feita em **2026-08-10**, depois de um erro concreto. Este documento não é
> histórico: é a lista do que precisa ser tratado e a regra que impede a
> repetição.

---

## Por que esta auditoria existe

Em 10/08 eu apresentei ao usuário, **três mensagens seguidas**, uma "pendência
bloqueada nele": validar a lista de papéis de contato — `assinar`,
`central_24h`, `financeiro`.

Ele respondeu: *"assinar não faz parte do escopo, nem central e nem
financeiro, de onde tirou isso?"*

A resposta: de mim. Os três estão no `CHECK` da migração 001 e na seção
`contato_papel` do `02_Modelo_Dados.md`, escritos em 05/08. Vieram por carona
do modelo do **ERP** de 03/08 — `assinar` casa com a Clicksign, `financeiro`
com o Asaas, `central_24h` com o monitoramento. Nada disso é atendimento por
WhatsApp.

🚨 **O erro não foi criar a tabela — foi transformá-la em pergunta.** Estrutura
inerte é barata. O que custou o tempo do usuário foi eu ler o banco, encontrar
uma regra que **eu mesmo tinha escrito**, e devolvê-la a ele como se fosse
requisito dele esperando validação. É o oposto da regra 1 da abertura do
`Proximos_Passos.md`: *antes de perguntar, verificar*.

---

## O método

O sinal é sempre o mesmo: **estrutura com regra escrita e zero uso**. Coisa
viva tem linha; coisa inventada fica vazia esperando alguém descobrir para que
serve.

Cruzam-se três coisas:

1. tabelas vazias e colunas nunca preenchidas (o banco, medido);
2. valores de `CHECK` que nunca apareceram em nenhuma linha;
3. **em qual documento o conceito aparece** — e esse é o teste decisivo.

⚠️ **`02_Modelo_Dados.md` é documento MEU.** Conceito que aparece só nele nunca
passou pelo escopo. Conceito que aparece também no `01_Escopo_Fase_1.md` foi ao
menos declarado como escopo antes de virar coluna.

---

## Resultado: três baldes, não um

### 🔴 Balde 1 — INVENTADO: existe, ninguém pediu, nenhum código usa

| O quê | Onde mora | Situação |
|---|---|---|
| **`contato_papel`** (`assinar`, `central_24h`, `financeiro`) | migração 001 + `02` | tabela **vazia**; **removido da ficha em 10/08** |
| **Avaliação de atendimento** — `conversa.avaliacao`, `avaliacao_pedida_em`, `avaliacao_comentario` + `config[avaliacao_ativa]` | migração 001 + `02` | **zero linhas de código** leem qualquer um deles |
| **`config[repasse_inatividade_min] = 30`** | `02` | nenhum código lê |
| **`config[adiamento_padrao_min] = 60`** | `02` | nenhum código lê |
| **`canal.gateway = 'email'`** | `02` | o MoviZap é canal de WhatsApp |
| **`contato.relacao`** = `parceiro`, `lead` | `02` | vocabulário de CRM; a base só tem `cliente` |
| **`atendente.max_conversas`** | `02` | implementado no CRUD, **NULL nos 4 atendentes** |

🚨 **O pior deles é `avaliacao_ativa = true`.** O banco afirma que a pesquisa de
satisfação está **ligada**. Nenhum cliente recebeu nada — porque não existe
código —, mas a configuração está mentindo, e mentira em configuração é o tipo
de coisa que alguém "religa" achando que está consertando. Somado ao fato de
que enviar pesquisa é **mensagem de saída para o cliente**, num canal que o
usuário decidiu em 07/08 que *não* serve para disparo, isso é uma armadilha
esperando implementação.

### 🟡 Balde 2 — LEGÍTIMO: decidido, ainda sem uso porque a peça não subiu

Não confundir com o balde 1. Estes estão vazios por cronograma, não por
invenção:

| O quê | Por que ainda está vazio |
|---|---|
| `conversa.estado` = `bot`/`fila`/`humano`/`resolvida`/`adiada` | máquina de estados subiu 07/08; ninguém triou ainda |
| `mensagem.autor = 'ia'`, `prompt_versao`, `conversa.prompt_versao_id` | a IA é o passo 8, ainda sem motor |
| `transferencia` (tabela) + `conversa.time_id`, `atendente_id` | atendimento pelo painel começou hoje |
| `contato_telefone.origem_campo = 'atendimento'` | criado hoje pela ficha lateral; vai encher com o uso |
| `cliente.origem`/`contato.origem` = `'movizap'` | preenche quando a ficha cria contato novo |
| `canal.modo = 'cloud_api'` | é o caminho da prospecção (Meta) |
| `atendente.google_sub`, `convite_token` | ⚠️ **decisão de 07/08: Google auth não será feito** — degradou para o balde 1 |

### 🟠 Balde 3 — PARADO POR DECISÃO EXPLÍCITA

| O quê | Decisão |
|---|---|
| `disparo`, `disparo_destino` (11 valores de estado, 0 linhas) | *"informativos não fará disparos em massa"* (07/08). Estrutura no ar, **propósito indefinido**, nada enviado |
| `time.time_transbordo_id` | a regra da fila sem atendente ainda não foi decidida |
| As **9 classificações** (0 usos) | catálogo plausível, mas **nunca validado** com quem atende |

---

## O que foi feito em 10/08 por causa desta auditoria

- **`contato_papel` saiu da ficha lateral.** A tabela fica — está vazia, não
  custa nada e o ERP pode querer o eixo depois. O que muda é que ela parou de
  aparecer na tela como se fosse recurso, e parou de ser pendência do usuário.
- **`avaliacao_ativa` passou para `false`.** O banco deixa de afirmar que uma
  pesquisa inexistente está ligada.

## O que fica pendente, e é decisão do usuário — não minha

1. **A avaliação de atendimento existe como produto?** Se não, as três colunas
   e a chave de config saem numa migração. Se sim, ela é mensagem de saída e
   precisa da mesma decisão que travou o informativo.
2. **As 9 classificações são as certas?** Foram propostas por mim e nunca
   confrontadas com quem atende. Zero usos ainda, então trocar é barato agora.

---

## 🚨 A REGRA, para não repetir

**1. Coluna nova exige frase do usuário, ou vira contorno rotulado.**
Se eu não consigo apontar onde ele pediu, o campo não nasce — ou nasce com um
comentário dizendo, com todas as letras, que foi decisão minha e por quê.

**2. `02_Modelo_Dados.md` não cria escopo.** Modelar é traduzir o que foi
decidido, não decidir. Conceito que só existe lá é suspeito por construção.

**3. Estrutura inerte NUNCA vira pergunta ao usuário.** Antes de listar algo
como "bloqueado em você", conferir a origem. Se a origem sou eu, o problema é
meu e a decisão de tirar também.

**4. Configuração não afirma o que o código não faz.** `avaliacao_ativa = true`
sem implementação é defeito, não preparação. Padrão ligado descreve
comportamento que existe.

**5. Herança de outro projeto se marca na hora.** Conceito vindo do ERP entrou
sem etiqueta e sobreviveu cinco dias parecendo requisito de atendimento. Se
vier de fora do escopo, o comentário diz de onde veio.
