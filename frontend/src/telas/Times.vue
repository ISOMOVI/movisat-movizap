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

const times = ref([])
const alertas = ref([])
const carregando = ref(true)
const erro = ref('')
const salvando = ref(false)
const incluirInativos = ref(false)

/** null = nada aberto; {} = criando; {id...} = editando */
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

    <section v-else class="cartao tela__bloco">
      <div class="tabela--rolavel">
        <table class="tabela">
          <thead>
            <tr>
              <th>Time</th>
              <th>Membros</th>
              <th>Transbordo</th>
              <th>Situação</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="t in times" :key="t.id" :class="{ 'linha--inativa': !t.ativo }">
              <td>
                <strong>{{ t.nome }}</strong>
                <p v-if="t.descricao" class="apagado pequeno">{{ t.descricao }}</p>
                <p v-else class="pequeno">
                  <span class="chip chip--aviso">sem descrição — a IA vai chutar</span>
                </p>
              </td>
              <td>
                <span v-if="!t.qtd_membros" class="chip chip--erro">
                  ninguém — a conversa não chega
                </span>
                <span v-for="m in t.membros" v-else :key="m.id" class="chip">{{ m.nome }}</span>
              </td>
              <td class="pequeno fraco">{{ t.transbordo_nome || '—' }}</td>
              <td>
                <span v-if="t.ativo" class="chip chip--ok">ativo</span>
                <span v-else class="chip">inativo</span>
              </td>
              <td>
                <button class="botao botao--pequeno botao--contorno" type="button" @click="abrirEdicao(t)">
                  Editar
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <p class="apagado pequeno">
      Time não é apagado, é desativado: <code>conversa</code> e
      <code>transferencia</code> apontam para ele, e sumir com a linha faria o
      histórico mentir sobre o que aconteceu.
    </p>
  </div>
</template>

<style scoped>
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
