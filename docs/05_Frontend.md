# 05 — Frontend

**Escrito em 2026-08-05**, quando o esqueleto do painel subiu. Cobre o que os
outros documentos não cobrem: o sistema de design, o contrato entre frontend e
backend, e como se constrói e publica.

Herda `00_Metodologia.md`. Onde divergir, a metodologia ganha.

---

## Stack

**Vue 3 + Vite 5**, só web. Servido pelo próprio FastAPI: `movizap/main.py`
monta `/assets` e devolve `frontend/dist/index.html` para toda rota que não
seja `/api`. Não há segundo processo, não há segunda porta, não há CORS.

| Dependência | Por quê |
|---|---|
| `vue` | decidido em 04/08 — inbox ao vivo é mais pesada que painel de abas |
| `vue-router` | rota é o que carrega o código da tela |
| `bootstrap-icons` | o backend já manda `icone: "bi-chat-dots"` no registro |

**Sem biblioteca de store.** O estado é um `reactive()` exportado
(`src/estado/sessao.js`). Proposital: quem mantém este projeto escreve Python,
e `defineStore` + `storeToRefs` é vocabulário a mais para resolver o que 40
linhas resolvem.

```
Objetivo:     estado de sessão legível por quem não vive em JavaScript
Hoje:         = o objetivo. reactive() exportado, sem Pinia
Por quê:      cada conceito a mais é custo permanente de manutenção, e hoje o
              estado é usuário + telas + início da sessão
Reavaliar se: a caixa de entrada ao vivo (conversas, websocket, não-lidos)
              começar a precisar de estado compartilhado entre telas distantes
```

---

## 1. O contrato: o frontend DESENHA, não decide

🚨 A regra mais importante deste documento.

- O menu vem de `GET /api/telas`. Título, rota e ícone são do backend.
  `MenuLateral.vue` **não tem uma linha** de "se for admin, mostra".
- Tela nova nasce em `movizap/telas.py`. Só depois ganha rota aqui.
- A guarda do router nega navegação para código que não veio na lista — isso é
  **cortesia**, não segurança. A barreira que vale é `requer_tela()` no
  backend, que checa de novo em toda requisição.

Se um dia o menu e a tela discordarem, quem está errado é o frontend.

## 2. Sistema de design — item 17 do escopo

Três arquivos em `src/estilo/`, nesta ordem de import:

| Arquivo | O que é |
|---|---|
| `tokens.css` | cor, tipografia, espaçamento, forma, movimento — claro e escuro |
| `base.css` | reset curto e comportamento dos elementos |
| `componentes.css` | `.botao`, `.campo`, `.cartao`, `.chip`, `.aviso`, `.tabela`, `.vazio` |

**Regra:** nenhuma tela escreve cor, tamanho de fonte, raio ou espaçamento na
mão. Se um valor não existe em `tokens.css`, ou ele vira token, ou não entra.
Peça nova nasce em `componentes.css`, não dentro de um `.vue`.

Existe desde a primeira tela de propósito: improvisar tela a tela é exatamente
o que dá cara de painel interno feito às pressas — e depois não se conserta,
porque conserto vira reescrita de tudo.

🚨 **Os VALORES dos tokens não são escolha deste projeto.** Eles vêm do
`theme.css` do MoviChat, que é o padrão visual da casa — ver
`/home/claude/docs/02_Padrao_Visual.md`, que vale para os quatro painéis.

⚠️ **Correção de 05/08.** O MoviZap nasceu em 04/08 com a paleta do MoviServer
(GitHub: `#0d1117`, `#1f6feb`) — próxima da do MoviChat, mas diferente. Isso
foi errado e está corrigido. *Quase* a mesma cor lê como defeito, não como
escolha. A arquitetura de tokens salvou o conserto: foi troca de valor num
arquivo, não reescrita de tela.

O menu lateral usa tokens próprios (`--menu-*`) porque é **escuro nos dois
temas** — é a assinatura do MoviChat e não segue claro/escuro.

**Tema.** `<html data-tema="claro|escuro">`. O valor é sempre resolvido, nunca
`sistema`, então o CSS tem um caso por tema e zero duplicação. A preferência
(`sistema` / `claro` / `escuro`) fica em `localStorage`.

⚠️ **Uma duplicação é aceita:** o cálculo do tema roda inline no `<head>` do
`index.html`, antes da primeira pintura. Sem isso o painel pisca branco a cada
carga para quem usa escuro — e este painel fica aberto o dia inteiro. Mudou a
regra em `src/estado/tema.js`, muda lá também.

## 3. Cliente HTTP — um lugar só

`src/api/cliente.js` é o único módulo que fala com o backend. Três coisas
valem para toda requisição, sem depender de disciplina:

1. o token vai no `Authorization`;
2. o `X-Request-Id` da resposta alimenta a barra de status;
3. **401 encerra a sessão em UM lugar** — espalhar isso pelas telas é como se
   perde sessão expirada virando tela em branco.

🚨 **200 com corpo que não é JSON vira erro explícito.** É o sintoma de rota de
API inexistente caindo no `index.html` da SPA. O backend agora responde 404 em
JSON para `/api/*` desconhecido, e o cliente ainda checa — as duas pontas,
porque este é o erro que aparece longe da causa.

## 4. Barra de status — critério de pronto nº 10

Mora em `App.vue`, **fora do `<RouterView>`**. Assim vale em toda tela sem que
nenhuma tela precise lembrar de incluí-la: o critério de pronto não pode
depender da disciplina de quem escrever a próxima tela.

Mostra: código da tela · quem está logado · duração da sessão · indicador de
requisição em voo · `req_id` · data/hora.

O `req_id` é o que muda o suporte: o atendente lê `req a3f9` na tela e o
journal da VPS tem `req=a3f9` naquela requisição exata. Sem isso, o que se
procura no log é "por volta das 14h, na tela de conversa".

## 4b. Tela de login

Estrutura, logo e tamanhos são os mesmos dos outros três painéis — ver
`/home/claude/docs/02_Padrao_Visual.md`. O que é específico daqui:

- a **proteção da rota** (limite de tentativas, mensagem única, teto de
  tamanho do corpo) está em `/home/claude/docs/01_Seguranca_Login.md`;
- **"Esqueci minha senha" está desabilitado** e continua assim até o
  `CAD_2.1` existir: hoje o usuário vem do `.env` e não há onde gravar senha
  nova, nem envio de e-mail.

## 5. Estado das telas (2026-08-05)

| Situação | Telas |
|---|---|
| **Implementada** | `CFG_9.1` Registro de telas — a única com backend pronto |
| **Registrada, roteada, sem conteúdo** | as outras 11 de fase 1 |
| **Código reservado, sem rota** | `ATD_3.1` · `ATD_4.1` · `CFG_2.2` · `REL_1.1` |

O placeholder diz **o que vem ali e o que trava**. Dizer "em breve" sem dizer o
motivo foi como o MoviServer ficou com 4 telas em branco sem ninguém saber por
quê.

## 6. Construir e publicar

```bash
cd /home/claude/movizap_painel/frontend
npm ci                 # primeira vez: npm install
npm run build          # gera frontend/dist
systemctl --user restart movizap.service
./venv/bin/python scripts/verificar_ao_vivo.py   # prova pelo estado
```

🚨 **`FRONTEND` em `main.py` e `outDir` em `vite.config.js` são o mesmo
contrato.** Mudar um sem o outro derruba o painel **sem** derrubar a API: o
serviço continua `active` e nada acusa. `tests/teste_frontend.py` cobre isso.

⚠️ `frontend/dist` e `frontend/node_modules` estão fora do git. `dist` é
reconstruível; versionar bundle minificado suja todo diff e mente sobre o que
mudou.

⚠️ **O processo escuta em `127.0.0.1:8008`; quem publica é o nginx.** O painel
está em **`https://movizap.movisat.com.br`**. O túnel SSH
(`ssh -L 8008:127.0.0.1:8008 vps`) continua servindo para depurar sem passar
pelo nginx, mas não é mais o caminho de uso.

## 7. O que este frontend NÃO tem

> 🚨 **ESTA SEÇÃO DESCREVIA UM ESQUELETO QUE NÃO EXISTE MAIS.** Até 12/08 ela
> afirmava três coisas falsas: que não havia banco, que `ATD_1.1`/`ATD_1.2`
> eram placeholder e que o acesso era por túnel SSH. Doc que descreve um
> estágio já superado é pior que doc faltando — quem lê para de procurar.
> Hoje são 31 tabelas, 18 telas registradas e o painel está publicado.

Está escrito para não ser redescoberto:

- **nenhum teste de frontend** — não existe runner de JS no projeto. O `build`
  pega import quebrado e erro de template, e `tests/teste_frontend.py` prova
  que o `dist` está onde o `main.py` procura. Nada disso pega **lógica**: o
  recorte da busca (`partir`/`marcar` na `CaixaDeEntrada.vue`) e a navegação
  entre ocorrências não têm teste, e é o maior buraco de cobertura do painel;
- **nenhuma verificação em navegador automatizada** — o `verificar_ao_vivo.py`
  prova a API e o HTML servido, não a renderização. Tela nova continua exigindo
  um humano abrindo e clicando;
- **nenhuma rolagem virtual** — a conversa desenha todos os balões de uma vez.
  O teto é de 1.000 mensagens (`conversas.TETO_MENSAGENS_NA_TELA`) e a maior
  conversa da base tem 130, então sobra folga; se uma chegar perto do teto, o
  custo é do **navegador**, não da API, e a saída é rolagem virtual — não
  baixar o teto de volta.

## 8. Documentos irmãos

Estes valem para os **quatro painéis**, não só para o MoviZap. Se algo aqui
divergir deles, eles ganham:

| Documento | Assunto |
|---|---|
| `/home/claude/docs/00_Commit_e_Segredos.md` | git, segredo em repositório, trava do commit automático |
| `/home/claude/docs/01_Seguranca_Login.md` | limite de tentativas, mensagem única, IP atrás do nginx |
| `/home/claude/docs/02_Padrao_Visual.md` | paleta, menu escuro, tela de login, os 16px do iOS |
