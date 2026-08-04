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

## ❌ Fica fora — e está escrito

| Item | Volta em |
|---|---|
| Canal **Informativos** e disparo em massa | Fase 2 |
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

**Não conta como pronto:** funcionar no teste unitário e não ter passado por WhatsApp real. Foi assim que o MoviBot ficou 6 semanas "pronto" sem nunca ter atendido ninguém.

---

## Riscos assumidos nesta fase

| Risco | Decisão |
|---|---|
| Baileys viola os Termos do WhatsApp | assumido pelo usuário. O canal de atendimento é receptivo e B2B — perfil de menor risco |
| Chip de teste pode cair | irrelevante nesta fase; é chip de teste |
| A caixa começa vazia (histórico não vem no QR) | aceito. O histórico que importa vem da ficha, não do balão |
| MoviChat tem 8.816 linhas sem teste e será reaproveitado | mitigado: o que for trazido para cá nasce com teste |
