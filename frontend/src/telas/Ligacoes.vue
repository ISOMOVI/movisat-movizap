<script setup>
/* ============================================================================
   LIG_1.1 — Ligações.
   ----------------------------------------------------------------------------
   🔵 Pedido dele (15/10): *"um grid simples que tenha as ligações do historico
   do MicroSip, consultadas por cliente - ja da base Movizap, ou por Atendente,
   ou por data ou por numero, etc, exportar e importar e um botão para baixar a
   ligação se quiser ou reproduzir por lá"*.

   🚨 A ABA NÃO PODE MENTIR POR OMISSÃO. Ela mostra só o que os PCs mandaram, e
   quem não tem agente instalado simplesmente não aparece — o que se parece
   com "essa pessoa não ligou". Daí a faixa de cobertura no topo: ela diz
   quantos ramais têm agente, e nomeia quem está de fora.

   ⚠️ O filtro por CLIENTE não é um campo de busca de empresa: buscar empresa
   por nome é `CAD_1.1`, permissão que esta aba não tem. Quando se chega aqui a
   partir da ficha de uma conversa, o `cliente_id` vem na URL e aparece como
   chip removível. Por número, a busca aceita pedaço ("9811").

   🚨 A aba nasceu só do owner e, horas depois, ele disse *"pode exibir a aba
   para todos"*: hoje é permissão `atendimento`. Ou seja, qualquer atendente
   ouve e baixa gravação de qualquer ligação — e exporta. Quem exportou fica
   registrado.

   🚨 O áudio vem por `pedirBlob`, não por `<audio src>`: o token vive no
   cabeçalho, e o navegador não o manda sozinho. Arrastar funciona porque o
   blob está inteiro na memória.
   ============================================================================ */
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute } from 'vue-router'

import { api, pedirBlob, ErroDeApi } from '../api/cliente.js'
import AjudaDaTela from '../componentes/AjudaDaTela.vue'

const route = useRoute()

const dados = ref({ itens: [], total: 0, paginas: 1, por_sentido: {} })
const agentes = ref([])
const carregando = ref(true)
const erro = ref('')
const exportando = ref(false)

const de = ref('')
const ate = ref('')
const atendenteId = ref('')
const sentido = ref('')
const numero = ref('')
const soComGravacao = ref(false)
const clienteId = ref('')
const clienteNome = ref('')
const pagina = ref(1)

/* Um player por vez: dois áudios tocando juntos é confusão, e cada blob
   aberto é memória presa até o revoke. */
const tocando = ref({ id: null, url: '' })

const SENTIDOS = [
  ['feita', 'Feitas'],
  ['recebida', 'Recebidas'],
  ['perdida', 'Perdidas'],
]

/* 🔴 19/10 — o REC na faixa de cobertura (pedido dele).
   🚨 TRÊS estados, não dois. O agente só avisa quando a gravação está
   DESLIGADA; "ligado" é a ausência do aviso na última passada. PC que ainda
   não falou não tem resposta, e a tela diz isso em vez de inventar uma. */
const REC_ROTULO = {
  ligado: 'REC ligado',
  desligado: 'REC desligado',
  desconhecido: 'REC não informado',
}
const REC_CLASSE = {
  ligado: 'chip--ok',
  desligado: 'chip--erro',
  desconhecido: 'chip--aviso',
}
const REC_AJUDA = {
  ligado: 'O PC informou, no último contato, que a gravação automática do '
          + 'MicroSIP está ligada.',
  desligado: 'O PC informou que a gravação automática do MicroSIP está '
             + 'desligada: as ligações sobem, o áudio não.',
  desconhecido: 'Este PC ainda não fez nenhuma passada, então não há o que '
                + 'dizer sobre a gravação dele.',
}

const comAgente = computed(() => agentes.value.filter((a) => a.agente_id))
const semAgente = computed(() => agentes.value.filter((a) => !a.agente_id))

function parametros() {
  const p = new URLSearchParams()
  if (de.value) p.set('de', de.value)
  if (ate.value) p.set('ate', ate.value)
  if (atendenteId.value) p.set('atendente_id', atendenteId.value)
  if (sentido.value) p.set('sentido', sentido.value)
  if (numero.value.trim()) p.set('numero', numero.value.trim())
  if (clienteId.value) p.set('cliente_id', clienteId.value)
  if (soComGravacao.value) p.set('com_gravacao', 'true')
  return p
}

async function carregar() {
  carregando.value = true
  try {
    const p = parametros()
    p.set('pagina', String(pagina.value))
    dados.value = await api.get(`/api/ligacoes?${p.toString()}`)
    erro.value = ''
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Falha ao ler as ligações.'
  } finally {
    carregando.value = false
  }
}

function buscar() {
  pagina.value = 1
  carregar()
}

watch(pagina, carregar)

onMounted(async () => {
  /* Vem da ficha da conversa: ?numero=…&dias=30 */
  if (route.query.numero) numero.value = String(route.query.numero)
  if (route.query.cliente_id) {
    clienteId.value = String(route.query.cliente_id)
    clienteNome.value = String(route.query.cliente || 'cliente')
  }
  if (route.query.dias) {
    const d = new Date()
    d.setDate(d.getDate() - Number(route.query.dias))
    de.value = d.toISOString().slice(0, 10)
  }
  try {
    agentes.value = (await api.get('/api/ligacoes/agentes')).agentes
  } catch {
    /* a faixa de cobertura é informação, não pré-requisito da tela */
    agentes.value = []
  }
  await carregar()
})

onUnmounted(() => soltarPlayer())

function soltarPlayer() {
  if (tocando.value.url) URL.revokeObjectURL(tocando.value.url)
  tocando.value = { id: null, url: '' }
}

async function tocar(g) {
  if (tocando.value.id === g.id) return soltarPlayer()
  soltarPlayer()
  try {
    const blob = await pedirBlob(`/api/ligacoes/gravacao/${g.id}`)
    tocando.value = { id: g.id, url: URL.createObjectURL(blob) }
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui abrir a gravação.'
  }
}

async function baixar(g, l) {
  try {
    const blob = await pedirBlob(`/api/ligacoes/gravacao/${g.id}`)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = g.nome || `ligacao-${l.id}.mp3`
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui baixar a gravação.'
  }
}

async function exportar() {
  exportando.value = true
  try {
    const blob = await pedirBlob(`/api/ligacoes/exportar.csv?${parametros().toString()}`)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `ligacoes-${new Date().toISOString().slice(0, 10)}.csv`
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Falha ao exportar.'
  } finally {
    exportando.value = false
  }
}

function limparCliente() {
  clienteId.value = ''
  clienteNome.value = ''
  buscar()
}

function data(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })
}

function duracao(seg) {
  const s = Number(seg || 0)
  if (!s) return '—'
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

function tamanho(bytes) {
  const mb = Number(bytes || 0) / 1024 / 1024
  return `${mb.toFixed(1)} MB`
}

function quando(iso) {
  if (!iso) return 'nunca falou'
  return new Date(iso).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })
}
</script>

<template>
  <div class="tela">
    <header class="tela__cabecalho">
      <div>
        <h1>Ligações</h1>
        <AjudaDaTela>
          O histórico de ligações do MicroSIP de cada PC, com a gravação quando
          houver. Dá para ouvir aqui, baixar o áudio e exportar o que está
          filtrado. A busca por número aceita pedaço do número.
        </AjudaDaTela>
      </div>
      <div class="linha">
        <span class="chip">{{ dados.total }} ligações</span>
        <span v-for="[valor, rotulo] in SENTIDOS" :key="valor" class="chip">
          {{ rotulo }}: {{ dados.por_sentido[valor] || 0 }}
        </span>
      </div>
    </header>

    <!-- 🚨 A FAIXA QUE IMPEDE A TELA DE MENTIR. Sem ela, quem não tem agente
         parece não ter ligado. -->
    <section class="cartao tela__bloco cobertura">
      <div class="cartao__corpo">
        <p class="pequeno">
          <strong>{{ comAgente.length }}</strong> de
          <strong>{{ agentes.length }}</strong> atendentes com agente instalado.
          Só aparecem aqui as ligações de quem tem.
        </p>
        <ul class="cobertura__lista">
          <li v-for="a in comAgente" :key="a.atendente_id">
            <span class="chip chip--ok">{{ a.nome }}</span>
            <span class="apagado pequeno mono">ramal {{ a.ramal }}</span>
            <span class="apagado pequeno">último contato {{ quando(a.ultimo_contato_em) }}</span>
            <span class="apagado pequeno">{{ a.ligacoes }} ligações</span>
            <!-- 🔴 19/10, pedido dele: o REC de cada PC na própria linha.
                 Sem isto a aba dizia "N ligações" de um PC que não grava
                 nenhuma, e o operador só descobria ao procurar o áudio. -->
            <span :class="['chip', REC_CLASSE[a.rec] || 'chip--aviso']"
                  :title="REC_AJUDA[a.rec]">{{ REC_ROTULO[a.rec] || 'REC ?' }}</span>
          </li>
        </ul>
        <p v-if="semAgente.length" class="apagado pequeno">
          Sem agente:
          {{ semAgente.map((a) => a.nome).join(', ') }}
        </p>
      </div>
    </section>

    <section class="cartao tela__bloco">
      <div class="cartao__corpo linha linha--quebra">
        <label class="campo">
          <span class="campo__rotulo">De</span>
          <input v-model="de" class="campo__entrada" type="date" />
        </label>
        <label class="campo">
          <span class="campo__rotulo">Até</span>
          <input v-model="ate" class="campo__entrada" type="date" />
        </label>
        <label class="campo">
          <span class="campo__rotulo">Atendente</span>
          <select v-model="atendenteId" class="campo__entrada" @change="buscar">
            <option value="">todos</option>
            <option v-for="a in comAgente" :key="a.atendente_id" :value="a.atendente_id">
              {{ a.nome }}
            </option>
          </select>
        </label>
        <label class="campo">
          <span class="campo__rotulo">Sentido</span>
          <select v-model="sentido" class="campo__entrada" @change="buscar">
            <option value="">todos</option>
            <option v-for="[valor, rotulo] in SENTIDOS" :key="valor" :value="valor">
              {{ rotulo }}
            </option>
          </select>
        </label>
        <label class="campo campo--numero">
          <span class="campo__rotulo">Número</span>
          <input
            v-model="numero"
            class="campo__entrada"
            type="search"
            placeholder="inteiro ou pedaço"
            @keyup.enter="buscar"
          />
        </label>
        <label class="campo campo--caixa">
          <input v-model="soComGravacao" type="checkbox" @change="buscar" />
          <span class="campo__rotulo">só com gravação</span>
        </label>

        <button class="botao botao--primario" type="button" @click="buscar">
          <i class="bi bi-search" aria-hidden="true"></i> Buscar
        </button>
        <button
          class="botao botao--contorno"
          type="button"
          :disabled="exportando || !dados.total"
          @click="exportar"
        >
          <i class="bi bi-filetype-csv" aria-hidden="true"></i>
          {{ exportando ? 'exportando…' : 'Exportar CSV' }}
        </button>
      </div>
      <div v-if="clienteId" class="cartao__corpo linha">
        <span class="chip chip--acento">cliente: {{ clienteNome }}</span>
        <button class="botao botao--pequeno botao--contorno" type="button" @click="limparCliente">
          tirar filtro
        </button>
      </div>
    </section>

    <p v-if="erro" class="aviso aviso--erro" role="alert">
      <i class="bi bi-exclamation-octagon aviso__icone" aria-hidden="true"></i>
      <span>{{ erro }}</span>
    </p>

    <p v-if="carregando" class="linha fraco">
      <span class="girando"></span> Lendo…
    </p>

    <div v-else-if="!dados.itens.length" class="vazio">
      <i class="bi bi-telephone vazio__icone" aria-hidden="true"></i>
      <p class="vazio__titulo">Nenhuma ligação neste filtro</p>
      <p>
        Lembre que só aparecem ligações de PCs com o agente instalado
        ({{ comAgente.length }} de {{ agentes.length }}).
      </p>
    </div>

    <section v-else class="cartao tela__bloco">
      <div class="tabela--rolavel">
        <table class="tabela">
          <thead>
            <tr>
              <th>Quando</th>
              <th>Sentido</th>
              <th>Número</th>
              <th>Cliente</th>
              <th>Atendente</th>
              <th>Duração</th>
              <th>Gravação</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="l in dados.itens" :key="l.id">
              <td class="pequeno fraco">{{ data(l.inicio) }}</td>
              <td>
                <span class="chip">{{ l.sentido }}</span>
                <p v-if="l.situacao" class="apagado pequeno">{{ l.situacao }}</p>
              </td>
              <td class="mono pequeno">{{ l.telefone_e164 || l.numero_bruto }}</td>
              <td>
                <template v-if="l.clientes.length">
                  <strong class="pequeno">{{ l.clientes[0].nome }}</strong>
                  <p class="apagado pequeno">{{ l.clientes[0].contato_nome }}</p>
                  <!-- 🚨 Um número pode estar em várias empresas: dizer "+N"
                       é melhor que escolher uma e calar as outras. -->
                  <span v-if="l.clientes.length > 1" class="chip">
                    +{{ l.clientes.length - 1 }}
                  </span>
                </template>
                <span v-else class="apagado pequeno">sem cadastro</span>
              </td>
              <td class="pequeno fraco">
                {{ l.atendente || '—' }}
                <p class="apagado pequeno mono">ramal {{ l.ramal }}</p>
              </td>
              <td class="mono pequeno">{{ duracao(l.duracao_s) }}</td>
              <td>
                <span v-if="!l.gravacoes.length" class="apagado pequeno">sem gravação</span>
                <div v-for="g in l.gravacoes" :key="g.id" class="gravacao">
                  <button
                    class="botao botao--pequeno botao--contorno"
                    type="button"
                    @click="tocar(g)"
                  >
                    <i
                      class="bi"
                      :class="tocando.id === g.id ? 'bi-stop-fill' : 'bi-play-fill'"
                      aria-hidden="true"
                    ></i>
                    {{ tocando.id === g.id ? 'parar' : 'ouvir' }}
                  </button>
                  <button
                    class="botao botao--pequeno botao--contorno"
                    type="button"
                    @click="baixar(g, l)"
                  >
                    <i class="bi bi-download" aria-hidden="true"></i>
                  </button>
                  <span class="apagado pequeno">{{ tamanho(g.bytes) }}</span>
                  <audio v-if="tocando.id === g.id" :src="tocando.url" controls autoplay></audio>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <nav v-if="dados.paginas > 1" class="linha lig__paginacao">
        <button
          class="botao botao--contorno botao--pequeno"
          :disabled="pagina <= 1"
          @click="pagina -= 1"
        >
          anterior
        </button>
        <span class="pequeno fraco">{{ pagina }} / {{ dados.paginas }}</span>
        <button
          class="botao botao--contorno botao--pequeno"
          :disabled="pagina >= dados.paginas"
          @click="pagina += 1"
        >
          próxima
        </button>
      </nav>
    </section>
  </div>
</template>

<style scoped>
.tela { max-width: 1240px; }

.tela__cabecalho {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--e-4);
  flex-wrap: wrap;
  margin-bottom: var(--e-5);
}
.tela__cabecalho p { max-width: var(--largura-texto); margin-top: var(--e-1); }

.tela__bloco { margin-bottom: var(--e-4); overflow: hidden; }

.linha--quebra { flex-wrap: wrap; gap: var(--e-3); align-items: flex-end; }
.campo--numero { min-width: 200px; }
.campo--caixa { flex-direction: row; align-items: center; gap: var(--e-2); }

.cobertura__lista {
  list-style: none;
  padding: 0;
  margin: var(--e-2) 0 0;
  display: flex;
  flex-direction: column;
  gap: var(--e-1);
}
.cobertura__lista li { display: flex; gap: var(--e-2); flex-wrap: wrap; align-items: center; }

.gravacao { display: flex; gap: var(--e-2); align-items: center; flex-wrap: wrap; }
/* O player nasce em largura de conteúdo: o padrão do navegador estica a
   coluna e empurra o resto do grid para fora da tela. */
.gravacao audio { max-width: 220px; height: 32px; }

.lig__paginacao { justify-content: center; gap: var(--e-3); padding: var(--e-3); }
</style>
