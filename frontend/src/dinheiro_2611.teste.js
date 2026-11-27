/**
 * `util/dinheiro.js` — a conversão de pt-BR, medida direto na função.
 *
 * 🚨 POR QUE ESTE ARQUIVO EXISTE. Em 26/11 a Aline emitiu um orçamento
 * digitando `60,00` no preço e leu *"Erro interno"*, duas vezes. A tela
 * validava a vírgula (`Number(texto.replace(',', '.'))`) e o POST mandava a
 * vírgula; o servidor lê com `Decimal`, que não a conhece, e `InvalidOperation`
 * não é `ValueError` — então escapava do 400 e virava 500.
 *
 * ⚠️ E O MAIS CARO DE TUDO: o helper `emitir()` do `agendar_2110.teste.js` já
 * digitava `'1,00'` e `'77,7'` desde 21/10. A suíte ficou verde cinco semanas
 * porque **nenhum teste lia o corpo do POST** — só o que a tela desenhava
 * depois. Teste que não olha o que atravessa a ponte não vê a ponte quebrar.
 *
 * O que se protege aqui é a função; o corpo do POST está no
 * `agendar_2110.teste.js`, junto do modal que o monta.
 */
import { describe, it, expect } from 'vitest'

import { comoNumero, paraCanonico, paraCentavos, paraReais }
  from './util/dinheiro.js'

describe('paraCentavos — reais escritos em pt-BR', () => {
  it('lê a vírgula, que é o que a pessoa digita', () => {
    expect(paraCentavos('60,00')).toBe(6000)
    expect(paraCentavos('199,90')).toBe(19990)
    expect(paraCentavos('1,5')).toBe(150)
  })

  it('lê o ponto também, porque é o que volta do servidor', () => {
    expect(paraCentavos('60.00')).toBe(6000)
    expect(paraCentavos(60)).toBe(6000)
  })

  it('🚨 199,90 não vira 19989 — o arredondamento é no inteiro', () => {
    expect(paraCentavos('199,90')).toBe(19990)
    expect(paraCentavos('0,07')).toBe(7)
    expect(paraCentavos('8,15')).toBe(815)
  })

  it('🚨 VAZIO é null e NÃO É NÚMERO é undefined — são coisas diferentes', () => {
    // Na ficha do técnico, branco é "não oferece" e zero é "cobra zero"
    // (cortesia, decisão dele de 04/11). Confundir os dois apaga a cortesia.
    expect(paraCentavos('')).toBe(null)
    expect(paraCentavos(null)).toBe(null)
    expect(paraCentavos('   ')).toBe(null)
    expect(paraCentavos('0')).toBe(0)
    expect(paraCentavos('0,00')).toBe(0)
  })

  it('recusa o que não é número, em vez de chutar', () => {
    expect(paraCentavos('abc')).toBe(undefined)
    expect(paraCentavos('R$ 60,00')).toBe(undefined)
    expect(paraCentavos('-5')).toBe(undefined)
  })

  it('⚠️ "1.000,00" é RECUSADO, e isso é de propósito', () => {
    // Mil reais para quem digita, e 1 para o `Decimal` do servidor. Entre
    // recusar e adivinhar, recusa — palpite viraria valor errado em silêncio.
    expect(paraCentavos('1.000,00')).toBe(undefined)
  })

  it('ignora espaço, inclusive no meio', () => {
    expect(paraCentavos(' 60,00 ')).toBe(6000)
    expect(paraCentavos('6 0,00')).toBe(6000)
  })
})

describe('paraReais — o que entra no campo', () => {
  it('escreve com vírgula e duas casas', () => {
    expect(paraReais(19990)).toBe('199,90')
    expect(paraReais(0)).toBe('0,00')
    expect(paraReais(5)).toBe('0,05')
  })

  it('vazio continua vazio: null e undefined não desenham "0,00"', () => {
    expect(paraReais(null)).toBe('')
    expect(paraReais(undefined)).toBe('')
  })

  it('ida e volta não perde valor', () => {
    for (const texto of ['0,00', '1,00', '77,70', '199,90', '1234,56']) {
      expect(paraReais(paraCentavos(texto))).toBe(texto)
    }
  })
})

describe('comoNumero — a conta que a tela mostra', () => {
  it('devolve NaN no que não é número, para `> 0` recusar sozinho', () => {
    expect(Number.isNaN(comoNumero(''))).toBe(true)
    expect(Number.isNaN(comoNumero('abc'))).toBe(true)
    expect(comoNumero('77,7') > 0).toBe(true)
    expect(comoNumero('0') > 0).toBe(false)
  })
})

describe('paraCanonico — o que ATRAVESSA a ponte', () => {
  it('🚨 a vírgula para aqui: o que sai tem ponto', () => {
    expect(paraCanonico('60,00')).toBe('60')
    expect(paraCanonico('77,7')).toBe('77.7')
    expect(paraCanonico('1,5')).toBe('1.5')
  })

  it('o que já está canônico passa igual', () => {
    expect(paraCanonico('77.7')).toBe('77.7')
    expect(paraCanonico('1')).toBe('1')
  })

  it('zero atravessa — é a cortesia, não um vazio', () => {
    expect(paraCanonico('0')).toBe('0')
    expect(paraCanonico('0,00')).toBe('0')
  })

  it('o que o servidor não leria não sai daqui', () => {
    expect(paraCanonico('')).toBe(undefined)
    expect(paraCanonico('R$ 60,00')).toBe(undefined)
    expect(paraCanonico('1.000,00')).toBe(undefined)
    expect(paraCanonico(null)).toBe(undefined)
  })

  it('⚠️ não inventa casa decimal que a pessoa não digitou', () => {
    // `String(Number(x))` normaliza a forma e nada mais: o arredondamento do
    // dinheiro é do servidor, que é quem imprime o papel.
    expect(paraCanonico('1,10')).toBe('1.1')
    expect(paraCanonico('100')).toBe('100')
  })
})
