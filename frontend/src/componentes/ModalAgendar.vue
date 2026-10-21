<script setup>
/* ============================================================================
   O modal do botão Agendar — três abas. 🔵 Pedido dele de 19/10.
   ----------------------------------------------------------------------------
   🔵 Fluxo real, nas palavras dele: *"o operador pede dados ao cliente via
   chat, confirma com o tecnico e dai envia o orçamento para ele; ele
   validando, vai clicar no agendamento tecnico e depois no do cliente para
   confirmar"*. Por isso a ordem é **Orçamento → Agendar → Confirmar**.

   🚨 A ABA QUE ABRE DEPENDE DO CONTATO. Conversa de técnico vê Orçamento e
   Agendar; conversa de cliente vê Confirmar. Conversa sem contato não some
   com o botão: ela **explica por que não dá**, que é a diferença entre uma
   tela que ensina e uma que esconde.

   🚨 AS DUAS CONFIRMAÇÕES SAEM PRÉ-ESCRITAS, E QUEM ENVIA É O ATENDENTE
   (decisão 6 dele). Este modal escreve no compositor e sai da frente -- não
   manda nada sozinho.
   ============================================================================ */
import { computed, onMounted, ref, watch } from 'vue'

import { api } from '../api/cliente.js'

const props = defineProps({
  conversaId: { type: Number, required: true },
  relacao: { type: String, default: '' },
  contatoNome: { type: String, default: '' },
  // Só existe em conversa de CLIENTE: em conversa de técnico o
  // `contato.cliente_id` é NULL por desenho (decisão dele de 07/10).
  clienteHarmonitId: { type: String, default: '' },
  clienteNome: { type: String, default: '' },
})
const emit = defineEmits(['fechar', 'inserir'])

const ehTecnico = computed(() => props.relacao === 'tecnico')
const ehCliente = computed(() => props.relacao === 'cliente')

const abas = computed(() => {
  if (ehTecnico.value) return [
    { id: 'orcamento', rotulo: 'Orçamento' },
    { id: 'agendar', rotulo: 'Agendar' },
  ]
  if (ehCliente.value) return [{ id: 'confirmar', rotulo: 'Confirmar' }]
  return []
})
const aba = ref('')
watch(abas, (lista) => { if (!aba.value && lista.length) aba.value = lista[0].id },
      { immediate: true })

const erro = ref('')
const ocupado = ref(false)

/* ---------------------------------------------------------------- Orçamento */
const catalogo = ref([])
const proximoNumero = ref(null)
const linhas = ref([])
const osDoOrcamento = ref('')
const orcamentoEmitido = ref(null)

function linhaNova() {
  const padrao = catalogo.value[0] || { servico: '', unidade: 'un' }
  return { servico: padrao.servico, preco_unit: '', quantidade: '1',
           unidade: padrao.unidade }
}

function trocarServico(linha) {
  const achado = catalogo.value.find((c) => c.servico === linha.servico)
  // A unidade acompanha o serviço: deslocamento é km, e é isso que faz o PDF
  // imprimir "77,7 km" em vez de "77.7 un".
  if (achado) linha.unidade = achado.unidade
}

const totalCentavos = computed(() => linhas.value.reduce((soma, l) => {
  const preco = Math.round((Number(String(l.preco_unit).replace(',', '.')) || 0) * 100)
  const qtd = Number(String(l.quantidade).replace(',', '.')) || 0
  return soma + Math.round(preco * qtd)
}, 0))

function emReais(centavos) {
  return (centavos / 100).toLocaleString('pt-BR', { minimumFractionDigits: 2 })
}

const podeEmitir = computed(() =>
  linhas.value.length > 0 &&
  linhas.value.every((l) => l.servico && Number(String(l.preco_unit).replace(',', '.')) > 0
                            && Number(String(l.quantidade).replace(',', '.')) > 0))

async function emitirOrcamento() {
  ocupado.value = true
  erro.value = ''
  try {
    const ordens = osDoOrcamento.value
      .split(/[\s,;]+/).map((n) => Number(n)).filter((n) => Number.isInteger(n) && n > 0)
    orcamentoEmitido.value = await api.post(
      `/api/conversas/${props.conversaId}/orcamento`,
      { ordens, itens: linhas.value.map((l) => ({ ...l })) })
    proximoNumero.value = orcamentoEmitido.value.numero + 1
  } catch (e) {
    erro.value = e?.message || 'Não deu para emitir o orçamento.'
  } finally {
    ocupado.value = false
  }
}

/* ------------------------------------------------------------------ Agendar */
const passo = ref(1)
const quando = ref('')
const clientes = ref([])
const buscaCliente = ref('')
const clienteEscolhido = ref(null)
const osDoCliente = ref([])
const jaAgendadas = ref([])
const osEscolhidas = ref([])
const endereco = ref('')
const agendado = ref(null)

const clientesFiltrados = computed(() => {
  const termo = buscaCliente.value.trim().toUpperCase()
  const lista = clientes.value.filter((c) => !c.sem_cadastro)
  if (!termo) return lista.slice(0, 40)
  return lista.filter((c) => (c.nome || '').toUpperCase().includes(termo)).slice(0, 40)
})

async function carregarClientes() {
  ocupado.value = true
  erro.value = ''
  try {
    const r = await api.get('/api/agendamento/clientes')
    clientes.value = r.clientes || []
  } catch (e) {
    // 🚨 Lista vazia e ponte fora do ar são coisas diferentes, e a tela diz
    // qual é o caso: o contrário faria agendar por cima de serviço existente.
    erro.value = e?.message || 'Não deu para consultar as OS no FPSL.'
    clientes.value = []
  } finally {
    ocupado.value = false
  }
}

async function escolherCliente(c) {
  clienteEscolhido.value = c
  osEscolhidas.value = []
  ocupado.value = true
  erro.value = ''
  try {
    const r = await api.get(`/api/agendamento/clientes/${c.harmonit_id}/os`)
    osDoCliente.value = r.os || []
    jaAgendadas.value = r.ja_agendadas || []
    const sugestao = await api.get(
      `/api/agendamento/endereco-sugerido/${c.harmonit_id}`)
    // Sugestão, não preenchimento automático: 🔵 decisão 11 dele é que o
    // operador DIGITA. Endereço herdado em silêncio manda técnico ao lugar
    // errado.
    if (sugestao.endereco && !endereco.value) endereco.value = sugestao.endereco
  } catch (e) {
    erro.value = e?.message || 'Não deu para consultar as OS deste cliente.'
    osDoCliente.value = []
  } finally {
    ocupado.value = false
  }
}

function placasDaOs(os) {
  if (!os.veiculos || !os.veiculos.length) return 'sem placa registrada'
  return os.veiculos.map((v) => v.placa).join(', ')
}

function alternarOs(os) {
  if (jaAgendadas.value.includes(os.numero_os)) return
  const i = osEscolhidas.value.findIndex((o) => o.numero_os === os.numero_os)
  if (i >= 0) osEscolhidas.value.splice(i, 1)
  else osEscolhidas.value.push({
    numero_os: os.numero_os,
    placa: (os.veiculos && os.veiculos[0] && os.veiculos[0].placa) || null,
  })
}

const osMarcada = (os) => osEscolhidas.value.some((o) => o.numero_os === os.numero_os)

const podeAgendar = computed(() =>
  !!quando.value && !!clienteEscolhido.value && osEscolhidas.value.length > 0)

async function gravarAgendamento() {
  ocupado.value = true
  erro.value = ''
  try {
    agendado.value = await api.post('/api/agendamentos', {
      conversa_id: props.conversaId,
      cliente_harmonit_id: clienteEscolhido.value.harmonit_id,
      cliente_nome: clienteEscolhido.value.nome,
      inicio: new Date(quando.value).toISOString(),
      endereco: endereco.value.trim() || null,
      ordens: osEscolhidas.value,
      orcamento_id: orcamentoEmitido.value ? orcamentoEmitido.value.id : null,
    })
    passo.value = 4
  } catch (e) {
    erro.value = e?.message || 'Não deu para gravar o agendamento.'
  } finally {
    ocupado.value = false
  }
}

/* ---------------------------------------------------------------- Confirmar */
const aguardando = ref([])
const marcados = ref([])
const responsavel = ref('')

async function carregarAguardando() {
  if (!props.clienteHarmonitId) return
  ocupado.value = true
  erro.value = ''
  try {
    const r = await api.get(`/api/agendamento/aguardando/${props.clienteHarmonitId}`)
    aguardando.value = r.agendamentos || []
  } catch (e) {
    erro.value = e?.message || 'Não deu para ler o que espera confirmação.'
  } finally {
    ocupado.value = false
  }
}

function alternarMarcado(a) {
  const i = marcados.value.indexOf(a.id)
  if (i >= 0) marcados.value.splice(i, 1)
  else marcados.value.push(a.id)
}

function dataBr(valor) {
  const d = new Date(valor)
  return d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' })
}
function horaBr(valor) {
  return new Date(valor).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
}

/* 🚨 REGRA DE AGRUPAMENTO DECLARADA: mesma DATA e HORA => UMA mensagem só,
   com as placas e as OS somadas. Sem isso o cliente receberia três mensagens
   iguais variando a placa. */
function agrupar(lista) {
  const grupos = new Map()
  for (const a of lista) {
    const chave = `${dataBr(a.inicio)} ${horaBr(a.inicio)}`
    if (!grupos.has(chave)) grupos.set(chave, [])
    grupos.get(chave).push(a)
  }
  return [...grupos.values()]
}

function textos(grupo) {
  const primeiro = grupo[0]
  const placas = [...new Set(grupo.flatMap(
    (a) => (a.ordens || []).map((o) => o.placa).filter(Boolean)))]
  const ordens = [...new Set(grupo.flatMap((a) => (a.ordens || []).map((o) => o.numero_os)))]
  const orcamentos = [...new Set(grupo.map((a) => a.orcamento_numero).filter(Boolean))]
  const placasTexto = placas.length ? placas.join(', ') : 'sem placa registrada'

  const cabecalho = `(SERVIÇO) | ${placasTexto} | ${primeiro.cliente_nome}`
  const corpo = [
    `DATA: ${dataBr(primeiro.inicio)}`,
    `HORÁRIO: ${horaBr(primeiro.inicio)}`,
    `ENDEREÇO: ${primeiro.endereco || '—'}`,
    `TÉCNICO RESPONSÁVEL: ${primeiro.tecnico_nome || '—'}`,
    `VEÍCULO(S) / PLACA(S): ${placasTexto}`,
    `RESPONSÁVEL DO CLIENTE POR ACOMPANHAR O TÉCNICO: ${primeiro.responsavel_cliente || responsavel.value || '—'}`,
  ]
  const doCliente = [cabecalho, '', ...corpo].join('\n')
  const doTecnico = [
    cabecalho, '', ...corpo,
    `OS: ${ordens.join(', ') || '—'}`,
    orcamentos.length ? `ORÇAMENTO ${orcamentos.join(', ')}` : 'ORÇAMENTO —',
  ].join('\n')
  return { doCliente, doTecnico }
}

const mensagens = ref([])

async function confirmar() {
  if (!responsavel.value.trim()) {
    erro.value = 'Diga quem acompanha o técnico — é campo das duas mensagens.'
    return
  }
  ocupado.value = true
  erro.value = ''
  try {
    const confirmados = []
    for (const id of marcados.value) {
      confirmados.push(await api.post(`/api/agendamentos/${id}/confirmar`,
                                      { responsavel_cliente: responsavel.value.trim() }))
    }
    mensagens.value = agrupar(confirmados).map(textos)
  } catch (e) {
    erro.value = e?.message || 'Não deu para confirmar.'
  } finally {
    ocupado.value = false
  }
}

function usar(texto) {
  emit('inserir', texto)
  emit('fechar')
}

onMounted(() => {
  if (ehTecnico.value) {
    api.get('/api/orcamento/catalogo').then((r) => {
      catalogo.value = r.catalogo || []
      proximoNumero.value = r.proximo_numero
      if (!linhas.value.length) linhas.value = [linhaNova()]
    }).catch((e) => { erro.value = e?.message || 'Não deu para ler o catálogo.' })
    carregarClientes()
  }
  if (ehCliente.value) carregarAguardando()
})
</script>

<template>
  <div class="agm__fundo" @click.self="emit('fechar')">
    <section class="agm" role="dialog" aria-label="Agendar serviço">
      <header class="agm__topo">
        <h2 class="agm__titulo">Agendar serviço</h2>
        <button class="botao botao--fantasma botao--icone" type="button"
                aria-label="Fechar" @click="emit('fechar')">
          <i class="bi bi-x-lg" aria-hidden="true"></i>
        </button>
      </header>

      <!-- 🚨 Sem contato o botão EXPLICA, em vez de sumir. -->
      <p v-if="!abas.length" class="aviso aviso--info">
        Esta conversa não tem contato marcado como <b>técnico</b> nem como
        <b>cliente</b>. Marque o tipo do contato na ficha ao lado: o orçamento
        sai no nome do técnico, e a confirmação é do cliente.
      </p>

      <template v-else>
        <nav class="agm__abas">
          <button v-for="a in abas" :key="a.id" type="button"
                  class="agm__aba" :class="{ 'agm__aba--ativa': aba === a.id }"
                  @click="aba = a.id">{{ a.rotulo }}</button>
        </nav>

        <p v-if="erro" class="aviso aviso--erro">{{ erro }}</p>

        <!-- ------------------------------------------------- aba Orçamento -->
        <div v-if="aba === 'orcamento'" class="agm__corpo">
          <p v-if="orcamentoEmitido" class="aviso aviso--ok">
            Orçamento <b>nº {{ orcamentoEmitido.numero }}</b> emitido —
            R$ {{ emReais(orcamentoEmitido.total_centavos) }}. O PDF foi para a
            conversa.
          </p>

          <template v-else>
            <p class="agm__dica">
              Próximo número: <b>{{ proximoNumero ?? '—' }}</b>. O número só é
              gasto quando o PDF é gerado.
            </p>

            <label class="agm__campo">
              <span>OS deste orçamento (números, separados por vírgula)</span>
              <input v-model="osDoOrcamento" class="campo__entrada"
                     placeholder="17015, 17016" />
            </label>

            <table class="tabela agm__itens">
              <thead>
                <tr><th>Serviço</th><th>Preço unit.</th><th>Qtde.</th><th>Un.</th><th>Valor</th><th></th></tr>
              </thead>
              <tbody>
                <tr v-for="(l, i) in linhas" :key="i">
                  <td>
                    <select v-model="l.servico" class="campo__entrada"
                            @change="trocarServico(l)">
                      <option v-for="c in catalogo" :key="c.servico" :value="c.servico">
                        {{ c.servico }}
                      </option>
                    </select>
                  </td>
                  <td><input v-model="l.preco_unit" class="campo__entrada agm__num"
                             inputmode="decimal" placeholder="0,00" /></td>
                  <td><input v-model="l.quantidade" class="campo__entrada agm__num"
                             inputmode="decimal" /></td>
                  <td>{{ l.unidade }}</td>
                  <td>
                    R$ {{ emReais(Math.round(
                      (Number(String(l.preco_unit).replace(',', '.')) || 0) * 100
                      * (Number(String(l.quantidade).replace(',', '.')) || 0))) }}
                  </td>
                  <td>
                    <button class="botao botao--fantasma botao--icone" type="button"
                            aria-label="Tirar linha" @click="linhas.splice(i, 1)">
                      <i class="bi bi-trash" aria-hidden="true"></i>
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>

            <div class="agm__linha">
              <button class="botao botao--contorno" type="button"
                      @click="linhas.push(linhaNova())">Mais uma linha</button>
              <b class="agm__total">Total: R$ {{ emReais(totalCentavos) }}</b>
            </div>

            <div class="agm__acoes">
              <button class="botao botao--primario" type="button"
                      :disabled="ocupado || !podeEmitir" @click="emitirOrcamento">
                {{ ocupado ? 'Gerando…' : 'Gerar e anexar o PDF' }}
              </button>
            </div>
          </template>
        </div>

        <!-- --------------------------------------------------- aba Agendar -->
        <div v-else-if="aba === 'agendar'" class="agm__corpo">
          <p v-if="agendado" class="aviso aviso--ok">
            Agendado para <b>{{ dataBr(agendado.inicio) }} às {{ horaBr(agendado.inicio) }}</b>,
            esperando a confirmação do cliente. Abra a conversa do cliente para
            confirmar e enviar os avisos.
          </p>

          <template v-else>
            <ol class="agm__passos">
              <li :class="{ 'agm__passo--ativo': passo === 1 }">1. Data e hora</li>
              <li :class="{ 'agm__passo--ativo': passo === 2 }">2. Cliente e OS</li>
              <li :class="{ 'agm__passo--ativo': passo === 3 }">3. Resumo e endereço</li>
            </ol>

            <div v-if="passo === 1">
              <label class="agm__campo">
                <span>Quando</span>
                <input v-model="quando" type="datetime-local" class="campo__entrada" />
              </label>
              <div class="agm__acoes">
                <button class="botao botao--primario" type="button"
                        :disabled="!quando" @click="passo = 2">Continuar</button>
              </div>
            </div>

            <div v-else-if="passo === 2">
              <p class="agm__dica">
                Só clientes com <b>OS em aberto nos últimos 6 meses</b>.
              </p>
              <label class="agm__campo">
                <span>Cliente</span>
                <input v-model="buscaCliente" class="campo__entrada"
                       placeholder="Buscar pelo nome" />
              </label>

              <ul v-if="!clienteEscolhido" class="agm__lista">
                <li v-for="c in clientesFiltrados" :key="c.harmonit_id">
                  <button type="button" class="agm__item" @click="escolherCliente(c)">
                    <span>{{ c.nome }}</span>
                    <small>{{ c.quantas_os }} OS</small>
                  </button>
                </li>
                <li v-if="!clientesFiltrados.length && !ocupado" class="agm__vazio">
                  Nenhum cliente com OS em aberto bate com esta busca.
                </li>
              </ul>

              <template v-else>
                <p class="agm__dica">
                  <b>{{ clienteEscolhido.nome }}</b>
                  <button class="botao botao--fantasma" type="button"
                          @click="clienteEscolhido = null">trocar</button>
                </p>
                <ul class="agm__lista">
                  <li v-for="os in osDoCliente" :key="os.numero_os">
                    <button type="button" class="agm__item"
                            :class="{ 'agm__item--marcado': osMarcada(os),
                                      'agm__item--preso': jaAgendadas.includes(os.numero_os) }"
                            :disabled="jaAgendadas.includes(os.numero_os)"
                            @click="alternarOs(os)">
                      <span>OS {{ os.numero_os }} — {{ placasDaOs(os) }}</span>
                      <small>
                        {{ os.sem_situacao ? 'sem situação' : os.status_str }}
                        <template v-if="jaAgendadas.includes(os.numero_os)">
                          · já agendada
                        </template>
                      </small>
                    </button>
                  </li>
                  <li v-if="!osDoCliente.length && !ocupado" class="agm__vazio">
                    Este cliente não tem OS em aberto no período.
                  </li>
                </ul>
              </template>

              <div class="agm__acoes">
                <button class="botao botao--contorno" type="button" @click="passo = 1">Voltar</button>
                <button class="botao botao--primario" type="button"
                        :disabled="!osEscolhidas.length" @click="passo = 3">Continuar</button>
              </div>
            </div>

            <div v-else-if="passo === 3">
              <p class="agm__dica">
                <b>{{ clienteEscolhido?.nome }}</b> ·
                {{ osEscolhidas.length }} OS ·
                {{ quando ? `${dataBr(quando)} às ${horaBr(quando)}` : '' }} ·
                técnico {{ contatoNome || '—' }}
              </p>
              <label class="agm__campo">
                <span>Endereço (sugerido com o último usado para este cliente)</span>
                <input v-model="endereco" class="campo__entrada"
                       placeholder="Rua, número, bairro, cidade" />
              </label>
              <p v-if="orcamentoEmitido" class="agm__dica">
                Orçamento nº {{ orcamentoEmitido.numero }} vai junto.
              </p>
              <div class="agm__acoes">
                <button class="botao botao--contorno" type="button" @click="passo = 2">Voltar</button>
                <button class="botao botao--primario" type="button"
                        :disabled="ocupado || !podeAgendar" @click="gravarAgendamento">
                  {{ ocupado ? 'Gravando…' : 'Agendar' }}
                </button>
              </div>
            </div>
          </template>
        </div>

        <!-- ------------------------------------------------- aba Confirmar -->
        <div v-else-if="aba === 'confirmar'" class="agm__corpo">
          <p v-if="!clienteHarmonitId" class="aviso aviso--info">
            Esta conversa não está ligada a um cliente com cadastro no Harmonit,
            então não há agendamento para confirmar aqui.
          </p>

          <template v-else-if="!mensagens.length">
            <p class="agm__dica">Marque o que o cliente confirmou:</p>
            <ul class="agm__lista">
              <li v-for="a in aguardando" :key="a.id">
                <button type="button" class="agm__item"
                        :class="{ 'agm__item--marcado': marcados.includes(a.id) }"
                        @click="alternarMarcado(a)">
                  <span>
                    {{ dataBr(a.inicio) }} às {{ horaBr(a.inicio) }} —
                    OS {{ (a.ordens || []).map((o) => o.numero_os).join(', ') }}
                  </span>
                  <small>{{ a.tecnico_nome || 'sem técnico' }}</small>
                </button>
              </li>
              <li v-if="!aguardando.length && !ocupado" class="agm__vazio">
                Nada esperando confirmação para este cliente.
              </li>
            </ul>

            <label class="agm__campo">
              <span>Quem acompanha o técnico</span>
              <input v-model="responsavel" class="campo__entrada"
                     placeholder="Nome de quem recebe o técnico" />
            </label>

            <div class="agm__acoes">
              <button class="botao botao--primario" type="button"
                      :disabled="ocupado || !marcados.length" @click="confirmar">
                {{ ocupado ? 'Confirmando…' : 'Confirmar e escrever os avisos' }}
              </button>
            </div>
          </template>

          <template v-else>
            <p class="aviso aviso--ok">
              Confirmado. Os avisos abaixo ficam <b>prontos para você revisar e
              enviar</b> — nada sai daqui sozinho.
            </p>
            <div v-for="(m, i) in mensagens" :key="i" class="agm__mensagem">
              <h3>Para o cliente</h3>
              <pre>{{ m.doCliente }}</pre>
              <button class="botao botao--contorno" type="button"
                      @click="usar(m.doCliente)">Escrever no compositor</button>
              <h3>Para o técnico</h3>
              <pre>{{ m.doTecnico }}</pre>
              <button class="botao botao--contorno" type="button"
                      @click="usar(m.doTecnico)">Escrever no compositor</button>
            </div>
          </template>
        </div>
      </template>
    </section>
  </div>
</template>

<style scoped>
.agm__fundo {
  position: fixed;
  inset: 0;
  z-index: 60;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--e-3);
  background: rgba(15, 23, 42, .55);
}
.agm {
  display: flex;
  flex-direction: column;
  gap: var(--e-3);
  width: min(760px, 100%);
  max-height: 90vh;
  overflow-y: auto;
  padding: var(--e-4);
  border-radius: var(--r-lg);
  background: var(--superficie);
  color: var(--texto);
}
.agm__topo { display: flex; align-items: center; justify-content: space-between; }
.agm__titulo { margin: 0; font-size: var(--txt-lg); }
.agm__abas { display: flex; gap: var(--e-2); border-bottom: var(--borda-fina) solid var(--borda); }
.agm__aba {
  padding: var(--e-2) var(--e-3);
  border: 0;
  border-bottom: 2px solid transparent;
  background: transparent;
  color: var(--texto-fraco);
  font-size: var(--txt-sm);
  font-weight: var(--peso-forte);
  cursor: pointer;
}
.agm__aba--ativa { color: var(--acento); border-bottom-color: var(--acento); }
.agm__corpo { display: flex; flex-direction: column; gap: var(--e-3); }
.agm__campo { display: flex; flex-direction: column; gap: var(--e-1); font-size: var(--txt-sm); }
/* 16px: abaixo disso o iOS dá zoom ao focar (padrão dos quatro painéis). */
.agm__campo .campo__entrada { font-size: 16px; }
.agm__num { width: 110px; font-size: 16px; }
.agm__dica { margin: 0; color: var(--texto-fraco); font-size: var(--txt-sm); }
.agm__linha { display: flex; align-items: center; justify-content: space-between; gap: var(--e-3); }
.agm__total { font-size: var(--txt-md); }
.agm__acoes { display: flex; gap: var(--e-2); justify-content: flex-end; flex-wrap: wrap; }
.agm__passos { display: flex; gap: var(--e-3); margin: 0; padding: 0; list-style: none; font-size: var(--txt-sm); color: var(--texto-fraco); }
.agm__passo--ativo { color: var(--acento); font-weight: var(--peso-forte); }
.agm__lista { list-style: none; margin: 0; padding: 0; max-height: 280px; overflow-y: auto; display: flex; flex-direction: column; gap: 4px; }
.agm__item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--e-2);
  width: 100%;
  padding: var(--e-2) var(--e-3);
  border: var(--borda-fina) solid var(--borda);
  border-radius: var(--r-sm);
  background: var(--superficie-2);
  color: inherit;
  text-align: left;
  cursor: pointer;
}
.agm__item--marcado { border-color: var(--acento); background: var(--acento-suave, var(--superficie-3)); }
.agm__item--preso { opacity: .55; cursor: not-allowed; }
.agm__item small { color: var(--texto-fraco); }
.agm__vazio { padding: var(--e-3); color: var(--texto-fraco); font-size: var(--txt-sm); }
.agm__mensagem { display: flex; flex-direction: column; gap: var(--e-2); }
.agm__mensagem h3 { margin: 0; font-size: var(--txt-sm); }
.agm__mensagem pre {
  margin: 0;
  padding: var(--e-3);
  border-radius: var(--r-sm);
  background: var(--superficie-2);
  font-family: inherit;
  font-size: var(--txt-sm);
  white-space: pre-wrap;
}
</style>
