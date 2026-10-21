<script setup>
/* ============================================================================
   CFG_7.1 — Geral. Os interruptores do SISTEMA.
   ----------------------------------------------------------------------------
   Pedido dele em 27/08: *"os acionadores dos interruptores devem ficar lá"*. Em
   28/08 ele mandou conferir se todos tinham chegado — e dois não tinham:

     🔴 `jornada_ativa` acionava em ATENDENTES (CAD_2.1), tela de cadastro.
        É interruptor do sistema: muda como a fila distribui. Estava escondido
        onde ninguém procura configuração -- o mesmo padrão que motivou a
        escada da IA.

     🔴 `avaliacao_ativa` não tinha acionador em tela NENHUMA. A chave existe no
        banco, com descrição, e não havia como ligá-la pelo painel.

   🚨 A LEITURA CONTINUA EM ATENDENTES, SÓ A CHAVE MUDOU DE LUGAR. Aquela tela
   precisa do estado para marcar quem está fora do horário; o que saiu de lá foi
   o BOTÃO. Interruptor tem um lugar só; estado se lê onde faz falta.

   ⚠️ `avaliacao_ativa` aparece TRAVADA, com o motivo escrito -- é a regra que
   ele aprovou na escada da IA: nada some, e o que não dá para usar diz o que
   falta. Ligar um interruptor cujo comportamento não existe seria pior que
   escondê-lo.
   ============================================================================ */
import { ref, computed, onMounted } from 'vue'

import { api, ErroDeApi } from '../api/cliente.js'
import AjudaDaTela from '../componentes/AjudaDaTela.vue'

const carregando = ref(true)
const salvando = ref(false)
const erro = ref('')
const recado = ref('')
const jornadaAtiva = ref(false)

/* 🔵 24/09 — a regra de status por tempo (*"igual ao MSN = 15min sem
   interação -Ausente; 1h sem interação Offline"*) e a mensagem de fim de
   expediente (*"deixar em branco e com flag de 'mensagem automatica' 'ativar'
   ou 'não'"*). As duas nascem desligadas; um PUT só grava as duas. */
const presenca = ref(null)
let retratoPresenca = ''
/* 🔵 19/10: a hora da última mudança da régua, no fuso de quem olha. O
   backend manda ISO; formatar aqui evita uma segunda verdade sobre fuso. */
const quandoMudou = computed(() => {
  const iso = presenca.value?.ultima_mudanca?.em
  if (!iso) return ''
  const d = new Date(iso)
  return Number.isNaN(d.getTime())
    ? '' : d.toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })
})

const presencaMudou = computed(() =>
  presenca.value !== null && JSON.stringify(presenca.value) !== retratoPresenca)

/* 🔵 24/09 — distribuição automática da fila: *"coloque em uma caixa de
   seleção para que eu mude isso quando quiser"*. Primeiro e reserva
   (*"Vão para Erika na mesma regra e depois fila se ambas estiverem
   offline"*). Lista só quem pode receber. */
const distribuicao = ref(null)
const podemReceber = ref([])
let retratoDistribuicao = ''
const distribuicaoMudou = computed(() =>
  distribuicao.value !== null && JSON.stringify(distribuicao.value) !== retratoDistribuicao)

async function carregarDistribuicao() {
  const [cfg, equipe] = await Promise.all([
    api.get('/api/config/distribuicao'),
    api.get('/api/atendentes'),
  ])
  distribuicao.value = {
    ligada: cfg.ligada, primeiro_id: cfg.primeiro_id,
    reserva_id: cfg.reserva_id, minutos: cfg.minutos,
  }
  retratoDistribuicao = JSON.stringify(distribuicao.value)
  podemReceber.value = equipe.filter((a) => a.ativo && a.transferivel)
}

async function salvarDistribuicao() {
  salvando.value = true
  recado.value = ''
  erro.value = ''
  try {
    const r = await api.put('/api/config/distribuicao', {
      ...distribuicao.value, minutos: Number(distribuicao.value.minutos),
    })
    distribuicao.value = {
      ligada: r.ligada, primeiro_id: r.primeiro_id, reserva_id: r.reserva_id, minutos: r.minutos,
    }
    retratoDistribuicao = JSON.stringify(distribuicao.value)
    recado.value = r.ligada
      ? 'Distribuição ligada. Só entram conversas em que o cliente escrever a partir de agora.'
      : 'Distribuição desligada.'
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui salvar.'
  } finally {
    salvando.value = false
  }
}

async function carregarPresenca() {
  presenca.value = await api.get('/api/config/presenca')
  retratoPresenca = JSON.stringify(presenca.value)
}

async function salvarPresenca() {
  salvando.value = true
  recado.value = ''
  erro.value = ''
  try {
    presenca.value = await api.put('/api/config/presenca', {
      ...presenca.value,
      minutos_ausente: Number(presenca.value.minutos_ausente),
      minutos_offline: Number(presenca.value.minutos_offline),
      minutos_painel_fila: Number(presenca.value.minutos_painel_fila),
    })
    retratoPresenca = JSON.stringify(presenca.value)
    recado.value = 'Regras de status e mensagem de fim de expediente salvas.'
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui salvar.'
  } finally {
    salvando.value = false
  }
}

async function carregar() {
  carregando.value = true
  try {
    jornadaAtiva.value = (await api.get('/api/config/jornada')).jornada_ativa
    // 🚨 EM TRY PRÓPRIO: é um interruptor a mais, e não pode derrubar a
    // leitura da tela inteira se a rota falhar. Achado por teste -- a suíte
    // da Geral ficou vermelha na primeira versão, que lia junto com o resto.
    try {
      harmonitLigado.value = (await api.get('/api/config/agendamento-harmonit')).ligada
    } catch {
      harmonitLigado.value = false
    }
    await carregarPresenca()
    await carregarDistribuicao()
    erro.value = ''
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui ler.'
  } finally {
    carregando.value = false
  }
}

const harmonitLigado = ref(false)

async function alternarHarmonit() {
  salvando.value = true
  recado.value = ''
  try {
    const r = await api.put('/api/config/agendamento-harmonit',
                            { ligada: !harmonitLigado.value })
    // Relê o que o servidor gravou: a confirmação é o estado.
    harmonitLigado.value = r.ligada
    recado.value = harmonitLigado.value
      ? 'Ligado: agendar aqui passa a criar o compromisso na OS do Harmonit.'
      : 'Desligado: o compromisso passa a viver só neste painel.'
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui mudar.'
  } finally {
    salvando.value = false
  }
}

async function alternarJornada() {
  salvando.value = true
  recado.value = ''
  try {
    const r = await api.put('/api/config/jornada', { ligada: !jornadaAtiva.value })
    jornadaAtiva.value = r.jornada_ativa
    recado.value = jornadaAtiva.value
      ? 'Jornada ligada: a fila passa a avisar quem está fora do horário.'
      : 'Jornada desligada: a escala continua gravada e não afeta a fila.'
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui mudar.'
  } finally {
    salvando.value = false
  }
}

onMounted(carregar)
</script>

<template>
  <div class="tela">
    <header class="tela__cabecalho">
      <div>
        <h1>Geral</h1>
        <AjudaDaTela>
          Os interruptores que valem para o painel inteiro. Os que são por
          canal, por tipo ou por pessoa ficam nas abas deles.
        </AjudaDaTela>
      </div>
    </header>

    <p v-if="erro" class="aviso aviso--erro" role="alert">{{ erro }}</p>
    <p v-if="recado" class="aviso aviso--ok" role="status">{{ recado }}</p>
    <p v-if="carregando" class="linha fraco"><span class="girando"></span> Lendo…</p>

    <section class="cartao tela__bloco">
      <div class="cartao__corpo pilha">
        <label class="interruptor">
          <input type="checkbox" :checked="jornadaAtiva" :disabled="salvando"
                 @change="alternarJornada" />
          <span><strong>Usar a jornada dos atendentes na fila</strong></span>
        </label>
        <p class="apagado pequeno">
          Desligada, a escala fica gravada e não afeta a fila. Monta-se com
          calma; ligar é ato separado.
        </p>
        <p class="apagado pequeno">
          A escala de cada pessoa se monta em <strong>Atendentes</strong>.
        </p>
      </div>
    </section>



    <template v-if="presenca">
      <section class="cartao tela__bloco">
        <div class="cartao__corpo pilha">
          <label class="interruptor">
            <input v-model="presenca.regra_ligada" type="checkbox" :disabled="salvando" />
            <span><strong>Mudar o status sozinho quando o atendente para de atender</strong></span>
          </label>
          <p class="apagado pequeno">
            Conta só ação de atendimento: enviar, assumir, entrar, transferir,
            concluir. Ficar com a tela aberta sem agir não conta para voltar a
            <strong>Disponível</strong>. Quem o sistema pôs como ausente ou offline
            volta a Disponível na próxima ação; o que a pessoa escolhe na Minha
            conta, o sistema não desfaz.
          </p>
          <!-- 🔵 19/10, a regra dele, FECHADA na segunda volta do dia:
               *"dentro da jornada cadastrada, impossível ficar fora do expediente,
               e se for colocado offline, volta automaticamente ao enviar mensagem
               para online"*. De manhã este mesmo cartão dizia que o offline
               voltava quando a pessoa fechava o painel -- deixou de ser verdade na
               mesma tarde, e texto que não acompanha o comportamento é defeito. -->
          <p class="aviso aviso--info pequeno">
            <i class="bi bi-info-circle aviso__icone" aria-hidden="true"></i>
            <span><strong>Dentro da jornada cadastrada ninguém fica "fora do
            expediente"</strong>: o máximo pelo tempo é <strong>Ausente</strong>, e
            quem for posto fora volta a <strong>Disponível</strong> na primeira
            mensagem que enviar. O campo "Offline depois de" vale <strong>fora do
            turno</strong>, e para quem não tem jornada cadastrada em Atendentes.</span>
          </p>
          <!-- 🔵 19/10: o terceiro número, que ele pediu ajustável. 🚨 Ele NÃO
               mexe no status de ninguém -- mexe em quem RECEBE. Sem ele, quem sai
               às 15h com o navegador fechado seguiria na fila até as 18h, porque o
               offline por tempo deixou de existir dentro do turno. -->
          <div class="regra">
            <label class="campo regra__campo">
              <span class="campo__rotulo">Sai da fila com o painel fechado há</span>
              <span class="regra__entrada">
                <input v-model="presenca.minutos_painel_fila" class="campo__entrada"
                       type="number" min="2" max="1440" />
                <span class="apagado">min</span>
              </span>
            </label>
          </div>
          <p class="apagado pequeno">
            Quem está com o painel fechado há mais que isso <strong>para de receber
            conversa distribuída</strong>, mas continua aceitando
            <strong>transferência à mão</strong> — quem transfere é avisado. Isto
            não muda o status dela na tela.
          </p>
          <!-- 🔵 19/10: *"a Geral não diz os valores em vigor"*. 🚨 O que se
               mostra é a última vez que a régua MUDOU alguém -- não existe carimbo
               de "passada", e ler `atualizado_em` seria mentira (nome, foto e
               afastamento carimbam a mesma coluna). Por isso o texto diz, em
               palavras, que silêncio significa "não mexeu em ninguém". -->
          <p class="apagado pequeno">
            <template v-if="presenca.ultima_mudanca">
              A régua passa a cada 1 min. A última vez que mexeu em alguém foi
              <strong>{{ quandoMudou }}</strong>
              ({{ presenca.ultima_mudanca.ausentes }} para ausente,
              {{ presenca.ultima_mudanca.offline }} para offline,
              {{ presenca.ultima_mudanca.curados }} devolvido(s) à jornada).
            </template>
            <template v-else>
              A régua passa a cada 1 min e ainda não mexeu em ninguém desde que isto
              passou a ser registrado — o que não quer dizer que ela não esteja
              rodando.
            </template>
          </p>
          <div class="regra">
            <label class="campo regra__campo">
              <span class="campo__rotulo">Ausente depois de</span>
              <span class="regra__entrada">
                <input v-model="presenca.minutos_ausente" class="campo__entrada" type="number"
                       min="1" max="1440" :disabled="!presenca.regra_ligada" />
                <span class="apagado">min</span>
              </span>
            </label>
            <label class="campo regra__campo">
              <span class="campo__rotulo">Offline depois de</span>
              <span class="regra__entrada">
                <input v-model="presenca.minutos_offline" class="campo__entrada" type="number"
                       min="2" max="1440" :disabled="!presenca.regra_ligada" />
                <span class="apagado">min</span>
              </span>
            </label>
          </div>
          <p class="aviso aviso--info pequeno">
            <i class="bi bi-info-circle aviso__icone" aria-hidden="true"></i>
            <span>Quem está <strong>offline não recebe transferência</strong>.</span>
          </p>
        </div>
      </section>

      <section class="cartao tela__bloco">
        <div class="cartao__corpo pilha">
          <label class="interruptor">
            <input v-model="presenca.mensagem_ligada" type="checkbox" :disabled="salvando" />
            <span><strong>Mensagem automática de fim de expediente</strong></span>
          </label>
          <label class="campo">
            <span class="campo__rotulo">Texto da mensagem</span>
            <textarea v-model="presenca.mensagem_texto" class="campo__entrada" rows="3"
                      maxlength="4000"
                      placeholder="Ex.: Nosso expediente se encerrou. Retornamos amanhã às 8h."></textarea>
            <span class="campo__ajuda">
              Vai ao cliente quando ele escreve e o atendente da conversa está
              fora da jornada dele. No máximo uma vez a cada 12 h por conversa, e
              nunca em grupo. A conversa não é transferida.
            </span>
          </label>
          <p v-if="presenca.mensagem_ligada && !jornadaAtiva" class="aviso aviso--atencao pequeno">
            <i class="bi bi-exclamation-triangle aviso__icone" aria-hidden="true"></i>
            <span>A jornada está desligada, então ninguém está "fora do expediente" e a
            mensagem não sai. Ligue a jornada acima.</span>
          </p>
        </div>
      </section>

      <section class="cartao tela__bloco">
        <div class="cartao__corpo pilha">
          <label class="interruptor">
            <input v-model="presenca.jornada_controla_estado" type="checkbox" :disabled="salvando" />
            <span><strong>A jornada controla o status</strong></span>
          </label>
          <p class="apagado pequeno">
            No <strong>início</strong> do turno de cada atendente o status volta a
            <strong>Disponível</strong>; no <strong>fim</strong>, vai a
            <strong>Fora do expediente</strong>. Dentro do turno, com o painel
            aberto, o tempo não leva ninguém a offline -- para em
            <strong>Ausente</strong>. Precisa da jornada cadastrada em Atendentes.
          </p>
        </div>
      </section>

      <section class="cartao tela__bloco">
        <div class="cartao__corpo pilha">
          <label class="interruptor">
            <input v-model="presenca.carimbo_nome_ligado" type="checkbox" :disabled="salvando" />
            <span><strong>Carimbar o nome de quem responde na mensagem ao cliente</strong></span>
          </label>
          <p class="apagado pequeno">
            Toda mensagem enviada ao cliente começa com <strong>*Nome:*</strong> — ele
            sabe com qual atendente está falando. O painel continua sem o carimbo
            (aqui o autor de cada mensagem já aparece). No áudio, o nome vai na
            mensagem de texto que o acompanha.
          </p>
        </div>
      </section>

      <div class="linha salvar">
        <button class="botao botao--primario" type="button"
                :disabled="salvando || !presencaMudou" @click="salvarPresenca">
          {{ salvando ? 'Salvando…' : 'Salvar regras de status e mensagem' }}
        </button>
        <span v-if="presencaMudou" class="chip chip--pequeno chip--aviso">não salvo</span>
      </div>
    </template>

    <section v-if="distribuicao" class="cartao tela__bloco">
      <div class="cartao__corpo pilha">
        <label class="interruptor">
          <input v-model="distribuicao.ligada" type="checkbox" :disabled="salvando" />
          <span><strong>Distribuir sozinho a conversa que fica sem dono</strong></span>
        </label>
        <p class="apagado pequeno">
          Conversa direta, sem dono e sem time, parada desde a primeira mensagem
          do cliente que espera, vai para quem estiver escolhido abaixo. Grupos
          ficam de fora. Ao ligar, só entram conversas em que o cliente escrever
          a partir dali: as que já estavam paradas não se mexem.
        </p>
        <div class="regra">
          <label class="campo regra__campo">
            <span class="campo__rotulo">Quem recebe</span>
            <select v-model="distribuicao.primeiro_id" class="campo__entrada">
              <option :value="null">— ninguém —</option>
              <option v-for="a in podemReceber" :key="a.id" :value="a.id">{{ a.nome }}</option>
            </select>
          </label>
          <label class="campo regra__campo">
            <span class="campo__rotulo">Se estiver offline, vai para</span>
            <select v-model="distribuicao.reserva_id" class="campo__entrada">
              <option :value="null">— fica na fila —</option>
              <option v-for="a in podemReceber" :key="a.id" :value="a.id"
                      :disabled="a.id === distribuicao.primeiro_id">{{ a.nome }}</option>
            </select>
          </label>
          <label class="campo regra__campo">
            <span class="campo__rotulo">Depois de</span>
            <span class="regra__entrada">
              <input v-model="distribuicao.minutos" class="campo__entrada" type="number"
                     min="1" max="1440" />
              <span class="apagado">min</span>
            </span>
          </label>
        </div>
        <p class="apagado pequeno">
          Se as duas estiverem offline, a conversa fica na fila e a Fila e o
          Início avisam. Quem assumir antes do tempo fica com a conversa.
        </p>
        <div class="linha">
          <button class="botao botao--primario" type="button"
                  :disabled="salvando || !distribuicaoMudou" @click="salvarDistribuicao">
            Salvar distribuição
          </button>
          <span v-if="distribuicaoMudou" class="chip chip--pequeno chip--aviso">não salvo</span>
        </div>
      </div>
    </section>

    <!-- ⚠️ TRAVADO, NÃO ESCONDIDO. A chave `avaliacao_ativa` existe no banco
         desde o começo e não tinha acionador em tela nenhuma: ficava invisível.
         Aparecer cinza, dizendo o que falta, é a regra que ele aprovou. -->
    <section class="cartao tela__bloco">
      <div class="cartao__corpo pilha">
        <label class="interruptor interruptor--travado">
          <input type="checkbox" disabled
                 title="A avaliação ainda não existe no atendimento" />
          <span><strong>Pedir nota de 1 a 5 ao encerrar a conversa</strong></span>
        </label>
        <p class="aviso aviso--atencao">
          <i class="bi bi-hourglass-split aviso__icone" aria-hidden="true"></i>
          <span>
            A avaliação ainda não existe no atendimento — ligar aqui não faria
            nada. O interruptor aparece para você saber que ele existe.
          </span>
        </p>
      </div>
    </section>
      <!-- 🔵 21/10: ligado por decisão dele, depois do relatório do teste na OS
         16991. 🚨 É interruptor do SISTEMA porque muda o que acontece FORA
         deste painel: cria compromisso na OS do Harmonit.

         ⚠️ FICA NO FIM DA TELA DE PROPÓSITO. Dois testes da Geral
         escolhem a caixa pelo ÍNDICE (`caixas[2]`), e qualquer
         interruptor inserido no meio desloca os dele -- os dois ficaram
         vermelhos na primeira versão desta entrega. Recurso novo não
         entra na frente do que já estava. -->
    <section class="cartao tela__bloco">
      <div class="cartao__corpo pilha">
        <label class="interruptor">
          <input type="checkbox" :checked="harmonitLigado" :disabled="salvando"
                 @change="alternarHarmonit" />
          <span><strong>Agendar também na OS do Harmonit</strong></span>
        </label>
        <p class="apagado pequeno">
          Ligado, agendar um serviço aqui cria o compromisso do técnico na OS
          do Harmonit. Desligado, o compromisso vive só neste painel e a OS é
          citada pelo número.
        </p>
        <p class="apagado pequeno">
          O agendamento daqui <strong>não depende</strong> disto dar certo: se
          o Harmonit recusar, o compromisso continua valendo e o motivo fica
          gravado na linha, visível na tela de Agendamentos.
        </p>
      </div>
    </section>
  </div>
</template>

<style scoped>
.interruptor { display: flex; align-items: center; gap: var(--e-3); cursor: pointer; }
.interruptor input { width: 18px; height: 18px; accent-color: var(--acento); }
.interruptor--travado { cursor: not-allowed; color: var(--texto-apagado); }
.regra { display: flex; flex-wrap: wrap; gap: var(--e-4); }
.regra__campo { margin-bottom: 0; }
.regra__entrada { display: flex; align-items: center; gap: var(--e-2); }
.regra__entrada .campo__entrada { width: 7rem; }
.salvar { margin-bottom: var(--e-5); }
textarea.campo__entrada { resize: vertical; min-height: 4.5rem; }
</style>
