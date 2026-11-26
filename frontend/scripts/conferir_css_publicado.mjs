/* 🔴 25/11, A 12ª CONFERÊNCIA SAIU DAQUI, e o motivo tem de ficar escrito.
   Ela exigia que nenhum arquivo de painel declarasse a família (`card__*`,
   `coluna*`, `painel__*`) -- guarda certa ENQUANTO a casa comum
   (`src/estilo/painel.css`) existia. A casa comum foi revertida: ela trocava as
   declarações de quatro telas de uma vez (a `PainelAba.vue` serve o Contratual,
   o Pós-venda e as duas do Financeiro) por corpos escritos à mão, e o estrago
   apareceu na tela dele, não em teste nenhum -- porque não há navegador headless
   aqui para medir layout.
   ⚠️ Com isso a CÓPIA de CSS entre telas volta a não ter trava. Isso é dívida
   declarada, não descuido: a casa comum só volta com aprovação dele e com uma
   forma de validar layout de verdade antes de publicar. */
/*
 * CONFERE O CSS QUE O NAVEGADOR RECEBE — roda depois do `vite build`.
 *
 * 🚨 POR QUE ISTO EXISTE, e os três defeitos que ele teria pego, todos em 05/11:
 *
 *   1. `max-width: 420px` herdado em silêncio. A `.modal__caixa` da CASA
 *      (`estilo/componentes.css`) impõe 420px, e a regra escopada do painel
 *      declarava `width` mas não `max-width` — `max-width` é um TETO aplicado
 *      depois de `width`, qualquer que seja a especificidade. O modal do card
 *      ficava com 420px e as duas colunas empilhavam. Ele apontou TRÊS vezes.
 *   2. Ordem de cascata. As regras do `.modal__painel` estavam ANTES das de
 *      `.modal__recados`, com a mesma especificidade — a de baixo ganha, e o
 *      cabeçalho do painel caía para `--txt-sm`.
 *   3. Doze tokens fora do `:root`. Um `}` no lugar errado pôs `--menu-*`,
 *      `--sombra-*`, `--foco` e os `--conversa-*` dentro de uma classe de
 *      TELA. O menu perdeu o fundo escuro e o sistema perdeu as sombras.
 *
 * ⚠️ NENHUM DOS TRÊS É ALCANÇÁVEL PELA SUÍTE: o jsdom não aplica `<style
 * scoped>` nem a folha global, então o vitest mede estrutura e texto, nunca o
 * resultado visual. Nas três vezes quem achou foi ELE, abrindo a tela.
 *
 * 🚨 E ESTE SCRIPT NÃO "PULA" QUANDO NÃO ACHA O `dist`: ele FALHA. Teste que
 * se declara verde sem ter medido nada é a pior espécie — e esta casa já tem
 * dois arquivos nesse estado no FPSL, contados no placar sem rodar.
 */
import { readFileSync, readdirSync, existsSync, statSync } from 'node:fs'
import { join } from 'node:path'

const PASTA = join(process.cwd(), 'dist', 'assets')

function cssPublicado() {
  if (!existsSync(PASTA)) {
    falhar(`não achei ${PASTA}. Rode \`npm run build\` antes.`)
  }
  const arquivos = readdirSync(PASTA).filter((f) => f.endsWith('.css'))
  if (!arquivos.length) falhar(`nenhum .css em ${PASTA}.`)
  /* ⚠️ Concatena TODOS: o `index-*.css` é o principal, mas um pedaço pode sair
     em outro arquivo se o Vite dividir. Medir só um daria falso verde. */
  return arquivos.map((f) => readFileSync(join(PASTA, f), 'utf8')).join('\n')
}

const erros = []
function falhar(msg) { erros.push(msg) }

/* Devolve o corpo da PRIMEIRA regra cujo seletor casa, e a posição dela. */
function regra(css, seletor) {
  /* o `scoped` do Vue publica `.classe[data-v-xxxxxxx]` */
  const re = new RegExp(
    seletor.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
      + '(\\[data-v-[0-9a-f]+\\])?\\s*\\{([^}]*)\\}')
  const m = css.match(re)
  return m ? { corpo: m[2], pos: m.index } : null
}

function prop(corpo, nome) {
  const m = corpo.match(new RegExp('(?:^|;)\\s*' + nome + '\\s*:\\s*([^;]+)'))
  return m ? m[1].trim() : null
}

/* ------------------------------------------------------------------ 1 */
function oDialogoDoPainelNaoHerdaOTeto(css) {
  const r = regra(css, '.painel__dialogo')
  if (!r) return falhar('.painel__dialogo não existe no CSS publicado.')
  const mw = prop(r.corpo, 'max-width')
  if (!mw || !mw.includes('1000px')) {
    falhar(`.painel__dialogo max-width = ${mw} — tem de declarar 1000px, `
           + 'senão herda os 420px da .modal__caixa da casa e o modal '
           + 'aparece com UMA coluna.')
  }
  if (prop(r.corpo, 'padding') !== '0') {
    falhar(`.painel__dialogo padding = ${prop(r.corpo, 'padding')} — tem de ser 0, `
           + 'senão as faixas não encostam na borda.')
  }
  const ov = prop(r.corpo, 'overflow')
  if (ov !== 'hidden') {
    falhar(`.painel__dialogo overflow = ${ov} — tem de ser hidden, senão a `
           + 'caixa rola junto com o corpo (duas rolagens).')
  }
}

/* ------------------------------------------------------------------ 2 */
function oPainelVemDepoisDasRegrasAntigas(css) {
  /* 🚨 COMPARA DENTRO DO MESMO `data-v`, e isto mudou em 05/11: depois de o
     diálogo virar componente, há DUAS regras `.modal__painel` no bundle, uma
     por componente. Comparar a primeira com o `h3` do OUTRO componente acusa
     conflito que não existe -- `scoped` com hashes diferentes não se cruzam --
     e, pior, podia ficar VERDE por sorte lendo metades de componentes
     distintos.
     ⚠️ A regra que esta conferência guarda continua valendo dentro de um
     componente: mesma especificidade, a de baixo ganha. */
  /* ⚠️ O `data-v` VAI NO ULTIMO SELETOR SIMPLES, e nao no primeiro: o
     `scoped` do Vue publica `.modal__recados h3[data-v-xxx]`. Procurar
     `.modal__recados[data-v-xxx] h3` nao acha nada -- e o "nao existe no CSS
     publicado" seria um verde disfarcado de vermelho. */
  const h3 = [...css.matchAll(
    /\.modal__recados\s+h3\[data-v-([0-9a-f]+)\]/g)]
  if (!h3.length) {
    return falhar('.modal__recados h3 não existe no CSS publicado.')
  }
  for (const m of h3) {
    const hash = m[1]
    const painel = css.search(
      new RegExp('\\.modal__painel\\[data-v-' + hash + '\\]'))
    if (painel < 0) {
      /* ⚠️ O componente pode não ter `.modal__painel` -- aí não há empate
         para desempatar, e a conferência não tem o que dizer. */
      continue
    }
    if (painel < m.index) {
      falhar(`.modal__painel está ANTES de .modal__recados h3 no escopo `
             + `data-v-${hash}. Mesma especificidade: a de baixo ganha, e o `
             + 'cabeçalho do painel volta a cair para --txt-sm.')
    }
  }
}

/* ------------------------------------------------------------------ 3 */
function osTokensDeSistemaEstaoNoRoot(css) {
  /* 🚨 Estes doze saíram do `:root` em 05/11 por um `}` no lugar errado. */
  const doze = [
    '--menu-fundo', '--menu-texto', '--menu-texto-forte', '--menu-hover',
    '--menu-borda', '--sombra-1', '--sombra-2', '--foco',
    '--conversa-raio', '--conversa-bico', '--conversa-lida',
    '--conversa-nota-texto',
  ]
  /* o corpo do `:root` do tema (o que tem as cores) */
  const roots = [...css.matchAll(/:root\s*\{([^}]*)\}/g)].map((m) => m[1]).join('\n')
  for (const t of doze) {
    if (!roots.includes(t + ':')) {
      falhar(`${t} não está em nenhum :root do CSS publicado — se ele caiu `
             + 'dentro de uma classe de tela, o resto do sistema fica sem ele.')
    }
  }
  /* e a escala do painel tem de ter SÓ os cinco --txt-* */
  const esc = regra(css, '.escala-operacao')
  if (!esc) return falhar('.escala-operacao não existe no CSS publicado.')
  const declaradas = [...esc.corpo.matchAll(/(--[a-z0-9-]+)\s*:/g)].map((m) => m[1])
  const intrusas = declaradas.filter((d) => !d.startsWith('--txt-'))
  if (intrusas.length) {
    falhar('.escala-operacao declara o que não é escala: ' + intrusas.join(', ')
           + '. Era o sintoma do `}` fora de lugar.')
  }
}

/* ------------------------------------------------------------------ 4 */
function osTresDialogosNaoEmpatamNoZIndex(css) {
  /* 🚨 O DEFEITO DE 05/11 que ele viu como "as observações não estão
     abrindo": os três diálogos do painel são IRMÃOS no mesmo contexto de
     empilhamento e usavam o MESMO `z-index`. Com empate, o desempate é a
     ORDEM DO DOCUMENTO — e o card aberto é o último do template, então
     pintava por cima. O modal das observações abria, ficava focado, recebia
     `Escape`, e era INVISÍVEL.
     ⚠️ E nenhum teste de tela alcança isto: o jsdom não faz layout nem
     pintura, e um modal 100% coberto passa como "aberto". */
  const base = regra(css, '.modal')
  if (!base) return falhar('.modal não existe no CSS publicado.')
  if (!prop(base.corpo, 'z-index')) {
    falhar('.modal não declara z-index — os diálogos voltariam a empatar.')
  }
  for (const [sel, soma] of [['.modal--recados', 10], ['.modal--aviso', 20],
                            ['.modal--disparo', 30]]) {
    const r = regra(css, sel)
    if (!r) {
      falhar(`${sel} não existe no CSS publicado. Sem ele o diálogo empata `
             + 'com o card aberto e desaparece atrás dele.')
      continue
    }
    const z = prop(r.corpo, 'z-index')
    if (!z || !z.includes(`+ ${soma}`)) {
      falhar(`${sel} z-index = ${z} — tem de somar ${soma} ao --z-modal, `
             + 'senão a ordem de empilhamento volta a depender da ordem do '
             + 'template.')
    }
  }
}

/* ------------------------------------------------------------------ 5 */
function oDialogoDoChamadoTemTetoProprioENaoEmpata(css) {
  /* 🚨 MESMO DEFEITO DE 05/11, OUTRO DIALOGO: a `.modal__caixa` da casa
     impoe `max-width: 420px`, e teto nao se vence com especificidade -- so
     redeclarando. Um dialogo que declara `width` e esquece `max-width`
     aparece com UMA coluna, e foi o que ele apontou tres vezes.
     ⚠️ O jsdom nao faz layout: nenhum teste de tela alcanca isto. */
  const r = regra(css, '.painel__dialogo--chamado');
  if (!r) {
    return falhar('.painel__dialogo--chamado não existe no CSS publicado — '
                  + 'o diálogo do chamado herdaria os 420px da casa.');
  }
  const mw = prop(r.corpo, 'max-width');
  if (!mw || !mw.includes('900px')) {
    falhar(`.painel__dialogo--chamado max-width = ${mw} — tem de declarar `
           + '900px, senão herda os 420px da .modal__caixa e o diálogo do '
           + 'chamado aparece com UMA coluna.');
  }
  const z = regra(css, '.modal--chamado');
  if (!z || !prop(z.corpo, 'z-index')) {
    falhar('.modal--chamado não declara z-index — o diálogo do chamado '
           + 'empataria com o card aberto e desapareceria atrás dele.');
  }
}


/* ------------------------------------------------------------------ 6 */
function osControlesDeRolagemFicamNaCamadaCerta(css) {
  /* 🚨 06/11, a camada NOVA. A barra grudada no alto e as faixas da borda
     ficam POR CIMA do quadro -- e camada nova e justamente o tipo de regra que
     some numa cascata sem nenhum teste de tela notar: o jsdom nao pinta.

     ⚠️ E ha um segundo defeito possivel, pior: a faixa esconde-se em
     `@media (hover: none)` para nao comer a area de arrastar no celular. Se
     essa regra ESCAPAR da media query, a faixa desaparece para TODOS -- foi
     exatamente o que um `max-width` global fez com o modal em 05/11. */
  const barra = regra(css, '.barrarolo')
  if (!barra) {
    return falhar('.barrarolo não existe no CSS publicado — a barra de '
                  + 'rolagem do quadro não subiu.')
  }
  if (!/position:\s*sticky/.test(barra.corpo)) {
    falhar('.barrarolo não é `sticky` — ela voltaria a ficar no pé do quadro, '
           + 'que é a queixa que ela existe para resolver.')
  }
  const zb = prop(barra.corpo, 'z-index') || ''
  if (!zb.includes('--z-rolagem')) {
    falhar('.barrarolo não usa a escala `--z-rolagem` (achei ' + (zb || 'nada')
           + '). Número cru funciona hoje e não acompanha a escala amanhã.')
  }

  const faixa = regra(css, '.borda')
  if (!faixa) {
    return falhar('.borda não existe no CSS publicado — as faixas de rolagem '
                  + 'não subiram.')
  }
  const zf = prop(faixa.corpo, 'z-index') || ''
  if (!zf.includes('--z-rolagem')) {
    falhar('.borda não usa a escala `--z-rolagem` (achei ' + (zf || 'nada') + ').')
  }
  if (!/pointer-events:\s*none/.test(faixa.corpo)) {
    falhar('.borda não tem `pointer-events: none` — ela cobriria o quadro '
           + 'inteiro e nenhum card seria clicável.')
  }

  /* 🚨 O `display:none` da faixa TEM de estar dentro de `@media (hover: none)`.
     Fora dela, a faixa desaparece para todo mundo. */
  const escondido = [...css.matchAll(/\.borda(\[[^\]]*\])?\s*\{\s*display:\s*none/g)]
  for (const m of escondido) {
    const antes = css.slice(0, m.index)
    const abriu = antes.lastIndexOf('@media')
    const fechou = antes.lastIndexOf('}')
    if (!(abriu > fechou)) {
      falhar('`.borda { display: none }` está FORA de uma media query no CSS '
             + 'publicado: as faixas de rolagem ficariam invisíveis para '
             + 'todos, em qualquer tela.')
    }
  }
}


/* ------------------------------------------------------------------ 7 */
function oAvisoDaEtapaEhCurtoEComBotaoNoCentro(css) {
  /* 🔵 11/11, dele: *"Reduzir o tamanho do modal e centralizar botão"*.
     🚨 AS DUAS COISAS SÃO CSS E NENHUM TESTE DE TELA AS VÊ -- o jsdom não faz
     layout, então um `max-width` perdido ou um rodapé que volta ao
     `space-between` passam verdes na suíte e aparecem na cara dele.
     ⚠️ O botão à esquerda não era um `text-align` esquecido: é o
     `justify-content: space-between` do rodapé da casa, que com UM filho
     encosta o único botão na borda. */
  const r = regra(css, '.modal__caixa--curta');
  if (!r) {
    return falhar('.modal__caixa--curta não existe no CSS publicado — o aviso '
                  + 'da etapa herdaria os 420px da .modal__caixa da casa.');
  }
  const mw = prop(r.corpo, 'max-width');
  if (!mw || !mw.includes('22rem')) {
    falhar(`.modal__caixa--curta max-width = ${mw} — tem de ser 22rem: é o `
           + 'tamanho que ele pediu, e sem declarar vale o teto da casa.');
  }
  const rod = regra(css, '.modal--aviso .modal__rodape');
  if (!rod) {
    return falhar('.modal--aviso .modal__rodape não existe no CSS publicado — '
                  + 'o rodapé da casa é `space-between` e, com um botão só, '
                  + 'joga o Ok para a esquerda.');
  }
  const jc = prop(rod.corpo, 'justify-content');
  if (jc !== 'center') {
    falhar(`.modal--aviso .modal__rodape justify-content = ${jc} — tem de ser `
           + 'center, senão o Ok volta para a borda esquerda.');
  }
}


/* ------------------------------------------------------------------ 8 */
function todaVarianteDePilulaTemAPilulaBase(css) {
  /* 🚨 NASCEU DE UM DEFEITO MEU EM 11/11. A `.pilula` é **scoped por
     componente** nesta casa -- ela não existe em `estilo/*.css`, e cada tela que
     a usa declara a sua. Publiquei a `ChecklistDeCards` usando a classe sem
     declarar: o selo saiu **sem forma, sem fundo e sem raio**. Não quebra, não
     avisa, e nenhum teste de tela alcança -- o jsdom não faz layout.

     A invariante que dá para medir no CSS publicado: todo escopo que declara uma
     VARIANTE (`--alerta`, `--pronto`, `--neutra`, `--forte`, `--origem`) tem de
     declarar também a BASE no mesmo escopo. Variante sem base é cor sem selo. */
  const escoposComVariante = new Set();
  const escoposComBase = new Set();
  const re = /\.pilula(--[a-z]+)?\[data-v-([0-9a-f]+)\]/g;
  let m;
  while ((m = re.exec(css)) !== null) {
    if (m[1]) escoposComVariante.add(m[2]);
    else escoposComBase.add(m[2]);
  }
  if (!escoposComBase.size) {
    return falhar('.pilula não aparece no CSS publicado — ou a classe mudou de '
                  + 'nome, ou nenhuma tela a declara (e todas que a usam estão '
                  + 'com o selo sem estilo).');
  }
  for (const escopo of escoposComVariante) {
    if (!escoposComBase.has(escopo)) {
      falhar(`o escopo data-v-${escopo} declara uma VARIANTE de .pilula e não `
             + 'declara a base — o selo fica com cor e sem forma. A `.pilula` é '
             + 'scoped por componente: cada tela que a usa declara a sua.');
    }
  }
}

/* ------------------------------------------------------------------ 9 */
function aBarraDeEtapasRolaENaoQuebra(css) {
  /* 🔵 11/11, dele: *"a barra interna de mudar etapa nos cards dessas
     etapas"*.
     🚨 A BARRA É UMA LINHA QUE ROLA, E ISSO É SÓ CSS. Com as 10 etapas do
     Financeiro, um `flex-wrap` que volte a `wrap` quebra a barra em três
     fileiras e empurra o corpo do card para fora da tela -- e a trava de
     tela fica VERDE, porque o jsdom não faz layout e `scrollWidth` é sempre
     0 lá. */
  /* 🔵 12/11, dele: *"pode ocultar essa barra ou transformá-la em lista,
     como no OP"* → *"A"*. A `.trilha` saiu do componente, então a conferência
     dela foi TROCADA, não apagada: apagar deixaria o controle de mover etapa
     sem nenhuma guarda de CSS publicado, e foi uma falta de forma que fez a
     barra nascer em 11/11.
     📏 O que a lista precisa é uma coisa só, com motivo medido: sem
     `min-width`, o `<select>` encolhe para o tamanho da opção escolhida e
     muda de largura a cada troca — a faixa inteira dançava. */
  const s = regra(css, '.faixa__select');
  if (!s) {
    return falhar('.faixa__select não existe no CSS publicado — a lista de '
                  + 'mudar etapa mudaria de largura a cada escolha.');
  }
  const largura = (prop(s.corpo, 'min-width') || '').trim();
  if (!largura || largura === '0' || largura === 'auto') {
    falhar(`.faixa__select min-width = ${largura || '(nenhum)'} — sem largura `
           + 'mínima o select encolhe para o tamanho da opção escolhida e a '
           + 'faixa dança a cada troca de etapa.');
  }

  /* 🚨 E a barra NÃO pode voltar sem decisão: classe morta no CSS publicado
     significa que alguém reconstruiu o controle antigo sem tirar o novo, e os
     dois juntos deixariam o estado ambíguo — dois caminhos para o mesmo ato
     foi o motivo de o `<select>` ter saído em 11/11. */
  if (regra(css, '.trilha') || regra(css, '.trilha__passo')) {
    falhar('.trilha voltou ao CSS publicado — a barra de passos foi trocada '
           + 'pela lista em 12/11 a pedido dele. Dois controles para o mesmo '
           + 'ato deixam o estado ambíguo.');
  }
}

/* ------------------------------------------------------------------ */
/* ------------------------------------------------------------------ 10 */
function todoVarUsadoExiste(css) {
  /* 🚨 O DEFEITO: `var(--nao-existe)` é DESCARTADA EM SILÊNCIO -- a declaração
     inteira desaparece, sem erro no console e sem aviso no build. Nenhuma das
     nove conferências acima vê isso: todas olham uma regra que já quebrou, e
     esta olha a CADEIA (o token existe? quem o usa o encontra?).

     ⚠️ FALLBACK FICA DE FORA, e não é indulgência: `var(--x, #fff)` não
     descarta nada. Medido em 23/11 -- é o caso do `IaPrompt.vue:440`, e
     reprovar ali seria a trava errada, do tipo que faz a casa afrouxar a
     trava em vez de consertar o código.

     ⚠️ DECLARADA EM QUALQUER LUGAR CONTA: `:root`, `[data-theme]`, um
     `@media`, ou uma classe de escala. O que se mede é EXISTIR; onde mora é
     assunto da conferência 3. */
  const declaradas = new Set(
    [...css.matchAll(/(--[a-zA-Z0-9_-]+)\s*:/g)].map((m) => m[1]))
  /* `var(` até a vírgula ou o fecha-parêntese: o que vier depois é fallback. */
  const usadas = new Map()
  for (const m of css.matchAll(/var\(\s*(--[a-zA-Z0-9_-]+)\s*([,)])/g)) {
    const nome = m[1]
    const temFallback = m[2] === ','
    if (temFallback) continue
    if (!usadas.has(nome)) usadas.set(nome, 0)
    usadas.set(nome, usadas.get(nome) + 1)
  }
  const orfas = [...usadas.keys()].filter((n) => !declaradas.has(n)).sort()
  if (orfas.length) {
    falhar(`${orfas.length} var() SEM declaração e SEM fallback: `
           + orfas.map((n) => `${n} (${usadas.get(n)}x)`).join(', ')
           + '. O navegador descarta a declaração inteira em silêncio — '
           + 'declare o token, ou dê um fallback se a ausência for esperada.')
  }
}

/* ------------------------------------------------------------------ 11 */
function todaVarianteDeBotaoUsadaTemRegra(css) {
  /* 🚨 O DEFEITO, medido em 25/11: `botao--fraco` usada **19 vezes** na aba 2
     do Financeiro e declarada em lugar nenhum -- nem no `componentes.css`, nem
     no `<style scoped>` da tela. Classe que não existe **não dá erro**: o
     navegador ignora e o botão renderiza como `.botao` base, com cara de
     primário. Uma tela com 19 primários não diz qual é a ação principal.

     ⚠️ É a mesma forma da conferência 10: o que se mede é a CADEIA (a classe
     usada no template encontra regra no CSS publicado?), não uma regra que já
     quebrou. A suíte não alcança isto -- o jsdom não aplica folha de estilo.

     ⚠️ SÓ O QUE ESTÁ EM `class=`/`:class=` conta. Varrer o arquivo inteiro
     pegaria o nome escrito em COMENTÁRIO (este projeto documenta defeito no
     comentário, inclusive o `botao--fraco` que acabou de sair) e a trava
     reprovaria por causa de um texto. */
  const raiz = join(process.cwd(), 'src')
  const vues = []
  const andar = (pasta) => {
    for (const nome of readdirSync(pasta)) {
      const caminho = join(pasta, nome)
      if (statSync(caminho).isDirectory()) andar(caminho)
      else if (nome.endsWith('.vue')) vues.push(caminho)
    }
  }
  if (!existsSync(raiz)) {
    falhar(`não achei ${raiz} para conferir as variantes de botão.`)
    return
  }
  andar(raiz)

  const usadas = new Map()
  for (const caminho of vues) {
    const texto = readFileSync(caminho, 'utf8')
    for (const atr of texto.matchAll(/:?class="([^"]*)"/g)) {
      for (const m of atr[1].matchAll(/botao--[a-z0-9-]+/g)) {
        if (!usadas.has(m[0])) usadas.set(m[0], new Set())
        usadas.get(m[0]).add(caminho.split('src').pop())
      }
    }
  }
  /* Declarada em QUALQUER lugar do CSS publicado conta -- global ou scoped
     (`.botao--x[data-v-...]`). O que se mede é existir. */
  const declaradas = new Set(
    [...css.matchAll(/\.(botao--[a-z0-9-]+)/g)].map((m) => m[1]))
  const orfas = [...usadas.keys()].filter((n) => !declaradas.has(n)).sort()
  if (orfas.length) {
    falhar(`${orfas.length} variante(s) de botão usada(s) em template SEM `
           + `regra no CSS publicado: `
           + orfas.map((n) => `${n} (${[...usadas.get(n)].join(', ')})`)
             .join(' · ')
           + '. O navegador ignora a classe e o botão sai como `.botao` base — '
           + 'use uma variante que existe em estilo/componentes.css, ou '
           + 'declare a regra.')
  }
}

/* ------------------------------------------------------------------ 12 */
/* 📏 A LINHA DE BASE, medida em 25/11: 35 classes compostas em uso sem regra
   em CSS nenhum, em 24 arquivos. É dívida anterior a esta entrega e está aqui
   À VISTA, não apagada -- `.chip--pequeno` sozinha aparece em 11 telas. Tirar
   um nome desta lista é consertar o defeito dele; acrescentar um nome é assumir
   dívida nova, e isso é decisão dele, não minha. */
const ORFAS_CONHECIDAS = new Set([
  'recado--apagada', 'etiqueta--', 'faixa__medida--etapa',
  'agm__campo--cep', 'agm__campo--num', 'agm__campo--uf', 'agm__itens',
  'chip--pequeno', 'agd__mes-botao', 'tela__bloco', 'linha--quebra',
  'balao__ir', 'diario__marca', 'email__assinatura-imagem',
  'inicio__titulo', 'tela__titulo', 'perm__celula', 'tela__aviso',
  'grade__linha', 'grade__linha--aberta',
  /* 25/11: embrulho do subgrupo do menu, sem regra nenhuma. A regra
     parecida (`menu__sub-nome`) é de OUTRO elemento. O conserto é
     remover o nome, e mexer no menu lateral não é esta entrega. */
  'menu__sub',
])

function todaClasseCompostaUsadaTemRegra(css) {
  /* 🚨 O DEFEITO DE 25/11: a reversão da folha comum do painel deixou cinco
     classes do card do artefato sem regra nenhuma, e as 11 conferências, as
     três suítes e o build passaram. A 11ª mede a mesma cadeia, mas só para
     `botao--*`; esta mede para TODA classe composta (`bloco__elemento` ou
     `bloco--variante`), que é a convenção desta casa.

     ⚠️ Classe SEM `__` nem `--` fica fora de propósito: nome de uma palavra é
     muitas vezes de biblioteca (`bi`, `fade`) ou vem de fora do `src`. */
  const raiz = join(process.cwd(), 'src')
  if (!existsSync(raiz)) {
    falhar(`não achei ${raiz} para conferir as classes compostas.`)
    return
  }
  const vues = []
  const andar = (pasta) => {
    for (const nome of readdirSync(pasta)) {
      const caminho = join(pasta, nome)
      if (statSync(caminho).isDirectory()) andar(caminho)
      else if (nome.endsWith('.vue')) vues.push(caminho)
    }
  }
  andar(raiz)

  const usadas = new Map()
  for (const caminho of vues) {
    const texto = readFileSync(caminho, 'utf8')
    /* ⚠️ Só o TEMPLATE: o `<style>` e o `<script>` escrevem nomes em prosa. */
    const corte = texto.indexOf('<style')
    const template = corte < 0 ? texto : texto.slice(0, corte)
    for (const atr of template.matchAll(/:?class="([^"]*)"/g)) {
      for (const m of atr[1].matchAll(/[A-Za-z_][A-Za-z0-9_-]*/g)) {
        const nome = m[0]
        if (!nome.includes('__') && !nome.includes('--')) continue
        /* ⚠️ Nome que TERMINA em `-` é prefixo montado em tempo de execução
           (`:class="'selo--' + a.semaforo"`), não classe. A classe final
           (`selo--laranja`) é medida normalmente. */
        if (nome.endsWith('-')) continue
        if (ORFAS_CONHECIDAS.has(nome)) continue
        if (!usadas.has(nome)) usadas.set(nome, new Set())
        usadas.get(nome).add(caminho.split('src').pop())
      }
    }
  }
  /* 🚨 AS DUAS FOLHAS. O `src/componentes/CamposDoFormulario.vue` é do
     FORMULÁRIO PÚBLICO (`publico/` -> `dist_publico`), um build separado:
     medi-lo contra a folha do painel acusaria 12 defeitos inexistentes. As
     outras 11 conferências medem o painel e leem só a dele. */
  let folhas = css
  const publico = join(process.cwd(), 'dist_publico', 'assets')
  if (existsSync(publico)) {
    for (const f of readdirSync(publico).filter((f) => f.endsWith('.css'))) {
      folhas += '\n' + readFileSync(join(publico, f), 'utf8')
    }
  }
  const declaradas = new Set(
    [...folhas.matchAll(/\.([A-Za-z_][A-Za-z0-9_-]*)/g)].map((m) => m[1]))
  const orfas = [...usadas.keys()].filter((n) => !declaradas.has(n)).sort()
  if (orfas.length) {
    falhar(`${orfas.length} classe(s) composta(s) usada(s) em template SEM `
           + 'regra no CSS publicado: '
           + orfas.map((n) => `${n} (${[...usadas.get(n)].join(', ')})`)
             .join(' · ')
           + '. O navegador ignora a classe EM SILÊNCIO e o elemento sai sem '
           + 'forma — declare a regra, ou use um nome que existe. Se a falta '
           + 'for mesmo esperada, o nome entra em ORFAS_CONHECIDAS com a data.')
  }
}

const css = cssPublicado()
if (!erros.length) {
  oDialogoDoPainelNaoHerdaOTeto(css)
  oPainelVemDepoisDasRegrasAntigas(css)
  osTokensDeSistemaEstaoNoRoot(css)
  osTresDialogosNaoEmpatamNoZIndex(css)
  oDialogoDoChamadoTemTetoProprioENaoEmpata(css)
  osControlesDeRolagemFicamNaCamadaCerta(css)
  oAvisoDaEtapaEhCurtoEComBotaoNoCentro(css)
  todaVarianteDePilulaTemAPilulaBase(css)
  aBarraDeEtapasRolaENaoQuebra(css)
  todoVarUsadoExiste(css)
  todaVarianteDeBotaoUsadaTemRegra(css)
  todaClasseCompostaUsadaTemRegra(css)
}

if (erros.length) {
  console.error(`\nCSS PUBLICADO: ${erros.length} problema(s)\n`)
  erros.forEach((e, i) => console.error(`  ${i + 1}. ${e}\n`))
  process.exit(1)
}
console.log('CSS publicado: as 12 conferências passaram (teto do diálogo, '
            + 'ordem da cascata, tokens no :root, empilhamento dos diálogos, '
            + 'teto e empilhamento do diálogo do chamado, camada dos controles '
            + 'de rolagem, forma do aviso da etapa, lista de etapas com largura estável, '
            + 'pílula com base no mesmo '
            + 'escopo, todo var() com token declarado, '
            + 'toda variante de botão usada com regra no CSS, toda classe composta usada com regra no CSS)')
