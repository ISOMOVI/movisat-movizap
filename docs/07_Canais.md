# 07 — Canais (CFG_1.1)

**Implementada em 2026-08-05.** Primeira tela do MoviZap com conteúdo real
depois da `CFG_9.1`. É onde o WhatsApp é pareado e onde se vê o que está
conectado.

---

## 1. 🚨 Duas fontes, e não são a mesma coisa

```
banco       o que a Movisat DECIDIU que existe   (canal cadastrado)
Evolution   o que está acontecendo AGORA         (conectado, caiu, sem QR)
```

O banco é a verdade sobre **configuração**. O Evolution é a verdade sobre
**estado**.

**Guardar estado no banco e confiar nele é como se descobre, três dias
depois, que parou de chegar mensagem.** Por isso `GET /api/canais` consulta o
Evolution a cada chamada — o banco nunca é a fonte do estado atual.

O que o banco guarda é a **mudança**: `canal_evento`. E ele grava só quando o
estado muda. Gravar a cada leitura encheria a tabela de linhas iguais e
afogaria a única pergunta que ela existe para responder: **quando** mudou.

## 2. O vigia — e por que ele precisou existir

Na primeira versão, `canal_evento` só era escrito quando **alguém abria a
tela**. A auditoria pegou o problema no mesmo dia:

> Se ninguém abrisse a CFG_1.1 por três dias e o canal caísse no primeiro, a
> queda seria registrada no terceiro — no instante em que alguém olhou, não
> no instante em que aconteceu.

**Tabela de histórico que só avança quando observada não é histórico: é uma
foto tirada na hora errada.** E o pior tipo de erro, porque a resposta *parece*
certa.

`movizap/vigia.py` é um laço no processo do painel, a cada 60 s.

| Decisão | Por quê |
|---|---|
| Evolution fora do ar **não** grava `desconectado` | seria registrar uma queda que nunca houve, na tabela que existe para datar quedas |
| avisa só depois de 5 rondas sem resposta | rede piscando não é incidente |
| exceção na ronda **não** mata o laço | vigia que morre em silêncio é pior que vigia nenhum |
| roda no processo, não por cron | com 1 worker basta e não precisa de agendador |

⚠️ **Com mais de um worker isto quebra:** cada um vigiaria por conta própria e
a mesma mudança entraria em duplicidade. Aí o vigia sai para um processo só.

## 3. 🚨 `_uma_ronda` é síncrona, e isso não é detalhe

Na primeira versão era `async def`, e `rodar()` chamava
`await asyncio.to_thread(_uma_ronda)`.

`to_thread` roda função **comum** numa thread. Recebendo uma corrotina, ele a
executou na thread, ela devolveu o objeto-corrotina, e ninguém o aguardou.

**O vigia subiu, escreveu "ativo" no log, e não rodou uma ronda sequer.** O
único sinal foi um `RuntimeWarning` que não aparece em produção.

Apareceu porque tentei **provar** que funcionava, não porque reli o código.
`tests/teste_vigia.py::TestARondaEhSincrona` reprova se voltar a ser `async`.

## 4. O QR

Expira em **~60 s** no Baileys.

- a tela conta o tempo e **pede outro sozinha** — pedir F5 no meio do
  pareamento é o detalhe que faz a pessoa desistir;
- enquanto o QR está na tela, o estado é consultado **a cada 3 s**: só o
  Evolution sabe quando o celular leu;
- ao ver `conectado`, a tela chama `/confirmar`.

## 5. 🚨 As settings entram no pareamento, não no arranque

```python
groupsIgnore    = True    # grupo é Fase 3, e a IA nunca responde em grupo
syncFullHistory = False   # o histórico que importa vem da ficha, não do balão
readMessages    = False   # quem marca lido é o atendente
```

Aplicadas **antes** de a instância conectar, elas não pegam — e o silêncio faz
parecer que pegaram. Por isso vão em `confirmar_pareamento`, depois de o
Evolution responder `open`.

## 6. Estado desconhecido cai para `desconectado`

`canal_evento.estado` tem `CHECK` no banco. Se uma versão futura do Evolution
inventar um estado e gravarmos cru, o `INSERT` quebra **longe da causa**.

`canais.traduzir()` mapeia o vocabulário deles para o nosso, e há teste
garantindo que **todo** valor traduzido passa no CHECK — inclusive os que não
existem.

⚠️ **`indisponivel` é da tela, não do banco.** Quando o Evolution não
responde, a tela mostra "Evolution fora do ar" — dizer "desconectado" seria
mentira e mandaria o atendente esperar um QR que nunca vem.

## 7. Rotas

| Rota | Faz |
|---|---|
| `GET /api/canais` | canais do banco + estado ao vivo + marcos |
| `GET /api/canais/{id}/eventos` | o histórico |
| `POST /api/canais/{id}/conectar` | pede um QR novo |
| `POST /api/canais/{id}/confirmar` | aplica as settings depois de conectar |
| `POST /api/canais/{id}/desconectar` | desfaz o pareamento |

Todas exigem a tela **`CFG_1.1`** (permissão `admin`). Pedir QR muda estado
real no WhatsApp: não pode ser rota aberta.

## 8. Segredo

`EVOLUTION_API_KEY` vive só no `.env` (modo 600). Há teste garantindo que ela
não aparece em **nenhuma** resposta da API, e que `settings.dsn_seguro()` não
carrega a senha do banco.

⚠️ `settings.avisos()` é separado de `faltando()`: chave ausente **loga aviso
e deixa o painel subir**. Derrubar o painel inteiro porque uma tela não vai
funcionar seria trocar um problema por um maior.

## 9. O que esta tela NÃO faz

- **não envia mensagem** — Fase 1 é receber. Quando o envio entrar, entra no
  `evolution.py`, com ritmo e teto;
- **não cadastra canal** — canal nasce por migração. Canal criado pela tela
  seria canal sem código, e o registro de telas perderia sentido;
- **não trata o canal `informativos`** — Fase 2.

## 10. Lição que ficou dos testes

A primeira versão de `teste_vigia.py` rodou contra o canal **de produção** com
o Evolution simulado, e deixou no histórico duas transições para `conectado`
que nunca aconteceram — na tabela cujo único propósito é não mentir sobre
isso.

**Teste que escreve em tabela de produção precisa da própria linha e precisa
levar embora o que criou.** Por isso `_uma_ronda` ganhou `apenas_canal_id`:
sem ele a ronda varre todos os canais ativos, e um teste que finge
"conectado" contamina o real.

---

## Decisões

### O estado vem do Evolution, o histórico fica no banco (05/08)
```
Objetivo:     saber o que está acontecendo agora E quando mudou
Hoje:         = o objetivo. GET consulta ao vivo; canal_evento grava mudança
Por quê:      estado guardado no banco envelhece sem avisar, e é assim que se
              descobre tarde demais que parou de chegar mensagem
Reavaliar se: o Evolution passar a mandar webhook de mudança de conexão --
              aí o vigia vira ouvinte em vez de perguntador
```

### Vigia dentro do processo do painel (05/08)
```
Objetivo:     histórico avançar mesmo sem ninguém olhando a tela
Hoje:         = o objetivo. Laço a cada 60 s, no processo do uvicorn
Por quê:      antes só a tela escrevia; a queda ficava datada na hora em que
              alguém abriu a CFG_1.1, não na hora em que houve
Reavaliar se: o serviço rodar com mais de um worker -- aí cada um vigia por
              conta e a mesma mudança entra duas vezes
```

### Canal nasce por migração, não pela tela (05/08)
```
Objetivo:     todo canal existir de propósito, com histórico desde o começo
Hoje:         = o objetivo. A 003 cadastra o `atendimento` e grava o estado
              inicial explícito
Por quê:      sem a linha inicial o histórico começaria na primeira consulta
              da tela, e "desde quando está assim?" responderia a hora errada
Reavaliar se: houver mais de um canal por semana entrando -- hoje são dois no
              total, e um deles é Fase 2
```
