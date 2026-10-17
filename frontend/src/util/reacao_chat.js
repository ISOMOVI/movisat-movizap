/* Reação no Chat interno (16/10, "como do externo").

   🚨 MORA AQUI, E NÃO DENTRO DO `ChatInterno.vue`, pela lição do
   `util/mencao.js` (23/09): teste que testa uma CÓPIA da função fica verde
   defendendo código que ninguém usa. A tela e o teste importam a MESMA. */

/**
 * O eco otimista: a lista como fica DEPOIS do meu clique, antes da resposta.
 *
 * Clicar no emoji que já é o meu TIRA (é o gesto do WhatsApp e da Caixa);
 * clicar noutro TROCA. ⚠️ Mexe só na MINHA parte: tirar a linha inteira
 * apagaria da tela a reação de um colega, que não mudou.
 *
 * @param {{emoji: string, n: number, minha: boolean, nomes: string[]}[]} reacoes
 * @param {string|null} minha  o emoji que eu tinha posto
 * @param {string} emoji       o emoji clicado
 * @returns {{reacoes: object[], novo: string}}  `novo` vazio = tirei
 */
export function reagirOtimista(reacoes, minha, emoji) {
  const novo = minha === emoji ? '' : emoji
  const lista = (reacoes || [])
    .map((r) => (r.minha
      ? { ...r, n: r.n - 1, minha: false, nomes: r.nomes.filter((x) => x !== 'você') }
      : { ...r }))
    .filter((r) => r.n > 0)
  if (novo) {
    const igual = lista.find((r) => r.emoji === novo)
    if (igual) {
      igual.n += 1
      igual.minha = true
      igual.nomes = [...(igual.nomes || []), 'você']
    } else {
      lista.push({ emoji: novo, n: 1, minha: true, nomes: ['você'] })
    }
  }
  return { reacoes: lista, novo }
}

/**
 * Quantos acertos da busca estão ANTES do que a tela carregou.
 *
 * 🚨 A sala carrega as 500 mais recentes e não pagina; o servidor acha em
 * tudo. Sem esta conta, o "3/7" levaria a um balão que não está na tela e
 * o clique não faria nada -- a tela diria que achou sem mostrar.
 */
export function acertosForaDaTela(achados, mensagens) {
  const carregadas = new Set((mensagens || []).map((m) => m.id))
  return (achados || []).filter((id) => !carregadas.has(id)).length
}
