<script setup>
/* ============================================================================
   Barra de status — item 15 do escopo, critério de pronto nº 10.
   ----------------------------------------------------------------------------
   "logado · duração da sessão · data/hora · código da tela · id da requisição"

   O `req_id` é o que faz a diferença no suporte: o usuário lê `req a3f9` na
   tela e o log da VPS tem `req=a3f9` naquela requisição exata. Sem isso, o
   que se procura no journal é "por volta das 14h, na tela de conversa".
   ============================================================================ */
import { computed, onBeforeUnmount, ref } from 'vue'
import { useRoute } from 'vue-router'

import { sessao } from '../estado/sessao.js'
import { rede } from '../api/cliente.js'

const rota = useRoute()

const agora = ref(new Date())
const relogio = setInterval(() => { agora.value = new Date() }, 1000)
onBeforeUnmount(() => clearInterval(relogio))

const dataHora = computed(() =>
  agora.value.toLocaleString('pt-BR', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  }),
)

const duracao = computed(() => {
  if (!sessao.iniciadaEm) return '—'
  const seg = Math.max(0, Math.floor((agora.value - sessao.iniciadaEm) / 1000))
  const h = Math.floor(seg / 3600)
  const m = Math.floor((seg % 3600) / 60)
  if (h) return `${h}h ${String(m).padStart(2, '0')}min`
  if (m) return `${m}min ${String(seg % 60).padStart(2, '0')}s`
  return `${seg}s`
})

const codigo = computed(() => rota.meta.codigo || '—')
</script>

<template>
  <footer class="barra">
    <span class="barra__item barra__item--codigo" :title="'Código da tela: ' + codigo">
      <i class="bi bi-window" aria-hidden="true"></i>
      <span class="mono">{{ codigo }}</span>
    </span>

    <span class="barra__sep" aria-hidden="true">·</span>

    <span class="barra__item barra__item--opcional">
      <i class="bi bi-person" aria-hidden="true"></i>
      {{ sessao.usuario?.nome || '—' }}
      <span v-if="sessao.usuario?.owner" class="chip chip--acento">owner</span>
    </span>

    <span class="barra__sep" aria-hidden="true">·</span>

    <span class="barra__item barra__item--opcional" title="Tempo desde o início desta sessão">
      <i class="bi bi-hourglass-split" aria-hidden="true"></i>
      sessão {{ duracao }}
    </span>

    <span class="espaco"></span>

    <span v-if="rede.emVoo > 0" class="barra__item barra__item--voando">
      <span class="girando"></span>
      <span class="so-leitor">carregando</span>
    </span>

    <span class="barra__item" :title="'Última requisição: ' + (rede.ultimoReqId || 'nenhuma')">
      <i class="bi bi-hash" aria-hidden="true"></i>
      <span class="mono">req {{ rede.ultimoReqId || '—' }}</span>
    </span>

    <span class="barra__sep" aria-hidden="true">·</span>

    <span class="barra__item mono">{{ dataHora }}</span>
  </footer>
</template>

<style scoped>
.barra {
  grid-area: barra;
  display: flex;
  align-items: center;
  gap: var(--e-2);
  height: var(--altura-barra);
  padding: 0 var(--e-4);
  border-top: var(--borda-fina) solid var(--borda);
  background: var(--superficie);
  color: var(--texto-apagado);
  font-size: var(--txt-xs);
  z-index: var(--z-barra);
  overflow: hidden;
  white-space: nowrap;
}
.barra__item { display: inline-flex; align-items: center; gap: 5px; }
.barra__item--codigo { color: var(--acento); font-weight: var(--peso-medio); }
.barra__item--voando { color: var(--texto-fraco); }
.barra__sep { opacity: .45; }
.barra .chip { padding: 0 6px; }

/* Em tela estreita a barra guarda o essencial: código, req e hora. */
@media (max-width: 720px) {
  .barra__item--opcional,
  .barra__sep { display: none; }
}
</style>
