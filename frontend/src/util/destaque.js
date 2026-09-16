/* ============================================================================
   Destaque do termo buscado — recorte e marcação.
   ----------------------------------------------------------------------------
   Vivia dentro do `<script setup>` da CaixaDeEntrada.vue e por isso nenhum
   teste alcançava. Saiu para cá em 12/08 com um objetivo só: poder testar.
   A lógica não mudou uma linha na mudança.

   🚨 AS DUAS DEVOLVEM PEDAÇOS, NUNCA HTML. O texto é o que o cliente escreveu.
   Montar `<mark>` numa string e injetar com `v-html` entregaria a tela a quem
   manda a mensagem: bastaria mandar `<img onerror=...>` para executar script
   no navegador do atendente. Devolvendo pedaços, o Vue escreve cada um como
   texto e o escape acontece sozinho.

   ⚠️ SEM REGEX, de propósito. O termo é digitado por gente, e `(`, `+`, `*`
   ou `[` num telefone quebrariam a expressão -- ou, pior, casariam errado.
   `indexOf` em minúscula resolve e não tem caso especial.
   ============================================================================ */

/** Quantos caracteres mostrar antes e depois do acerto, no recorte da lista. */
export const ANTES = 30
export const DEPOIS = 70

/**
 * Recorta um trecho em volta da PRIMEIRA ocorrência e a marca.
 * Usado na prévia da lista, onde só cabe uma linha.
 *
 * ⚠️ Recorta em volta do ACERTO, não do começo: numa mensagem longa o termo
 * costuma estar no meio, e mostrar os primeiros 100 caracteres esconderia
 * justamente o motivo de a conversa estar na lista.
 *
 * @returns {{texto: string, casa: boolean}[]}
 */
export function partir(texto, termo) {
  const alvo = (termo || '').trim()
  if (!texto) return [{ texto: '', casa: false }]
  if (!alvo) return [{ texto: texto.slice(0, ANTES + DEPOIS), casa: false }]

  const onde = texto.toLowerCase().indexOf(alvo.toLowerCase())
  if (onde < 0) return [{ texto: texto.slice(0, ANTES + DEPOIS), casa: false }]

  const de = Math.max(0, onde - ANTES)
  const ate = Math.min(texto.length, onde + alvo.length + DEPOIS)
  const pedacos = []
  if (de > 0) pedacos.push({ texto: '…', casa: false })
  if (onde > de) pedacos.push({ texto: texto.slice(de, onde), casa: false })
  pedacos.push({ texto: texto.slice(onde, onde + alvo.length), casa: true })
  if (ate > onde + alvo.length) {
    pedacos.push({ texto: texto.slice(onde + alvo.length, ate), casa: false })
  }
  if (ate < texto.length) pedacos.push({ texto: '…', casa: false })
  return pedacos
}

/**
 * Marca TODAS as ocorrências, sem recortar. Usado dentro do balão, onde a
 * mensagem inteira precisa continuar legível.
 *
 * @returns {{texto: string, casa: boolean}[]}
 */
export function marcar(texto, termo) {
  const alvo = (termo || '').trim()
  if (!texto || !alvo) return [{ texto: texto || '', casa: false }]

  const baixo = texto.toLowerCase()
  const alvoBaixo = alvo.toLowerCase()
  const pedacos = []
  let i = 0
  while (i < texto.length) {
    const onde = baixo.indexOf(alvoBaixo, i)
    if (onde < 0) {
      pedacos.push({ texto: texto.slice(i), casa: false })
      break
    }
    if (onde > i) pedacos.push({ texto: texto.slice(i, onde), casa: false })
    pedacos.push({ texto: texto.slice(onde, onde + alvo.length), casa: true })
    i = onde + alvo.length
  }
  return pedacos
}

/* ⚠️ AQUI SIM É REGEX, e de propósito -- o contrário de `marcar`/`partir`.
   Lá o alvo é digitado por gente (o termo de busca) e vira ele mesmo o
   padrão; aqui o padrão é FIXO (a forma de uma URL) e o texto é dado, então
   não há metacaractere de usuário para escapar. */
const URL = /https?:\/\/[^\s<>"']+/gi

/* Pontuação de frase que gruda no fim de um link colado ("...gov.br/login.",
   "(veja aqui: https://x.com)"): não faz parte da URL, e mandar assim quebra
   o destino. Fica de fora do link e volta como texto comum. */
const PONTUACAO_NO_FIM = /[).,;:!?\]]+$/

/**
 * Separa um texto em pedaços de link e não-link, sem tocar em HTML.
 *
 * Mesma garantia de `marcar`: nunca devolve marcação, só pedaços de string
 * que, somados, reconstroem o texto original -- quem transforma link em
 * `<a>` é o template, com `:href`, não esta função.
 *
 * @returns {{texto: string, link: boolean}[]}
 */
export function linkificar(texto) {
  if (!texto) return [{ texto: texto || '', link: false }]

  const pedacos = []
  let i = 0
  for (const m of texto.matchAll(URL)) {
    const inicio = m.index
    if (inicio > i) pedacos.push({ texto: texto.slice(i, inicio), link: false })

    let url = m[0]
    const sufixo = url.match(PONTUACAO_NO_FIM)
    if (sufixo) url = url.slice(0, url.length - sufixo[0].length)

    if (url) pedacos.push({ texto: url, link: true })
    if (sufixo) pedacos.push({ texto: sufixo[0], link: false })
    i = m.index + m[0].length
  }
  if (i < texto.length) pedacos.push({ texto: texto.slice(i), link: false })
  return pedacos.length ? pedacos : [{ texto, link: false }]
}
