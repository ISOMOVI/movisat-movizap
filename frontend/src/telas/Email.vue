<script setup>
/* ============================================================================
   EML_1.1 — E-mail
   ----------------------------------------------------------------------------
   🚨 NUNCA SE MISTURA COM O WHATSAPP (decisão do usuário em 10/08). Caixa
   própria, marcadores próprios, tela própria. Nada aqui entra na caixa de
   entrada de conversas, e vice-versa.

   Ela mora no MoviZap por dois motivos: atender, e SOMAR CADASTRO -- o
   remetente identifica a empresa, e 788 dos 944 clientes ativos já têm e-mail
   no cadastro. 442 deles não têm WhatsApp alcançável: é aqui que se fala com
   quem o WhatsApp não alcança.

   ⚠️ EM CONSTRUÇÃO, e a tela diz isso. Hoje ela LÊ; responder e encaminhar
   exigem o escopo `gmail.send`, que é outro consentimento.
   ============================================================================ */
import { ref, computed, onMounted } from 'vue'

import { api, ErroDeApi } from '../api/cliente.js'

const marcadores = ref([])
const mensagens = ref([])
const aberta = ref(null)
const marcadorAtual = ref('INBOX')
const busca = ref('')
const carregando = ref(false)

/* O menu de pastas recolhe, como no Gmail. Fica guardado porque quem recolhe
   quer que continue recolhido amanhã -- e não é preferência que valha uma
   coluna no banco. */
const menuAberto = ref(localStorage.getItem('movizap.email.menu') !== 'fechado')
/* ⚠️ SÓ LEITURA HOJE. O escopo concedido é `gmail.readonly`: escrever exige
   outro consentimento. Os botões aparecem para a tela ser a tela final, e
   dizem por que não funcionam -- em vez de sumirem e a pessoa procurar. */
/* ---- escrever -------------------------------------------------------------
   🚨 UMA MENSAGEM POR VEZ, de propósito. Não existe campo de lista nem rota
   que receba vários destinatários: e-mail enviado não volta, e disparo é
   outro produto -- a mesma regra que já vale no WhatsApp. */
const escrevendo = ref(false)
const rascunho = ref({ para: '', cc: '', cco: '', assunto: '', corpo: '', responder_a: null })
/* Cc e Cco começam escondidos, como no Gmail: a maioria dos e-mails não usa,
   e dois campos vazios a mais atrapalham quem só quer responder. */
const mostrarCopias = ref(false)
const editor = ref(null)
const anexos = ref([])
const subindo = ref(false)

async function anexar(evento) {
  const arquivos = Array.from(evento.target.files || [])
  subindo.value = true
  for (const f of arquivos) {
    const dados = new FormData()
    dados.append('arquivo', f)
    try {
      /* Sobe direto por fetch: `api.post` manda JSON, e FormData precisa que
         o navegador monte o `boundary` sozinho -- definir Content-Type à mão
         quebra o upload de um jeito que só aparece no servidor. */
      const r = await fetch('/api/email/anexo', {
        method: 'POST',
        headers: { Authorization: `Bearer ${localStorage.getItem('movizap.token')}` },
        body: dados,
      })
      if (!r.ok) throw new Error()
      anexos.value.push(await r.json())
    } catch {
      erro.value = `Não consegui subir ${f.name}.`
    }
  }
  subindo.value = false
  evento.target.value = ''
}

function tirarAnexo(id) {
  anexos.value = anexos.value.filter((a) => a.id !== id)
}

function tamanho(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1048576) return `${Math.round(bytes / 1024)} KB`
  return `${(bytes / 1048576).toFixed(1)} MB`
}

/* ⚠️ `execCommand` está marcado como obsoleto há anos, mas funciona em todos
   os navegadores atuais e não tem substituto padronizado -- o `Editing API`
   nunca saiu do papel. A alternativa seria uma biblioteca de editor, que
   sozinha pesa mais que todo o nosso bundle. Quando quebrar, troca-se. */
function formatar(comando, valor = null) {
  document.execCommand(comando, false, valor)
  editor.value?.focus()
}

function inserirLink() {
  const url = prompt('Endereço do link:')
  if (url) formatar('createLink', url)
}

/* O que vai no envio: HTML do editor + versão em texto, na mesma mensagem.
   Quem lê sem HTML recebe o texto; ninguém recebe tag crua. */
function corpoDoEditor() {
  const el = editor.value
  if (!el) return { html: '', texto: rascunho.value.corpo || '' }
  return { html: el.innerHTML, texto: el.innerText }
}

const FERRAMENTAS = [
  { i: 'bi-type-bold', c: 'bold', t: 'Negrito' },
  { i: 'bi-type-italic', c: 'italic', t: 'Itálico' },
  { i: 'bi-type-underline', c: 'underline', t: 'Sublinhado' },
  { sep: true },
  { i: 'bi-list-ul', c: 'insertUnorderedList', t: 'Lista' },
  { i: 'bi-list-ol', c: 'insertOrderedList', t: 'Lista numerada' },
  { sep: true },
  { i: 'bi-text-left', c: 'justifyLeft', t: 'Alinhar à esquerda' },
  { i: 'bi-text-center', c: 'justifyCenter', t: 'Centralizar' },
  { i: 'bi-text-right', c: 'justifyRight', t: 'Alinhar à direita' },
  { sep: true },
  { i: 'bi-quote', c: 'formatBlock', v: 'blockquote', t: 'Citação' },
  { i: 'bi-eraser', c: 'removeFormat', t: 'Limpar formatação' },
]
const enviando = ref(false)

function novaMensagem() {
  rascunho.value = { para: '', cc: '', cco: '', assunto: '', corpo: '', responder_a: null }
  mostrarCopias.value = false
  escrevendo.value = true
}

function responder(encaminhar = false) {
  if (!aberta.value) return
  const a = aberta.value
  mostrarCopias.value = false
  rascunho.value = {
    cc: '', cco: '',
    para: encaminhar ? '' : (a.remetente || ''),
    assunto: (encaminhar ? 'Enc: ' : 'Re: ') + (a.assunto || '').replace(/^(Re|Enc):\s*/i, ''),
    corpo: `\n\n--- Em ${new Date(a.enviado_em).toLocaleString('pt-BR')}, ${a.remetente} escreveu:\n${a.texto || ''}`,
    // Só a resposta encaixa na conversa existente; encaminhar abre fio novo.
    responder_a: encaminhar ? null : a.id,
  }
  escrevendo.value = true
}

async function mandar() {
  enviando.value = true
  erro.value = ''
  try {
    const c = corpoDoEditor()
    await api.post('/api/email/enviar',
                   { ...rascunho.value, corpo: c.texto, html: c.html,
                     anexos: anexos.value.map((a) => a.id) })
    anexos.value = []
    recado.value = 'Enviado.'
    escrevendo.value = false
    await carregar()
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui enviar.'
  } finally {
    enviando.value = false
  }
}

/* ---- vincular ao cadastro -------------------------------------------------
   🚨 É O OBJETIVO: o e-mail existir aqui para SOMAR CADASTRO. Sem isto o
   painel identifica só quem casa sozinho e o resto morre como mensagem. */
const buscaEmpresa = ref('')
const achados = ref([])

async function procurarEmpresa() {
  if (buscaEmpresa.value.trim().length < 2) { achados.value = []; return }
  try {
    const r = await api.get(
      `/api/conversas/buscar-empresa?termo=${encodeURIComponent(buscaEmpresa.value)}`)
    achados.value = r.itens || []
  } catch { achados.value = [] }
}

async function vincular(clienteId) {
  try {
    const r = await api.post(`/api/email/mensagens/${aberta.value.id}/vincular`,
                             { cliente_id: clienteId })
    recado.value = `Vinculado a ${r.cliente} — ${r.mensagens} mensagem(ns) deste remetente.`
    buscaEmpresa.value = ''
    achados.value = []
    await abrir(aberta.value.id)
    await carregar()
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui vincular.'
  }
}

/* ---- assinatura ---------------------------------------------------------- */
const assinatura = ref('')
const editandoAssinatura = ref(false)

async function carregarAssinatura() {
  try { assinatura.value = (await api.get('/api/eu/assinatura')).html || '' } catch {}
}
async function salvarAssinatura() {
  await api.put('/api/eu/assinatura', { html: assinatura.value })
  editandoAssinatura.value = false
  recado.value = 'Assinatura salva.'
}

function alternarMenu() {
  menuAberto.value = !menuAberto.value
  localStorage.setItem('movizap.email.menu', menuAberto.value ? 'aberto' : 'fechado')
}
const erro = ref('')
const recado = ref('')

/* 🚨 A API do Gmail devolve identificador interno: `INBOX`, `CATEGORY_UPDATES`,
   `UNREAD`. Ninguém que abre uma caixa de e-mail deveria descobrir que existe
   uma API por trás -- aqui eles viram nome de gente. */
const NOMES = {
  INBOX: 'Caixa de entrada',
  SENT: 'Enviados',
  STARRED: 'Com estrela',
  IMPORTANT: 'Importantes',
  UNREAD: 'Não lidas',
}

/* Lixo, rascunho e as CATEGORIAS internas do Gmail não aparecem: são
   classificação automática dele, não organização de quem atende. */
const ESCONDIDOS = ['SPAM', 'TRASH', 'CHAT', 'DRAFT']

function rotulo(m) {
  return NOMES[m.id_externo] || m.nome
}

const visiveis = computed(() =>
  marcadores.value
    .filter((m) => !ESCONDIDOS.includes(m.id_externo))
    .filter((m) => !m.id_externo.startsWith('CATEGORY_'))
    .sort((a, b) => {
      // Caixa de entrada e Enviados primeiro; os seus marcadores depois.
      const ordem = ['INBOX', 'SENT', 'STARRED', 'IMPORTANT', 'UNREAD']
      const ia = ordem.indexOf(a.id_externo)
      const ib = ordem.indexOf(b.id_externo)
      if (ia !== ib) return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib)
      return rotulo(a).localeCompare(rotulo(b))
    }),
)

/* Iniciais do remetente, como toda caixa moderna. Sem foto: não temos, e
   inventar avatar genérico é ruído. */
function iniciais(m) {
  const base = (m.remetente_nome || m.remetente || '?').trim()
  const partes = base.replace(/[<>"]/g, '').split(/[\s@.]+/).filter(Boolean)
  return ((partes[0]?.[0] || '?') + (partes[1]?.[0] || '')).toUpperCase()
}

function corDaInicial(m) {
  const base = (m.remetente || '?')
  let soma = 0
  for (const c of base) soma += c.charCodeAt(0)
  return `hsl(${soma % 360} 45% 42%)`
}

async function carregarMarcadores() {
  try {
    marcadores.value = (await api.get('/api/email/marcadores')).marcadores || []
  } catch {
    marcadores.value = []
  }
}

async function carregar() {
  carregando.value = true
  erro.value = ''
  try {
    const q = new URLSearchParams({ marcador: marcadorAtual.value, busca: busca.value })
    mensagens.value = (await api.get(`/api/email/mensagens?${q}`)).mensagens || []
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui ler a caixa.'
  } finally {
    carregando.value = false
  }
}

async function abrir(id) {
  try {
    aberta.value = await api.get(`/api/email/mensagens/${id}`)
    /* Marca lida no Gmail, não só aqui. Falha em silêncio: não conseguir
       marcar não pode impedir a pessoa de LER a mensagem. */
    const naLista = mensagens.value.find((m) => m.id === id)
    if (naLista && !naLista.lida) {
      naLista.lida = true
      api.post(`/api/email/mensagens/${id}/lida`, {}).catch(() => {})
    }
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui abrir.'
  }
}

async function buscarNovos() {
  recado.value = 'buscando no Gmail…'
  try {
    const r = await api.post('/api/email/ler', {})
    recado.value = `${r.novas} nova(s), ${r.repetidas} já tínhamos.`
    await carregar()
  } catch (e) {
    recado.value = ''
    erro.value = e instanceof ErroDeApi ? e.message : 'Falha ao buscar.'
  }
}

function trocar(id) {
  marcadorAtual.value = id
  aberta.value = null
  carregar()
}

function quando(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const hoje = new Date().toDateString() === d.toDateString()
  return hoje
    ? d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
    : d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' })
}

onMounted(async () => {
  await carregarMarcadores()
  await carregar()
  await carregarAssinatura()
})
</script>

<template>
  <div class="tela">
    <header class="tela__cabecalho">
      <div>
        <h1 class="tela__titulo">E-mail</h1>
        <p class="apagado pequeno">
          Por enquanto dá para ler e consultar. Responder pela tela vem em breve.
        </p>
      </div>
      <div class="linha">
        <input v-model="busca" class="campo__entrada" type="search"
               placeholder="Buscar por assunto ou remetente" @keyup.enter="carregar" />
        <button class="botao botao--pequeno botao--contorno" type="button" @click="buscarNovos">
          <i class="bi bi-arrow-clockwise" aria-hidden="true"></i> Atualizar
        </button>
      </div>
    </header>

    <p v-if="erro" class="aviso aviso--erro">{{ erro }}</p>
    <p v-if="recado" class="apagado pequeno">{{ recado }}</p>

    <!-- barra de orientação: onde estou, quantas há, e o que dá para fazer -->
    <div class="email__barra">
      <div class="linha">
        <button class="botao botao--pequeno botao--fantasma" type="button"
                :aria-expanded="menuAberto" title="Mostrar ou esconder as pastas"
                @click="alternarMenu">
          <i class="bi bi-list" aria-hidden="true"></i>
        </button>
        <strong>{{ NOMES[marcadorAtual] || marcadorAtual || 'Todas' }}</strong>
        <span class="apagado pequeno">{{ mensagens.length }} mensagens</span>
      </div>

      <div class="linha email__acoes">
        <button class="botao botao--pequeno botao--acento" type="button" @click="novaMensagem">
          <i class="bi bi-pencil-square" aria-hidden="true"></i> Nova mensagem
        </button>
        <span class="email__separador" aria-hidden="true"></span>
        <button class="botao botao--pequeno botao--fantasma" type="button"
                :disabled="!aberta" @click="responder(false)">
          <i class="bi bi-reply" aria-hidden="true"></i> Responder
        </button>
        <button class="botao botao--pequeno botao--fantasma" type="button"
                :disabled="!aberta" @click="responder(true)">
          <i class="bi bi-arrow-right" aria-hidden="true"></i> Encaminhar
        </button>
        <span class="email__separador" aria-hidden="true"></span>
        <button class="botao botao--pequeno botao--fantasma" type="button"
                title="Sua assinatura, usada nos e-mails que você enviar"
                @click="editandoAssinatura = !editandoAssinatura">
          <i class="bi bi-vector-pen" aria-hidden="true"></i> Assinatura
        </button>
      </div>
    </div>

    <!-- assinatura: HTML colado da que a pessoa já usa -->
    <section v-if="editandoAssinatura" class="cartao email__painel">
      <h2 class="inicio__titulo">Sua assinatura</h2>
      <p class="apagado pequeno">
        Cole aqui o HTML da assinatura que você já usa. ⚠️ A configurada no
        Gmail <strong>não</strong> se aplica ao que sai por esta tela.
      </p>
      <textarea v-model="assinatura" class="campo__entrada email__area" rows="6"
                placeholder="<div>Seu nome<br>Movisat</div>"></textarea>
      <div v-if="assinatura" class="email__previa" v-html="assinatura"></div>
      <div class="linha">
        <button class="botao botao--pequeno botao--acento" type="button" @click="salvarAssinatura">
          Salvar
        </button>
        <button class="botao botao--pequeno botao--fantasma" type="button"
                @click="editandoAssinatura = false">Fechar</button>
      </div>
    </section>

    <!-- escrever: UMA mensagem, nunca lista -->
    <section v-if="escrevendo" class="cartao email__painel">
      <h2 class="inicio__titulo">
        {{ rascunho.responder_a ? 'Responder' : 'Nova mensagem' }}
      </h2>
      <div class="campo email__para">
        <span class="campo__rotulo">Para</span>
        <div class="linha">
          <input v-model="rascunho.para" class="campo__entrada" type="email"
                 placeholder="alguem@empresa.com.br" />
          <button class="email__quadrado" type="button"
                  :class="{ 'email__quadrado--ligado': mostrarCopias }"
                  title="Cópia e cópia oculta"
                  @click="mostrarCopias = !mostrarCopias">Cc</button>
        </div>
      </div>

      <template v-if="mostrarCopias">
        <label class="campo">
          <span class="campo__rotulo">Cc <span class="apagado">— todos veem quem recebeu</span></span>
          <input v-model="rascunho.cc" class="campo__entrada" type="text"
                 placeholder="separe por vírgula" />
        </label>
        <label class="campo">
          <span class="campo__rotulo">Cco <span class="apagado">— ninguém vê quem recebeu</span></span>
          <input v-model="rascunho.cco" class="campo__entrada" type="text"
                 placeholder="separe por vírgula" />
        </label>
      </template>

      <label class="campo">
        <span class="campo__rotulo">Assunto</span>
        <input v-model="rascunho.assunto" class="campo__entrada" type="text" />
      </label>
      <div class="campo">
        <span class="campo__rotulo">Mensagem</span>
        <div class="email__ferramentas">
          <template v-for="(f, i) in FERRAMENTAS" :key="i">
            <span v-if="f.sep" class="email__separador" aria-hidden="true"></span>
            <button v-else class="email__quadrado" type="button" :title="f.t"
                    @mousedown.prevent="formatar(f.c, f.v)">
              <i class="bi" :class="f.i" aria-hidden="true"></i>
            </button>
          </template>
          <select class="email__tamanho" title="Tamanho"
                  @change="formatar('fontSize', $event.target.value)">
            <option value="">Tamanho</option>
            <option value="2">Pequeno</option>
            <option value="3">Normal</option>
            <option value="5">Grande</option>
          </select>
          <button class="email__quadrado" type="button" title="Inserir link"
                  @mousedown.prevent="inserirLink">
            <i class="bi bi-link-45deg" aria-hidden="true"></i>
          </button>
        </div>
        <div ref="editor" class="email__editor" contenteditable="true"
             v-html="rascunho.corpo.replace(/\n/g, '<br>')"></div>
      </div>
      <p class="apagado pequeno">
        Sai de <strong>{{ marcadorAtual ? '' : '' }}sua caixa</strong>, com a sua
        assinatura. Um destinatário por vez.
      </p>
      <div class="linha linha--quebra email__anexos">
        <label class="botao botao--pequeno botao--contorno">
          <i class="bi bi-paperclip" aria-hidden="true"></i>
          {{ subindo ? 'subindo…' : 'Anexar' }}
          <input type="file" multiple hidden @change="anexar" />
        </label>
        <span v-for="a in anexos" :key="a.id" class="chip">
          {{ a.nome }} <span class="apagado">{{ tamanho(a.tamanho) }}</span>
          <button class="email__tirar" type="button" title="Remover"
                  @click="tirarAnexo(a.id)">×</button>
        </span>
      </div>

      <div class="linha">
        <button class="botao botao--acento" type="button" :disabled="enviando" @click="mandar">
          <i class="bi bi-send" aria-hidden="true"></i>
          {{ enviando ? 'enviando…' : 'Enviar' }}
        </button>
        <button class="botao botao--fantasma" type="button" @click="escrevendo = false">
          Cancelar
        </button>
      </div>
    </section>

    <div class="email" :class="{ 'email--sem-menu': !menuAberto }">
      <!-- marcadores: a navegação, como no Gmail -->
      <nav v-show="menuAberto" class="cartao email__lado">
        <button
          v-for="m in visiveis"
          :key="m.id"
          class="email__marcador"
          :class="{ 'email__marcador--ativo': marcadorAtual === m.id_externo }"
          type="button"
          @click="trocar(m.id_externo)"
        >
          <span>{{ rotulo(m) }}</span>
          <span v-if="m.quantidade" class="apagado pequeno">{{ m.quantidade }}</span>
        </button>
        <p v-if="!visiveis.length" class="apagado pequeno">
          Clique em <strong>Atualizar</strong> para trazer suas pastas.
        </p>
      </nav>

      <!-- lista -->
      <div class="cartao email__lista">
        <p v-if="carregando" class="apagado pequeno">carregando…</p>
        <div v-else-if="!mensagens.length" class="email__vazio">
          <i class="bi bi-inbox" aria-hidden="true"></i>
          <p>Nenhuma mensagem por aqui.</p>
          <p class="apagado pequeno">Clique em <strong>Atualizar</strong> para buscar as novas.</p>
        </div>
        <button
          v-for="m in mensagens"
          :key="m.id"
          class="email__item"
          :class="{ 'email__item--aberta': aberta && aberta.id === m.id,
                    'email__item--nova': !m.lida }"
          type="button"
          @click="abrir(m.id)"
        >
          <span class="email__inicial" :style="{ background: corDaInicial(m) }" aria-hidden="true">
            {{ iniciais(m) }}
          </span>
          <span class="email__de">{{ m.remetente_nome || m.remetente }}</span>
          <span class="email__assunto">{{ m.assunto || '(sem assunto)' }}</span>
          <span v-if="m.cliente_nome" class="chip email__cliente">{{ m.cliente_nome }}</span>
          <i v-if="m.tem_anexo" class="bi bi-paperclip apagado" aria-hidden="true"></i>
          <span class="apagado pequeno email__quando">{{ quando(m.enviado_em) }}</span>
        </button>
      </div>

      <!-- leitura -->
      <div class="cartao email__leitura">
        <div v-if="!aberta" class="email__vazio">
          <i class="bi bi-envelope-open" aria-hidden="true"></i>
          <p>Escolha uma mensagem para ler</p>
        </div>
        <template v-else>
          <h2 class="email__titulo">{{ aberta.assunto || '(sem assunto)' }}</h2>
          <p class="apagado pequeno mono">
            {{ aberta.remetente }} · {{ new Date(aberta.enviado_em).toLocaleString('pt-BR') }}
          </p>

          <!-- a mesma faixa da ficha do WhatsApp: quem é, ou como vincular -->
          <p v-if="aberta.cliente_nome" class="chip chip--acento">
            <i class="bi bi-building" aria-hidden="true"></i> {{ aberta.cliente_nome }}
          </p>
          <div v-if="aberta.bitrix" class="gaveta__bitrix">
            <strong class="pequeno">Aparece no Bitrix</strong>
            <span v-if="aberta.bitrix.nome">{{ aberta.bitrix.nome }}</span>
            <span v-if="aberta.bitrix.empresa" class="apagado pequeno">{{ aberta.bitrix.empresa }}</span>
            <span v-if="aberta.bitrix.tipo" class="chip">{{ aberta.bitrix.tipo }}</span>
            <span class="apagado pequeno">Sistema antigo — <strong>não é vínculo</strong>.</span>
          </div>

          <div v-if="!aberta.cliente_nome" class="email__vincular">
            <p class="apagado pequeno">
              Este remetente ainda não está ligado a nenhum cliente.
              Vincule e <strong>todas</strong> as mensagens dele passam a ser
              identificadas.
            </p>
            <input v-model="buscaEmpresa" class="campo__entrada" type="search"
                   placeholder="Buscar empresa por nome ou CNPJ"
                   @input="procurarEmpresa" />
            <ul v-if="achados.length" class="gaveta__lista">
              <li v-for="c in achados" :key="c.id">
                <button class="botao botao--pequeno botao--contorno gaveta__achado"
                        type="button" @click="vincular(c.id)">
                  <span>{{ c.nome }}</span>
                  <span class="apagado pequeno mono">{{ c.documento }}</span>
                </button>
              </li>
            </ul>
          </div>

          <div v-if="aberta.anexos && aberta.anexos.length" class="linha pequeno">
            <span v-for="a in aberta.anexos" :key="a.nome" class="chip">
              <i class="bi bi-paperclip" aria-hidden="true"></i> {{ a.nome }}
            </span>
          </div>

          <pre class="email__corpo">{{ aberta.texto || '(sem texto legível)' }}</pre>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* A barra fica GRUDADA acima das colunas, com respiro embaixo: sem a margem
   o botão de recolher parecia flutuando solto sobre a lista. */
.email__barra {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--e-2);
  padding: var(--e-2) var(--e-3);
  margin-bottom: var(--e-3);
  background: var(--superficie);
  border: var(--borda-fina) solid var(--borda);
  border-radius: var(--r-lg);
  box-shadow: var(--sombra-1);
}
.email__acoes { flex-wrap: wrap; gap: var(--e-1); }
.email__separador {
  width: 1px; height: 20px;
  background: var(--borda);
  margin: 0 var(--e-1);
}
/* Desabilitado tem que PARECER desabilitado, senão vira clique frustrado. */
.email__acoes .botao:disabled { opacity: .45; cursor: not-allowed; }

/* 🚨 AS TRES AREAS DIVIDEM A MESMA ALTURA e rolam por dentro. Antes cada
   cartao terminava onde o conteudo dele acabava, e o desalinhamento aparecia
   de cara -- lista curta ao lado de leitura longa. */
.email {
  display: grid;
  grid-template-columns: 190px minmax(280px, 360px) 1fr;
  gap: var(--e-3);
  align-items: stretch;
  height: calc(100vh - 250px);   /* desconta cabeçalho + barra de ações */
  min-height: 420px;
}
.email--sem-menu { grid-template-columns: minmax(280px, 360px) 1fr; }

/* Abaixo de 1100px o painel ja tem o menu lateral dele: dois menus lado a
   lado espremem a leitura. A lista some e fica só o que se está lendo. */
@media (max-width: 1100px) {
  .email { grid-template-columns: minmax(260px, 320px) 1fr; }
  .email__lado { display: none; }
}
@media (max-width: 760px) {
  .email { grid-template-columns: 1fr; height: auto; }
  .email__lista, .email__leitura { max-height: 60vh; }
}

.email__lado { padding: var(--e-2); display: flex; flex-direction: column; gap: 2px; }

.email__inicial {
  width: 26px; height: 26px; flex: none;
  display: grid; place-items: center;
  border-radius: var(--r-full);
  color: #fff; font-size: var(--txt-sm); font-weight: 600;
}
.email__de {
  width: 150px; flex: none;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.email__assunto {
  flex: 1; min-width: 0;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  color: var(--texto-fraco);
}
.email__cliente { flex: none; max-width: 130px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.email__quando { flex: none; width: 46px; text-align: right; font-variant-numeric: tabular-nums; }

/* Não lida em negrito e com barra: é o que a pessoa procura ao abrir. */
.email__item--nova { border-left: 3px solid var(--acento); }
.email__item--nova .email__de { font-weight: 700; }

/* Botão quadrado: ocupa o mínimo. Espaço de tela é caro, e formatação é
   coisa que se reconhece pelo ícone, não pelo rótulo. */
.email__quadrado {
  width: 30px; height: 30px; flex: none;
  display: grid; place-items: center;
  border: var(--borda-fina) solid var(--borda);
  border-radius: var(--r-sm);
  background: var(--superficie);
  color: var(--texto-fraco);
  cursor: pointer;
  font-size: var(--txt-sm);
  font-family: var(--fonte);
}
.email__quadrado:hover { background: var(--superficie-2); color: var(--texto); }
.email__quadrado--ligado { background: var(--acento-suave); color: var(--acento); border-color: var(--acento-borda); }

.email__ferramentas {
  display: flex; flex-wrap: wrap; align-items: center; gap: 2px;
  padding: var(--e-1);
  border: var(--borda-fina) solid var(--borda);
  border-bottom: none;
  border-radius: var(--r-sm) var(--r-sm) 0 0;
  background: var(--superficie-2);
}
.email__tamanho {
  height: 30px; border: var(--borda-fina) solid var(--borda);
  border-radius: var(--r-sm); background: var(--superficie);
  font-size: var(--txt-sm); font-family: var(--fonte); color: var(--texto-fraco);
}

.email__editor {
  min-height: 190px; max-height: 40vh; overflow-y: auto;
  padding: var(--e-3);
  border: var(--borda-fina) solid var(--borda);
  border-radius: 0 0 var(--r-sm) var(--r-sm);
  background: var(--superficie);
  font-size: var(--txt-md);
  line-height: 1.55;
}
.email__editor:focus { outline: none; box-shadow: var(--foco); }
.email__editor blockquote {
  margin: 0 0 0 var(--e-2); padding-left: var(--e-2);
  border-left: 3px solid var(--borda-forte); color: var(--texto-fraco);
}
.email__para .linha { gap: var(--e-1); }
.email__para .campo__entrada { flex: 1; }

.email__anexos { gap: var(--e-2); align-items: center; }
.email__tirar {
  border: none; background: transparent; cursor: pointer;
  color: var(--texto-fraco); font-size: var(--txt-md); line-height: 1;
  padding: 0 0 0 4px;
}
.email__tirar:hover { color: var(--erro); }

.email__painel { padding: var(--e-4); margin-bottom: var(--e-3); display: flex; flex-direction: column; gap: var(--e-2); }
.email__area { font-family: var(--fonte-mono); font-size: var(--txt-sm); resize: vertical; }
.email__previa {
  border: var(--borda-fina) dashed var(--borda-forte);
  border-radius: var(--r-sm);
  padding: var(--e-2);
  background: var(--superficie-2);
}
.gaveta__bitrix {
  display: flex; flex-direction: column; gap: 2px;
  padding: var(--e-2); margin: var(--e-2) 0;
  border-left: 3px solid var(--aviso);
  background: var(--aviso-suave);
  border-radius: var(--r-sm);
}
.email__vincular { display: flex; flex-direction: column; gap: var(--e-2); margin: var(--e-2) 0; }
.gaveta__lista { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--e-1); max-height: 200px; overflow-y: auto; }
.gaveta__achado { width: 100%; display: flex; justify-content: space-between; gap: var(--e-2); text-align: left; }

.email__vazio {
  display: flex; flex-direction: column; align-items: center; gap: var(--e-1);
  padding: var(--e-6) var(--e-3); text-align: center; color: var(--texto-apagado);
}
.email__vazio i { font-size: 30px; opacity: .5; }
.email__vazio p { margin: 0; }
.email__marcador {
  display: flex;
  justify-content: space-between;
  gap: var(--e-2);
  padding: var(--e-2);
  border: none;
  background: transparent;
  border-radius: var(--r-sm);
  cursor: pointer;
  text-align: left;
  font-family: var(--fonte);
  font-size: var(--txt-sm);
  color: var(--texto);
}
.email__marcador:hover { background: var(--superficie-2); }
.email__marcador--ativo { background: var(--acento-suave); color: var(--acento); font-weight: 600; }

.email__lista {
  padding: var(--e-2);
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-height: 0;   /* sem isto o filho de grid não encolhe e a rolagem não nasce */
}
/* Uma linha, como no Gmail: mostra o dobro de mensagens na mesma altura. */
.email__item {
  display: flex;
  align-items: center;
  gap: var(--e-2);
  min-width: 0;
  padding: var(--e-2);
  border: none;
  border-bottom: var(--borda-fina) solid var(--borda);
  background: transparent;
  cursor: pointer;
  text-align: left;
  font-family: var(--fonte);
}
.email__item:hover { background: var(--superficie-2); }
.email__item--aberta { background: var(--acento-suave); }
.email__assunto { font-size: var(--txt-sm); color: var(--texto-fraco); overflow-wrap: anywhere; }

.email__leitura { padding: var(--e-4); overflow-y: auto; min-height: 0; }
.email__lado { overflow-y: auto; min-height: 0; }
.email__titulo { font-size: var(--txt-lg); margin: 0 0 var(--e-1); }
/* Largura de leitura confortável. Texto esticado até a borda de uma tela
   larga cansa: o olho perde a linha na volta. */
.email__corpo {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  font-family: var(--fonte);
  font-size: var(--txt-md);
  line-height: 1.55;
  max-width: 65ch;
  margin-top: var(--e-3);
}
</style>
