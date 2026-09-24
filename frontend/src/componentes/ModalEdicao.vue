<script setup>
/* ============================================================================
   Modal de edição — o formulário que PERGUNTA antes de jogar fora
   ----------------------------------------------------------------------------
   🔵 Pedido dele em 24/09 (CAD_2.1): *"o botão editar dos atendentes deve abrir
   um modal e fizer alterações e clicar fora, deve perguntar se deseja
   descartar as alterações 'Descartar' - 'Continuar editando' e no fim do
   modal, os botões 'Salvar' - 'Cancelar alterações'"*. Times usa o mesmo.

   ⚠️ O `.modal` global fecha ao clique no fundo, e ali isso é o lado seguro
   (fechar = cancelar uma confirmação). AQUI NÃO É: fechar por engano perde o
   que a pessoa digitou. Por isso clique fora e Esc só fecham direto quando
   nada mudou; com mudança, perguntam.

   ⚠️ "CLIQUE FORA" É APERTAR E SOLTAR NO FUNDO. Quem seleciona texto num campo
   e solta o mouse além da borda dispara `click` no fundo -- sem conferir onde
   o botão desceu, arrastar uma seleção pediria para descartar.

   "Cancelar alterações" é pedido explícito: fecha sem perguntar.
   ============================================================================ */
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue'

const props = defineProps({
  titulo: { type: String, required: true },
  subtitulo: { type: String, default: '' },
  sujo: { type: Boolean, default: false },
  salvando: { type: Boolean, default: false },
  podeSalvar: { type: Boolean, default: true },
})
const emit = defineEmits(['salvar', 'fechar'])

const confirmando = ref(false)
const caixa = ref(null)
let desceuNoFundo = false

function tentarFechar() {
  if (props.salvando) return
  if (props.sujo) confirmando.value = true
  else emit('fechar')
}

function aoDescer(e) { desceuNoFundo = e.target === e.currentTarget }
function aoClicarNoFundo(e) {
  if (desceuNoFundo && e.target === e.currentTarget) tentarFechar()
  desceuNoFundo = false
}

function aoTeclar(e) {
  if (e.key !== 'Escape') return
  e.preventDefault()
  if (confirmando.value) confirmando.value = false
  else tentarFechar()
}

onMounted(async () => {
  document.addEventListener('keydown', aoTeclar)
  await nextTick()
  caixa.value?.querySelector('input:not([type=checkbox]):not([disabled]), select, textarea')?.focus()
})
onBeforeUnmount(() => document.removeEventListener('keydown', aoTeclar))
</script>

<template>
  <div class="modal edicao" @mousedown="aoDescer" @click="aoClicarNoFundo">
    <div ref="caixa" class="edicao__caixa" role="dialog" aria-modal="true" :aria-label="titulo">
      <header class="edicao__topo">
        <slot name="icone" />
        <div class="edicao__titulos">
          <p class="edicao__titulo">{{ titulo }}</p>
          <p v-if="subtitulo" class="edicao__subtitulo">{{ subtitulo }}</p>
        </div>
        <span v-if="sujo" class="chip chip--pequeno chip--aviso">não salvo</span>
      </header>

      <div class="edicao__corpo">
        <slot />
      </div>

      <footer class="edicao__rodape">
        <button class="botao botao--primario" type="button"
                :disabled="salvando || !podeSalvar" @click="emit('salvar')">
          <span v-if="salvando" class="girando"></span>
          {{ salvando ? 'Salvando…' : 'Salvar' }}
        </button>
        <button class="botao botao--contorno" type="button" :disabled="salvando"
                @click="emit('fechar')">
          Cancelar alterações
        </button>
      </footer>

      <!-- A pergunta mora DENTRO da caixa: é sobre este formulário, e o fundo
           escurecido de um segundo modal esconderia o que vai ser perdido. -->
      <div v-if="confirmando" class="edicao__pergunta" role="alertdialog"
           aria-label="Descartar alterações?">
        <div class="edicao__pergunta-caixa">
          <p class="modal__titulo">Descartar as alterações?</p>
          <p class="modal__texto">O que você mudou neste formulário ainda não foi salvo.</p>
          <div class="edicao__pergunta-acoes">
            <button class="botao botao--perigo" type="button" @click="emit('fechar')">
              Descartar
            </button>
            <button class="botao botao--primario" type="button" @click="confirmando = false">
              Continuar editando
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.edicao { align-items: center; }

.edicao__caixa {
  position: relative;
  display: flex;
  flex-direction: column;
  width: 100%;
  max-width: 760px;
  max-height: min(90vh, 900px);
  border: var(--borda-fina) solid var(--borda);
  border-radius: var(--r-lg);
  background: var(--superficie);
  box-shadow: 0 24px 64px rgba(15, 23, 42, .28), 0 4px 12px rgba(15, 23, 42, .12);
  overflow: hidden;
}

.edicao__topo {
  display: flex;
  align-items: center;
  gap: var(--e-3);
  padding: var(--e-4) var(--e-5);
  border-bottom: var(--borda-fina) solid var(--borda);
  background: var(--superficie-2);
}
.edicao__titulos { flex: 1; min-width: 0; }
.edicao__titulo {
  margin: 0;
  font-size: var(--txt-lg);
  font-weight: var(--peso-forte);
  color: var(--texto);
  overflow-wrap: anywhere;
}
.edicao__subtitulo { margin: 2px 0 0; font-size: var(--txt-sm); color: var(--texto-apagado); }

.edicao__corpo {
  flex: 1;
  overflow-y: auto;
  padding: var(--e-5);
}

/* Rodapé fixo: o Salvar não pode sumir rolando junto com uma jornada longa. */
.edicao__rodape {
  display: flex;
  flex-wrap: wrap;
  gap: var(--e-2);
  padding: var(--e-3) var(--e-5);
  border-top: var(--borda-fina) solid var(--borda);
  background: var(--superficie);
}

.edicao__pergunta {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--e-4);
  background: rgba(15, 23, 42, .45);
}
.edicao__pergunta-caixa {
  width: 100%;
  max-width: 380px;
  padding: var(--e-5);
  border: var(--borda-fina) solid var(--borda);
  border-radius: var(--r-lg);
  background: var(--superficie);
  box-shadow: var(--sombra-2);
}
.edicao__pergunta-acoes { display: flex; flex-wrap: wrap; gap: var(--e-2); }

@media (max-width: 640px) {
  .edicao { padding: 0; align-items: stretch; }
  .edicao__caixa { max-width: none; max-height: none; height: 100%; border-radius: 0; border: 0; }
  .edicao__topo, .edicao__corpo, .edicao__rodape { padding-left: var(--e-4); padding-right: var(--e-4); }
  .edicao__rodape .botao { flex: 1; }
}
</style>
