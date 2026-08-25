<script setup>
/* ============================================================================
   CAD_2.2 — Times.
   ----------------------------------------------------------------------------
   Os 7 vieram do Chatwoot, que é a estrutura em uso. Daqui em diante o
   cadastro é aqui: o Chatwoot foi ponto de partida, não fonte permanente.

   🚨 A DESCRIÇÃO DO TIME É ENTRADA DA IA, não enfeite. É por ela que a camada
   5 do prompt (CFG_2.1) escolhe para onde transferir. Time sem descrição faz
   a IA chutar — por isso a tela cobra, em vez de deixar em branco calado.

   🚨 TIME SEM NENHUM MEMBRO aparece em vermelho. Três dos sete estão assim, e
   conversa transferida para eles hoje não chega a ninguém — sem erro, sem
   log, sem ninguém saber.
   ============================================================================ */
import { ref, computed, onMounted } from 'vue'

import { api, ErroDeApi } from '../api/cliente.js'
import { corDaInicial, iniciais } from '../util/avatar.js'

const times = ref([])
const alertas = ref([])
const carregando = ref(true)
const erro = ref('')
const salvando = ref(false)
const incluirInativos = ref(false)

/** null = nada aberto; {} = criando; {id...} = editando */
/* O transbordo do transbordo: dois elos bastam para mostrar a direção sem
   virar diagrama, e é onde a conversa costuma se perder. */
function transbordoDe(id) {
  const alvo = times.value.find((t) => t.id === id)
  return alvo?.transbordo_nome || null
}

const editando = ref(null)

const form = ref({ nome: '', descricao: '', time_transbordo_id: null, ativo: true })

const outrosTimes = computed(() =>
  times.value.filter((t) => !editando.value?.id || t.id !== editando.value.id),
)

async function carregar() {
  carregando.value = true
  erro.value = ''
  try {
    const [lista, avisos] = await Promise.all([
      api.get(`/api/times?incluir_inativos=${incluirInativos.value}`),
      api.get('/api/operacao/alertas'),
    ])
    times.value = lista
    alertas.value = avisos
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Falha ao ler os times.'
  } finally {
    carregando.value = false
  }
}

onMounted(carregar)

function abrirNovo() {
  editando.value = {}
  form.value = { nome: '', descricao: '', time_transbordo_id: null, ativo: true }
  erro.value = ''
}

function abrirEdicao(time) {
  editando.value = time
  form.value = {
    nome: time.nome,
    descricao: time.descricao || '',
    time_transbordo_id: time.time_transbordo_id,
    ativo: time.ativo,
  }
  erro.value = ''
}

function fechar() {
  editando.value = null
  erro.value = ''
}

async function salvar() {
  salvando.value = true
  erro.value = ''
  const corpo = {
    nome: form.value.nome,
    descricao: form.value.descricao || null,
    time_transbordo_id: form.value.time_transbordo_id || null,
    ativo: form.value.ativo,
  }
  try {
    if (editando.value?.id) await api.put(`/api/times/${editando.value.id}`, corpo)
    else await api.post('/api/times', corpo)
    fechar()
    await carregar()
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui salvar.'
  } finally {
    salvando.value = false
  }
}
</script>

<template>
  <div class="tela">
    <header class="tela__cabecalho">
      <div>
        <h1>Times</h1>
        <p class="fraco pequeno">
          Quem recebe transferência. A descrição não é enfeite: é o texto que a
          IA lê para escolher o destino.
        </p>
      </div>
      <div class="linha">
        <label class="linha pequeno fraco">
          <input v-model="incluirInativos" type="checkbox" @change="carregar" />
          mostrar inativos
        </label>
        <button class="botao botao--primario" type="button" @click="abrirNovo">
          <i class="bi bi-plus-lg" aria-hidden="true"></i> Novo time
        </button>
      </div>
    </header>

    <p v-if="alertas.length === 0 && !carregando" class="so-leitor">Sem alertas.</p>
    <p
      v-for="alerta in alertas"
      :key="alerta.titulo"
      class="aviso"
      :class="alerta.grave ? 'aviso--erro' : 'aviso--atencao'"
      role="status"
    >
      <i class="bi bi-exclamation-triangle aviso__icone" aria-hidden="true"></i>
      <span>
        <strong>{{ alerta.titulo }}:</strong> {{ alerta.detalhe }}.
        <span class="fraco">{{ alerta.porque }}</span>
      </span>
    </p>

    <p v-if="erro && !editando" class="aviso aviso--erro" role="alert">
      <i class="bi bi-exclamation-octagon aviso__icone" aria-hidden="true"></i>
      <span>{{ erro }}</span>
    </p>

    <section v-if="editando" class="cartao tela__bloco">
      <header class="cartao__cabecalho">
        <span>{{ editando.id ? `Editando ${editando.nome}` : 'Novo time' }}</span>
      </header>
      <div class="cartao__corpo pilha">
        <label class="campo">
          <span class="campo__rotulo">Nome</span>
          <input v-model="form.nome" class="campo__entrada" maxlength="200" />
        </label>

        <label class="campo">
          <span class="campo__rotulo">Descrição — a IA lê isto</span>
          <textarea
            v-model="form.descricao"
            class="campo__entrada"
            rows="3"
            maxlength="1000"
            placeholder="Ex.: Boleto, fatura, segunda via, negociação de débito."
          ></textarea>
          <span class="campo__ajuda">
            É por aqui que a IA decide mandar a conversa para cá. Sem descrição,
            ela chuta.
          </span>
        </label>

        <label class="campo">
          <span class="campo__rotulo">Transbordo</span>
          <select v-model="form.time_transbordo_id" class="campo__entrada">
            <option :value="null">— fica na fila do próprio time —</option>
            <option v-for="t in outrosTimes" :key="t.id" :value="t.id">{{ t.nome }}</option>
          </select>
          <span class="campo__ajuda">
            Para onde a conversa vai quando este time não atende. Ciclo entre
            times é recusado no servidor.
          </span>
        </label>

        <label v-if="editando.id" class="linha">
          <input v-model="form.ativo" type="checkbox" />
          <span>Ativo</span>
        </label>

        <p v-if="erro" class="aviso aviso--erro" role="alert">
          <i class="bi bi-exclamation-octagon aviso__icone" aria-hidden="true"></i>
          <span>{{ erro }}</span>
        </p>

        <div class="linha">
          <button class="botao botao--primario" type="button" :disabled="salvando" @click="salvar">
            <span v-if="salvando" class="girando"></span>
            {{ salvando ? 'Salvando…' : 'Salvar' }}
          </button>
          <button class="botao botao--fantasma" type="button" @click="fechar">Cancelar</button>
        </div>
      </div>
    </section>

    <p v-if="carregando" class="linha fraco">
      <span class="girando"></span> Lendo os times…
    </p>

    <div v-else-if="!times.length" class="vazio">
      <i class="bi bi-diagram-2 vazio__icone" aria-hidden="true"></i>
      <p class="vazio__titulo">Nenhum time</p>
      <p>Os 7 do Chatwoot deviam estar aqui — confira a importação.</p>
    </div>

    <!-- 🚨 CARTÕES, NÃO TABELA. Numa tabela, nome, descrição, membros,
         transbordo e situação recebem o mesmo peso -- e a descrição, que é a
         ENTRADA DA IA, virava texto miúdo numa célula. No cartão ela tem
         lugar próprio, e a cadeia de transbordo pode ser desenhada. -->
    <section v-else class="times">
      <article
        v-for="t in times"
        :key="t.id"
        class="cartao time"
        :class="{ 'time--inativo': !t.ativo, 'time--vazio': !t.qtd_membros }"
      >
        <header class="time__topo">
          <div>
            <strong class="time__nome">{{ t.nome }}</strong>
            <span v-if="!t.ativo" class="chip chip--pequeno">inativo</span>
          </div>
          <!-- Quantas esperam AGORA: é o número que diz se o time dá conta. -->
          <span class="time__fila" :class="{ 'time__fila--pede': t.na_fila }">
            <strong>{{ t.na_fila }}</strong>
            <span class="apagado pequeno">na fila</span>
          </span>
        </header>

        <p v-if="t.descricao" class="time__descricao">{{ t.descricao }}</p>
        <p v-else class="chip chip--aviso">
          sem descrição — a IA vai chutar o destino
        </p>

        <div class="time__membros">
          <template v-if="t.qtd_membros">
            <!-- Avatar em vez de chip com nome: cinco chips de nome ocupam a
                 largura toda e nenhum deles é lido. -->
            <span
              v-for="m in t.membros"
              :key="m.id"
              class="time__avatar"
              :style="{ background: corDaInicial(m.nome) }"
              :title="m.nome + (m.transferivel ? '' : ' — não recebe transferência')"
            >{{ iniciais(m.nome) }}</span>
            <span class="apagado pequeno">{{ t.qtd_membros }} recebem transferência</span>
          </template>
          <span v-else class="chip chip--erro">ninguém dentro — a conversa não chega</span>
        </div>

        <!-- ⚠️ A CADEIA DESENHADA, não uma célula com um nome. Quem lê "vai
             para o Geral" não sabe para onde o Geral manda, e é aí que a
             conversa se perde. -->
        <p class="time__cadeia pequeno">
          <span class="time__elo">{{ t.nome }}</span>
          <template v-if="t.transbordo_nome">
            <i class="bi bi-arrow-right" aria-hidden="true"></i>
            <span class="time__elo">{{ t.transbordo_nome }}</span>
            <i v-if="transbordoDe(t.time_transbordo_id)" class="bi bi-arrow-right"
               aria-hidden="true"></i>
            <span v-if="transbordoDe(t.time_transbordo_id)" class="time__elo">
              {{ transbordoDe(t.time_transbordo_id) }}
            </span>
          </template>
          <span v-else class="apagado">fica na fila do próprio time</span>
        </p>

        <!-- 🚨 LISTA VAZIA AQUI SIGNIFICA O CONTRÁRIO DO QUE PARECE: sem linha
             de permissão, TODO MUNDO vê a fila deste time. É o padrão
             permissivo da migração 001, e ele não aparecia em tela nenhuma. -->
        <p class="time__quemve pequeno apagado">
          <i class="bi bi-eye" aria-hidden="true"></i>
          <template v-if="t.quem_ve.length">
            só {{ t.quem_ve.join(', ') }} veem esta fila
          </template>
          <template v-else>todos veem esta fila</template>
        </p>

        <div class="time__acoes">
          <button class="botao botao--pequeno botao--contorno" type="button"
                  @click="abrirEdicao(t)">
            Editar
          </button>
        </div>
      </article>
    </section>

    <p class="apagado pequeno">
      Time não é apagado, é desativado: <code>conversa</code> e
      <code>transferencia</code> apontam para ele, e sumir com a linha faria o
      histórico mentir sobre o que aconteceu.
    </p>
  </div>
</template>

<style scoped>
.times {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: var(--e-3);
}
.time { padding: var(--e-4); display: flex; flex-direction: column; gap: var(--e-2); }
.time--inativo { opacity: .6; }
/* Time sem ninguém dentro aceita a transferência e a conversa não chega:
   é o único estado que muda a borda do cartão. */
.time--vazio { border-color: var(--erro-borda); }
.time__topo { display: flex; justify-content: space-between; align-items: flex-start; gap: var(--e-2); }
.time__nome { font-size: var(--txt-lg); }
.time__fila { display: flex; flex-direction: column; align-items: flex-end; line-height: 1.1; }
.time__fila strong { font-size: var(--txt-xl); color: var(--texto-fraco); }
.time__fila--pede strong { color: var(--aviso); }
.time__descricao { margin: 0; color: var(--texto-fraco); font-size: var(--txt-sm); }
.time__membros { display: flex; align-items: center; gap: var(--e-1); flex-wrap: wrap; }
.time__avatar {
  width: 28px; height: 28px;
  border-radius: var(--r-full);
  display: inline-flex; align-items: center; justify-content: center;
  color: #fff; font-size: var(--txt-xs); font-weight: var(--peso-forte);
}
.time__cadeia { display: flex; align-items: center; gap: var(--e-1); flex-wrap: wrap; }
.time__elo {
  padding: 2px var(--e-2);
  background: var(--superficie-2);
  border-radius: var(--r-full);
}
.time__quemve { display: flex; align-items: center; gap: var(--e-1); }
.time__acoes { margin-top: auto; }

.tela { max-width: 1100px; }

.tela__cabecalho {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--e-4);
  flex-wrap: wrap;
  margin-bottom: var(--e-5);
}
.tela__cabecalho p { max-width: var(--largura-texto); margin-top: var(--e-1); }

.tela__bloco { margin-bottom: var(--e-5); overflow: hidden; }

.linha--inativa td { opacity: .6; }

textarea.campo__entrada { resize: vertical; min-height: 4.5rem; }
</style>
