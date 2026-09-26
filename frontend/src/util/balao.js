/* ============================================================================
   O balão do Windows — o aviso "igual do MSN" (25/09)
   ----------------------------------------------------------------------------
   🔵 Pergunta dele: *"como ficou a notificação? igual do MSN?"* -- e depois
   *"é possível fazer via browser? considere UX/UI"*. É a Notification API do
   navegador: aparece no canto da tela com o navegador minimizado e não depende
   do clique que o som exige depois do F5. Conteúdo: 🔵 *"Nome + trecho"*.

   🟡 Desenho:
     · só com o painel FORA DE FOCO -- com ele à vista, o número e o som bastam;
     · `tag` por conversa: mensagem nova da mesma conversa SUBSTITUI o balão em
       vez de empilhar, e duas abas abertas não mostram dois;
     · a permissão se pede EM CONTEXTO (convite do Notificador ou botão da
       CFG_11.1), nunca ao abrir o painel. Recusada, o navegador não pergunta
       de novo -- e a tela ensina onde religar.

   ⚠️ LIMITES QUE A TELA EXPLICA: só funciona com uma aba do MoviZap aberta
   (avisar com o navegador fechado exigiria push com service worker), e o
   "Não perturbe" do Windows cala o balão.
   ============================================================================ */

export const ICONE = '/movisat-logo.png'
const CHAVE_ADIADO = 'movizap.balao.adiado_ate'
const SETE_DIAS_MS = 7 * 24 * 60 * 60 * 1000

export function disponivel() {
  return typeof window !== 'undefined' && 'Notification' in window
}

/** 'granted' | 'denied' | 'default' | 'indisponivel' */
export function permissao() {
  return disponivel() ? window.Notification.permission : 'indisponivel'
}

export async function pedirPermissao() {
  if (!disponivel()) return 'indisponivel'
  try {
    return await window.Notification.requestPermission()
  } catch {
    return window.Notification.permission
  }
}

/** O painel não está diante da pessoa: aba escondida ou janela sem foco. */
export function foraDeFoco() {
  return document.hidden || !document.hasFocus()
}

/**
 * @param {{id:number, nome:string, trecho?:string}} conversa
 * @param {(id:number) => void} aoClicar
 */
export function mostrarBalao(conversa, aoClicar) {
  if (permissao() !== 'granted') return null
  try {
    const n = new window.Notification(`Nova mensagem · ${conversa.nome}`, {
      body: conversa.trecho || '',
      tag: `conversa-${conversa.id}`,
      renotify: true,
      icon: ICONE,
    })
    n.onclick = () => {
      window.focus()
      aoClicar(conversa.id)
      n.close()
    }
    return n
  } catch {
    return null // navegador que exige service worker para notificar: fica o som
  }
}

/* "Agora não" no convite: some por 7 dias. localStorage pode falhar (aba
   privada, bloqueio); aí o convite volta a aparecer, e é só isso. */
export function conviteAdiado(agora = Date.now()) {
  try {
    return Number(localStorage.getItem(CHAVE_ADIADO) || 0) > agora
  } catch {
    return false
  }
}

export function adiarConvite(agora = Date.now()) {
  try {
    localStorage.setItem(CHAVE_ADIADO, String(agora + SETE_DIAS_MS))
  } catch { /* sem armazenamento: o convite volta na próxima abertura */ }
}
