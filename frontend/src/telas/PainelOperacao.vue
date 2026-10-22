<script setup>
/* ============================================================================
   PNL_1.1 — Painel da Operação (opção A: kanban pelas situações da OS)
   ----------------------------------------------------------------------------
   🔵 Escolha dele em 22/10, entre três mockups lado a lado: *"vamos de A
   somente para a Operação por enquanto, mas bem documentado para as demais
   futuramente"*. A opção A é a única em que **mover o card É a ação** — e foi
   esse o motivo que ele deu para o painel existir: *"hoje ainda não usamos a
   situação da OS, por isso o painel e consulta para atualizar a situação no
   painel"*.

   🚨 MOVER AINDA NÃO EXISTE, E A TELA DIZ ISSO. A rota que escreve
   `situacaoId` no Harmonit é da volta seguinte e depende de uma decisão dele.
   Enquanto não existir, não há `draggable` nenhum: oferecer o gesto e não
   gravar seria pior que não ter o gesto. É o precedente do `ModalAgendar`, que
   explica em vez de sumir.

   🚨 COLUNA VAZIA NASCE COLAPSADA, com o contador à vista — são 13 colunas, e
   nenhuma tela mostra 13 colunas sem rolar. É o que o kanban do FPSL já faz
   com a coluna "Pago". ⚠️ As duas primeiras ("Sem OS" e "Sem situação")
   nunca colapsam: a primeira é de onde a OS nasce, e a segunda existe porque
   **164 das 574 OS do Harmonit não estão em nenhuma das 11 situações**
   (medido em 22/10). Esconder essas duas seria esconder justamente o que há.

   🚨 A COR NUNCA É O ÚNICO PORTADOR: o estado da solicitação vem escrito na
   etiqueta, e a situação vem escrita no card. É a regra do quadro de demandas
   do FPSL -- *"o estado continua legível pela etiqueta"*.
   ============================================================================ */
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { api, ErroDeApi } from '../api/cliente.js'
import AjudaDaTela from '../componentes/AjudaDaTela.vue'

const router = useRouter()
const quadro = ref(null)
const carregando = ref(true)
const erro = ref('')
const abertas = ref({})

/* As duas que nunca colapsam. */
const SEMPRE_ABERTAS = ['sem_os', 'sem_situacao']

async function carregar() {
  carregando.value = true
  erro.value = ''
  try {
    quadro.value = await api.get('/api/paineis/operacao')
    for (const coluna of quadro.value.colunas) {
      /* Vazia nasce fechada; com card, aberta. */
      abertas.value[coluna.chave] = SEMPRE_ABERTAS.includes(coluna.chave)
        || coluna.total > 0
    }
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui ler o painel.'
  } finally {
    carregando.value = false
  }
}

function alternar(coluna) {
  if (SEMPRE_ABERTAS.includes(coluna.chave)) return
  abertas.value[coluna.chave] = !abertas.value[coluna.chave]
}

function abrirSolicitacao(card) {
  /* A ficha completa é da FRM_1.1 — o painel não repete a leitura dos 34
     campos do credenciamento. */
  router.push({ path: '/solicitacoes', query: { solicitacao: card.id } })
}

const vazio = computed(
  () => Boolean(quadro.value) && quadro.value.total === 0)

function quando(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })
}

const ROTULO_ESTADO = {
  nova: 'Nova', em_andamento: 'Em andamento', concluida: 'Concluída',
}

onMounted(carregar)
</script>

<template>
  <div class="tela">
    <header class="tela__cabecalho">
      <div>
        <h1>Operação</h1>
        <AjudaDaTela>
          As solicitações dos formulários da <strong>Operação</strong> (Suporte,
          Demonstração, Teste gratuito e Credenciamento técnico), em colunas
          pela <strong>situação da OS no Harmonit</strong>. Quem nunca virou OS
          fica na primeira coluna, e é de lá que a OS nasce.
        </AjudaDaTela>
      </div>
      <button class="botao botao--contorno" type="button" @click="carregar">Atualizar</button>
    </header>

    <p v-if="erro" class="aviso aviso--erro" role="alert">{{ erro }}</p>
    <p v-if="carregando" class="apagado">Lendo…</p>

    <template v-if="quadro">
      <p v-if="!quadro.pode_mover" class="aviso aviso--info">
        <i class="bi bi-info-circle aviso__icone" aria-hidden="true"></i>
        <span>{{ quadro.porque_nao_move }}</span>
      </p>

      <p class="apagado pequeno formularios">
        <span v-for="f in quadro.formularios" :key="f.codigo">
          {{ f.titulo }} <small>· {{ f.campos }} campos{{ f.ativo ? '' : ' · fora do ar' }}</small>
        </span>
      </p>

      <p v-if="vazio" class="aviso aviso--atencao">
        <i class="bi bi-inbox aviso__icone" aria-hidden="true"></i>
        <span>
          Nenhuma solicitação da Operação chegou ainda — as colunas estão
          desenhadas e vazias, e é o estado certo. Os quatro formulários estão
          no ar em <strong>forms.movisat.com.br</strong>.
        </span>
      </p>

      <div class="quadro">
        <section
          v-for="coluna in quadro.colunas"
          :key="coluna.chave"
          class="coluna"
          :class="{
            'coluna--fechada': !abertas[coluna.chave],
            'coluna--sem-os': coluna.chave === 'sem_os',
            'coluna--sem-situacao': coluna.chave === 'sem_situacao',
          }"
          :aria-label="coluna.titulo"
        >
          <h2 class="coluna__titulo">
            <button
              v-if="!SEMPRE_ABERTAS.includes(coluna.chave)"
              class="coluna__botao"
              type="button"
              :aria-expanded="abertas[coluna.chave] ? 'true' : 'false'"
              @click="alternar(coluna)"
            >
              <span>{{ coluna.titulo }}</span>
              <span class="coluna__conta">{{ coluna.total }}</span>
            </button>
            <span v-else class="coluna__botao coluna__botao--fixo">
              <span>{{ coluna.titulo }}</span>
              <span class="coluna__conta">{{ coluna.total }}</span>
            </span>
          </h2>

          <div v-if="abertas[coluna.chave]" class="coluna__corpo">
            <p v-if="coluna.nota" class="apagado pequeno">{{ coluna.nota }}</p>
            <p v-if="coluna.situacao_id" class="apagado pequeno">
              situação {{ coluna.situacao_id }} no Harmonit
            </p>

            <article v-for="card in coluna.cards" :key="card.id" class="card">
              <button class="card__abrir" type="button" @click="abrirSolicitacao(card)">
                <span class="card__topo">
                  <strong>{{ card.formulario }}</strong>
                  <span class="etiqueta" :class="`etiqueta--${card.estado}`">
                    {{ ROTULO_ESTADO[card.estado] || card.estado }}
                  </span>
                </span>
                <span v-if="card.cliente" class="card__cliente">{{ card.cliente }}</span>
                <span v-if="card.resumo" class="apagado pequeno">{{ card.resumo }}</span>
                <span class="apagado pequeno">
                  {{ quando(card.criada_em) }}
                  <template v-if="card.anexos"> · {{ card.anexos }} anexo(s)</template>
                </span>
                <!-- a OS, quando existir: é a outra metade do card que ele pediu -->
                <span v-if="card.os_id" class="apagado pequeno">
                  OS {{ card.numero_ordem || card.os_id }}
                  <!-- ⚠️ situação crua à vista: 0 é um valor que existe em 127 OS -->
                  <template v-if="card.situacao_id !== null">
                    · situação {{ card.situacao_id }}
                  </template>
                  <template v-else> · situação nunca lida</template>
                </span>
              </button>
            </article>

            <p v-if="!coluna.cards.length" class="apagado pequeno">Vazia.</p>
          </div>
        </section>
      </div>
    </template>
  </div>
</template>

<style scoped>
.tela__cabecalho { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--e-3); margin-bottom: var(--e-4); }
.tela__cabecalho h1 { margin: 0; font-size: var(--txt-xl); }

.formularios { display: flex; flex-wrap: wrap; gap: var(--e-3); margin: 0 0 var(--e-3); }

.quadro { display: flex; gap: var(--e-3); overflow-x: auto; padding-bottom: var(--e-3); align-items: flex-start; }

.coluna {
  flex: 0 0 248px;
  background: var(--superficie);
  border: var(--borda-fina) solid var(--borda);
  border-radius: var(--r-md);
}
/* 🚨 Colapsada fica ESTREITA, não invisível: o contador continua à vista. */
.coluna--fechada { flex: 0 0 210px; }

.coluna__titulo { margin: 0; font-size: var(--txt-sm); }
.coluna__botao {
  width: 100%;
  min-height: var(--altura-toque);
  display: flex; align-items: center; justify-content: space-between; gap: var(--e-2);
  padding: var(--e-2) var(--e-3);
  border: 0; border-bottom: var(--borda-fina) solid var(--borda);
  border-radius: var(--r-md) var(--r-md) 0 0;
  background: var(--superficie-2);
  color: var(--texto);
  font-size: var(--txt-sm); font-weight: var(--peso-forte);
  text-align: left;
  cursor: pointer;
}
.coluna__botao--fixo { cursor: default; }
.coluna--sem-os .coluna__botao { background: var(--acento-suave); color: var(--acento); }
.coluna--sem-situacao .coluna__botao { background: var(--aviso-suave); color: var(--aviso); }
.coluna__conta {
  background: var(--superficie);
  border: var(--borda-fina) solid var(--borda-forte);
  border-radius: var(--r-full);
  padding: 0 var(--e-2);
  font-size: var(--txt-xs);
  font-weight: var(--peso-normal);
}
.coluna__corpo { padding: var(--e-3); display: flex; flex-direction: column; gap: var(--e-2); }

.card { display: block; }
.card__abrir {
  width: 100%;
  min-height: var(--altura-toque);
  display: flex; flex-direction: column; gap: 2px;
  padding: var(--e-3);
  text-align: left;
  background: var(--superficie);
  border: var(--borda-fina) solid var(--borda);
  border-left: 3px solid var(--acento);
  border-radius: var(--r-md);
  color: var(--texto);
  cursor: pointer;
}
.card__abrir:hover { background: var(--superficie-2); }
.card__topo { display: flex; align-items: center; justify-content: space-between; gap: var(--e-2); }
.card__cliente { font-size: var(--txt-md); }

.etiqueta { padding: 0 var(--e-2); border-radius: var(--r-full); font-size: var(--txt-xs); border: var(--borda-fina) solid var(--borda); }
.etiqueta--nova { background: var(--acento-suave); border-color: var(--acento-borda); color: var(--acento); }
.etiqueta--em_andamento { background: var(--aviso-suave); border-color: var(--aviso); color: var(--aviso); }
.etiqueta--concluida { background: var(--ok-suave); border-color: var(--ok-borda); color: var(--ok); }
</style>
