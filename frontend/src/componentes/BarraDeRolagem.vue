<script setup>
/* ============================================================================
   BARRA DE ROLAGEM GRUDADA NO ALTO DO QUADRO — 06/11.
   ----------------------------------------------------------------------------
   🔵 Pedido dele: *"precisamos disso nos paineis, pois o scroll ficou la
   embaixo"* · *"pode ser uma barra fina tbm, o mouse ficando parado ou o scrol
   ficando na tela tbm resolve -- o que vê como melhor, pela usabilidade da
   tela"* · e o OK: *"Ok go"*.

   🚨 **O ACHADO QUE DECIDIU PELA BARRA.** As colunas NÃO têm rolagem própria
   (`.coluna__corpo` sem `overflow-y` nem `max-height`): elas crescem com os
   cards, e quem rola na vertical é o **casco** (`.painel__conteudo`, que tem
   `overflow: auto`). Com 15 cards numa coluna o quadro fica altíssimo e a barra
   nativa do `overflow-x` mora **no pé dele**, centenas de pixels abaixo da
   dobra. Para andar de lado era preciso primeiro andar para baixo — o gesto
   certo exigia o gesto errado.

   🚨 **E É SÓ ELA QUE DIZ QUE EXISTE MAIS QUADRO.** Uma faixa de hover na borda
   é invisível até o ponteiro chegar nela: quem abre a Operação vê 4 colunas e
   nunca descobre que existem **18**. Com 18 colunas, não saber que são 18 é a
   falha maior. A barra mostra **posição e extensão** sem ensinar nada a
   ninguém.

   ⚠️ **POR QUE NÃO É A BARRA NATIVA.** Não há como mover a barra do navegador
   para o alto do elemento. Esta é um `role="scrollbar"` de verdade: espelha o
   `scrollLeft` do rolo nos dois sentidos, e o rolo continua rolando por roda,
   por teclado e por toque como sempre. Nada foi tirado — isto é um segundo
   caminho para o mesmo estado.

   🚨 **NÃO EXISTE SE NÃO HÁ PARA ONDE ROLAR.** `scrollWidth <= clientWidth` e a
   barra não é desenhada. O Contratual tem 6 colunas e numa tela larga cabe
   inteiro; oferecer o gesto ali seria controle morto — o precedente do
   `ModalAgendar`.

   ⚠️ **O ROLO MUDA DE TAMANHO SOZINHO:** coluna que colapsa (360 → 280px),
   filtro que esconde cards, janela que muda. Por isso há `ResizeObserver` no
   rolo E no primeiro filho — só no rolo não acusa conteúdo que cresceu sem a
   caixa mudar.
   ============================================================================ */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps({
  /* O elemento com `overflow-x: auto`. Vem de fora porque o rolo é do painel,
     não desta barra -- ela é um controle PARA ele. */
  rolo: { type: Object, default: null },
  /* Rótulo do que se rola, para quem usa leitor de tela. */
  rotulo: { type: String, default: 'Quadro' },
})

const trilho = ref(null)
const esquerda = ref(0)
const visivel = ref(0)
const total = ref(0)
const arrastando = ref(false)

let observador = null
let roloAtual = null

/* 🚨 UMA COLUNA É O PASSO, e é o que casa com o quadro ser uma fila de
   colunas: 360px da coluna aberta + o `--e-3` do `gap`. ⚠️ A coluna fechada
   tem 280px, então o passo não cai exatamente numa borda sempre -- e é o
   certo: alinhar à força faria o clique "voltar" quando o alvo é a metade de
   uma coluna larga. */
const PASSO = 376

function medir() {
  const el = props.rolo
  if (!el) {
    total.value = 0
    return
  }
  total.value = el.scrollWidth
  visivel.value = el.clientWidth
  esquerda.value = el.scrollLeft
}

/* Há transbordo? 🚨 A tolerância de 2px não é frouxidão: `scrollWidth` e
   `clientWidth` divergem por arredondamento de subpixel em zoom não inteiro, e
   sem ela a barra apareceria e desapareceria sozinha em 110% de zoom. */
const transborda = computed(() => total.value - visivel.value > 2)

const larguraDoPolegar = computed(() => {
  if (!transborda.value) return 0
  // Piso de 8%: num quadro de 18 colunas o polegar proporcional teria ~5px e
  // seria impossível de pegar com o ponteiro.
  return Math.max(8, (visivel.value / total.value) * 100)
})

const posicaoDoPolegar = computed(() => {
  const curso = total.value - visivel.value
  if (curso <= 0) return 0
  const fracao = esquerda.value / curso
  // O polegar não pode passar da borda direita: o espaço que ele percorre é
  // 100% MENOS a largura dele.
  return fracao * (100 - larguraDoPolegar.value)
})

const porcento = computed(() => {
  const curso = total.value - visivel.value
  return curso <= 0 ? 0 : Math.round((esquerda.value / curso) * 100)
})

function irPara(x) {
  const el = props.rolo
  if (!el) return
  const curso = el.scrollWidth - el.clientWidth
  el.scrollLeft = Math.max(0, Math.min(curso, x))
}

function andar(passos) {
  irPara((props.rolo?.scrollLeft || 0) + passos * PASSO)
}

/* Clique no trilho leva ao PONTO CLICADO, como numa barra de rolagem de
   verdade -- é a convenção que a pessoa já tem na mão. ⚠️ O ponto é o CENTRO
   do polegar, senão clicar na metade do trilho deixaria a vista à esquerda do
   que se apontou. */
function cliqueNoTrilho(ev) {
  if (!trilho.value || !props.rolo) return
  const caixa = trilho.value.getBoundingClientRect()
  if (!caixa.width) return
  const fracao = (ev.clientX - caixa.left) / caixa.width
  const curso = props.rolo.scrollWidth - props.rolo.clientWidth
  irPara(fracao * props.rolo.scrollWidth - props.rolo.clientWidth / 2)
  void curso
}

/* O arraste do polegar usa `pointer*` e não `mouse*`: com `setPointerCapture` o
   ponteiro continua sendo nosso mesmo saindo do elemento, que é o que faz o
   arraste não "escapar" ao passar por cima de um card. */
function pegarPolegar(ev) {
  if (!trilho.value) return
  arrastando.value = true
  ev.currentTarget.setPointerCapture?.(ev.pointerId)
  ev.preventDefault()
}

function moverPolegar(ev) {
  if (!arrastando.value || !trilho.value || !props.rolo) return
  const caixa = trilho.value.getBoundingClientRect()
  if (!caixa.width) return
  const fracao = (ev.clientX - caixa.left) / caixa.width
  irPara(fracao * props.rolo.scrollWidth - props.rolo.clientWidth / 2)
}

function soltarPolegar(ev) {
  arrastando.value = false
  ev.currentTarget.releasePointerCapture?.(ev.pointerId)
}

function noTeclado(ev) {
  const el = props.rolo
  if (!el) return
  const acoes = {
    ArrowRight: () => andar(1),
    ArrowLeft: () => andar(-1),
    PageDown: () => irPara(el.scrollLeft + el.clientWidth),
    PageUp: () => irPara(el.scrollLeft - el.clientWidth),
    Home: () => irPara(0),
    End: () => irPara(el.scrollWidth),
  }
  const acao = acoes[ev.key]
  if (!acao) return
  ev.preventDefault()
  acao()
}

function ligar(el) {
  if (roloAtual === el) return
  desligar()
  roloAtual = el
  if (!el) return
  el.addEventListener('scroll', medir, { passive: true })
  // ⚠️ DOIS alvos no observador: o rolo (a caixa) e o primeiro filho (o
  // conteúdo). Coluna que colapsa muda o conteúdo sem mudar a caixa, e só
  // observar o rolo não acusaria.
  if (typeof ResizeObserver !== 'undefined') {
    observador = new ResizeObserver(medir)
    observador.observe(el)
    if (el.firstElementChild) observador.observe(el.firstElementChild)
  }
  medir()
}

function desligar() {
  if (roloAtual) roloAtual.removeEventListener('scroll', medir)
  observador?.disconnect()
  observador = null
  roloAtual = null
}

watch(() => props.rolo, (el) => ligar(el), { immediate: true })
onMounted(() => {
  window.addEventListener('resize', medir)
  ligar(props.rolo)
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', medir)
  desligar()
})

/* Exposto para o painel poder remedir depois de recarregar o quadro: o
   `ResizeObserver` cobre quase tudo, mas trocar o conteúdo inteiro num tique só
   às vezes não muda nenhuma caixa observada. */
defineExpose({ medir })
</script>

<template>
  <!-- 🚨 `v-if` NO TRANSBORDO: barra que não rola nada não é desenhada. -->
  <div
    v-if="transborda"
    class="barrarolo"
    :class="{ 'barrarolo--ativa': arrastando }"
  >
    <div
      ref="trilho"
      class="barrarolo__trilho"
      role="scrollbar"
      tabindex="0"
      aria-orientation="horizontal"
      :aria-label="`Rolar ${rotulo} na horizontal`"
      :aria-valuenow="porcento"
      aria-valuemin="0"
      aria-valuemax="100"
      :aria-valuetext="`${porcento}% da largura`"
      @pointerdown="cliqueNoTrilho"
      @keydown="noTeclado"
    >
      <div
        class="barrarolo__polegar"
        :style="{ width: `${larguraDoPolegar}%`,
                  left: `${posicaoDoPolegar}%` }"
        @pointerdown.stop="pegarPolegar"
        @pointermove="moverPolegar"
        @pointerup="soltarPolegar"
        @pointercancel="soltarPolegar"
      />
    </div>
  </div>
</template>

<style scoped>
/* 🚨 `sticky` RELATIVO AO CASCO, que é quem tem `overflow: auto`
   (`.painel__conteudo` do `App.vue`). O `top: 0` cola no alto da área visível
   do casco, então a barra acompanha quem desce por uma coluna alta -- é
   exatamente a frase dele, *"o scroll ficou la embaixo"*, deixando de ser
   verdade.
   ⚠️ O `z-index` é BAIXO de propósito: acima do quadro, abaixo de qualquer
   diálogo. Barra de rolagem por cima de um modal seria o defeito de camada que
   a conferência do CSS publicado caça. */
.barrarolo {
  position: sticky;
  top: 0;
  z-index: calc(var(--z-rolagem) + 1);
  padding: var(--e-2) 0;
  background: var(--superficie);
}
.barrarolo__trilho {
  position: relative;
  height: 10px;
  border-radius: 999px;
  background: var(--borda);
  cursor: pointer;
}
.barrarolo__trilho:focus-visible {
  outline: 2px solid var(--acento);
  outline-offset: 2px;
}
.barrarolo__polegar {
  position: absolute;
  top: 0;
  height: 100%;
  min-width: 28px;
  border-radius: 999px;
  background: var(--texto-fraco);
  /* ⚠️ A transição é só da COR: animar `left` faria o polegar correr atrás do
     ponteiro durante o arraste, com um atraso visível. */
  transition: background-color 120ms ease;
}
.barrarolo__trilho:hover .barrarolo__polegar,
.barrarolo--ativa .barrarolo__polegar {
  background: var(--texto);
}
/* 44px de alvo de toque sem engordar o traço: a área clicável cresce por
   `::before`, e o desenho continua fino. Padrão dos quatro painéis. */
.barrarolo__trilho::before {
  content: '';
  position: absolute;
  inset: -17px 0;
}
</style>
