<script setup>
/* ============================================================================
   Aviso da distribuição automática — Fila e Início (24/09)
   ----------------------------------------------------------------------------
   🔵 Decisão dele (4a): *"Vão para Erika na mesma regra e depois fila se ambas
   estiverem offline"* -- e quando param, a tela avisa. Desligada, não aparece.
   Relê a cada minuto, o mesmo passo do laço que distribui.
   ============================================================================ */
import { ref, onMounted, onUnmounted } from 'vue'

import { api } from '../api/cliente.js'

const situacao = ref(null)
let relogio = null

async function ler() {
  try {
    situacao.value = await api.get('/api/fila/distribuicao')
  } catch {
    situacao.value = null
  }
}

onMounted(() => { ler(); relogio = setInterval(ler, 60000) })
onUnmounted(() => clearInterval(relogio))
</script>

<template>
  <template v-if="situacao?.ligada">
    <p v-if="situacao.parada" class="aviso aviso--erro" role="alert">
      <i class="bi bi-sign-stop aviso__icone" aria-hidden="true"></i>
      <span>
        <strong>Distribuição parada:</strong>
        {{ [situacao.primeiro, situacao.reserva].filter(Boolean).join(' e ') }}
        {{ situacao.reserva ? 'estão' : 'está' }} offline.
        <template v-if="situacao.esperando">
          {{ situacao.esperando }} conversa(s) esperando na fila.
        </template>
      </span>
    </p>
    <p v-else-if="!situacao.primeiro_disponivel" class="aviso aviso--atencao" role="status">
      <i class="bi bi-arrow-left-right aviso__icone" aria-hidden="true"></i>
      <span>
        {{ situacao.primeiro }} está offline: conversa sem dono há {{ situacao.minutos }} min
        vai para <strong>{{ situacao.destino_agora }}</strong>.
      </span>
    </p>
    <p v-else class="aviso aviso--info" role="status">
      <i class="bi bi-arrow-right-circle aviso__icone" aria-hidden="true"></i>
      <span>
        Conversa sem dono há {{ situacao.minutos }} min vai sozinha para
        <strong>{{ situacao.destino_agora }}</strong>.
      </span>
    </p>
  </template>
</template>

<style scoped>
.aviso { margin-bottom: var(--e-4); }
</style>
