<script setup>
/* ============================================================================
   O CARD DE PIPELINE ABERTO — chamado, treinamento, pós-venda
   ----------------------------------------------------------------------------
   🔵 Ele, 05/11: *"nessa coluna não são OS ainda, somente o CARD mesmo, com
   OBS, etc"* · *"ter o botão de 'Finalizar Chamado' e daí vai perguntar
   'Resolvido' ou 'Não resolvido'"* · *"um botão de 'abrir conversa'"*.

   🚨 COMPONENTE, E NÃO UMA SEGUNDA CÓPIA: a coluna `Chamados` e as abas de
   Pós-venda usam o mesmo diálogo. Duplicar o markup faria a correção seguinte
   ter de ser lembrada em dois lugares — e é assim que uma delas apodrece.

   🚨 NENHUMA LEITURA DAQUI VAI AO ERP, e é a diferença inteira em relação ao
   card de OS: a `/chamado/{id}` lê o nosso banco, então não pode devolver 502
   por falha de terceiro.

   ⚠️ O DIÁLOGO DECLARA O PRÓPRIO TETO: a `.modal__caixa` da casa impõe
   `max-width: 420px`, e teto não se vence com especificidade — só
   redeclarando. Foi o defeito que ele apontou três vezes em 05/11, e aqui ele
   voltaria inteiro, porque o `.painel__dialogo` da tela da Operação é
   `scoped` e não alcança este componente.
   ============================================================================ */
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { api, ErroDeApi } from '../api/cliente.js'
import BalaoDeRecado from './BalaoDeRecado.vue'

const props = defineProps({
  card: { type: Object, required: true },
  /* ⚠️ O rótulo do botão é da TELA, não do componente: na Operação ele é
     *"Finalizar Chamado"*, palavra dele; numa aba de Pós-venda, "chamado" não
     diz nada. */
  rotuloFinalizar: { type: String, default: 'Finalizar Chamado' },
})
const emit = defineEmits(['fechar', 'mudou'])

const router = useRouter()
const caixa = ref(null)
const ficha = ref(null)
const lendo = ref(false)
const erro = ref('')
const perguntandoDesfecho = ref(false)
const finalizando = ref(false)
const movendo = ref(false)
const recado = ref('')
const enviandoRecado = ref(false)
const erroDoRecado = ref('')

const observacoes = computed(() => ficha.value?.observacoes || [])
const etapas = computed(() => ficha.value?.etapas || [])
const etapaAtual = computed(() => ficha.value?.card?.etapa_id ?? null)

function quando(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleString('pt-BR', { day: '2-digit', month: '2-digit',
                                     hour: '2-digit', minute: '2-digit' })
}

async function carregarFicha() {
  lendo.value = true
  erro.value = ''
  try {
    ficha.value = await api.get(
      `/api/paineis/operacao/chamado/${props.card.id}`)
  } catch (e) {
    erro.value = e instanceof ErroDeApi
      ? e.message : 'Não deu para ler este card agora.'
  } finally {
    lendo.value = false
  }
}

/* 🚨 `requestAnimationFrame` e não `nextTick`: o `nextTick` do Vue resolve
   antes de o navegador pintar, e `focus()` num elemento ainda não pintado não
   move o foco. */
function focar() {
  requestAnimationFrame(() => {
    if (caixa.value && typeof caixa.value.focus === 'function') {
      caixa.value.focus()
    }
  })
}

onMounted(async () => {
  focar()
  await carregarFicha()
})

watch(() => props.card?.id, async (novo, velho) => {
  if (novo && novo !== velho) {
    perguntandoDesfecho.value = false
    recado.value = ''
    await carregarFicha()
  }
})

/* 🔵 *"Resolvido"* ou *"Não resolvido"*. 🚨 Os dois SÓ MARCAM — decisão dele:
   *"só marca; a OS é pelo Operação"*. Nada escreve no ERP, e é isso que torna
   o botão reversível. */
async function finalizar(desfecho) {
  finalizando.value = true
  erro.value = ''
  try {
    await api.post(
      `/api/paineis/operacao/chamado/${props.card.id}/finalizar`, { desfecho })
    perguntandoDesfecho.value = false
    await carregarFicha()
    emit('mudou')
  } catch (e) {
    erro.value = e instanceof ErroDeApi
      ? e.message : 'Não deu para finalizar.'
  } finally {
    finalizando.value = false
  }
}

async function reabrir() {
  finalizando.value = true
  try {
    await api.post(`/api/paineis/operacao/chamado/${props.card.id}/reabrir`)
    await carregarFicha()
    emit('mudou')
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não deu para reabrir.'
  } finally {
    finalizando.value = false
  }
}

/* ⚠️ Mover aqui NÃO fala com o Harmonit — rota separada, de propósito: a
   `/operacao/mover` grava `situacaoId` no ERP, e um card de pipeline não tem
   situação para gravar. Duas rotas é o que impede o caminho errado. */
async function mover(paraEtapa) {
  const destino = Number(paraEtapa)
  if (!destino || destino === etapaAtual.value) return
  movendo.value = true
  erro.value = ''
  try {
    await api.post(`/api/paineis/operacao/chamado/${props.card.id}/mover`,
                   { para_etapa: destino })
    await carregarFicha()
    emit('mudou')
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não deu para mover.'
  } finally {
    movendo.value = false
  }
}

/* 🚨 ABRIR CONVERSA É UM `router.push`, E NADA MAIS — o padrão já existe e está
   em uso na ficha do cliente (`Clientes.vue`): a Caixa de Entrada lê `?numero=`
   e resolve os três casos sozinha (uma conversa achada abre; nenhuma abre o
   painel do `+` já preenchido; várias deixam a lista filtrada).
   ⚠️ E NÃO se usa o `conversas.iniciar_conversa`: essa função EXIGE texto, de
   propósito, para não deixar conversa vazia órfã na Caixa. */
function abrirConversa() {
  const tel = props.card?.telefone
  if (!tel) return
  router.push(`/atendimento?numero=${encodeURIComponent(tel)}`)
}

async function salvarRecado() {
  const texto = (recado.value || '').trim()
  const sid = ficha.value?.chamado?.solicitacao_id
  if (!texto || !sid) return
  enviandoRecado.value = true
  erroDoRecado.value = ''
  try {
    const r = await api.post('/api/paineis/operacao/chamado/observacao',
                             { solicitacao_id: sid, texto })
    ficha.value = { ...ficha.value, observacoes: r.observacoes || [] }
    recado.value = ''
    emit('mudou')
  } catch (e) {
    erroDoRecado.value = e instanceof ErroDeApi
      ? e.message : 'Não deu para salvar a observação.'
  } finally {
    enviandoRecado.value = false
  }
}

/* ⚠️ O `Escape` E DA TELA, E NAO DAQUI, e e deliberado: a tela da Operacao
   tem tres dialogos e a ORDEM de fechamento importa (*"fechar o card por baixo
   de um modal aberto em cima dele deixaria o de cima orfao"*). Dois ouvintes
   fariam o `fechar` disparar duas vezes -- e `devolverFoco` tirando dois da
   pilha devolveria o foco ao lugar errado. Cada tela que abre este componente
   amarra o seu. */
</script>

<template>
  <div class="modal modal--chamado" role="dialog" aria-modal="true"
       :aria-label="`Card ${card.id}`" @click.self="emit('fechar')">
    <div ref="caixa" tabindex="-1"
         class="modal__caixa painel__dialogo--chamado">

      <header class="modal__topo">
        <div class="modal__quem">
          <h2 class="modal__cliente">
            {{ card.cliente || 'Sem cliente identificado' }}
          </h2>
          <p class="modal__ident">
            <strong class="modal__os">{{ card.formulario || 'Card' }}</strong>
            <span class="modal__risco" aria-hidden="true"></span>
            <span>aberto {{ quando(card.criada_em) }}</span>
            <!-- ⚠️ O selo diz QUAL desfecho: esmaecer o card não distingue
                 Resolvido de Virou OS. -->
            <template v-if="card.desfecho">
              <span class="modal__risco" aria-hidden="true"></span>
              <span class="card__arquivado">{{ card.desfecho_rotulo }}</span>
            </template>
          </p>
        </div>
        <button class="modal__fechar" type="button" aria-label="Fechar"
                @click="emit('fechar')">✕</button>
      </header>

      <div class="modal__faixa">
        <div class="faixa__medida faixa__medida--etapa">
          <span class="faixa__rotulo">Etapa</span>
          <!-- 🔵 Mover entre as etapas NOSSAS. ⚠️ Um card arquivado não se
               move: reabrir primeiro é o gesto, e oferecer os dois ao mesmo
               tempo deixaria o estado ambíguo. -->
          <select v-if="etapas.length > 1 && !card.desfecho"
                  class="campo faixa__select" :disabled="movendo"
                  aria-label="Mover de etapa"
                  :value="etapaAtual"
                  @change="mover($event.target.value)">
            <option v-for="e in etapas" :key="e.id" :value="e.id">
              {{ e.titulo }}
            </option>
          </select>
          <strong v-else>
            {{ etapas.find((e) => e.id === etapaAtual)?.titulo || '—' }}
          </strong>
        </div>
        <div class="faixa__medida">
          <span class="faixa__rotulo">Observações</span>
          <strong>{{ observacoes.length }}</strong>
        </div>
        <div v-if="card.desfecho" class="faixa__medida">
          <span class="faixa__rotulo">Finalizado</span>
          <strong>{{ quando(card.desfecho_em) }}</strong>
        </div>
      </div>

      <p v-if="erro" class="aviso aviso--erro" role="alert">{{ erro }}</p>

      <div class="modal__corpo modal__corpo--duas">
        <div class="modal__coluna">
          <p class="modal__secao">O que o cliente disse</p>

          <section class="modal__painel">
            <h3>
              Chamado
              <span v-if="ficha && ficha.chamado" class="pilula">
                {{ ficha.chamado.respostas.length }} campos
              </span>
            </h3>
            <p v-if="lendo" class="nota pequeno">Lendo…</p>
            <!-- 🚨 Os campos com RÓTULO, nunca as chaves do Bitrix: a tela não
                 pode mostrar `COMPANY_UF_CRM_1646332310941` a ninguém. -->
            <dl v-else-if="ficha && ficha.chamado" class="temas__respostas">
              <template v-for="r in ficha.chamado.respostas" :key="r.nome">
                <dt>{{ r.rotulo }}</dt>
                <dd>{{ Array.isArray(r.valor) ? r.valor.join(' · ') : r.valor }}</dd>
              </template>
            </dl>
            <p v-else class="nota pequeno">
              Este card não veio de formulário.
            </p>
          </section>

          <section class="modal__painel">
            <h3>Observações <span class="pilula">{{ observacoes.length }}</span></h3>
            <ul v-if="observacoes.length" class="recados">
              <BalaoDeRecado v-for="o in [...observacoes].reverse()"
                             :key="o.id" :recado="o" :quando="quando" />
            </ul>
            <p v-else class="nota pequeno">Nenhuma observação ainda.</p>

            <div class="modal__rodape--escrever">
              <textarea v-model="recado" rows="2" :disabled="enviandoRecado"
                        placeholder="o que a análise deste card precisa registrar"
                        aria-label="Escrever observação"></textarea>
              <div class="modal__pe">
                <button class="botao" type="button"
                        :disabled="enviandoRecado || !recado.trim()"
                        @click="salvarRecado">
                  {{ enviandoRecado ? 'Salvando…' : 'Salvar' }}
                </button>
              </div>
              <p v-if="erroDoRecado" class="aviso aviso--erro" role="alert">
                {{ erroDoRecado }}
              </p>
            </div>
          </section>
        </div>

        <div class="modal__coluna">
          <p class="modal__secao">O histórico</p>
          <section class="modal__painel">
            <h3>Passagens de etapa</h3>
            <ol v-if="ficha && ficha.historico.length" class="modal__passagens">
              <li v-for="p in ficha.historico" :key="p.id">
                <span class="nota pequeno">{{ quando(p.em) }}</span>
                <span>
                  <template v-if="p.de_titulo">{{ p.de_titulo }} &#8594; </template>
                  <strong>{{ p.para_titulo }}</strong>
                </span>
                <span class="pilula">{{ p.quem || 'sem autor' }}</span>
              </li>
            </ol>
            <p v-else class="nota pequeno">Nenhuma passagem registrada.</p>
          </section>
        </div>
      </div>

      <footer class="modal__rodape">
        <div class="modal__agir">
          <!-- ⚠️ Sem telefone o botão NÃO APARECE, em vez de oferecer um gesto
               que falha: o campo é obrigatório no formulário de suporte, mas um
               card criado a mão não terá. -->
          <button v-if="card.telefone" class="botao botao--contorno"
                  type="button" @click="abrirConversa">
            <i class="bi bi-whatsapp" aria-hidden="true"></i>
            Abrir conversa
          </button>

          <!-- 🔵 A pergunta aparece NO LUGAR do botão, e não num terceiro
               diálogo empilhado: empilhar foi o que deixou o modal das
               observações atrás do card em 05/11. -->
          <template v-if="!card.desfecho">
            <button v-if="!perguntandoDesfecho" class="botao" type="button"
                    @click="perguntandoDesfecho = true">
              {{ rotuloFinalizar }}
            </button>
            <span v-else class="desfecho__pergunta">
              <span class="desfecho__rotulo">Resolvido?</span>
              <button class="botao" type="button" :disabled="finalizando"
                      @click="finalizar('resolvido')">Resolvido</button>
              <button class="botao botao--contorno" type="button"
                      :disabled="finalizando"
                      @click="finalizar('virou_os')">Não resolvido</button>
              <button class="botao botao--fantasma" type="button"
                      :disabled="finalizando"
                      @click="perguntandoDesfecho = false">Cancelar</button>
            </span>
          </template>
          <!-- ⚠️ Reabrir existe porque finalizar SÓ MARCA: nada foi escrito
               fora, então desfazer é seguro — e marca que não se desmarca seria
               porta de mão única numa tela de uso diário. -->
          <button v-else class="botao botao--contorno" type="button"
                  :disabled="finalizando" @click="reabrir">
            Reabrir
          </button>
        </div>

        <div class="modal__acoes">
          <button class="botao" type="button" @click="emit('fechar')">Fechar</button>
        </div>
      </footer>
    </div>
  </div>
</template>

<style scoped>
/* 🚨 O DIÁLOGO DECLARA AS QUATRO PROPRIEDADES DE FORMA, e nenhuma delas é
   herdada: a `.modal__caixa` global (`estilo/componentes.css`) é um aviso de
   420px com `padding: var(--e-5)` e `overflow-y: auto`. `max-width` é teto
   aplicado DEPOIS do `width`, então especificidade não resolve — só
   redeclarar. ⚠️ E não adianta o `.painel__dialogo` da tela da Operação: ele é
   `scoped` daquele componente e não alcança este. */
.painel__dialogo--chamado {
  width: min(900px, 100%);
  max-width: min(900px, 100%);
  padding: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  max-height: min(88vh, 900px);
}
/* O card abre por cima do quadro, e abaixo dos avisos. */
.modal--chamado { z-index: calc(var(--z-modal, 50) + 5); }

.modal__topo {
  display: flex; align-items: flex-start; gap: var(--e-3);
  padding: var(--e-4) var(--e-5);
  border-bottom: var(--borda-fina) solid var(--borda);
}
.modal__quem { flex: 1 1 auto; min-width: 0; }
.modal__cliente {
  margin: 0; font-size: var(--txt-lg); line-height: 1.25;
  color: var(--texto);
}
.modal__ident {
  margin: var(--e-1) 0 0; display: flex; flex-wrap: wrap;
  align-items: center; gap: var(--e-2);
  font-size: var(--txt-sm); color: var(--texto-fraco);
}
.modal__os { color: var(--texto); }
.modal__risco {
  width: 3px; height: 3px; border-radius: var(--r-full);
  background: var(--borda-forte);
}
.modal__fechar {
  flex: 0 0 auto; border: 0; background: transparent; cursor: pointer;
  font-size: var(--txt-md); color: var(--texto-fraco);
  padding: var(--e-1) var(--e-2); border-radius: var(--r-sm);
}
.modal__fechar:hover { background: var(--superficie-2); color: var(--texto); }

.modal__faixa {
  display: flex; flex-wrap: wrap; gap: var(--e-5);
  padding: var(--e-3) var(--e-5);
  background: var(--superficie-2);
  border-bottom: var(--borda-fina) solid var(--borda);
}
.faixa__medida { display: flex; flex-direction: column; gap: 2px; }
.faixa__rotulo {
  font-size: var(--txt-xs); color: var(--texto-fraco);
  text-transform: uppercase; letter-spacing: .04em;
}
.faixa__select { min-width: 190px; }

/* 🚨 UMA rolagem só, e é esta: duas rolagens empilhadas (o palco e o corpo)
   foi um dos defeitos de 05/11. */
.modal__corpo {
  display: grid; gap: var(--e-5);
  padding: var(--e-5);
  overflow-y: auto;
}
.modal__corpo--duas { grid-template-columns: 1.3fr 1fr; }
@media (max-width: 760px) {
  .modal__corpo--duas { grid-template-columns: 1fr; }
}
.modal__coluna { display: flex; flex-direction: column; gap: var(--e-4); min-width: 0; }
.modal__secao {
  margin: 0; font-size: var(--txt-xs); font-weight: var(--peso-forte);
  text-transform: uppercase; letter-spacing: .04em; color: var(--texto-fraco);
}
/* ⚠️ A seção define o PRÓPRIO respiro: a `.modal__caixa` tem `padding: 0`
   agora, e filha direta sem padding colava na borda — o defeito D1 de 05/11. */
.modal__painel {
  border: var(--borda-fina) solid var(--borda);
  border-radius: var(--r-md);
  background: var(--superficie);
  padding: var(--e-4);
}
.modal__painel h3 {
  margin: 0 0 var(--e-3); font-size: var(--txt-sm);
  display: flex; align-items: center; gap: var(--e-2);
}
.temas__respostas { margin: 0; display: grid; gap: var(--e-2); }
.temas__respostas dt {
  font-size: var(--txt-xs); color: var(--texto-fraco);
  text-transform: uppercase; letter-spacing: .03em;
}
.temas__respostas dd {
  margin: 0 0 var(--e-2); font-size: var(--txt-sm); color: var(--texto);
  overflow-wrap: anywhere;
}
.recados { list-style: none; margin: 0 0 var(--e-3); padding: 0;
           display: flex; flex-direction: column; gap: var(--e-2); }
.modal__passagens {
  list-style: none; margin: 0; padding: 0;
  display: flex; flex-direction: column; gap: var(--e-2);
  font-size: var(--txt-sm);
}
.modal__passagens li { display: flex; flex-wrap: wrap; gap: var(--e-2);
                       align-items: center; }
.modal__rodape--escrever textarea {
  width: 100%; resize: vertical;
  border: var(--borda-fina) solid var(--borda);
  border-radius: var(--r-sm); padding: var(--e-2);
  font: inherit; color: var(--texto); background: var(--superficie);
}
.modal__pe { display: flex; justify-content: flex-end; margin-top: var(--e-2); }

.modal__rodape {
  display: flex; flex-wrap: wrap; gap: var(--e-3);
  justify-content: space-between; align-items: center;
  padding: var(--e-4) var(--e-5);
  border-top: var(--borda-fina) solid var(--borda);
  background: var(--superficie-2);
}
.modal__agir { display: flex; flex-wrap: wrap; gap: var(--e-2); align-items: center; }

/* 🔵 A pergunta do desfecho fica NO LUGAR do botão. */
.desfecho__pergunta {
  display: inline-flex; align-items: center; gap: var(--e-2); flex-wrap: wrap;
}
.desfecho__rotulo {
  font-size: var(--txt-sm); font-weight: var(--peso-forte);
  color: var(--texto-fraco);
}
.card__arquivado {
  display: inline-flex; align-items: center; gap: var(--e-1);
  padding: 1px var(--e-2);
  border: var(--borda-fina) solid var(--borda-forte);
  border-radius: var(--r-full);
  background: var(--superficie-2);
  font-size: var(--txt-xs); font-weight: var(--peso-forte);
  color: var(--texto-fraco);
}
.pilula {
  display: inline-flex; align-items: center;
  padding: 1px var(--e-2); border-radius: var(--r-full);
  background: var(--superficie-2); color: var(--texto-fraco);
  font-size: var(--txt-xs); font-weight: var(--peso-forte);
}
.nota { color: var(--texto-fraco); }
.pequeno { font-size: var(--txt-sm); }
</style>
