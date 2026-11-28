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

   🚨 UMA LEITURA DAQUI VAI AO ERP, E SÓ UMA, desde 19/11: a ficha da OS do
   card, quando ele tem OS. 🔵 Pedido dele: *"faltam trazer os dados das OS
   para os cards, no menu da direita do card aberto"* · *"igual os cards que
   são de OS do operacional"*.

   ⚠️ E ELA É SEPARADA DA OUTRA de propósito: a `/chamado/{id}` lê o nosso
   banco e não pode devolver 502 por falha de terceiro, então uma falha do
   Harmonit não pode levar o diálogo inteiro junto. São dois estados de
   carregamento e dois de erro, e o da OS é dito na própria caixa dela.

   ⚠️ O DIÁLOGO DECLARA O PRÓPRIO TETO: a `.modal__caixa` da casa impõe
   `max-width: 420px`, e teto não se vence com especificidade — só
   redeclarando. Foi o defeito que ele apontou três vezes em 05/11, e aqui ele
   voltaria inteiro, porque o `.painel__dialogo` da tela da Operação é
   `scoped` e não alcança este componente.
   ============================================================================ */
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { api, ErroDeApi } from '../api/cliente.js'
/* 🚨 O HELPER COMPARTILHADO, e nao um `<a href>` cru: link cru nao leva o
   cabecalho de sessao, e o 401 abria uma aba em branco EM SILENCIO. O
   `util/baixar.js` existe porque o mesmo defeito apareceu em tres telas. */
import { baixarArquivo } from '../util/baixar.js'
import BalaoDeRecado from './BalaoDeRecado.vue'
import { sessao } from '../estado/sessao.js'

const props = defineProps({
  card: { type: Object, required: true },
  /* ⚠️ O rótulo do botão é da TELA, não do componente: na Operação ele é
     *"Finalizar Chamado"*, palavra dele; numa aba de Pós-venda, "chamado" não
     diz nada. */
  rotuloFinalizar: { type: String, default: 'Finalizar Chamado' },
  /* 🚨 QUAL PAINEL ABRIU ESTE DIÁLOGO. A `PainelAba.vue` serve QUATRO telas
     (`PNL_1.2`, `PNL_1.3`, `PNL_1.4`, `PNL_1.5`), e a pergunta nova do
     "Finalizar" é só da etapa 888 do Contratual. Sem isto a condição seria o
     número da etapa sozinho, e no dia em que outra aba tivesse uma etapa 888 a
     pergunta apareceria onde não deve.
     ⚠️ Vazio é o caso da Operação, que monta este diálogo direto e não tem
     aba de pipeline nenhuma. */
  aba: { type: String, default: '' },
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

/* 🚨 ESTADO PRÓPRIO DA OS, e não o `lendo`/`erro` do diálogo: a leitura do
   Harmonit falha sozinha, e misturar os dois faria uma falha do ERP apagar o
   card inteiro -- que é lido do nosso banco e estava certo. */
const fichaDaOs = ref(null)
const lendoOs = ref(false)
const erroDaOs = ref('')
const temaAberto = ref('descricao')

/* ==========================================================================
   A ETAPA 888 DO CONTRATUAL — 🔵 D1 e D8 dele, 23/11
   ==========================================================================
   🔵 *"o botão 'Finalizar' do card de 'Assinado' pergunta se há termo para
   gerar OS e em caso de não, ele continua o fluxo local. Em caso de 'Sim' abre
   o modal"* (19/11) · 🔵 **D1**: o "Não" grava `resolvido` e o "Sim" grava
   `virou_os` · 🔵 **D8**: o caminho é o **C**, aba nova, e não o modal.

   🚨 **POR QUE NÃO É `final`.** Medido em 23/11 no `pipeline_etapa`: a 888
   (Assinado) é `final = true`, MAS a 889 (Não assinado) e a 890 (Desistiu de
   cancelar) também são. Condicionar por "etapa final" levaria a pergunta do
   termo para duas colunas onde ela não faz sentido nenhum.

   🚨 **POR QUE A ABA ENTRA NA CONDIÇÃO.** O número 888 é um id de
   `pipeline_etapa`, não um conceito. A aba é quem diz que estamos no
   Contratual, e as duas juntas é o que a D1 descreve.

   ⚠️ **E POR QUE AS OUTRAS ETAPAS NÃO MUDAM.** Medido: os cards 1500 e 2241
   estão na etapa 885 com `desfecho = virou_os`, e o 2588 na 885 com
   `resolvido`. O "Finalizar" já é usado fora da 888, e trocar o texto para
   todos reescreveria o significado de três cards reais. */
const ETAPA_ASSINADO = 888
const ABA_DO_CONTRATUAL = 'PNL_1.5'

/* 🚨 O ENDEREÇO PÚBLICO DO FPSL, lido em 23/11 do nginx
   (`/etc/nginx/sites-available/fpsl.conf`: `server_name fpsl.movisat.com.br`).
   ⚠️ **NÃO é o `FPSL_BASE_URL` do `.env`**, que vale `http://127.0.0.1:8004`:
   aquele é o endereço servidor-a-servidor da ponte, e o navegador de quem usa
   a tela não o alcança. Esta constante mora aqui, e não em configuração,
   porque este app não tem `VITE_*` nem rota de config que o frontend leia --
   medido hoje. No dia em que houver um segundo ambiente, isto vira campo do
   servidor, e a trava do `contratual_termo_os_2311.teste.js` avisa. */
const URL_DO_FPSL_OPERACOES = 'https://fpsl.movisat.com.br/painel/operacoes'

const observacoes = computed(() => ficha.value?.observacoes || [])

/* 🔵 27/11, ele: *"quem ve usa tudo"* · *"pode subir tudo"*.

   🚨 **A FICHA JA TRAZIA ISTO E A TELA NAO DESENHAVA.**
   `chamado.anexos` sao os arquivos que a pessoa anexou NO FORMULARIO. Eles
   chegavam ao servidor, ficavam em `formulario_arquivo`, apareciam na
   `FRM_1.1` -- e no card nao havia sinal deles. Campo que o servidor devolve e
   a tela nunca mostra e dado inalcancavel.

   ⚠️ SAO DUAS PASTAS E DUAS ROTAS: `formulario_arquivo` (o envio) e
   `os_observacao_arquivo` (o que alguem juntou numa observacao). Trocar uma
   pela outra da 404. */
const anexosDoFormulario = computed(() => ficha.value?.chamado?.anexos || [])
const baixandoAnexo = ref(null)
const erroDoAnexo = ref('')

/* ⚠️ KB e MB com uma casa, porque o que a pessoa decide com este numero e
   *"vale abrir agora ou espero o wi-fi"*. Byte cru nao responde isso. */
function tamanhoLegivel(bytes) {
  const n = Number(bytes) || 0
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${Math.round(n / 1024)} KB`
  return `${(n / 1024 / 1024).toFixed(1)} MB`
}

async function baixarAnexoDoFormulario(anexo) {
  const sid = ficha.value?.chamado?.solicitacao_id
  if (!anexo || !sid) return
  baixandoAnexo.value = anexo.id
  erroDoAnexo.value = ''
  try {
    await baixarArquivo(`/api/solicitacoes/${sid}/arquivo/${anexo.id}`,
                        anexo.nome_original || 'anexo')
  } catch (e) {
    /* 🚨 A FALHA E DITA. Esta pasta nao tem backup: 410 acontece, e a tela
       precisa dizer *"o arquivo nao esta mais aqui"* em vez de nao fazer
       nada. */
    erroDoAnexo.value = e?.message || 'Nao consegui baixar este anexo.'
  } finally {
    baixandoAnexo.value = null
  }
}
const etapas = computed(() => ficha.value?.etapas || [])
const etapaAtual = computed(() => ficha.value?.card?.etapa_id ?? null)

/* ⚠️ A FICHA PRIMEIRO, O CARD DEPOIS: a ficha é o retrato fresco (ela é relida
   a cada passagem de etapa), mas ela chega por rede e o botão existe antes
   dela. Sem o `props.card` o diálogo mostraria a pergunta ERRADA pelo tempo da
   leitura -- e tela que muda de texto sozinha é a `M12`. */
const perguntaDoTermo = computed(() =>
  props.aba === ABA_DO_CONTRATUAL
  && (etapaAtual.value ?? props.card?.etapa_id ?? null) === ETAPA_ASSINADO)

/* 🚨 OS MESMOS QUATRO TEMAS DA OPERAÇÃO, na mesma ordem e com os mesmos
   títulos: é o *"igual os cards que são de OS do operacional"* dele. O que
   muda é UMA linha -- o Agendamento, que lá acende pela situação 1316 do ERP e
   aqui não pode: 🚨 o card de uma aba tem `situacao_id` NULO de propósito (é
   esse nulo que o mantém fora do arrasto para o Harmonit). Então aqui ele
   acende pelo que a ficha respondeu, que é a única fonte que esta tela tem.

   ⚠️ VAZIO É DITO, nunca deixado em branco: caixa branca parece defeito. */
const temas = computed(() => {
  const f = fichaDaOs.value
  return [
    {
      chave: 'descricao',
      titulo: 'Descrição da OS',
      resumo: f ? (f.descricao || 'sem descrição escrita') : '…',
      texto: f?.descricao || null,
      vazio: !!f && !f.descricao,
      ligado: true,
    },
    {
      chave: 'solucao',
      titulo: 'Solução técnica',
      resumo: f ? (f.solucao_tecnica || 'sem solução técnica escrita') : '…',
      texto: f?.solucao_tecnica || null,
      vazio: !!f && !f.solucao_tecnica,
      ligado: true,
    },
    {
      chave: 'chamado',
      titulo: 'Dados do chamado',
      resumo: f
        ? (f.chamado
            ? `${f.chamado.formulario} · ${f.chamado.respostas.length} campos`
              + (f.chamado.anexos ? ` · ${f.chamado.anexos} anexo(s)` : '')
            : 'esta OS não veio de formulário')
        : '…',
      respostas: f?.chamado?.respostas || [],
      vazio: !!f && !f.chamado,
      ligado: true,
    },
    {
      chave: 'agendamento',
      titulo: 'Agendamento',
      ligado: !!f?.tem_agendamento,
      resumo: f
        ? (f.tem_agendamento
            ? `${f.agendamentos.length} compromisso(s)`
            : 'nenhum compromisso nesta OS')
        : '…',
      agendamentos: f?.agendamentos || [],
      vazio: !!f && !f.tem_agendamento,
    },
  ]
})

/* 🔵 25/11 — O TERMO POSTO A MAO (migração 120).
   📏 A razão, medida: o quadro do Contratual tem 6 cards e nenhum com termo,
   porque os seis são solicitações SEM OS -- e o termo não é campo da OS, é
   extraído de dentro dela. Ele: *"o operador coloca a mão no card, pois só
   depois de assinado que ele será gerado oficialmente"*.
   ⚠️ O campo só existe no Contratual, pela `aba` que o diálogo já recebe. */
const termo = ref(props.card.termo || '')
const salvandoTermo = ref(false)
const erroDoTermo = ref('')

/* 🚨 SÓ quando o número é do OPERADOR. Com a OS no card o termo é o oficial e
   não se digita por cima: deixar o campo editável ali faria a tela prometer
   uma escrita que a regra do servidor ignora (`M12`). */
const podePorTermo = computed(() =>
  props.aba === ABA_DO_CONTRATUAL && !props.card.numero_os)

/* ⚠️ Reabrir o diálogo em outro card tem de trazer o número DAQUELE card. */
watch(() => props.card.id, () => {
  termo.value = props.card.termo || ''
  erroDoTermo.value = ''
})

async function salvarTermo() {
  if (salvandoTermo.value) return
  salvandoTermo.value = true
  erroDoTermo.value = ''
  try {
    await api.post(`/api/paineis/operacao/chamado/${props.card.id}/termo`,
                   { termo: termo.value.trim() })
    /* `mudou` para o quadro reler: o card fechado mostra o termo na linha 1, e
       sem reler ele continuaria com o número antigo até a próxima abertura. */
    emit('mudou')
  } catch (e) {
    erroDoTermo.value = e instanceof ErroDeApi
      ? e.message : 'Não consegui salvar o número do termo.'
  } finally {
    salvandoTermo.value = false
  }
}

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

/* 🚨 A OS SÓ É PEDIDA SE O CARD TIVER OS, e o número sai do CARD no servidor:
   o chamado de verdade não tem OS, e pedir por ele seria um 404 por desenho.
   ⚠️ 404 aqui é *"este card não tem OS"* e não é erro de tela: o diálogo
   simplesmente não mostra a caixa. */
async function carregarOs() {
  fichaDaOs.value = null
  erroDaOs.value = ''
  if (!props.card?.numero_os) return
  lendoOs.value = true
  try {
    fichaDaOs.value = await api.get(
      `/api/paineis/operacao/chamado/${props.card.id}/os`)
  } catch (e) {
    /* 🚨 ERRO, NÃO CAIXA VAZIA: ficha vazia é indistinguível de OS sem dados,
       e quem lê concluiria que não há o que ver. */
    erroDaOs.value = e instanceof ErroDeApi
      ? e.message : 'Não deu para ler a OS no Harmonit agora.'
  } finally {
    lendoOs.value = false
  }
}

onMounted(async () => {
  focar()
  await Promise.all([carregarFicha(), carregarOs()])
})

watch(() => props.card?.id, async (novo, velho) => {
  if (novo && novo !== velho) {
    perguntandoDesfecho.value = false
    recado.value = ''
    temaAberto.value = 'descricao'
    await Promise.all([carregarFicha(), carregarOs()])
  }
})

/* 🔵 *"Resolvido"* ou *"Não resolvido"* -- e, na etapa 888 do Contratual,
   *"Não"* ou *"Sim"* (D1, 23/11), com os MESMOS dois desfechos.
   🚨 Os dois SÓ MARCAM — decisão dele: *"só marca; a OS é pelo Operação"*.
   Nada escreve no ERP, e é isso que torna o botão reversível.
   ⚠️ Nem o *"Sim"*: abrir o FPSL é NAVEGAR, não escrever. A OS continua
   nascendo pelas mãos de quem chega lá. */
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

/* 🔵 11/11: apagar observação. Apaga **qualquer pessoa com o painel**
   (decisão dele) e **sem janela de tempo**. ⚠️ O conteúdo só o owner vê, e quem
   esconde é o servidor -- aqui só se decide o botão. */
const souOwner = computed(() => Boolean(sessao.usuario?.owner))

async function apagarRecado(recado) {
  if (!recado) return
  erro.value = ''
  try {
    await api.post(`/api/paineis/operacao/observacao/${recado.id}/apagar`, {})
    await carregarFicha()
    emit('mudou')
  } catch (e) {
    erro.value = e instanceof ErroDeApi
      ? e.message : 'Não consegui excluir esta observação.'
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

/* 🔵 27/11, ele: *"ja pode colocar o campo de OBS nas mesmas regras dos demais
   paineis - com anexo, historico"*.

   🚨 **O QUE A MEDIÇÃO MOSTROU, E MUDOU O PEDIDO:** subir arquivo numa
   observação estava escrito **só** na `PainelOperacao.vue`. Este diálogo --
   o de Compras, Contratual, Financeiro e Pós-venda -- baixava anexo que já
   existisse e **não tinha como anexar**. Então *"as mesmas regras dos demais
   painéis"* era, até hoje, SEM anexo.

   ⚠️ **ESTE ARQUIVO SERVE QUATRO TELAS DELE.** O caminho antigo -- salvar
   observação sem anexo -- não muda em nada, e é a primeira coisa que o
   `obs_anexo_no_dialogo_2711.teste.js` mede. Foi o erro de 25/11 (mexer na
   tela compartilhada mudou quatro painéis sem ele pedir) que põe essa trava
   aqui. */
const anexoEscolhido = ref(null)

function escolherAnexo(evento) {
  anexoEscolhido.value = evento.target.files?.[0] || null
  erroDoRecado.value = ''
}

function tirarAnexo() {
  anexoEscolhido.value = null
  /* ⚠️ Limpa o `<input type=file>` também: sem isto, escolher o MESMO arquivo
     de novo não dispara `change` e a tela ficaria sem o anexo em silêncio. */
  const campo = document.getElementById(`obs-anexo-${props.card.id}`)
  if (campo) campo.value = ''
}

/* 🚨 `fetch` cru, e não `api.post`: arquivo vai por `FormData`, e o navegador
   precisa montar o `Content-Type` com o boundary. Definir o cabeçalho na mão
   quebra o upload EM SILÊNCIO, com o servidor recebendo corpo vazio. */
async function subirAnexoDaObservacao(observacaoId, arquivo) {
  const forma = new FormData()
  forma.append('arquivo', arquivo)
  const r = await fetch(
    `/api/paineis/operacao/observacao/${observacaoId}/anexo`,
    { method: 'POST',
      headers: { Authorization: `Bearer ${localStorage.getItem('movizap.token')}` },
      body: forma })
  const texto = await r.text()
  let corpo = null
  try { corpo = JSON.parse(texto) } catch { corpo = null }
  if (!r.ok) {
    throw new Error((corpo && corpo.detail) || `Falha no anexo (${r.status}).`)
  }
  return corpo
}

async function salvarRecado() {
  const texto = (recado.value || '').trim()
  const arquivo = anexoEscolhido.value
  const sid = ficha.value?.chamado?.solicitacao_id
  /* 🔵 27/11 -- O DEFEITO QUE A KARLA ACHOU, e ele era SILÊNCIOSO.
     Esta função lia **só** `ficha.chamado.solicitacao_id`. Num card de **OS** a
     ficha não traz `chamado` nenhum -- o servidor só o monta quando o card tem
     `solicitacao_id` --, então o `sid` vinha vazio e a função **retornava sem
     fazer nada**: nenhum pedido, nenhuma mensagem, nenhum erro no console. O
     botão Salvar parecia morto.
     📏 Medido: o Financeiro tem **13 cards que são só OS** de 19, e o
     Contratual tem **zero** -- é por isso que ela viu lá e ninguém viu aqui.
     ⚠️ É ANTERIOR à entrega de hoje: o arquivo de antes tem o mesmo
     `if (!texto || !sid) return`. */
  const numeroOs = props.card?.numero_os
    || ficha.value?.card?.numero_os || null
  /* 🚨 SEM DONO NÃO SE MANDA: o CHECK `os_observacao_tem_um_dono` exige OS
     **ou** chamado. Card sem os dois não deveria existir, e se existir a tela
     não pode mandar um pedido que o banco vai recusar. */
  if ((!texto && !arquivo) || (!sid && !numeroOs)) return
  enviandoRecado.value = true
  erroDoRecado.value = ''
  try {
    /* ⚠️ O anexo pende de uma observação, então ela vem primeiro. Sem texto,
       um é inventado com o nome do arquivo -- a rota recusa texto vazio (422),
       e anexo solto não se explica sozinho daqui a três meses. É a mesma frase
       da Operação. */
    const corpo = { texto: texto || `(anexo) ${arquivo.name}` }
    /* 🚨 SÃO DUAS ROTAS, E A DIFERENÇA NÃO É ESTILO: a do chamado grava
       `solicitacao_id`, a da OS grava `numero_os`. Mandar uma pela outra dá
       recado sem dono, que o CHECK recusa. */
    const r = sid
      ? await api.post('/api/paineis/operacao/chamado/observacao',
                       { ...corpo, solicitacao_id: sid })
      : await api.post('/api/paineis/operacao/observacao',
                       { ...corpo, numero_os: numeroOs })
    /* 🚨 A LISTA VEM DA RESPOSTA DA ROTA, e isto é GARANTIA ANTIGA desta
       tela: a observação aparece **sem recarregar a ficha**. Eu a troquei por
       uma releitura ao por o anexo e o `painel_chamados_0511.teste.js` me
       pegou -- entrega que muda comportamento garantido sem ele pedir é o
       mesmo defeito da `M12`, pelo avesso. */
    ficha.value = { ...ficha.value, observacoes: r.observacoes || [] }

    /* 🚨 AS DUAS RESPOSTAS TÊM FORMAS DIFERENTES: a do chamado devolve
       `{id, observacoes}`; a da OS devolve `{numero_os, observacoes}`, **sem
       `id`**. Então o id do recado novo é o da resposta, ou o `[0]` da lista.
       ⚠️ E `[0]` É O NOVO: as duas consultas de `passagem` ordenam
       `o.em DESC, o.id DESC` -- da mais nova para a mais velha. Eu havia
       escrito aqui, hoje, que vinham da mais antiga para a mais nova; errado.
       Quem inverte é o TEMPLATE, na hora de desenhar. */
    const idDoRecado = r?.id ?? (r?.observacoes || [])[0]?.id ?? null

    if (arquivo && idDoRecado) {
      try {
        await subirAnexoDaObservacao(idDoRecado, arquivo)
      } catch (e) {
        /* 🚨 A OBSERVAÇÃO JÁ ESTÁ GRAVADA, e a tela tem de dizer isso: sem a
           primeira frase, quem lê o erro acha que nada foi salvo e escreve
           tudo de novo. ⚠️ O arquivo não fica solto no disco -- a rota recusa
           extensão e tamanho ANTES de escrever. */
        erroDoRecado.value = 'A observação foi salva, mas o anexo não: '
          + (e?.message || 'falha ao anexar.')
        await carregarFicha()
        emit('mudou')
        return
      }
      /* ⚠️ E SÓ COM ANEXO SE RELÊ: os anexos de cada observação não vêm na
         resposta da rota, só na ficha. Sem anexo, a releitura seria uma ida à
         rede para não mudar nada -- e mataria a garantia de cima. */
      await carregarFicha()
    }

    recado.value = ''
    anexoEscolhido.value = null
    tirarAnexo()
    emit('mudou')
  } catch (e) {
    erroDoRecado.value = e instanceof ErroDeApi
      ? e.message
      : (e?.message || 'Não deu para salvar a observação.')
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
          <!-- 🔵 12/11, dele: *"pode ocultar essa barra ou transformá-la em
               lista, como no OP"* → *"A"*. A barra de passos numerados de
               11/11 saiu: 📏 com as 10 etapas do Financeiro sobravam 6 ou 7
               letras por passo, e ele leu "1. Nova s…" na tela.
               ⚠️ Um card arquivado não se move: reabrir primeiro é o gesto, e
               oferecer os dois ao mesmo tempo deixaria o estado ambíguo —
               por isso o `<strong>` no `v-else`, que continua DIZENDO a etapa
               mesmo quando não deixa mudar. -->
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
          <!-- 🔵 25/11 — O NÚMERO DO TERMO, posto pelo operador. Fica no topo
               da coluna porque é o identificador do contrato, e é o que ele
               carrega para o FPSL quando clica "Sim" no Finalizar.
               ⚠️ A frase diz POR QUE existe o campo: número que ainda não
               nasceu oficialmente não está em lugar nenhum do sistema. -->
          <section v-if="podePorTermo" class="modal__painel">
            <h3>Número do termo</h3>
            <p class="nota pequeno">
              O termo oficial só nasce com a OS. Até lá, o número vai aqui.
            </p>
            <div class="termo__linha">
              <input v-model="termo" class="campo campo--termo" type="text"
                     maxlength="20" placeholder="12345"
                     :disabled="salvandoTermo" />
              <button class="botao botao--contorno" type="button"
                      :disabled="salvandoTermo" @click="salvarTermo">
                <i class="bi bi-check2" aria-hidden="true"></i>
                Salvar termo
              </button>
            </div>
            <p v-if="erroDoTermo" class="nota pequeno erro">{{ erroDoTermo }}</p>
            <p v-else-if="card.termo_a_mao && card.termo_por_nome"
               class="nota pequeno">
              posto por {{ card.termo_por_nome }}
            </p>
          </section>

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

            <!-- 🔵 27/11: OS ANEXOS DO FORMULÁRIO.
                 🚨 `v-if` na lista, e não um cabeçalho fixo: card sem anexo
                 ganharia um título com nada embaixo, que é o que parece
                 defeito -- a mesma régua da caixa "A OS no Harmonit" logo
                 abaixo. -->
            <div v-if="anexosDoFormulario.length" class="anexo__bloco">
              <p class="anexo__titulo">Anexos do formulário</p>
              <ul class="anexo__lista">
                <li v-for="a in anexosDoFormulario" :key="a.id">
                  <button class="anexo__baixar" type="button"
                          :disabled="baixandoAnexo === a.id"
                          @click="baixarAnexoDoFormulario(a)">
                    <i class="bi bi-download" aria-hidden="true"></i>
                    {{ a.nome_original || 'anexo' }}
                    <span class="anexo__peso">{{ tamanhoLegivel(a.bytes) }}</span>
                  </button>
                </li>
              </ul>
              <p v-if="erroDoAnexo" class="aviso aviso--erro pequeno"
                 role="alert">{{ erroDoAnexo }}</p>
            </div>
          </section>

          <section class="modal__painel">
            <h3>Observações <span class="pilula">{{ observacoes.length }}</span></h3>
            <ul v-if="observacoes.length" class="recados">
              <BalaoDeRecado v-for="o in [...observacoes].reverse()"
                             :key="o.id" :recado="o" :quando="quando"
                             :sou-owner="souOwner" :pode-apagar="true"
                             @apagar="apagarRecado" />
            </ul>
            <p v-else class="nota pequeno">Nenhuma observação ainda.</p>

            <div class="modal__rodape--escrever">
              <textarea v-model="recado" rows="2" :disabled="enviandoRecado"
                        placeholder="o que a análise deste card precisa registrar"
                        aria-label="Escrever observação"></textarea>

              <!-- 🔵 27/11: o anexo da observação, que até hoje só existia na
                   Operação. 🚨 BOTÃO COM RÓTULO, não só ícone: `title` não é
                   rótulo -- o balão do navegador demora cerca de um segundo e
                   não existe em toque. -->
              <div class="modal__pe">
                <label class="botao botao--contorno obs__anexar"
                       :class="{ 'botao--ocupado': enviandoRecado }">
                  <i class="bi bi-paperclip" aria-hidden="true"></i>
                  Anexar
                  <input :id="`obs-anexo-${card.id}`" class="so-leitor"
                         type="file" :disabled="enviandoRecado"
                         @change="escolherAnexo" />
                </label>

                <span v-if="anexoEscolhido" class="obs__escolhido">
                  {{ anexoEscolhido.name }}
                  <button class="obs__tirar" type="button"
                          :disabled="enviandoRecado"
                          aria-label="Tirar o anexo escolhido"
                          @click="tirarAnexo">✕</button>
                </span>

                <button class="botao obs__salvar" type="button"
                        :disabled="enviandoRecado
                                   || (!recado.trim() && !anexoEscolhido)"
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
          <!-- 🔵 19/11, dele: *"faltam trazer os dados das OS para os cards, no
               menu da direita do card aberto"* · *"igual os cards que são de OS
               do operacional"*. 🚨 A caixa só existe quando o card TEM OS --
               num chamado de verdade ela seria um cabeçalho com nada embaixo,
               que é o que parece defeito. -->
          <template v-if="card.numero_os">
            <p class="modal__secao">A OS no Harmonit</p>
            <section class="modal__painel modal__temas">
              <h3>OS {{ card.numero_os }}</h3>
              <p v-if="lendoOs" class="nota pequeno">Lendo a OS no Harmonit…</p>
              <p v-else-if="erroDaOs" class="aviso aviso--erro" role="alert">
                {{ erroDaOs }}
              </p>

              <div class="temas__abas" role="tablist">
                <button v-for="t in temas" :key="t.chave" type="button"
                        role="tab" class="temas__aba"
                        :class="{ 'temas__aba--ativa': temaAberto === t.chave,
                                  'temas__aba--apagada': !t.ligado }"
                        :aria-selected="temaAberto === t.chave"
                        :disabled="!t.ligado"
                        @click="temaAberto = t.chave">
                  <strong>{{ t.titulo }}</strong>
                  <span class="temas__resumo">{{ t.resumo }}</span>
                </button>
              </div>

              <div v-for="t in temas" :key="`c-${t.chave}`" class="temas__corpo">
                <template v-if="temaAberto === t.chave">
                  <p v-if="t.vazio" class="nota pequeno">{{ t.resumo }}</p>

                  <pre v-else-if="t.texto" class="temas__texto">{{ t.texto }}</pre>

                  <!-- os dados do chamado, com RÓTULO e nunca a chave do Bitrix -->
                  <dl v-else-if="t.respostas && t.respostas.length"
                      class="temas__respostas">
                    <template v-for="r in t.respostas" :key="r.nome">
                      <dt>{{ r.rotulo }}</dt>
                      <dd>{{ Array.isArray(r.valor) ? r.valor.join(' · ') : r.valor }}</dd>
                    </template>
                  </dl>

                  <ul v-else-if="t.agendamentos && t.agendamentos.length"
                      class="temas__respostas">
                    <li v-for="a in t.agendamentos" :key="a.agendamento_id">
                      {{ a.nome || `usuário ${a.usuario_id}` }} —
                      <template v-if="a.janela">{{ a.janela }} · </template>compromisso {{ a.agendamento_id }}
                    </li>
                  </ul>

                  <p v-else class="nota pequeno">{{ t.resumo }}</p>
                </template>
              </div>
            </section>
          </template>

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
            <!-- 🔵 D1, 23/11: NA ETAPA 888 DO CONTRATUAL a pergunta é outra.
                 🚨 Os dois botões gravam os MESMOS dois desfechos, na mesma
                 ordem: "Não" grava `resolvido` (o que "Resolvido" já gravava)
                 e "Sim" grava `virou_os` (o que "Não resolvido" já gravava).
                 Nenhum payload muda, nenhuma migração, e o `DESFECHOS` do
                 `pipeline.py` não foi tocado. -->
            <span v-else-if="perguntaDoTermo" class="desfecho__pergunta">
              <span class="desfecho__rotulo">Há termo para gerar OS?</span>
              <!-- 🔵 D8: o "Sim" abre o FPSL em ABA NOVA (caminho C).
                   ⚠️ **ÂNCORA, NÃO `window.open`** -- a lição está no
                   `ModalKm.vue`: *"bloqueador de pop-up come `window.open` sem
                   aviso, e aí o clique não faria nada e pareceria defeito"*. A
                   navegação nativa de um `<a target="_blank">` nunca é
                   bloqueada, e o `@click` grava o desfecho no mesmo gesto.
                   🚨 `rel="noopener"`: sem isto a aba do FPSL ganharia
                   `window.opener` e poderia navegar a nossa.
                   ⚠️ Se o POST falhar a aba já abriu. É aceitável e reversível:
                   nada foi escrito no ERP, o erro aparece aqui, e o card segue
                   sem desfecho -- o "Reabrir" existe para o caso inverso. -->
              <!-- ⚠️ `<a>` NÃO ACEITA `disabled`: os irmãos são `<button>` e
                   param sozinhos durante o POST, este não. Sem a classe, dois
                   cliques mandariam dois POST, e o segundo volta com *"este
                   card já foi finalizado"* -- erro vermelho numa ação que deu
                   certo. `pointer-events: none` é o que de fato segura. -->
              <a class="botao" :class="{ 'desfecho__sim--inerte': finalizando }"
                 :href="URL_DO_FPSL_OPERACOES"
                 target="_blank" rel="noopener noreferrer"
                 :aria-disabled="finalizando ? 'true' : 'false'"
                 @click="finalizar('virou_os')">Sim</a>
              <button class="botao botao--contorno" type="button"
                      :disabled="finalizando"
                      @click="finalizar('resolvido')">Não</button>
              <button class="botao botao--fantasma" type="button"
                      :disabled="finalizando"
                      @click="perguntandoDesfecho = false">Cancelar</button>
            </span>
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
/* ⚠️ 190px: largura do `<select>` de etapas. Sem um mínimo, ele encolhe para
   o tamanho da opção escolhida e muda de largura a cada troca -- a faixa
   inteira dançava. */
.faixa__select { min-width: 190px; }

/* 🚨 UMA rolagem só, e é esta: duas rolagens empilhadas (o palco e o corpo)
   foi um dos defeitos de 05/11. */
.modal__corpo {
  display: grid; gap: var(--e-5);
  padding: var(--e-5);
  overflow-y: auto;
}
.modal__corpo--duas { grid-template-columns: 1.3fr 1fr; }
/* O campo e o botão na MESMA linha, e o campo cresce: número de 5 dígitos num
   campo de largura total ao lado de um botão pequeno fica desequilibrado.
   ⚠️ `min-width: 0` para o campo poder encurtar em coluna estreita em vez de
   empurrar o botão para fora. */
.termo__linha { display: flex; gap: var(--e-2); align-items: center; }
/* ⚠️ A regra e da CLASSE, nao do descendente: a 12ª conferência de CSS
   reprovou o build porque `campo--termo` estava escrita no template e não
   existia em CSS nenhum -- a trava achou a própria órfã que eu criei, no
   dia em que ela nasceu. E a classe diz o PAPEL, que é o que a trava de
   tela também seleciona (`M13`). */
.campo--termo { flex: 1 1 auto; min-width: 0; }
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
/* 🚨 AS CLASSES `temas__*` SÃO REDECLARADAS AQUI, e não herdadas: as da
   Operação vivem no `<style scoped>` daquela TELA e não alcançam este
   componente. Foi a lição de 05/11 com o `max-width` do modal, e a de 12/11
   com a `.pilula`: nome de classe igual não é estilo igual. */
.modal__temas { display: flex; flex-direction: column; gap: var(--e-2); }
.temas__abas { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: var(--e-2); }
.temas__aba {
  text-align: left; min-height: 56px; padding: var(--e-2) var(--e-3);
  border: var(--borda-fina) solid var(--borda); border-radius: var(--r-sm, 6px);
  background: var(--superficie); color: var(--texto); cursor: pointer;
  display: flex; flex-direction: column; gap: 2px;
  transition: border-color .15s ease, box-shadow .15s ease;
}
.temas__aba:hover:not(:disabled) { box-shadow: var(--sombra-1); }
.temas__aba--ativa { border-color: var(--acento); box-shadow: var(--sombra-1); }
.temas__aba--apagada { border-style: dashed; opacity: .65; cursor: not-allowed; }
.temas__resumo { font-size: var(--txt-xs); color: var(--texto-fraco); }
.temas__corpo:empty { display: none; }
.temas__texto {
  margin: 0; white-space: pre-wrap; word-break: break-word;
  font-family: inherit; font-size: var(--txt-sm);
  background: var(--superficie-2); border-radius: var(--r-sm, 6px);
  padding: var(--e-3); max-height: 240px; overflow-y: auto;
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
/* 🔵 27/11 -- os anexos do formulário no card aberto. 🚨 Toda classe composta
   usada no template precisa de regra publicada, senão o navegador a ignora EM
   SILÊNCIO: é a 12ª conferência do `npm run build`. */
.anexo__bloco { margin-top: var(--e-3); }
.anexo__titulo {
  margin: 0 0 var(--e-2);
  font-size: var(--txt-xs); font-weight: var(--peso-forte);
  letter-spacing: .04em; text-transform: uppercase;
  color: var(--texto-apagado);
}
.anexo__lista {
  list-style: none; margin: 0; padding: 0;
  display: flex; flex-wrap: wrap; gap: var(--e-2);
}
.anexo__baixar {
  display: inline-flex; align-items: center; gap: var(--e-1);
  max-width: 260px; padding: var(--e-1) var(--e-2);
  font: inherit; font-size: var(--txt-sm);
  color: var(--acento); background: var(--acento-suave);
  border: var(--borda-fina) solid var(--acento-borda);
  border-radius: var(--r-full);
  cursor: pointer;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.anexo__baixar:hover:not(:disabled) { background: var(--superficie-2); }
.anexo__baixar:disabled { color: var(--texto-fraco); cursor: progress; }
.anexo__peso { flex-shrink: 0; font-size: var(--txt-xs); color: var(--texto-fraco); }

/* 🔵 27/11 -- o anexo da observação. 🚨 Toda classe composta usada no
   template precisa de regra publicada, senão o navegador a ignora EM SILÊNCIO
   e o elemento sai sem forma: é a 12ª conferência do `npm run build`, e ela já
   me pegou uma órfã hoje. */
.obs__anexar { cursor: pointer; }
.obs__escolhido {
  display: inline-flex; align-items: center; gap: var(--e-1);
  max-width: 220px; padding: 2px var(--e-2);
  font-size: var(--txt-sm); color: var(--texto-fraco);
  background: var(--superficie-2);
  border: var(--borda-fina) solid var(--borda);
  border-radius: var(--r-full);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.obs__tirar {
  flex-shrink: 0; padding: 0 2px; border: 0; background: transparent;
  color: var(--texto-fraco); font: inherit; line-height: 1; cursor: pointer;
}
.obs__tirar:hover:not(:disabled) { color: var(--erro); }
/* ⚠️ Piso de largura porque o rótulo troca para *"Salvando…"*, que é mais
   curto: sem ele o botão encolhe debaixo do dedo no instante do clique. */
.obs__salvar { min-width: 10ch; }

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
/* 🚨 O "Sim" da etapa 888 é uma `<a>`, não um `<button>` (D8: aba nova, e
   âncora não é comida por bloqueador de pop-up -- lição do `ModalKm.vue`).
   ⚠️ O `estilo/base.css:37` tem `a:hover { text-decoration: underline }`, e o
   `.botao:hover` só mexe no fundo: sem esta linha o "Sim" sublinharia no hover
   e os três botões da pergunta pareceriam de famílias diferentes. Nenhum teste
   de jsdom veria isso -- ele não faz layout. */
.desfecho__pergunta a.botao:hover { text-decoration: none; }
/* ⚠️ Nome PRÓPRIO e não `.botao:disabled`: este componente é `scoped`, e
   reusar um nome que já existe no global faria trava-por-texto virar sorteio.
   📏 `.5` é a mesma opacidade do `.botao:disabled` do `componentes.css`. */
.desfecho__sim--inerte { opacity: .5; pointer-events: none; }
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
