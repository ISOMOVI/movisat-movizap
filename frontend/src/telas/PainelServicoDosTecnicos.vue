<script setup>
/* ============================================================================
   SERVIÇO DOS TÉCNICOS — a aba 2 do Financeiro (PNL_1.6), 18/11
   ----------------------------------------------------------------------------
   🔵 Pedido dele: *"Nova aba2 no painel do Financeiro Movizap: 'Serviço dos
   técnicos'"*, com cinco colunas — Movimentação, Preparação, Validação, Procfy
   e Pagamento enviado.

   🚨 TELA PRÓPRIA, E NÃO O `PainelAba.vue`: as cinco colunas **não são etapas
   nossas nem situações do ERP** — são estados do *artefato de pagamento*, que
   vive no FPSL. O `quadro_da_aba` desenharia cinco colunas vazias para sempre.

   🚨 A UNIDADE É O ARTEFATO, e é o que faz as colunas se encaixarem: um serviço
   pago a um técnico numa OS, com **Orçamento · OS · TERMO · valor** — a ordem
   que ele escreveu. O artefato atravessa as cinco colunas; o CARD não: o da
   coluna 1 é permanente por técnico (🔵 decisão dele) e os das outras são
   lotes. É por isso que *"os removidos voltam para o card da primeira
   coluna"* funciona de qualquer etapa.

   📏 O que ela mostra no primeiro dia, medido contra o cache de 633 OS: **79
   artefatos** em **9 cards** — Franck com 40 (R$ 3.430,00 + R$ 933,10) e um
   card *"sem técnico identificado"* com **21** somando **R$ 2.581,90** sem
   destinatário. 🚨 Esses 21 são o funil que ele mandou consertar em 11/11
   (70 → 16 → 8 OS): aqui eles aparecem em vez de serem descartados.

   ⚠️ **COR NUNCA SOZINHA.** Todo estado do semáforo carrega ícone e texto:
   quem não distingue a cor tem de conseguer ler qual é qual.
   ============================================================================ */
import { computed, onMounted, ref } from 'vue'
import { api, ErroDeApi } from '../api/cliente.js'

const BASE = '/api/paineis/servico-dos-tecnicos'

const quadro = ref(null)
const carregando = ref(false)
const erro = ref('')
const aviso = ref('')
const marcados = ref(new Set())
/* 🔵 *"ter o filtro de datas sempre dentro do card coluna 1 (...) por exemplo,
   só quero fechar de 16-18/11/26 filtro isso e flego"*.
   ⚠️ A data é a DO SERVIÇO (a previsão da OS), não a da coleta: é ela que vai
   ao Procfy como competência. */
const de = ref('')
const ate = ref('')

/* O modal de conferir, da coluna 2 — 🔵 *"confirmar 1 a 1 na tela modal"*. */
const conferindo = ref(null)
const devolvendo = ref(null)
const justificativa = ref('')

const TITULOS = {
  movimentacao: 'Movimentação',
  preparacao: 'Preparação',
  validacao: 'Validação',
  procfy: 'Procfy',
  enviado: 'Pagamento enviado',
}

/* 🚨 Ícone e texto por cor, porque cor sozinha não informa. */
const SEMAFORO = {
  verde: { icone: 'bi-check-circle-fill', texto: 'conforme' },
  amarelo: { icone: 'bi-exclamation-circle-fill', texto: 'divergência ou ausência' },
  laranja: { icone: 'bi-arrow-counterclockwise', texto: 'devolvido' },
  vermelho: { icone: 'bi-x-circle-fill', texto: 'a pagar maior que o recibo' },
}

async function carregar() {
  carregando.value = true
  erro.value = ''
  try {
    quadro.value = await api.get(BASE)
  } catch (e) {
    /* 🚨 QUADRO VAZIO NUNCA: vazio silencioso faria concluir que não há
       pagamento a preparar, justo quando há. */
    erro.value = e instanceof ErroDeApi ? e.message
      : 'Não consegui ler o quadro de pagamentos.'
  } finally {
    carregando.value = false
  }
}

function dentroDoFiltro(artefato) {
  if (!de.value && !ate.value) return true
  const iso = isoDaData(artefato.data_os)
  if (!iso) return false
  if (de.value && iso < de.value) return false
  if (ate.value && iso > ate.value) return false
  return true
}

function isoDaData(bruto) {
  /* ⚠️ A `data_previsao` do cache vem `dd/mm/aaaa HH:MM:SS` — o JavaScript não
     sabe ler isso (`new Date(...)` = Invalid Date), e foi essa armadilha que
     deixou o "há 2 dias" sumido em 10 de 10 cards em 05/11. */
  if (!bruto) return ''
  const m = String(bruto).match(/^(\d{2})\/(\d{2})\/(\d{4})/)
  return m ? `${m[3]}-${m[2]}-${m[1]}` : ''
}

function artefatosVisiveis(card) {
  return (card.artefatos || []).filter(dentroDoFiltro)
}

function alternar(id) {
  const novo = new Set(marcados.value)
  if (novo.has(id)) novo.delete(id)
  else novo.add(id)
  marcados.value = novo
}

function marcarTodosDoCard(card) {
  const novo = new Set(marcados.value)
  for (const a of artefatosVisiveis(card)) novo.add(a.id)
  marcados.value = novo
}

const quantosMarcados = computed(() => marcados.value.size)

function moeda(v) {
  return (Number(v) || 0).toLocaleString('pt-BR',
    { style: 'currency', currency: 'BRL' })
}

function totalDe(card) {
  return artefatosVisiveis(card).reduce(
    (s, a) => s + (Number(a.valor_pagamento) || 0) + (Number(a.valor_km) || 0), 0)
}

async function chamar(caminho, corpo, metodo = 'post') {
  erro.value = ''
  aviso.value = ''
  try {
    const r = metodo === 'get'
      ? await api.get(BASE + caminho)
      : await api.post(BASE + caminho, corpo || {})
    /* 🚨 RECUSA É RESPOSTA, não exceção: o motivo vem por extenso e aparece na
       tela. 🔵 *"os motivos de recusa deve aparecer descritos ao inves de erro
       generico, para que me tragam o problema ja cientes"*. */
    if (r && r.ok === false) {
      erro.value = r.motivo || 'A ação foi recusada e não veio o motivo.'
      return null
    }
    return r
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui completar.'
    return null
  }
}

async function varrer() {
  const r = await chamar('/varrer')
  if (r) {
    aviso.value = `Varredura: ${r.novos} artefato(s) novo(s), `
      + `${r.ja_existiam} que já existiam, ${r.sem_tecnico} sem técnico.`
    await carregar()
  }
}

async function preparar() {
  const r = await chamar('/preparar', { artefatos: [...marcados.value] })
  if (!r) return
  marcados.value = new Set()
  if (r.recusados && r.recusados.length) {
    /* ⚠️ O QUE FICOU DE FORA É DITO, não descartado em silêncio: são os sem
       técnico, e eles existem para o dinheiro não sair de vista. */
    aviso.value = `${r.preparados} preparado(s). Ficaram de fora: `
      + r.recusados.map((x) => `OS ${x.numero_os} (${x.porque})`).join('; ')
  } else {
    aviso.value = `${r.preparados} artefato(s) em preparação.`
  }
  await carregar()
}

async function abrirConferencia(card) {
  const linhas = []
  for (const a of card.artefatos || []) {
    const r = await chamar(`/conferir/${a.id}`)
    if (r) linhas.push({ ...a, ...r })
  }
  conferindo.value = { card, linhas }
}

async function ciente(linha) {
  if (await chamar(`/ciente/${linha.id}`)) {
    linha.ciente_em = new Date().toISOString()
  }
}

function pedirDevolucao(linha) {
  devolvendo.value = linha
  justificativa.value = ''
}

async function devolver() {
  const alvo = devolvendo.value
  if (!alvo) return
  const r = await chamar('/devolver', {
    artefato_id: alvo.id, justificativa: justificativa.value,
  })
  if (r) {
    devolvendo.value = null
    conferindo.value = null
    aviso.value = `OS ${alvo.numero_os} voltou para a Movimentação.`
    await carregar()
  }
}

async function auditar(card) {
  const r = await chamar(`/auditar/${card.lote_id}`)
  if (r) {
    conferindo.value = null
    aviso.value = `${r.avancaram} avançaram; ${r.ficaram} ficaram sem ciente.`
    await carregar()
  }
}

async function revalidar(card) {
  const r = await chamar(`/revalidar/${card.lote_id}`)
  if (r) {
    aviso.value = `${r.revalidados} artefato(s) relidos.`
    await carregar()
  }
}

async function montarArquivo(card) {
  const r = await chamar(`/montar-arquivo/${card.lote_id}`)
  if (r) {
    aviso.value = `Arquivo montado: ${r.avancaram} artefato(s)`
      + (r.ficaram ? `, ${r.ficaram} ficaram sem comprovante.` : '.')
    await carregar()
  }
}

function baixar(card) {
  /* ⚠️ `window.open` e não `fetch`: o navegador é quem salva o arquivo, e o
     cabeçalho `Content-Disposition` é o que dá o nome. */
  window.open(`${BASE}/arquivo/${card.lote_id}`, '_blank')
}

async function enviar(card) {
  const r = await chamar(`/enviar/${card.lote_id}`)
  if (r) {
    aviso.value = 'Lote marcado como pagamento enviado.'
    await carregar()
  }
}

onMounted(carregar)
</script>

<template>
  <section class="painel">
    <header class="painel__topo">
      <h1 class="painel__titulo">Serviço dos técnicos</h1>
      <div class="painel__acoes">
        <button class="botao" type="button" @click="varrer">
          <i class="bi bi-arrow-repeat" aria-hidden="true"></i>
          Buscar serviços
        </button>
      </div>
    </header>

    <p v-if="erro" class="aviso aviso--erro" role="alert">{{ erro }}</p>
    <p v-if="aviso" class="aviso" role="status">{{ aviso }}</p>
    <p v-if="carregando && !quadro" class="nota">Abrindo…</p>

    <div v-if="quadro" class="quadro">
      <div v-for="coluna in quadro.colunas" :key="coluna.chave" class="coluna">
        <h2 class="coluna__titulo">
          {{ TITULOS[coluna.chave] || coluna.chave }}
          <span class="coluna__conta">{{ coluna.total }}</span>
        </h2>

        <!-- ================= COLUNA 1 — Movimentação ================= -->
        <template v-if="coluna.chave === 'movimentacao'">
          <article v-for="card in coluna.cards" :key="card.tecnico_id || 0"
                   class="card">
            <h3 class="card__tecnico">
              {{ card.tecnico_nome || 'técnico ' + card.tecnico_id }}
            </h3>

            <!-- 🔵 O FILTRO DE DATAS DENTRO DO CARD: *"só quero fechar de
                 16-18/11/26 filtro isso e flego"*. ⚠️ A data é a do SERVIÇO. -->
            <div class="card__filtro">
              <label>de <input v-model="de" type="date" /></label>
              <label>até <input v-model="ate" type="date" /></label>
            </div>

            <ul class="artefatos">
              <li v-for="a in artefatosVisiveis(card)" :key="a.id"
                  class="artefato">
                <label class="artefato__marca">
                  <input type="checkbox" :checked="marcados.has(a.id)"
                         :disabled="!card.pode_preparar"
                         @change="alternar(a.id)" />
                  <!-- 🔵 A ordem é a dele: Orçamento — OS — TERMO. -->
                  <span v-if="a.orcamento_numero" class="artefato__orcamento">
                    Orç {{ a.orcamento_numero }}
                  </span>
                  <span v-else class="artefato__orcamento artefato__orcamento--sem">
                    <i class="bi bi-exclamation-circle" aria-hidden="true"></i>
                    sem orçamento
                  </span>
                  <span class="artefato__os">OS {{ a.numero_os }}</span>
                  <span v-if="a.termo" class="artefato__termo">
                    TERMO {{ a.termo }}
                  </span>
                  <span class="artefato__valor">
                    {{ moeda((a.valor_pagamento || 0) + (a.valor_km || 0)) }}
                  </span>
                </label>
                <!-- 🔵 O devolvido é LARANJA e a justificativa fica à vista:
                     laranja sem motivo é cor sem informação. -->
                <p v-if="a.semaforo === 'laranja'" class="artefato__devolvido">
                  <i class="bi bi-arrow-counterclockwise" aria-hidden="true"></i>
                  devolvido: {{ a.justificativa }}
                </p>
              </li>
            </ul>

            <p class="card__total">
              {{ artefatosVisiveis(card).length }} artefato(s) ·
              {{ moeda(totalDe(card)) }}
            </p>

            <!-- 🚨 O card dos SEM TÉCNICO não prepara, e DIZ por quê: sem
                 técnico não há a quem pagar. Ele existe para o dinheiro não
                 sair de vista. -->
            <p v-if="!card.pode_preparar" class="card__trava">
              <i class="bi bi-info-circle" aria-hidden="true"></i>
              Estas OS têm valor de pagamento e nenhum técnico identificado na
              linha. Não há a quem pagar até alguém vincular o técnico na OS.
            </p>
            <div v-else class="card__acoes">
              <button class="botao botao--fraco" type="button"
                      @click="marcarTodosDoCard(card)">Marcar todos</button>
              <button class="botao" type="button"
                      :disabled="!quantosMarcados" @click="preparar">
                Preparar os marcados ({{ quantosMarcados }})
              </button>
            </div>
          </article>
        </template>

        <!-- ============ COLUNAS 2 a 5 — os lotes por técnico ============ -->
        <template v-else>
          <article v-for="card in coluna.cards" :key="card.lote_id"
                   class="card">
            <h3 class="card__tecnico">
              {{ card.tecnico_nome || 'técnico ' + card.tecnico_id }}
            </h3>
            <ul class="artefatos">
              <li v-for="a in card.artefatos" :key="a.id" class="artefato">
                <span class="artefato__os">OS {{ a.numero_os }}</span>
                <span class="artefato__valor">
                  {{ moeda((a.valor_pagamento || 0) + (a.valor_km || 0)) }}
                </span>
                <!-- 🚨 Ícone E texto: cor sozinha não é portadora. -->
                <span v-if="a.semaforo" class="selo"
                      :class="'selo--' + a.semaforo">
                  <i :class="'bi ' + SEMAFORO[a.semaforo].icone"
                     aria-hidden="true"></i>
                  {{ SEMAFORO[a.semaforo].texto }}
                </span>
                <span v-if="a.datascope_form_state" class="selo">
                  DataScope: {{ a.datascope_form_state }}
                </span>
              </li>
            </ul>
            <div class="card__acoes">
              <!-- 🔵 *"todos os cards tem botão de 'atualizar'"*. -->
              <button class="botao botao--fraco" type="button"
                      @click="revalidar(card)">Atualizar</button>
              <button v-if="coluna.chave === 'preparacao'" class="botao"
                      type="button" @click="abrirConferencia(card)">
                Conferir e auditar
              </button>
              <button v-if="coluna.chave === 'validacao'" class="botao"
                      type="button" @click="montarArquivo(card)">
                Montar arquivo
              </button>
              <template v-if="coluna.chave === 'procfy'">
                <button class="botao" type="button" @click="baixar(card)">
                  Baixar o arquivo
                </button>
                <button class="botao botao--fraco" type="button"
                        @click="enviar(card)">Marcar como enviado</button>
              </template>
            </div>
          </article>
        </template>

        <p v-if="!coluna.total" class="nota pequeno">Vazia.</p>
      </div>
    </div>

    <!-- 🔵 O MODAL DE CONFERIR, da coluna 2: *"exibir para o operador
         confirmar 1 a 1 na tela modal que abrir"*. -->
    <div v-if="conferindo" class="modal" role="dialog" aria-modal="true">
      <div class="modal__caixa">
        <h2>Conferir a situação, uma a uma</h2>
        <ul class="conferencia">
          <li v-for="l in conferindo.linhas" :key="l.id">
            <span class="artefato__os">OS {{ l.numero_os }}</span>
            <span class="selo" :class="l.libera ? 'selo--verde' : 'selo--amarelo'">
              <i :class="'bi ' + (l.libera ? 'bi-check-circle-fill'
                                           : 'bi-exclamation-circle-fill')"
                 aria-hidden="true"></i>
              {{ l.motivo }}
            </span>
            <span v-if="l.etapa_nossa" class="selo">
              está em Serviço Realizado (etapa nossa)
            </span>
            <button v-if="!l.ciente_em" class="botao botao--fraco" type="button"
                    @click="ciente(l)">Ciente</button>
            <span v-else class="selo selo--verde">
              <i class="bi bi-check2" aria-hidden="true"></i> ciente
            </span>
            <button class="botao botao--fraco" type="button"
                    @click="pedirDevolucao(l)">Remover</button>
          </li>
        </ul>
        <div class="modal__acoes">
          <button class="botao botao--fraco" type="button"
                  @click="conferindo = null">Fechar</button>
          <!-- 🔵 *"irá mover o card somente com os cientes de situação e não
               negados para a próxima coluna"*. -->
          <button class="botao" type="button"
                  @click="auditar(conferindo.card)">Auditar</button>
        </div>
      </div>
    </div>

    <!-- 🔵 *"abrindo um campo de justificativa com campo de texto pequeno"*. -->
    <div v-if="devolvendo" class="modal" role="dialog" aria-modal="true">
      <div class="modal__caixa modal__caixa--curta">
        <h2>Por que está removendo?</h2>
        <p class="nota pequeno">
          A OS {{ devolvendo.numero_os }} volta para a Movimentação em laranja,
          com esta justificativa à vista.
        </p>
        <input v-model="justificativa" class="campo" maxlength="400"
               placeholder="ex.: OS ainda em Agendar serviço" />
        <div class="modal__acoes">
          <button class="botao botao--fraco" type="button"
                  @click="devolvendo = null">Cancelar</button>
          <button class="botao" type="button" :disabled="!justificativa.trim()"
                  @click="devolver">Remover</button>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.painel { display: flex; flex-direction: column; gap: var(--e-4); }
.painel__topo {
  display: flex; flex-wrap: wrap; gap: var(--e-3);
  align-items: center; justify-content: space-between;
}
.painel__titulo { margin: 0; font-size: var(--txt-lg); }
.quadro { display: flex; gap: var(--e-3); overflow-x: auto; }
.coluna {
  flex: 0 0 320px; display: flex; flex-direction: column; gap: var(--e-2);
}
.coluna__titulo {
  margin: 0; font-size: var(--txt-sm); display: flex;
  align-items: center; gap: var(--e-2);
}
.coluna__conta {
  padding: 0 var(--e-2); border-radius: var(--r-full);
  background: var(--superficie-2); font-size: var(--txt-xs);
}
.card {
  display: flex; flex-direction: column; gap: var(--e-2);
  padding: var(--e-3);
  border: var(--borda-fina) solid var(--borda); border-radius: var(--r-2);
  background: var(--superficie);
}
.card__tecnico { margin: 0; font-size: var(--txt-sm); }
.card__filtro { display: flex; gap: var(--e-2); font-size: var(--txt-xs); }
.card__total { margin: 0; font-size: var(--txt-xs); color: var(--texto-fraco); }
.card__trava {
  margin: 0; font-size: var(--txt-xs); color: var(--texto-fraco);
  display: flex; gap: var(--e-1);
}
.card__acoes { display: flex; flex-wrap: wrap; gap: var(--e-2); }
.artefatos { list-style: none; margin: 0; padding: 0;
             display: flex; flex-direction: column; gap: var(--e-1); }
.artefato { display: flex; flex-direction: column; gap: 2px;
            font-size: var(--txt-xs); }
.artefato__marca { display: flex; flex-wrap: wrap; align-items: center;
                   gap: var(--e-1); cursor: pointer; }
.artefato__os { font-weight: var(--peso-forte); color: var(--acento); }
.artefato__termo, .artefato__orcamento { color: var(--texto-fraco); }
.artefato__orcamento--sem { color: var(--aviso); }
.artefato__valor { margin-left: auto; font-weight: var(--peso-forte); }
.artefato__devolvido { margin: 0; color: var(--aviso); display: flex;
                       gap: var(--e-1); }

/* 🚨 CLASSE PRÓPRIA, NUNCA `.pilula`: ela é `scoped` por componente e não
   existe em `estilo/*.css` -- o selo nasceria sem estilo, e o jsdom, que não
   faz layout, não pegaria. É a lição de 05–11/11, e ela custou uma tela. */
.selo {
  display: inline-flex; align-items: center; gap: var(--e-1);
  padding: 1px var(--e-2);
  border: var(--borda-fina) solid var(--borda);
  border-radius: var(--r-full);
  font-size: var(--txt-xs); color: var(--texto-fraco);
}
.selo--verde { border-color: var(--sucesso); color: var(--sucesso); }
.selo--amarelo { border-color: var(--aviso); color: var(--aviso); }
.selo--laranja { border-color: var(--aviso); color: var(--aviso); }
.selo--vermelho { border-color: var(--perigo); color: var(--perigo); }

.modal {
  position: fixed; inset: 0; display: grid; place-items: center;
  background: rgba(0, 0, 0, .45); z-index: var(--z-modal, 50);
}
.modal__caixa {
  width: min(760px, 92vw); max-height: 86vh; overflow: auto;
  padding: var(--e-4); border-radius: var(--r-3);
  background: var(--superficie); display: flex; flex-direction: column;
  gap: var(--e-3);
}
.modal__caixa--curta { width: min(420px, 92vw); }
.modal__acoes { display: flex; justify-content: flex-end; gap: var(--e-2); }
.conferencia { list-style: none; margin: 0; padding: 0;
               display: flex; flex-direction: column; gap: var(--e-2); }
.conferencia li { display: flex; flex-wrap: wrap; align-items: center;
                  gap: var(--e-2); font-size: var(--txt-xs); }
.nota { color: var(--texto-fraco); }
.pequeno { font-size: var(--txt-xs); }
</style>
