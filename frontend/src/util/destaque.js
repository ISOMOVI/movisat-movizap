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
