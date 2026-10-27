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

   ── 26/10: A "BASE QUADRADA DE RESPOSTA" ───────────────────────────────────
   🔵 Decisão dele: o corpo da mensagem passa a ser um **quadro alinhado**,
   rótulo à esquerda, pontinhos, valor à direita.

   🚨 E ISSO SÓ FUNCIONA DENTRO DE ``` (TRÊS CRASES). O WhatsApp usa fonte
   PROPORCIONAL: em fonte proporcional, pontinhos NÃO alinham — cada letra tem
   largura diferente, e o quadro sairia torto. As três crases põem o bloco em
   **monoespaçado**, e é isso que também o desenha numa caixa. Sem a cerca, a
   entrega inteira não acontece.

   🚨 CONSEQUÊNCIA: A LINHA TEM TETO. Monoespaçado no celular quebra linha
   sozinho se ela for comprida, e linha quebrada pelo celular destrói o
   alinhamento que o quadro existe para ter. Daí `LARGURA` e a quebra ser
   NOSSA, em pedaço inteiro (segmento de endereço, placa), nunca no meio de
   uma palavra.

   ⚠️ OS RÓTULOS ENCURTARAM, e é parte do desenho: `RESPONSÁVEL DO CLIENTE POR
   ACOMPANHAR O TÉCNICO` tem 48 caracteres e, como rótulo de coluna, empurraria
   o valor para fora de qualquer celular. Ficou `ACOMPANHA`. O mesmo com
   `VEÍCULO(S) / PLACA(S)` -> `PLACA(S)` e `TÉCNICO RESPONSÁVEL` -> `TÉCNICO`.
   ============================================================================ */

/* O teto da linha, em caracteres, DENTRO do bloco monoespaçado.

   ⚠️ 36 é escolha medida contra o desenho dele, não número mágico: o rótulo
   mais longo (`ACOMPANHA`/`ORÇAMENTO`, 9) mais os pontinhos e os espaços dão
   14 de prefixo, e "Pres. Prudente - SP" (19) tem de caber na continuação --
   14 + 19 = 33. Com 36 sobra folga para cidade um pouco maior sem o celular
   quebrar por conta. 🚨 Só o celular DELE decide se está certo: nenhum teste
   vê fonte (`M9`). */
export const LARGURA = 36

/* Quantos pontinhos no mínimo, depois do rótulo mais longo. Três é o que o
   desenho dele mostra. */
const PONTOS_MINIMOS = 3

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

/* 🚨 `length` de texto acentuado depende da FORMA. "HORÁRIO" tem 7 caracteres
   em NFC e 8 em NFD (o acento vira caractere separado), e a largura da coluna
   sairia errada por um — num quadro alinhado, isso é o defeito inteiro.
   Normalizar aqui é mais barato que descobrir depois no celular. */
function largura(texto) {
  return String(texto).normalize('NFC').length
}

/* Os separadores que o valor já usa, do mais semântico para o menos: o ` · `
   monta a linha de endereço (`agendamento.linha_do_endereco`), e a `, ` junta
   placas e OS. Quebrar por eles é quebrar onde o dado já tem junta. */
const SEPARADORES = [' · ', ', ']

function pedacos(texto) {
  for (const sep of SEPARADORES) {
    if (texto.includes(sep)) return { partes: texto.split(sep), sep }
  }
  return { partes: [texto], sep: ' ' }
}

/* Junta os pedaços em linhas que caibam, sem partir palavra.

   ⚠️ O SEPARADOR NÃO FICA PENDURADO no fim da linha. `Centro ·` com o resto na
   linha seguinte é sujeira: a própria quebra já separa, e o desenho dele não
   tem esse traço solto. */
function empacotar(partes, sep, disponivel) {
  /* ⚠️ A junção é o SEPARADOR COMO ELE É (` · `, `, `), não o sinal
     reembrulhado em espaços: `sep.trim()` entre espaços devolvia
     "ABC1D23 , EFG4H56", com espaço antes da vírgula. */
  const juncao = sep
  const linhas = []
  let atual = ''
  for (const parte of partes) {
    const candidato = atual ? atual + juncao + parte : parte
    if (atual && largura(candidato) > disponivel) {
      linhas.push(atual)
      atual = parte
    } else {
      atual = candidato
    }
  }
  if (atual) linhas.push(atual)
  return linhas
}

/* Quebra por espaço, e no fim por corte seco -- este último existe só para não
   haver caso sem resposta (uma palavra de 40 letras não deve derrubar a
   montagem da mensagem). */
function quebrarPorEspaco(texto, disponivel) {
  const linhas = empacotar(texto.split(' '), ' ', disponivel)
  return linhas.flatMap((l) => {
    if (largura(l) <= disponivel) return [l]
    const fatias = []
    for (let i = 0; i < l.length; i += disponivel) fatias.push(l.slice(i, i + disponivel))
    return fatias
  })
}

/* O quadro: `[[rótulo, valor], ...]` -> as linhas alinhadas.

   ⚠️ A largura da coluna é CALCULADA do rótulo mais longo do próprio quadro,
   nunca cravada: a mensagem do técnico tem duas linhas a mais (OS e ORÇAMENTO)
   e precisa continuar alinhada sozinha.

   ⚠️ Valor VAZIO sai com o rótulo e os pontinhos, e nada depois -- de
   propósito. É o caso do `ACOMPANHA` num compromisso ainda `aguardando`
   (decisão de 21/10: não se inventa nome). Um `—` ali faria um campo que
   ESPERA ser preenchido parecer resolvido. A linha é aparada no fim para não
   deixar espaço solto. */
export function quadro(pares, { larguraMaxima = LARGURA } = {}) {
  const maior = Math.max(...pares.map(([rotulo]) => largura(rotulo)))
  const prefixo = maior + 1 + PONTOS_MINIMOS + 1
  const aoLado = Math.max(8, larguraMaxima - prefixo)
  /* Abaixo do rótulo o valor ganha quase a linha inteira: o recuo é só o que
     mostra que aquelas linhas pertencem ao campo de cima. */
  const RECUO = 2
  const embaixo = Math.max(8, larguraMaxima - RECUO)

  const linhas = []
  for (const [rotuloCru, valor] of pares) {
    /* 🚨 NORMALIZA PARA EMITIR, não só para medir. Medir em NFC e escrever o
       rótulo como veio desalinha o quadro em um caractere quando o texto chega
       em NFD ("HORÁRIO" com o acento separado ocupa 8 unidades e desenha 7
       colunas). Achado pelo teste `acento não desalinha`, não pela leitura. */
    const rotulo = String(rotuloCru).normalize('NFC')
    const pontos = '.'.repeat(prefixo - largura(rotulo) - 2)
    const etiqueta = `${rotulo} ${pontos}`
    const texto = String(valor ?? '').normalize('NFC')
    const { partes, sep } = pedacos(texto)
    const ladoALado = empacotar(partes, sep, aoLado)

    /* 🚨 AS DUAS FORMAS, E A REGRA QUE ESCOLHE ENTRE ELAS.
       Ao lado do rótulo sobram ~22 caracteres, e isso basta para data, hora,
       técnico, placas -- e para o endereço CURTO do desenho dele
       ("Rua X, 123 · Centro" + "Pres. Prudente - SP", duas linhas). Mas um
       endereço real dos sete campos da migração 073 não cabe em 22: forçá-lo
       ali vira salada ("Presidente Prudente -" / "SP").
       Então: cabendo em até DUAS linhas, fica ao lado, alinhado -- que é o
       quadro que ele desenhou. Passando disso, o valor desce para baixo do
       rótulo com a linha quase inteira, e aí cada pedaço do endereço (rua,
       bairro, complemento, cidade, CEP) cabe numa linha só.
       ⚠️ A escolha é por CABER, não por nome de campo: amanhã um técnico de
       nome comprido cai na mesma régua, sem ninguém tocar aqui. */
    const serve = ladoALado.length <= 2
                  && ladoALado.every((l) => largura(l) <= aoLado)
    if (serve) {
      const [primeira, ...resto] = ladoALado
      linhas.push(`${etiqueta} ${primeira ?? ''}`.trimEnd())
      for (const l of resto) linhas.push(`${' '.repeat(prefixo)}${l}`.trimEnd())
      continue
    }

    linhas.push(etiqueta)
    for (const parte of partes) {
      for (const l of quebrarPorEspaco(parte, embaixo)) {
        linhas.push(`${' '.repeat(RECUO)}${l}`.trimEnd())
      }
    }
  }
  return linhas
}

/* A cerca do monoespaçado do WhatsApp. Ver o aviso do topo: sem ela o quadro
   sai torto, porque a fonte padrão é proporcional. */
function cercar(linhas) {
  return ['```', ...linhas, '```'].join('\n')
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

  /* 🚨 O CABEÇALHO FICA FORA DA CERCA, de propósito. Ele é a frase que
     identifica o serviço (tipo | placas | cliente) e é naturalmente comprido:
     dentro do monoespaçado, ele quebraria em duas ou três linhas e sujaria o
     quadro que vem embaixo. Fora, o WhatsApp o trata como texto normal e
     quebra onde couber, sem desalinhar nada. */
  const cabecalho = [
    tipos.length ? `(${tipos.join(', ').toUpperCase()})` : null,
    placasTexto,
    primeiro.cliente_nome,
  ].filter(Boolean).join(' | ')

  const camposComuns = [
    ['DATA', dataBr(primeiro.inicio)],
    ['HORÁRIO', horaBr(primeiro.inicio)],
    ['ENDEREÇO', primeiro.endereco || '—'],
    ['TÉCNICO', primeiro.tecnico_nome || '—'],
    ['PLACA(S)', placasTexto],
    ['ACOMPANHA', responsavel],
  ]

  const doCliente = [cabecalho, '', cercar(quadro(camposComuns))].join('\n')
  const doTecnico = [cabecalho, '', cercar(quadro([
    ...camposComuns,
    ['OS', ordens.join(', ') || '—'],
    ['ORÇAMENTO', orcamentos.join(', ') || '—'],
  ]))].join('\n')

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
