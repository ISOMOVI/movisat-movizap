<script setup>
/* ============================================================================
   CAD_2.1 — Atendentes.
   ----------------------------------------------------------------------------
   Os 4 vieram do Chatwoot SEM SENHA, de propósito: conta que não tem senha não
   entra no painel — `auth.validar_login` recusa antes do bcrypt. A senha se
   define aqui, uma a uma.

   🚨 A PAUSA DO ALMOÇO É O INTERVALO ENTRE DUAS FAIXAS DO MESMO DIA.
   08:00–12:00 e 13:00–18:00 são duas linhas, e o almoço é o buraco entre elas.
   Não existe campo "pausa", e é por isso que cada dia aceita várias faixas.

   ⚠️ A jornada NÃO bloqueia transferência. Ela existe para a fila AVISAR que
   a pessoa está fora do horário — bloquear faria o atendente fechar a conversa
   para se livrar dela, e aí o cliente some do radar de vez.
   ============================================================================ */
import { ref, computed, onMounted } from 'vue'

import { api, ErroDeApi } from '../api/cliente.js'

const DIAS = ['Domingo', 'Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado']
const PERFIS = ['owner', 'admin', 'atendimento', 'cadastro']
const ESTADOS = [
  { valor: 'disponivel', rotulo: 'Disponível' },
  { valor: 'ausente', rotulo: 'Ausente' },
  { valor: 'nao_perturbe', rotulo: 'Não perturbe' },
]

const atendentes = ref([])
const times = ref([])
const carregando = ref(true)
const erro = ref('')
const salvando = ref(false)
const incluirInativos = ref(false)

const editando = ref(null)
const form = ref(vazio())
const timesMarcados = ref([])
const jornada = ref([])
const novaSenha = ref('')
const recado = ref('')

/* ⚠️ Cada faixa carrega um `uid` só para o :key do v-for. Sem chave estável, o
   Vue recicla o <input> pelo índice: remover a faixa do meio faz o horário da
   seguinte aparecer no lugar errado, e o usuário salva sem perceber. */
let proximoUid = 1
const comUid = (faixa) => ({ ...faixa, uid: proximoUid++ })

function vazio() {
  return {
    nome: '', login: '', email: '', perfil: 'atendimento',
    estado: 'disponivel', max_conversas: null, ativo: true,
    fuso: 'America/Sao_Paulo',
  }
}

async function carregar() {
  carregando.value = true
  erro.value = ''
  try {
    const [lista, listaTimes] = await Promise.all([
      api.get(`/api/atendentes?incluir_inativos=${incluirInativos.value}`),
      api.get('/api/times'),
    ])
    atendentes.value = lista
    times.value = listaTimes
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Falha ao ler os atendentes.'
  } finally {
    carregando.value = false
  }
}

onMounted(carregar)

function abrirNovo() {
  editando.value = {}
  form.value = vazio()
  timesMarcados.value = []
  jornada.value = []
  novaSenha.value = ''
  erro.value = ''
  recado.value = ''
}

function abrirEdicao(a) {
  editando.value = a
  form.value = {
    nome: a.nome, login: a.login, email: a.email || '', perfil: a.perfil,
    estado: a.estado, max_conversas: a.max_conversas, ativo: a.ativo,
    fuso: a.fuso,
  }
  timesMarcados.value = a.times.map((t) => t.id)
  jornada.value = a.jornada.map((f) => comUid({
    dia_semana: f.dia_semana,
    inicio: (f.inicio || '').slice(0, 5),
    fim: (f.fim || '').slice(0, 5),
  }))
  novaSenha.value = ''
  erro.value = ''
  recado.value = ''
}

function fechar() {
  editando.value = null
  erro.value = ''
  recado.value = ''
}

function adicionarFaixa(dia) {
  jornada.value.push(comUid({ dia_semana: dia, inicio: '08:00', fim: '12:00' }))
}

function removerFaixa(faixa) {
  jornada.value = jornada.value.filter((f) => f !== faixa)
}

function faixasDe(dia) {
  return jornada.value.filter((f) => f.dia_semana === dia)
}

const resumoJornada = (a) => {
  if (!a.jornada.length) return 'sem jornada'
  const dias = new Set(a.jornada.map((f) => f.dia_semana))
  return `${a.jornada.length} faixa(s) em ${dias.size} dia(s)`
}

const timesDe = (a) => (a.times.length ? a.times.map((t) => t.nome).join(', ') : '—')

const semSenha = computed(() => atendentes.value.filter((a) => !a.tem_senha).length)

async function salvar() {
  salvando.value = true
  erro.value = ''
  recado.value = ''
  try {
    const corpo = {
      ...form.value,
      email: form.value.email || null,
      max_conversas: form.value.max_conversas || null,
    }
    const alvo = editando.value?.id
      ? await api.put(`/api/atendentes/${editando.value.id}`, corpo)
      : await api.post('/api/atendentes', corpo)

    await api.put(`/api/atendentes/${alvo.id}/times`, { times: timesMarcados.value })
    await api.put(`/api/atendentes/${alvo.id}/jornada`, { faixas: jornada.value })

    if (novaSenha.value) {
      await api.post(`/api/atendentes/${alvo.id}/senha`, { senha: novaSenha.value })
      novaSenha.value = ''
    }
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
        <h1>Atendentes</h1>
        <p class="fraco pequeno">
          Quem atende, em quais times, e em que horário. Conta sem senha existe
          mas não entra no painel.
        </p>
      </div>
      <div class="linha">
        <label class="linha pequeno fraco">
          <input v-model="incluirInativos" type="checkbox" @change="carregar" />
          mostrar inativos
        </label>
        <button class="botao botao--primario" type="button" @click="abrirNovo">
          <i class="bi bi-person-plus" aria-hidden="true"></i> Novo atendente
        </button>
      </div>
    </header>

    <p v-if="semSenha && !carregando" class="aviso aviso--atencao" role="status">
      <i class="bi bi-key aviso__icone" aria-hidden="true"></i>
      <span>
        <strong>{{ semSenha }} conta(s) sem senha.</strong>
        Vieram do Chatwoot e ainda não entram no painel — isso é o falha-fechado
        funcionando, não defeito. Defina a senha ao editar cada uma.
      </span>
    </p>

    <p v-if="erro && !editando" class="aviso aviso--erro" role="alert">
      <i class="bi bi-exclamation-octagon aviso__icone" aria-hidden="true"></i>
      <span>{{ erro }}</span>
    </p>

    <section v-if="editando" class="cartao tela__bloco">
      <header class="cartao__cabecalho">
        <span>{{ editando.id ? `Editando ${editando.nome}` : 'Novo atendente' }}</span>
        <span v-if="editando.origem" class="chip mono pequeno">{{ editando.origem }}</span>
      </header>

      <div class="cartao__corpo pilha">
        <div class="grade">
          <label class="campo">
            <span class="campo__rotulo">Nome de exibição</span>
            <input v-model="form.nome" class="campo__entrada" maxlength="200" />
            <span class="campo__ajuda">É o que o cliente vê.</span>
          </label>

          <label class="campo">
            <span class="campo__rotulo">Login</span>
            <input v-model="form.login" class="campo__entrada" maxlength="60" autocapitalize="off" />
          </label>

          <label class="campo">
            <span class="campo__rotulo">E-mail</span>
            <input v-model="form.email" class="campo__entrada" type="email" maxlength="200" />
          </label>

          <label class="campo">
            <span class="campo__rotulo">Perfil</span>
            <select v-model="form.perfil" class="campo__entrada">
              <option v-for="p in PERFIS" :key="p" :value="p">{{ p }}</option>
            </select>
            <span class="campo__ajuda">Define o que a pessoa enxerga no menu.</span>
          </label>

          <label class="campo">
            <span class="campo__rotulo">Estado</span>
            <select v-model="form.estado" class="campo__entrada">
              <option v-for="e in ESTADOS" :key="e.valor" :value="e.valor">{{ e.rotulo }}</option>
            </select>
          </label>

          <label class="campo">
            <span class="campo__rotulo">Teto de conversas simultâneas</span>
            <input v-model.number="form.max_conversas" class="campo__entrada" type="number" min="1" />
            <span class="campo__ajuda">
              Em branco = sem teto. Evita empilhar tudo em quem é rápido.
            </span>
          </label>
        </div>

        <fieldset class="bloco">
          <legend class="campo__rotulo">Times</legend>
          <div class="linha linha--quebra">
            <label v-for="t in times" :key="t.id" class="linha pequeno">
              <input v-model="timesMarcados" type="checkbox" :value="t.id" />
              <span>{{ t.nome }}</span>
            </label>
          </div>
        </fieldset>

        <fieldset class="bloco">
          <legend class="campo__rotulo">Jornada</legend>
          <p class="campo__ajuda">
            A pausa do almoço é o <strong>intervalo entre duas faixas do mesmo
            dia</strong>: 08:00–12:00 e 13:00–18:00. Sem jornada, a fila conta
            a pessoa como fora do expediente sempre.
          </p>
          <div v-for="(nome, dia) in DIAS" :key="dia" class="dia">
            <span class="dia__nome">{{ nome }}</span>
            <div class="dia__faixas">
              <div v-for="faixa in faixasDe(dia)" :key="faixa.uid" class="linha">
                <input v-model="faixa.inicio" class="campo__entrada campo--hora" type="time" />
                <span class="fraco">até</span>
                <input v-model="faixa.fim" class="campo__entrada campo--hora" type="time" />
                <button
                  class="botao botao--pequeno botao--fantasma"
                  type="button"
                  :aria-label="`Remover faixa de ${nome}`"
                  @click="removerFaixa(faixa)"
                >
                  <i class="bi bi-x-lg" aria-hidden="true"></i>
                </button>
              </div>
              <button class="botao botao--pequeno botao--contorno" type="button" @click="adicionarFaixa(dia)">
                <i class="bi bi-plus-lg" aria-hidden="true"></i> faixa
              </button>
            </div>
          </div>
        </fieldset>

        <label class="campo">
          <span class="campo__rotulo">
            {{ editando.tem_senha ? 'Trocar a senha' : 'Definir a senha' }}
          </span>
          <input
            v-model="novaSenha"
            class="campo__entrada"
            type="password"
            autocomplete="new-password"
            minlength="10"
            maxlength="256"
            placeholder="deixe em branco para não mexer"
          />
          <span class="campo__ajuda">Pelo menos 10 caracteres.</span>
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
      <span class="girando"></span> Lendo os atendentes…
    </p>

    <div v-else-if="!atendentes.length" class="vazio">
      <i class="bi bi-people vazio__icone" aria-hidden="true"></i>
      <p class="vazio__titulo">Nenhum atendente</p>
      <p>Os 4 do Chatwoot deviam estar aqui — confira a importação.</p>
    </div>

    <section v-else class="cartao tela__bloco">
      <div class="tabela--rolavel">
        <table class="tabela">
          <thead>
            <tr>
              <th>Atendente</th>
              <th>Perfil</th>
              <th>Times</th>
              <th>Jornada</th>
              <th>Entra?</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="a in atendentes" :key="a.id" :class="{ 'linha--inativa': !a.ativo }">
              <td>
                <strong>{{ a.nome }}</strong>
                <p class="apagado pequeno mono">{{ a.login }}<span v-if="a.email"> · {{ a.email }}</span></p>
              </td>
              <td><span class="chip">{{ a.perfil }}</span></td>
              <td class="pequeno fraco">{{ timesDe(a) }}</td>
              <td class="pequeno">
                <span :class="a.jornada.length ? 'fraco' : 'chip chip--aviso'">{{ resumoJornada(a) }}</span>
              </td>
              <td>
                <span v-if="a.tem_senha" class="chip chip--ok">sim</span>
                <span v-else class="chip chip--aviso">sem senha</span>
              </td>
              <td>
                <button class="botao botao--pequeno botao--contorno" type="button" @click="abrirEdicao(a)">
                  Editar
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <p class="apagado pequeno">
      Atendente não é apagado, é desativado — <code>conversa</code> e
      <code>transferencia</code> apontam para ele. E ninguém consegue desativar
      a própria conta.
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

.grade {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: var(--e-3);
}

.bloco { border: 0; padding: 0; margin: 0; }

.linha--quebra { flex-wrap: wrap; gap: var(--e-3); }

.dia {
  display: flex;
  align-items: flex-start;
  gap: var(--e-3);
  padding: var(--e-2) 0;
  flex-wrap: wrap;
}
.dia__nome { min-width: 84px; font-weight: 600; }
.dia__faixas { display: flex; flex-direction: column; gap: var(--e-2); }

.campo--hora { width: auto; min-width: 7.5rem; }

.linha--inativa td { opacity: .6; }
</style>
