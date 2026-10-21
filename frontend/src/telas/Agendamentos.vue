<script setup>
/* ============================================================================
   ATD_7.1 — Agendamentos. 🔵 Decisão 14 dele (19/10): é TELA, em Atendimento,
   **aberta a todo atendente**.
   ----------------------------------------------------------------------------
   🚨 ESTA TELA DIZ A COBERTURA DELA. Só aparece aqui o que foi agendado pelo
   MoviZap — serviço combinado por fora, ou marcado direto no Harmonit, não
   existe nesta lista. Mesma régua da faixa da aba Ligações: ausência não pode
   parecer "não tem".

   🚨 NÃO É O `agenda.py` DA TELA INÍCIO. Aquele é a agenda do Google e o topo
   dele diz, desde que nasceu, que não é um calendário — virar calendário faria
   a Início deixar de ser "o que precisa de você". O calendário é aqui.
   ============================================================================ */
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { api } from '../api/cliente.js'

const router = useRouter()

const agendamentos = ref([])
const carregando = ref(true)
const erro = ref('')
const acaoErro = ref('')

/* O carrossel: ontem, hoje e os 5 próximos — os 7 dias que ele pediu. */
const DIAS_ANTES = 1
const DIAS_DEPOIS = 5

function iso(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

const hoje = new Date()
const ancora = ref(iso(hoje))
const selecionado = ref(iso(hoje))

const dias = computed(() => {
  const base = new Date(`${ancora.value}T12:00:00`)
  const lista = []
  for (let i = -DIAS_ANTES; i <= DIAS_DEPOIS; i += 1) {
    const d = new Date(base)
    d.setDate(base.getDate() + i)
    lista.push({
      iso: iso(d),
      dia: d.getDate(),
      mes: d.toLocaleDateString('pt-BR', { month: 'short' }).replace('.', ''),
      semana: d.toLocaleDateString('pt-BR', { weekday: 'short' }).replace('.', ''),
      hoje: iso(d) === iso(hoje),
    })
  }
  return lista
})

const doDia = computed(() =>
  agendamentos.value.filter((a) => (a.inicio || '').slice(0, 10) === selecionado.value))

/* Quantos por dia, para o carrossel marcar os dias com serviço — um ponto no
   dia vazio e um no dia cheio seria a mesma tela para casos diferentes. */
const porDia = computed(() => {
  const conta = {}
  for (const a of agendamentos.value) {
    if (a.estado === 'cancelado') continue
    const d = (a.inicio || '').slice(0, 10)
    conta[d] = (conta[d] || 0) + 1
  }
  return conta
})

const ROTULO_ESTADO = {
  rascunho: 'Rascunho',
  aguardando: 'Aguardando confirmação',
  confirmado: 'Confirmado',
  cancelado: 'Cancelado',
}

function hora(valor) {
  if (!valor) return '—'
  return new Date(valor).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
}

function placas(a) {
  const comPlaca = (a.ordens || []).filter((o) => o.placa).map((o) => o.placa)
  // ⚠️ Só 236 das 572 OS têm oficina, e é dela que sai a placa. Dizer o
  // porquê é diferente de desenhar uma coluna em branco.
  if (!comPlaca.length) return 'sem placa registrada'
  return comPlaca.join(', ')
}

function ordens(a) {
  return (a.ordens || []).map((o) => o.numero_os).join(', ') || '—'
}

async function carregar() {
  carregando.value = true
  erro.value = ''
  const base = new Date(`${ancora.value}T12:00:00`)
  const de = new Date(base)
  de.setDate(base.getDate() - DIAS_ANTES)
  const ate = new Date(base)
  ate.setDate(base.getDate() + DIAS_DEPOIS)
  try {
    const r = await api.get(`/api/agendamentos?de=${iso(de)}&ate=${iso(ate)}`)
    agendamentos.value = r.agendamentos || []
  } catch (e) {
    erro.value = e?.message || 'Não deu para carregar os agendamentos.'
    agendamentos.value = []
  } finally {
    carregando.value = false
  }
}

function andar(passo) {
  const base = new Date(`${ancora.value}T12:00:00`)
  base.setDate(base.getDate() + passo)
  ancora.value = iso(base)
  selecionado.value = iso(base)
  carregar()
}

function irParaHoje() {
  ancora.value = iso(hoje)
  selecionado.value = iso(hoje)
  carregar()
}

async function cancelar(a) {
  const motivo = window.prompt(
    `Cancelar o agendamento de ${a.cliente_nome}?\n\nPor quê? (fica registrado)`)
  if (!motivo || !motivo.trim()) return
  acaoErro.value = ''
  try {
    await api.post(`/api/agendamentos/${a.id}/cancelar`, { motivo: motivo.trim() })
    await carregar()
  } catch (e) {
    acaoErro.value = e?.message || 'Não deu para cancelar.'
  }
}

async function reagendar(a) {
  const quando = window.prompt(
    `Nova data e hora para ${a.cliente_nome}:`,
    (a.inicio || '').slice(0, 16).replace('T', ' '))
  if (!quando) return
  const normalizado = quando.trim().replace(' ', 'T')
  if (Number.isNaN(Date.parse(normalizado))) {
    acaoErro.value = 'Data não reconhecida. Use AAAA-MM-DD HH:MM.'
    return
  }
  acaoErro.value = ''
  try {
    await api.post(`/api/agendamentos/${a.id}/reagendar`,
                   { inicio: new Date(normalizado).toISOString() })
    await carregar()
  } catch (e) {
    acaoErro.value = e?.message || 'Não deu para reagendar.'
  }
}

function abrirConversa(a) {
  if (!a.conversa_id) return
  router.push(`/atendimento/${a.conversa_id}`)
}

onMounted(carregar)
</script>

<template>
  <section class="agd">
    <header class="agd__topo">
      <h1 class="agd__titulo">Agendamentos</h1>
      <div class="agd__navegacao">
        <button class="botao botao--fantasma" type="button" @click="andar(-7)">
          <i class="bi bi-chevron-left" aria-hidden="true"></i> Semana anterior
        </button>
        <button class="botao botao--fantasma" type="button" @click="irParaHoje">Hoje</button>
        <button class="botao botao--fantasma" type="button" @click="andar(7)">
          Próxima semana <i class="bi bi-chevron-right" aria-hidden="true"></i>
        </button>
      </div>
    </header>

    <!-- 🚨 A faixa de cobertura. Ausência não pode parecer "não tem". -->
    <p class="aviso aviso--info agd__cobertura">
      Aparece aqui o que foi agendado <b>por este painel</b>. Serviço combinado
      por fora, ou marcado direto no Harmonit, não entra nesta lista.
    </p>

    <nav class="agd__carrossel" aria-label="Dias">
      <button
        v-for="d in dias"
        :key="d.iso"
        type="button"
        class="agd__dia"
        :class="{ 'agd__dia--ativo': d.iso === selecionado, 'agd__dia--hoje': d.hoje }"
        @click="selecionado = d.iso"
      >
        <span class="agd__dia-semana">{{ d.semana }}</span>
        <span class="agd__dia-numero">{{ d.dia }}</span>
        <span class="agd__dia-mes">{{ d.mes }}</span>
        <span v-if="porDia[d.iso]" class="agd__dia-selo">{{ porDia[d.iso] }}</span>
      </button>
    </nav>

    <p v-if="erro" class="aviso aviso--erro">{{ erro }}</p>
    <p v-if="acaoErro" class="aviso aviso--erro">{{ acaoErro }}</p>
    <p v-if="carregando" class="agd__vazio">Carregando…</p>

    <p v-else-if="!doDia.length" class="agd__vazio">
      Nenhum serviço agendado por este painel neste dia.
    </p>

    <div v-else class="agd__grid">
      <table class="tabela">
        <thead>
          <tr>
            <th>Hora</th>
            <th>Cliente</th>
            <th>Técnico</th>
            <th>Placas</th>
            <th>OS</th>
            <th>Endereço</th>
            <th>Responsável</th>
            <th>Orçamento</th>
            <th>Estado</th>
            <th>Ações</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="a in doDia" :key="a.id" :class="{ 'agd__linha--cancelada': a.estado === 'cancelado' }">
            <td>{{ hora(a.inicio) }}</td>
            <td>{{ a.cliente_nome }}</td>
            <td>{{ a.tecnico_nome || '—' }}</td>
            <td>{{ placas(a) }}</td>
            <td>{{ ordens(a) }}</td>
            <td>{{ a.endereco || '—' }}</td>
            <td>{{ a.responsavel_cliente || '—' }}</td>
            <td>{{ a.orcamento_numero || '—' }}</td>
            <td>
              <span class="agd__estado" :class="`agd__estado--${a.estado}`">
                {{ ROTULO_ESTADO[a.estado] || a.estado }}
              </span>
              <small v-if="a.estado === 'cancelado' && a.motivo_cancelamento"
                     class="agd__motivo">{{ a.motivo_cancelamento }}</small>
            </td>
            <td class="agd__acoes">
              <button v-if="a.estado !== 'cancelado'" class="botao botao--fantasma"
                      type="button" @click="reagendar(a)">Reagendar</button>
              <button v-if="a.estado !== 'cancelado'" class="botao botao--fantasma"
                      type="button" @click="cancelar(a)">Cancelar</button>
              <button v-if="a.conversa_id" class="botao botao--fantasma"
                      type="button" @click="abrirConversa(a)">Abrir conversa</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<style scoped>
.agd { display: flex; flex-direction: column; gap: var(--e-3); min-height: 0; }
.agd__topo { display: flex; align-items: center; justify-content: space-between; gap: var(--e-3); flex-wrap: wrap; }
.agd__titulo { margin: 0; font-size: var(--txt-lg); }
.agd__navegacao { display: flex; gap: var(--e-2); flex-wrap: wrap; }
.agd__cobertura { margin: 0; }

.agd__carrossel { display: flex; gap: var(--e-2); overflow-x: auto; padding-bottom: var(--e-1); }
.agd__dia {
  position: relative;
  flex: none;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  min-width: 68px;
  padding: var(--e-2);
  border: var(--borda-fina) solid var(--borda);
  border-radius: var(--r-md);
  background: var(--superficie-2);
  color: inherit;
  cursor: pointer;
}
.agd__dia--hoje { border-color: var(--acento); }
.agd__dia--ativo { background: var(--acento); color: #fff; border-color: var(--acento); }
.agd__dia-semana, .agd__dia-mes { font-size: var(--txt-xs); text-transform: uppercase; }
.agd__dia-numero { font-size: var(--txt-lg); font-weight: var(--peso-forte); }
.agd__dia-selo {
  position: absolute;
  top: 4px;
  right: 6px;
  min-width: 16px;
  height: 16px;
  padding: 0 4px;
  border-radius: 999px;
  background: var(--acento);
  color: #fff;
  font-size: 10px;
  line-height: 16px;
}
.agd__dia--ativo .agd__dia-selo { background: rgba(255, 255, 255, .35); }

.agd__grid { overflow-x: auto; }
.agd__vazio { color: var(--texto-fraco); font-size: var(--txt-sm); }
.agd__acoes { display: flex; gap: var(--e-1); flex-wrap: wrap; }
.agd__linha--cancelada { opacity: .65; }
.agd__motivo { display: block; color: var(--texto-fraco); }
.agd__estado { font-size: var(--txt-xs); font-weight: var(--peso-forte); }
.agd__estado--confirmado { color: var(--ok); }
.agd__estado--aguardando { color: var(--aviso); }
.agd__estado--cancelado { color: var(--erro); }
</style>
