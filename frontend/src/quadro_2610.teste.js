/**
 * A "base quadrada de resposta" (26/10) — o quadro alinhado das mensagens.
 *
 * 🔵 Decisão dele: o corpo da mensagem de agendamento passa a ser um quadro,
 * rótulo à esquerda, pontinhos, valor à direita.
 *
 * 🚨 O QUE ESTE ARQUIVO PRENDE, E O `agendar_2110` NÃO: a FORMA. Lá se mede se
 * o conteúdo certo está na mensagem; aqui se mede que ele está alinhado, que o
 * bloco vem cercado por ``` (sem a cerca o WhatsApp usa fonte proporcional e o
 * quadro sai torto) e que nenhuma linha passa da largura (linha comprida é
 * quebrada pelo celular, e quebra do celular destrói o alinhamento).
 *
 * ⚠️ NENHUM TESTE VÊ FONTE (`M9`). O que se prova aqui é a geometria do texto;
 * se 36 colunas é a largura certa no celular dele, só o celular dele diz.
 */
import { describe, it, expect } from 'vitest'

import { quadro, textosDoGrupo, LARGURA } from './util/mensagem_agendamento.js'

/* O caso do desenho dele. */
const GRUPO = [{
  inicio: '2026-10-26T14:30:00-03:00',
  endereco: 'Rua X, 123 · Centro · Pres. Prudente - SP',
  tecnico_nome: 'João',
  cliente_nome: 'Velasco Leite Pastelaria ME',
  responsavel_cliente: 'Dona Maria',
  orcamento_numero: 1668,
  ordens: [{ numero_os: 16548, placa: 'ABC1D23', tipo_nome: 'Instalação' },
           { numero_os: 16549, placa: 'EFG4H56', tipo_nome: 'Instalação' }],
}]

/* Endereço real dos sete campos da migração 073. */
const LONGO = [{
  ...GRUPO[0],
  endereco: 'Rua Joaquim Nabuco, 1234 · Jardim Bongiovani · Sala 3 · '
            + 'Presidente Prudente - SP · CEP 19013180',
  tecnico_nome: 'Iago Santos do Ó Souza',
}]

function dentroDaCerca(texto) {
  const partes = texto.split('```')
  expect(partes).toHaveLength(3)   // antes, dentro, depois
  return partes[1].split('\n').filter((l) => l.length)
}

function comprimento(linha) {
  return linha.normalize('NFC').length
}

describe('o quadro', () => {
  it('alinha o valor na MESMA coluna, qualquer que seja o rótulo', () => {
    const linhas = quadro([
      ['DATA', '26/10'],
      ['HORÁRIO', '14:30'],
      ['ACOMPANHA', 'Dona Maria'],
    ])
    const colunas = linhas.map((l) => l.search(/ \S/, l.indexOf('. ')))
    /* Mede a coluna do VALOR: todas as linhas têm de começar o valor no mesmo
       lugar, que é a definição de quadro alinhado. */
    const inicios = linhas.map((l) => l.lastIndexOf('. ') + 2)
    expect(new Set(inicios).size).toBe(1)
    expect(colunas.length).toBe(3)
  })

  it('a largura da coluna sai do rótulo MAIS LONGO, não de um número cravado', () => {
    const curto = quadro([['DATA', 'x'], ['OS', 'y']])
    const longo = quadro([['DATA', 'x'], ['ACOMPANHA', 'y']])
    const colunaCurto = curto[0].lastIndexOf('. ') + 2
    const colunaLongo = longo[0].lastIndexOf('. ') + 2
    expect(colunaLongo).toBeGreaterThan(colunaCurto)
  })

  it('🚨 acento não desalinha (NFC × NFD)', () => {
    /* "HORÁRIO" tem 7 caracteres em NFC e 8 em NFD. Sem normalizar, a coluna
       sairia errada por um -- e num quadro alinhado isso é o defeito inteiro. */
    const nfd = 'HORÁRIO'.normalize('NFD')
    expect(nfd.length).not.toBe('HORÁRIO'.normalize('NFC').length)
    const linhas = quadro([['DATA', '26/10'], [nfd, '14:30']])
    const inicios = linhas.map((l) => l.lastIndexOf('. ') + 2)
    expect(new Set(inicios).size).toBe(1)
  })

  it('valor vazio sai sem traço inventado e sem espaço solto no fim', () => {
    /* Decisão de 21/10: compromisso `aguardando` não tem responsável, e o
       texto NÃO inventa nome. Um `—` ali faria um campo que espera ser
       preenchido parecer resolvido. */
    const [linha] = quadro([['ACOMPANHA', '']])
    expect(linha).toBe('ACOMPANHA ...')
    expect(linha).not.toContain('—')
    expect(linha).toBe(linha.trimEnd())
  })

  it('nenhuma linha passa da largura', () => {
    for (const linhas of [quadro([['ENDEREÇO', 'A'.repeat(90)]]),
                          quadro([['PLACA(S)', Array(12).fill('ABC1D23').join(', ')]])]) {
      for (const l of linhas) expect(comprimento(l)).toBeLessThanOrEqual(LARGURA)
    }
  })

  it('não parte palavra quando dá para quebrar na junta do dado', () => {
    const linhas = quadro([['PLACA(S)', 'FZU5D16, ABC1D23, XYZ9W87']])
    expect(linhas.join('\n')).toContain('FZU5D16')
    expect(linhas.join('\n')).toContain('XYZ9W87')
    for (const l of linhas) expect(l).not.toMatch(/[A-Z]{3}\d$/)  // placa cortada
  })

  /* ⚠️ Os três testes abaixo montam o quadro com os MESMOS rótulos da mensagem
     de verdade (`ACOMPANHA`, 9 letras, é o mais longo). Medir o endereço num
     quadro de um rótulo só daria outra largura de coluna -- e foi exatamente
     esse o meu erro ao escrever este arquivo: a asserção cravava 14 colunas
     enquanto a chamada produzia 13. O teste tem de exercitar a geometria que
     o cliente recebe. */
  const COMO_NA_MENSAGEM = (endereco) => quadro([
    ['ENDEREÇO', endereco],
    ['ACOMPANHA', 'Dona Maria'],
  ])

  it('o separador NÃO fica pendurado no fim da linha', () => {
    const linhas = COMO_NA_MENSAGEM(GRUPO[0].endereco)
    for (const l of linhas) {
      expect(l.trimEnd()).not.toMatch(/·$/)
      expect(l.trimEnd()).not.toMatch(/,$/)
    }
  })

  it('valor que cabe em duas linhas fica AO LADO do rótulo', () => {
    /* É o caso do desenho dele: "Rua X, 123 · Centro" + a continuação. */
    const linhas = COMO_NA_MENSAGEM(GRUPO[0].endereco)
    expect(linhas[0]).toMatch(/^ENDEREÇO \.+ Rua X, 123 · Centro$/)
    /* a 3ª é a linha do ACOMPANHA */
    expect(linhas).toHaveLength(3)
    expect(linhas[1]).toMatch(/^ {14}Pres\. Prudente - SP$/)
  })

  it('valor que não cabe desce para BAIXO do rótulo, com a linha quase inteira', () => {
    /* Ao lado sobram ~22 colunas, e um endereço real não cabe: forçá-lo ali
       daria "Presidente Prudente -" / "SP". Embaixo, cada pedaço (rua, bairro,
       complemento, cidade, CEP) cabe numa linha só. */
    const linhas = COMO_NA_MENSAGEM(LONGO[0].endereco)
    expect(linhas[0]).toBe('ENDEREÇO ....')
    expect(linhas).toContain('  Rua Joaquim Nabuco, 1234')
    expect(linhas).toContain('  Jardim Bongiovani')
    expect(linhas).toContain('  Presidente Prudente - SP')
    expect(linhas).toContain('  CEP 19013180')
  })
})

describe('as duas mensagens', () => {
  it('🚨 vêm cercadas por ``` — sem isso o quadro sai torto no WhatsApp', () => {
    /* O WhatsApp usa fonte PROPORCIONAL: pontinhos só alinham em
       monoespaçado, e as três crases são o que põe o bloco em monoespaçado.
       Sem a cerca, a entrega inteira não acontece. */
    const { doCliente, doTecnico } = textosDoGrupo(GRUPO)
    expect(doCliente).toContain('```')
    expect(doTecnico).toContain('```')
    expect(dentroDaCerca(doCliente).length).toBeGreaterThan(3)
  })

  it('o cabeçalho fica FORA da cerca', () => {
    /* Ele é comprido por natureza (tipo | placas | cliente) e, dentro do
       monoespaçado, quebraria em três linhas e sujaria o quadro. Fora, o
       WhatsApp quebra onde couber sem desalinhar nada. */
    const { doCliente } = textosDoGrupo(GRUPO)
    const antes = doCliente.split('```')[0]
    expect(antes).toContain('Velasco Leite Pastelaria ME')
    expect(antes).toContain('(INSTALAÇÃO)')
    expect(dentroDaCerca(doCliente).join('\n')).not.toContain('Velasco Leite')
  })

  it('nenhuma linha do quadro passa da largura, nos dois textos', () => {
    for (const grupo of [GRUPO, LONGO]) {
      const { doCliente, doTecnico } = textosDoGrupo(grupo)
      for (const texto of [doCliente, doTecnico]) {
        for (const l of dentroDaCerca(texto)) {
          expect(comprimento(l)).toBeLessThanOrEqual(LARGURA)
        }
      }
    }
  })

  it('a do técnico tem OS e ORÇAMENTO; a do cliente, não', async () => {
    const { doCliente, doTecnico } = textosDoGrupo(GRUPO)
    expect(doTecnico).toMatch(/OS \.+ 16548, 16549/)
    expect(doTecnico).toMatch(/ORÇAMENTO \.+ 1668/)
    expect(doCliente).not.toContain('ORÇAMENTO')
  })

  it('o quadro do técnico continua alinhado com as duas linhas a mais', () => {
    /* `ORÇAMENTO` tem 9 letras e entra só na mensagem do técnico: se a largura
       fosse cravada em vez de calculada, esta mensagem sairia torta. */
    const linhas = dentroDaCerca(textosDoGrupo(GRUPO).doTecnico)
    const comRotulo = linhas.filter((l) => /^[A-ZÇÁÉÍÓÚÃÕ()\s]+\.{3,} \S/.test(l))
    const inicios = comRotulo.map((l) => l.lastIndexOf('. ') + 2)
    expect(comRotulo.length).toBeGreaterThanOrEqual(6)
    expect(new Set(inicios).size).toBe(1)
  })

  it('os seis campos do cliente estão lá, com os rótulos curtos', () => {
    const dentro = dentroDaCerca(textosDoGrupo(GRUPO).doCliente).join('\n')
    for (const rotulo of ['DATA', 'HORÁRIO', 'ENDEREÇO', 'TÉCNICO',
                          'PLACA(S)', 'ACOMPANHA']) {
      expect(dentro).toContain(rotulo)
    }
    /* Os rótulos longos de antes de 26/10 não voltam: eles empurravam o valor
       para fora do celular. */
    expect(dentro).not.toContain('RESPONSÁVEL DO CLIENTE')
    expect(dentro).not.toContain('VEÍCULO(S)')
  })
})
