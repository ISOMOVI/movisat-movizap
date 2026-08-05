<script setup>
/* ============================================================================
   Tela de fase 1 registrada, roteada e ainda sem implementação.
   ----------------------------------------------------------------------------
   Não é enfeite: existe para que o esqueleto esteja COMPLETO — as 12 telas de
   fase 1 navegáveis, com código válido na barra de status (critério de pronto
   nº 10) — enquanto o conteúdo de cada uma chega.

   Dizer o que falta é intencional. "Em breve" sem dizer o que trava é como o
   MoviServer ficou com 4 telas em branco sem ninguém saber o motivo.
   ============================================================================ */
defineProps({
  codigo: { type: String, required: true },
  titulo: { type: String, required: true },
  oQueVemAqui: { type: String, default: '' },
})
</script>

<template>
  <div class="tela">
    <header class="tela__cabecalho">
      <h1>{{ titulo }}</h1>
      <span class="chip chip--codigo chip--acento">{{ codigo }}</span>
    </header>

    <div class="vazio">
      <i class="bi bi-cone-striped vazio__icone" aria-hidden="true"></i>
      <p class="vazio__titulo">Tela registrada, conteúdo ainda não</p>
      <p v-if="oQueVemAqui" class="tela__texto">{{ oQueVemAqui }}</p>
      <p class="apagado pequeno tela__nota">
        O código <span class="mono">{{ codigo }}</span> já está reservado no registro
        do backend, a rota existe e a permissão é aplicada. Falta o conteúdo.
      </p>
    </div>
  </div>
</template>

<style scoped>
.tela { max-width: 900px; }

.tela__cabecalho {
  display: flex;
  align-items: center;
  gap: var(--e-3);
  margin-bottom: var(--e-5);
}

.tela__texto {
  max-width: var(--largura-texto);
  margin: 0 auto;
  color: var(--texto-fraco);
}
.tela__nota { margin-top: var(--e-4); }
</style>
