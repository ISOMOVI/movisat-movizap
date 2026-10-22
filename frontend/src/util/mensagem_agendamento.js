/* ============================================================================
   As duas mensagens do agendamento — a do cliente e a do técnico.
   ----------------------------------------------------------------------------
   🚨 ESTE ARQUIVO EXISTE PARA HAVER UMA SÓ VERSÃO DO TEXTO. Ele nasceu dentro
   do `ModalAgendar.vue` (21/10) e saiu de lá quando a `ATD_7.1` ganhou
   "Reenviar confirmação" (ponta 2 do plano): a mesma mensagem montada em dois
   lugares viraria duas mensagens diferentes no primeiro ajuste de campo -- e a
   do cliente é a única que sai para fora da casa.

   🔵 REGRA DE AGRUPAMENTO DECLARADA POR ELE: mesma DATA e HORA => UMA mensagem
   só, com as placas e as OS somadas. Sem isso o cliente receberia três
   mensagens iguais variando a placa.

   🚨 ESTE MÓDULO NÃO ENVIA NADA, e não sabe enviar. Decisão 6 dele: as duas
   confirmações saem pré-escritas e **quem envia é o atendente**.
   ============================================================================ */

export function dataBr(valor) {
  return new Date(valor).toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' })
}

export function horaBr(valor) {
  return new Date(valor).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
}

/* A chave do agrupamento: data + hora, nada mais. ⚠️ Cliente NÃO entra aqui de
   propósito -- quem chama já trabalha dentro de um cliente (a aba Confirmar
   lista um cliente só; a `ATD_7.1` filtra pelo cliente da linha). Pôr o
   cliente na chave esconderia esse contrato em vez de deixá-lo à vista. */
export function chaveDoGrupo(agendamento) {
  return `${dataBr(agendamento.inicio)} ${horaBr(agendamento.inicio)}`
}

export function agrupar(lista) {
  const grupos = new Map()
  for (const a of lista) {
    const chave = chaveDoGrupo(a)
    if (!grupos.has(chave)) grupos.set(chave, [])
    grupos.get(chave).push(a)
  }
  return [...grupos.values()]
}

/* As duas mensagens de um grupo.

   `responsavelPadrao` é o que a aba Confirmar está digitando agora: na
   `ATD_7.1` não existe, e aí vale o que está gravado no compromisso.

   ⚠️ COMPROMISSO AINDA `aguardando` NÃO TEM RESPONSÁVEL, e o texto sai com o
   campo vazio em vez de inventar nome. Quem desenha a tela diz por quê --
   `semResponsavel` abaixo é o que permite dizer. */
export function textosDoGrupo(grupo, { responsavelPadrao = '' } = {}) {
  const primeiro = grupo[0]
  const placas = [...new Set(grupo.flatMap(
    (a) => (a.ordens || []).map((o) => o.placa).filter(Boolean)))]
  const ordens = [...new Set(grupo.flatMap((a) => (a.ordens || []).map((o) => o.numero_os)))]
  const orcamentos = [...new Set(grupo.map((a) => a.orcamento_numero).filter(Boolean))]
  const placasTexto = placas.length ? placas.join(', ') : 'sem placa registrada'

  /* 🚨 O CABEÇALHO IMPRIME O TIPO DA OS, e esta é a única mensagem que sai
     para o CLIENTE (§7.4 do plano; era a palavra `(SERVIÇO)` literal até
     21/10). O nome vem GRAVADO no compromisso (migração 072), retrato do
     momento do agendamento.

     ⚠️ SEM NOME, O SEGMENTO SAI FORA -- inteiro, parênteses e barra incluídos.
     173 das 547 OS têm `tipo` fora da lista do Harmonit (nove ids medidos em
     21/10), e para elas não existe nome a imprimir: `(tipo 57)` não diz nada
     ao cliente, e inventar rótulo é tela que mente.

     ⚠️ Um grupo pode juntar OS de tipos diferentes (a regra de agrupamento é
     data + hora, não tipo): então sai a lista dos tipos distintos, como as
     placas já faziam. */
  const tipos = [...new Set(grupo.flatMap(
    (a) => (a.ordens || []).map((o) => o.tipo_nome).filter(Boolean)))]

  const responsavel = primeiro.responsavel_cliente || responsavelPadrao || ''

  const cabecalho = [
    tipos.length ? `(${tipos.join(', ').toUpperCase()})` : null,
    placasTexto,
    primeiro.cliente_nome,
  ].filter(Boolean).join(' | ')

  const corpo = [
    `DATA: ${dataBr(primeiro.inicio)}`,
    `HORÁRIO: ${horaBr(primeiro.inicio)}`,
    `ENDEREÇO: ${primeiro.endereco || '—'}`,
    `TÉCNICO RESPONSÁVEL: ${primeiro.tecnico_nome || '—'}`,
    `VEÍCULO(S) / PLACA(S): ${placasTexto}`,
    `RESPONSÁVEL DO CLIENTE POR ACOMPANHAR O TÉCNICO: ${responsavel || ''}`,
  ]
  const doCliente = [cabecalho, '', ...corpo].join('\n')
  const doTecnico = [
    cabecalho, '', ...corpo,
    `OS: ${ordens.join(', ') || '—'}`,
    orcamentos.length ? `ORÇAMENTO ${orcamentos.join(', ')}` : 'ORÇAMENTO —',
  ].join('\n')

  return {
    doCliente,
    doTecnico,
    // Para a tela poder EXPLICAR o campo vazio, em vez de entregar um texto
    // truncado e deixar o operador descobrir sozinho.
    semResponsavel: !responsavel,
    quantos: grupo.length,
    ordens,
  }
}
