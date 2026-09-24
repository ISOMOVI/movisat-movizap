<script setup>
/* ============================================================================
   Notificador — o som e a aba piscando, em QUALQUER tela (24/09)
   ----------------------------------------------------------------------------
   🔵 Pedidos dele: notificação *"somente de conversas assumidas"*, teto de 4
   (e conversa nova toca uma vez), *"pisca aba obrigatoriamente"*, tom e
   volume de cada um, e o owner liga/desliga por pessoa -- desligada, *"some
   tudo"* (som e piscar; o contador das abas fica, é informativo).

   🚨 MORA NA CASCA (App.vue), NÃO NA CAIXA. A Caixa só se atualiza enquanto
   está aberta; quem está em Atendentes ou no E-mail não saberia de nada.

   ⚠️ 8 s e não os 15 s do selo do Chat interno: a notificação é o aviso de
   que um cliente espera. Somado ao caminho WhatsApp -> painel (medido em
   28/08), a demora fica em ~10-15 s.
   ============================================================================ */
import { onMounted, onUnmounted } from 'vue'

import { api } from '../api/cliente.js'
import { notificacoes } from '../estado/notificacoes.js'
import { decidirToque } from '../util/regraToque.js'
import { somBloqueado, tocar } from '../util/som.js'

const INTERVALO_MS = 8000
let antes = null
let relogio = null
let pisca = null
let tituloBase = ''

function pararDePiscar() {
  if (pisca) {
    clearInterval(pisca)
    pisca = null
    document.title = tituloBase || document.title
  }
}

/* 🔵 "pisca aba obrigatoriamente": não há opção para desligar. Só pisca com o
   painel em SEGUNDO PLANO -- com ele à vista, o título piscando não avisa
   nada que a tela já não mostre. */
function piscar(quantas) {
  if (!document.hidden || !notificacoes.ativa || quantas <= 0) {
    pararDePiscar()
    return
  }
  if (pisca) return
  tituloBase = document.title
  let alterna = false
  pisca = setInterval(() => {
    alterna = !alterna
    document.title = alterna ? `(${notificacoes.assumidasNaoLidas}) Nova mensagem` : tituloBase
  }, 1000)
}

async function ler() {
  let r
  try {
    r = await api.get('/api/eu/notificacoes')
  } catch {
    return // falhou a leitura: não toca, não pisca, tenta de novo no próximo ciclo
  }
  notificacoes.carregado = true
  notificacoes.ativa = Boolean(r.ativa)
  notificacoes.tom = r.tom
  notificacoes.volume = r.volume
  notificacoes.abas = r.abas || { minhas: 0, time: 0 }
  notificacoes.assumidasNaoLidas = (r.assumidas || []).length

  const decisao = decidirToque(antes, r)
  antes = { donas: r.donas || [], assumidas: r.assumidas || [] }
  if (!notificacoes.ativa) {
    pararDePiscar()
    return
  }
  if (decisao.tocar) await tocar(notificacoes.tom, notificacoes.volume)
  piscar(notificacoes.assumidasNaoLidas)
}

function aoMudarVisibilidade() {
  if (!document.hidden) pararDePiscar()
  else piscar(notificacoes.assumidasNaoLidas)
}

onMounted(() => {
  ler()
  relogio = setInterval(ler, INTERVALO_MS)
  document.addEventListener('visibilitychange', aoMudarVisibilidade)
})

onUnmounted(() => {
  clearInterval(relogio)
  pararDePiscar()
  document.removeEventListener('visibilitychange', aoMudarVisibilidade)
})
</script>

<template>
  <!-- O navegador bloqueia som antes do primeiro clique na página. Em vez de
       falhar calado, diz o que fazer -- e qualquer clique já resolve. -->
  <button v-if="somBloqueado && notificacoes.ativa" type="button" class="destravar"
          title="O navegador só toca som depois de um clique na página">
    <i class="bi bi-volume-mute" aria-hidden="true"></i>
    Clique para ativar o som das notificações
  </button>
</template>

<style scoped>
.destravar {
  position: fixed;
  right: var(--e-4);
  bottom: calc(var(--altura-barra) + var(--e-3));
  z-index: var(--z-flutuante);
  display: inline-flex;
  align-items: center;
  gap: var(--e-2);
  padding: var(--e-2) var(--e-3);
  border: var(--borda-fina) solid var(--aviso-borda);
  border-radius: var(--r-full);
  background: var(--aviso-suave);
  color: var(--texto);
  font: inherit;
  font-size: var(--txt-sm);
  box-shadow: var(--sombra-2);
  cursor: pointer;
}
</style>
