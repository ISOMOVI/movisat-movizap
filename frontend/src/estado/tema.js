/* ============================================================================
   Tema claro / escuro.
   ----------------------------------------------------------------------------
   Três valores de preferência: 'claro' (PADRÃO), 'escuro' e 'sistema'.
   O que vai para <html data-tema> é sempre RESOLVIDO — 'claro' ou 'escuro',
   nunca 'sistema'. Assim o CSS tem um caso por tema e nenhuma duplicação.

   ⚠️ O padrão é CLARO, não 'sistema' — decisão do usuário em 05/08. Por isso
   'sistema' precisa ficar GRAVADO quando escolhido: não dá para deduzi-lo da
   ausência de valor, que agora significa 'claro'.

   O mesmo cálculo roda inline no <head> do index.html, antes da primeira
   pintura. Se mudar a regra aqui, mudar lá também — é a única duplicação
   aceita, e existe para não piscar branco num painel que fica aberto o dia
   inteiro em sala escura.
   ============================================================================ */
import { reactive, watchEffect } from 'vue'

const CHAVE = 'movizap.tema'
const OPCOES = ['claro', 'escuro', 'sistema']
const PADRAO = 'claro'

const consultaEscuro = window.matchMedia('(prefers-color-scheme: dark)')

function preferenciaGuardada() {
  const v = localStorage.getItem(CHAVE)
  return OPCOES.includes(v) ? v : PADRAO
}

export const tema = reactive({
  preferencia: preferenciaGuardada(),
  /** o que está de fato na tela: 'claro' ou 'escuro' */
  resolvido: 'claro',
})

function resolver() {
  tema.resolvido =
    tema.preferencia === 'sistema'
      ? consultaEscuro.matches
        ? 'escuro'
        : 'claro'
      : tema.preferencia
}

export function definirTema(preferencia) {
  if (!OPCOES.includes(preferencia)) return
  tema.preferencia = preferencia
  // Grava sempre, inclusive 'sistema'. Apagar a chave significaria 'claro'.
  localStorage.setItem(CHAVE, preferencia)
  resolver()
}

/** Alterna claro <-> escuro. Sai de 'sistema' para o oposto do que está na tela. */
export function alternarTema() {
  definirTema(tema.resolvido === 'escuro' ? 'claro' : 'escuro')
}

export function iniciarTema() {
  resolver()
  // Se a preferência é 'sistema', seguir o sistema quando ele mudar.
  consultaEscuro.addEventListener('change', () => {
    if (tema.preferencia === 'sistema') resolver()
  })
  watchEffect(() => {
    document.documentElement.setAttribute('data-tema', tema.resolvido)
  })
}
