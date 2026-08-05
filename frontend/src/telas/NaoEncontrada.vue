<script setup>
import { useRoute } from 'vue-router'

const rota = useRoute()
</script>

<template>
  <div class="tela">
    <div class="vazio">
      <i class="bi bi-signpost-split vazio__icone" aria-hidden="true"></i>
      <p class="vazio__titulo">Rota não encontrada</p>
      <p class="mono pequeno">{{ rota.fullPath }}</p>
      <p class="apagado pequeno tela__nota">
        Tela que não está no registro não existe. Se esta rota deveria existir,
        ela precisa nascer em <span class="mono">movizap/telas.py</span> primeiro.
      </p>
      <RouterLink class="botao botao--contorno tela__voltar" to="/">
        <i class="bi bi-arrow-left" aria-hidden="true"></i> Voltar
      </RouterLink>
    </div>
  </div>
</template>

<style scoped>
.tela { max-width: 620px; margin: var(--e-7) auto 0; }
.tela__nota { margin-top: var(--e-3); }
.tela__voltar { margin-top: var(--e-5); }
</style>
