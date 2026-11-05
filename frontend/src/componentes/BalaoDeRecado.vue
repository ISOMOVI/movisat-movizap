<script setup>
/* ============================================================================
   Um recado em formato de conversa — o balão do painel da Operação.
   ----------------------------------------------------------------------------
   🔵 04/11: *"Card OBS anexos, texto, format conve -- exibir em modal"*.

   🚨 ESTE COMPONENTE NÃO FOI EXTRAÍDO DA `CaixaDeEntrada.vue`, e isso é uma
   escolha declarada. O plano previa extrair, mas o markup das bolhas vive
   dentro de uma tela de ~4 mil linhas que é a mais usada do sistema, com
   modificadores próprios (`balao--casa`, `balao--atual`, `balao--tocado`,
   `balao--realcado`, mídia, citada, áudio). Mexer nela para reaproveitar
   bolha de recado seria risco desproporcional ao ganho.

   ⚠️ O custo está dito: agora há **três** desenhos de bolha no projeto — o da
   Caixa, o do Chat interno e este. Unificá-los é frente própria, e o recado
   aqui é bem mais simples que os outros dois (não tem mídia inline, nem
   citação, nem áudio).

   ⚠️ O recado do SISTEMA (`[checklist] ...`, `[sistema] prioridade: ...`) é
   desenhado diferente: ele não foi escrito por uma pessoa, e mostrá-lo igual
   a um recado humano faria parecer que alguém digitou aquilo.
   ============================================================================ */
import { computed } from 'vue'

const props = defineProps({
  recado: { type: Object, required: true },
  quando: { type: Function, required: true },
})

/* `[checklist]` e `[sistema]` são os dois prefixos que o servidor usa. */
const doSistema = computed(
  () => /^\[(checklist|sistema)\]/.test(props.recado.texto || ''))

const linhas = computed(() => String(props.recado.texto || '').split('\n'))

function tamanho(bytes) {
  if (!bytes) return ''
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}
</script>

<template>
  <li class="recado" :class="{ 'recado--sistema': doSistema }">
    <div class="recado__balao">
      <p v-for="(linha, i) in linhas" :key="i" class="recado__linha">{{ linha }}</p>

      <ul v-if="recado.anexos && recado.anexos.length" class="recado__anexos">
        <li v-for="a in recado.anexos" :key="a.id">
          <!-- ⚠️ O link leva o ID, nunca o caminho de disco. E abre em outra
               aba: baixar não pode tirar quem opera do painel. -->
          <a :href="`/api/paineis/operacao/anexo/${a.id}`" target="_blank"
             rel="noopener">
            <i class="bi bi-paperclip" aria-hidden="true"></i>
            {{ a.nome_original }}
          </a>
          <span class="apagado pequeno">{{ tamanho(a.bytes) }}</span>
        </li>
      </ul>
    </div>

    <p class="recado__pe apagado pequeno">
      <span v-if="doSistema">registrado pelo sistema</span>
      <span v-else>{{ recado.quem || 'sem autor' }}</span>
      <span>· {{ quando(recado.em) }}</span>
    </p>
  </li>
</template>

<style scoped>
.recado { list-style: none; margin: 0 0 var(--e-3); }

.recado__balao {
  background: var(--fundo-2, rgba(127, 127, 127, .08));
  border-radius: var(--raio, 8px);
  padding: var(--e-2) var(--e-3);
  /* ⚠️ O recado pode ter linha longa (o checklist tem). Quebrar é melhor que
     rolar na horizontal dentro do modal. */
  overflow-wrap: anywhere;
}

/* 🚨 O recado do sistema é visivelmente outro: barra na lateral E a frase
   "registrado pelo sistema" no pé. Cor sozinha não é portador. */
.recado--sistema .recado__balao {
  border-left: 3px solid var(--acento, #1B75BB);
  background: transparent;
}

.recado__linha { margin: 0; }
.recado__linha:empty { height: .5em; }

.recado__anexos {
  list-style: none;
  margin: var(--e-2) 0 0;
  padding: 0;
  display: grid;
  gap: var(--e-1);
}
.recado__anexos li { display: flex; align-items: center; gap: var(--e-2); }

.recado__pe { margin: var(--e-1) 0 0; display: flex; gap: var(--e-1); }
</style>
