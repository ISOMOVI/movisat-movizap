<script setup>
/* ============================================================================
   O que esta tela é, num ícone.
   ----------------------------------------------------------------------------
   Pedido dele em 27/08: *"as abas tem textos explicativos do que as telas são,
   o que fazem e o que falta... transforme em balões ícones apenas, se passar
   mouse aparece os textos"*.

   🚨 UM COMPONENTE, NÃO TREZE EDIÇÕES. O texto explicativo vive em 13 telas
   com a mesma marcação; treze cópias do mesmo balão divergiriam na primeira
   vez que alguém mexesse numa delas.

   🚨 O TEXTO NÃO SE PERDE, ELE SE RECOLHE. Continua no fonte, continua no DOM
   e continua legível por leitor de tela -- some só da vista de quem já sabe o
   que a tela faz. Esconder informação atrás de um ícone que não a devolve
   seria trocar um problema por outro.

   ⚠️ ABRE NO HOVER **E** NO FOCO. Só no hover, quem usa teclado e quem usa
   toque nunca leriam o texto -- é o mesmo defeito das ações do balão, que
   custou uma auditoria em 27/08.
   ============================================================================ */
defineProps({
  /* Rótulo do gatilho para quem não vê o ícone. O `?` sozinho não diz nada. */
  titulo: { type: String, default: 'O que esta tela faz' },
})
</script>

<template>
  <span class="ajuda">
    <button class="ajuda__gatilho" type="button"
            :aria-label="titulo" :title="titulo">
      <i class="bi bi-question-circle" aria-hidden="true"></i>
    </button>
    <!-- `role="tooltip"` e não `title`: o `title` do navegador demora ~1s,
         não formata e não dá para ler no celular. -->
    <span class="ajuda__balao" role="tooltip"><slot /></span>
  </span>
</template>

<style scoped>
.ajuda { position: relative; display: inline-flex; vertical-align: middle; }

.ajuda__gatilho {
  display: grid;
  place-items: center;
  width: 22px;
  height: 22px;
  padding: 0;
  border: 0;
  border-radius: var(--r-full);
  background: none;
  color: var(--texto-apagado);
  cursor: help;
  font-size: 14px;
  line-height: 1;
  transition: color var(--tempo-rapido) var(--curva),
              background var(--tempo-rapido) var(--curva);
}
.ajuda:hover .ajuda__gatilho,
.ajuda:focus-within .ajuda__gatilho {
  color: var(--acento);
  background: var(--acento-suave);
}
.ajuda__gatilho:focus-visible { outline: none; box-shadow: var(--foco); }

.ajuda__balao {
  position: absolute;
  top: calc(100% + 6px);
  left: 0;
  z-index: var(--z-flutuante);
  /* ⚠️ Largura com teto E piso: sem o piso, um texto curto vira uma tira de
     duas palavras por linha; sem o teto, um longo atravessa a tela. */
  width: max-content;
  min-width: 220px;
  max-width: 380px;
  padding: var(--e-3);
  background: var(--superficie);
  border: var(--borda-fina) solid var(--borda);
  border-radius: var(--r-md);
  box-shadow: var(--sombra-2);
  font-size: var(--txt-sm);
  font-weight: var(--peso-normal);
  line-height: var(--entrelinha);
  color: var(--texto-fraco);
  text-align: left;
  letter-spacing: normal;
  text-transform: none;

  /* 🚨 `visibility`, NÃO `display: none`. Com `display:none` o conteúdo sai da
     árvore e alguns leitores de tela deixam de anunciá-lo; e foi exatamente o
     `display:none` que tirou as ações do balão do alcance do teclado. */
  visibility: hidden;
  opacity: 0;
  transform: translateY(-3px);
  transition: opacity var(--tempo) var(--curva),
              transform var(--tempo) var(--curva),
              visibility var(--tempo);
}
.ajuda:hover .ajuda__balao,
.ajuda:focus-within .ajuda__balao {
  visibility: visible;
  opacity: 1;
  transform: none;
}

/* Encostado na direita da tela, o balão sai pela borda: nas telas estreitas
   ele passa a se ancorar pelo outro lado. */
@media (max-width: 860px) {
  .ajuda__balao { left: auto; right: 0; }
}
</style>
