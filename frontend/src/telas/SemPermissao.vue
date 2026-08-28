<script setup>
/* ============================================================================
   O usuário chegou numa rota cuja tela o backend NÃO listou para ele.
   ----------------------------------------------------------------------------
   Mostrar o código é de propósito: quem for pedir acesso pede por `CAD_2.1`,
   não por "aquela tela de cadastro de gente".
   ============================================================================ */
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const rota = useRoute()
const codigo = computed(() => rota.query.codigo || '—')
</script>

<template>
  <div class="tela">
    <div class="vazio">
      <i class="bi bi-shield-lock vazio__icone" aria-hidden="true"></i>
      <p class="vazio__titulo">Sem permissão para esta tela</p>
      <p>
        A tela <span class="mono">{{ codigo }}</span> não está liberada para a sua conta.
      </p>
      <p class="apagado pequeno tela__nota">
        Peça o acesso citando o código.
      </p>
      <RouterLink class="botao botao--contorno tela__voltar" to="/">
        <i class="bi bi-arrow-left" aria-hidden="true"></i> Voltar
      </RouterLink>
    </div>
  </div>
</template>

<style scoped>
.tela { max-width: 620px; margin: var(--e-7) auto 0; }
.tela__nota { margin-top: var(--e-2); }
.tela__voltar { margin-top: var(--e-5); }
</style>
