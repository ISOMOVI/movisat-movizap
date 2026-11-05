<script setup>
/* ============================================================================
   PAINEL DE UMA ABA DE PIPELINE — Pós-venda, e os próximos
   ----------------------------------------------------------------------------
   🔵 Ele, 05/11: *"a aba 'Operação' do Movizap é a mesma lógica para os demais:
   Pós-venda - Abas - Permissão por abas / Aba 1: Treinamentos / Solicitação:
   Agenda* / Treinamento 1: / Treinamento 2: / Entregue: / Aba 2: Pós-venda"*, e
   depois as colunas da segunda: *"Solicitação: Testes: Realizar Pós-venda:
   Pós-venda Realizado:"*.

   🚨 TODAS AS COLUNAS DAQUI SÃO NOSSAS — nenhuma existe no Harmonit, e por isso
   esta tela **nunca** fala com o ERP. É a diferença inteira em relação ao
   painel da Operação, cujas 17 colunas são situações da OS: lá mover escreve
   `situacaoId` no ERP; aqui, só no nosso banco.

   🚨 UMA TELA, DUAS ROTAS: a `PNL_1.2` e a `PNL_1.3` são a MESMA tela com
   `codigo` diferente, porque as colunas vivem no banco (`pipeline_etapa`,
   migração 094) e não no código. Uma tela por aba seria copiar isto por aba.
   ⚠️ Mas a ENTRADA no `telas.py` é uma por aba, e isso não é redundância: a
   permissão é campo da entrada, e ele quer *"a Erika, apenas a aba 3"*.

   🔴 OS CARDS NASCEM VAZIOS, E É ESTADO, NÃO DEFEITO: a origem deles ficou em
   aberto por decisão dele (*"deixe em aberto, depois veremos"*). A tela diz
   isso — quadro vazio que não explica por que está vazio é `M12`.
   ============================================================================ */
import { computed, onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { api, ErroDeApi } from '../api/cliente.js'
import DialogoDeChamado from '../componentes/DialogoDeChamado.vue'
import { codigosPermitidos } from '../estado/sessao.js'

const rota = useRoute()
const quadro = ref(null)
const carregando = ref(true)
const erro = ref('')
const abertas = ref({})
const cardAberto = ref(null)
const erroDeMover = ref('')
const arrastando = ref(null)
const colunaAlvo = ref(null)
let arrastouAgora = 0
const focoAnterior = ref(null)

/* ⚠️ O código da aba vem da ROTA, não de um `prop`: é o que permite uma tela
   servir as duas (e as do Financeiro, quando ele der as colunas). */
const codigo = computed(() => rota.meta?.aba || '')

const total = computed(() => quadro.value?.total ?? 0)

/* 🔵 AS ABAS DENTRO DA TELA -- correcao dele em 05/11: *"so aba principal
   no menu. As demais sao dentro dela ja"*.

   ⚠️ A LISTA SAI DA PERMISSAO, e nao de uma constante solta: quem nao tem
   a `PNL_1.3` nao ve a segunda aba. A fonte e o `codigosPermitidos` da
   sessao -- a mesma que a guarda de rota usa, porque duas fontes
   divergiriam no dia em que ele conceder uma aba a alguem.

   🚨 E ELAS SAO DECLARADAS AQUI, e nao lidas do servidor, de proposito: o
   nome e a ORDEM das abas sao dele (*"Aba 1: Treinamentos (...) Aba 2:
   Pos-venda"*), e o `telas.py` ja e a fonte de quem pode abrir cada uma. */
const AS_ABAS = [
  { codigo: 'PNL_1.2', titulo: 'Treinamentos', rota: '/paineis/pos-venda' },
  { codigo: 'PNL_1.3', titulo: 'Pós-venda',
    rota: '/paineis/pos-venda/realizado' },
]
const abasVisiveis = computed(
  () => AS_ABAS.filter((a) => codigosPermitidos.value.has(a.codigo)),
)

function dataCurta(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  const mesmoAno = d.getFullYear() === new Date().getFullYear()
  return d.toLocaleDateString('pt-BR', mesmoAno
    ? { day: '2-digit', month: '2-digit' }
    : { day: '2-digit', month: '2-digit', year: '2-digit' })
}

/* A cor é da COLUNA, e não do card: o card já está nela, e dentro dela todos
   teriam a mesma cor — foi a régua que o painel da Operação adotou em 05/11. */
const CORES = ['#2563EB', '#7C3AED', '#0891B2', '#059669', '#D97706', '#DB2777']
const corDaEtapa = (i) => CORES[i % CORES.length]

async function carregar() {
  carregando.value = true
  erro.value = ''
  try {
    quadro.value = await api.get(`/api/paineis/aba/${codigo.value}`)
    for (const coluna of quadro.value.colunas) {
      if (abertas.value[coluna.chave] === undefined) {
        abertas.value[coluna.chave] = true
      }
    }
    /* 🚨 O CARD ABERTO É RECARREGADO DO QUADRO NOVO, e não mantido: o
       `cardAberto` ficaria apontando para um retrato velho — com a etapa
       antiga escrita na tela. É o mesmo cuidado do `moverDoModal` da
       Operação. */
    if (cardAberto.value) {
      const vivo = quadro.value.colunas
        .flatMap((c) => c.cards)
        .find((c) => c.id === cardAberto.value.id)
      cardAberto.value = vivo || null
    }
  } catch (e) {
    erro.value = e instanceof ErroDeApi
      ? e.message : 'Não deu para abrir este painel agora.'
  } finally {
    carregando.value = false
  }
}

onMounted(carregar)
/* A mesma tela serve as duas abas, então trocar de rota recarrega. */
watch(codigo, (novo) => { if (novo) { abertas.value = {}; carregar() } })

function alternar(coluna) {
  abertas.value[coluna.chave] = !abertas.value[coluna.chave]
}

function abrirCard(card) {
  focoAnterior.value = document.activeElement
  cardAberto.value = card
}
function fecharCard() {
  cardAberto.value = null
  const alvo = focoAnterior.value
  focoAnterior.value = null
  if (alvo && typeof alvo.focus === 'function') alvo.focus()
}
function cliqueNoCard(card) {
  if (Date.now() - arrastouAgora < 400) return
  abrirCard(card)
}

function aoTeclar(evento) {
  if (evento.key !== 'Escape') return
  if (cardAberto.value) fecharCard()
}
onMounted(() => window.addEventListener('keydown', aoTeclar))
onBeforeUnmount(() => window.removeEventListener('keydown', aoTeclar))

function comecarArrasto(card, evento) {
  arrastando.value = card
  arrastouAgora = Date.now()
  if (evento.dataTransfer) {
    evento.dataTransfer.effectAllowed = 'move'
    evento.dataTransfer.setData('text/plain', String(card.id))
  }
}
function terminarArrasto() { arrastando.value = null; colunaAlvo.value = null }
function sobreAColuna(coluna) {
  if (arrastando.value) colunaAlvo.value = coluna.chave
}
function saiuDaColuna(coluna) {
  if (colunaAlvo.value === coluna.chave) colunaAlvo.value = null
}

async function soltarNaColuna(coluna) {
  const card = arrastando.value
  arrastando.value = null
  colunaAlvo.value = null
  arrastouAgora = Date.now()
  if (!card || !coluna.etapa_id) return
  /* ⚠️ Card arquivado não se move: reabrir primeiro é o gesto. Oferecer os
     dois ao mesmo tempo deixaria o estado ambíguo. */
  if (card.desfecho) {
    erroDeMover.value = 'Este card está finalizado. Reabra antes de mover.'
    return
  }
  if (card.etapa_id === coluna.etapa_id) return
  erroDeMover.value = ''
  try {
    await api.post(`/api/paineis/operacao/chamado/${card.id}/mover`,
                   { para_etapa: coluna.etapa_id })
    await carregar()
  } catch (e) {
    erroDeMover.value = e instanceof ErroDeApi
      ? e.message : 'Não deu para mover este card.'
  }
}
</script>

<template>
  <section class="painel escala-operacao">
    <header class="painel__topo">
      <h1 class="painel__titulo">Pós-venda</h1>
      <div class="painel__medidas">
        <span class="pilula">{{ total }} {{ total === 1 ? 'card' : 'cards' }}</span>
        <button class="botao botao--contorno" type="button"
                :disabled="carregando" @click="carregar">
          <i class="bi bi-arrow-clockwise" aria-hidden="true"></i>
          Atualizar
        </button>
      </div>
    </header>

    <!-- 🔵 AS ABAS: *"abas de pipeline: Treinamento / Pos venda"*.
         ⚠️ Com uma aba so, a barra nao aparece: uma aba sozinha nao e
         escolha, e desenhar a barra seria enfeite. -->
    <nav v-if="abasVisiveis.length > 1" class="abas"
         aria-label="Abas do Pós-venda">
      <RouterLink v-for="a in abasVisiveis" :key="a.codigo" :to="a.rota"
                  class="abas__item"
                  :class="{ 'abas__item--atual': a.codigo === codigo }"
                  :aria-current="a.codigo === codigo ? 'page' : undefined">
        {{ a.titulo }}
      </RouterLink>
    </nav>

    <p v-if="erro" class="aviso aviso--erro" role="alert">{{ erro }}</p>
    <p v-if="erroDeMover" class="aviso aviso--erro" role="alert">
      {{ erroDeMover }}
    </p>

    <p v-if="carregando && !quadro" class="nota">Abrindo…</p>

    <!-- 🚨 QUADRO VAZIO QUE NÃO DIZ POR QUÊ É `M12`: estas abas nascem sem
         cards porque a ORIGEM deles é decisão dele, e não porque algo falhou.
         ⚠️ Isto é ESTADO, e não texto explicativo: diz o que há, não como
         funciona. -->
    <p v-else-if="quadro && !total" class="nota">
      Nenhum card nesta aba ainda.
    </p>

    <div v-if="quadro" class="painel__quadro">
      <div v-for="(coluna, indice) in quadro.colunas" :key="coluna.chave"
           class="coluna"
           :class="{ 'coluna--vazia': !coluna.total,
                     'coluna--alvo': colunaAlvo === coluna.chave }"
           :style="{ borderTopColor: corDaEtapa(indice) }"
           :aria-label="coluna.titulo"
           @dragover.prevent="sobreAColuna(coluna)"
           @dragenter.prevent="sobreAColuna(coluna)"
           @dragleave="saiuDaColuna(coluna)"
           @drop.prevent="soltarNaColuna(coluna)">
        <h2 class="coluna__titulo">
          <button class="coluna__botao" type="button"
                  :aria-expanded="abertas[coluna.chave] ? 'true' : 'false'"
                  @click="alternar(coluna)">
            <span class="coluna__nome">{{ coluna.titulo }}</span>
            <span class="coluna__conta"
                  :class="{ 'coluna__conta--zero': !coluna.total }">
              {{ coluna.total }}
            </span>
          </button>
        </h2>

        <div v-if="abertas[coluna.chave]" class="coluna__corpo">
          <article v-for="card in coluna.cards" :key="card.id" class="card"
                   :draggable="!card.desfecho"
                   @dragstart="comecarArrasto(card, $event)"
                   @dragend="terminarArrasto">
            <div class="card__abrir"
                 :class="{ 'card__abrir--arquivado': !!card.desfecho }"
                 @click="cliqueNoCard(card)">
              <!-- 🔵 O SELO DO DESFECHO: *"ele esmaece e fica no fim da fila
                   arquivado com status de concluído"*. ⚠️ O esmaecer sozinho
                   não diz QUAL dos dois foi — opacidade não é portadora de
                   informação. -->
              <span v-if="card.desfecho" class="card__arquivado">
                <i class="bi bi-archive" aria-hidden="true"></i>
                {{ card.desfecho_rotulo || card.desfecho }}
                <template v-if="card.desfecho_em">
                  &middot; {{ dataCurta(card.desfecho_em) }}
                </template>
              </span>

              <p class="card__cliente" :title="card.cliente || ''">
                {{ card.cliente || 'Sem cliente identificado' }}
              </p>
              <span class="card__ident">
                <button class="card__os" type="button"
                        @click.stop="cliqueNoCard(card)">
                  {{ card.formulario || 'Card ' + card.id }}
                </button>
                <span class="card__quando">{{ dataCurta(card.criada_em) }}</span>
              </span>
              <p v-if="card.resumo" class="card__resumo">{{ card.resumo }}</p>
              <span v-if="card.observacoes" class="pilula">
                <i class="bi bi-chat-left-text" aria-hidden="true"></i>
                {{ card.observacoes }}
              </span>
            </div>
          </article>

          <p v-if="!coluna.total" class="nota pequeno">Vazia.</p>
        </div>
      </div>
    </div>

    <DialogoDeChamado v-if="cardAberto" :card="cardAberto"
                      rotulo-finalizar="Finalizar"
                      @fechar="fecharCard" @mudou="carregar" />
  </section>
</template>

<style scoped>
.painel { display: flex; flex-direction: column; gap: var(--e-4); }
.painel__topo {
  display: flex; flex-wrap: wrap; gap: var(--e-3);
  align-items: center; justify-content: space-between;
}
.painel__titulo { margin: 0; font-size: var(--txt-lg); }
.painel__medidas { display: flex; align-items: center; gap: var(--e-2); }

/* ⚠️ A ABA ATUAL E MARCADA POR BORDA, e nao so por cor: cor sozinha nao
   carrega informacao, e foi a regua que o item ativo do menu adotou em
   05/11 (barra branca, porque `--acento` sobre o fundo `#04034D` dava
   3,6:1). */
.abas {
  display: flex; gap: var(--e-1); flex-wrap: wrap;
  border-bottom: var(--borda-fina) solid var(--borda);
}
.abas__item {
  padding: var(--e-2) var(--e-3);
  border-bottom: 3px solid transparent;
  color: var(--texto-fraco); text-decoration: none;
  font-size: var(--txt-sm); font-weight: var(--peso-forte);
}
.abas__item:hover { color: var(--texto); background: var(--superficie-2); }
.abas__item--atual {
  color: var(--texto); border-bottom-color: var(--acento);
}

/* 🚨 A COLUNA DE 360px, e são 3 por scroll em 1366px — a medida que ele
   aprovou na Operação em 05/11: *"vendo 3 colunas por scroll esta ok"*. */
.painel__quadro {
  display: flex; gap: var(--e-3);
  overflow-x: auto; padding-bottom: var(--e-2);
  align-items: flex-start;
}
.coluna {
  flex: 0 0 360px;
  background: var(--fundo);
  border: var(--borda-fina) solid var(--borda);
  border-top: 3px solid var(--borda-forte);
  border-radius: var(--r-md);
  padding: var(--e-3);
}
.coluna--alvo { background: var(--superficie-2); }
.coluna--vazia { opacity: .8; }
.coluna__titulo { margin: 0; font-size: var(--txt-sm); }
.coluna__botao {
  width: 100%; display: flex; align-items: center; justify-content: space-between;
  gap: var(--e-2); border: 0; background: transparent; cursor: pointer;
  font: inherit; color: var(--texto); padding: 0 0 var(--e-2);
  text-align: left;
}
.coluna__nome { font-weight: var(--peso-forte); }
.coluna__conta {
  flex: 0 0 auto; min-width: 22px; text-align: center;
  padding: 0 var(--e-1); border-radius: var(--r-full);
  background: var(--acento); color: #FFFFFF;
  font-size: var(--txt-xs); font-weight: var(--peso-forte);
}
.coluna__conta--zero {
  background: transparent; color: var(--texto-fraco);
  border: var(--borda-fina) solid var(--borda-forte);
}
.coluna__corpo { display: flex; flex-direction: column; gap: var(--e-2); }

/* 🚨 A COLUNA RECUA E O CARD É BRANCO: os dois eram `--superficie` na
   Operação até 05/11, e 1px no tom mais claro da paleta era a única separação
   — era isso que fazia as caixas não terem limite. */
.card { border-radius: var(--r-md); }
.card[draggable="true"] { cursor: grab; }
.card[draggable="true"]:active { cursor: grabbing; }
.card__abrir {
  display: flex; flex-direction: column; gap: var(--e-1);
  padding: var(--e-3);
  background: var(--superficie);
  border: var(--borda-fina) solid var(--borda-forte);
  border-radius: var(--r-md);
  box-shadow: var(--sombra-1);
  cursor: pointer;
}
.card__abrir:hover { box-shadow: var(--sombra-2); }
.card__abrir--arquivado { opacity: .62; }
.card__abrir--arquivado:hover { opacity: 1; }

/* ⚠️ O NOME CORTA EM 2 LINHAS e o inteiro fica no `title`: 11 dos 15 nomes de
   cliente do quadro passam de 24 caracteres (mediana 28, o maior 56). */
.card__cliente {
  margin: 0; font-weight: var(--peso-forte); color: var(--texto);
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  overflow: hidden;
}
.card__ident {
  display: flex; flex-wrap: wrap; align-items: center; gap: var(--e-2);
  font-size: var(--txt-sm); color: var(--texto-fraco);
}
.card__os {
  border: 0; background: transparent; padding: 0; cursor: pointer;
  font: inherit; font-weight: var(--peso-forte); color: var(--texto);
  text-align: left;
}
.card__os:hover { text-decoration: underline; }
.card__resumo {
  margin: 0; font-size: var(--txt-sm); color: var(--texto-fraco);
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  overflow: hidden;
}
.card__arquivado {
  display: inline-flex; align-items: center; gap: var(--e-1);
  align-self: flex-start;
  padding: 1px var(--e-2);
  border: var(--borda-fina) solid var(--borda-forte);
  border-radius: var(--r-full);
  background: var(--superficie-2);
  font-size: var(--txt-xs); font-weight: var(--peso-forte);
  color: var(--texto-fraco);
}
.pilula {
  display: inline-flex; align-items: center; gap: var(--e-1);
  align-self: flex-start;
  padding: 1px var(--e-2); border-radius: var(--r-full);
  background: var(--superficie-2); color: var(--texto-fraco);
  font-size: var(--txt-xs); font-weight: var(--peso-forte);
}
.nota { color: var(--texto-fraco); }
.pequeno { font-size: var(--txt-sm); }
</style>
