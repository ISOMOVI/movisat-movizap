<script setup>
/* ============================================================================
   CFG_12.1 — Mensagens rápidas (25/09, Plano 3)
   ----------------------------------------------------------------------------
   🔵 *"Serão em tipos: pode criar uma aba disso nas configurações de cada para
   controle tbm // Owner e admin criam as do tipo: 'Padrões'; outra aba é
   'Minhas Notas' onde ela pode criar as notas dela e deixar salvo ... tbm
   deve ter um tipo de lista chamada Formularios ... É possivel apelido curto
   como 'Mensagem de encerramento' para salvar a nota e ele quem aparecerá na
   lista da conversa"*. Formulário: 🔵 *"serão links"*, de owner e admin.

   🟡 Quem não administra a equipe vê Padrões e Formulários só para leitura:
   saber o que existe ajuda a usar. Quem barra a escrita é a rota.
   ============================================================================ */
import { computed, onMounted, ref } from 'vue'

import { api, ErroDeApi } from '../api/cliente.js'
import { VARIAVEIS, aplicarVariaveis } from '../util/variaveis.js'
import AjudaDaTela from '../componentes/AjudaDaTela.vue'
import ModalEdicao from '../componentes/ModalEdicao.vue'

const ABAS = [
  { tipo: 'padrao', rotulo: 'Padrões', ajuda: 'Textos da equipe, que todos usam na conversa com o cliente. Criados por quem administra a equipe.' },
  { tipo: 'nota', rotulo: 'Minhas notas', ajuda: 'Os seus textos prontos. Só você vê, na conversa com o cliente e no Chat interno.' },
  { tipo: 'formulario', rotulo: 'Formulários', ajuda: 'Links que se mandam ao cliente (ficha, cadastro, pesquisa). Criados por quem administra a equipe; aparecem também no Chat interno.' },
]
const EXEMPLO = { cliente: 'Pastelaria Velasco', contato: 'João' }

const grupos = ref({ padrao: [], nota: [], formulario: [] })
const podeEquipe = ref(false)
const aba = ref('padrao')
const carregando = ref(true)
const erro = ref('')
const recado = ref('')

const abaAtual = computed(() => ABAS.find((a) => a.tipo === aba.value))
const podeMexer = computed(() => aba.value === 'nota' || podeEquipe.value)
const lista = computed(() => grupos.value[aba.value] || [])

async function carregar() {
  carregando.value = true
  erro.value = ''
  try {
    const r = await api.get('/api/mensagens-rapidas/gestao')
    podeEquipe.value = Boolean(r.pode_equipe)
    grupos.value = { padrao: r.padrao || [], nota: r.nota || [], formulario: r.formulario || [] }
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui ler as mensagens rápidas.'
  } finally {
    carregando.value = false
  }
}
onMounted(carregar)

/* ---- o modal ------------------------------------------------------------- */
const editando = ref(null)
const form = ref({ apelido: '', conteudo: '', ativo: true })
const salvando = ref(false)
const erroModal = ref('')
const campoTexto = ref(null)
let retrato = ''

const ehLink = computed(() => editando.value?.tipo === 'formulario')
const sujo = computed(() => editando.value !== null && JSON.stringify(form.value) !== retrato)
const previa = computed(() => aplicarVariaveis(form.value.conteudo, EXEMPLO).texto)

function abrir(m) {
  editando.value = m.id ? m : { tipo: aba.value }
  form.value = m.id
    ? { apelido: m.apelido, conteudo: m.conteudo, ativo: m.ativo }
    : { apelido: '', conteudo: '', ativo: true }
  erroModal.value = ''
  recado.value = ''
  retrato = JSON.stringify(form.value)
}
function fechar() { editando.value = null }

/* Os três botões inserem a variável NO CURSOR -- ninguém precisa decorar a
   chave, e chave digitada errada ({Cliente}) não seria trocada. */
function inserirVariavel(chave) {
  const el = campoTexto.value
  const atual = form.value.conteudo
  const ini = el?.selectionStart ?? atual.length
  const fim = el?.selectionEnd ?? atual.length
  form.value.conteudo = atual.slice(0, ini) + chave + atual.slice(fim)
  requestAnimationFrame(() => {
    el?.focus()
    el?.setSelectionRange(ini + chave.length, ini + chave.length)
  })
}

async function salvar() {
  salvando.value = true
  erroModal.value = ''
  try {
    const corpo = { tipo: editando.value.tipo, ...form.value }
    if (editando.value.id) await api.put(`/api/mensagens-rapidas/${editando.value.id}`, corpo)
    else await api.post('/api/mensagens-rapidas', corpo)
    recado.value = `"${form.value.apelido}" salva.`
    fechar()
    await carregar()
  } catch (e) {
    erroModal.value = e instanceof ErroDeApi ? e.message : 'Não consegui salvar.'
  } finally {
    salvando.value = false
  }
}

const apagando = ref(null)
async function confirmarApagar() {
  const m = apagando.value
  try {
    await api.del(`/api/mensagens-rapidas/${m.id}`)
    recado.value = `"${m.apelido}" apagada.`
    apagando.value = null
    await carregar()
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui apagar.'
    apagando.value = null
  }
}
</script>

<template>
  <div class="tela">
    <header class="tela__cabecalho">
      <div>
        <h1>Mensagens rápidas</h1>
        <AjudaDaTela>
          Textos prontos que entram no campo de escrever pelo botão
          <i class="bi bi-lightning-charge" aria-hidden="true"></i> da conversa, e ainda podem ser editados antes de enviar.
        </AjudaDaTela>
      </div>
    </header>

    <nav class="abas-mr" role="tablist" aria-label="Tipos">
      <button v-for="a in ABAS" :key="a.tipo" type="button" role="tab" class="abas-mr__aba"
              :class="{ 'abas-mr__aba--ativa': aba === a.tipo }" :aria-selected="aba === a.tipo"
              @click="aba = a.tipo">
        {{ a.rotulo }} <span class="apagado pequeno">{{ (grupos[a.tipo] || []).length }}</span>
      </button>
    </nav>

    <p v-if="erro" class="aviso aviso--erro" role="alert">{{ erro }}</p>
    <p v-if="recado" class="aviso aviso--ok" role="status">{{ recado }}</p>

    <section class="cartao tela__bloco">
      <div class="cartao__corpo pilha">
        <div class="cabeca">
          <p class="apagado pequeno cabeca__ajuda">{{ abaAtual.ajuda }}</p>
          <button v-if="podeMexer" class="botao botao--primario" type="button" @click="abrir({})">
            <i class="bi bi-plus-lg" aria-hidden="true"></i>
            {{ aba === 'formulario' ? 'Novo formulário' : 'Nova mensagem' }}
          </button>
        </div>
        <p v-if="!podeMexer" class="aviso aviso--info pequeno">
          <i class="bi bi-eye aviso__icone" aria-hidden="true"></i>
          <span>Só leitura: quem administra a equipe cria e altera estas. Você as usa pelo botão da conversa.</span>
        </p>

        <p v-if="carregando" class="linha fraco"><span class="girando"></span> Lendo…</p>
        <p v-else-if="!lista.length" class="apagado">
          Nenhuma ainda.<template v-if="podeMexer"> Crie a primeira em
          "{{ aba === 'formulario' ? 'Novo formulário' : 'Nova mensagem' }}".</template>
        </p>
        <ul v-else class="lista">
          <li v-for="m in lista" :key="m.id" class="item" :class="{ 'item--inativa': !m.ativo }">
            <div class="item__texto">
              <strong>{{ m.apelido }}</strong>
              <span v-if="!m.ativo" class="chip chip--pequeno">desativada</span>
              <small class="apagado item__conteudo">{{ m.conteudo }}</small>
            </div>
            <div v-if="podeMexer" class="item__acoes">
              <button class="botao botao--pequeno botao--contorno" type="button" @click="abrir(m)">
                <i class="bi bi-pencil" aria-hidden="true"></i> Editar
              </button>
              <button class="botao botao--pequeno botao--fantasma" type="button" @click="apagando = m">
                <i class="bi bi-trash" aria-hidden="true"></i> Apagar
              </button>
            </div>
          </li>
        </ul>
      </div>
    </section>

    <ModalEdicao
      v-if="editando"
      :titulo="editando.id ? editando.apelido : (ehLink ? 'Novo formulário' : 'Nova mensagem rápida')"
      :subtitulo="ABAS.find((a) => a.tipo === editando.tipo).rotulo"
      :sujo="sujo"
      :salvando="salvando"
      :pode-salvar="Boolean(form.apelido.trim() && form.conteudo.trim())"
      @salvar="salvar"
      @fechar="fechar"
    >
      <label class="campo">
        <span class="campo__rotulo">Apelido</span>
        <input v-model="form.apelido" class="campo__entrada" maxlength="60"
               placeholder="ex.: Mensagem de encerramento" />
        <span class="campo__ajuda">É o que aparece na lista da conversa.</span>
      </label>

      <label v-if="ehLink" class="campo">
        <span class="campo__rotulo">Link</span>
        <input v-model="form.conteudo" class="campo__entrada" type="url" maxlength="4000"
               inputmode="url" placeholder="https://" />
        <span class="campo__ajuda">Vai para o campo de escrever como está, para o cliente clicar.</span>
      </label>
      <template v-else>
        <label class="campo">
          <span class="campo__rotulo">Texto</span>
          <textarea ref="campoTexto" v-model="form.conteudo" class="campo__entrada" rows="6"
                    maxlength="4000"></textarea>
        </label>
        <div class="variaveis">
          <span class="campo__rotulo">Preencher sozinho</span>
          <div class="variaveis__botoes">
            <button v-for="v in VARIAVEIS" :key="v.chave" type="button"
                    class="botao botao--pequeno botao--contorno" :title="v.ajuda"
                    @click="inserirVariavel(v.chave)">
              <i class="bi bi-plus" aria-hidden="true"></i> {{ v.rotulo }}
            </button>
          </div>
          <span class="campo__ajuda">Entra no ponto do cursor. Na conversa vira o dado dela.</span>
        </div>
        <div v-if="form.conteudo.trim()" class="previa">
          <span class="campo__rotulo">Como fica (exemplo)</span>
          <p class="previa__texto">{{ previa }}</p>
        </div>
      </template>

      <label class="ligada">
        <input v-model="form.ativo" type="checkbox" />
        <span>Aparece na conversa</span>
      </label>

      <p v-if="erroModal" class="aviso aviso--erro" role="alert">{{ erroModal }}</p>
    </ModalEdicao>

    <div v-if="apagando" class="modal" @click.self="apagando = null">
      <div class="modal__caixa" role="dialog" aria-modal="true" aria-label="Apagar">
        <p class="modal__titulo">Apagar "{{ apagando.apelido }}"?</p>
        <p class="modal__texto pequeno">O que já foi enviado nas conversas continua lá.</p>
        <div class="modal__acoes">
          <button class="botao botao--contorno" type="button" @click="apagando = null">Cancelar</button>
          <button class="botao botao--perigo" type="button" @click="confirmarApagar">Apagar</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.tela { max-width: 860px; }
.tela__cabecalho { margin-bottom: var(--e-4); }
.tela__bloco { margin-bottom: var(--e-4); }
.aviso { margin-bottom: var(--e-3); }

.abas-mr { display: flex; flex-wrap: wrap; gap: var(--e-2); margin-bottom: var(--e-4); }
.abas-mr__aba {
  min-height: var(--altura-toque); padding: 0 var(--e-4);
  border: var(--borda-fina) solid var(--borda); border-radius: var(--r-full);
  background: var(--superficie); color: inherit; font: inherit; cursor: pointer;
}
.abas-mr__aba--ativa { border-color: var(--acento); background: var(--acento-suave); color: var(--acento); font-weight: var(--peso-medio); }

.cabeca { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--e-3); flex-wrap: wrap; }
.cabeca__ajuda { margin: 0; max-width: 520px; }

.lista { list-style: none; margin: 0; padding: 0; border: var(--borda-fina) solid var(--borda); border-radius: var(--r-md); }
.item { display: flex; align-items: center; justify-content: space-between; gap: var(--e-3); flex-wrap: wrap; padding: var(--e-3); }
.item + .item { border-top: var(--borda-fina) solid var(--borda); }
.item--inativa .item__texto { opacity: .6; }
.item__texto { display: flex; flex-direction: column; gap: 2px; min-width: 0; flex: 1 1 280px; }
.item__conteudo {
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  overflow: hidden; overflow-wrap: anywhere; white-space: pre-line;
}
.item__acoes { display: flex; gap: var(--e-2); }

.variaveis { display: flex; flex-direction: column; gap: var(--e-2); margin-bottom: var(--e-4); }
.variaveis__botoes { display: flex; flex-wrap: wrap; gap: var(--e-2); }
.previa { margin-bottom: var(--e-4); }
.previa__texto {
  margin: var(--e-1) 0 0; padding: var(--e-3); border-radius: var(--r-md);
  background: var(--superficie-2); white-space: pre-line; overflow-wrap: anywhere;
}
.ligada { display: flex; align-items: center; gap: var(--e-2); cursor: pointer; margin-bottom: var(--e-3); }
.ligada input { width: 18px; height: 18px; accent-color: var(--acento); }
</style>
