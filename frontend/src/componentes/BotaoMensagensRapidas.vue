<script setup>
/* ============================================================================
   O botão das mensagens rápidas, no canto do campo de escrever (25/09)
   ----------------------------------------------------------------------------
   🔵 *"no canto inferior das conversas, pode ter o botão redondinho onde abre
   um menu dos tipos de Notas: Padrões; Minhas notas; e ao escolher, o texto
   vai para o campo de digitação, mas pode ser editado ainda"* -- e *"Só o
   botão"* (sem atalho `/`). No Chat interno, 🔵 *"Minhas notas e
   Formulários"*.

   🟡 O menu tem busca no topo e anda por teclado (setas, Enter, Esc), como a
   lista do `@` que já existe no mesmo campo. A lista vem do servidor ao abrir:
   quem acabou de criar uma nota em Configurações a vê sem recarregar.
   ============================================================================ */
import { computed, nextTick, onUnmounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import { api, ErroDeApi } from '../api/cliente.js'
import { aplicarVariaveis, rotuloDe } from '../util/variaveis.js'

const props = defineProps({
  onde: { type: String, default: 'cliente' },          // 'cliente' | 'interno'
  dados: { type: Object, default: () => ({}) },         // { cliente, contato }
})
const emit = defineEmits(['inserir'])

const NOMES = { padrao: 'Padrões', nota: 'Minhas notas', formulario: 'Formulários' }

const aberto = ref(false)
const carregando = ref(false)
const erro = ref('')
const grupos = ref({})
const tipo = ref('')
const busca = ref('')
const aqui = ref(0)
const aviso = ref('')
const raiz = ref(null)
const campoBusca = ref(null)
let relogioAviso = null

const tipos = computed(() => Object.keys(grupos.value))
const itens = computed(() => {
  const termo = busca.value.trim().toLowerCase()
  const lista = grupos.value[tipo.value] || []
  if (!termo) return lista
  return lista.filter((m) => m.apelido.toLowerCase().includes(termo)
    || m.conteudo.toLowerCase().includes(termo))
})

async function abrir() {
  if (aberto.value) { fechar(); return }
  aberto.value = true
  carregando.value = true
  erro.value = ''
  busca.value = ''
  aqui.value = 0
  document.addEventListener('mousedown', foraDoMenu)
  try {
    grupos.value = await api.get(`/api/mensagens-rapidas?onde=${props.onde}`)
    if (!tipos.value.includes(tipo.value)) {
      // Abre no primeiro tipo que tem alguma coisa; senão, no primeiro.
      tipo.value = tipos.value.find((t) => grupos.value[t].length) || tipos.value[0] || ''
    }
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui ler as mensagens rápidas.'
  } finally {
    carregando.value = false
    nextTick(() => campoBusca.value?.focus())
  }
}

function fechar() {
  aberto.value = false
  document.removeEventListener('mousedown', foraDoMenu)
}
function foraDoMenu(evento) {
  if (raiz.value && !raiz.value.contains(evento.target)) fechar()
}
onUnmounted(() => {
  document.removeEventListener('mousedown', foraDoMenu)
  clearTimeout(relogioAviso)
})

function trocarTipo(t) {
  tipo.value = t
  aqui.value = 0
}

function escolher(m) {
  const { texto, faltando } = aplicarVariaveis(m.conteudo, props.dados)
  emit('inserir', texto)
  fechar()
  clearTimeout(relogioAviso)
  aviso.value = faltando.length
    ? `Sem dado para ${faltando.map(rotuloDe).join(' e ')}: ficou em branco. Confira antes de enviar.`
    : ''
  if (aviso.value) relogioAviso = setTimeout(() => { aviso.value = '' }, 10000)
}

function teclado(evento) {
  if (evento.key === 'Escape') { evento.preventDefault(); fechar(); return }
  if (!itens.value.length) return
  if (evento.key === 'ArrowDown') { evento.preventDefault(); aqui.value = (aqui.value + 1) % itens.value.length }
  if (evento.key === 'ArrowUp') { evento.preventDefault(); aqui.value = (aqui.value - 1 + itens.value.length) % itens.value.length }
  if (evento.key === 'Enter') { evento.preventDefault(); escolher(itens.value[aqui.value]) }
}
</script>

<template>
  <span ref="raiz" class="mr">
    <button class="botao botao--contorno botao--icone mr__botao" type="button"
            :aria-expanded="aberto" aria-haspopup="dialog"
            title="Mensagens rápidas" aria-label="Mensagens rápidas" @click="abrir">
      <i class="bi bi-lightning-charge" aria-hidden="true"></i>
    </button>

    <div v-if="aberto" class="mr__menu" role="dialog" aria-label="Mensagens rápidas"
         @keydown="teclado">
      <p class="mr__titulo">Mensagens rápidas</p>
      <div v-if="tipos.length > 1" class="mr__tipos" role="tablist">
        <button v-for="t in tipos" :key="t" type="button" role="tab" class="mr__tipo"
                :class="{ 'mr__tipo--ativo': tipo === t }" :aria-selected="tipo === t"
                @click="trocarTipo(t)">
          {{ NOMES[t] }}
          <span class="mr__conta">{{ grupos[t].length }}</span>
        </button>
      </div>
      <input ref="campoBusca" v-model="busca" class="campo__entrada mr__busca" type="search"
             placeholder="Procurar pelo apelido" aria-label="Procurar mensagem rápida"
             @input="aqui = 0" />

      <p v-if="carregando" class="linha pequeno fraco"><span class="girando"></span> Lendo…</p>
      <p v-else-if="erro" class="aviso aviso--erro pequeno">{{ erro }}</p>
      <ul v-else-if="itens.length" class="mr__lista" role="listbox">
        <li v-for="(m, i) in itens" :key="m.id">
          <button type="button" class="mr__item" :class="{ 'mr__item--aqui': i === aqui }"
                  :aria-selected="i === aqui" @mouseenter="aqui = i" @click="escolher(m)">
            <strong>{{ m.apelido }}</strong>
            <small class="apagado">{{ m.conteudo }}</small>
          </button>
        </li>
      </ul>
      <p v-else class="mr__vazio pequeno apagado">
        {{ busca ? 'Nada com esse nome.' : 'Nenhuma mensagem aqui ainda.' }}
        <RouterLink to="/config/mensagens-rapidas" @click="fechar">Criar em Configurações</RouterLink>
      </p>
    </div>

    <span v-if="aviso" class="mr__aviso pequeno" role="status">
      <i class="bi bi-exclamation-triangle" aria-hidden="true"></i> {{ aviso }}
    </span>
  </span>
</template>

<style scoped>
.mr { position: relative; display: inline-flex; align-items: center; gap: var(--e-2); }
.mr__botao { border-radius: var(--r-full); }

.mr__menu {
  position: absolute;
  bottom: calc(100% + var(--e-2));
  left: 0;
  z-index: var(--z-flutuante);
  width: min(380px, calc(100vw - 2 * var(--e-4)));
  display: flex;
  flex-direction: column;
  gap: var(--e-2);
  padding: var(--e-3);
  border: var(--borda-fina) solid var(--borda);
  border-radius: var(--r-lg);
  background: var(--superficie);
  box-shadow: var(--sombra-2);
}
/* No celular o menu passava da borda direita (visto na prévia de 25/09): o
   botão não fica no canto esquerdo da tela. Vira uma folha fixa, com 16 px de
   margem dos dois lados, logo acima da barra de status. */
@media (max-width: 640px) {
  .mr__menu {
    position: fixed;
    left: var(--e-4);
    right: var(--e-4);
    bottom: calc(var(--altura-barra) + var(--e-4));
    width: auto;
    max-height: 70vh;
    overflow-y: auto;
  }
}
.mr__titulo { margin: 0; font-weight: var(--peso-forte); }
.mr__tipos { display: flex; flex-wrap: wrap; gap: var(--e-1); }
.mr__tipo {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 4px var(--e-2); border: var(--borda-fina) solid var(--borda);
  border-radius: var(--r-full); background: var(--superficie);
  font: inherit; font-size: var(--txt-sm); cursor: pointer;
}
.mr__tipo--ativo { border-color: var(--acento); background: var(--acento-suave); color: var(--acento); }
.mr__conta { font-size: var(--txt-xs); color: var(--texto-apagado); }
.mr__busca { margin: 0; }
.mr__lista { list-style: none; margin: 0; padding: 0; max-height: 260px; overflow-y: auto; }
.mr__item {
  display: flex; flex-direction: column; align-items: flex-start; gap: 2px;
  width: 100%; padding: var(--e-2); border: 0; border-radius: var(--r-md);
  background: transparent; color: inherit; font: inherit; text-align: left; cursor: pointer;
}
.mr__item small {
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  overflow: hidden; overflow-wrap: anywhere;
}
.mr__item--aqui { background: var(--acento-suave); }
.mr__vazio { margin: 0; }
.mr__aviso { color: var(--aviso); max-width: 360px; }
</style>
