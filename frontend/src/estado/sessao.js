/* ============================================================================
   Estado da sessão.
   ----------------------------------------------------------------------------
   Um objeto `reactive` exportado, sem biblioteca de store. É proposital: o
   projeto é lido e mantido por quem escreve Python, e `defineStore` +
   `storeToRefs` é um vocabulário a mais para resolver o que 40 linhas
   resolvem. Quando o estado da caixa de entrada chegar (conversas ao vivo,
   websocket), a decisão se reavalia.

   ⚠️ NENHUMA REGRA DE PERMISSÃO MORA AQUI. `telas` é o que o backend
   devolveu em /api/telas — o frontend desenha, não decide. Guardar aqui a
   lista serve para desenhar menu e negar navegação cedo; a barreira de
   verdade é a rota do backend, que checa de novo em toda requisição.
   ============================================================================ */
import { reactive, computed, ref } from 'vue'
import { api, definirToken, temToken, quandoPerderSessao } from '../api/cliente.js'

const CHAVE_INICIO = 'movizap.sessao_iniciada_em'

export const sessao = reactive({
  /** null enquanto não sabemos; objeto depois de /api/sessao/eu */
  usuario: null,
  /** [{codigo, titulo, rota, icone}] — exatamente como veio do backend */
  telas: [],
  /** epoch ms do início da sessão, para a duração na barra de status */
  iniciadaEm: Number(localStorage.getItem(CHAVE_INICIO)) || 0,
  /* 🔵 15/10 — A SESSÃO É DO DIA. ISO da hora em que este token morre, dito
     pelo backend (que é quem decide), nunca calculado aqui: duas contas da
     mesma regra divergem no primeiro feriado de fuso. */
  expiraEm: '',
  /** true enquanto a restauração de sessão do arranque não terminou */
  carregando: false,
})

export const autenticado = computed(() => Boolean(sessao.usuario))

/* 🚨 POR QUE A PESSOA FOI PARAR NO LOGIN. Até hoje o 401 limpava a sessão e
   NÃO navegava: quem ficasse com a tela aberta na virada do dia continuava
   olhando uma Caixa de entrada sem casca, que não respondia mais nada, até
   tentar navegar. Era defeito já existente, e com um login por dia ele
   passaria a aparecer TODA madrugada. */
export const motivoDaSaida = ref('')

/** O conjunto de códigos que este usuário enxerga. */
export const codigosPermitidos = computed(
  () => new Set(sessao.telas.map((t) => t.codigo)),
)

function limpar() {
  sessao.usuario = null
  sessao.telas = []
  sessao.iniciadaEm = 0
  sessao.expiraEm = ''
  localStorage.removeItem(CHAVE_INICIO)
  apagarRascunhos()
  definirToken('')
}

/* 🔵 15/10, decisão dele: *"o login vale até a virada do dia; o rascunho
   morre com ele"*. É aqui que isso acontece de fato -- este `limpar()` roda
   no logout E na queda de sessão, então dentro do dia o rascunho fica e na
   virada ele vai embora junto.

   ⚠️ Em try/catch e varrendo as chaves ao contrário: remover dentro de um
   laço crescente pula item, porque o índice do `localStorage` reindexa. */
const PREFIXO_RASCUNHO = 'movizap.rascunho.'

function apagarRascunhos() {
  try {
    for (let i = localStorage.length - 1; i >= 0; i--) {
      const chave = localStorage.key(i)
      if (chave && chave.startsWith(PREFIXO_RASCUNHO)) localStorage.removeItem(chave)
    }
  } catch { /* sem storage: não havia rascunho para apagar */ }
}

export async function entrar(login, senha) {
  const r = await api.post('/api/sessao/login', { login, senha })
  definirToken(r.token)
  motivoDaSaida.value = ''
  sessao.expiraEm = r.expira_em || ''
  sessao.iniciadaEm = Date.now()
  localStorage.setItem(CHAVE_INICIO, String(sessao.iniciadaEm))
  await carregarEu()
  return r
}

export function sair() {
  // Sair por vontade própria não precisa de explicação na tela de login.
  motivoDaSaida.value = ''
  limpar()
}

/** Busca quem sou e o que enxergo. Fonte única do menu. */
export async function carregarEu() {
  const eu = await api.get('/api/sessao/eu')
  /* 🚨 ENTRAR NO PAINEL E PODER ATENDER SÃO COISAS DIFERENTES. `vinculo_atendimento`
     é false quando a conta não tem linha em `atendente` com e-mail — e sem
     vínculo tudo que a pessoa escrever é gravado com autor NULL. Até 12/08
     isso acontecia calado; agora a INI_1.1 diz o que houve. */
  sessao.usuario = {
    login: eu.login,
    nome: eu.nome,
    owner: eu.owner,
    email: eu.email || null,
    vinculoAtendimento: eu.vinculo_atendimento !== false,
  }
  sessao.telas = eu.telas || []
  /* Vem daqui também, e não só da resposta do login: um F5 não refaz o
     login, e quem entra pelo Google nem passa pela rota de senha. */
  sessao.expiraEm = eu.sessao_expira_em || ''
  return eu
}

/**
 * Chamado uma vez no arranque. Se há token guardado, tenta usá-lo.
 * Token vencido cai em 401 -> `quandoPerderSessao` já limpou tudo.
 */
export async function restaurar() {
  if (!temToken()) return false
  sessao.carregando = true
  try {
    await carregarEu()
    // Token válido mas sem marca de início (localStorage limpo pela metade):
    // conta a partir de agora em vez de mostrar duração absurda.
    if (!sessao.iniciadaEm) {
      sessao.iniciadaEm = Date.now()
      localStorage.setItem(CHAVE_INICIO, String(sessao.iniciadaEm))
    }
    return true
  } catch {
    limpar()
    return false
  } finally {
    sessao.carregando = false
  }
}

// 401 em qualquer requisição derruba a sessão aqui, num lugar só.
quandoPerderSessao(() => {
  // A frase é do fim do DIA porque é esse o fim normal agora. Um 401 por
  // outro motivo (chave rotacionada, conta desativada) cai na mesma tela, e
  // "entre de novo" continua sendo a ação certa.
  motivoDaSaida.value = 'Sua sessão do dia terminou. Entre de novo.'
  limpar()
})
