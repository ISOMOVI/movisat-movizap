<script setup>
/* ============================================================================
   CAD_2.2 — Times.
   ----------------------------------------------------------------------------
   Os 7 vieram do Chatwoot, que era a estrutura em uso. Daqui em diante o
   cadastro é aqui: o Chatwoot foi ponto de partida, não fonte permanente.

   🚨 A DESCRIÇÃO DO TIME É ENTRADA DA IA, não enfeite. É por ela que a camada
   5 do prompt (CFG_2.1) escolhe para onde transferir. Time sem descrição faz
   a IA chutar — por isso a tela cobra, em vez de deixar em branco calado.

   🚨 TIME SEM NINGUÉM QUE RECEBA aparece em vermelho: conversa transferida
   para ele não chega a ninguém — sem erro, sem log, sem ninguém saber.
   (Em 25/08 os 7 tinham de 2 a 4 membros; o alerta existe porque a situação
   pode voltar.)

   🔵 QUEM ESTÁ NO TIME SE DECIDE AQUI DESDE 24/09, decisão dele: *"vamos
   deixar a tela de times vincular os atendentes"*. A CAD_2.1 passou a só
   mostrar. A lista é dos ATIVOS: o backend só troca o vínculo deles, e um
   inativo que não aparece não perde nada por isso.

   🟡 A edição abre no mesmo modal da CAD_2.1 (ModalEdicao), que pergunta
   antes de descartar — repaginada de 24/09.
   ============================================================================ */
import { ref, computed, onMounted } from 'vue'

import { api, ErroDeApi } from '../api/cliente.js'
import { corDaInicial, iniciais } from '../util/avatar.js'
import AjudaDaTela from '../componentes/AjudaDaTela.vue'
import ModalEdicao from '../componentes/ModalEdicao.vue'

const times = ref([])
const atendentes = ref([])
const alertas = ref([])
const carregando = ref(true)
const erro = ref('')
const recado = ref('')
const incluirInativos = ref(false)

async function carregar() {
  carregando.value = true
  erro.value = ''
  try {
    const [lista, avisos, equipe] = await Promise.all([
      api.get(`/api/times?incluir_inativos=${incluirInativos.value}`),
      api.get('/api/operacao/alertas'),
      api.get('/api/atendentes'),
    ])
    times.value = lista
    alertas.value = avisos
    atendentes.value = equipe
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Falha ao ler os times.'
  } finally {
    carregando.value = false
  }
}

onMounted(carregar)

/* O transbordo do transbordo: dois elos bastam para mostrar a direção sem
   virar diagrama, e é onde a conversa costuma se perder. */
function transbordoDe(id) {
  return times.value.find((t) => t.id === id)?.transbordo_nome || null
}

const naFilaTotal = computed(() => times.value.reduce((s, t) => s + (t.na_fila || 0), 0))

/* ---- o modal de edição --------------------------------------------------- */
const editando = ref(null)
const form = ref(vazio())
const membrosMarcados = ref([])
const erroModal = ref('')
const salvando = ref(false)
let retrato = ''

function vazio() {
  return { nome: '', descricao: '', time_transbordo_id: null, ativo: true }
}

function estadoAtual() {
  return JSON.stringify({ form: form.value, membros: [...membrosMarcados.value].sort() })
}
const sujo = computed(() => editando.value !== null && estadoAtual() !== retrato)

const outrosTimes = computed(() =>
  times.value.filter((t) => !editando.value?.id || t.id !== editando.value.id),
)

function abrir(time) {
  editando.value = time
  form.value = time.id
    ? {
        nome: time.nome,
        descricao: time.descricao || '',
        time_transbordo_id: time.time_transbordo_id,
        ativo: time.ativo,
      }
    : vazio()
  membrosMarcados.value = (time.membros || []).map((m) => m.id)
  erroModal.value = ''
  recado.value = ''
  retrato = estadoAtual()
}

function fechar() {
  editando.value = null
  erroModal.value = ''
}

async function salvar() {
  salvando.value = true
  erroModal.value = ''
  const corpo = {
    nome: form.value.nome,
    descricao: form.value.descricao || null,
    time_transbordo_id: form.value.time_transbordo_id || null,
    ativo: form.value.ativo,
  }
  try {
    const salvo = editando.value.id
      ? await api.put(`/api/times/${editando.value.id}`, corpo)
      : await api.post('/api/times', corpo)
    await api.put(`/api/times/${salvo.id}/membros`, { atendentes: membrosMarcados.value })
    recado.value = editando.value.id ? `${salvo.nome}: alterações salvas.` : `Time ${salvo.nome} criado.`
    fechar()
    await carregar()
  } catch (e) {
    erroModal.value = e instanceof ErroDeApi ? e.message : 'Não consegui salvar.'
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
        <AjudaDaTela>Quem recebe transferência, e quem está em cada time. A descrição não é enfeite: é o texto que a IA lê para escolher o destino.</AjudaDaTela>
      </div>
      <div class="cabecalho__acoes">
        <label class="linha pequeno fraco">
          <input v-model="incluirInativos" type="checkbox" @change="carregar" />
          mostrar inativos
        </label>
        <button class="botao botao--primario" type="button" @click="abrir({})">
          <i class="bi bi-plus-lg" aria-hidden="true"></i> Novo time
        </button>
      </div>
    </header>

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

    <p v-if="recado" class="aviso aviso--ok" role="status">
      <i class="bi bi-check2-circle aviso__icone" aria-hidden="true"></i>
      <span>{{ recado }}</span>
    </p>

    <p v-if="erro" class="aviso aviso--erro" role="alert">
      <i class="bi bi-exclamation-octagon aviso__icone" aria-hidden="true"></i>
      <span>{{ erro }}</span>
    </p>

    <p v-if="carregando" class="linha fraco">
      <span class="girando"></span> Lendo os times…
    </p>

    <div v-else-if="!times.length" class="vazio">
      <i class="bi bi-diagram-2 vazio__icone" aria-hidden="true"></i>
      <p class="vazio__titulo">Nenhum time</p>
      <p>Crie o primeiro em "Novo time".</p>
    </div>

    <template v-else>
      <p class="contagem pequeno apagado">
        {{ times.length }} time(s) · <strong>{{ naFilaTotal }}</strong> conversa(s) esperando agora
      </p>

      <!-- 🚨 CARTÕES, NÃO TABELA. Numa tabela, nome, descrição, membros,
           transbordo e situação recebem o mesmo peso -- e a descrição, que é
           a ENTRADA DA IA, virava texto miúdo numa célula. -->
      <section class="times">
        <article
          v-for="t in times"
          :key="t.id"
          class="cartao time"
          :class="{ 'time--inativo': !t.ativo, 'time--vazio': !t.qtd_membros }"
        >
          <header class="time__topo">
            <div class="time__titulo">
              <strong class="time__nome">{{ t.nome }}</strong>
              <span v-if="!t.ativo" class="chip chip--pequeno">inativo</span>
            </div>
            <!-- Quantas esperam AGORA: é o número que diz se o time dá conta. -->
            <span class="time__fila" :class="{ 'time__fila--pede': t.na_fila }"
                  :title="`${t.na_fila} conversa(s) esperando neste time`">
              <strong>{{ t.na_fila }}</strong>
              <span>na fila</span>
            </span>
          </header>

          <div class="time__corpo">
            <p v-if="t.descricao" class="time__descricao">{{ t.descricao }}</p>
            <p v-else class="chip chip--aviso">
              <i class="bi bi-robot" aria-hidden="true"></i>
              sem descrição — a IA vai chutar o destino
            </p>

            <div class="time__membros">
              <template v-if="t.membros.length">
                <!-- Avatares sobrepostos: o nome aparece ao passar o mouse, e
                     a contagem diz quantos RECEBEM (o owner não recebe). -->
                <div class="empilhados">
                  <span
                    v-for="m in t.membros"
                    :key="m.id"
                    class="avatar"
                    :class="{ 'avatar--fora': !m.transferivel }"
                    :style="{ background: corDaInicial(m.nome) }"
                    :title="m.nome + (m.transferivel ? '' : ' — não recebe transferência')"
                  >{{ iniciais(m.nome) }}</span>
                </div>
                <span class="pequeno fraco">
                  <strong>{{ t.qtd_membros }}</strong> recebe(m) transferência
                </span>
              </template>
              <span v-if="!t.qtd_membros" class="chip chip--erro">
                <i class="bi bi-exclamation-octagon" aria-hidden="true"></i>
                ninguém recebe — a conversa não chega
              </span>
            </div>
          </div>

          <footer class="time__rodape">
            <!-- ⚠️ A CADEIA DESENHADA, não uma célula com um nome. Quem lê "vai
                 para o Geral" não sabe para onde o Geral manda. -->
            <p class="time__cadeia pequeno">
              <i class="bi bi-signpost-split apagado" aria-hidden="true"></i>
              <template v-if="t.transbordo_nome">
                <span class="time__elo">{{ t.transbordo_nome }}</span>
                <template v-if="transbordoDe(t.time_transbordo_id)">
                  <i class="bi bi-arrow-right apagado" aria-hidden="true"></i>
                  <span class="time__elo">{{ transbordoDe(t.time_transbordo_id) }}</span>
                </template>
              </template>
              <span v-else class="apagado">sem transbordo</span>
            </p>
            <!-- 🚨 LISTA VAZIA AQUI SIGNIFICA O CONTRÁRIO DO QUE PARECE: sem
                 linha de permissão, TODO MUNDO vê a fila deste time. -->
            <p class="time__quemve pequeno apagado">
              <i class="bi bi-eye" aria-hidden="true"></i>
              <template v-if="t.quem_ve.length">só {{ t.quem_ve.join(', ') }} veem esta fila</template>
              <template v-else>todos veem esta fila</template>
            </p>
            <button class="botao botao--pequeno botao--contorno time__editar" type="button"
                    @click="abrir(t)">
              <i class="bi bi-pencil" aria-hidden="true"></i> Editar
            </button>
          </footer>
        </article>
      </section>
    </template>

    <!-- ---------------------------------------------------------- edição -->
    <ModalEdicao
      v-if="editando"
      :titulo="editando.id ? editando.nome : 'Novo time'"
      :subtitulo="editando.id ? `${editando.na_fila} conversa(s) na fila agora` : 'Recebe transferência de quem atende e da IA'"
      :sujo="sujo"
      :salvando="salvando"
      @salvar="salvar"
      @fechar="fechar"
    >
      <template #icone>
        <span class="modal-icone" aria-hidden="true"><i class="bi bi-diagram-2"></i></span>
      </template>

      <section class="secao">
        <h2 class="secao__titulo">O time</h2>
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
          <span class="campo__ajuda">A IA usa isto para escolher o time.</span>
        </label>

        <div class="grade">
          <label class="campo">
            <span class="campo__rotulo">Transbordo</span>
            <select v-model="form.time_transbordo_id" class="campo__entrada">
              <option :value="null">— fica na fila do próprio time —</option>
              <option v-for="t in outrosTimes" :key="t.id" :value="t.id">{{ t.nome }}</option>
            </select>
            <span class="campo__ajuda">Para onde a conversa vai quando este time não atende.</span>
          </label>

          <label v-if="editando.id" class="campo interruptor">
            <span class="campo__rotulo">Situação</span>
            <span class="linha">
              <input v-model="form.ativo" type="checkbox" />
              <span>{{ form.ativo ? 'Ativo' : 'Inativo' }}</span>
            </span>
            <span class="campo__ajuda">Inativo sai do "Transferir".</span>
          </label>
        </div>
      </section>

      <section class="secao">
        <h2 class="secao__titulo">
          Atendentes neste time
          <span class="secao__contagem">{{ membrosMarcados.length }} de {{ atendentes.length }}</span>
        </h2>
        <div class="membros">
          <label v-for="a in atendentes" :key="a.id" class="membro"
                 :class="{ 'membro--marcado': membrosMarcados.includes(a.id) }">
            <input v-model="membrosMarcados" type="checkbox" :value="a.id" />
            <span class="avatar avatar--pequeno" :style="{ background: corDaInicial(a.nome) }" aria-hidden="true">
              {{ iniciais(a.nome) }}
            </span>
            <span class="membro__nome">{{ a.nome }}</span>
          </label>
        </div>
        <p class="campo__ajuda">Quem está marcado recebe as conversas transferidas para este time.</p>
      </section>

      <p v-if="erroModal" class="aviso aviso--erro" role="alert">
        <i class="bi bi-exclamation-octagon aviso__icone" aria-hidden="true"></i>
        <span>{{ erroModal }}</span>
      </p>
    </ModalEdicao>
  </div>
</template>

<style scoped>
.tela { max-width: 1180px; }

.tela__cabecalho {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--e-4);
  flex-wrap: wrap;
  margin-bottom: var(--e-5);
}
.tela__cabecalho p { max-width: var(--largura-texto); margin-top: var(--e-1); }
.cabecalho__acoes { display: flex; align-items: center; gap: var(--e-3); flex-wrap: wrap; }

.aviso { margin-bottom: var(--e-4); }
.contagem { margin: 0 0 var(--e-3); }

/* ---- cartões ---- */
.times {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(100%, 320px), 1fr));
  gap: var(--e-4);
}
.time {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transition: box-shadow var(--tempo) var(--curva), border-color var(--tempo) var(--curva);
}
.time:hover { box-shadow: var(--sombra-2); border-color: var(--borda-forte); }
.time--inativo { opacity: .6; }
/* Time sem ninguém que receba: único estado que muda a borda do cartão. */
.time--vazio { border-color: var(--erro-borda); }
.time--vazio .time__topo { background: var(--erro-suave); }

.time__topo {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--e-3);
  padding: var(--e-3) var(--e-4);
  background: var(--superficie-2);
  border-bottom: var(--borda-fina) solid var(--borda);
}
.time__titulo { display: flex; align-items: center; gap: var(--e-2); min-width: 0; }
.time__nome { font-size: var(--txt-lg); color: var(--texto); overflow-wrap: anywhere; }

.time__fila {
  flex: none;
  display: inline-flex;
  align-items: baseline;
  gap: 4px;
  padding: 2px var(--e-3);
  border: var(--borda-fina) solid var(--borda);
  border-radius: var(--r-full);
  background: var(--superficie);
  font-size: var(--txt-xs);
  color: var(--texto-apagado);
}
.time__fila strong { font-size: var(--txt-md); color: var(--texto-fraco); font-variant-numeric: tabular-nums; }
.time__fila--pede { border-color: var(--aviso-borda); background: var(--aviso-suave); }
.time__fila--pede strong { color: var(--aviso); }

.time__corpo { display: flex; flex-direction: column; gap: var(--e-3); padding: var(--e-4); flex: 1; }
.time__descricao { margin: 0; color: var(--texto-fraco); font-size: var(--txt-sm); line-height: var(--entrelinha); }

.time__membros { display: flex; align-items: center; gap: var(--e-3); flex-wrap: wrap; }
/* Lado a lado, sem sobrepor: sobrepostos, cada avatar cobria a inicial do
   anterior (visto na prévia de 24/09). */
.empilhados { display: flex; flex-wrap: wrap; gap: 3px; }

.avatar {
  flex: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border-radius: var(--r-full);
  color: #fff;
  font-size: var(--txt-xs);
  font-weight: var(--peso-forte);
  box-shadow: 0 0 0 2px var(--superficie);
}
.avatar--fora { opacity: .45; }
.avatar--pequeno { width: 26px; height: 26px; box-shadow: none; }

.time__rodape {
  display: flex;
  flex-direction: column;
  gap: var(--e-2);
  padding: var(--e-3) var(--e-4);
  border-top: var(--borda-fina) solid var(--borda);
}
.time__cadeia, .time__quemve { display: flex; align-items: center; gap: var(--e-1); flex-wrap: wrap; margin: 0; }
.time__elo {
  padding: 1px var(--e-2);
  border: var(--borda-fina) solid var(--borda);
  border-radius: var(--r-full);
  background: var(--superficie-2);
  color: var(--texto-fraco);
}
.time__editar { align-self: flex-start; margin-top: var(--e-1); }

/* ---- modal ---- */
.modal-icone {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  border-radius: var(--r-md);
  background: var(--acento-suave);
  color: var(--acento);
  font-size: var(--txt-xl);
}
.secao { padding-bottom: var(--e-5); margin-bottom: var(--e-5); border-bottom: var(--borda-fina) solid var(--borda); }
.secao:last-of-type { border-bottom: 0; margin-bottom: 0; padding-bottom: 0; }
.secao__titulo {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 0 0 var(--e-3);
  font-size: var(--txt-sm);
  font-weight: var(--peso-forte);
  letter-spacing: .04em;
  text-transform: uppercase;
  color: var(--texto-fraco);
}
.secao__contagem { font-weight: var(--peso-normal); letter-spacing: 0; text-transform: none; color: var(--texto-apagado); }

.grade {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  column-gap: var(--e-4);
}
textarea.campo__entrada { resize: vertical; min-height: 4.5rem; }

.membros {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(100%, 200px), 1fr));
  gap: var(--e-2);
  margin-bottom: var(--e-2);
}
.membro {
  display: flex;
  align-items: center;
  gap: var(--e-2);
  min-height: var(--altura-toque);
  padding: var(--e-2) var(--e-3);
  border: var(--borda-fina) solid var(--borda);
  border-radius: var(--r-md);
  background: var(--superficie);
  cursor: pointer;
  transition: background var(--tempo-rapido) var(--curva), border-color var(--tempo-rapido) var(--curva);
}
.membro:hover { border-color: var(--borda-forte); background: var(--superficie-2); }
.membro--marcado { border-color: var(--acento-borda); background: var(--acento-suave); }
.membro input { width: 17px; height: 17px; accent-color: var(--acento); flex: none; }
.membro__nome { min-width: 0; overflow-wrap: anywhere; font-size: var(--txt-sm); }
</style>
