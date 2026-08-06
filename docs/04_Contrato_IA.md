# 04 — Contrato da IA

O que a IA do MoviZap faz, o que ela **nunca** faz, e como se prova que ela continua fazendo certo.

Motor reaproveitado do MoviChat: `services/llm/` (gateway multi-provider, DeepSeek + Groq, 706 linhas). **Não se reescreve o motor — herda-se.**

---

## Papel

**Triagem inicial no canal de atendimento.** Ela é o primeiro a responder, entende o que a pessoa quer, busca o que dá para buscar, resolve o que é simples e **entrega para o humano com contexto** o que não é.

Ela **não** é uma árvore de menu com linguagem natural por cima. Não existe "digite 1".

```
Objetivo:     cliente resolvido sem espera, e humano recebendo contexto pronto
Hoje:         = o objetivo na Fase 1, só no canal de atendimento
Por quê:      menu numerado não sobrevive a pergunta fora do script, e a maioria é
Reavaliar se: taxa de transferência ficar tão alta que a triagem não esteja poupando ninguém
```

---

## Ferramentas que ela pode chamar

| Ferramenta | O que faz |
|---|---|
| `identificar_contato(telefone)` | quem é, pelo telefone normalizado |
| `dados_cliente(cliente_id)` | razão social, documento, situação |
| `listar_veiculos(cliente_id)` | placas e equipamentos |
| `posicao_veiculo(placa)` | **ao vivo, nunca do cache** |
| `consultar_faturas(cliente_id)` | em aberto e vencidas |
| `historico_conversas(contato_id)` | o que já foi falado |
| `transferir(time, motivo)` | manda para a fila humana |
| `encerrar(motivo)` | fecha quando resolveu |

⚠️ **Toda ferramenta é somente leitura na Fase 1**, com exceção de `transferir` e `encerrar`. A IA não escreve em cadastro, não abre OS, não altera nada.

---

## O que ela nunca faz

1. **Prometer prazo.** Nem "amanhã", nem "em breve", nem "logo".
2. **Dar desconto, isentar, negociar valor.**
3. **Confirmar pagamento.** Ela informa o que o sistema mostra; quem confirma baixa é o financeiro.
4. **Cancelar, suspender ou alterar contrato.**
5. **Expor o mecanismo.** Não fala de API, cache, Harmonit, WESO, "meu sistema", "não consegui consultar". O cliente não precisa saber como a salsicha é feita.
6. **Inventar.** Se não sabe, transfere.
7. **Responder em grupo.** (Grupos são Fase 3, e mesmo lá: nunca.)
8. **Repetir dado sensível sem necessidade** — não recita CPF/CNPJ inteiro na conversa.

🚨 O item 6 é o que custou caro no MoviChat em 02/07, 15/07 e 28/07: a IA **negava o que ela mesma já tinha no banco**. A regressão de 168 perguntas nasceu disso.

---

## Caminho de "não sei"

```
não tenho a informação  →  transfere, com o resumo do que já foi apurado
tenho, mas é ambígua    →  pergunta UMA vez, depois transfere
o cliente pediu humano  →  transfere na hora, sem insistir
```

**Nunca:** "não consegui acessar", "estou com problema técnico", "tente novamente". Isso é expor mecanismo — e é o item 5.

## Handoff

- Ao transferir, a IA escreve uma **nota interna** (não vai para o cliente) com: quem é, o que quer, o que já foi consultado, o que falta.
- Quando um humano assume, **a IA cala imediatamente** — sem despedida, sem "vou transferir você". O cliente não deve perceber a troca.
- O humano pode **devolver ao bot** depois de resolver.

## Agrupamento de entrada

O cliente manda três mensagens seguidas. A IA espera **~5 segundos de silêncio** e trata as três como **uma**. Responder cada uma isoladamente é a coisa que mais denuncia um robô.

## Saída

- Teto de tamanho por mensagem.
- Atraso proporcional ao texto, com "digitando…".
- **Nunca mais de 2 balões seguidos.**

---

## Versionamento

**O prompt não é editado por cima.** Cada alteração cria uma linha em `prompt_versao`, e cada conversa grava `prompt_versao_id`.

Sem isso, "por que a IA respondeu isso em julho?" não tem resposta — o prompt de julho não existe mais.

Publicar versão nova exige **passar no teste de aceite** abaixo.

---

## Teste de aceite

Reaproveita o insumo que já existe: **as 168 perguntas reais** da regressão do MoviChat, mais as **17 negativas** (perguntas que a IA deve recusar ou transferir, não responder).

| Critério | Meta |
|---|---|
| Respondem sem exceção | 168/168 |
| Negativas corretas | ≥ 16/17 |
| Nenhuma resposta expõe mecanismo | 100% |
| Nenhuma resposta promete prazo ou valor | 100% |
| Custo médio por mensagem | acompanhado, não travado |

🚨 **A asserção precisa detectar valor constante, não só `NULL`.** Um campo devolvendo `0` em 100% das linhas passa batido num teste de nulidade — foi assim que `bateria = 0` sobreviveu.

⚠️ Teste que roda só contra mock não conta. O aceite final é conversa real no chip de teste.

---


---

## 🚨 O interruptor — ela nasce desligada

**Decisão do usuário em 2026-08-06.** A IA tem um interruptor **por canal**, e
ele nasce em `false`. Ninguém liga por acidente; ligar é um ato.

```
Objetivo:     a IA só fala quando alguém decidiu que ela devia falar
Hoje:         = o objetivo. canal.ia_ligada, false por padrão (migração 007)
Por quê:      pedido do usuário -- a ordem é validar conexão, depois o bot, e
              só então ligar. Um sistema que já nasce respondendo ao cliente
              não tem ensaio: o primeiro erro dele é em público
Reavaliar se: -- fechado
```

### Por que por canal e não global

| | |
|---|---|
| **Global** | obriga alguém a lembrar de desligar antes de cada disparo do informativo. **"Lembrar" é exatamente o que falha.** |
| **Por canal** | o informativo não tem como ligar. Não é disciplina, é a coluna |

**Somente o canal `atendimento` tem IA.** O `informativo` não recebe mensagem
como conversa — o que chegar nele é gravado em `webhook_evento` e marcado como
processado, sem virar conversa e sem acionar a IA.

⚠️ E vai chegar mensagem nele: **gente responde boleto.** Fingir que não chega
faria a resposta do cliente sumir sem rastro. Guardar sem atender é o meio
termo honesto.

### A sequência de ativação

```
1. parear o chip                     CFG_1.1
2. confirmar que mensagem chega      conferir webhook_evento
3. validar o bot respondendo         em conversa de teste
4. LIGAR O INTERRUPTOR               ato deliberado, na CFG_1.1
```

O banco registra `ia_ligada_em` e `ia_ligada_por`. Não é burocracia: quando
alguém perguntar *"desde quando a IA está respondendo os clientes?"*, a
resposta não pode ser um encolher de ombros.

---

## Os dados que ela pode consultar

**Só leitura, e só o que está no banco do MoviZap.** A IA não fala com o
Harmonit nem com a WESO: fala com o cadastro que o sync já trouxe. Isso não é
economia de código — é o que impede uma pergunta em linguagem natural de virar
carga na API de terceiro, e o que garante que ela vê o mesmo dado que o
atendente vê na ficha.

| Tabela | O que ela enxerga | O que ela NUNCA enxerga |
|---|---|---|
| `cliente` | nome, fantasia, documento, situação | — |
| `contato` | nome, relação, e-mail | — |
| `contato_telefone` | E.164, `tem_whatsapp` | o `bruto`, que não acrescenta nada a ela |
| `contato_papel` | papéis | — |
| `conversa`, `mensagem` | **só a conversa em andamento** | conversa de outro contato |
| FPSL | veículos, contratos, faturas | qualquer escrita |

🚨 **Ela nunca enxerga `config`, `atendente`, `prompt_versao` nem
`webhook_evento`.** Não é só privacidade: uma IA que lê a própria configuração
é uma IA que pode ser convencida a descrevê-la para quem estiver do outro lado.

🚨 **Nunca escreve no cadastro.** Se a conversa revelar que o cadastro está
errado — telefone de outra empresa, nome trocado — ela **registra na conversa**
e não corrige nada. Correção de cadastro é ato de gente, com rastro.

### O caso do número compartilhado

44 números da base estavam em mais de um cliente (`08_Identidade.md`). Os
duvidosos ficaram **sem dono**, então `identificar_contato` vai devolver
**vazio** para eles — e isso é o comportamento certo.

Quando isso acontecer, a IA **pergunta**: *"você está falando em nome de qual
empresa?"*, e registra a resposta na conversa para um humano confirmar.

🚨 **É a única fonte que sabe a verdade — a pessoa do outro lado.** Nenhuma
regra automática resolve isso, e chutar produziria ficha errada na tela do
atendente, que é pior que ficha nenhuma.
## Chave e custo

- Chave lida do `.env` por **um único gateway**. Nenhum outro módulo sabe que ela existe.
- Montagem usa a chave atual; a chave própria do MoviZap entra depois — **é uma linha no `.env`, sem tocar em código**.
- Chave separada por projeto dá **custo discriminado** e permite revogar uma sem derrubar as outras.
- Em tela de configuração, mostra-se `sk-...a3f9`. Nunca o valor.
- 🚨 `httpx` / `httpcore` / `hpack` silenciados desde a primeira linha — é por ali que a chave da WESO vazou para um log.
