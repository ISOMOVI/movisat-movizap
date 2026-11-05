<script setup>
/* ============================================================================
   TEC_1.1 — Técnicos: a LISTA.
   ----------------------------------------------------------------------------
   🔵 Pedido dele (04/11): *"abaixo de 'orçamentos' vamos propor uma tela CRUD
   dos tecnicos"*.

   🔵 Segunda volta, no mesmo dia: *"não gosto desse modelo de quando clico em
   'abrir ficha', ele cria uma pagina em cima da atual. fica feio"*. A ficha
   saiu desta tela e virou tela própria (`FichaDoTecnico.vue`, com seta de
   voltar); aqui ficou só a lista, os credenciamentos recebidos e o cadastro à
   mão.

   🔵 *"o botão pode chamar 'Ficha' pois as vezes é só uma consulta aos dados
   dele"* — e é o nome do botão em todas as linhas, com ficha ou sem.

   🚨 TÉCNICO SEM FICHA APARECE NA LISTA. Eram 303 contatos de técnico e 0
   fichas em 04/11: listar só os fichados abriria a tela vazia e pareceria
   quebrada. A coluna "ficha" é o que mostra o trabalho que falta.

   🚨 LER É DE TODO ATENDENTE; ESCREVER DEPENDE DA `TEC_1.2`. Quem não tem a
   chave não vê os botões de criar — e a tela diz o que acontece, sem citar
   quem decidiu.
   ============================================================================ */
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'

import { api, ErroDeApi } from '../api/cliente.js'
import AjudaDaTela from '../componentes/AjudaDaTela.vue'
import { sessao } from '../estado/sessao.js'

const router = useRouter()

const podeEscrever = computed(
  () => sessao.telas.some((t) => t.codigo === 'TEC_1.2'))

const dados = ref({ itens: [], total: 0, paginas: 1, sem_ficha: 0 })
const candidatos = ref({ formulario: null, itens: [], motivo: '' })
const carregando = ref(true)
const erro = ref('')
const salvando = ref(false)

const busca = ref('')
const estado = ref('')
const comFicha = ref('')
const pagina = ref(1)

const criando = ref(false)
const novo = ref({ nome: '', telefone: '' })

const vazio = computed(() => !carregando.value && !dados.value.itens.length)

const ESTADOS = [
  { valor: 'candidato', rotulo: 'Candidato' },
  { valor: 'credenciado', rotulo: 'Credenciado' },
  { valor: 'recusado', rotulo: 'Recusado' },
]

function rotuloDoEstado(valor) {
  return ESTADOS.find((e) => e.valor === valor)?.rotulo || valor
}

/* O nome que se lê: em conversa de técnico o `contato.nome` é o telefone cru, e
   mostrar "+5518..." onde se espera uma empresa é o grid lendo a coluna errada. */
function nomeNaLista(t) {
  return t.nome_fantasia || t.harmonit_tecnico_nome || t.nome
}

function parametros() {
  const p = new URLSearchParams()
  if (busca.value.trim()) p.set('busca', busca.value.trim())
  if (estado.value) p.set('estado', estado.value)
  if (comFicha.value) p.set('com_ficha', comFicha.value)
  p.set('pagina', String(pagina.value))
  return p.toString()
}

async function carregar() {
  carregando.value = true
  erro.value = ''
  try {
    dados.value = await api.get(`/api/tecnicos?${parametros()}`)
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Falha ao ler os técnicos.'
  } finally {
    carregando.value = false
  }
}

async function carregarCandidatos() {
  try {
    candidatos.value = await api.get('/api/tecnicos/candidatos')
  } catch { /* candidato é um extra; a lista principal não depende dele */ }
}

onMounted(async () => {
  await Promise.all([carregar(), carregarCandidatos()])
})

watch([estado, comFicha], () => { pagina.value = 1; carregar() })
watch(pagina, carregar)

let timer = null
watch(busca, () => {
  clearTimeout(timer)
  timer = setTimeout(() => { pagina.value = 1; carregar() }, 350)
})

/* A ficha é outra tela. `solicitacao` vai na query quando se abre um
   credenciamento recebido — é o que faz a ficha nascer preenchida para
   conferir, sem gravar nada. */
function abrirFicha(contatoId, solicitacaoId = null) {
  router.push({
    path: `/tecnicos/ficha/${contatoId}`,
    query: solicitacaoId ? { solicitacao: String(solicitacaoId) } : {},
  })
}

async function criar() {
  salvando.value = true
  erro.value = ''
  try {
    const r = await api.post('/api/tecnicos', { ...novo.value })
    criando.value = false
    novo.value = { nome: '', telefone: '' }
    abrirFicha(r.contato.contato_id)
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui criar.'
  } finally {
    salvando.value = false
  }
}
</script>

<template>
  <div class="tela">
    <header class="tela__cabecalho">
      <div>
        <h1>Técnicos</h1>
        <AjudaDaTela>
          A ficha de cada técnico: o <strong>endereço fixo</strong> que a calculadora de KM
          usa como origem, a <strong>tabela de preço</strong> por serviço e o credenciamento.
        </AjudaDaTela>
      </div>
      <div class="linha">
        <button v-if="podeEscrever" class="botao botao--primario" type="button"
                @click="criando = !criando">
          <i class="bi bi-plus-lg" aria-hidden="true"></i> Novo técnico
        </button>
      </div>
    </header>

    <p v-if="!podeEscrever" class="apagado pequeno">
      Esta tela abre a ficha para consulta. Cadastrar técnico, alterar valores e
      credenciar não é possível por aqui.
    </p>

    <p v-if="erro" class="aviso aviso--erro" role="alert">
      <i class="bi bi-exclamation-octagon aviso__icone" aria-hidden="true"></i>
      <span>{{ erro }}</span>
    </p>

    <!-- novo à mão -->
    <section v-if="criando && podeEscrever" class="cartao tela__bloco">
      <header class="cartao__cabecalho"><span>Novo técnico</span></header>
      <div class="cartao__corpo pilha">
        <label class="campo">
          <span class="campo__rotulo">Nome</span>
          <input v-model="novo.nome" class="campo__entrada" maxlength="120" />
        </label>
        <label class="campo">
          <span class="campo__rotulo">Telefone (opcional)</span>
          <input v-model="novo.telefone" class="campo__entrada" />
          <span class="campo__ajuda">
            É o que casa com o cadastro do Harmonit — lá o e-mail do técnico é o
            telefone dele.
          </span>
        </label>
        <div class="linha">
          <button class="botao botao--primario" type="button" :disabled="salvando"
                  @click="criar">
            <span v-if="salvando" class="girando"></span>
            {{ salvando ? 'Criando…' : 'Criar e abrir a ficha' }}
          </button>
          <button class="botao botao--fantasma" type="button" @click="criando = false">
            Cancelar
          </button>
        </div>
      </div>
    </section>

    <!-- credenciamentos recebidos -->
    <section v-if="candidatos.itens.length" class="cartao tela__bloco">
      <header class="cartao__cabecalho">
        <span>Credenciamentos recebidos ({{ candidatos.itens.length }})</span>
      </header>
      <div class="cartao__corpo pilha">
        <p class="pequeno fraco">
          Chegaram pelo formulário público e ainda não têm ficha. Abrir um deles
          <strong>preenche a ficha para você conferir</strong> — nada é gravado antes de
          salvar.
        </p>
        <div class="tabela--rolavel">
          <table class="tabela">
            <thead>
              <tr><th>Quando</th><th>Empresa</th><th>CNPJ</th><th>Cidade</th><th></th></tr>
            </thead>
            <tbody>
              <tr v-for="c in candidatos.itens" :key="c.id">
                <td class="pequeno fraco">
                  {{ new Date(c.criada_em).toLocaleString('pt-BR') }}
                </td>
                <td><strong>{{ c.resumo?.empresa || '—' }}</strong></td>
                <td class="mono pequeno">{{ c.resumo?.cnpj || '—' }}</td>
                <td>{{ c.resumo?.cidade || '—' }}</td>
                <td>
                  <button v-if="podeEscrever && c.contato_id"
                          class="botao botao--pequeno botao--contorno" type="button"
                          @click="abrirFicha(c.contato_id, c.id)">
                    Conferir e credenciar
                  </button>
                  <span v-else-if="!c.contato_id" class="pequeno fraco">
                    sem contato ligado
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <p v-else-if="candidatos.motivo" class="aviso aviso--atencao">
      <i class="bi bi-exclamation-triangle aviso__icone" aria-hidden="true"></i>
      <span>{{ candidatos.motivo }}</span>
    </p>

    <!-- a lista -->
    <section class="cartao tela__bloco">
      <header class="cartao__cabecalho"><span>Todos os técnicos</span></header>
      <div class="cartao__corpo pilha">
        <div class="grade">
          <label class="campo">
            <span class="campo__rotulo">Procurar</span>
            <input v-model="busca" class="campo__entrada"
                   placeholder="nome, telefone, CNPJ ou CPF" />
          </label>
          <label class="campo">
            <span class="campo__rotulo">Estado</span>
            <select v-model="estado" class="campo__entrada">
              <option value="">todos</option>
              <option v-for="e in ESTADOS" :key="e.valor" :value="e.valor">
                {{ e.rotulo }}
              </option>
            </select>
          </label>
          <label class="campo">
            <span class="campo__rotulo">Ficha</span>
            <select v-model="comFicha" class="campo__entrada">
              <option value="">todos</option>
              <option value="true">com ficha</option>
              <option value="false">sem ficha</option>
            </select>
          </label>
        </div>

        <p class="pequeno fraco">
          {{ dados.total }} técnico(s) no filtro — <strong>{{ dados.sem_ficha }}</strong>
          ainda sem ficha.
        </p>

        <p v-if="carregando" class="linha fraco">
          <span class="girando"></span> Lendo…
        </p>

        <div v-else-if="vazio" class="vazio">
          <i class="bi bi-person-badge vazio__icone" aria-hidden="true"></i>
          <p class="vazio__titulo">Nenhum técnico neste filtro</p>
          <p>
            Técnico é contato do tipo <strong>técnico</strong>; o tipo se define na ficha
            da conversa.
          </p>
        </div>

        <div v-else class="tabela--rolavel">
          <table class="tabela">
            <thead>
              <tr>
                <th>Técnico</th>
                <th>Telefone</th>
                <th>Cidade</th>
                <th>Harmonit</th>
                <th>Serviços</th>
                <th>Ficha</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="t in dados.itens" :key="t.contato_id"
                  :class="{ 'linha--inativa': !t.ativo }">
                <td><strong>{{ nomeNaLista(t) }}</strong></td>
                <td class="mono pequeno">{{ t.telefone || '—' }}</td>
                <td>
                  <span v-if="t.cidade">
                    {{ t.cidade }}<span v-if="t.uf"> — {{ t.uf }}</span>
                  </span>
                  <span v-else class="pequeno fraco">sem endereço</span>
                </td>
                <td>
                  <span v-if="t.harmonit_tecnico_id" class="chip chip--ok">
                    #{{ t.harmonit_tecnico_id }}
                  </span>
                  <span v-else class="pequeno fraco">sem vínculo</span>
                </td>
                <td>
                  <span v-if="t.servicos_com_preco">{{ t.servicos_com_preco }} com valor</span>
                  <span v-else class="pequeno fraco">nenhum</span>
                </td>
                <td>
                  <span v-if="!t.tem_ficha" class="chip">sem ficha</span>
                  <span v-else class="chip" :class="{
                    'chip--ok': t.estado === 'credenciado',
                    'chip--acento': t.estado === 'candidato' }">
                    {{ rotuloDoEstado(t.estado) }}
                  </span>
                </td>
                <td>
                  <!-- 🔵 *"o botão pode chamar 'Ficha' pois as vezes é só uma
                       consulta aos dados dele"*. -->
                  <button class="botao botao--pequeno botao--contorno" type="button"
                          @click="abrirFicha(t.contato_id)">
                    Ficha
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <nav v-if="dados.paginas > 1" class="linha">
          <button class="botao botao--contorno botao--pequeno" :disabled="pagina <= 1"
                  @click="pagina -= 1">
            anterior
          </button>
          <span class="pequeno fraco">{{ pagina }} / {{ dados.paginas }}</span>
          <button class="botao botao--contorno botao--pequeno"
                  :disabled="pagina >= dados.paginas" @click="pagina += 1">
            próxima
          </button>
        </nav>
      </div>
    </section>
  </div>
</template>

<style scoped>
.tela { max-width: 1100px; }

.tela__cabecalho {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--e-4);
  flex-wrap: wrap;
  margin-bottom: var(--e-5);
}
.tela__cabecalho p { max-width: var(--largura-texto); margin-top: var(--e-1); }

.tela__bloco { margin-bottom: var(--e-5); }

.grade {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: var(--e-3);
  align-items: start;
}

.linha--inativa td { opacity: .6; }
</style>
