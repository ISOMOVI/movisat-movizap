<!--
  CFG_17.1 — CHECKLIST DE CARDS
  ============================================================================
  🔵 11/11, dele: *"boa sugestão, pode fazer uma outra aba só para isso de
  'Checklist de Cards' vamos centralizar os fixos ali"*.

  🚨 ESTA TELA NASCE PARA ROTAS QUE JÁ ESTAVAM NO AR SEM PORTA. As rotas de
  modelo do checklist existem desde 04/11 e **ninguém nunca pôde usá-las**: não
  havia tela e não havia trava. Até hoje, acrescentar item na lista de uma etapa
  só era possível escrevendo uma migração.

  🚨 MEXER AQUI MUDA O CARD DE TODO MUNDO, e é por isso que a aba é `owner` e as
  rotas de escrita pedem a `CFG_17.1` -- não a permissão do painel.

  ⚠️ MAS NÃO REESCREVE CARD JÁ ABERTO. O item do card é CÓPIA do modelo
  (migração 090): mudar o texto aqui não reescreve o que alguém já marcou, e
  desativar não tira o item de quem já o tinha. A tela diz isso em texto, porque
  é a primeira coisa que alguém supõe errado.

  ✅ E ACRESCENTAR É ADITIVO: item novo entra no card na próxima abertura
  daquela etapa, inclusive em card que já estava aberto -- sem tocar no que está
  marcado.
-->
<script setup>
import { computed, onMounted, ref } from 'vue'

import { api, ErroDeApi } from '../api/cliente.js'

const etapas = ref([])
const carregando = ref(true)
const erro = ref('')
const salvando = ref(0)

/* O texto novo, por etapa: um campo por linha da lista, e não um só
   compartilhado -- com um campo único, escrever e trocar de etapa levaria o
   texto para a etapa errada. */
const novo = ref({})

/* ⚠️ Etapa aberta, uma por vez: são 17 listas, e todas abertas de uma vez dão
   uma página de rolagem infinita em que ninguém acha nada. */
const aberta = ref(null)

const comLista = computed(
  () => etapas.value.filter((e) => e.itens.some((i) => i.ativo)).length)

async function carregar() {
  carregando.value = true
  erro.value = ''
  try {
    const r = await api.get('/api/config/checklist-de-cards')
    etapas.value = r.etapas || []
  } catch (e) {
    erro.value = e instanceof ErroDeApi
      ? e.message : 'Não consegui ler as listas das etapas.'
  } finally {
    carregando.value = false
  }
}

function ativos(etapa) {
  return etapa.itens.filter((i) => i.ativo)
}

async function acrescentar(etapa) {
  const texto = String(novo.value[etapa.situacao_id] || '').trim()
  if (!texto || salvando.value) return
  salvando.value = etapa.situacao_id
  erro.value = ''
  try {
    /* A ordem é a próxima: quem acrescenta quer o item no FIM da lista, e não
       no meio dela. */
    const ordem = ativos(etapa).length + 1
    await api.post('/api/paineis/operacao/checklist/modelo',
                   { situacao_id: etapa.situacao_id, texto, ordem })
    novo.value[etapa.situacao_id] = ''
    await carregar()
  } catch (e) {
    erro.value = e instanceof ErroDeApi
      ? e.message : 'Não consegui acrescentar este item.'
  } finally {
    salvando.value = 0
  }
}

async function renomear(item, texto) {
  const limpo = String(texto || '').trim()
  if (!limpo || limpo === item.texto || salvando.value) return
  salvando.value = item.id
  erro.value = ''
  try {
    await api.put(`/api/paineis/operacao/checklist/modelo/${item.id}`,
                  { situacao_id: item.situacao_id, texto: limpo,
                    ordem: item.ordem, ativo: item.ativo })
    await carregar()
  } catch (e) {
    erro.value = e instanceof ErroDeApi
      ? e.message : 'Não consegui mudar este item.'
  } finally {
    salvando.value = 0
  }
}

/* 🚨 DESATIVAR, E NÃO APAGAR -- é a régua da casa, e aqui ela tem motivo
   concreto: o item apagado continuaria no card de quem já o tinha, e a lista
   deixaria de explicar de onde ele veio. */
async function alternar(item) {
  if (salvando.value) return
  salvando.value = item.id
  erro.value = ''
  try {
    await api.put(`/api/paineis/operacao/checklist/modelo/${item.id}`,
                  { situacao_id: item.situacao_id, texto: item.texto,
                    ordem: item.ordem, ativo: !item.ativo })
    await carregar()
  } catch (e) {
    erro.value = e instanceof ErroDeApi
      ? e.message : 'Não consegui mudar este item.'
  } finally {
    salvando.value = 0
  }
}

onMounted(carregar)
</script>

<template>
  <section class="checklist">
    <header class="checklist__topo">
      <h2>Checklist de Cards</h2>
      <!-- 🚨 ESTADO, NÃO PARÁGRAFO. Ele já tirou texto explicativo de tela
           três vezes (*"atrapalha o profissionalismo"*), e a régua da casa é
           que a tela diga o ESTADO. O que o item desativado faz nos cards
           antigos está escrito na própria linha dele, onde é estado. -->
      <p class="nota pequeno">
        <strong>{{ comLista }} de {{ etapas.length }}</strong> etapas com lista
        · vale para os próximos cards
      </p>
    </header>

    <p v-if="carregando" class="nota pequeno">lendo…</p>
    <p v-if="erro" class="aviso aviso--erro" role="alert">{{ erro }}</p>

    <ul v-if="!carregando" class="etapas">
      <li v-for="e in etapas" :key="e.situacao_id" class="etapa">
        <button type="button" class="etapa__porta"
                :aria-expanded="aberta === e.situacao_id"
                @click="aberta = aberta === e.situacao_id ? null : e.situacao_id">
          <strong>{{ e.nome }}</strong>
          <span class="pilula"
                :class="ativos(e).length ? 'pilula--pronto' : 'pilula--alerta'">
            {{ ativos(e).length }}
            {{ ativos(e).length === 1 ? 'item' : 'itens' }}
          </span>
        </button>

        <div v-if="aberta === e.situacao_id" class="etapa__corpo">
          <ul v-if="e.itens.length" class="itens">
            <li v-for="i in e.itens" :key="i.id" class="item"
                :class="{ 'item--inativo': !i.ativo }">
              <input class="campo__entrada" :value="i.texto"
                     :disabled="!i.ativo || salvando === i.id"
                     :aria-label="`Texto do item ${i.ordem} de ${e.nome}`"
                     @change="renomear(i, $event.target.value)" />
              <!-- ⚠️ "Desativar"/"Reativar" por extenso: um ✕ aqui pareceria
                   apagar, e apagar é o que esta tela não faz. -->
              <button type="button" class="botao botao--pequeno botao--fantasma"
                      :disabled="salvando === i.id" @click="alternar(i)">
                {{ i.ativo ? 'Desativar' : 'Reativar' }}
              </button>
              <span v-if="!i.ativo" class="apagado pequeno">
                fora da lista — segue nos cards que já o tinham
              </span>
            </li>
          </ul>
          <p v-else class="nota pequeno">
            Esta etapa não tem lista: o card não mostra o botão do checklist, e
            mover para cá não dá aviso.
          </p>

          <div class="etapa__novo">
            <input v-model="novo[e.situacao_id]" class="campo__entrada"
                   placeholder="+ Acrescentar item a esta etapa"
                   :aria-label="`Acrescentar item a ${e.nome}`"
                   @keyup.enter="acrescentar(e)" />
            <button class="botao" type="button"
                    :disabled="!String(novo[e.situacao_id] || '').trim()
                               || salvando === e.situacao_id"
                    @click="acrescentar(e)">Acrescentar</button>
          </div>
        </div>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.checklist { display: flex; flex-direction: column; gap: var(--e-4); }
.checklist__topo h2 { margin: 0 0 var(--e-1); font-size: var(--txt-lg); }
.checklist__topo .nota { margin: 0 0 var(--e-1); }

.etapas { list-style: none; margin: 0; padding: 0;
          display: flex; flex-direction: column; gap: var(--e-2); }

.etapa { border: 1px solid var(--borda); border-radius: var(--r-md);
         background: var(--superficie); overflow: hidden; }

.etapa__porta {
  width: 100%; display: flex; align-items: center; justify-content: space-between;
  gap: var(--e-3); padding: var(--e-3) var(--e-4);
  min-height: var(--altura-toque);
  background: none; border: 0; font: inherit; color: inherit;
  cursor: pointer; text-align: left;
}
.etapa__porta:hover { background: var(--superficie-2); }

.etapa__corpo { padding: 0 var(--e-4) var(--e-4);
                display: flex; flex-direction: column; gap: var(--e-3); }

.itens { list-style: none; margin: 0; padding: 0;
         display: flex; flex-direction: column; gap: var(--e-2); }

/* ⚠️ `wrap` e `min-width` no campo: em tela de celular os três elementos da
   linha não cabem lado a lado, e sem isto o botão sai da tela. */
.item { display: flex; align-items: center; gap: var(--e-2); flex-wrap: wrap; }
.item .campo__entrada { flex: 1 1 14rem; min-width: 0; }
.item--inativo .campo__entrada { text-decoration: line-through; opacity: .6; }

.etapa__novo { display: flex; gap: var(--e-2); flex-wrap: wrap; }
.etapa__novo .campo__entrada { flex: 1 1 14rem; min-width: 0; }

/* 🚨 A `.pilula` É SCOPED POR COMPONENTE nesta casa -- ela não existe em
   `estilo/*.css`. O `PainelOperacao` e o `PainelAba` definem cada um a sua, e
   tela nova que usa a classe sem declarar fica com o selo SEM ESTILO: não
   quebra, não avisa, só fica feio. ⚠️ Nenhuma trava de tela pega isso, porque
   o jsdom não faz layout.
   ⚠️ Os valores são os do `PainelAba`, para os selos da casa parecerem os
   mesmos selos. */
.pilula {
  display: inline-flex; align-items: center; gap: var(--e-1);
  align-self: flex-start;
  padding: 1px var(--e-2); border-radius: var(--r-full);
  background: var(--superficie-2); color: var(--texto-fraco);
  font-size: var(--txt-xs); font-weight: var(--peso-forte);
}
/* ⚠️ Os dois que alertam diferem em LUMINOSIDADE, não só em matiz -- âmbar e
   verde, nunca vermelho e verde. É a régua do card. */
.pilula--alerta {
  color: var(--aviso-texto); background: var(--aviso-suave);
}
.pilula--pronto {
  color: var(--ok-texto); background: var(--ok-suave);
}
.pilula--neutra {
  color: var(--texto-fraco); background: var(--superficie-2);
}
</style>
