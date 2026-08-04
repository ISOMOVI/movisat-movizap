# 00 — Metodologia

Como se trabalha no MoviZap.

**Este documento herda `moviserver/docs/01_Metodologia.md` e `fpsl_weso/docs/fpsl/00_Metodologia.md` por inteiro.** Não se inventa processo novo. Aqui ficam **apenas** as regras que não existiam antes porque os projetos anteriores não tinham webhook, não tinham telefone como chave e não tinham base própria alimentada por terceiro.

Se este doc divergir dos herdados em algo geral, **os herdados ganham**.

---

## O que vale igual, sem repetir aqui

- **VPS é a única fonte de verdade.** Espelho local é leitura.
- **Deploy:** diff normalizando CRLF → backup → scp via PowerShell → re-diff → `py_compile` → restart → `is-active` + journal.
- **Validar antes de gravar**, nunca depois. Montar em memória, validar o candidato, só então escrever.
- **Todo lote começa com 1 caso, e a confirmação é reler o estado — nunca o HTTP.**
- **Nunca credencial em linha de comando.** Nunca segredo em log.
- **Permissão vive no backend**, em toda rota. Conta nova nasce sem nada: falha fechado.
- **Um doc por assunto. Reescrever, não acrescentar.** Decisão no formato de 4 linhas.
- **Verificar antes de perguntar.**

🚨 **`py_compile` não pega import faltando nem símbolo errado.** Aconteceu 4 vezes em 29/07. Conferir o símbolo no namespace do módulo e **rodar os testes**.

---

## 1. Idempotência de webhook — a regra número um deste projeto

O Evolution **reenvia** e **não garante ordem**. Um webhook processado duas vezes duplica a conversa do cliente na tela do atendente.

```
Toda mensagem que entra é gravada por `id_externo`, com UNIQUE no banco.
Reentrega é conflito esperado: ignora e responde 200.
```

- **Responder 200 rápido, processar depois.** Se o processamento demorar, o Evolution considera falha e reenvia — e aí o problema piora sozinho.
- **Nunca deduplicar por conteúdo ou timestamp.** Cliente manda "ok" duas vezes de propósito, e isso é legítimo.
- Fora de ordem é normal: a ordenação da tela é por `criada_em` do provedor, não por ordem de chegada.

## 2. Telefone é chave, e telefone brasileiro é sujo

É a mesma lição da placa na WESO, com outro nome. A faxina ajuda; **o que imuniza é a leitura tolerante**.

- Grava-se **sempre** o bruto e o normalizado (E.164). O bruto nunca se perde.
- Busca **nunca** por igualdade do que chegou — sempre pelo normalizado.
- O nono dígito é o caso clássico: `+551899811xxxx` e `+55189811xxxx` são a mesma pessoa. O normalizador precisa resolver os dois sentidos.
- **`tem_whatsapp` é um campo, não uma suposição.** Verificado pelo Evolution, com data. `NULL` significa "não verificado" e é diferente de `false`.

🚨 Sem isso, o cliente escreve e o sistema responde que ele não é cliente.

## 3. O sync nunca apaga o que não é dele

A base cadastral tem duas origens no mesmo lugar.

| `origem` | Quem manda | O sync pode |
|---|---|---|
| `harmonit` | o Harmonit | criar, atualizar, **inativar** |
| `movizap` | nós | **nada — é intocável** |

- Sync é **upsert por `harmonit_id`**. Nunca "apaga tudo e reinsere".
- Registro que sumiu do Harmonit vira `ativo = false`. **Não se apaga cadastro.**
- Toda execução grava: quando, origem (cron ou botão), quantos lidos, criados, atualizados, erros.

🚨 **O Harmonit responde "encontrado" como `list` e "não encontrado" como `dict`** — e o `dict` é *truthy*. Tratar a resposta como verdade fez o sistema concluir que todo CPF já existia, inclusive um inventado. O sync precisa checar o **tipo** da resposta, não a veracidade dela.

🚨 **Resposta vazia não é falha.** A numeração do Harmonit tem buracos. Separar `ok` / `vazio` / `erro` — sem isso o painel acusa 76% de falha num sistema saudável.

## 4. Escrita no WhatsApp

O canal é irreversível: mensagem enviada não volta.

- **Disparo em lote começa com 1**, e a confirmação é o estado de entrega, não o retorno do POST.
- **Ritmo, não rajada.** Intervalo entre envios e teto por hora são regra de código, não de disciplina humana.
- **Nunca enviar para `tem_whatsapp = false`.** Falha silenciosa em cobrança só aparece no caixa.

## 5. Segredo

Igual aos outros projetos, com um acréscimo que já custou caro:

🚨 **Silenciar `httpx` / `httpcore` / `hpack` desde a primeira linha.** Foi assim que a chave da WESO apareceu num log — o cliente HTTP imprime o header `Authorization` em DEBUG.

- Chave de LLM sai do `.env`, lida por **um único gateway**. Nenhum outro módulo sabe que ela existe. Trocar a chave é uma linha no `.env` + restart.
- Se aparecer em tela de configuração, mostra-se `sk-...a3f9`. Nunca o valor.

## 6. Testes — o que precisa existir desde o começo

O MoviChat tem **8.816 linhas e zero teste**, e é a peça mais reaproveitada aqui. Não repetir.

| Assunto | Por que desde o dia 1 |
|---|---|
| Normalização de telefone | é a chave de tudo; erro aqui é invisível e caro |
| Idempotência de webhook | só se testa simulando reentrega |
| Máquina de estados da conversa | transição inválida tem que ser impossível, não improvável |
| Leitura do Harmonit | o formato duplo (`list`/`dict`) precisa de fixture real |
| Contrato da IA | as 168 perguntas reais, incluindo as negativas |

🚨 A asserção precisa detectar **valor constante**, não só `NULL`. `bateria = 0` em 100% das linhas passa batido num teste de nulidade.

## 7. Antes de começar qualquer sessão

1. Ler o **MIOLO** de `Proximos_Passos.md`.
2. Conferir drift local × VPS antes de editar.
3. Verificar antes de perguntar.
4. Item já decidido não volta como pergunta — mas checar o `Reavaliar se`.
