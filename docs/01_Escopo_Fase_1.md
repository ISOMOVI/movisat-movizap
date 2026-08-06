# 01 — Escopo da Fase 1

**Definido em 2026-08-04.** Este documento é a **borda**. O que não está aqui, não é Fase 1 — nem "se der tempo", nem "já que estamos mexendo".

---

## O que o MoviZap é

O **comunicador da Movisat**: caixa de entrada de WhatsApp, própria, com IA fazendo a triagem inicial e a ficha do cliente ao lado da conversa.

Substitui o Chatwoot. Nasce dentro do que vai ser o ERP — a base cadastral daqui **é** o cadastro do ERP começando, não middleware descartável.

```
Objetivo:     atendimento com a ficha do cliente na mesma tela, sem integração
Hoje:         nada implementado — Fase 1 é o comunicador funcionando ponta a ponta
Por quê:      no Chatwoot a ficha é iframe alimentado por integração; aqui é consulta
Reavaliar se: — fechado pelo usuário em 2026-08-04
```

## Frase que define a Fase 1

> **Uma conversa real, de ponta a ponta, com IA e ficha.**

Se uma mensagem entra pelo WhatsApp, a IA responde, transfere para um humano, o humano resolve, classifica e fecha — e a ficha do cliente esteve na tela o tempo todo — a Fase 1 acabou.

---

## ✅ Entra

| # | Item | Detalhe |
|---|---|---|
| 1 | **Um canal** | MoviBot (atendimento), Baileys/QR, **no chip de teste** — não no número principal |
| 2 | **Base cadastral** | cliente, contato, telefone. Papéis **só como cadastro**, sem gerar demanda |
| 3 | **Sync Harmonit** | a cada 12h + botão "sincronizar agora", com registro de cada execução |
| 4 | **Cadastro manual** | contato criado no MoviZap, marcado como cliente/fornecedor/técnico/lead. **Não sobe para o Harmonit** |
| 5 | **`tem_whatsapp`** | verificado pelo Evolution. Sem WhatsApp, não envia |
| 6 | **Caixa de entrada** | lista de conversas, conversa aberta, envio de **texto** |
| 7 | **Recebimento de mídia** | áudio (inclusive de voz), foto, vídeo, documento — ver e ouvir na tela |
| 8 | **IA na triagem** | identifica, consulta, responde, transfere. **Sem menu numerado** |
| 9 | **Máquina de estados** | nova → bot → fila → humano → resolvida, com adiar e reabrir |
| 10 | **Botões na conversa** | Encerrar · Transferir · Adiar · Devolver ao bot |
| 11 | **Classificação no fechamento** | obrigatória — é o que alimenta analytics depois |
| 12 | **Ficha lateral** | cliente, veículos, contratos, faturas — consulta ao FPSL |
| 13 | **Login local** | padrão MoviServer. Google OAuth é Fase 2 |
| 14 | **Times** | cadastro e transferência entre eles |
| 15 | **Barra de status** | logado · duração da sessão · data/hora · código da tela · id da requisição |
| 16 | **Registro de telas** | códigos imutáveis servindo navegação, permissão e auditoria |
| 17 | **Sistema de design** | tokens, tipografia, claro/escuro — desde a primeira tela |
| 18 | **Notas internas na conversa** | visíveis só para a equipe. **Nunca saem para o cliente** |
| 19 | **Resumo na transferência** | quem transfere escreve o contexto; quem recebe lê antes de assumir |
| 20 | **Histórico** (`ATD_5.1`) | conversas encerradas, pesquisáveis |
| 21 | **Jornada do atendente** | dentro da `CAD_2.1`: horário de atendimento, pausa e dias da semana |
| 22 | **Segundo canal: Informativos** | conectar e **receber**. Mensagem que chegar é gravada e **não vira conversa** |
| 23 | **Interruptor da IA, por canal** | nasce **desligado**. Só o `atendimento` tem IA |
| 24 | **Registro cru do webhook** | `webhook_evento` guarda o corpo inteiro antes de qualquer interpretação |

> ⚠️ **Emenda de 2026-08-06, autorizada pelo usuário.** Os itens **18 a 21**
> alargam a Fase 1 em relação ao que foi fechado em 04/08. Estão escritos aqui
> porque **a borda é este documento**: item que entra sem passar por ele não é
> escopo, é penduricalho — e daqui a três semanas ninguém sabe qual era qual.
>
> O item 21 tem uma consequência que não é óbvia: **jornada vira insumo da
> fila**. Saber quem está em horário é o que separa "conversa esperando" de
> "conversa esperando alguém que só volta segunda". Por isso a `CAD_2.1` é
> construída **antes** da `ATD_1.3`.
>
> **Itens 22 a 24, emenda de 06/08 (mesmo dia, mais tarde).** O usuário tem
> chip para o Informativos e pediu para subir os dois e tratar depois.
>
> 🚨 **O item 22 NÃO reabre o disparo em massa**, que continua na lista de
> Fase 2 abaixo. Conectar e receber não é disparar, e nenhuma rota de envio em
> lote existe neste projeto. O que muda é que o canal passa a existir.
>
> ⚠️ O informativo **vai receber mensagem** mesmo não devendo — gente responde
> boleto. Ela é gravada em `webhook_evento` e marcada como processada, sem
> virar conversa e sem IA: honra o "não recebe" sem jogar fora o que chegou.
>
> O item 24 é a **mitigação escrita** do risco de parear o chip por último,
> declarado no fim deste documento.

## ❌ Fica fora — e está escrito

| Item | Volta em |
|---|---|
| ~~Canal Informativos~~ **e disparo em massa** | ⚠️ **O canal entrou em 06/08 (item 22) — o DISPARO continua Fase 2** |
| **Envio** de arquivo/mídia pela API | Fase 2 |
| Leitura de e-mail e dashboard de não lidos | Fase 2 (depende de Workspace, já confirmado como viável) |
| Google OAuth e convite por e-mail | Fase 2 |
| Grupos | Fase 3 — e quando entrar, **IA nunca responde em grupo** |
| Analytics da IA | Fase 2 |
| Relatórios | Fase 3 |
| Chamados e **geração de demanda** | quando o ERP tiver OS |
| API oficial da Meta | quando/se a empresa for verificada |
| Desligar o Chatwoot | só depois que este receber mensagem real |
| Migrar `evolution_db` para o Postgres do host | faxina posterior, não bloqueia nada |

⚠️ Os papéis do contato (assinar · central 24h · financeiro) **são gravados mas não acionam nada** na Fase 1. Existem para o cadastro nascer completo, não para gerar demanda.

---

## Critério de pronto

A Fase 1 está pronta quando **todos** forem verdade:

1. Uma mensagem enviada de um celular real aparece na tela em menos de 5 segundos.
2. A mesma mensagem reentregue pelo Evolution **não** duplica nada.
3. Um número não cadastrado é atendido e pode virar cadastro ali mesmo.
4. Um número cadastrado é reconhecido pelo nome, mesmo com nono dígito diferente.
5. A IA responde uma pergunta de triagem, consulta um dado real e transfere para um time.
6. O atendente assume, a IA cala, e o cliente não percebe a troca.
7. Foto e áudio enviados pelo cliente abrem e tocam na tela.
8. A conversa é adiada, volta sozinha para a fila e é encerrada com classificação.
9. A ficha lateral mostra os veículos do cliente vindos do FPSL.
10. Toda tela mostra a barra de status com um código válido.
11. Os testes do item 6 da metodologia passam.
12. Uma **nota interna** escrita na conversa **não chega ao cliente** — conferido no WhatsApp real, não no banco.
13. Uma conversa transferida chega ao time de destino **com o resumo legível antes de assumir**.
14. Uma conversa encerrada é encontrada no **Histórico** pelo telefone do cliente.
15. Um atendente **fora de jornada não recebe atribuição automática**.

*(12 a 15 acrescentados na emenda de 06/08, junto com os itens 18 a 21. Item de escopo sem critério de pronto é item que ninguém sabe dizer se ficou pronto.)*

**Não conta como pronto:** funcionar no teste unitário e não ter passado por WhatsApp real. Foi assim que o MoviBot ficou 6 semanas "pronto" sem nunca ter atendido ninguém.

🚨 **Todos os 15 critérios só podem ser verificados depois do pareamento do
chip**, que por decisão de 06/08 é o **último** passo. É risco assumido.

✅ **A mitigação foi implementada em 06/08, antes das telas** (item 24). A
tabela `webhook_evento` guarda o corpo inteiro de todo evento **antes de
qualquer interpretação**, e as duas instâncias do Evolution já apontam para
ela. Assim o formato real é conferido com **uma** mensagem, em vez de com
catorze telas construídas em cima da documentação do Evolution 2.3.7 — que é
contra o que todo parser deste projeto foi escrito.

⚠️ **Sobre o item 5 (`tem_whatsapp`):** o campo só pode ser preenchido pelo
Evolution com a instância conectada, então fica `NULL` até o pareamento. Isso
**não** viola a regra "sem WhatsApp, não envia": na Fase 1 só se responde a
quem escreveu, e quem escreveu tem WhatsApp por demonstração. `NULL` é "não
verificado" e nunca deve ser lido como `false`.

---

## Riscos assumidos nesta fase

| Risco | Decisão |
|---|---|
| Baileys viola os Termos do WhatsApp | assumido pelo usuário. O canal de atendimento é receptivo e B2B — perfil de menor risco |
| Chip de teste pode cair | irrelevante nesta fase; é chip de teste |
| A caixa começa vazia (histórico não vem no QR) | aceito. O histórico que importa vem da ficha, não do balão |
| MoviChat tem 8.816 linhas sem teste e será reaproveitado | mitigado: o que for trazido para cá nasce com teste |
