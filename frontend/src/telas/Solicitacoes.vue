<script setup>
/* ============================================================================
   FRM_1.1 — Solicitações.
   ----------------------------------------------------------------------------
   O que chega pelos formulários próprios (`forms.movisat.com.br`). Lista à
   esquerda, a solicitação aberta à direita -- o mesmo arranjo do Histórico,
   porque é o mesmo gesto: varrer uma lista e ler um item.

   🚨 O ESTADO É DE TRÊS VALORES (`nova`, `em_andamento`, `concluida`) e é ele
   que o selo do menu conta -- a MESMA coluna, para a bolinha nunca discordar
   da lista. Em 22/10 um selo de e-mail nasceu de uma cópia do `WHERE` da aba
   e mostrou 61 onde a verdade era 5.

   ⚠️ A FICHA MOSTRA O RÓTULO, NÃO O NOME DO CAMPO: `DEAL_UF_CRM_DEAL_164944…`
   é o nome de origem do Bitrix, e o número dentro dele é o timestamp em que
   alguém criou o campo. Quem traduz é o servidor, com a definição de agora.

   ⚠️ Campo que SAIU da definição continua aparecendo, pela chave crua e
   marcado -- sumi-lo seria a tela mentir sobre o que a pessoa respondeu.

   🔵 22/10: ligar/desligar formulário é do OWNER (abrir um formulário é abrir
   uma porta para a internet). A rota também recusa quem não é.
   ============================================================================ */
import { computed, onMounted, ref } from 'vue'

import { api, ErroDeApi } from '../api/cliente.js'
import { sessao } from '../estado/sessao.js'
import AjudaDaTela from '../componentes/AjudaDaTela.vue'

const ESTADOS = [
  { valor: 'nova', rotulo: 'Nova' },
  { valor: 'em_andamento', rotulo: 'Em andamento' },
  { valor: 'concluida', rotulo: 'Concluída' },
]

const formularios = ref([])
const solicitacoes = ref([])
const aberta = ref(null)
const filtroFormulario = ref('')
const filtroEstado = ref('')
const carregando = ref(true)
const erro = ref('')
const recado = ref('')

const souOwner = computed(() => Boolean(sessao.usuario?.owner))

async function carregar() {
  carregando.value = true
  erro.value = ''
  try {
    const busca = new URLSearchParams()
    if (filtroFormulario.value) busca.set('formulario', filtroFormulario.value)
    if (filtroEstado.value) busca.set('estado', filtroEstado.value)
    const sufixo = busca.toString() ? `?${busca}` : ''
    ;[formularios.value, solicitacoes.value] = await Promise.all([
      api.get('/api/formularios'),
      api.get(`/api/solicitacoes${sufixo}`),
    ])
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message
      : 'Não consegui ler as solicitações.'
  } finally {
    carregando.value = false
  }
}

async function abrir(id) {
  erro.value = ''
  try {
    aberta.value = await api.get(`/api/solicitacoes/${id}`)
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui abrir.'
  }
}

async function mudarEstado(estado) {
  if (!aberta.value) return
  try {
    const r = await api.put(`/api/solicitacoes/${aberta.value.id}/estado`, { estado })
    aberta.value = { ...aberta.value, estado: r.estado, lida_em: r.lida_em }
    recado.value = 'Estado salvo.'
    await carregar()
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui salvar.'
  }
}

async function alternarFormulario(f) {
  try {
    const r = await api.put(`/api/formularios/${f.codigo}/ativo`, { ativo: !f.ativo })
    recado.value = r.ativo
      ? `${f.titulo} está no ar em /f/${r.slug}`
      : `${f.titulo} saiu do ar — o link responde "não encontrado".`
    await carregar()
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui mudar.'
  }
}

function quando(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })
}

function resumo(s) {
  /* As duas primeiras respostas, só para a pessoa reconhecer a linha. */
  const valores = Object.values(s.valores || {}).filter((v) => typeof v === 'string')
  return valores.slice(0, 2).join(' · ') || '—'
}

function valorLegivel(resposta) {
  return Array.isArray(resposta.valor) ? resposta.valor.join(', ') : resposta.valor
}

function tamanho(bytes) {
  if (!bytes) return '—'
  return bytes < 1024 * 1024
    ? `${Math.round(bytes / 1024)} KB`
    : `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

onMounted(carregar)
</script>

<template>
  <div class="tela">
    <header class="tela__cabecalho">
      <h1>Solicitações</h1>
      <AjudaDaTela>
        O que chega pelos formulários próprios, em
        <strong>forms.movisat.com.br</strong>. Cada formulário tem um link, e só
        o owner o põe no ar. A solicitação é um <strong>retrato</strong>: fica
        como a pessoa escreveu, mesmo que o formulário mude depois.
      </AjudaDaTela>
    </header>

    <p v-if="erro" class="aviso aviso--erro" role="alert">{{ erro }}</p>
    <p v-if="recado" class="aviso aviso--ok">{{ recado }}</p>

    <section class="cartao tela__bloco">
      <div class="cartao__corpo">
        <table class="tabela">
          <thead>
            <tr>
              <th>Formulário</th><th>Setor</th><th>Link</th>
              <th>Novas</th><th>Total</th><th>Última</th><th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="f in formularios" :key="f.codigo">
              <td>{{ f.titulo }}</td>
              <td class="apagado">{{ f.setor }}</td>
              <td><code>/f/{{ f.slug }}</code></td>
              <td>{{ f.novas }}</td>
              <td class="apagado">{{ f.solicitacoes }}</td>
              <td class="apagado">{{ quando(f.ultima_em) }}</td>
              <td>
                <span v-if="!souOwner" class="apagado pequeno">
                  {{ f.ativo ? 'no ar' : 'fora do ar' }}
                </span>
                <label v-else class="interruptor">
                  <input type="checkbox" :checked="f.ativo" @change="alternarFormulario(f)" />
                  <span>{{ f.ativo ? 'No ar' : 'Fora do ar' }}</span>
                </label>
              </td>
            </tr>
            <tr v-if="!formularios.length && !carregando">
              <td colspan="7" class="apagado">
                Nenhum formulário carregado ainda.
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <div class="colunas">
      <section class="cartao">
        <div class="cartao__corpo pilha">
          <div class="filtros">
            <select v-model="filtroFormulario" @change="carregar">
              <option value="">Todos os formulários</option>
              <option v-for="f in formularios" :key="f.slug" :value="f.slug">
                {{ f.titulo }}
              </option>
            </select>
            <select v-model="filtroEstado" @change="carregar">
              <option value="">Todos os estados</option>
              <option v-for="e in ESTADOS" :key="e.valor" :value="e.valor">
                {{ e.rotulo }}
              </option>
            </select>
          </div>

          <p v-if="carregando" class="apagado">Lendo…</p>
          <p v-else-if="!solicitacoes.length" class="apagado">
            Nada chegou ainda com esses filtros.
          </p>
          <ul v-else class="lista">
            <li v-for="s in solicitacoes" :key="s.id">
              <button
                class="lista__item"
                :class="{ 'lista__item--aberta': aberta && aberta.id === s.id }"
                @click="abrir(s.id)"
              >
                <span class="lista__topo">
                  <strong>{{ s.titulo }}</strong>
                  <span class="etiqueta" :class="`etiqueta--${s.estado}`">
                    {{ ESTADOS.find((e) => e.valor === s.estado)?.rotulo || s.estado }}
                  </span>
                </span>
                <span class="apagado pequeno">{{ resumo(s) }}</span>
                <span class="apagado pequeno">
                  {{ quando(s.criada_em) }}
                  <template v-if="s.anexos"> · {{ s.anexos }} anexo(s)</template>
                </span>
              </button>
            </li>
          </ul>
        </div>
      </section>

      <section v-if="aberta" class="cartao">
        <div class="cartao__corpo pilha">
          <h2 class="cartao__titulo">{{ aberta.titulo }}</h2>
          <p class="apagado pequeno">
            {{ aberta.setor }} · {{ quando(aberta.criada_em) }}
            <template v-if="aberta.lida_por_nome"> · lida por {{ aberta.lida_por_nome }}</template>
          </p>

          <div class="filtros">
            <button
              v-for="e in ESTADOS"
              :key="e.valor"
              class="botao botao--contorno"
              :class="{ 'botao--ativo': aberta.estado === e.valor }"
              @click="mudarEstado(e.valor)"
            >
              {{ e.rotulo }}
            </button>
          </div>

          <dl class="ficha">
            <template v-for="r in aberta.respostas" :key="r.nome">
              <dt>
                {{ r.rotulo }}
                <span v-if="r.fora_da_definicao" class="apagado pequeno">
                  (campo que saiu do formulário)
                </span>
              </dt>
              <dd>{{ valorLegivel(r) }}</dd>
            </template>
          </dl>

          <div v-if="aberta.anexos && aberta.anexos.length" class="pilha">
            <strong>Anexos</strong>
            <ul class="anexos">
              <li v-for="a in aberta.anexos" :key="a.id">
                <a :href="`/api/solicitacoes/${aberta.id}/arquivo/${a.id}`" target="_blank">
                  {{ a.nome_original }}
                </a>
                <span class="apagado pequeno"> · {{ tamanho(a.bytes) }}</span>
              </li>
            </ul>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.tela__cabecalho { display: flex; align-items: center; gap: var(--e-2); margin-bottom: var(--e-5); }
.tela__cabecalho h1 { margin: 0; font-size: var(--txt-xl); }
.tela__bloco { margin-bottom: var(--e-4); }

/* ⚠️ `.cartao__titulo` e `.interruptor` nao existem no `componentes.css`: sao
   de tela, e os valores sao COPIADOS da CFG_11.1 (Notificacoes.vue), nao
   "parecidos" -- quase a mesma medida le como defeito, nao como escolha. */
.cartao__titulo { display: flex; align-items: center; gap: var(--e-2); margin: 0; font-size: var(--txt-lg); }
.interruptor { display: flex; align-items: center; gap: var(--e-2); cursor: pointer; }
.interruptor input { width: 18px; height: 18px; accent-color: var(--acento); }

.colunas { display: grid; grid-template-columns: minmax(280px, 380px) 1fr; gap: var(--e-4); align-items: start; }
@media (max-width: 860px) { .colunas { grid-template-columns: 1fr; } }

.filtros { display: flex; flex-wrap: wrap; gap: var(--e-2); }
.filtros select {
  min-height: var(--altura-toque);
  padding: var(--e-2);
  border: var(--borda-fina) solid var(--borda);
  border-radius: var(--r-md);
  background: var(--superficie);
  color: var(--texto);
  font-size: var(--txt-campo);
}

.lista { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--e-2); }
.lista__item {
  width: 100%;
  min-height: var(--altura-toque);
  display: flex; flex-direction: column; gap: 2px;
  padding: var(--e-3);
  text-align: left;
  background: var(--superficie);
  border: var(--borda-fina) solid var(--borda);
  border-radius: var(--r-md);
  color: var(--texto);
  cursor: pointer;
}
.lista__item:hover { background: var(--superficie-2); }
.lista__item--aberta { border-color: var(--acento); background: var(--acento-suave); }
.lista__topo { display: flex; align-items: center; justify-content: space-between; gap: var(--e-2); }

.etiqueta { padding: 2px var(--e-2); border-radius: var(--r-full); font-size: var(--txt-xs); border: var(--borda-fina) solid var(--borda); }
.etiqueta--nova { background: var(--acento-suave); border-color: var(--acento-borda); color: var(--acento); }
.etiqueta--em_andamento { background: var(--aviso-suave); border-color: var(--aviso); color: var(--aviso); }
.etiqueta--concluida { background: var(--ok-suave); border-color: var(--ok-borda); color: var(--ok); }

.ficha { display: grid; grid-template-columns: minmax(140px, 240px) 1fr; gap: var(--e-2) var(--e-4); margin: 0; }
.ficha dt { color: var(--texto-fraco); font-size: var(--txt-sm); }
.ficha dd { margin: 0; white-space: pre-wrap; }

.anexos { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--e-1); }
.botao--ativo { border-color: var(--acento); color: var(--acento); }
.tabela code { font-family: var(--fonte-mono); font-size: var(--txt-sm); }
</style>
