<script setup>
/* ============================================================================
   CAD_1.2 — Contatos, com as três abas do registro
   ----------------------------------------------------------------------------
   CAD_1.2.1 dados · CAD_1.2.2 telefones · CAD_1.2.3 papéis

   As abas não têm rota própria: vivem dentro desta tela e herdam a permissão
   dela. O código existe mesmo assim, porque é ele que o log de auditoria grava
   -- quando o erro foi na aba de telefones, `CAD_1.2.2` é o que se procura.

   ⚠️ Os papéis (assinar · central 24h · financeiro) são GRAVADOS e não
   acionam nada na Fase 1. Existem para o cadastro nascer completo. A tela diz
   isso, senão alguém marca "central 24h" esperando que algo aconteça.
   ============================================================================ */
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'

import { api, ErroDeApi } from '../api/cliente.js'

const busca = ref('')
const pagina = ref(1)
const dados = ref(null)
const carregando = ref(true)
const erro = ref('')

const selecionado = ref(null)
const aba = ref('CAD_1.2.1')

let debounce = null

const ABAS = [
  { codigo: 'CAD_1.2.1', titulo: 'Dados', icone: 'bi-person' },
  { codigo: 'CAD_1.2.2', titulo: 'Telefones', icone: 'bi-telephone' },
  { codigo: 'CAD_1.2.3', titulo: 'Papéis', icone: 'bi-person-badge' },
]

const PAPEIS = {
  assinar: 'Assina contrato',
  central_24h: 'Central 24 h',
  financeiro: 'Financeiro',
}

/* ⚠️ ESTA LISTA É CÓPIA DO CHECK DO BANCO (`contato_relacao_check`, migração
   023). O banco é quem manda: se divergir, o <select> oferece uma opção que a
   gravação recusa. Mudar o vocabulário é migração, e as duas listas andam
   juntas -- `cadastro.RELACOES` no backend é a terceira. */
const RELACOES = ['cliente', 'fornecedor', 'parceiro', 'tecnico', 'lead',
                  'colaborador', 'teste', 'sem_identificacao']

/* Nome legível do valor cru do banco. `sem_identificacao` é o DEFAULT desde a
   migração 031: é como o contato nasce, e não uma marcação de ninguém. */
const NOME_RELACAO = {
  cliente: 'Cliente',
  fornecedor: 'Fornecedor',
  parceiro: 'Parceiro',
  tecnico: 'Técnico',
  lead: 'Lead',
  colaborador: 'Colaborador',
  teste: 'Teste',
  sem_identificacao: 'Sem identificação',
}

/* ---- filtro e marcação em lote (25/08) -----------------------------------
   🚨 O LOTE EXISTE PORQUE A BASE MENTE. 1.750 dos 1.754 contatos dizem
   "cliente" porque até a migração 031 o INSERT do sync gravava essa palavra
   literal. Ninguém corrige 1.750 linhas uma a uma -- e sem base honesta o
   interruptor de automação por tipo dispara para quem não devia. */
const tiposFiltro = ref([])
const filtroAberto = ref(false)

/* ⚠️ Fecha ao clicar fora: popover por cima da tabela faz a pessoa clicar
   duas vezes achando que a tela travou. */
function fecharFiltroSeForaDele(evento) {
  if (!filtroAberto.value) return
  if (!evento.target.closest('.filtro')) filtroAberto.value = false
}
const marcados = ref([])
const relacaoDoLote = ref('')
const aplicandoLote = ref(false)
const recadoLote = ref('')

function alternarTipoFiltro(valor) {
  tiposFiltro.value = tiposFiltro.value.includes(valor)
    ? tiposFiltro.value.filter((t) => t !== valor)
    : [...tiposFiltro.value, valor]
  pagina.value = 1
  carregar()
}

function alternarMarcado(id) {
  marcados.value = marcados.value.includes(id)
    ? marcados.value.filter((m) => m !== id)
    : [...marcados.value, id]
}

const todosMarcados = computed(
  () => itens.value.length > 0 && itens.value.every(
    (i) => marcados.value.includes(i.id)),
)

function alternarTodos() {
  const daPagina = itens.value.map((i) => i.id)
  marcados.value = todosMarcados.value
    ? marcados.value.filter((m) => !daPagina.includes(m))
    : [...new Set([...marcados.value, ...daPagina])]
}

async function aplicarLote() {
  if (!marcados.value.length || !relacaoDoLote.value) return
  aplicandoLote.value = true
  recadoLote.value = ''
  erro.value = ''
  try {
    const r = await api.put('/api/contatos/relacao-em-lote', {
      ids: marcados.value,
      relacao: relacaoDoLote.value,
    })
    /* ⚠️ Diz quantos MUDARAM, não "pronto". Pedir 40 e mudar 37 quer dizer
       que 3 já estavam assim -- e quem marcou precisa saber. */
    recadoLote.value = r.mudados === r.pedidos
      ? `${r.mudados} contato(s) marcados como ${NOME_RELACAO[r.relacao]}.`
      : `${r.mudados} de ${r.pedidos} mudaram — os outros já estavam assim.`
    marcados.value = []
    relacaoDoLote.value = ''
    await carregar()
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui marcar.'
  } finally {
    aplicandoLote.value = false
  }
}

const salvandoRelacao = ref(false)
const relacaoSalva = ref(false)

async function salvarRelacao(nova) {
  if (!selecionado.value || nova === selecionado.value.relacao) return
  salvandoRelacao.value = true
  relacaoSalva.value = false
  erro.value = ''
  try {
    await api.put(`/api/contatos/${selecionado.value.id}/relacao`, { relacao: nova })
    // 🚨 Relê em vez de confiar no 200: o que vale é o que o banco gravou.
    selecionado.value = await api.get(`/api/contatos/${selecionado.value.id}`)
    relacaoSalva.value = true
    await carregar()
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui gravar a relação.'
  } finally {
    salvandoRelacao.value = false
  }
}

const itens = computed(() => dados.value?.itens || [])
const interpretacao = computed(() => dados.value?.busca || { tipo: 'vazio' })
const total = computed(() => dados.value?.total ?? 0)
const paginas = computed(() => dados.value?.paginas ?? 1)

async function carregar() {
  carregando.value = true
  try {
    const p = new URLSearchParams({
      busca: busca.value,
      pagina: String(pagina.value),
    })
    if (tiposFiltro.value.length) p.set('relacoes', tiposFiltro.value.join(','))
    dados.value = await api.get(`/api/contatos?${p}`)
    erro.value = ''
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Falha ao ler os contatos.'
  } finally {
    carregando.value = false
  }
}

async function abrir(item) {
  aba.value = 'CAD_1.2.1'
  relacaoSalva.value = false
  try {
    selecionado.value = await api.get(`/api/contatos/${item.id}`)
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Falha ao abrir o contato.'
  }
}

watch(busca, () => {
  clearTimeout(debounce)
  debounce = setTimeout(() => {
    pagina.value = 1
    carregar()
  }, 300)
})

watch(pagina, carregar)

function numero(n) {
  return (n ?? 0).toLocaleString('pt-BR')
}

function telefoneBonito(e164) {
  const m = /^\+55(\d{2})(\d{4,5})(\d{4})$/.exec(e164 || '')
  return m ? `(${m[1]}) ${m[2]}-${m[3]}` : e164 || '—'
}

function quando(iso) {
  return iso ? new Date(iso).toLocaleString('pt-BR') : '—'
}

onMounted(() => {
  carregar()
  document.addEventListener('click', fecharFiltroSeForaDele)
})
onUnmounted(() => document.removeEventListener('click', fecharFiltroSeForaDele))
</script>

<template>
  <div class="tela">
    <header class="tela__cabecalho">
      <div>
        <h1>Contatos</h1>
        <p class="fraco pequeno">
          Pessoas, seus telefones em E.164 com o bruto preservado, e seus papéis.
        </p>
      </div>
      <span class="chip chip--codigo chip--acento">CAD_1.2</span>
    </header>

    <section class="cartao">
      <div class="cartao__corpo">
        <!-- 🚨 O FILTRO MORA NO CAMPO DE BUSCA. Buscar e filtrar são a
             MESMA pergunta -- "quais contatos eu quero ver" -- e separá-los
             em dois lugares enchia a tela de botões antes de qualquer
             contato aparecer. -->
        <div class="cad__linhabusca">
          <label class="cad__busca">
            <i class="bi bi-search" aria-hidden="true"></i>
            <input
              v-model="busca"
              class="campo"
              type="search"
              placeholder="Nome, documento do cliente ou telefone…"
              aria-label="Buscar contato"
            />
          </label>

          <div class="filtro">
            <button
              class="botao botao--contorno botao--icone"
              type="button"
              :class="{ 'botao--filtrando': tiposFiltro.length }"
              :aria-expanded="filtroAberto"
              title="Filtrar por tipo"
              aria-label="Filtrar por tipo"
              @click.prevent="filtroAberto = !filtroAberto"
            >
              <i class="bi bi-funnel" aria-hidden="true"></i>
              <span v-if="tiposFiltro.length" class="filtro__conta">
                {{ tiposFiltro.length }}
              </span>
            </button>

            <div v-if="filtroAberto" class="filtro__caixa">
              <p class="filtro__titulo">Tipo</p>
              <label v-for="r in RELACOES" :key="r" class="filtro__linha">
                <input
                  type="checkbox"
                  :checked="tiposFiltro.includes(r)"
                  @change="alternarTipoFiltro(r)"
                />
                <span>{{ NOME_RELACAO[r] }}</span>
              </label>
              <button
                v-if="tiposFiltro.length"
                class="botao botao--pequeno botao--fantasma filtro__limpar"
                type="button"
                @click.prevent="tiposFiltro = []; pagina = 1; carregar()"
              >
                limpar filtro
              </button>
            </div>
          </div>
        </div>

        <span v-if="tiposFiltro.length" class="filtro__resumo pequeno">
          <i class="bi bi-funnel-fill" aria-hidden="true"></i>
          {{ RELACOES.filter((r) => tiposFiltro.includes(r))
                     .map((r) => NOME_RELACAO[r]).join(' · ') }}
        </span>
      </div>

      <!-- 🚨 A BARRA SÓ APARECE COM ALGO MARCADO. Barra de ação permanente
           num cadastro de 1.754 linhas é convite para clique errado, e marcar
           tipo em massa não tem desfazer. -->
      <div v-if="marcados.length" class="cartao__corpo lote">
        <strong>{{ marcados.length }} selecionado(s)</strong>
        <label class="campo lote__campo">
          <span class="so-leitor">Marcar como</span>
          <select v-model="relacaoDoLote" class="campo__entrada">
            <option value="">marcar como…</option>
            <option v-for="r in RELACOES" :key="r" :value="r">
              {{ NOME_RELACAO[r] }}
            </option>
          </select>
        </label>
        <button
          class="botao botao--pequeno botao--primario"
          type="button"
          :disabled="!relacaoDoLote || aplicandoLote"
          @click="aplicarLote"
        >
          <span v-if="aplicandoLote" class="girando"></span>
          Aplicar
        </button>
        <button
          class="botao botao--pequeno botao--fantasma"
          type="button"
          @click="marcados = []"
        >
          limpar seleção
        </button>
      </div>

      <p v-if="recadoLote" class="aviso aviso--ok">
        <i class="bi bi-check-circle aviso__icone" aria-hidden="true"></i>
        <span>{{ recadoLote }}</span>
      </p>

      <p v-if="interpretacao.tipo === 'telefone'" class="aviso aviso--info">
        <i class="bi bi-telephone aviso__icone" aria-hidden="true"></i>
        <span>
          Procurando pelo telefone
          <strong>{{ telefoneBonito(interpretacao.e164) }}</strong>, nas duas
          grafias — <code class="mono">{{ interpretacao.variantes.join(' · ') }}</code>.
        </span>
      </p>
    </section>

    <p v-if="erro" class="aviso aviso--erro" role="alert">
      <i class="bi bi-exclamation-octagon aviso__icone" aria-hidden="true"></i>
      <span>{{ erro }}</span>
    </p>

    <p v-if="carregando" class="linha fraco">
      <span class="girando"></span> Consultando…
    </p>

    <div v-else-if="!itens.length" class="vazio">
      <i class="bi bi-person-x vazio__icone" aria-hidden="true"></i>
      <p class="vazio__titulo">Nenhum contato encontrado</p>
    </div>

    <template v-else>
      <p class="fraco pequeno cad__contagem">
        {{ numero(total) }} {{ total === 1 ? 'contato' : 'contatos' }}
        <span v-if="paginas > 1">· página {{ pagina }} de {{ paginas }}</span>
      </p>

      <div class="tabela--rolavel">
        <table class="tabela">
          <thead>
            <tr>
              <th class="cad__marca">
                <input
                  type="checkbox"
                  :checked="todosMarcados"
                  :aria-label="todosMarcados ? 'Desmarcar a página' : 'Marcar a página'"
                  @change="alternarTodos"
                />
              </th>
              <th>Nome</th>
              <th>Cliente</th>
              <th>Relação</th>
              <th>Telefone principal</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="item in itens"
              :key="item.id"
              :class="{ 'cad__inativo': !item.ativo }"
            >
              <td class="cad__marca">
                <input
                  type="checkbox"
                  :checked="marcados.includes(item.id)"
                  :aria-label="`Selecionar ${item.nome}`"
                  @change="alternarMarcado(item.id)"
                />
              </td>
              <td><strong>{{ item.nome }}</strong></td>
              <td class="pequeno fraco">{{ item.cliente_nome || '—' }}</td>
              <td>
                <!-- ⚠️ Nome legível, não o valor cru: a tela mostrava
                     `sem_identificacao` com underscore. -->
                <span class="chip">{{ NOME_RELACAO[item.relacao] || item.relacao }}</span>
              </td>
              <td class="mono pequeno">
                {{ telefoneBonito(item.telefone) }}
                <span v-if="item.telefones > 1" class="fraco">
                  +{{ item.telefones - 1 }}
                </span>
              </td>
              <td>
                <button class="botao botao--fantasma botao--pequeno" @click="abrir(item)">
                  abrir
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <nav v-if="paginas > 1" class="linha cad__paginacao">
        <button
          class="botao botao--contorno botao--pequeno"
          :disabled="pagina <= 1"
          @click="pagina -= 1"
        >
          anterior
        </button>
        <span class="pequeno fraco">{{ pagina }} / {{ paginas }}</span>
        <button
          class="botao botao--contorno botao--pequeno"
          :disabled="pagina >= paginas"
          @click="pagina += 1"
        >
          próxima
        </button>
      </nav>
    </template>

    <!-- ------------------------------------------------------ detalhe/abas -->
    <section v-if="selecionado" class="cartao cad__detalhe">
      <header class="cartao__cabecalho">
        <span class="linha">
          <i class="bi bi-person" aria-hidden="true"></i>
          {{ selecionado.nome }}
        </span>
        <span class="linha">
          <span class="chip chip--codigo">{{ aba }}</span>
          <button class="botao botao--fantasma botao--pequeno" @click="selecionado = null">
            fechar
          </button>
        </span>
      </header>

      <nav class="cad__abas" role="tablist">
        <button
          v-for="a in ABAS"
          :key="a.codigo"
          class="cad__aba"
          :class="{ 'cad__aba--ativa': aba === a.codigo }"
          role="tab"
          :aria-selected="aba === a.codigo"
          @click="aba = a.codigo"
        >
          <i class="bi" :class="a.icone" aria-hidden="true"></i>
          {{ a.titulo }}
        </button>
      </nav>

      <div class="cartao__corpo">
        <!-- ------------------------------------------------ CAD_1.2.1 dados -->
        <dl v-if="aba === 'CAD_1.2.1'" class="cad__dados">
          <div><dt>Nome</dt><dd>{{ selecionado.nome }}</dd></div>
          <div><dt>Cliente</dt><dd>{{ selecionado.cliente_nome || '—' }}</dd></div>
          <div><dt>Documento do cliente</dt><dd class="mono">{{ selecionado.cliente_documento || '—' }}</dd></div>
          <!-- 🚨 O ÚNICO CAMPO EDITÁVEL DESTA ABA, e por um motivo medido: o
               sync grava 'cliente' para TODO contato do Harmonit, então
               1.751 de 1.752 estavam assim -- não porque a base seja toda de
               clientes, mas porque era uma constante no código. Não existe
               chave dura que separe fornecedor de cliente (conferido em
               12/08), então quem separa é gente, aqui. -->
          <div>
            <dt>Relação</dt>
            <dd>
              <select
                :value="selecionado.relacao"
                class="campo__entrada cad__relacao"
                :disabled="salvandoRelacao"
                @change="salvarRelacao($event.target.value)"
              >
                <option v-for="r in RELACOES" :key="r" :value="r">
                  {{ NOME_RELACAO[r] || r }}
                </option>
              </select>
              <span v-if="salvandoRelacao" class="apagado pequeno"> gravando…</span>
              <span v-else-if="relacaoSalva" class="chip chip--ok">gravado</span>
              <span class="campo__ajuda">
                O que a pessoa é para a Movisat. O sync do Harmonit
                <strong>não</strong> desfaz o que for marcado aqui.
              </span>
            </dd>
          </div>
          <div><dt>E-mail</dt><dd>{{ selecionado.email || '—' }}</dd></div>
          <div><dt>Origem</dt><dd>{{ selecionado.origem }}</dd></div>
          <div><dt>Id no Harmonit</dt><dd class="mono">{{ selecionado.harmonit_id || '—' }}</dd></div>
          <div><dt>Situação</dt><dd>{{ selecionado.ativo ? 'ativo' : 'inativo' }}</dd></div>
        </dl>

        <!-- -------------------------------------------- CAD_1.2.2 telefones -->
        <template v-else-if="aba === 'CAD_1.2.2'">
          <div v-if="!selecionado.telefones.length" class="vazio">
            <i class="bi bi-telephone-x vazio__icone" aria-hidden="true"></i>
            <p class="vazio__titulo">Nenhum telefone</p>
            <p>O Harmonit não tem número para este contato.</p>
          </div>

          <div v-else class="tabela--rolavel">
            <table class="tabela">
              <thead>
                <tr>
                  <th>E.164</th>
                  <th>Como veio</th>
                  <th>Campo</th>
                  <th>WhatsApp</th>
                  <th>Verificado</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="t in selecionado.telefones" :key="t.id">
                  <td class="mono">
                    {{ telefoneBonito(t.e164) }}
                    <span v-if="t.principal" class="chip chip--acento">principal</span>
                  </td>
                  <td class="mono pequeno fraco">{{ t.bruto }}</td>
                  <td><span class="chip">{{ t.origem_campo }}</span></td>
                  <td>
                    <span
                      class="chip"
                      :class="t.tem_whatsapp === true ? 'chip--ok'
                              : t.tem_whatsapp === false ? '' : 'chip--aviso'"
                    >
                      {{ t.tem_whatsapp === true ? 'sim'
                         : t.tem_whatsapp === false ? 'não' : 'não verificado' }}
                    </span>
                  </td>
                  <td class="pequeno fraco">{{ quando(t.verificado_em) }}</td>
                </tr>
              </tbody>
            </table>
          </div>

          <p class="aviso aviso--info cad__nota">
            <i class="bi bi-info-circle aviso__icone" aria-hidden="true"></i>
            <span>
              <strong>Como veio</strong> é o que o Harmonit gravou, palavra por
              palavra. O E.164 ao lado é derivado dele.
              <br /><span class="pequeno">
                Guardar os dois não é redundância: quando o número tem 8
                dígitos, o nono é acrescentado por regra — correta, mas ainda
                assim uma dedução. O bruto é o que prova que ninguém inventou.
              </span>
            </span>
          </p>

          <p class="aviso aviso--atencao cad__nota">
            <i class="bi bi-whatsapp aviso__icone" aria-hidden="true"></i>
            <span>
              <strong>Não verificado</strong> é diferente de <strong>não tem
              WhatsApp</strong>.
              <br /><span class="pequeno">
                Quem verifica é o Evolution, e ele precisa de um canal
                conectado. Enquanto o chip não parear, toda a base fica assim.
              </span>
            </span>
          </p>
        </template>

        <!-- ----------------------------------------------- CAD_1.2.3 papéis -->
        <template v-else>
          <ul class="cad__papeis">
            <li v-for="(rotulo, chave) in PAPEIS" :key="chave" class="linha">
              <i
                class="bi"
                :class="selecionado.papeis.includes(chave)
                  ? 'bi-check-square' : 'bi-square'"
                aria-hidden="true"
              ></i>
              <span :class="{ apagado: !selecionado.papeis.includes(chave) }">
                {{ rotulo }}
              </span>
            </li>
          </ul>

          <p class="aviso aviso--atencao cad__nota">
            <i class="bi bi-pause-circle aviso__icone" aria-hidden="true"></i>
            <span>
              Os papéis são <strong>gravados e não acionam nada</strong> na Fase 1.
              <br /><span class="pequeno">
                Existem para o cadastro nascer completo — não para gerar
                demanda. Marcar “Central 24 h” aqui não avisa ninguém, e é
                melhor dizer isso do que deixar alguém esperando.
              </span>
            </span>
          </p>
        </template>
      </div>
    </section>
  </div>
</template>

<style scoped>
.cad__busca {
  display: flex;
  align-items: center;
  gap: var(--e-2);
}

.cad__busca .campo {
  flex: 1;
}

.cad__contagem {
  margin: var(--e-3) 0;
}

.cad__inativo {
  opacity: 0.62;
}

.cad__paginacao {
  gap: var(--e-3);
  margin-top: var(--e-4);
  align-items: center;
}

.cad__detalhe {
  margin-top: var(--e-5);
}

.cad__abas {
  display: flex;
  gap: var(--e-1);
  padding: 0 var(--e-4);
  border-bottom: var(--borda-fina);
}

.cad__aba {
  display: inline-flex;
  align-items: center;
  gap: var(--e-2);
  padding: var(--e-3) var(--e-4);
  background: none;
  border: 0;
  border-bottom: 2px solid transparent;
  color: var(--texto-fraco);
  font: inherit;
  font-size: var(--txt-sm);
  cursor: pointer;
  transition: color var(--tempo-rapido), border-color var(--tempo-rapido);
}

.cad__aba:hover {
  color: var(--texto);
}

.cad__aba--ativa {
  color: var(--acento-texto);
  border-bottom-color: var(--acento);
  font-weight: var(--peso-medio);
}

.cad__dados {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(11rem, 1fr));
  gap: var(--e-4);
  margin: 0;
}

.cad__dados dt {
  font-size: var(--txt-xs);
  color: var(--texto-fraco);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.cad__dados dd {
  margin: 0;
}

.cad__relacao { max-width: 14rem; }
.cad__marca { width: 2.2rem; text-align: center; }

.cad__linhabusca { display: flex; align-items: center; gap: var(--e-2); }
.cad__linhabusca .cad__busca { flex: 1 1 auto; }

.filtro { position: relative; flex: none; }
.botao--filtrando {
  border-color: var(--acento);
  color: var(--acento);
  background: var(--acento-suave);
}
.filtro__conta {
  position: absolute;
  top: -6px; right: -6px;
  min-width: 16px; height: 16px; padding: 0 4px;
  border-radius: var(--r-full);
  background: var(--acento); color: var(--acento-texto);
  font-size: var(--txt-xs); line-height: 16px; text-align: center;
}
.filtro__caixa {
  position: absolute;
  top: calc(100% + var(--e-1)); right: 0;
  z-index: var(--z-flutuante);
  min-width: 220px; padding: var(--e-3);
  background: var(--superficie);
  border: var(--borda-fina) solid var(--borda);
  border-radius: var(--r-lg);
  box-shadow: var(--sombra-2);
}
.filtro__titulo {
  margin: 0 0 var(--e-2);
  font-size: var(--txt-sm); font-weight: var(--peso-forte);
  color: var(--texto-fraco);
}
.filtro__linha {
  display: flex; align-items: center; gap: var(--e-2);
  padding: var(--e-1) 0; cursor: pointer;
}
.filtro__limpar { margin-top: var(--e-2); padding-left: 0; }
.filtro__resumo {
  display: inline-flex; align-items: center; gap: var(--e-1);
  color: var(--acento); margin-top: var(--e-2);
}

.lote {
  display: flex;
  align-items: center;
  gap: var(--e-3);
  flex-wrap: wrap;
  background: var(--acento-suave);
  border-top: var(--borda-fina) solid var(--acento-borda);
}
.lote__campo { margin: 0; min-width: 12rem; }

.cad__papeis {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: var(--e-3);
}

.cad__nota {
  margin-top: var(--e-4);
}
</style>
