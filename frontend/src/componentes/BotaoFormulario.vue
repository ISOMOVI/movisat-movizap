<script setup>
/* ============================================================================
   O botão do formulário, no menu "+" do campo de escrever (12/11)
   ----------------------------------------------------------------------------
   🔵 Dele, em 11/11: formulários *"pré-preenchidos quando abertos pelo botão
   dentro do chat"*. Em 12/11, sobre fazer: *"ok pode seguir"*.

   🚨 ESTE BOTÃO NÃO MANDA MENSAGEM NENHUMA. Ele monta o link e o escreve NO
   CAMPO DE RESPOSTA. Quem manda é a pessoa, clicando em "Enviar ao cliente"
   como em qualquer outra mensagem. Mensagem ao cliente é irreversível, e a
   régua da casa é confirmação antes de enviar -- então o gesto continua com
   quem fala. A rota do servidor também não envia nada, e isso está escrito
   lá.

   🚨 O LINK NÃO LEVA DADO DO CLIENTE. O que viaja é um bilhete opaco
   (`?c=...`); os valores sugeridos ficam na tabela. CNPJ e telefone na URL
   entrariam no log do servidor, no histórico do navegador de quem abrisse e
   em qualquer repasse do link.

   ⚠️ A LISTA VEM DA ROTA DA CONVERSA, não de `/api/formularios`: aquela pede
   `FRM_1.1`, que é tela **owner**, e o botão é de quem atende (`ATD_1.2`).
   Buscar lá deixaria nove de dez atendentes com a lista vazia.
   ============================================================================ */
import { computed, nextTick, onUnmounted, ref } from 'vue'

import { api, ErroDeApi } from '../api/cliente.js'

const props = defineProps({
  conversaId: { type: [Number, String], default: null },
})
const emit = defineEmits(['inserir'])

const aberto = ref(false)
const carregando = ref(false)
const erro = ref('')
const formularios = ref([])
const convites = ref([])
const busca = ref('')
const aqui = ref(0)
const montando = ref('')
const raiz = ref(null)
const campoBusca = ref(null)

const itens = computed(() => {
  const termo = busca.value.trim().toLowerCase()
  if (!termo) return formularios.value
  return formularios.value.filter(
    (f) => f.titulo.toLowerCase().includes(termo)
      || (f.setor || '').toLowerCase().includes(termo))
})

/* Só os convites que ainda servem para alguma coisa. Convite vencido na lista
   confundiria: quem o visse poderia achar que o cliente ainda pode usá-lo. */
const convitesVivos = computed(
  () => convites.value.filter((c) => !c.vencido && !c.usado_em))

async function abrir() {
  if (aberto.value) { fechar(); return }
  if (!props.conversaId) return
  aberto.value = true
  carregando.value = true
  erro.value = ''
  busca.value = ''
  aqui.value = 0
  document.addEventListener('mousedown', foraDoMenu)
  try {
    const r = await api.get(
      `/api/conversas/${props.conversaId}/links-de-formulario`)
    formularios.value = r.formularios || []
    convites.value = r.convites || []
  } catch (e) {
    erro.value = e instanceof ErroDeApi
      ? e.message : 'Não consegui ler os formulários.'
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
onUnmounted(() => document.removeEventListener('mousedown', foraDoMenu))

/* 🚨 ESCOLHER NÃO ENVIA: cria o convite no servidor e escreve o link no campo.
   A pessoa lê, acrescenta o que quiser, e só então clica em enviar. */
async function escolher(f) {
  if (montando.value) return
  montando.value = f.slug
  erro.value = ''
  try {
    const r = await api.post(
      `/api/conversas/${props.conversaId}/link-de-formulario`,
      { slug: f.slug })
    emit('inserir', r.url)
    convites.value = [{ ...r, titulo: f.titulo, vencido: false,
                        usado_em: null, aberturas: 0 }, ...convites.value]
    fechar()
  } catch (e) {
    /* ⚠️ A frase do servidor é melhor que a minha: formulário desligado volta
       com o interruptor da FRM_1.1, e isso é gesto de owner, não erro de quem
       clicou. */
    erro.value = e instanceof ErroDeApi
      ? e.message : 'Não consegui montar o link.'
  } finally {
    montando.value = ''
  }
}

function teclado(evento) {
  if (evento.key === 'Escape') { evento.preventDefault(); fechar(); return }
  if (!itens.value.length) return
  if (evento.key === 'ArrowDown') {
    evento.preventDefault()
    aqui.value = (aqui.value + 1) % itens.value.length
  }
  if (evento.key === 'ArrowUp') {
    evento.preventDefault()
    aqui.value = (aqui.value - 1 + itens.value.length) % itens.value.length
  }
  if (evento.key === 'Enter') {
    evento.preventDefault()
    escolher(itens.value[aqui.value])
  }
}

function quando(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' })
}
</script>

<template>
  <span ref="raiz" class="bf">
    <!-- ⚠️ ÍCONE **E** PALAVRA, pela régua escrita na tela da conversa:
         "ganha palavra o que age sobre a conversa". O Agendar segue a mesma. -->
    <button class="botao botao--contorno" type="button"
            :aria-expanded="aberto" aria-haspopup="dialog"
            :disabled="!conversaId"
            title="Mandar o link de um formulário já preenchido"
            @click="abrir">
      <i class="bi bi-ui-checks" aria-hidden="true"></i>
      <span>Formulário</span>
    </button>

    <div v-if="aberto" class="bf__menu" role="dialog"
         aria-label="Link de formulário" @keydown="teclado">
      <p class="bf__titulo">Mandar link de formulário</p>

      <!-- 🚨 AS DUAS COISAS QUE QUEM MANDA PRECISA SABER, ditas antes do
           clique e não depois: o link vence, e ele não carrega os dados. -->
      <p class="bf__nota pequeno fraco">
        O link vence em <strong>7 dias</strong> e já abre com o que a casa sabe
        deste cliente. Os dados <strong>não viajam no endereço</strong>.
      </p>

      <input ref="campoBusca" v-model="busca" class="campo__entrada bf__busca"
             type="search" placeholder="Procurar pelo nome ou setor"
             aria-label="Procurar formulário" @input="aqui = 0" />

      <p v-if="carregando" class="linha pequeno fraco">
        <span class="girando"></span> Lendo…
      </p>
      <p v-else-if="erro" class="aviso aviso--erro pequeno" role="alert">
        {{ erro }}
      </p>
      <ul v-else-if="itens.length" class="bf__lista" role="listbox">
        <li v-for="(f, i) in itens" :key="f.slug">
          <button type="button" class="bf__item"
                  :class="{ 'bf__item--aqui': i === aqui }"
                  :aria-selected="i === aqui"
                  :disabled="!!montando"
                  @mouseenter="aqui = i" @click="escolher(f)">
            <strong>{{ f.titulo }}</strong>
            <small class="apagado">
              <span v-if="montando === f.slug" class="girando"></span>
              {{ montando === f.slug ? 'montando o link…' : f.setor }}
            </small>
          </button>
        </li>
      </ul>
      <p v-else class="bf__vazio pequeno apagado">
        {{ busca ? 'Nada com esse nome.' : 'Nenhum formulário publicado.' }}
      </p>

      <!-- ⚠️ OS QUE JÁ SAÍRAM DAQUI. Sem isto, a pessoa manda o terceiro link
           do mesmo formulário sem saber que já mandou dois -- e o cliente
           recebe três endereços diferentes para a mesma coisa. -->
      <div v-if="convitesVivos.length" class="bf__ja">
        <p class="bf__ja__titulo pequeno">Já saíram desta conversa</p>
        <ul class="bf__ja__lista">
          <li v-for="c in convitesVivos" :key="c.bilhete" class="pequeno">
            <span>{{ c.titulo || c.slug }}</span>
            <span class="apagado">
              {{ quando(c.criado_em) }}<template v-if="c.criado_por_nome">
                · {{ c.criado_por_nome }}</template>
              · {{ c.aberturas ? 'aberto' : 'não aberto' }}
            </span>
          </li>
        </ul>
      </div>
    </div>
  </span>
</template>

<style scoped>
/* ⚠️ Nomes próprios (`bf__`), e não `.lista`/`.item` soltos: classe reusada em
   componente `scoped` não dá erro em lugar nenhum e transforma a conferência
   de CSS publicado num sorteio -- foi o que aconteceu com `.etapas` em
   11/11. */
.bf { position: relative; display: inline-flex; align-items: center; }

.bf__menu {
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
/* No celular o menu passaria da borda: vira folha fixa, com 16 px dos dois
   lados, logo acima da barra de status -- igual ao das mensagens rápidas. */
@media (max-width: 640px) {
  .bf__menu {
    position: fixed;
    left: var(--e-4);
    right: var(--e-4);
    bottom: calc(var(--altura-barra) + var(--e-4));
    width: auto;
    max-height: 70vh;
    overflow-y: auto;
  }
}
.bf__titulo { margin: 0; font-weight: var(--peso-forte); }
.bf__nota { margin: 0; }
.bf__busca { margin: 0; }
.bf__lista {
  list-style: none; margin: 0; padding: 0;
  max-height: 260px; overflow-y: auto;
}
.bf__item {
  display: flex; flex-direction: column; align-items: flex-start; gap: 2px;
  width: 100%; padding: var(--e-2); border: 0; border-radius: var(--r-md);
  background: transparent; color: inherit; font: inherit;
  text-align: left; cursor: pointer;
}
.bf__item--aqui { background: var(--acento-suave); }
.bf__item:disabled { cursor: progress; }
.bf__vazio { margin: 0; }
.bf__ja {
  border-top: var(--borda-fina) solid var(--borda);
  padding-top: var(--e-2);
}
.bf__ja__titulo { margin: 0 0 var(--e-1); font-weight: var(--peso-forte); }
.bf__ja__lista { list-style: none; margin: 0; padding: 0; }
.bf__ja__lista li {
  display: flex; justify-content: space-between; gap: var(--e-2);
  padding: 2px 0;
}
</style>
