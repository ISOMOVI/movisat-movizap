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
const SO_LEITURA = 'Ainda não disponível: a caixa está conectada só para leitura.'

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
        <button class="botao botao--pequeno botao--acento" type="button"
                :title="SO_LEITURA" disabled>
          <i class="bi bi-pencil-square" aria-hidden="true"></i> Nova mensagem
        </button>
        <span class="email__separador" aria-hidden="true"></span>
        <button class="botao botao--pequeno botao--fantasma" type="button"
                :title="SO_LEITURA" :disabled="true">
          <i class="bi bi-reply" aria-hidden="true"></i> Responder
        </button>
        <button class="botao botao--pequeno botao--fantasma" type="button"
                :title="SO_LEITURA" :disabled="true">
          <i class="bi bi-arrow-right" aria-hidden="true"></i> Encaminhar
        </button>
        <button class="botao botao--pequeno botao--fantasma" type="button"
                :title="SO_LEITURA" :disabled="true">
          <i class="bi bi-folder-symlink" aria-hidden="true"></i> Mover
        </button>
        <button class="botao botao--pequeno botao--fantasma" type="button"
                :title="SO_LEITURA" :disabled="true">
          <i class="bi bi-trash" aria-hidden="true"></i> Excluir
        </button>
      </div>
    </div>

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
          <p v-else class="apagado pequeno">
            Este remetente ainda não está ligado a nenhum cliente.
          </p>

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
