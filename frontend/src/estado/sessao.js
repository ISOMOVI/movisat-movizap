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
import { reactive, computed } from 'vue'
import { api, definirToken, temToken, quandoPerderSessao } from '../api/cliente.js'

const CHAVE_INICIO = 'movizap.sessao_iniciada_em'

export const sessao = reactive({
  /** null enquanto não sabemos; objeto depois de /api/sessao/eu */
  usuario: null,
  /** [{codigo, titulo, rota, icone}] — exatamente como veio do backend */
  telas: [],
  /** epoch ms do início da sessão, para a duração na barra de status */
  iniciadaEm: Number(localStorage.getItem(CHAVE_INICIO)) || 0,
  /** true enquanto a restauração de sessão do arranque não terminou */
  carregando: false,
})

export const autenticado = computed(() => Boolean(sessao.usuario))

/** O conjunto de códigos que este usuário enxerga. */
export const codigosPermitidos = computed(
  () => new Set(sessao.telas.map((t) => t.codigo)),
)

function limpar() {
  sessao.usuario = null
  sessao.telas = []
  sessao.iniciadaEm = 0
  localStorage.removeItem(CHAVE_INICIO)
  definirToken('')
}

export async function entrar(login, senha) {
  const r = await api.post('/api/sessao/login', { login, senha })
  definirToken(r.token)
  sessao.iniciadaEm = Date.now()
  localStorage.setItem(CHAVE_INICIO, String(sessao.iniciadaEm))
  await carregarEu()
  return r
}

export function sair() {
  limpar()
}

/** Busca quem sou e o que enxergo. Fonte única do menu. */
export async function carregarEu() {
  const eu = await api.get('/api/sessao/eu')
  sessao.usuario = { login: eu.login, nome: eu.nome, owner: eu.owner }
  sessao.telas = eu.telas || []
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
quandoPerderSessao(limpar)
