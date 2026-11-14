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
  /* 🔵 19/10: `nao_perturbe` SAIU (migração 068, decisão dele: *"pode
     remover esse status então"*). O motivo: ele não perturbava nada -- quem
     barra receber conversa é `presenca.pode_receber`, e lá só offline e
     afastamento barram. A pessoa marcava, continuava recebendo, e o botão não
     dizia isso. ⚠️ Valor que sumir do `CHECK` tem de sumir daqui também, senão
     a tela mostra "sem estado" para uma linha antiga. */
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

/* 🔵 13/11, DELE: *"pode colocar à frente do nome, 'status a x minutos' ...
   pode fazer em múltiplos de 10min arredondado = 'ausente há 30min'"*.

   🚨 QUEM CONTA É O SERVIDOR (`chat.minutos_no_estado`); aqui só se arredonda.
   O relógio do navegador de quem olha não entra na conta -- máquina com a hora
   errada diria "online há 3 horas" sobre quem acabou de entrar.

   ⚠️ ABAIXO DE 10 MIN É "agora", e não "há 0min": arredondar para baixo em
   múltiplos de 10 faria todo mundo que acabou de mudar de estado aparecer com
   zero, que é um número que não diz nada.
   ⚠️ `null`/`undefined` devolve vazio -- é o caso de quem não tem hora de
   estado gravada, e inventar "há 0min" seria afirmar o que ninguém sabe. */
export function tempoNoEstado(minutos) {
  if (minutos === null || minutos === undefined || Number.isNaN(Number(minutos))) return ''
  const m = Math.max(0, Math.floor(Number(minutos)))
  if (m < 10) return 'agora'
  if (m < 60) return `há ${Math.floor(m / 10) * 10}min`
  const h = Math.floor(m / 60)
  if (h < 24) return `há ${h}h`
  const d = Math.floor(h / 24)
  return d === 1 ? 'há 1 dia' : `há ${d} dias`
}
