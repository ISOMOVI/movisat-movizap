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
import { agrupar, chaveDoGrupo, textosDoGrupo } from '../util/mensagem_agendamento.js'

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

/* ---- MÊS NAVEGÁVEL AO LADO (ponta 3 do plano, §8) ------------------------
   O carrossel entrega semana anterior / hoje / próxima; faltava o mês ao lado,
   para pular para um dia distante sem andar de sete em sete.

   ⚠️ O MÊS É UM ATALHO DE NAVEGAÇÃO, NÃO UMA SEGUNDA LISTA. Escolher um dia
   nele move a âncora do carrossel e recarrega os 7 dias -- quem manda no que
   a tela mostra continua sendo o carrossel. Duas listas de agendamento na
   mesma tela seriam duas respostas para a mesma pergunta.

   🚨 O SELO DE "TEM SERVIÇO" NÃO APARECE NO MÊS, de propósito: o que está
   carregado é a semana da âncora, então o mês saberia de uns dias e não de
   outros -- e um mês com pontos em três dias afirmaria que nos outros não há
   nada. Tela que mente é defeito. */
const mesAberto = ref(false)

function primeiroDoMes(isoDia) {
  const d = new Date(`${isoDia}T12:00:00`)
  return new Date(d.getFullYear(), d.getMonth(), 1, 12, 0, 0)
}

const mesCursor = ref(primeiroDoMes(iso(hoje)))

const rotuloDoMes = computed(() =>
  mesCursor.value.toLocaleDateString('pt-BR', { month: 'long', year: 'numeric' }))

const diasDoMes = computed(() => {
  const base = mesCursor.value
  const primeiro = new Date(base.getFullYear(), base.getMonth(), 1, 12, 0, 0)
  const lista = []
  // Os vazios antes do dia 1, para o dia cair na coluna do seu dia da semana.
  for (let i = 0; i < primeiro.getDay(); i += 1) lista.push(null)
  const d = new Date(primeiro)
  while (d.getMonth() === base.getMonth()) {
    lista.push({ iso: iso(d), dia: d.getDate(), hoje: iso(d) === iso(hoje) })
    d.setDate(d.getDate() + 1)
  }
  return lista
})

function andarMes(passo) {
  const d = new Date(mesCursor.value)
  d.setMonth(d.getMonth() + passo)
  mesCursor.value = new Date(d.getFullYear(), d.getMonth(), 1, 12, 0, 0)
}

function escolherDoMes(d) {
  ancora.value = d.iso
  selecionado.value = d.iso
  mesAberto.value = false
  carregar()
}

/* ---- REENVIAR CONFIRMAÇÃO (ponta 2 do plano, §8) -------------------------
   A quarta ação da linha. Entregaram-se três em 21/10 (Reagendar, Cancelar,
   Abrir conversa) e esta ficou faltando.

   🚨 NÃO ENVIA NADA. Decisão 6 dele, ao pé da letra: as duas confirmações
   saem pré-escritas e **quem envia é o atendente**. Aqui ela mostra os dois
   textos para copiar e oferece abrir a conversa com o texto no compositor.

   🚨 MONTA COM A MESMA REGRA DE AGRUPAMENTO (mesma data e hora => uma
   mensagem só, placas e OS somadas), e por isso junta os compromissos IRMÃOS:
   o mesmo cliente, na mesma hora, menos os cancelados. Reenviar só a linha
   clicada mandaria ao cliente um texto diferente do que ele recebeu.

   ⚠️ COMPROMISSO AINDA `aguardando` NÃO TEM RESPONSÁVEL: o texto sai com o
   campo vazio, e a tela diz por quê em vez de deixar o operador descobrir. */
const reenvio = ref(null)
const copiado = ref('')

function irmaosDe(a) {
  const chave = chaveDoGrupo(a)
  return agendamentos.value.filter(
    (x) => x.estado !== 'cancelado'
      && x.cliente_harmonit_id === a.cliente_harmonit_id
      && chaveDoGrupo(x) === chave)
}

function reenviarConfirmacao(a) {
  const grupo = irmaosDe(a)
  // `irmaosDe` exclui cancelado, e a ação não aparece em linha cancelada --
  // mas se por algum caminho chegar aqui vazia, usa a própria linha em vez de
  // montar mensagem de lista vazia.
  const [primeiro] = agrupar(grupo.length ? grupo : [a])
  reenvio.value = {
    agendamento: a,
    ...textosDoGrupo(primeiro, {}),
  }
  copiado.value = ''
}


async function copiar(qual, texto) {
  try {
    await navigator.clipboard.writeText(texto)
    copiado.value = qual
  } catch {
    // 🚨 A ÁREA DE TRANSFERÊNCIA FALHA SEM AVISO em contexto não seguro e
    // quando a aba não tem o foco. O texto está na tela, selecionável: o que
    // não pode é a tela afirmar que copiou sem ter copiado.
    copiado.value = ''
    acaoErro.value = 'Não deu para copiar — selecione o texto e copie à mão.'
  }
}

/* Abre a conversa com o texto JÁ no compositor.

   🚨 O CAMINHO É O RASCUNHO POR CONVERSA (Bloco 7, 15/10): a Caixa semeia o
   compositor com `localStorage['movizap.rascunho.<id>']` ao abrir a conversa.
   Escrever aqui é usar o mecanismo que já existe, em vez de inventar um
   segundo caminho de "texto pendente".

   ⚠️ NÃO SOBRESCREVE RASCUNHO SEM AVISAR: se já havia texto guardado naquela
   conversa, pergunta. Perder meia frase digitada pelo colega é o defeito que
   o Bloco 7 nasceu para corrigir. */
function abrirConversaComTexto(a, texto) {
  if (!a.conversa_id) return
  const chave = `movizap.rascunho.${a.conversa_id}`
  try {
    const havia = localStorage.getItem(chave)
    if (havia && havia.trim() && havia !== texto
        && !window.confirm('Esta conversa já tem texto não enviado no '
                           + 'compositor. Substituir pelo da confirmação?')) {
      return
    }
    localStorage.setItem(chave, texto)
  } catch {
    // Sem storage (janela privada, dados bloqueados): abre a conversa de todo
    // jeito e diz que o texto não foi semeado -- o texto continua na tela.
    acaoErro.value = 'Abri a conversa, mas não deu para deixar o texto no '
      + 'compositor neste navegador. Copie o texto acima.'
  }
  reenvio.value = null
  router.push(`/atendimento/${a.conversa_id}`)
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
        <!-- Ponta 3: o mês ao lado, para pular para um dia distante sem andar
             de sete em sete. Atalho de navegação, não uma segunda lista. -->
        <button class="botao botao--fantasma agd__mes-botao" type="button"
                :aria-expanded="mesAberto ? 'true' : 'false'"
                @click="mesAberto = !mesAberto">
          <i class="bi bi-calendar3" aria-hidden="true"></i> Mês
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

    <div v-if="mesAberto" class="agd__mes">
      <header class="agd__mes-topo">
        <button class="botao botao--fantasma" type="button" @click="andarMes(-1)"
                aria-label="Mês anterior">
          <i class="bi bi-chevron-left" aria-hidden="true"></i>
        </button>
        <strong class="agd__mes-rotulo">{{ rotuloDoMes }}</strong>
        <button class="botao botao--fantasma" type="button" @click="andarMes(1)"
                aria-label="Mês seguinte">
          <i class="bi bi-chevron-right" aria-hidden="true"></i>
        </button>
      </header>
      <div class="agd__mes-grade">
        <span v-for="s in ['D', 'S', 'T', 'Q', 'Q', 'S', 'S']" :key="s"
              class="agd__mes-semana">{{ s }}</span>
        <template v-for="(d, i) in diasDoMes" :key="d ? d.iso : `vazio-${i}`">
          <span v-if="!d" class="agd__mes-vago"></span>
          <button v-else type="button" class="agd__mes-dia"
                  :class="{ 'agd__mes-dia--ativo': d.iso === selecionado,
                            'agd__mes-dia--hoje': d.hoje }"
                  @click="escolherDoMes(d)">{{ d.dia }}</button>
        </template>
      </div>
      <!-- 🚨 Dizer isto evita que a ausência de marca pareça ausência de
           serviço: o que está carregado é a semana da âncora. -->
      <p class="agd__mes-nota">
        Escolher um dia move a semana do carrossel. As marcas de serviço ficam
        no carrossel, que é o que está carregado.
      </p>
    </div>

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
              <button v-if="a.estado !== 'cancelado'" class="botao botao--fantasma"
                      type="button" @click="reenviarConfirmacao(a)">Reenviar confirmação</button>
              <button v-if="a.conversa_id" class="botao botao--fantasma"
                      type="button" @click="abrirConversa(a)">Abrir conversa</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 🚨 NÃO ENVIA NADA (decisão 6 dele): mostra para copiar e oferece abrir
         a conversa com o texto no compositor. -->
    <div v-if="reenvio" class="agd__reenvio">
      <header class="agd__reenvio-topo">
        <strong>Confirmação de {{ reenvio.agendamento.cliente_nome }}</strong>
        <button class="botao botao--fantasma" type="button" @click="reenvio = null">
          Fechar
        </button>
      </header>

      <p class="aviso aviso--info agd__reenvio-aviso">
        Isto <b>não envia nada</b>: quem envia é você. Copie o texto, ou abra a
        conversa com ele já no compositor.
      </p>
      <p v-if="reenvio.quantos > 1" class="agd__reenvio-nota">
        Mesma data e hora: {{ reenvio.quantos }} compromissos entraram numa
        mensagem só, com as placas e as OS somadas ({{ reenvio.ordens.join(', ') }}).
      </p>
      <!-- ⚠️ Compromisso ainda aguardando não tem responsável: o campo sai
           vazio, e a tela diz por quê. -->
      <p v-if="reenvio.semResponsavel" class="aviso aviso--atencao agd__reenvio-nota">
        Este compromisso ainda não foi confirmado pelo cliente, então ninguém
        disse quem acompanha o técnico — o campo sai vazio. Quem preenche é a
        aba <b>Confirmar</b>, na conversa do cliente.
      </p>

      <div class="agd__reenvio-textos">
        <article>
          <h3 class="agd__reenvio-rotulo">Para o cliente</h3>
          <pre class="agd__reenvio-pre">{{ reenvio.doCliente }}</pre>
          <div class="agd__acoes">
            <button class="botao botao--fantasma" type="button"
                    @click="copiar('cliente', reenvio.doCliente)">
              {{ copiado === 'cliente' ? 'Copiado' : 'Copiar' }}
            </button>
            <button v-if="reenvio.agendamento.conversa_id" class="botao botao--contorno"
                    type="button"
                    @click="abrirConversaComTexto(reenvio.agendamento, reenvio.doCliente)">
              Abrir conversa com este texto
            </button>
          </div>
        </article>
        <article>
          <h3 class="agd__reenvio-rotulo">Para o técnico</h3>
          <pre class="agd__reenvio-pre">{{ reenvio.doTecnico }}</pre>
          <div class="agd__acoes">
            <button class="botao botao--fantasma" type="button"
                    @click="copiar('tecnico', reenvio.doTecnico)">
              {{ copiado === 'tecnico' ? 'Copiado' : 'Copiar' }}
            </button>
            <button v-if="reenvio.agendamento.conversa_id" class="botao botao--contorno"
                    type="button"
                    @click="abrirConversaComTexto(reenvio.agendamento, reenvio.doTecnico)">
              Abrir conversa com este texto
            </button>
          </div>
        </article>
      </div>
      <!-- A conversa de ORIGEM é a do técnico (decisão dele de 07/10: em
           conversa de técnico o `cliente_id` do contato é nulo). Dizer isso
           evita o operador achar que "abrir conversa" leva ao cliente. -->
      <p class="agd__reenvio-nota">
        “Abrir conversa” leva à conversa de onde este agendamento saiu — a do
        técnico. A do cliente abre-se pela Caixa.
      </p>
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

/* O mês ao lado (ponta 3) */
.agd__mes {
  display: flex;
  flex-direction: column;
  gap: var(--e-2);
  align-self: flex-start;
  padding: var(--e-3);
  border: var(--borda-fina) solid var(--borda);
  border-radius: var(--r-md);
  background: var(--superficie-2);
}
.agd__mes-topo { display: flex; align-items: center; justify-content: space-between; gap: var(--e-2); }
.agd__mes-rotulo { text-transform: capitalize; }
.agd__mes-grade { display: grid; grid-template-columns: repeat(7, 36px); gap: 4px; }
.agd__mes-semana { text-align: center; font-size: var(--txt-xs); color: var(--texto-fraco); }
.agd__mes-vago { display: block; }
.agd__mes-dia {
  height: 32px;
  border: var(--borda-fina) solid transparent;
  border-radius: var(--r-sm);
  background: var(--superficie);
  color: inherit;
  cursor: pointer;
}
.agd__mes-dia--hoje { border-color: var(--acento); }
.agd__mes-dia--ativo { background: var(--acento); color: #fff; }
.agd__mes-nota { margin: 0; max-width: 34ch; color: var(--texto-fraco); font-size: var(--txt-xs); }

/* Reenviar confirmação (ponta 2) */
.agd__reenvio {
  display: flex;
  flex-direction: column;
  gap: var(--e-2);
  padding: var(--e-3);
  border: var(--borda-fina) solid var(--borda);
  border-radius: var(--r-md);
  background: var(--superficie-2);
}
.agd__reenvio-topo { display: flex; align-items: center; justify-content: space-between; gap: var(--e-2); }
.agd__reenvio-aviso, .agd__reenvio-nota { margin: 0; }
.agd__reenvio-nota { color: var(--texto-fraco); font-size: var(--txt-sm); }
.agd__reenvio-textos { display: flex; gap: var(--e-3); flex-wrap: wrap; }
.agd__reenvio-textos > article { flex: 1 1 320px; display: flex; flex-direction: column; gap: var(--e-2); }
.agd__reenvio-rotulo { margin: 0; font-size: var(--txt-sm); }
.agd__reenvio-pre {
  margin: 0;
  padding: var(--e-2);
  border: var(--borda-fina) solid var(--borda);
  border-radius: var(--r-sm);
  background: var(--superficie);
  white-space: pre-wrap;
  word-break: break-word;
  font-size: var(--txt-sm);
}
.agd__vazio { color: var(--texto-fraco); font-size: var(--txt-sm); }
.agd__acoes { display: flex; gap: var(--e-1); flex-wrap: wrap; }
.agd__linha--cancelada { opacity: .65; }
.agd__motivo { display: block; color: var(--texto-fraco); }
.agd__estado { font-size: var(--txt-xs); font-weight: var(--peso-forte); }
.agd__estado--confirmado { color: var(--ok); }
.agd__estado--aguardando { color: var(--aviso); }
.agd__estado--cancelado { color: var(--erro); }
</style>
