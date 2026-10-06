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

/* 🔵 05/10 (decisão dele): o `offline` tem DOIS significados. Quando a régua de
   inatividade o põe DENTRO do turno, a pessoa está só inativa, não fora do
   expediente -- o rótulo é "Ausente". "Fora do expediente" fica para quem
   escolheu o estado à mão, ou para o offline posto FORA do turno (fim de dia).
   Os flags vêm do backend por atendente (`estado_automatico` e `em_jornada`);
   sem eles, o comportamento é o de antes ("fora do expediente"). */
export function rotuloDoEstado(estado, { automatico = false, emJornada = false } = {}) {
  if (estado === 'offline' && automatico && emJornada) return 'Ausente'
  return (ESTADO[estado] || {}).rotulo || 'sem estado'
}
