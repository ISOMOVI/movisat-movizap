/* ============================================================================
   Cliente HTTP do MoviZap — o ÚNICO lugar que fala com o backend.
   ----------------------------------------------------------------------------
   Concentra aqui porque três coisas precisam valer para toda requisição, sem
   exceção e sem depender de disciplina:

     1. o token vai no Authorization;
     2. o X-Request-Id da resposta alimenta a barra de status — quando algo dá
        errado, o que se procura no journal é `req=a3f9`, não a tela;
     3. 401 encerra a sessão em UM lugar. Espalhar isso pelas telas é como se
        perde sessão expirada virando tela em branco.
   ============================================================================ */
import { reactive } from 'vue'

const CHAVE_TOKEN = 'movizap.token'

/** Estado que a barra de status observa. Só o cliente escreve aqui. */
export const rede = reactive({
  /** id da última requisição — é o `req a3f9` da barra */
  ultimoReqId: '',
  /** requisições em voo; > 0 mostra o indicador de carregando */
  emVoo: 0,
})

let token = localStorage.getItem(CHAVE_TOKEN) || ''
let aoPerderSessao = () => {}

/** O estado de sessão registra aqui o que fazer quando o backend disser 401. */
export function quandoPerderSessao(fn) {
  aoPerderSessao = fn
}

export function definirToken(novo) {
  token = novo || ''
  if (token) localStorage.setItem(CHAVE_TOKEN, token)
  else localStorage.removeItem(CHAVE_TOKEN)
}

export function temToken() {
  return Boolean(token)
}

/** Erro de API: carrega o status e o req_id para a tela poder mostrá-los. */
export class ErroDeApi extends Error {
  constructor(mensagem, status, reqId) {
    super(mensagem)
    this.name = 'ErroDeApi'
    this.status = status
    this.reqId = reqId
  }
}

async function pedir(metodo, caminho, corpo) {
  const cabecalhos = { Accept: 'application/json' }
  if (token) cabecalhos.Authorization = `Bearer ${token}`
  if (corpo !== undefined) cabecalhos['Content-Type'] = 'application/json'

  rede.emVoo += 1
  let resposta
  try {
    resposta = await fetch(caminho, {
      method: metodo,
      headers: cabecalhos,
      body: corpo === undefined ? undefined : JSON.stringify(corpo),
    })
  } catch (e) {
    // rede caiu, backend fora do ar, DNS. Não há req_id: a requisição não chegou.
    rede.emVoo -= 1
    throw new ErroDeApi('Sem resposta do servidor. Verifique a conexão.', 0, '')
  }
  rede.emVoo -= 1

  const reqId = resposta.headers.get('X-Request-Id') || ''
  if (reqId) rede.ultimoReqId = reqId

  // 🚨 Não confiar no código de retorno: o corpo é que diz o que houve.
  // Ler antes de decidir, e nunca supor que veio JSON.
  const texto = await resposta.text()
  let dados = null
  if (texto) {
    try {
      dados = JSON.parse(texto)
    } catch {
      dados = null
    }
  }

  if (resposta.ok) {
    if (dados === null && texto) {
      // 200 com corpo que não é JSON = quase sempre o index.html da SPA
      // devolvido para uma rota de API que não existe.
      throw new ErroDeApi(`Resposta não-JSON em ${caminho}.`, resposta.status, reqId)
    }
    return dados
  }

  if (resposta.status === 401) {
    definirToken('')
    aoPerderSessao()
  }

  const detalhe = dados && dados.detail ? dados.detail : `Erro ${resposta.status}.`
  throw new ErroDeApi(
    typeof detalhe === 'string' ? detalhe : `Erro ${resposta.status}.`,
    resposta.status,
    reqId,
  )
}

export const api = {
  get: (caminho) => pedir('GET', caminho),
  post: (caminho, corpo) => pedir('POST', caminho, corpo ?? {}),
  put: (caminho, corpo) => pedir('PUT', caminho, corpo ?? {}),
  del: (caminho) => pedir('DELETE', caminho),
}
