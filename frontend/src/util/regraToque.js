/* ============================================================================
   Quando a notificação TOCA — a regra dele, em função pura (24/09)
   ----------------------------------------------------------------------------
   🔵 *"Notificações somente de conversas assumidas, ou quando tiver no máximo
   4 notificações só. Então se a pessoa como ela tiver 20 conversas, só vai
   tocar 4 vezes. Se tiver 2, vai tocar 2, quando chegar mensagem"* -- e, ao
   confirmar o teto: *"ou entrar uma nova, dai toca uma vez só e para, assim
   não some a atenção"*.

   Lida assim:
     1. Só conversa em que sou o DONO.
     2. Toca quando uma conversa minha passa de LIDA para COM NÃO LIDA. Mensagem
        nova numa conversa que já estava não lida não toca de novo.
     3. Enquanto eu tiver até 4 conversas não lidas, cada uma que vira não lida
        toca. Da 5ª em diante, fica só o número...
     4. ...exceto conversa NOVA para mim (acabou de chegar -- transferida,
        distribuída, assumida), que toca UMA vez mesmo acima do teto.
     5. A primeira leitura depois de abrir o painel NUNCA toca: sem ela, todo
        F5 tocaria até 4 vezes.

   Função pura de propósito: é a parte que decide, e tem de ser testada sem
   navegador, sem som e sem servidor.
   ============================================================================ */

export const TETO = 4

/**
 * @param {null | {donas: number[], assumidas: {id:number, nao_lidas:number}[]}} antes
 * @param {{donas: number[], assumidas: {id:number, nao_lidas:number}[]}} depois
 * @returns {{tocar: boolean, motivo: string}}
 */
export function decidirToque(antes, depois) {
  if (!antes) return { tocar: false, motivo: 'primeira leitura' }

  const eraNaoLida = new Set((antes.assumidas || []).filter((c) => c.nao_lidas > 0).map((c) => c.id))
  const eraMinha = new Set(antes.donas || [])
  const agora = (depois.assumidas || []).filter((c) => c.nao_lidas > 0)

  const viraramNaoLidas = agora.filter((c) => !eraNaoLida.has(c.id))
  if (!viraramNaoLidas.length) return { tocar: false, motivo: 'nada novo' }

  if (agora.length <= TETO) return { tocar: true, motivo: 'até o teto' }

  const novasParaMim = viraramNaoLidas.filter((c) => !eraMinha.has(c.id))
  if (novasParaMim.length) return { tocar: true, motivo: 'conversa nova acima do teto' }
  return { tocar: false, motivo: 'acima do teto' }
}
