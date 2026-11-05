<script setup>
/* ============================================================================
   TEC_1.1 — a FICHA de um técnico, em tela própria.
   ----------------------------------------------------------------------------
   🔵 04/11, segunda volta, decisão dele: *"não gosto desse modelo de quando
   clico em 'abrir ficha', ele cria uma pagina em cima da atual. fica feio (...)
   indico o uso de modais para abrir um novo quadro, ou ir para outra tela
   objetiva só para isso. Com seta de voltar."* Escolhida a **tela própria**: a
   ficha tem sete blocos, e num modal ela rolaria dentro de uma caixa, com duas
   barras de rolagem. Tela própria também dá link direto para uma ficha.

   🔵 *"o botão pode chamar 'Ficha' pois as vezes é só uma consulta aos dados
   dele"* — e é por isso que esta tela abre para **todo atendente**. Só os
   botões de gravar dependem da `TEC_1.2`.

   🚨 A SETA VOLTA PARA A LISTA, E GUARDA O FILTRO. Ela usa `router.back()`
   quando há história, e cai em `/tecnicos` quando alguém chegou por link
   direto — voltar para a primeira página de uma lista filtrada seria perder o
   lugar de quem estava trabalhando.

   ⚠️ O BLOCO DO HARMONIT SAIU. *"o campo 'tecnico no hamronit não tem uso
   dentro da ficha do tecnico'"* — no lugar há o **acesso**: o e-mail com que
   ele entra lá, estático, porque não há edição. A senha não é exibida porque
   **não existe em lugar nenhum que eu alcance** (ver o aviso no `main.py`), e
   mostrar uma derivação seria exibir adivinhação como se fosse dado.
   ============================================================================ */
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { api, ErroDeApi } from '../api/cliente.js'
import { sessao } from '../estado/sessao.js'

const route = useRoute()
const router = useRouter()

const podeEscrever = computed(
  () => sessao.telas.some((t) => t.codigo === 'TEC_1.2'))

const contatoId = computed(() => Number(route.params.contatoId))

const dados = ref(null)
const form = ref({})
const precos = ref({})
const acesso = ref(null)
const sugestao = ref(null)
const carregando = ref(true)
const salvando = ref(false)
const erro = ref('')
const recado = ref('')

const ESTADOS = {
  candidato: 'Candidato', credenciado: 'Credenciado', recusado: 'Recusado',
}

const FORMAS = [
  { valor: 'pix', rotulo: 'PIX' },
  { valor: 'ted', rotulo: 'TED / depósito em conta' },
  { valor: 'boleto', rotulo: 'Boleto' },
]

const UFS = ['AC', 'AL', 'AP', 'AM', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 'MT',
  'MS', 'MG', 'PA', 'PB', 'PR', 'PE', 'PI', 'RJ', 'RN', 'RS', 'RO', 'RR', 'SC',
  'SP', 'SE', 'TO']

/* Um lugar só para o dinheiro ir e vir. `Number('199,90')` é NaN e
   `parseFloat('199,90')` devolve 199 — daí a vírgula trocada antes, e o
   arredondamento no inteiro para 199,90 não virar 19989 por ponto flutuante. */
function paraCentavos(texto) {
  const limpo = String(texto ?? '').replace(/\s/g, '').replace(',', '.')
  if (!limpo) return null
  const n = Number(limpo)
  if (!Number.isFinite(n) || n < 0) return undefined   // undefined = recusar
  return Math.round(n * 100)
}

function paraReais(centavos) {
  if (centavos === null || centavos === undefined) return ''
  return (centavos / 100).toFixed(2).replace('.', ',')
}

const titulo = computed(() => {
  if (!dados.value) return 'Ficha do técnico'
  return dados.value.ficha?.nome_fantasia
    || dados.value.contato.harmonit_tecnico_nome
    || dados.value.contato.nome
})

async function carregar() {
  carregando.value = true
  erro.value = ''
  try {
    const r = await api.get(`/api/tecnicos/${contatoId.value}`)
    dados.value = r
    form.value = { ...(r.ficha || {}) }
    form.value.km_valor_reais = paraReais(r.ficha?.km_valor_centavos ?? null)
    precos.value = {}
    for (const p of r.precos) precos.value[p.servico_id] = paraReais(p.custo_centavos)
    await carregarAcesso()
    if (route.query.solicitacao) await puxarSugestao(route.query.solicitacao)
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Falha ao abrir a ficha.'
  } finally {
    carregando.value = false
  }
}

onMounted(carregar)

function voltar() {
  /* ⚠️ `back()` só quando há de onde voltar: quem abriu por link direto cairia
     fora do painel. */
  if (window.history.length > 1) router.back()
  else router.push('/tecnicos')
}

async function carregarAcesso() {
  acesso.value = null
  try {
    acesso.value = await api.get(`/api/contatos/${contatoId.value}/tecnico-harmonit`)
  } catch { /* ponte fora do ar NÃO é "sem acesso" — a tela diz isso */ }
}

async function puxarSugestao(solicitacaoId) {
  try {
    const r = await api.get(`/api/tecnicos/da-solicitacao/${solicitacaoId}`)
    sugestao.value = r
    /* 🚨 PREENCHE O FORMULÁRIO, NÃO O BANCO. Nada é gravado até alguém salvar. */
    for (const [campo, valor] of Object.entries(r.sugestao || {})) {
      if (valor !== null && valor !== undefined) form.value[campo] = valor
    }
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Falha ao ler a solicitação.'
  }
}

async function salvar() {
  /* 🚨 OS NÚMEROS SE CONFEREM ANTES DE QUALQUER CHAMADA: a ficha e os preços
     são duas rotas, e um valor impossível no meio deixaria metade salva. */
  const km = paraCentavos(form.value.km_valor_reais)
  if (km === undefined) { erro.value = 'O valor do km não é um número.'; return }

  const mapa = {}
  for (const s of dados.value.precos) {
    const c = paraCentavos(precos.value[s.servico_id])
    if (c === undefined) { erro.value = `O valor de ${s.nome} não é um número.`; return }
    mapa[s.servico_id] = c
  }

  salvando.value = true
  erro.value = ''
  try {
    const corpo = { ...form.value }
    corpo.km_valor_centavos = km
    delete corpo.km_valor_reais
    delete corpo.km_valor_texto
    if (sugestao.value) corpo.solicitacao_id = sugestao.value.solicitacao_id

    await api.put(`/api/tecnicos/${contatoId.value}`, corpo)
    await api.put(`/api/tecnicos/${contatoId.value}/precos`, { precos: mapa })

    recado.value = 'Ficha salva.'
    sugestao.value = null
    await carregar()
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui salvar.'
  } finally {
    salvando.value = false
  }
}

async function mudarEstado(novo) {
  salvando.value = true
  erro.value = ''
  try {
    await api.put(`/api/tecnicos/${contatoId.value}/estado`,
                  { estado: novo, nota: form.value.estado_nota || null })
    recado.value = novo === 'credenciado' ? 'Técnico credenciado.'
      : novo === 'recusado' ? 'Credenciamento recusado.' : 'Volta a candidato.'
    await carregar()
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui mudar o estado.'
  } finally {
    salvando.value = false
  }
}

/* ------------------------------------------------------------------- CEP --
   🚨 TRÊS RESPOSTAS, E A TELA PRECISA DAS TRÊS. A rota devolve `achado: true`
   com o endereço, `achado: false` quando o CEP não existe, e **503** quando não
   deu para perguntar. Tratar os dois últimos como um só faria a tela acusar de
   errado um CEP certo que ela não conseguiu conferir.
   ⚠️ E o NÚMERO nunca é preenchido: o ViaCEP não sabe o número. */
const cepEstado = ref('')      // '', 'procurando', 'nao_existe', 'indisponivel'

async function buscarCep() {
  const cep = String(form.value.cep || '').replace(/\D/g, '')
  cepEstado.value = ''
  if (cep.length !== 8) return
  cepEstado.value = 'procurando'
  try {
    const r = await api.get(`/api/cep/${cep}`)
    if (r.achado) {
      form.value.logradouro = r.logradouro || form.value.logradouro
      form.value.bairro = r.bairro || form.value.bairro
      form.value.cidade = r.cidade || form.value.cidade
      form.value.uf = r.uf || form.value.uf
      cepEstado.value = ''
    } else {
      cepEstado.value = 'nao_existe'
    }
  } catch {
    cepEstado.value = 'indisponivel'
  }
}
</script>

<template>
  <div class="tela">
    <!-- 🔵 A seta de voltar que ele pediu. -->
    <header class="ficha__topo">
      <button class="botao botao--fantasma botao--pequeno" type="button"
              aria-label="Voltar para a lista de técnicos" @click="voltar">
        <i class="bi bi-arrow-left" aria-hidden="true"></i> Voltar
      </button>
      <div class="ficha__titulo">
        <h1>{{ titulo }}</h1>
        <span v-if="dados?.ficha" class="chip" :class="{
          'chip--ok': dados.ficha.estado === 'credenciado',
          'chip--acento': dados.ficha.estado === 'candidato' }">
          {{ ESTADOS[dados.ficha.estado] || dados.ficha.estado }}
        </span>
        <span v-else-if="dados" class="chip">sem ficha</span>
      </div>
    </header>

    <p v-if="carregando" class="linha fraco">
      <span class="girando"></span> Lendo…
    </p>

    <p v-else-if="!dados" class="aviso aviso--erro" role="alert">
      <i class="bi bi-exclamation-octagon aviso__icone" aria-hidden="true"></i>
      <span>{{ erro || 'Não achei este técnico.' }}</span>
    </p>

    <template v-else>
      <p v-if="!podeEscrever" class="apagado pequeno">
        Esta ficha está aberta para consulta. Alterar os dados, mexer no valor dos
        serviços e credenciar não é possível por aqui.
      </p>

      <p v-if="erro" class="aviso aviso--erro" role="alert">
        <i class="bi bi-exclamation-octagon aviso__icone" aria-hidden="true"></i>
        <span>{{ erro }}</span>
      </p>

      <p v-if="recado" class="aviso aviso--ok" role="status">
        <i class="bi bi-check2-circle aviso__icone" aria-hidden="true"></i>
        <span>{{ recado }}</span>
      </p>

      <div v-if="sugestao" class="aviso aviso--atencao">
        <i class="bi bi-clipboard-check aviso__icone" aria-hidden="true"></i>
        <div>
          <p>
            Os campos abaixo vieram do que ele respondeu no formulário de
            credenciamento. <strong>Nada foi gravado</strong> — confira e salve.
          </p>
          <ul v-if="sugestao.avisos?.length" class="pilha pequeno">
            <li v-for="(a, i) in sugestao.avisos" :key="i">{{ a }}</li>
          </ul>
          <p v-if="Object.keys(sugestao.precos_respondidos || {}).length" class="pequeno">
            Os valores que ele mandou, que <strong>não</strong> são os serviços desta
            tabela:
            <span v-for="(v, k) in sugestao.precos_respondidos" :key="k" class="chip">
              {{ k }}: {{ v }}
            </span>
          </p>
        </div>
      </div>

      <!-- EMPRESA -->
      <section class="cartao bloco">
        <header class="cartao__cabecalho"><span>Empresa</span></header>
        <div class="cartao__corpo grade">
          <label class="campo campo--largo">
            <span class="campo__rotulo">Nome fantasia</span>
            <input v-model="form.nome_fantasia" class="campo__entrada" maxlength="120"
                   :disabled="!podeEscrever" />
          </label>
          <label class="campo campo--largo">
            <span class="campo__rotulo">Razão social</span>
            <input v-model="form.razao_social" class="campo__entrada" maxlength="120"
                   :disabled="!podeEscrever" />
          </label>
          <label class="campo">
            <span class="campo__rotulo">CNPJ</span>
            <input v-model="form.cnpj" class="campo__entrada" :disabled="!podeEscrever" />
          </label>
          <label class="campo">
            <span class="campo__rotulo">Telefone fixo</span>
            <input v-model="form.telefone_fixo" class="campo__entrada"
                   :disabled="!podeEscrever" />
          </label>
          <label class="campo campo--largo">
            <span class="campo__rotulo">E-mail geral</span>
            <input v-model="form.email_geral" class="campo__entrada"
                   :disabled="!podeEscrever" />
          </label>
        </div>
      </section>

      <!-- RESPONSÁVEL -->
      <section class="cartao bloco">
        <header class="cartao__cabecalho"><span>Responsável</span></header>
        <div class="cartao__corpo grade">
          <label class="campo">
            <span class="campo__rotulo">Nome</span>
            <input v-model="form.responsavel_nome" class="campo__entrada" maxlength="80"
                   :disabled="!podeEscrever" />
          </label>
          <label class="campo">
            <span class="campo__rotulo">Sobrenome</span>
            <input v-model="form.responsavel_sobrenome" class="campo__entrada"
                   maxlength="80" :disabled="!podeEscrever" />
          </label>
          <label class="campo">
            <span class="campo__rotulo">CPF</span>
            <input v-model="form.cpf" class="campo__entrada" :disabled="!podeEscrever" />
          </label>
          <label class="campo">
            <span class="campo__rotulo">Celular / WhatsApp</span>
            <input v-model="form.responsavel_celular" class="campo__entrada"
                   :disabled="!podeEscrever" />
          </label>
          <label class="campo campo--largo">
            <span class="campo__rotulo">E-mail</span>
            <input v-model="form.responsavel_email" class="campo__entrada"
                   :disabled="!podeEscrever" />
          </label>
        </div>
      </section>

      <!-- ENDEREÇO FIXO -->
      <section class="cartao bloco">
        <header class="cartao__cabecalho"><span>Endereço fixo</span></header>
        <div class="cartao__corpo pilha">
          <p class="pequeno fraco">
            É daqui que a calculadora de KM sai. Mudar o endereço na hora do cálculo
            vale só para aquele orçamento; os próximos voltam a abrir com este.
          </p>
          <div class="grade">
            <label class="campo">
              <span class="campo__rotulo">CEP</span>
              <div class="linha">
                <input v-model="form.cep" class="campo__entrada" inputmode="numeric"
                       maxlength="9" :disabled="!podeEscrever"
                       @blur="buscarCep" @keyup.enter="buscarCep" />
                <button v-if="podeEscrever" class="botao botao--contorno botao--pequeno"
                        type="button" @click="buscarCep">
                  Buscar
                </button>
              </div>
              <span v-if="cepEstado === 'procurando'" class="campo__ajuda">procurando…</span>
              <span v-else-if="cepEstado === 'nao_existe'" class="campo__ajuda">
                este CEP não existe
              </span>
              <span v-else-if="cepEstado === 'indisponivel'" class="campo__ajuda">
                não deu para conferir agora — preencha à mão
              </span>
              <span v-else class="campo__ajuda">preenche rua, bairro, cidade e UF</span>
            </label>
            <label class="campo campo--largo">
              <span class="campo__rotulo">Rua</span>
              <input v-model="form.logradouro" class="campo__entrada" maxlength="80"
                     :disabled="!podeEscrever" />
            </label>
            <label class="campo campo--curto">
              <span class="campo__rotulo">Número</span>
              <input v-model="form.numero" class="campo__entrada" maxlength="10"
                     :disabled="!podeEscrever" />
            </label>
            <label class="campo">
              <span class="campo__rotulo">Bairro</span>
              <input v-model="form.bairro" class="campo__entrada" maxlength="60"
                     :disabled="!podeEscrever" />
            </label>
            <label class="campo">
              <span class="campo__rotulo">Cidade</span>
              <input v-model="form.cidade" class="campo__entrada" maxlength="50"
                     :disabled="!podeEscrever" />
            </label>
            <label class="campo campo--curto">
              <span class="campo__rotulo">UF</span>
              <select v-model="form.uf" class="campo__entrada" :disabled="!podeEscrever">
                <option value="">—</option>
                <option v-for="u in UFS" :key="u" :value="u">{{ u }}</option>
              </select>
            </label>
            <label class="campo campo--largo">
              <span class="campo__rotulo">Complemento</span>
              <input v-model="form.complemento" class="campo__entrada" maxlength="40"
                     :disabled="!podeEscrever" />
            </label>
          </div>
        </div>
      </section>

      <!-- DADOS DE PAGAMENTO -->
      <section class="cartao bloco">
        <header class="cartao__cabecalho"><span>Dados de pagamento</span></header>
        <div class="cartao__corpo pilha">
          <p class="pequeno fraco">
            As mesmas três opções que o formulário de credenciamento oferece — é o que
            liga o que ele respondeu ao que fica na ficha.
          </p>
          <div class="grade">
            <label class="campo">
              <span class="campo__rotulo">Forma</span>
              <select v-model="form.pagamento_forma" class="campo__entrada"
                      :disabled="!podeEscrever">
                <option :value="null">—</option>
                <option v-for="f in FORMAS" :key="f.valor" :value="f.valor">
                  {{ f.rotulo }}
                </option>
              </select>
            </label>
            <label class="campo campo--largo">
              <span class="campo__rotulo">Dados</span>
              <textarea v-model="form.pagamento_dados" class="campo__entrada" rows="2"
                        :disabled="!podeEscrever"
                        placeholder="chave PIX, ou banco, agência, conta e titular"></textarea>
            </label>
          </div>
        </div>
      </section>

      <!-- TABELA DE PREÇO -->
      <section class="cartao bloco">
        <header class="cartao__cabecalho"><span>Tabela de preço</span></header>
        <div class="cartao__corpo pilha">
          <p class="pequeno fraco">
            O que <strong>ele cobra da Movisat</strong>, em reais, por serviço. Campo em
            branco significa que ele <strong>não oferece</strong> o serviço — diferente
            de cobrar zero.
          </p>
          <div class="tabela--rolavel">
            <table class="tabela">
              <thead>
                <tr><th>Serviço</th><th>Valor (R$)</th><th>Hoje</th></tr>
              </thead>
              <tbody>
                <tr v-for="s in dados.precos" :key="s.servico_id">
                  <td><strong>{{ s.nome }}</strong></td>
                  <td>
                    <input v-model="precos[s.servico_id]"
                           class="campo__entrada campo__entrada--valor"
                           inputmode="decimal" placeholder="não oferece"
                           :disabled="!podeEscrever" />
                  </td>
                  <td>
                    <span v-if="s.custo_texto" class="mono">{{ s.custo_texto }}</span>
                    <span v-else class="pequeno fraco">não oferece</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <!-- DESLOCAMENTO -->
      <section class="cartao bloco">
        <header class="cartao__cabecalho"><span>Deslocamento</span></header>
        <div class="cartao__corpo pilha">
          <!-- 🔵 *"o campo de deslocamento ficou legal, mas layout está quebrado"*.
               ⚠️ A causa: as três perguntas de sim/não eram `label.linha` dentro
               da mesma `.grade` dos campos de texto, com `align-items: end` —
               então a caixa de seleção assentava na linha de base de um campo
               que tem rótulo em cima, e cada uma ficava numa altura diferente.
               Agora as perguntas têm lista própria e os campos têm a sua. -->
          <ul class="perguntas">
            <li>
              <label class="pergunta">
                <input v-model="form.ponto_fixo" type="checkbox" :disabled="!podeEscrever" />
                <span>Tem ponto fixo para receber serviços</span>
              </label>
            </li>
            <li>
              <label class="pergunta">
                <input v-model="form.vai_ao_cliente" type="checkbox"
                       :disabled="!podeEscrever" />
                <span>Vai até o cliente</span>
              </label>
            </li>
            <li>
              <label class="pergunta">
                <input v-model="form.cobra_deslocamento" type="checkbox"
                       :disabled="!podeEscrever" />
                <span>Cobra o deslocamento à parte</span>
              </label>
            </li>
            <li>
              <!-- 🔵 04/11, no fechamento: *"crie um campo de flag, junto com
                   os do deslocamento chamado 'Preenche OS'"*. ⚠️ Está aqui
                   porque ele pediu aqui. E é registro: não liga nem desliga
                   nada hoje. -->
              <label class="pergunta">
                <input v-model="form.preenche_os" type="checkbox"
                       :disabled="!podeEscrever" />
                <span>Preenche OS</span>
              </label>
            </li>
          </ul>
          <div class="grade">
            <label class="campo">
              <span class="campo__rotulo">Área de cobertura</span>
              <input v-model="form.area_cobertura" class="campo__entrada" maxlength="120"
                     :disabled="!podeEscrever" placeholder="ex.: até 50 km" />
            </label>
            <label class="campo">
              <span class="campo__rotulo">Valor do km (R$)</span>
              <input v-model="form.km_valor_reais"
                     class="campo__entrada campo__entrada--valor" inputmode="decimal"
                     :disabled="!podeEscrever" placeholder="não informado" />
              <span class="campo__ajuda">
                Hoje: {{ dados.ficha?.km_valor_texto || 'não informado' }}
              </span>
            </label>
          </div>
        </div>
      </section>

      <!-- ACESSO -->
      <section class="cartao bloco">
        <header class="cartao__cabecalho"><span>Acesso ao Harmonit</span></header>
        <div class="cartao__corpo pilha">
          <p v-if="acesso === null" class="pequeno fraco">
            Não consegui falar com o cadastro do Harmonit agora — isto não quer dizer
            que ele esteja sem acesso.
          </p>
          <template v-else-if="acesso.harmonit_tecnico_id">
            <dl class="estatico">
              <dt>E-mail de acesso</dt>
              <dd class="mono">
                <span v-if="acesso.email">{{ acesso.email }}</span>
                <span v-else class="fraco">
                  {{ acesso.email_motivo || 'não informado no cadastro de lá' }}
                </span>
              </dd>
              <dt>Nome no Harmonit</dt>
              <dd>{{ acesso.harmonit_tecnico_nome }}</dd>
              <dt>Código</dt>
              <dd class="mono">#{{ acesso.harmonit_tecnico_id }}</dd>
            </dl>
            <p class="apagado pequeno">
              Só leitura: o cadastro é feito como usuário do sistema no Harmonit, e
              nada desta tela escreve lá. A senha não fica guardada aqui.
            </p>
          </template>
          <p v-else class="pequeno fraco">
            Este contato ainda não está ligado a um cadastro de técnico do Harmonit, e
            é esse cadastro que dá o acesso. A ligação se faz na ficha da conversa.
          </p>
        </div>
      </section>

      <!-- OBSERVAÇÃO -->
      <section class="cartao bloco">
        <header class="cartao__cabecalho"><span>Observação</span></header>
        <div class="cartao__corpo">
          <label class="campo">
            <textarea v-model="form.observacao" class="campo__entrada" rows="3"
                      :disabled="!podeEscrever"></textarea>
          </label>
        </div>
      </section>

      <!-- AÇÕES -->
      <section v-if="podeEscrever" class="cartao bloco">
        <div class="cartao__corpo pilha">
          <label class="campo">
            <span class="campo__rotulo">Nota da validação</span>
            <input v-model="form.estado_nota" class="campo__entrada"
                   placeholder="por que credenciou, ou por que recusou" />
          </label>
          <div class="linha acoes">
            <button class="botao botao--primario" type="button" :disabled="salvando"
                    @click="salvar">
              <span v-if="salvando" class="girando"></span>
              {{ salvando ? 'Salvando…' : 'Salvar a ficha' }}
            </button>
            <button v-if="dados.ficha && dados.ficha.estado !== 'credenciado'"
                    class="botao botao--contorno" type="button" :disabled="salvando"
                    @click="mudarEstado('credenciado')">
              Credenciar
            </button>
            <button v-if="dados.ficha && dados.ficha.estado !== 'recusado'"
                    class="botao botao--fantasma" type="button" :disabled="salvando"
                    @click="mudarEstado('recusado')">
              Recusar
            </button>
            <button v-if="dados.ficha && dados.ficha.estado !== 'candidato'"
                    class="botao botao--fantasma" type="button" :disabled="salvando"
                    @click="mudarEstado('candidato')">
              Voltar a candidato
            </button>
          </div>
          <p class="apagado pequeno">
            Para credenciar, a ficha precisa de rua, cidade e pelo menos um serviço
            com valor — é o que a calculadora de KM e o orçamento usam.
          </p>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.tela { max-width: 900px; }

.ficha__topo {
  display: flex;
  align-items: center;
  gap: var(--e-3);
  flex-wrap: wrap;
  margin-bottom: var(--e-4);
}
.ficha__titulo { display: flex; align-items: center; gap: var(--e-2); flex-wrap: wrap; }
.ficha__titulo h1 { margin: 0; }

.bloco { margin-bottom: var(--e-4); }

.grade {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: var(--e-3);
  /* ⚠️ `start`, não `end`: com `end`, campo com texto de ajuda embaixo
     empurrava o vizinho e a linha ficava torta — foi metade do "layout
     quebrado" que ele viu. */
  align-items: start;
}
.campo--largo { grid-column: span 2; }
.campo--curto { max-width: 8rem; }

/* 16px é o mínimo: abaixo disso o iOS dá zoom no campo ao focar. */
.campo__entrada--valor { max-width: 9rem; font-size: 16px; text-align: right; }

/* As perguntas de sim/não, fora da grade dos campos de texto. */
.perguntas { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--e-2); }
.pergunta { display: flex; align-items: center; gap: var(--e-2); }
.pergunta input { margin: 0; flex: none; }

/* O bloco estático do acesso: rótulo e valor, sem campo de edição. */
.estatico {
  display: grid;
  grid-template-columns: minmax(8rem, auto) 1fr;
  gap: var(--e-1) var(--e-3);
  margin: 0;
}
.estatico dt { font-size: .85rem; opacity: .7; }
.estatico dd { margin: 0; }

.acoes { flex-wrap: wrap; gap: var(--e-2); }

@media (max-width: 640px) {
  .campo--largo { grid-column: span 1; }
  .estatico { grid-template-columns: 1fr; }
  .estatico dd { margin-bottom: var(--e-2); }
}
</style>
