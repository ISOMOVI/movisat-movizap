/* O estado de um atendente, como bolinha e rótulo -- 23/09.

   🚨 MORA AQUI PARA HAVER UMA RÉGUA SÓ. Nasceu dentro do `ChatInterno.vue`;
   em 23/09 a Caixa de entrada passou a mostrar o estado do DONO da conversa
   (*"deveria, proponha"*, sobre a conversa não mostrar o estado de quem
   atende), e duas cópias do mapa divergiriam no próximo estado novo -- foi
   o que quase aconteceu com o `offline` da 044.

   `atendente.estado` existe desde a migração 001. Valor novo no `CHECK` do
   banco obriga a olhar AQUI. */
export const ESTADO = {
  disponivel: { rotulo: 'disponível', cor: 'var(--ok)' },
  ausente: { rotulo: 'em pausa', cor: 'var(--aviso)' },
  nao_perturbe: { rotulo: 'não perturbe', cor: 'var(--erro)' },
  /* Entrou com a 044 (17/09). Sem esta linha, quem escolhesse "fora do
     expediente" apareceria como "sem estado", que é o rótulo de quem nunca
     escolheu nada. */
  offline: { rotulo: 'fora do expediente', cor: 'var(--texto-apagado)' },
}

export function corDoEstado(estado) {
  return (ESTADO[estado] || {}).cor || 'var(--texto-apagado)'
}

export function rotuloDoEstado(estado) {
  return (ESTADO[estado] || {}).rotulo || 'sem estado'
}
