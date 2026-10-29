<script setup>
/* ============================================================================
   A página pública do formulário — `forms.movisat.com.br/f/<slug>`
   ----------------------------------------------------------------------------
   🚨 ESTA PÁGINA NÃO É O PAINEL, e é um bundle à parte de propósito. O bundle
   do painel publica `sourcemap: true`: uma rota pública dentro dele faria
   qualquer anônimo baixar o painel inteiro com o código-fonte. A pergunta foi
   dele (*"qual a mais segura para os links que terão acesso externos"*).

   🚨 QUEM RECUSA É O SERVIDOR. O obrigatório, a opção de lista, o tipo do
   arquivo, o tempo mínimo e a conta de somar são conferidos lá -- aqui o que
   existe é a mensagem que a pessoa lê. No Bitrix era o contrário: toda a
   validação no navegador, e um POST cru criou registro em 22/10.

   🚨 DOIS FORMATOS, E O BANCO É QUEM DIZ QUAL (29/10, pedido dele sobre o
   Suporte: *"ajuste ele no novo formato 'etapas, logo, cor, placas, etc'"*).
   `formato = 'novo'` traz a logo oficial, a base `#021529`, o trilho de etapas
   e o repetidor; `'classico'` é a página de 22/10, inalterada. Hoje só o
   Suporte está em `novo` -- os outros 14 esperam ele validar este no
   navegador, formulário por formulário.

   ⚠️ A ISCA É INVISÍVEL PARA GENTE E VISÍVEL PARA ROBÔ: campo fora da tela,
   sem rótulo e com `tabindex="-1"`. Preenchido, o servidor descarta o envio
   em silêncio -- e responde o mesmo "recebemos" de sempre, porque robô que
   toma erro aprende a tentar de outro jeito.

   ⚠️ SEM `autocomplete="off"`: o cliente que preenche a ficha cadastral no
   celular merece o preenchimento do próprio navegador.
   ============================================================================ */
import { computed, onMounted, reactive, ref } from 'vue'

import CamposDoFormulario from '../src/componentes/CamposDoFormulario.vue'
import { visiveis } from '../src/util/regras_formulario.js'
import { problemas } from '../src/util/validacao_campo.js'
import './identidade.css'
import logoMovisat from './movisat_logo.png'

const slug = (window.location.pathname.split('/f/')[1] || '').split(/[?#/]/)[0]

const def = ref(null)
const valores = reactive({})
const anexos = reactive({})
const erro = ref('')
const naoExiste = ref(false)
const enviando = ref(false)
const pronto = ref(false)
const desafio = ref(null)
const resposta = ref('')
const etapa = ref(0)
const avisos = ref([])
const recados = reactive({})
/* As placas ativas do cliente, por campo com `fonte = 'weso_placas'`. Chegam
   junto com a busca do CNPJ -- uma ida ao servidor, não duas. */
const sugestoes = reactive({})
/* O que a WESO respondeu sobre cada placa escrita. 🔵 Regra dele: chamado só
   para placa ativa na WESO. */
const placasConferidas = reactive({})
const buscando = ref(false)
/* 🚨 Quem a BUSCA confirmou. Vazio = nenhuma empresa vinculada, e é o que
   dispara a caixa de diálogo antes de enviar (pedido dele, 29/10). */
const clienteAchado = ref('')
const perguntarSemEmpresa = ref(false)

const ehNovo = computed(() => def.value?.formato === 'novo')
const etapas = computed(() => (ehNovo.value && def.value?.etapas) || [])
const temEtapas = computed(() => etapas.value.length > 1)
const ultima = computed(() => !temEtapas.value || etapa.value === etapas.value.length - 1)

/* 🚨 AS 6 CORES DO CATAVENTO, e entram SÓ COMO CÓDIGO DE ETAPA -- a cor
   informa, não enfeita (design de 23/10). A base da página continua
   `#021529`. ⚠️ A cor nunca é o único portador: a etapa tem número e nome
   escritos ao lado. */
const CATAVENTO = ['#8CC63F', '#FFC20E', '#F07F13', '#C4203F', '#1B75BB', '#41BFE8']
function corDaEtapa(i) { return CATAVENTO[i % CATAVENTO.length] }

/* Os campos da etapa de agora, já sem os que a regra condicional esconde. */
const camposDaEtapa = computed(() => {
  if (!temEtapas.value) return []
  const dePe = visiveis({ campos: def.value.campos, regras: def.value.regras }, valores)
  return (etapas.value[etapa.value]?.campos || []).filter((n) => dePe.has(n))
})

async function carregar() {
  try {
    const r = await fetch(`/api/publico/formulario/${encodeURIComponent(slug)}`)
    if (r.status === 404) { naoExiste.value = true; return }
    if (!r.ok) throw new Error('falha')
    def.value = await r.json()
    desafio.value = def.value.desafio
    document.title = def.value.titulo || 'Formulário'
  } catch {
    erro.value = 'Não consegui abrir o formulário agora. Tente de novo em instantes.'
  }
}

function guardarArquivo(nome, arquivos) {
  anexos[nome] = [...(arquivos || [])]
}

/* 🔵 O botão *Buscar* do CNPJ — pedido dele, 29/10: *"ao colocar CPF CNPJ, ter
   botão de buscar pelo CNPJ para preenchimento automático da base do
   harmonit"*.

   🚨 A ROTA NÃO FALA COM O HARMONIT, e devolve só o nome -- o porquê está em
   `formularios.cliente_por_documento`. Aqui o que se faz com a resposta é
   preencher o campo de empresa e dizer, por extenso, o que foi encontrado.

   ⚠️ "Não achou" NÃO é erro: a maior parte de quem preenche o formulário
   público ainda não é cliente. A frase diz isso sem alarme. */
async function buscarCliente(nomeDoCampo, documento) {
  buscando.value = true
  recados[nomeDoCampo] = 'Procurando…'
  try {
    const corpo = new FormData()
    corpo.append('documento', documento || '')
    corpo.append('abertura', def.value.abertura)
    const r = await fetch(
      `/api/publico/formulario/${encodeURIComponent(slug)}/cliente`,
      { method: 'POST', body: corpo })
    const dados = await r.json().catch(() => ({}))
    if (!r.ok) {
      recados[nomeDoCampo] = dados.detail || 'Não consegui consultar agora.'
      return
    }
    if (!dados.achou) {
      clienteAchado.value = ''
      recados[nomeDoCampo] = 'Não encontramos este CNPJ na nossa base. '
        + 'Pode seguir preenchendo.'
      return
    }
    clienteAchado.value = dados.nome
    recados[nomeDoCampo] = dados.varios
      ? `Mais de um cadastro com este CNPJ. O primeiro é ${dados.nome}.`
      : `Cliente: ${dados.nome}`

    /* 🔵 A frota ativa do cliente vai para todo campo que declara a fonte.
       🚨 `placas_erro` é diferente de lista vazia: a ponte do FPSL fora do ar
       não pode virar "você não tem veículo". Nos dois casos sobra o campo de
       digitar, que é o caminho de sempre. */
    for (const campo of def.value.campos) {
      if (campo.fonte !== 'weso_placas') continue
      sugestoes[campo.nome] = dados.placas || []
      if (dados.placas_erro) {
        recados[campo.nome] = 'Não consegui consultar seus veículos agora — '
          + 'informe a placa abaixo.'
      } else if (!(dados.placas || []).length) {
        recados[campo.nome] = 'Não encontrei veículo ativo neste cadastro — '
          + 'informe a placa abaixo.'
      } else {
        recados[campo.nome] = `${dados.placas.length} veículo(s) ativo(s) `
          + 'neste cadastro.'
      }
    }
    /* ⚠️ Preenche a EMPRESA e nada mais: é o único campo que a resposta tem
       como preencher sem adivinhar. */
    const empresa = def.value.campos.find((c) => c.tipo === 'company-name')
    if (empresa) valores[empresa.nome] = dados.nome
  } catch {
    recados[nomeDoCampo] = 'Não consegui consultar agora.'
  } finally {
    buscando.value = false
  }
}

/* 🚨 SEGURAR O *AVANÇAR* NÃO É VALIDAR NO LUGAR DO SERVIDOR: o envio continua
   sendo recusado lá. É o que impede a pessoa de descobrir na última etapa que
   faltou algo na primeira -- que é o defeito que as etapas existem para
   resolver. A conta é a mesma do componente (`validacao_campo.problemas`). */
function conferirEtapa() {
  const dePe = visiveis({ campos: def.value.campos, regras: def.value.regras }, valores)
  const daEtapa = new Set(camposDaEtapa.value)
  const campos = def.value.campos.filter((c) => daEtapa.has(c.nome))
  avisos.value = problemas(campos, valores, dePe)
  return avisos.value.length === 0
}

function avancar() {
  if (!conferirEtapa()) return
  etapa.value = Math.min(etapa.value + 1, etapas.value.length - 1)
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

/* ⚠️ Voltar NÃO confere nada e NÃO perde o preenchido: quem volta está
   corrigindo, e cobrar na saída puniria exatamente esse movimento. */
function voltar() {
  avisos.value = []
  etapa.value = Math.max(etapa.value - 1, 0)
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

/* 🔵 A CAIXA DE DIÁLOGO ANTES DE ENVIAR — pedido dele, 29/10: *"antes de
   enviar o formulário de suporte, caixa de diálogo para confirmação do
   operador se não tiver empresa vinculada"*.

   🚨 MODAL PRÓPRIO, NÃO `window.confirm`: o `confirm` do navegador só tem
   "OK" e "Cancelar", e em 21/10 ele pediu as palavras *cancelar/continuar*
   nos botões. Palavra no botão exige modal nosso.

   ⚠️ Só pergunta UMA VEZ: confirmado, envia. Perguntar de novo a cada clique
   transformaria a confirmação em obstáculo. */
function podeEnviarSemEmpresa() {
  if (!ehNovo.value) return true
  if (clienteAchado.value) return true
  perguntarSemEmpresa.value = true
  return false
}

function confirmarSemEmpresa() {
  perguntarSemEmpresa.value = false
  /* Marca como respondido para não perguntar outra vez. */
  clienteAchado.value = '(sem empresa vinculada — confirmado)'
  enviar()
}

/* 🔵 A regra da placa, avisada na hora. ⚠️ A recusa de verdade é no envio, no
   servidor -- isto existe para a pessoa não preencher tudo e descobrir no fim. */
async function conferirPlaca(valor) {
  const chave = String(valor ?? '').trim()
  if (!chave || placasConferidas[chave]) return
  try {
    const corpo = new FormData()
    corpo.append('placa', chave)
    corpo.append('abertura', def.value.abertura)
    const r = await fetch(
      `/api/publico/formulario/${encodeURIComponent(slug)}/placa`,
      { method: 'POST', body: corpo })
    if (!r.ok) { placasConferidas[chave] = { conferiu: false }; return }
    placasConferidas[chave] = await r.json()
  } catch {
    placasConferidas[chave] = { conferiu: false }
  }
}

async function enviar() {
  if (temEtapas.value && !conferirEtapa()) return
  if (!podeEnviarSemEmpresa()) return
  erro.value = ''
  enviando.value = true
  try {
    const corpo = new FormData()
    corpo.append('valores', JSON.stringify(valores))
    corpo.append('abertura', def.value.abertura)
    corpo.append('isca', document.getElementById('isca')?.value || '')
    if (desafio.value) {
      corpo.append('desafio_token', desafio.value.token)
      corpo.append('desafio_resposta', resposta.value)
    }
    /* Os anexos vão em duas listas paralelas: multipart com nome de campo
       dinâmico não dá para declarar do outro lado. O servidor confere o par. */
    for (const [campo, arquivos] of Object.entries(anexos)) {
      for (const arquivo of arquivos) {
        corpo.append('campos', campo)
        corpo.append('arquivos', arquivo)
      }
    }
    const r = await fetch(`/api/publico/formulario/${encodeURIComponent(slug)}`,
                          { method: 'POST', body: corpo })
    const dados = await r.json().catch(() => ({}))
    if (!r.ok) {
      erro.value = dados.detail || 'Não consegui enviar. Confira os dados.'
      /* Conta errada ou expirada: pede outra, senão a pessoa fica presa na
         mesma pergunta. */
      if (desafio.value) {
        const nova = await fetch('/api/publico/desafio').then((x) => x.json())
        desafio.value = nova
        resposta.value = ''
      }
      return
    }
    pronto.value = true
  } catch {
    erro.value = 'Não consegui enviar agora. Tente de novo em instantes.'
  } finally {
    enviando.value = false
  }
}

onMounted(carregar)
</script>

<template>
  <main class="pagina" :class="{ 'pagina--novo': ehNovo }">
    <!-- 🚨 A LOGO É O ARQUIVO DELE, nunca redesenhada (*"não pode mudar nossa
         logo, deve usar o arquivo que mandei"*). Vai como arquivo publicado ao
         lado da página, não como SVG aproximado. -->
    <img v-if="ehNovo" class="marca" :src="logoMovisat" alt="Movisat" />

    <div v-if="naoExiste" class="cartao">
      <h1 class="titulo">Formulário não encontrado</h1>
      <!-- 🚨 A MESMA FRASE para "não existe" e "está desligado": distinguir
           os dois contaria ao mundo quais formulários a casa tem. -->
      <p class="apoio">
        Confira o link. Se ele veio de alguém da Movisat, peça o endereço de novo.
      </p>
    </div>

    <div v-else-if="pronto" class="cartao">
      <h1 class="titulo">Recebemos sua solicitação</h1>
      <p class="apoio">Em breve entraremos em contato.</p>
    </div>

    <form v-else-if="def" class="cartao" @submit.prevent="enviar">
      <h1 class="titulo">{{ def.titulo }}</h1>
      <p v-if="def.descricao" class="apoio">{{ def.descricao }}</p>

      <!-- ===================== o trilho de etapas ===================== -->
      <!-- ⚠️ Rola na horizontal no celular e acompanha a etapa; cada etapa tem
           NÚMERO e NOME, porque a cor não pode ser o único portador. -->
      <nav v-if="temEtapas" class="trilho" aria-label="Etapas">
        <button
          v-for="(e, i) in etapas"
          :key="i"
          type="button"
          class="trilho__passo"
          :class="{ 'trilho__passo--agora': i === etapa, 'trilho__passo--feito': i < etapa }"
          :style="{ '--cor-etapa': corDaEtapa(i) }"
          :aria-current="i === etapa ? 'step' : undefined"
          @click="i < etapa ? (etapa = i) : null"
        >
          <span class="trilho__n">{{ i + 1 }}</span>
          <span class="trilho__nome">{{ e.titulo }}</span>
        </button>
      </nav>
      <p v-if="temEtapas" class="passo-de">
        Etapa {{ etapa + 1 }} de {{ etapas.length }}
      </p>

      <CamposDoFormulario
        :campos="def.campos"
        :regras="def.regras"
        :valores="valores"
        :erro="erro"
        :formato="def.formato"
        :somente="camposDaEtapa"
        :recados="recados"
        :sugestoes="sugestoes"
        :placas="placasConferidas"
        @arquivo="guardarArquivo"
        @buscar="buscarCliente"
        @placa="conferirPlaca"
      />

      <!-- Só na última etapa: a conta de somar é do ENVIO, não do caminho. -->
      <label v-if="desafio && ultima" class="campo-desafio">
        <span>{{ desafio.pergunta }}</span>
        <input v-model="resposta" class="entrada" inputmode="numeric" required />
      </label>

      <ul v-if="avisos.length" class="avisos" role="alert">
        <li v-for="a in avisos" :key="a.nome">{{ a.mensagem }}</li>
      </ul>

      <!-- a isca -->
      <input id="isca" class="isca" tabindex="-1" aria-hidden="true" autocomplete="off" />

      <div class="acoes">
        <button v-if="temEtapas && etapa > 0" type="button" class="botao botao--calado" @click="voltar">
          Voltar
        </button>
        <button v-if="temEtapas && !ultima" type="button" class="botao" @click="avancar">
          Avançar
        </button>
        <button v-if="ultima" class="botao" type="submit" :disabled="enviando">
          {{ enviando ? 'Enviando…' : (def.botao || 'Enviar') }}
        </button>
      </div>
    </form>

    <p v-else-if="erro" class="cartao apoio">{{ erro }}</p>

    <!-- 🔵 A confirmação de "sem empresa vinculada". Modal próprio, porque as
         palavras dos botões são dele: *cancelar / continuar*. -->
    <div v-if="perguntarSemEmpresa" class="sombra" @click.self="perguntarSemEmpresa = false">
      <div class="modal" role="dialog" aria-modal="true" aria-labelledby="t-modal">
        <h2 id="t-modal" class="titulo">Sem empresa vinculada</h2>
        <p class="apoio">
          Não identificamos a empresa deste chamado na nossa base. Você pode
          buscar pelo CNPJ para vincular, ou continuar e enviar assim mesmo.
        </p>
        <div class="acoes">
          <button type="button" class="botao" @click="confirmarSemEmpresa">
            Continuar
          </button>
          <button type="button" class="botao botao--calado" @click="perguntarSemEmpresa = false">
            Cancelar
          </button>
        </div>
      </div>
    </div>
  </main>
</template>

<style scoped>
.pagina {
  min-height: 100vh;
  padding: var(--e-5) var(--e-4);
  background: var(--fundo);
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  align-items: center;
  gap: var(--e-4);
}
/* ⚠️ `max-width: 62vw` para a logo não empurrar a página no celular estreito. */
.marca { width: 190px; max-width: 62vw; height: auto; }
.cartao {
  width: 100%;
  max-width: 680px;
  display: flex;
  flex-direction: column;
  gap: var(--e-4);
  padding: var(--e-5);
  background: var(--superficie);
  border: var(--borda-fina) solid var(--borda);
  border-radius: var(--r-md);
}
.titulo { margin: 0; font-size: var(--txt-xl); color: var(--texto); }
.apoio { margin: 0; color: var(--texto-fraco); line-height: var(--entrelinha); }

/* ---- trilho ---- */
.trilho {
  display: flex;
  gap: var(--e-2);
  overflow-x: auto;
  padding-bottom: var(--e-1);
}
.trilho__passo {
  flex: none;
  display: flex;
  align-items: center;
  gap: var(--e-2);
  padding: var(--e-2) var(--e-3);
  border: var(--borda-fina) solid var(--borda);
  border-radius: var(--r-full);
  background: var(--superficie);
  color: var(--texto-fraco);
  font-size: var(--txt-sm);
  cursor: default;
}
.trilho__passo--feito { cursor: pointer; color: var(--texto); }
.trilho__passo--agora {
  border-color: var(--cor-etapa);
  box-shadow: inset 0 -3px 0 0 var(--cor-etapa);
  color: var(--texto);
  font-weight: var(--peso-forte);
}
.trilho__n {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: var(--r-full);
  background: var(--cor-etapa);
  color: #FFFFFF;
  font-weight: var(--peso-forte);
}
.trilho__nome { white-space: nowrap; }
.passo-de { margin: 0; color: var(--texto-fraco); font-size: var(--txt-sm); }

.campo-desafio { display: flex; flex-direction: column; gap: var(--e-2); }
.entrada {
  min-height: var(--altura-toque);
  padding: var(--e-2) var(--e-3);
  border: var(--borda-fina) solid var(--borda);
  border-radius: var(--r-md);
  font-size: var(--txt-campo);
  background: var(--superficie);
  color: var(--texto);
}
.avisos {
  margin: 0;
  padding: var(--e-3) var(--e-3) var(--e-3) var(--e-5);
  border: var(--borda-fina) solid var(--erro);
  border-radius: var(--r-md);
  color: var(--erro);
}
.acoes { display: flex; gap: var(--e-2); flex-wrap: wrap; }
.botao {
  min-height: var(--altura-toque);
  padding: var(--e-2) var(--e-5);
  border: 0;
  border-radius: var(--r-md);
  background: var(--acento);
  color: var(--acento-texto);
  font-size: var(--txt-md);
  font-weight: var(--peso-medio);
  cursor: pointer;
}
.botao:disabled { background: var(--borda-forte); cursor: progress; }
.botao--calado {
  background: var(--superficie);
  color: var(--texto);
  border: var(--borda-fina) solid var(--borda-forte);
}

/* ---- o modal ---- */
.sombra {
  position: fixed;
  inset: 0;
  background: rgba(2, 21, 41, .55);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--e-4);
  z-index: var(--z-modal);
}
.modal {
  width: 100%;
  max-width: 440px;
  display: flex;
  flex-direction: column;
  gap: var(--e-3);
  padding: var(--e-5);
  background: var(--superficie);
  border-radius: var(--r-md);
}

/* A isca sai da tela sem `display:none` -- robô ignora campo oculto por
   display, mas preenche o que existe no DOM. */
.isca { position: absolute; left: -9999px; width: 1px; height: 1px; opacity: 0; }

@media (max-width: 560px) {
  .cartao { padding: var(--e-4); }
}
</style>
