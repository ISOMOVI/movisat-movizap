<script setup>
/* ============================================================================
   Casca do painel.
   ----------------------------------------------------------------------------
   Duas formas: tela pública (login) ocupa tudo; tela de sistema ganha menu,
   conteúdo e barra de status.

   A barra de status fica AQUI, fora do <RouterView>, para valer em toda tela
   sem que nenhuma tela precise lembrar de incluí-la — critério de pronto
   nº 10 ("toda tela mostra a barra com um código válido") não pode depender
   de disciplina de quem escreve a próxima tela.
   ============================================================================ */
import { computed } from 'vue'
import { useRoute } from 'vue-router'

import MenuLateral from './componentes/MenuLateral.vue'
import BarraStatus from './componentes/BarraStatus.vue'
import { autenticado } from './estado/sessao.js'

const rota = useRoute()
const comCasca = computed(() => autenticado.value && !rota.meta.publica)
</script>

<template>
  <div v-if="comCasca" class="painel">
    <MenuLateral />
    <main class="painel__conteudo">
      <RouterView />
    </main>
    <BarraStatus />
  </div>

  <RouterView v-else />
</template>

<style scoped>
.painel {
  display: grid;
  grid-template-areas:
    "menu conteudo"
    "barra barra";
  grid-template-columns: auto 1fr;
  grid-template-rows: 1fr auto;
  height: 100%;
}

.painel__conteudo {
  grid-area: conteudo;
  min-width: 0;
  overflow: auto;
  padding: var(--e-6) var(--e-7);
}

@media (max-width: 860px) {
  .painel__conteudo { padding: var(--e-4); }
}
</style>
