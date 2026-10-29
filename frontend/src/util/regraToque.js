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

   6. 🔵 25/09 (*"Só marca lida vista"*): a conversa que está ABERTA E À
      VISTA não toca -- a pessoa já está olhando para ela. Ela continua
      contando para o teto.

   Função pura de propósito: é a parte que decide, e tem de ser testada sem
   navegador, sem som e sem servidor. Devolve também QUAIS conversas fizeram
   tocar (`conversas`): é para elas que sai o balão do Windows.
   ============================================================================ */

export const TETO = 4

/**
 * @param {null | {donas: number[], assumidas: {id:number, nao_lidas:number}[]}} antes
 * @param {{donas: number[], assumidas: {id:number, nao_lidas:number}[]}} depois
 * @param {number|null} aVista  a conversa aberta com a tela à vista, se houver
 * @returns {{tocar: boolean, motivo: string, conversas: number[]}}
 */
export function decidirToque(antes, depois, aVista = null) {
  if (!antes) return { tocar: false, motivo: 'primeira leitura', conversas: [] }

  const eraNaoLida = new Set((antes.assumidas || []).filter((c) => c.nao_lidas > 0).map((c) => c.id))
  const eraMinha = new Set(antes.donas || [])
  const agora = (depois.assumidas || []).filter((c) => c.nao_lidas > 0)

  const viraramNaoLidas = agora.filter((c) => !eraNaoLida.has(c.id) && c.id !== aVista)
  if (!viraramNaoLidas.length) return { tocar: false, motivo: 'nada novo', conversas: [] }

  if (agora.length <= TETO) {
    return { tocar: true, motivo: 'até o teto', conversas: viraramNaoLidas.map((c) => c.id) }
  }

  const novasParaMim = viraramNaoLidas.filter((c) => !eraMinha.has(c.id))
  if (novasParaMim.length) {
    return { tocar: true, motivo: 'conversa nova acima do teto', conversas: novasParaMim.map((c) => c.id) }
  }
  return { tocar: false, motivo: 'acima do teto', conversas: [] }
}

/* ============================================================================
   Quando a NOTA INTERNA toca (28/10)
   ----------------------------------------------------------------------------
   🔵 Pedido dele: *"verifique se as notas internas tbm estao gerando
   notificacoes como mensagens novas"* -> não geravam. Isto é a régua nova.

   🚨 FUNÇÃO SEPARADA, e não um ramo dentro do `decidirToque`. Os dois eventos
   são diferentes para quem recebe: um é o CLIENTE esperando resposta, o outro é
   um COLEGA deixando recado. Misturar na mesma função faria o teto de 4 do
   cliente ser gasto por nota de bastidor -- e o teto existe para *"não sumir a
   atenção"* do cliente.

   A régua, no molde da dele:
     1. Toca quando uma conversa passa a ter nota nova PARA MIM. Nota a mais
        numa conversa que já tinha nota nova não toca de novo.
     2. Teto de 4 conversas, igual ao da mensagem -- contado só entre notas.
     3. A conversa ABERTA E À VISTA não toca: a pessoa está olhando, e o
        "visto por" vai carimbar sozinho.
     4. A primeira leitura depois de abrir o painel nunca toca (senão todo F5
        tocaria).
   ⚠️ NÃO há a exceção de "conversa nova acima do teto": aquela existe porque
   conversa nova é cliente novo esperando. Nota não cria fila.
   ============================================================================ */
export function decidirToqueNota(antes, depois, aVista = null) {
  if (!antes) return { tocar: false, motivo: 'primeira leitura', notas: [] }

  const tinha = new Set((antes.notas || []).map((x) => x.conversa_id))
  const agora = (depois.notas || [])
  const novas = agora.filter((x) => !tinha.has(x.conversa_id) && x.conversa_id !== aVista)
  if (!novas.length) return { tocar: false, motivo: 'nada novo', notas: [] }
  if (agora.length > TETO) return { tocar: false, motivo: 'acima do teto', notas: [] }
  return { tocar: true, motivo: 'nota nova', notas: novas }
}
