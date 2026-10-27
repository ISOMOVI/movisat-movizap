<script setup>
/* ============================================================================
   ORC_1.1 — Orçamentos.
   ----------------------------------------------------------------------------
   🔵 Pedido dele (26/10): *"Painel de orçamento salvo para consulta apenas;
   Consultar em grid os orçamentos aba nova 'Orçamentos' (como das ligações)"*.

   🚨 SÓ CONSULTA, E A TELA DIZ ISSO EM TEXTO. Orçamento emitido não muda de
   conteúdo: o `reenviar` do backend remonta o MESMO papel a partir do que está
   gravado. Então não há editar, cancelar nem emitir aqui — e ausência de botão
   não explica nada a ninguém. Quem emite é o modal de agendar, na conversa do
   técnico. O precedente é o card do `PNL_1.1`, que escreve por que não se
   arrasta.

   🚨 O VALOR JÁ CHEGA ESCRITO. O backend manda `total` ("629,00") junto com
   `total_centavos`, porque `orcamento.reais()` é o único lugar do projeto que
   escreve centavos em português. Dividir por 100 aqui seria um segundo lugar,
   com outra regra de arredondamento — e seria o grid divergindo do PDF.

   🚨 O NOME DO TÉCNICO VEM DO HARMONIT, não do contato: em conversa de técnico
   o `contato.nome` é o telefone cru. Quem resolve isso é o backend; a tela só
   mostra o que veio.

   🚨 O PDF SAI POR `/api/midia/{id}/ver`, que já existia. Ele é uma `midia` de
   conversa, e essa rota já serve quem tem `ATD_1.2` — a mesma permissão desta
   aba. Vem por `pedirBlob` porque o token vive no cabeçalho, e o navegador não
   o manda sozinho num `<a href>`.
   ============================================================================ */
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'

import { api, pedirBlob, ErroDeApi } from '../api/cliente.js'
import AjudaDaTela from '../componentes/AjudaDaTela.vue'

const dados = ref({ itens: [], total: 0, paginas: 1, soma: '0,00' })
const filtros = ref({ tecnicos: [], atendentes: [] })
const carregando = ref(true)
const erro = ref('')

const de = ref('')
const ate = ref('')
const numero = ref('')
const osNumero = ref('')
const tecnicoId = ref('')
const atendenteId = ref('')
const soComPdf = ref(false)
const pagina = ref(1)

/* Um PDF aberto por vez. Cada blob é memória presa até o revoke, e abrir dez
   abas de orçamento não é o que ninguém quer. */
const pdfAberto = ref({ id: null, url: '' })

const vazio = computed(() => !carregando.value && !dados.value.itens.length)

function parametros() {
  const p = new URLSearchParams()
  if (de.value) p.set('de', de.value)
  if (ate.value) p.set('ate', ate.value)
  if (numero.value.trim()) p.set('numero', numero.value.trim())
  if (osNumero.value.trim()) p.set('os_numero', osNumero.value.trim())
  if (tecnicoId.value) p.set('tecnico_contato_id', tecnicoId.value)
  if (atendenteId.value) p.set('atendente_id', atendenteId.value)
  if (soComPdf.value) p.set('com_pdf', 'true')
  return p
}

async function carregar() {
  carregando.value = true
  try {
    const p = parametros()
    p.set('pagina', String(pagina.value))
    dados.value = await api.get(`/api/orcamentos?${p.toString()}`)
    erro.value = ''
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Falha ao ler os orçamentos.'
  } finally {
    carregando.value = false
  }
}

function buscar() {
  pagina.value = 1
  carregar()
}

watch(pagina, carregar)

onMounted(async () => {
  try {
    filtros.value = await api.get('/api/orcamentos/filtros')
  } catch {
    /* os seletores são conveniência, não pré-requisito do grid */
    filtros.value = { tecnicos: [], atendentes: [] }
  }
  await carregar()
})

onUnmounted(() => soltarPdf())

function soltarPdf() {
  if (pdfAberto.value.url) URL.revokeObjectURL(pdfAberto.value.url)
  pdfAberto.value = { id: null, url: '' }
}

async function abrirPdf(o) {
  if (pdfAberto.value.id === o.id) return soltarPdf()
  soltarPdf()
  try {
    const blob = await pedirBlob(`/api/midia/${o.midia_id}/ver`)
    pdfAberto.value = { id: o.id, url: URL.createObjectURL(blob) }
  } catch (e) {
    erro.value = e instanceof ErroDeApi
      ? e.message
      : 'Não consegui abrir o PDF deste orçamento.'
  }
}

async function baixarPdf(o) {
  try {
    const blob = await pedirBlob(`/api/midia/${o.midia_id}/ver`)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `orcamento-${o.numero}.pdf`
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui baixar o PDF.'
  }
}

function limpar() {
  de.value = ''
  ate.value = ''
  numero.value = ''
  osNumero.value = ''
  tecnicoId.value = ''
  atendenteId.value = ''
  soComPdf.value = false
  buscar()
}

function data(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })
}
</script>

<template>
  <div class="tela">
    <header class="tela__cabecalho">
      <div>
        <h1>Orçamentos</h1>
        <AjudaDaTela>
          Os orçamentos já emitidos, com número, técnico, valor, as OS que o
          documento imprime e o PDF. A busca por número é exata: número de
          orçamento é documento, e o 1 não casa com o 10.
        </AjudaDaTela>
      </div>
      <div class="linha">
        <span class="chip">{{ dados.total }} orçamentos</span>
        <span class="chip chip--acento">R$ {{ dados.soma }}</span>
      </div>
    </header>

    <!-- 🚨 O QUE ESTA ABA NÃO FAZ, ESCRITO. Orçamento emitido não muda de
         conteúdo, e isso é regra do documento, não falta de botão. Sem esta
         frase, a aba parece uma tela incompleta. -->
    <p class="aviso aviso--info orc__regra">
      <i class="bi bi-info-circle aviso__icone" aria-hidden="true"></i>
      <span>
        Esta aba é <strong>só de consulta</strong>: orçamento emitido não muda
        de conteúdo, então aqui não se edita, não se cancela e não se emite.
        Para emitir, abra a conversa do técnico e use <em>Agendar</em>. A
        numeração fica em Configuração › Orçamento.
      </span>
    </p>

    <section class="cartao tela__bloco">
      <div class="cartao__corpo linha linha--quebra">
        <label class="campo">
          <span class="campo__rotulo">De</span>
          <input v-model="de" class="campo__entrada" type="date" />
        </label>
        <label class="campo">
          <span class="campo__rotulo">Até</span>
          <input v-model="ate" class="campo__entrada" type="date" />
        </label>
        <label class="campo campo--curto">
          <span class="campo__rotulo">Nº</span>
          <input
            v-model="numero"
            class="campo__entrada"
            type="search"
            inputmode="numeric"
            placeholder="exato"
            @keyup.enter="buscar"
          />
        </label>
        <label class="campo campo--curto">
          <span class="campo__rotulo">OS</span>
          <input
            v-model="osNumero"
            class="campo__entrada"
            type="search"
            inputmode="numeric"
            placeholder="nº da OS"
            @keyup.enter="buscar"
          />
        </label>
        <label class="campo">
          <span class="campo__rotulo">Técnico</span>
          <select v-model="tecnicoId" class="campo__entrada" @change="buscar">
            <option value="">todos</option>
            <option v-for="t in filtros.tecnicos" :key="t.contato_id" :value="t.contato_id">
              {{ t.tecnico }} ({{ t.orcamentos }})
            </option>
          </select>
        </label>
        <label class="campo">
          <span class="campo__rotulo">Emitido por</span>
          <select v-model="atendenteId" class="campo__entrada" @change="buscar">
            <option value="">todos</option>
            <option
              v-for="a in filtros.atendentes"
              :key="a.atendente_id"
              :value="a.atendente_id"
            >
              {{ a.nome }} ({{ a.orcamentos }})
            </option>
          </select>
        </label>
        <label class="campo campo--caixa">
          <input v-model="soComPdf" type="checkbox" @change="buscar" />
          <span class="campo__rotulo">só com PDF</span>
        </label>

        <button class="botao botao--primario" type="button" @click="buscar">
          <i class="bi bi-search" aria-hidden="true"></i> Buscar
        </button>
        <button class="botao botao--contorno" type="button" @click="limpar">
          limpar
        </button>
      </div>
    </section>

    <p v-if="erro" class="aviso aviso--erro" role="alert">
      <i class="bi bi-exclamation-octagon aviso__icone" aria-hidden="true"></i>
      <span>{{ erro }}</span>
    </p>

    <p v-if="carregando" class="linha fraco">
      <span class="girando"></span> Lendo…
    </p>

    <div v-else-if="vazio" class="vazio">
      <i class="bi bi-receipt-cutoff vazio__icone" aria-hidden="true"></i>
      <p class="vazio__titulo">Nenhum orçamento neste filtro</p>
      <p>
        Orçamento se emite na conversa do técnico, pelo botão
        <strong>Agendar</strong> — esta aba só mostra os que já saíram.
      </p>
    </div>

    <section v-else class="cartao tela__bloco">
      <div class="tabela--rolavel">
        <table class="tabela">
          <thead>
            <tr>
              <th>Nº</th>
              <th>Quando</th>
              <th>Técnico</th>
              <th>Linhas</th>
              <th>Total</th>
              <th>OS</th>
              <th>Agendamento</th>
              <th>PDF</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="o in dados.itens" :key="o.id">
              <td><span class="chip chip--codigo">{{ o.numero }}</span></td>
              <td class="pequeno fraco">{{ data(o.criado_em) }}</td>
              <td>
                <strong class="pequeno">{{ o.tecnico || '—' }}</strong>
                <p class="apagado pequeno">emitido por {{ o.atendente || '—' }}</p>
              </td>
              <td>
                <p v-for="i in o.itens" :key="i.ordem" class="pequeno orc__linha">
                  {{ i.servico }}
                  <span class="apagado">{{ i.quantidade_texto }} × R$ {{ i.preco_unit }}</span>
                  <span class="mono">R$ {{ i.valor }}</span>
                </p>
              </td>
              <td class="mono">R$ {{ o.total }}</td>
              <td>
                <!-- ⚠️ `ordens_os` é array de números, SEM chave estrangeira:
                     a OS vive no Harmonit. Então aqui é o número, e nada mais
                     se promete sobre ele. -->
                <template v-if="o.ordens_os.length">
                  <span v-for="n in o.ordens_os" :key="n" class="chip chip--pequeno mono">
                    {{ n }}
                  </span>
                </template>
                <span v-else class="apagado pequeno">sem OS</span>
              </td>
              <td>
                <template v-if="o.agendamento">
                  <span class="chip chip--ok chip--pequeno">{{ o.agendamento.estado }}</span>
                  <p class="apagado pequeno">
                    {{ data(o.agendamento.inicio) }}
                    <br />{{ o.agendamento.cliente_nome }}
                  </p>
                </template>
                <!-- "sem agendamento" é o estado COMUM (1 de 3 em 26/10), não
                     defeito: o elo só existe quando o orçamento foi emitido
                     antes do compromisso, no mesmo modal. -->
                <span v-else class="apagado pequeno">—</span>
              </td>
              <td>
                <div v-if="o.midia_id" class="orc__pdf">
                  <button
                    class="botao botao--pequeno botao--contorno"
                    type="button"
                    @click="abrirPdf(o)"
                  >
                    <i
                      class="bi"
                      :class="pdfAberto.id === o.id ? 'bi-x-lg' : 'bi-file-earmark-pdf'"
                      aria-hidden="true"
                    ></i>
                    {{ pdfAberto.id === o.id ? 'fechar' : 'abrir' }}
                  </button>
                  <button
                    class="botao botao--pequeno botao--contorno"
                    type="button"
                    title="Baixar o PDF"
                    @click="baixarPdf(o)"
                  >
                    <i class="bi bi-download" aria-hidden="true"></i>
                  </button>
                </div>
                <span v-else class="apagado pequeno">sem PDF</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- O PDF abre DENTRO da tela, abaixo do grid: nova aba com blob é
           bloqueada por bloqueador de pop-up em alguns navegadores, e aí o
           clique não faria nada e pareceria defeito. -->
      <div v-if="pdfAberto.url" class="orc__visor">
        <div class="linha">
          <strong class="pequeno">Orçamento aberto</strong>
          <button class="botao botao--pequeno botao--contorno" type="button" @click="soltarPdf">
            fechar
          </button>
        </div>
        <iframe :src="pdfAberto.url" title="PDF do orçamento"></iframe>
      </div>

      <nav v-if="dados.paginas > 1" class="linha orc__paginacao">
        <button
          class="botao botao--contorno botao--pequeno"
          :disabled="pagina <= 1"
          @click="pagina -= 1"
        >
          anterior
        </button>
        <span class="pequeno fraco">{{ pagina }} / {{ dados.paginas }}</span>
        <button
          class="botao botao--contorno botao--pequeno"
          :disabled="pagina >= dados.paginas"
          @click="pagina += 1"
        >
          próxima
        </button>
      </nav>
    </section>
  </div>
</template>

<style scoped>
.tela { max-width: 1240px; }

.tela__cabecalho {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--e-4);
  flex-wrap: wrap;
  margin-bottom: var(--e-5);
}
.tela__cabecalho p { max-width: var(--largura-texto); margin-top: var(--e-1); }

.tela__bloco { margin-bottom: var(--e-4); overflow: hidden; }

.orc__regra { margin-bottom: var(--e-4); }

.linha--quebra { flex-wrap: wrap; gap: var(--e-3); align-items: flex-end; }
.campo--curto { max-width: 120px; }
.campo--caixa { flex-direction: row; align-items: center; gap: var(--e-2); }

.orc__linha {
  display: flex;
  gap: var(--e-2);
  flex-wrap: wrap;
  align-items: baseline;
  margin: 0;
}

.orc__pdf { display: flex; gap: var(--e-2); align-items: center; flex-wrap: wrap; }

.orc__visor { padding: var(--e-3); border-top: 1px solid var(--borda); }
.orc__visor iframe {
  width: 100%;
  height: 70vh;
  border: 1px solid var(--borda);
  border-radius: var(--r-md);
  margin-top: var(--e-2);
  background: var(--superficie-2);
}

.orc__paginacao { justify-content: center; gap: var(--e-3); padding: var(--e-3); }
</style>
