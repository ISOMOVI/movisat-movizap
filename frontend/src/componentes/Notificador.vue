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
import { onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { api } from '../api/cliente.js'
import { notificacoes } from '../estado/notificacoes.js'
import { decidirToque } from '../util/regraToque.js'
import { somBloqueado, tocar } from '../util/som.js'
import {
  adiarConvite, conviteAdiado, foraDeFoco, mostrarBalao, pedirPermissao, permissao,
} from '../util/balao.js'

const INTERVALO_MS = 8000
const router = useRouter()
let antes = null
let relogio = null
let pisca = null
let tituloBase = ''

/* 🔵 25/09: o balão do Windows. O convite aparece só enquanto a permissão
   nunca foi respondida e a pessoa não disse "Agora não" nesta semana. */
notificacoes.permissaoBalao = permissao()
const adiado = ref(conviteAdiado())

async function ativarBalao() {
  notificacoes.permissaoBalao = await pedirPermissao()
}
function agoraNao() {
  adiarConvite()
  adiado.value = true
}
function abrirConversa(id) {
  router.push(`/atendimento/${id}`)
}

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

  // 🔵 25/09: a conversa aberta com a tela à vista não toca.
  const aVista = document.hidden ? null : notificacoes.conversaAberta
  const decisao = decidirToque(antes, r, aVista)
  antes = { donas: r.donas || [], assumidas: r.assumidas || [] }
  if (!notificacoes.ativa) {
    pararDePiscar()
    return
  }
  if (decisao.tocar) {
    // O balão sai antes do som: o som pode estar bloqueado (F5 sem clique), o
    // balão não depende disso.
    if (foraDeFoco()) {
      for (const id of decisao.conversas.slice(0, 4)) {
        const c = (r.assumidas || []).find((x) => x.id === id)
        if (c) mostrarBalao(c, abrirConversa)
      }
    }
    await tocar(notificacoes.tom, notificacoes.volume)
  }
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
  <!-- 🔵 25/09: o convite do balão, no mesmo canto. Pede permissão só com o
       clique da pessoa -- pedir ao abrir o painel é o jeito certo de ouvir
       "bloquear" para sempre. -->
  <div v-else-if="notificacoes.ativa && notificacoes.permissaoBalao === 'default' && !adiado"
       class="destravar convite" role="region" aria-label="Avisos na tela">
    <i class="bi bi-window-stack" aria-hidden="true"></i>
    <span>Avisar no canto da tela quando chegar mensagem?</span>
    <button type="button" class="botao botao--pequeno botao--primario" @click="ativarBalao">
      Ativar avisos na tela
    </button>
    <button type="button" class="botao botao--pequeno botao--fantasma" @click="agoraNao">
      Agora não
    </button>
  </div>
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
.convite {
  flex-wrap: wrap;
  max-width: min(520px, calc(100vw - 2 * var(--e-4)));
  border-radius: var(--r-lg);
  border-color: var(--acento-borda);
  background: var(--superficie);
  cursor: default;
}
</style>
